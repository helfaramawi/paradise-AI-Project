"""Specialised domain agents.

Each agent is a deterministic analytical module: it reads the validated dataset and the
quantitative simulation outputs through read-only tools and emits structured, bilingual
findings with explicit evidence, claim type, confidence and assumptions. No text here is a
pre-scripted transcript: every statement is computed from the current inputs.
"""

from __future__ import annotations

from collections.abc import Callable

from .base import AgentContext, Evidence, Finding, m

FUTURE_NAMES = {"A": ("Future A", "المستقبل أ"), "B": ("Future B", "المستقبل ب"), "C": ("Future C", "المستقبل ج")}


def _ds(ref: str, label: str, value: str) -> Evidence:
    return Evidence("dataset", ref, label, value, verified=False)


def _sim(ref: str, label: str, value: str) -> Evidence:
    return Evidence("simulation", ref, label, value)


def _fe(k: str) -> str:
    return FUTURE_NAMES[k][0]


def _fa(k: str) -> str:
    return FUTURE_NAMES[k][1]


# ======================================================================== phase 1
def strategy_analyze(ctx: AgentContext) -> list[Finding]:
    b, c = ctx.baseline, ctx.controls
    target = b.annual_opex * c.cost_reduction_target_pct / 100
    non_personnel = b.annual_opex - b.personnel_cost
    share = target / non_personnel * 100 if non_personnel else 0
    out = [
        Finding("strategy", "STR-01", "fact", "objective",
                f"Objective: reduce the EGP {m(b.annual_opex)}M cost base by {c.cost_reduction_target_pct:.0f}% "
                f"(EGP {m(target)}M run-rate) within {c.implementation_months} months, without terminations, "
                f"while protecting delivery, contracts and customer satisfaction.",
                f"الهدف: خفض قاعدة التكاليف البالغة {m(b.annual_opex)} مليون جنيه بنسبة {c.cost_reduction_target_pct:.0f}% "
                f"({m(target)} مليون سنوياً) خلال {c.implementation_months} أشهر دون إنهاء خدمة أحد، مع حماية التسليم "
                f"والعقود ورضا العملاء.",
                0.95, [_ds("baseline.annual_opex", "Annual operating cost base", f"EGP {m(b.annual_opex)}M"),
                       Evidence("assumption", "controls.cost_reduction_target_pct", "Target", f"{c.cost_reduction_target_pct:.0f}%")]),
        Finding("strategy", "STR-02", "estimate", "feasibility",
                f"With personnel cost (EGP {m(b.personnel_cost)}M) protected by the no-termination constraint, the "
                f"target equals {share:.0f}% of the remaining EGP {m(non_personnel)}M addressable spend. "
                f"This is a structurally demanding target.",
                f"مع حماية تكلفة الموظفين ({m(b.personnel_cost)} مليون) بقيد عدم الإنهاء، يعادل الهدف {share:.0f}% "
                f"من الإنفاق القابل للخفض البالغ {m(non_personnel)} مليون. هذا هدف صعب هيكلياً.",
                0.8, [_ds("baseline.personnel_cost", "Personnel cost (synthetic assumption)", f"EGP {m(b.personnel_cost)}M")],
                ["Personnel cost decomposition is a synthetic assumption"]),
        Finding("strategy", "STR-03", "recommendation", "success_criteria",
                f"Success criteria: run-rate savings ≥ EGP {m(target)}M by month {c.implementation_months}; "
                f"delay increase ≤ {c.acceptable_delay_increase_pct:.1f} pts; CSAT ≥ {c.min_csat_pct:.0f}%; "
                f"zero terminations; implementation cost ≤ EGP {m(c.implementation_budget)}M.",
                f"معايير النجاح: وفورات سنوية ≥ {m(target)} مليون بحلول الشهر {c.implementation_months}؛ زيادة التأخير "
                f"≤ {c.acceptable_delay_increase_pct:.1f} نقطة؛ رضا العملاء ≥ {c.min_csat_pct:.0f}%؛ صفر إنهاء خدمة؛ "
                f"تكلفة التنفيذ ≤ {m(c.implementation_budget)} مليون.",
                0.9, [Evidence("assumption", "controls", "Executive controls", "user-defined")]),
    ]
    return out


def cfo_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    cats = {k: v for k, v in b.cost_categories.items() if k != "personnel"}
    ranked = sorted(cats.items(), key=lambda kv: kv[1], reverse=True)
    top = ", ".join(f"{k} {m(v)}M" for k, v in ranked[:3])
    top_ar = "، ".join(f"{k} {m(v)} مليون" for k, v in ranked[:3])
    op_profit = b.annual_revenue - b.annual_opex
    dq2 = next((x for x in ctx.validation.checks if x.code == "DQ-002"), None)
    out = [
        Finding("cfo", "CFO-01", "fact", "cost_structure",
                f"Largest addressable (non-personnel) categories: {top}. Contractors are the single largest "
                f"addressable item at {b.contractor_cost / b.annual_opex * 100:.0f}% of the cost base.",
                f"أكبر فئات الإنفاق القابلة للخفض: {top_ar}. المتعاقدون أكبر بند منفرد بنسبة "
                f"{b.contractor_cost / b.annual_opex * 100:.0f}% من قاعدة التكاليف.",
                0.85, [_ds("baseline.contractor_cost", "External contractor cost", f"EGP {m(b.contractor_cost)}M"),
                       _ds("baseline.software_cost", "Software licensing", f"EGP {m(b.software_cost)}M"),
                       _ds("baseline.infrastructure_cost", "Infrastructure", f"EGP {m(b.infrastructure_cost)}M")]),
        Finding("cfo", "CFO-02", "estimate", "profitability",
                f"Under the modelling interpretation (opex = total cost base) operating profit is EGP {m(op_profit)}M "
                f"({op_profit / b.annual_revenue * 100:.0f}% margin). The stated {b.gross_margin_pct:.0f}% gross margin "
                f"contradicts this and must be reconciled before financial sign-off.",
                f"وفق تفسير النموذج (المصروفات = إجمالي التكاليف) يبلغ الربح التشغيلي {m(op_profit)} مليون "
                f"(هامش {op_profit / b.annual_revenue * 100:.0f}%). هامش الربح الإجمالي المذكور {b.gross_margin_pct:.0f}% "
                f"يتعارض مع ذلك ويجب تسويته قبل الاعتماد المالي.",
                0.5, [Evidence("validation", "DQ-002", "Gross margin consistency check",
                               dq2.severity if dq2 else "n/a", verified=True)],
                ["Opex represents the total cost base"]),
        Finding("cfo", "CFO-03", "recommendation", "cash",
                f"Implementation spend must be funded from an opening cash position of EGP {m(b.opening_cash)}M "
                f"(synthetic). Front-loaded investments should be phased to keep cash above zero.",
                f"يجب تمويل إنفاق التنفيذ من رصيد نقدي افتتاحي {m(b.opening_cash)} مليون (افتراضي). ينبغي تقسيط "
                f"الاستثمارات المبكرة للحفاظ على رصيد نقدي موجب.",
                0.7, [_ds("baseline.opening_cash", "Opening cash (synthetic assumption)", f"EGP {m(b.opening_cash)}M")]),
    ]
    return out


def coo_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    head = b.max_sustainable_utilization_pct - b.utilization_pct
    buffer = b.contractual_delay_tolerance_pct - b.avg_project_delay_pct
    return [
        Finding("coo", "COO-01", "fact", "capacity",
                f"Utilisation is {b.utilization_pct:.0f}% against a {b.max_sustainable_utilization_pct:.0f}% sustainable "
                f"ceiling: {head:.0f} pts (~{b.employees * head / 100:.1f} FTE) of raw headroom before skill matching.",
                f"الاستغلال {b.utilization_pct:.0f}% مقابل حد مستدام {b.max_sustainable_utilization_pct:.0f}%: هامش {head:.0f} "
                f"نقطة (حوالي {b.employees * head / 100:.1f} موظف) قبل مطابقة المهارات.",
                0.8, [_ds("baseline.utilization_pct", "Resource utilisation", f"{b.utilization_pct:.0f}%")]),
        Finding("coo", "COO-02", "fact", "bottleneck",
                f"Average project delay is already {b.avg_project_delay_pct:.0f}%, leaving only {buffer:.0f} pts before "
                f"the assumed {b.contractual_delay_tolerance_pct:.0f}% contractual tolerance. Delivery is the binding bottleneck.",
                f"متوسط تأخير المشروعات {b.avg_project_delay_pct:.0f}% بالفعل، أي هامش {buffer:.0f} نقطة فقط قبل حد "
                f"التأخير التعاقدي المفترض {b.contractual_delay_tolerance_pct:.0f}%. التسليم هو عنق الزجاجة.",
                0.8, [_ds("baseline.avg_project_delay_pct", "Average project delay", f"{b.avg_project_delay_pct:.0f}%"),
                      Evidence("assumption", "baseline.contractual_delay_tolerance_pct", "Contractual delay tolerance",
                               f"{b.contractual_delay_tolerance_pct:.0f}%")]),
        Finding("coo", "COO-03", "hypothesis", "automation",
                "Reporting, resource scheduling and back-office processes are plausible automation candidates. "
                "No process-mining data is available to confirm volumes.",
                "التقارير وجدولة الموارد وعمليات المكاتب الخلفية مرشحة للأتمتة. لا تتوفر بيانات تنقيب عمليات لتأكيد الأحجام.",
                0.4, [Evidence("assumption", "params.automation_productivity", "Automation productivity prior", "1.0–2.6 FTE/EGP M")],
                ["Automation candidates exist at sufficient volume"]),
    ]


def hr_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    return [
        Finding("hr", "HR-01", "fact", "constraint",
                f"No-termination constraint protects {b.employees} employees and EGP {m(b.personnel_cost)}M personnel cost "
                f"({b.personnel_cost / b.annual_opex * 100:.0f}% of the cost base). Savings must come from other categories.",
                f"قيد عدم الإنهاء يحمي {b.employees} موظفاً و{m(b.personnel_cost)} مليون من تكلفة الموظفين "
                f"({b.personnel_cost / b.annual_opex * 100:.0f}% من التكاليف). يجب أن تأتي الوفورات من فئات أخرى.",
                0.9, [_ds("baseline.employees", "Employees", str(b.employees))]),
        Finding("hr", "HR-02", "assumption", "skills",
                "No skills inventory is available. Whether internal staff can absorb contractor work is UNVERIFIED; "
                "the model uses a 35–75% skill-match prior.",
                "لا يتوفر سجل للمهارات. قدرة الموظفين على استيعاب أعمال المتعاقدين غير متحقق منها؛ يستخدم النموذج "
                "تقديراً لتوافق المهارات بين 35% و75%.",
                0.35, [Evidence("assumption", "params.skill_match", "Skill-match prior", "0.35 / 0.55 / 0.75")],
                ["Skill match 35–75%"]),
        Finding("hr", "HR-03", "recommendation", "retraining",
                f"Retraining programmes can raise skill match, but the training budget sits inside other G&A "
                f"(~EGP {m(b.other_ga_cost * b.training_share_of_other_ga)}M) and is exposed to expense freezes.",
                f"برامج إعادة التأهيل ترفع توافق المهارات، لكن ميزانية التدريب ضمن المصروفات العمومية "
                f"(حوالي {m(b.other_ga_cost * b.training_share_of_other_ga)} مليون) ومعرضة لتجميد الإنفاق.",
                0.6, [_ds("baseline.training_share_of_other_ga", "Training share of G&A (assumption)",
                          f"{b.training_share_of_other_ga:.0%}")]),
    ]


def delivery_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    share = b.contractor_fte / b.delivery_workload_fte * 100
    return [
        Finding("delivery", "DEL-01", "estimate", "dependency",
                f"Contractors supply ~{b.contractor_fte:.0f} FTE ({share:.0f}% of delivery workload) across "
                f"{b.active_projects} active projects. Removing them without replacement capacity directly reduces throughput.",
                f"يوفر المتعاقدون حوالي {b.contractor_fte:.0f} موظف مكافئ ({share:.0f}% من عبء التسليم) عبر "
                f"{b.active_projects} مشروعاً نشطاً. إزالتهم دون طاقة بديلة تخفض الإنتاجية مباشرة.",
                0.7, [_ds("baseline.contractor_cost", "Contractor cost", f"EGP {m(b.contractor_cost)}M"),
                      Evidence("assumption", "baseline.contractor_fte_cost", "Cost per contractor FTE", f"EGP {b.contractor_fte_cost}M")]),
    ]


def legal_analyze(ctx: AgentContext) -> list[Finding]:
    return [
        Finding("legal", "LEG-01", "hypothesis", "contracts",
                "No customer, contractor or vendor contracts have been provided. Notice periods, termination fees "
                "and liquidated-damages clauses are UNKNOWN. Any contract change requires review by qualified counsel.",
                "لم تُقدَّم عقود العملاء أو المتعاقدين أو الموردين. فترات الإخطار ورسوم الإنهاء وبنود التعويضات "
                "غير معروفة. أي تعديل في العقود يتطلب مراجعة مستشار قانوني مؤهل.",
                0.3, [Evidence("policy", "GOV-006", "Legal review of contract changes", "required", verified=True)]),
        Finding("legal", "LEG-02", "fact", "labour",
                "The no-termination constraint removes the main labour-law exposure. Changes to working hours or "
                "role scope may still need review under applicable labour regulations.",
                "قيد عدم الإنهاء يزيل أهم مخاطر قانون العمل. قد تحتاج تغييرات ساعات العمل أو نطاق الأدوار إلى مراجعة "
                "وفق لوائح العمل المعمول بها.",
                0.6, [Evidence("policy", "GOV-001", "No employee terminations", "enforced", verified=True)]),
    ]


def risk_analyze(ctx: AgentContext) -> list[Finding]:
    v = ctx.validation
    errors = [x.code for x in v.checks if x.severity == "error"]
    return [
        Finding("risk", "RSK-01", "fact", "data_quality",
                f"Data quality score {v.quality_score:.0%}. Errors: {', '.join(errors) or 'none'}. All figures are "
                f"synthetic; no historical outcomes exist to calibrate distributions.",
                f"درجة جودة البيانات {v.quality_score:.0%}. الأخطاء: {', '.join(errors) or 'لا يوجد'}. جميع الأرقام "
                f"افتراضية ولا توجد نتائج تاريخية لمعايرة التوزيعات.",
                0.9, [Evidence("validation", c, "Validation check", "error", verified=True) for c in errors]
                or [Evidence("validation", "DQ", "Validation", "ok", verified=True)]),
    ]


# ======================================================================== phase 2 (with simulation)
def _summ(f: dict, k: str, q: str = "p50") -> float:
    return f["summary"][k][q]


def cfo_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    target = ctx.controls.cost_reduction_target_pct
    for k in ("A", "B", "C"):
        f = ctx.fut(k)
        sav = _summ(f, "savings_pct_at_deadline")
        nb = _summ(f, "net_benefit_12m")
        impl = _summ(f, "one_off_implementation_cost")
        stance = "support" if sav >= max(_summ(ctx.fut(x), "savings_pct_at_deadline") for x in "ABC") - 1e-6 else (
            "conditional" if nb > 0 else "oppose")
        out.append(Finding(
            "cfo", f"CFO-F{k}", "estimate", "savings", strategy_key=k, stance=stance, phase="court",
            text_en=f"{_fe(k)} delivers a median {sav:.1f}% run-rate reduction (EGP {m(_summ(f, 'run_rate_savings_at_deadline'))}M) "
                    f"vs the {target:.0f}% target, with 12-month net benefit EGP {m(nb)}M after EGP {m(impl)}M implementation cost.",
            text_ar=f"{_fa(k)} يحقق خفضاً وسيطاً {sav:.1f}% ({m(_summ(f, 'run_rate_savings_at_deadline'))} مليون سنوياً) "
                    f"مقابل هدف {target:.0f}%، بصافي منفعة {m(nb)} مليون خلال 12 شهراً بعد تكلفة تنفيذ {m(impl)} مليون.",
            confidence=0.7,
            evidence=[_sim(f"futures.{k}.summary.savings_pct_at_deadline.p50", "Median savings %", f"{sav:.1f}%"),
                      _sim(f"futures.{k}.summary.net_benefit_12m.p50", "Median 12m net benefit", f"EGP {m(nb)}M")]))
    return out


def delivery_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    acc = ctx.controls.acceptable_delay_increase_pct
    for k in ("A", "B", "C"):
        f = ctx.fut(k)
        pp = f["project_portfolio"]
        d50 = _summ(f, "max_delay_increase_pct")
        d90 = _summ(f, "max_delay_increase_pct", "p90")
        n = pp["projects_at_risk"]
        stance = "oppose" if (n > 0 or d50 > acc) else ("conditional" if d90 > acc else "support")
        out.append(Finding(
            "delivery", f"DEL-F{k}", "estimate", "delivery", strategy_key=k, stance=stance, phase="court",
            text_en=f"{_fe(k)} could delay {n} of {len(pp['projects'])} active projects beyond +{pp['at_risk_threshold_pct']:.0f}% "
                    f"(discrete-event simulation). Portfolio delay increase: median {d50:.1f} pts, P90 {d90:.1f} pts "
                    f"vs {acc:.1f} pts acceptable.",
            text_ar=f"{_fa(k)} قد يؤخر {n} من {len(pp['projects'])} مشروعاً نشطاً بأكثر من +{pp['at_risk_threshold_pct']:.0f}% "
                    f"(محاكاة الأحداث المتقطعة). زيادة تأخير المحفظة: الوسيط {d50:.1f} نقطة، P90 {d90:.1f} نقطة مقابل "
                    f"{acc:.1f} نقطة مقبولة.",
            confidence=0.6,
            evidence=[Evidence("des", f"futures.{k}.project_portfolio.projects_at_risk", "Projects at risk (SimPy)", str(n)),
                      _sim(f"futures.{k}.summary.max_delay_increase_pct.p90", "P90 delay increase", f"{d90:.1f} pts")],
            assumptions=["Synthetic project portfolio structure", "Delay elasticity prior 0.8–1.8"]))
    return out


def hr_evaluate(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    out = []
    for k in ("A", "B", "C"):
        f = ctx.fut(k)
        lv = f["levers"]
        removed = b.contractor_fte * lv["contractor_reduction"]
        util = _summ(f, "peak_utilization_pct")
        short = max(f["trajectory"]["capacity_shortfall_fte"]["expected"])
        if removed <= 0:
            continue
        stance = "oppose" if short > 2 or util > ctx.controls.max_utilization_pct + 3 else (
            "conditional" if short > 0 else "support")
        out.append(Finding(
            "hr", f"HR-F{k}", "estimate", "workload", strategy_key=k, stance=stance, phase="court",
            text_en=f"{_fe(k)} removes ~{removed:.1f} contractor FTE. Internal capacity is insufficient by up to "
                    f"{short:.1f} FTE in the expected case; peak utilisation reaches {util:.0f}%."
                    + (" Retraining in this future raises skill match." if lv["operating_model_redesign"] > 0 else "")
                    + (" The expense freeze also cuts training budget." if lv["expense_freeze"] >= 0.8 else ""),
            text_ar=f"{_fa(k)} يزيل حوالي {removed:.1f} موظف متعاقد مكافئ. الطاقة الداخلية غير كافية بما يصل إلى "
                    f"{short:.1f} موظف في الحالة المتوقعة؛ ويبلغ الاستغلال الأقصى {util:.0f}%."
                    + (" إعادة التأهيل في هذا المستقبل ترفع توافق المهارات." if lv["operating_model_redesign"] > 0 else "")
                    + (" كما أن تجميد الإنفاق يقلص ميزانية التدريب." if lv["expense_freeze"] >= 0.8 else ""),
            confidence=0.5,
            evidence=[_sim(f"futures.{k}.trajectory.capacity_shortfall_fte", "Peak capacity shortfall", f"{short:.1f} FTE"),
                      Evidence("assumption", "params.skill_match", "Skill match (unverified)", "0.55 mode")],
            assumptions=["Internal staff skill match 35–75%"]))
    return out


def coo_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    D = ctx.controls.implementation_months
    fb = ctx.fut("B")
    traj = fb["trajectory"]["savings_run_rate"]["expected"]
    at_d = traj[min(D, len(traj) - 1)]
    at_12 = traj[-1]
    out.append(Finding(
        "coo", "COO-FB", "estimate", "automation", strategy_key="B",
        stance="support" if _summ(fb, "max_delay_increase_pct") <= ctx.controls.acceptable_delay_increase_pct else "conditional",
        phase="court",
        text_en=f"Automation in Future B protects delivery (median delay +{_summ(fb, 'max_delay_increase_pct'):.1f} pts) but "
                f"savings mature slowly: EGP {m(at_d)}M run-rate at month {D} vs EGP {m(at_12)}M at month 12.",
        text_ar=f"الأتمتة في المستقبل ب تحمي التسليم (زيادة تأخير وسيطة +{_summ(fb, 'max_delay_increase_pct'):.1f} نقطة) "
                f"لكن الوفورات تنضج ببطء: {m(at_d)} مليون سنوياً في الشهر {D} مقابل {m(at_12)} مليون في الشهر 12.",
        confidence=0.55,
        evidence=[_sim("futures.B.trajectory.savings_run_rate.expected", f"Run-rate month {D}", f"EGP {m(at_d)}M")],
        assumptions=["Automation adoption S-curve 4–9 months"]))
    fc = ctx.fut("C")
    peak_short = max(fc["trajectory"]["capacity_shortfall_fte"]["expected"])
    out.append(Finding(
        "coo", "COO-FC", "estimate", "transition", strategy_key="C",
        stance="conditional", phase="court",
        text_en=f"Future C's redesign causes transition disruption (peak shortfall {peak_short:.1f} FTE) before "
                f"reallocation gains arrive; phasing the redesign across delivery cycles reduces this.",
        text_ar=f"إعادة التصميم في المستقبل ج تسبب اضطراباً انتقالياً (أقصى عجز {peak_short:.1f} موظف) قبل ظهور "
                f"مكاسب إعادة التوزيع؛ تقسيم إعادة التصميم على دورات التسليم يقلل ذلك.",
        confidence=0.5,
        evidence=[_sim("futures.C.trajectory.capacity_shortfall_fte.expected", "Peak shortfall", f"{peak_short:.1f} FTE")],
        assumptions=["Change disruption 1–6% during transition"]))
    return out


def legal_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in ("A", "B", "C"):
        f = ctx.fut(k)
        p = f["probabilities"]["contractual_breach"]
        if p <= 0.05:
            continue
        out.append(Finding(
            "legal", f"LEG-F{k}", "hypothesis", "contractual", strategy_key=k,
            stance="oppose" if p > 0.5 else "conditional", phase="court",
            text_en=f"{_fe(k)}: modelled probability {p:.0%} that portfolio delay exceeds the assumed contractual tolerance. "
                    f"Penalty exposure is an ESTIMATE from a proxy rate; actual liability depends on contract terms that "
                    f"have not been reviewed.",
            text_ar=f"{_fa(k)}: احتمال متوقع {p:.0%} أن يتجاوز التأخير حد التسامح التعاقدي المفترض. التعرض للغرامات "
                    f"تقدير مبني على معدل تقريبي؛ والمسؤولية الفعلية تعتمد على شروط عقود لم تُراجع.",
            confidence=0.35,
            evidence=[_sim(f"futures.{k}.probabilities.contractual_breach", "P(contractual breach)", f"{p:.0%}"),
                      Evidence("assumption", "params.penalty_rate_pct", "Penalty proxy rate", "0.05–0.20% rev/pt")],
            assumptions=["Contractual delay tolerance 10%", "Penalty proxy rate"]))
    return out


def strategy_evaluate(ctx: AgentContext) -> list[Finding]:
    c = ctx.controls
    ach = {k: ctx.fut(k)["achievable_reduction_pct_at_tolerance"] for k in "ABC"}
    best = max(ach, key=ach.get)
    feasible = [k for k in "ABC" if ach[k] >= c.cost_reduction_target_pct]
    if feasible:
        txt_en = f"Target is achievable at the {c.risk_tolerance} risk tolerance in: {', '.join(_fe(k) for k in feasible)}."
        txt_ar = f"الهدف قابل للتحقيق عند مستوى المخاطرة المختار في: {'، '.join(_fa(k) for k in feasible)}."
        ct = "estimate"
    else:
        txt_en = (f"No future reaches {c.cost_reduction_target_pct:.0f}% at the {c.risk_tolerance} risk tolerance. "
                  f"Highest achievable: {ach[best]:.1f}% ({_fe(best)}). Options: revise the target, extend the timeline, "
                  f"or relax a constraint — each is an executive choice.")
        txt_ar = (f"لا يوجد مستقبل يحقق {c.cost_reduction_target_pct:.0f}% عند مستوى المخاطرة المختار. أعلى نسبة ممكنة: "
                  f"{ach[best]:.1f}% ({_fa(best)}). الخيارات: تعديل الهدف أو مد الإطار الزمني أو تخفيف أحد القيود — "
                  f"وكلها قرارات تنفيذية.")
        ct = "recommendation"
    return [Finding("strategy", "STR-F", ct, "feasibility", txt_en, txt_ar, 0.7,
                    [_sim(f"futures.{k}.achievable_reduction_pct_at_tolerance", f"Achievable % {_fe(k)}", f"{ach[k]:.1f}%")
                     for k in "ABC"], phase="court")]


def risk_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in ("A", "B", "C"):
        f = ctx.fut(k)
        top = f["sensitivity"][0]
        p = f["probabilities"]
        out.append(Finding(
            "risk", f"RSK-F{k}", "estimate", "uncertainty", strategy_key=k, phase="court",
            stance="oppose" if f["hard_constraints_violated"] else "conditional",
            text_en=f"{_fe(k)}: P(meet target) {p['meet_target']:.0%}, P(delay acceptable) {p['delay_within_acceptable']:.0%}, "
                    f"P(CSAT maintained) {p['csat_maintained']:.0%}. Largest uncertainty driver: {top['label_en']} "
                    f"(net-benefit swing EGP {m(top['swing'])}M).",
            text_ar=f"{_fa(k)}: احتمال تحقيق الهدف {p['meet_target']:.0%}، احتمال تأخير مقبول {p['delay_within_acceptable']:.0%}، "
                    f"احتمال الحفاظ على رضا العملاء {p['csat_maintained']:.0%}. أكبر مصدر لعدم اليقين: {top['label_ar']} "
                    f"(تذبذب صافي المنفعة {m(top['swing'])} مليون).",
            confidence=0.65,
            evidence=[_sim(f"futures.{k}.probabilities", "Monte Carlo probabilities",
                           f"n={ctx.simulation['meta']['iterations']}"),
                      _sim(f"futures.{k}.sensitivity[0]", "Top sensitivity driver", top["parameter"])]))
    return out


PHASE1: dict[str, Callable[[AgentContext], list[Finding]]] = {
    "strategy": strategy_analyze,
    "cfo": cfo_analyze,
    "coo": coo_analyze,
    "hr": hr_analyze,
    "delivery": delivery_analyze,
    "legal": legal_analyze,
    "risk": risk_analyze,
}

PHASE2: dict[str, Callable[[AgentContext], list[Finding]]] = {
    "cfo": cfo_evaluate,
    "delivery": delivery_evaluate,
    "hr": hr_evaluate,
    "coo": coo_evaluate,
    "legal": legal_evaluate,
    "strategy": strategy_evaluate,
    "risk": risk_evaluate,
}
