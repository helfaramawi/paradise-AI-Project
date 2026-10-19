"""Agents, court rules, collision rules and risk register for the collections decision domain.

Same contracts as domain.py / court.py / collision.py (structured, bilingual, evidence-linked findings
computed from the dataset and the receivables simulation); only the business questions differ: how
much more cash a collection agency or an in-house programme can bring in, at what fee, and at what
cost to customer relationships, data protection and the collections team.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..simulation.collections import ATTRITION_LIMIT_PCT, TERMS_MONTHS
from .base import AgentContext, Evidence, Finding, Objection, m
from .domain import _fa, _fe


def _ds(ref: str, label: str, value: str) -> Evidence:
    return Evidence("dataset", ref, label, value, verified=False)


def _sim(ref: str, label: str, value: str) -> Evidence:
    return Evidence("simulation", ref, label, value)


def _s(f: dict, k: str, q: str = "p50") -> float:
    return f["summary"][k][q]


def _base_collections(ctx: AgentContext) -> float:
    b = ctx.baseline
    return b.annual_revenue / 12 * b.ontime_collection_rate_pct / 100 + b.overdue_receivables * b.inhouse_recovery_rate_pct / 100


def _dso(ctx: AgentContext) -> float:
    b = ctx.baseline
    return (b.annual_revenue / 12 * TERMS_MONTHS + b.overdue_receivables) / (b.annual_revenue / 360)


# ======================================================================== phase 1
def strategy_analyze(ctx: AgentContext) -> list[Finding]:
    b, c = ctx.baseline, ctx.controls
    base = _base_collections(ctx)
    goal = base * (1 + c.cost_reduction_target_pct / 100)
    extra = goal - base
    return [
        Finding("strategy", "STR-01", "fact", "objective",
                f"Objective: raise monthly cash collections by {c.cost_reduction_target_pct:.0f}% (from EGP {m(base)}M to "
                f"EGP {m(goal)}M a month) within {c.implementation_months} months"
                + (", by contracting a collection agency" if ctx.intake.get("mentions_agency") else "")
                + ", without terminations and without damaging customer relationships.",
                f"الهدف: رفع المتحصلات النقدية الشهرية بنسبة {c.cost_reduction_target_pct:.0f}% (من {m(base)} إلى {m(goal)} مليون "
                f"جنيه شهرياً) خلال {c.implementation_months} أشهر"
                + ("، عبر التعاقد مع شركة تحصيل" if ctx.intake.get("mentions_agency") else "")
                + "، دون إنهاء خدمة أحد ودون الإضرار بالعلاقة مع العملاء.",
                0.95, [_ds("baseline.annual_revenue", "Annual billing", f"EGP {m(b.annual_revenue)}M"),
                       Evidence("assumption", "controls.cost_reduction_target_pct", "Target", f"{c.cost_reduction_target_pct:.0f}%")]),
        Finding("strategy", "STR-02", "estimate", "feasibility",
                f"A collection agency works on the overdue book (EGP {m(b.overdue_receivables)}M), not on invoices paid on time. "
                f"The extra EGP {m(extra)}M a month equals {extra / b.overdue_receivables * 100:.0f}% of the whole overdue book "
                f"every month - a structurally demanding target.",
                f"شركة التحصيل تعمل على المتأخرات ({m(b.overdue_receivables)} مليون) وليس على الفواتير المسددة في موعدها. "
                f"الزيادة المطلوبة {m(extra)} مليون شهرياً تعادل {extra / b.overdue_receivables * 100:.0f}% من كل المتأخرات "
                f"كل شهر - وهو هدف صعب هيكلياً.",
                0.8, [_ds("baseline.overdue_receivables", "Overdue receivables (synthetic)", f"EGP {m(b.overdue_receivables)}M")],
                ["Overdue book composition is a synthetic assumption"]),
        Finding("strategy", "STR-03", "recommendation", "success_criteria",
                f"Success criteria: monthly collections ≥ EGP {m(goal)}M by month {c.implementation_months}; complaint-rate "
                f"increase ≤ {c.acceptable_delay_increase_pct:.1f} pts; CSAT ≥ {c.min_csat_pct:.0f}%; key-account attrition "
                f"≤ {ATTRITION_LIMIT_PCT:.0f}% of revenue; zero terminations; implementation cost ≤ EGP {m(c.implementation_budget)}M.",
                f"معايير النجاح: متحصلات شهرية ≥ {m(goal)} مليون بحلول الشهر {c.implementation_months}؛ زيادة الشكاوى "
                f"≤ {c.acceptable_delay_increase_pct:.1f} نقطة؛ رضا العملاء ≥ {c.min_csat_pct:.0f}%؛ فقد كبار العملاء "
                f"≤ {ATTRITION_LIMIT_PCT:.0f}% من الإيرادات؛ صفر إنهاء خدمة؛ تكلفة التنفيذ ≤ {m(c.implementation_budget)} مليون.",
                0.9, [Evidence("assumption", "controls", "Executive controls", "user-defined")]),
    ]


def cfo_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    billing = b.annual_revenue / 12
    slip = billing * (1 - b.ontime_collection_rate_pct / 100)
    rec = b.overdue_receivables * b.inhouse_recovery_rate_pct / 100
    wo = b.overdue_receivables * b.writeoff_rate_pct / 100
    dq2 = next((x for x in ctx.validation.checks if x.code == "DQ-002"), None)
    return [
        Finding("cfo", "CFO-01", "fact", "receivables",
                f"Monthly billing EGP {m(billing)}M; {b.ontime_collection_rate_pct:.0f}% is collected within terms. EGP {m(slip)}M "
                f"slips into overdue every month while only EGP {m(rec)}M is recovered and EGP {m(wo, 2)}M written off: the "
                f"overdue book (EGP {m(b.overdue_receivables)}M) is growing. DSO is about {_dso(ctx):.0f} days.",
                f"الفوترة الشهرية {m(billing)} مليون جنيه؛ يُحصَّل {b.ontime_collection_rate_pct:.0f}% منها في موعده. يتأخر "
                f"{m(slip)} مليون كل شهر بينما يُسترد {m(rec)} مليون فقط ويُعدم {m(wo, 2)} مليون: المتأخرات "
                f"({m(b.overdue_receivables)} مليون) في ازدياد. متوسط فترة التحصيل حوالي {_dso(ctx):.0f} يوماً.",
                0.85, [_ds("baseline.ontime_collection_rate_pct", "On-time collection rate", f"{b.ontime_collection_rate_pct:.0f}%"),
                       _ds("baseline.overdue_receivables", "Overdue receivables", f"EGP {m(b.overdue_receivables)}M"),
                       _ds("baseline.writeoff_rate_pct", "Monthly write-off rate", f"{b.writeoff_rate_pct:.1f}%")]),
        Finding("cfo", "CFO-02", "estimate", "profitability",
                f"Most extra collections are cash brought forward, not new profit: only avoided write-offs "
                f"(today ~EGP {m(wo * 12)}M a year) improve the P&L. The stated {b.gross_margin_pct:.0f}% gross margin also "
                f"contradicts the cost base and must be reconciled before financial sign-off.",
                f"معظم المتحصلات الإضافية نقد يُحصَّل مبكراً وليست ربحاً جديداً: فقط الديون المعدومة التي نتجنبها "
                f"(حالياً حوالي {m(wo * 12)} مليون سنوياً) تحسّن الأرباح. كما أن هامش الربح الإجمالي المذكور "
                f"{b.gross_margin_pct:.0f}% يتعارض مع قاعدة التكاليف ويجب تسويته قبل الاعتماد المالي.",
                0.55, [Evidence("validation", "DQ-002", "Gross margin consistency check", dq2.severity if dq2 else "n/a", verified=True)],
                ["Write-off rate stays at its current level without action"]),
        Finding("cfo", "CFO-03", "recommendation", "fees",
                "Agency fees are paid on every amount recovered, including payments that would have arrived anyway. "
                "The business case must compare fees with the cost of waiting, not with zero.",
                "عمولة شركة التحصيل تُدفع على كل مبلغ يتم تحصيله، حتى المدفوعات التي كانت ستصل على أي حال. "
                "يجب مقارنة العمولة بتكلفة الانتظار، وليس بالصفر.",
                0.7, [Evidence("assumption", "params.agency_fee_rate", "Agency fee prior", "15% / 20% / 27%")]),
    ]


def coo_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    slip = b.annual_revenue / 12 * (1 - b.ontime_collection_rate_pct / 100)
    return [
        Finding("coo", "COO-01", "fact", "capacity",
                f"The collections team is {b.collections_team_fte:.0f} FTE at {b.collections_team_utilization_pct:.0f}% "
                f"utilisation, following up EGP {m(b.overdue_receivables)}M of overdue invoices largely by phone and e-mail.",
                f"فريق التحصيل {b.collections_team_fte:.0f} موظفين باستغلال {b.collections_team_utilization_pct:.0f}%، "
                f"يتابع متأخرات بقيمة {m(b.overdue_receivables)} مليون غالباً بالهاتف والبريد.",
                0.8, [_ds("baseline.collections_team_fte", "Collections team", f"{b.collections_team_fte:.0f} FTE")]),
        Finding("coo", "COO-02", "fact", "bottleneck",
                f"The root cause is the inflow: EGP {m(slip)}M of each month's billing becomes overdue. An agency works on the "
                f"stock of old debt; it does not stop new invoices from becoming late.",
                f"السبب الجذري هو التدفق: {m(slip)} مليون من فواتير كل شهر تتحول إلى متأخرات. شركة التحصيل تعمل على رصيد "
                f"الديون القديمة؛ ولا تمنع الفواتير الجديدة من التأخر.",
                0.8, [_ds("baseline.ontime_collection_rate_pct", "On-time collection rate", f"{b.ontime_collection_rate_pct:.0f}%")]),
        Finding("coo", "COO-03", "hypothesis", "automation",
                "E-invoicing, automated reminders and payment links could raise on-time payment by 1-4 points. "
                "No pilot data is available to confirm the effect.",
                "الفوترة الإلكترونية والتذكيرات الآلية وروابط الدفع قد ترفع السداد في الموعد من 1 إلى 4 نقاط. "
                "لا تتوفر بيانات تجريبية لتأكيد الأثر.",
                0.4, [Evidence("assumption", "params.ontime_uplift", "On-time uplift prior", "1% / 2.5% / 4%")],
                ["Digital channels reach the finance teams of late payers"]),
    ]


def hr_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    return [
        Finding("hr", "HR-01", "fact", "constraint",
                f"The no-termination constraint protects the {b.collections_team_fte:.0f} collectors: an agency may take over "
                f"accounts, not jobs. Freed capacity must be redeployed.",
                f"قيد عدم الإنهاء يحمي {b.collections_team_fte:.0f} موظفي تحصيل: شركة التحصيل قد تتولى حسابات وليس وظائف. "
                f"يجب إعادة توظيف أي طاقة تتحرر.",
                0.9, [_ds("baseline.collections_team_fte", "Collections team", f"{b.collections_team_fte:.0f} FTE")]),
        Finding("hr", "HR-02", "assumption", "skills",
                "Moving finance staff into collections needs negotiation and customer-contact skills. No skills inventory "
                "exists; the model assumes a 2-month ramp-up.",
                "نقل موظفين من المالية إلى التحصيل يحتاج مهارات تفاوض وتواصل مع العملاء. لا يوجد سجل مهارات؛ "
                "ويفترض النموذج شهرين للوصول إلى الكفاءة.",
                0.4, [Evidence("assumption", "economics.reallocation_fte", "Reallocated FTE", "3")], ["2-month ramp-up"]),
    ]


def delivery_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    return [
        Finding("delivery", "DEL-01", "estimate", "relationships",
                f"{b.key_account_overdue_share_pct:.0f}% of the overdue book is owed by government and key corporate clients "
                f"who are also active clients on the {b.active_projects} running projects. Pressure on these accounts can "
                f"slow approvals and future awards.",
                f"{b.key_account_overdue_share_pct:.0f}% من المتأخرات مستحقة على جهات حكومية وكبار عملاء هم أيضاً عملاء في "
                f"{b.active_projects} مشروعاً جارياً. الضغط على هذه الحسابات قد يبطئ الموافقات والترسيات القادمة.",
                0.65, [_ds("baseline.key_account_overdue_share_pct", "Overdue owed by key/government accounts",
                           f"{b.key_account_overdue_share_pct:.0f}%")]),
    ]


def legal_analyze(ctx: AgentContext) -> list[Finding]:
    return [
        Finding("legal", "LEG-01", "hypothesis", "data_protection",
                "Placing debts with an agency shares customer personal data with a third party. A data-processing agreement "
                "under the Personal Data Protection Law (Law 151 of 2020) and qualified legal review are required.",
                "تسليم المديونيات لشركة تحصيل يعني مشاركة بيانات العملاء الشخصية مع طرف ثالث. يلزم اتفاقية معالجة بيانات "
                "وفق قانون حماية البيانات الشخصية (القانون 151 لسنة 2020) ومراجعة قانونية متخصصة.",
                0.5, [Evidence("policy", "GOV-015", "Customer data shared with a third party", "require_approval", verified=True)]),
        Finding("legal", "LEG-02", "hypothesis", "conduct",
                "Collection conduct must be fair: no harassment or threats, and legal action decided case by case. Debts "
                "owed by government entities may follow specific procedures. Customer contracts and their late-payment "
                "clauses have not been provided.",
                "يجب أن يكون التحصيل عادلاً: لا مضايقات ولا تهديد، وأي إجراء قانوني يُقرر لكل حالة. ديون الجهات "
                "الحكومية قد تخضع لإجراءات خاصة. لم تُقدَّم عقود العملاء وبنود التأخير في السداد.",
                0.4, [Evidence("policy", "GOV-016", "Fair collection conduct", "deny", verified=True)]),
    ]


def risk_analyze(ctx: AgentContext) -> list[Finding]:
    v = ctx.validation
    errors = [x.code for x in v.checks if x.severity == "error"]
    return [
        Finding("risk", "RSK-01", "fact", "data_quality",
                f"Data quality score {v.quality_score:.0%}. Errors: {', '.join(errors) or 'none'}. Receivables figures are "
                f"synthetic assumptions; no recovery history exists to calibrate the agency's performance.",
                f"درجة جودة البيانات {v.quality_score:.0%}. الأخطاء: {', '.join(errors) or 'لا يوجد'}. أرقام المديونيات "
                f"افتراضية، ولا يوجد سجل استرداد لمعايرة أداء شركة التحصيل.",
                0.9, [Evidence("validation", c, "Validation check", "error", verified=True) for c in errors]
                or [Evidence("validation", "DQ", "Validation", "ok", verified=True)]),
    ]


# ======================================================================== phase 2 (with simulation)
def cfo_evaluate(ctx: AgentContext) -> list[Finding]:
    t = ctx.controls.cost_reduction_target_pct
    best = max(_s(ctx.fut(x), "savings_pct_at_deadline") for x in "ABC")
    out = []
    for k in "ABC":
        f = ctx.fut(k)
        up, nb, fee = _s(f, "savings_pct_at_deadline"), _s(f, "net_benefit_12m"), _s(f, "agency_fees_12m")
        stance = "support" if up >= best - 1e-6 else ("conditional" if nb > 0 else "oppose")
        out.append(Finding(
            "cfo", f"CFO-F{k}", "estimate", "collections", strategy_key=k, stance=stance, phase="court",
            text_en=f"{_fe(k)} lifts monthly collections by a median {up:.1f}% at month {ctx.controls.implementation_months} "
                    f"(EGP {m(_s(f, 'run_rate_savings_at_deadline'))}M a year) vs the {t:.0f}% target. 12-month net cash benefit "
                    f"EGP {m(nb)}M after EGP {m(fee)}M agency fees; write-offs avoided EGP {m(_s(f, 'writeoff_avoided_12m'))}M.",
            text_ar=f"{_fa(k)} يرفع المتحصلات الشهرية بنسبة وسيطة {up:.1f}% في الشهر {ctx.controls.implementation_months} "
                    f"({m(_s(f, 'run_rate_savings_at_deadline'))} مليون سنوياً) مقابل هدف {t:.0f}%. صافي المنفعة النقدية خلال 12 شهراً "
                    f"{m(nb)} مليون بعد عمولات {m(fee)} مليون؛ ديون معدومة تم تجنبها {m(_s(f, 'writeoff_avoided_12m'))} مليون.",
            confidence=0.7,
            evidence=[_sim(f"futures.{k}.summary.savings_pct_at_deadline.p50", "Median collections uplift", f"{up:.1f}%"),
                      _sim(f"futures.{k}.summary.net_benefit_12m.p50", "Median 12m net benefit", f"EGP {m(nb)}M"),
                      _sim(f"futures.{k}.summary.agency_fees_12m.p50", "Agency fees 12m", f"EGP {m(fee)}M")]))
    return out


def delivery_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in "ABC":
        f = ctx.fut(k)
        pp = f["project_portfolio"]
        att = _s(f, "relationship_loss_pct")
        p = f["probabilities"]["contractual_breach"]
        n = pp["projects_at_risk"]
        stance = "oppose" if (n > 0 or att > ATTRITION_LIMIT_PCT) else ("conditional" if p > 0.1 else "support")
        segs = ", ".join(r["name_en"] for r in pp["projects"] if r["at_risk"]) or "none"
        segs_ar = "، ".join(r["name_ar"] for r in pp["projects"] if r["at_risk"]) or "لا يوجد"
        out.append(Finding(
            "delivery", f"DEL-F{k}", "estimate", "relationships", strategy_key=k, stance=stance, phase="court",
            text_en=f"{_fe(k)}: client relationships at risk: {segs}. Modelled key-account attrition median {att:.2f}% of revenue "
                    f"(limit {ATTRITION_LIMIT_PCT:.0f}%); probability of exceeding it {p:.0%}.",
            text_ar=f"{_fa(k)}: علاقات العملاء المعرضة للخطر: {segs_ar}. فقد كبار العملاء المتوقع (الوسيط) {att:.2f}% من الإيرادات "
                    f"(الحد {ATTRITION_LIMIT_PCT:.0f}%)؛ احتمال تجاوزه {p:.0%}.",
            confidence=0.55,
            evidence=[Evidence("des", f"futures.{k}.project_portfolio.projects_at_risk", "Client segments at risk", str(n)),
                      _sim(f"futures.{k}.summary.relationship_loss_pct.p50", "Key-account attrition", f"{att:.2f}%")],
            assumptions=["Key-account attrition prior 1-7% of their revenue a year under aggressive contact"]))
    return out


def hr_evaluate(ctx: AgentContext) -> list[Finding]:
    b, out = ctx.baseline, []
    for k in "ABC":
        f = ctx.fut(k)
        lv = f["levers"]
        util = _s(f, "peak_utilization_pct")
        short = max(f["trajectory"]["capacity_shortfall_fte"]["expected"])
        if lv["agency_placement"] > 0:
            freed = b.collections_team_fte * b.collections_team_utilization_pct / 100 * 0.35 * lv["agency_placement"]
            txt_en = (f"{_fe(k)} moves accounts to the agency and frees ~{freed:.1f} FTE of collector time; peak utilisation "
                      f"{util:.0f}%. Freed staff must be redeployed (e.g. to dispute resolution), not released.")
            txt_ar = (f"{_fa(k)} ينقل حسابات إلى شركة التحصيل ويحرر حوالي {freed:.1f} موظف من وقت المحصلين؛ الاستغلال الأقصى "
                      f"{util:.0f}%. يجب إعادة توظيفهم (مثلاً في حل النزاعات) وليس الاستغناء عنهم.")
            stance = "conditional"
        else:
            txt_en = (f"{_fe(k)} reassigns {3 * lv['team_reallocation']:.0f} finance staff to collections; peak utilisation "
                      f"{util:.0f}%, capacity shortfall up to {short:.1f} FTE. Training is needed in the first two months.")
            txt_ar = (f"{_fa(k)} ينقل {3 * lv['team_reallocation']:.0f} موظفين من المالية إلى التحصيل؛ الاستغلال الأقصى "
                      f"{util:.0f}%، وعجز الطاقة حتى {short:.1f} موظف. يلزم تدريب خلال أول شهرين.")
            stance = "support" if short <= 0.1 and util <= ctx.controls.max_utilization_pct else "conditional"
        out.append(Finding("hr", f"HR-F{k}", "estimate", "workload", strategy_key=k, stance=stance, phase="court",
                           text_en=txt_en, text_ar=txt_ar, confidence=0.5,
                           evidence=[_sim(f"futures.{k}.summary.peak_utilization_pct.p50", "Peak team utilisation", f"{util:.0f}%")],
                           assumptions=["Agency placement removes up to 35% of collector workload"]))
    return out


def coo_evaluate(ctx: AgentContext) -> list[Finding]:
    D, out = ctx.controls.implementation_months, []
    for k in "BC":
        f = ctx.fut(k)
        traj = f["trajectory"]["savings_run_rate"]["expected"]
        at_d, at_12 = traj[min(D, len(traj) - 1)], traj[-1]
        dso0, dso_d = f["trajectory"]["dso_days"]["expected"][0], _s(f, "dso_days_at_deadline")
        out.append(Finding(
            "coo", f"COO-F{k}", "estimate", "process", strategy_key=k,
            stance="support" if _s(f, "max_delay_increase_pct") <= ctx.controls.acceptable_delay_increase_pct else "conditional",
            phase="court",
            text_en=f"{_fe(k)} fixes the inflow as well as the stock: DSO {dso0:.0f} → {dso_d:.0f} days by month {D}. Digital "
                    f"adoption takes time: uplift EGP {m(at_d)}M a year at month {D} vs EGP {m(at_12)}M at month 12.",
            text_ar=f"{_fa(k)} يعالج التدفق وليس الرصيد فقط: متوسط فترة التحصيل {dso0:.0f} ← {dso_d:.0f} يوماً بحلول الشهر {D}. "
                    f"التبني الرقمي يحتاج وقتاً: الزيادة {m(at_d)} مليون سنوياً في الشهر {D} مقابل {m(at_12)} مليون في الشهر 12.",
            confidence=0.55,
            evidence=[_sim(f"futures.{k}.summary.dso_days_at_deadline.p50", "DSO at deadline", f"{dso_d:.0f} days")],
            assumptions=["Digital adoption S-curve 3-8 months"]))
    fa = ctx.fut("A")
    traj = fa["trajectory"]["collections_monthly"]["expected"]
    peak, end = max(traj), traj[-1]
    out.append(Finding(
        "coo", "COO-FA", "estimate", "fade", strategy_key="A", stance="conditional", phase="court",
        text_en=f"Future A's uplift peaks early (EGP {m(peak)}M in a month) then fades to EGP {m(end)}M by month 12: the agency "
                f"drains a finite overdue book while new late invoices keep arriving.",
        text_ar=f"زيادة المستقبل أ تبلغ ذروتها مبكراً ({m(peak)} مليون في شهر) ثم تتراجع إلى {m(end)} مليون في الشهر 12: "
                f"الشركة تستنزف رصيداً محدوداً من المتأخرات بينما تستمر الفواتير الجديدة في التأخر.",
        confidence=0.6,
        evidence=[_sim("futures.A.trajectory.collections_monthly.expected", "Monthly collections path", f"peak EGP {m(peak)}M")]))
    return out


def legal_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in "ABC":
        lv = ctx.fut(k)["levers"]
        if lv["agency_placement"] <= 0:
            continue
        aggressive = lv["aggressive_tactics"] > 0
        out.append(Finding(
            "legal", f"LEG-F{k}", "hypothesis", "compliance", strategy_key=k,
            stance="oppose" if aggressive else "conditional", phase="court",
            text_en=f"{_fe(k)} shares data on {lv['agency_placement']:.0%} of the overdue book with an agency: a data-processing "
                    f"agreement and Legal approval are required (GOV-015)."
                    + (" Its high-frequency contact and early legal escalation breach the fair-collection policy (GOV-016)."
                       if aggressive else " Fair-conduct rules must be written into the agency contract."),
            text_ar=f"{_fa(k)} يشارك بيانات {lv['agency_placement']:.0%} من المتأخرات مع شركة تحصيل: يلزم اتفاقية معالجة بيانات "
                    f"وموافقة قانونية (GOV-015)."
                    + (" كما أن التواصل المكثف والتصعيد القانوني المبكر يخالفان سياسة التحصيل العادل (GOV-016)."
                       if aggressive else " ويجب النص على قواعد التحصيل العادل في عقد الشركة."),
            confidence=0.45,
            evidence=[Evidence("policy", "GOV-015", "Customer data shared with a third party", "require_approval", verified=True)]
            + ([Evidence("policy", "GOV-016", "Fair collection conduct", "deny", verified=True)] if aggressive else []),
            assumptions=["Customer contracts not reviewed"]))
    return out


def strategy_evaluate(ctx: AgentContext) -> list[Finding]:
    c = ctx.controls
    ach = {k: ctx.fut(k)["achievable_reduction_pct_at_tolerance"] for k in "ABC"}
    best = max(ach, key=ach.get)
    feasible = [k for k in "ABC" if ach[k] >= c.cost_reduction_target_pct]
    if feasible:
        en = f"The target is achievable at the {c.risk_tolerance} risk tolerance in: {', '.join(_fe(k) for k in feasible)}."
        ar = f"الهدف قابل للتحقيق عند مستوى المخاطرة المختار في: {'، '.join(_fa(k) for k in feasible)}."
        ct = "estimate"
    else:
        en = (f"No future reaches {c.cost_reduction_target_pct:.0f}% more collections at the {c.risk_tolerance} risk tolerance. "
              f"Highest achievable: {ach[best]:.1f}% ({_fe(best)}). A one-off release of old debt is possible, but a sustained "
              f"{c.cost_reduction_target_pct:.0f}% needs more billing, not only better collection.")
        ar = (f"لا يوجد مستقبل يحقق زيادة {c.cost_reduction_target_pct:.0f}% في المتحصلات عند مستوى المخاطرة المختار. أعلى نسبة "
              f"ممكنة: {ach[best]:.1f}% ({_fa(best)}). يمكن تحصيل جزء من الديون القديمة مرة واحدة، لكن زيادة مستدامة "
              f"{c.cost_reduction_target_pct:.0f}% تحتاج مبيعات أكثر وليس تحصيلاً أفضل فقط.")
        ct = "recommendation"
    return [Finding("strategy", "STR-F", ct, "feasibility", en, ar, 0.7,
                    [_sim(f"futures.{k}.achievable_reduction_pct_at_tolerance", f"Achievable % {_fe(k)}", f"{ach[k]:.1f}%")
                     for k in "ABC"], phase="court")]


def risk_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in "ABC":
        f = ctx.fut(k)
        top, p = f["sensitivity"][0], f["probabilities"]
        out.append(Finding(
            "risk", f"RSK-F{k}", "estimate", "uncertainty", strategy_key=k, phase="court",
            stance="oppose" if f["hard_constraints_violated"] else "conditional",
            text_en=f"{_fe(k)}: P(meet target) {p['meet_target']:.0%}, P(complaints acceptable) {p['delay_within_acceptable']:.0%}, "
                    f"P(CSAT maintained) {p['csat_maintained']:.0%}. Largest uncertainty driver: {top['label_en']} "
                    f"(net-benefit swing EGP {m(top['swing'])}M).",
            text_ar=f"{_fa(k)}: احتمال تحقيق الهدف {p['meet_target']:.0%}، احتمال بقاء الشكاوى في الحد المقبول "
                    f"{p['delay_within_acceptable']:.0%}، احتمال الحفاظ على رضا العملاء {p['csat_maintained']:.0%}. أكبر مصدر "
                    f"لعدم اليقين: {top['label_ar']} (تذبذب صافي المنفعة {m(top['swing'])} مليون).",
            confidence=0.65,
            evidence=[_sim(f"futures.{k}.probabilities", "Monte Carlo probabilities", f"n={ctx.simulation['meta']['iterations']}"),
                      _sim(f"futures.{k}.sensitivity[0]", "Top sensitivity driver", top["parameter"])]))
    return out


PHASE1: dict[str, Callable[[AgentContext], list[Finding]]] = {
    "strategy": strategy_analyze, "cfo": cfo_analyze, "coo": coo_analyze, "hr": hr_analyze,
    "delivery": delivery_analyze, "legal": legal_analyze, "risk": risk_analyze,
}
PHASE2: dict[str, Callable[[AgentContext], list[Finding]]] = {
    "cfo": cfo_evaluate, "delivery": delivery_evaluate, "hr": hr_evaluate, "coo": coo_evaluate,
    "legal": legal_evaluate, "strategy": strategy_evaluate, "risk": risk_evaluate,
}


# ======================================================================== court
def _find(findings: list[Finding], code: str) -> Finding | None:
    return next((f for f in findings if f.code == code), None)


def redteam_challenge(ctx: AgentContext, findings: list[Finding]) -> list[Objection]:
    sim, obs = ctx.simulation, []
    assert sim is not None
    acc = ctx.controls.acceptable_delay_increase_pct

    # R1: the agency recovery rate behind the agency futures is an unvalidated prior
    best = max("AB", key=lambda k: sim["futures"][k]["summary"]["savings_pct_at_deadline"]["p50"])
    sens = {s["parameter"]: s for s in sim["futures"][best]["sensitivity"]}
    ar = sens.get("agency_recovery_rate")
    if ar:
        obs.append(Objection(
            "redteam", "cfo", f"CFO-F{best}", best, "unsupported_assumption", "high",
            f"The CFO's case for {_fe(best)} assumes the agency recovers 8.5% of the placed book every month. No agency has "
            f"been tendered and no recovery history exists. At 5% the uplift falls to {ar['savings_pct_at_low']:.1f}% and "
            f"net benefit to EGP {m(ar['net_benefit_at_low'])}M.",
            f"حجة المدير المالي لصالح {_fa(best)} تفترض أن شركة التحصيل تسترد 8.5% من المتأخرات المسلّمة كل شهر. لم تُطرح "
            f"مناقصة ولا يوجد سجل استرداد. عند 5% تنخفض الزيادة إلى {ar['savings_pct_at_low']:.1f}% وصافي المنفعة إلى "
            f"{m(ar['net_benefit_at_low'])} مليون."))
    # R2: CFO supports, Delivery opposes the same future
    for k in "ABC":
        cf, dl = _find(findings, f"CFO-F{k}"), _find(findings, f"DEL-F{k}")
        if cf and dl and cf.stance == "support" and dl.stance == "oppose":
            obs.append(Objection(
                "redteam", "cfo", cf.code, k, "contradiction", "high",
                f"Contradiction on {_fe(k)}: the CFO Agent supports it for the cash it brings in, while the Delivery Agent "
                f"opposes it because it puts government and key clients at risk. The cash figures do not price that loss.",
                f"تناقض حول {_fa(k)}: وكيل المدير المالي يؤيده بسبب النقد الذي يجلبه، بينما يعارضه وكيل التسليم لأنه يعرّض "
                f"الجهات الحكومية وكبار العملاء للخطر. أرقام النقد لا تحسب تكلفة هذه الخسارة."))
    # R3: uplift fades - finite stock
    fa = sim["futures"]["A"]["trajectory"]["collections_monthly"]["expected"]
    if max(fa) > fa[-1] * 1.03:
        obs.append(Objection(
            "redteam", "strategy", "STR-01", "A", "optimism", "medium",
            f"The early peak is not a new run-rate: Future A collects EGP {m(max(fa))}M in its best month but EGP {m(fa[-1])}M "
            f"by month 12, because old debt runs out. Judging the agency on its first months overstates it.",
            f"الذروة المبكرة ليست معدلاً جديداً: المستقبل أ يحصّل {m(max(fa))} مليون في أفضل شهر لكن {m(fa[-1])} مليون في "
            f"الشهر 12 لأن الديون القديمة تنفد. الحكم على الشركة من أشهرها الأولى مبالغ فيه."))
    # R4: data integrity
    if ctx.validation.has_errors:
        obs.append(Objection(
            "redteam", "cfo", "CFO-02", None, "data_integrity", "high",
            "Every financial projection rests on a dataset that fails its own consistency check (gross margin vs cost base), "
            "and the receivables profile itself is a synthetic assumption.",
            "كل التوقعات المالية تعتمد على بيانات فشلت في اختبار الاتساق الخاص بها (الهامش الإجمالي مقابل التكاليف)، "
            "كما أن بيانات المديونيات نفسها افتراضية."))
    # R5: agency fees at P90
    for k in "AB":
        s = sim["futures"][k]["summary"]["agency_fees_12m"]
        if s["p90"] > s["expected"] * 1.15:
            obs.append(Objection(
                "redteam", "cfo", f"CFO-F{k}", k, "optimism", "medium",
                f"{_fe(k)} agency fees: expected EGP {m(s['expected'])}M but P90 EGP {m(s['p90'])}M. Fees apply to payments "
                f"that would have arrived anyway; test the case at P90.",
                f"عمولات {_fa(k)}: المتوقع {m(s['expected'])} مليون لكن P90 يبلغ {m(s['p90'])} مليون. العمولة تُدفع حتى على "
                f"مدفوعات كانت ستصل على أي حال؛ يجب اختبار الجدوى عند P90."))
    # R6: target infeasible
    ach = {k: sim["futures"][k]["achievable_reduction_pct_at_tolerance"] for k in "ABC"}
    if max(ach.values()) < ctx.controls.cost_reduction_target_pct:
        obs.append(Objection(
            "redteam", "strategy", "STR-01", None, "infeasible_objective", "critical",
            f"The {ctx.controls.cost_reduction_target_pct:.0f}% objective is not reached by any simulated future (max "
            f"{max(ach.values()):.1f}%). Collections cannot exceed what is billed for long.",
            f"هدف {ctx.controls.cost_reduction_target_pct:.0f}% لا يتحقق في أي مستقبل تمت محاكاته (الأقصى "
            f"{max(ach.values()):.1f}%). لا يمكن للمتحصلات أن تتجاوز المفوتر لفترة طويلة."))
    # R7: cash acceleration is not profit
    fb = sim["futures"]["B"]["summary"]
    obs.append(Objection(
        "redteam", "cfo", "CFO-FB", "B", "hidden_dependency", "medium",
        f"Most of the gain is cash brought forward. In Future B only EGP {m(fb['writeoff_avoided_12m']['p50'])}M of write-offs "
        f"are avoided in 12 months, against EGP {m(fb['agency_fees_12m']['p50'])}M of fees: the P&L effect is far smaller "
        f"than the cash effect.",
        f"معظم المكسب نقد يُحصَّل مبكراً. في المستقبل ب يتم تجنب {m(fb['writeoff_avoided_12m']['p50'])} مليون فقط من الديون "
        f"المعدومة خلال 12 شهراً مقابل عمولات {m(fb['agency_fees_12m']['p50'])} مليون: الأثر على الأرباح أصغر بكثير من الأثر النقدي."))
    # R8: adverse case for the lowest-complaint option
    safest = min("ABC", key=lambda k: sim["futures"][k]["summary"]["max_delay_increase_pct"]["p50"])
    d90 = sim["futures"][safest]["summary"]["max_delay_increase_pct"]["p90"]
    worst = max("ABC", key=lambda k: sim["futures"][k]["summary"]["max_delay_increase_pct"]["p90"])
    w90 = sim["futures"][worst]["summary"]["max_delay_increase_pct"]["p90"]
    if w90 > acc:
        obs.append(Objection(
            "redteam", "delivery", f"DEL-F{worst}", worst, "adverse_scenario", "medium",
            f"Adverse case: in the P90 scenario {_fe(worst)} raises complaints by +{w90:.1f} pts, above the {acc:.1f} pts limit "
            f"(the lowest-complaint option, {_fe(safest)}, stays at +{d90:.1f} pts).",
            f"سيناريو سلبي: في سيناريو P90 يرفع {_fa(worst)} الشكاوى +{w90:.1f} نقطة متجاوزاً الحد {acc:.1f} نقطة "
            f"(الخيار الأقل شكاوى، {_fa(safest)}، يبقى عند +{d90:.1f} نقطة)."))
    return obs


def respond(ctx: AgentContext, obs: list[Objection]) -> list[Objection]:
    sim = ctx.simulation
    assert sim is not None
    for o in obs:
        o.response_by = o.target_agent
        t = o.objection_type
        if t == "unsupported_assumption":
            o.response_en = ("Conceded in part. Proposed mitigation: tender two agencies with a 3-month pilot on a sample of "
                             "aged debt and pay on results; scale only if the recovery rate is confirmed.")
            o.response_ar = ("أُقرّ جزئياً. التخفيف المقترح: طرح مناقصة لشركتين مع تجربة 3 أشهر على عينة من الديون القديمة "
                             "والدفع حسب النتائج؛ والتوسع فقط إذا تأكد معدل الاسترداد.")
            o.resolution = "partially"
        elif t == "contradiction":
            loss = sim["futures"][o.strategy_key]["summary"]["delivery_loss_12m"]["p50"]
            o.response_en = (f"Acknowledged. Including the modelled relationship loss (EGP {m(loss)}M over 12 months) the case "
                             f"weakens; the CFO position becomes 'conditional on excluding key and government accounts'.")
            o.response_ar = (f"تم الإقرار. بإضافة خسارة العلاقات المتوقعة ({m(loss)} مليون خلال 12 شهراً) تضعف الحجة؛ ويصبح "
                             f"موقف المدير المالي 'مشروطاً باستبعاد كبار العملاء والجهات الحكومية'.")
            o.resolution = "partially"
        elif t == "optimism" and o.target_agent == "strategy":
            o.response_en = "Agreed. The dossier judges each future on its month-12 run-rate, not its best month."
            o.response_ar = "موافق. ملف القرار يقيّم كل مستقبل على معدله في الشهر 12 وليس على أفضل شهر."
            o.resolution = "resolved"
        elif t == "optimism":
            o.response_en = "Agreed. Fees are reported at P90 next to the expected value; the contract should cap the fee on early-stage debt."
            o.response_ar = "موافق. تُعرض العمولات عند P90 بجانب القيمة المتوقعة؛ ويجب أن يضع العقد سقفاً للعمولة على الديون الحديثة."
            o.resolution = "resolved"
        elif t == "data_integrity":
            o.response_en = ("Cannot be resolved by analysis. The dataset owner must reconcile the margin and load the real "
                             "ageing report. Governance requires approvers to acknowledge this (GOV-011).")
            o.response_ar = ("لا يمكن حله بالتحليل. يجب على مالك البيانات تسوية الهامش وتحميل تقرير الأعمار الحقيقي. "
                             "تشترط الحوكمة إقرار المعتمدين بذلك (GOV-011).")
            o.resolution = "unresolved"
        elif t == "infeasible_objective":
            o.response_en = ("Accepted. The orchestrator will present the highest achievable uplift, the one-off cash release "
                             "from old debt, and timeline alternatives for an executive decision.")
            o.response_ar = ("مقبول. سيعرض المنسق أعلى زيادة ممكنة، والنقد الذي يمكن تحريره مرة واحدة من الديون القديمة، "
                             "وبدائل الإطار الزمني لاتخاذ قرار تنفيذي.")
            o.resolution = "unresolved"
        elif t == "hidden_dependency":
            o.response_en = "Valid. The dossier reports the cash effect and the P&L effect (avoided write-offs) separately."
            o.response_ar = "صحيح. يعرض ملف القرار الأثر النقدي والأثر على الأرباح (الديون المعدومة التي تم تجنبها) بشكل منفصل."
            o.resolution = "resolved"
        elif t == "adverse_scenario":
            o.response_en = ("Acknowledged. Mitigation: contact-frequency limits in the agency contract, a complaints hotline "
                             "and monthly monitoring of complaints against the forecast band.")
            o.response_ar = ("تم الإقرار. التخفيف: حدود لعدد مرات التواصل في عقد الشركة، وخط ساخن للشكاوى، ومراقبة شهرية "
                             "للشكاوى مقابل نطاق التوقع.")
            o.resolution = "partially"
    return obs


def ethics_findings(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in "ABC":
        lv = ctx.fut(k)["levers"]
        if lv["aggressive_tactics"] > 0:
            out.append(Finding(
                "governance", f"ETH-C{k}", "hypothesis", "ethics", strategy_key=k, stance="oppose", phase="governance",
                text_en=f"Ethical concern: {_fe(k)} applies pressure tactics through a third party, including to customers "
                        f"who may be in genuine difficulty. Collection should separate 'cannot pay' from 'will not pay'.",
                text_ar=f"مخاوف أخلاقية: {_fa(k)} يمارس أساليب ضغط عبر طرف ثالث، بما في ذلك على عملاء قد يمرون بصعوبات "
                        f"حقيقية. يجب أن يفرق التحصيل بين من لا يستطيع السداد ومن يرفض السداد.",
                confidence=0.6,
                evidence=[Evidence("policy", "GOV-016", "Fair collection conduct", "deny", verified=True)]))
    return out


# ======================================================================== collisions and risks
def _sev(score: float) -> str:
    return "critical" if score >= 0.75 else "high" if score >= 0.5 else "medium" if score >= 0.25 else "low"


def _stance(findings: list[Finding], agent: str, k: str) -> Finding | None:
    return next((f for f in findings if f.agent == agent and f.strategy_key == k and f.phase == "court"), None)


def detect_collisions(ctx: AgentContext, findings: list[Finding]) -> list[dict[str, Any]]:
    sim = ctx.simulation
    assert sim is not None
    b, c, out = ctx.baseline, ctx.controls, []
    for k in "ABC":
        f = sim["futures"][k]
        lv, s = f["levers"], f["summary"]
        cfo, dl, lg = (_stance(findings, a, k) for a in ("cfo", "delivery", "legal"))
        # COL-11: agency cash vs client relationships
        if lv["agency_placement"] > 0 and cfo and cfo.stance in ("support", "conditional") and dl and dl.stance == "oppose":
            p = f["probabilities"]["contractual_breach"]
            score = min(1.0, 0.3 + 0.35 * p + 0.15 * s["max_delay_increase_pct"]["p50"] / max(c.acceptable_delay_increase_pct, 0.5)
                        + 0.1 * f["project_portfolio"]["projects_at_risk"])
            positions = [{"agent": a.agent, "stance": a.stance, "text_en": a.text_en, "text_ar": a.text_ar} for a in (cfo, dl, lg) if a]
            out.append({
                "rule_code": "COL-11", "strategy_key": k, "severity_score": round(score, 3), "severity": _sev(score),
                "title_en": f"{_fe(k)}: agency cash collides with key-client relationships",
                "title_ar": f"{_fa(k)}: نقد شركة التحصيل يتصادم مع العلاقة مع كبار العملاء",
                "positions": positions,
                "affected_objectives": ["collections_uplift", "customer_relationships", "customer_satisfaction"],
                "consequences": [
                    {"en": f"Key-account attrition median {s['relationship_loss_pct']['p50']:.2f}% of revenue (limit {ATTRITION_LIMIT_PCT:.0f}%)",
                     "ar": f"فقد كبار العملاء الوسيط {s['relationship_loss_pct']['p50']:.2f}% من الإيرادات (الحد {ATTRITION_LIMIT_PCT:.0f}%)"},
                    {"en": f"Complaint rate +{s['max_delay_increase_pct']['p50']:.1f} pts", "ar": f"معدل الشكاوى +{s['max_delay_increase_pct']['p50']:.1f} نقطة"},
                    {"en": f"Minimum CSAT {s['min_csat_pct']['p50']:.1f}%", "ar": f"أدنى رضا للعملاء {s['min_csat_pct']['p50']:.1f}%"},
                    {"en": f"12-month relationship loss EGP {m(s['delivery_loss_12m']['p50'])}M",
                     "ar": f"خسارة العلاقات خلال 12 شهراً {m(s['delivery_loss_12m']['p50'])} مليون"},
                ],
                "resolutions": [
                    {"en": "Keep government and key accounts in-house", "ar": "إبقاء الجهات الحكومية وكبار العملاء داخلياً"},
                    {"en": "Place only debt older than 90 days", "ar": "تسليم الديون الأقدم من 90 يوماً فقط"},
                    {"en": "Write fair-conduct and contact limits into the agency contract", "ar": "النص على التحصيل العادل وحدود التواصل في العقد"},
                ],
                "requires_human": True,
            })
        # COL-13: deadline vs digital adoption
        if lv["digital_collections"] > 0:
            traj = f["trajectory"]["savings_run_rate"]["expected"]
            D = c.implementation_months
            at_d, at_end = traj[min(D, len(traj) - 1)], traj[-1]
            if at_end > 0 and at_d / at_end < 0.85:
                score = min(1.0, 0.2 + 0.5 * (1 - at_d / at_end))
                out.append({
                    "rule_code": "COL-13", "strategy_key": k, "severity_score": round(score, 3), "severity": _sev(score),
                    "title_en": f"{_fe(k)}: {D}-month deadline collides with digital adoption",
                    "title_ar": f"{_fa(k)}: مهلة {D} أشهر تتصادم مع منحنى التبني الرقمي",
                    "positions": [
                        {"agent": "strategy", "stance": "support", "text_en": f"Uplift required by month {D}.", "text_ar": f"الزيادة مطلوبة بحلول الشهر {D}."},
                        {"agent": "coo", "stance": "conditional", "text_en": f"Only {at_d / at_end:.0%} of the month-12 uplift is reached by month {D}.",
                         "text_ar": f"يتحقق {at_d / at_end:.0%} فقط من زيادة الشهر 12 بحلول الشهر {D}."},
                    ],
                    "affected_objectives": ["collections_uplift", "timeline"],
                    "consequences": [{"en": f"Uplift at month {D}: EGP {m(at_d)}M a year vs EGP {m(at_end)}M at month 12",
                                      "ar": f"الزيادة في الشهر {D}: {m(at_d)} مليون سنوياً مقابل {m(at_end)} مليون في الشهر 12"}],
                    "resolutions": [{"en": "Accept a later realisation date", "ar": "قبول موعد تحقق لاحق"},
                                    {"en": "Start with payment links and reminders, the fastest tools", "ar": "البدء بروابط الدفع والتذكيرات لأنها الأسرع"}],
                    "requires_human": True,
                })
        # COL-12: fees consume the gain
        fees, gross = s["agency_fees_12m"]["p50"], s["realized_savings_12m"]["p50"]
        if lv["agency_placement"] > 0 and gross > 0 and fees / gross > 0.2:
            out.append({
                "rule_code": "COL-12", "strategy_key": k, "severity_score": round(min(0.6, fees / gross), 3),
                "severity": _sev(min(0.6, fees / gross)),
                "title_en": f"{_fe(k)}: agency fees absorb {fees / gross:.0%} of the extra cash",
                "title_ar": f"{_fa(k)}: عمولات الشركة تستهلك {fees / gross:.0%} من النقد الإضافي",
                "positions": [
                    {"agent": "cfo", "stance": "conditional", "text_en": f"Fees EGP {m(fees)}M on EGP {m(gross)}M extra cash.",
                     "text_ar": f"عمولات {m(fees)} مليون على نقد إضافي {m(gross)} مليون."},
                    {"agent": "coo", "stance": "conditional", "text_en": "Part of the fee is paid on invoices that would be paid anyway.",
                     "text_ar": "جزء من العمولة يُدفع على فواتير كانت ستُسدد على أي حال."},
                ],
                "affected_objectives": ["collections_uplift"],
                "consequences": [{"en": f"Net cash benefit EGP {m(s['net_benefit_12m']['p50'])}M after fees",
                                  "ar": f"صافي المنفعة النقدية {m(s['net_benefit_12m']['p50'])} مليون بعد العمولات"}],
                "resolutions": [{"en": "Tiered fee: lower on debt under 90 days", "ar": "عمولة متدرجة: أقل على الديون الأحدث من 90 يوماً"},
                                {"en": "Place only accounts the team cannot reach", "ar": "تسليم الحسابات التي يتعذر على الفريق الوصول إليها فقط"}],
                "requires_human": False,
            })
    # COL-14: target vs finite overdue book
    ach = max(sim["futures"][k]["achievable_reduction_pct_at_tolerance"] for k in "ABC")
    if ach < c.cost_reduction_target_pct:
        gap = c.cost_reduction_target_pct - ach
        score = min(1.0, 0.5 + gap / 40)
        base = _base_collections(ctx)
        out.append({
            "rule_code": "COL-14", "strategy_key": None, "severity_score": round(score, 3), "severity": _sev(score),
            "title_en": f"{c.cost_reduction_target_pct:.0f}% more collections collides with the size of the overdue book",
            "title_ar": f"زيادة المتحصلات {c.cost_reduction_target_pct:.0f}% تتصادم مع حجم المتأخرات",
            "positions": [
                {"agent": "strategy", "stance": "support", "text_en": f"Board objective: +{c.cost_reduction_target_pct:.0f}% collections.",
                 "text_ar": f"هدف مجلس الإدارة: زيادة المتحصلات {c.cost_reduction_target_pct:.0f}%."},
                {"agent": "cfo", "stance": "oppose", "text_en": f"Overdue book is EGP {m(b.overdue_receivables)}M; collections cannot exceed billing for long.",
                 "text_ar": f"المتأخرات {m(b.overdue_receivables)} مليون؛ ولا يمكن أن تتجاوز المتحصلات المفوتر لفترة طويلة."},
                {"agent": "risk", "stance": "oppose", "text_en": f"Max achievable at tolerance: {ach:.1f}% (gap {gap:.1f} pts).",
                 "text_ar": f"أقصى نسبة ممكنة: {ach:.1f}% (فجوة {gap:.1f} نقطة)."},
            ],
            "affected_objectives": ["collections_uplift"],
            "consequences": [{"en": f"Shortfall of EGP {m(base * gap / 100)}M a month vs target",
                              "ar": f"عجز {m(base * gap / 100)} مليون شهرياً عن الهدف"}],
            "resolutions": [{"en": f"Revise the target to ≈{ach:.0f}%", "ar": f"تعديل الهدف إلى ≈{ach:.0f}%"},
                            {"en": "Set a separate one-off target for clearing old debt", "ar": "تحديد هدف منفصل لتحصيل الديون القديمة مرة واحدة"},
                            {"en": "Combine with revenue growth initiatives", "ar": "الجمع مع مبادرات لزيادة المبيعات"}],
            "requires_human": True,
        })
    out.sort(key=lambda x: x["severity_score"], reverse=True)
    return out


def risk_register(ctx: AgentContext) -> list[dict[str, Any]]:
    sim = ctx.simulation
    assert sim is not None
    c, rows = ctx.controls, []
    base = _base_collections(ctx)
    for k in "ABC":
        f = sim["futures"][k]
        p, s, lv = f["probabilities"], f["summary"], f["levers"]
        items = [
            ("R-TGT", "Collections target missed", "عدم تحقيق هدف المتحصلات", 1 - p["meet_target"],
             max(0.0, base * 12 * c.cost_reduction_target_pct / 100 - s["run_rate_savings_at_deadline"]["p50"]),
             "P(uplift < target); impact = median annual gap", "Revise the target; track collections weekly.",
             "تعديل الهدف؛ متابعة المتحصلات أسبوعياً."),
            ("R-REL", "Key-account attrition", "فقد كبار العملاء", p["contractual_breach"], s["delivery_loss_12m"]["p90"],
             "P(attrition > 1% of revenue); impact = P90 relationship loss", "Keep key and government accounts in-house.",
             "إبقاء كبار العملاء والجهات الحكومية داخلياً."),
            ("R-CMP", "Complaints above the acceptable limit", "شكاوى فوق الحد المقبول", 1 - p["delay_within_acceptable"],
             ctx.baseline.annual_revenue * 0.002 * max(0.0, s["max_delay_increase_pct"]["p90"]),
             "P(complaint increase > limit); impact = churn proxy 0.2% revenue per complaint pt",
             "Contact-frequency limits; complaints hotline.", "حدود لمرات التواصل؛ خط ساخن للشكاوى."),
            ("R-CSAT", "Customer satisfaction decline", "تراجع رضا العملاء", 1 - p["csat_maintained"],
             ctx.baseline.annual_revenue * max(0.0, c.min_csat_pct - s["min_csat_pct"]["p10"]) * 0.002,
             "P(min CSAT < floor); impact = churn proxy (assumption)", "Monthly account-level satisfaction check.",
             "قياس شهري لرضا كل عميل."),
            ("R-DPL", "Data-protection breach via third party", "تسرب بيانات عبر طرف ثالث", 0.08 * lv["agency_placement"],
             2.0 * lv["agency_placement"], "Expert prior: 8% at full placement; impact = fine and remediation proxy",
             "Data-processing agreement, minimum data shared, audit rights.", "اتفاقية معالجة بيانات، أقل قدر من البيانات، حق التدقيق."),
            ("R-IMP", "Implementation cost overrun", "تجاوز تكلفة التنفيذ",
             float(s["one_off_implementation_cost"]["p90"] > c.implementation_budget) * 0.1 + 0.25,
             max(0.0, s["one_off_implementation_cost"]["p90"] - s["one_off_implementation_cost"]["expected"]),
             "Overrun prior (0.95-1.4x); impact = P90 minus expected cost", "Stage-gate funding.", "تمويل على مراحل."),
        ]
        for code, en, ar, prob, impact, basis, mit_en, mit_ar in items:
            if prob <= 0 and code == "R-DPL":
                continue
            exp_loss = prob * impact
            sev = "critical" if exp_loss > 3 else "high" if exp_loss > 1 else "medium" if exp_loss > 0.3 else "low"
            rows.append({"scenario_key": k, "risk_code": code, "title_en": en, "title_ar": ar,
                         "probability": round(float(prob), 3), "impact_egp_m": round(float(impact), 2), "severity": sev,
                         "basis": basis, "mitigation_en": mit_en, "mitigation_ar": mit_ar})
    return rows


# ======================================================================== recommendation text
NEXT_STEPS = [
    {"en": "Load the real receivables ageing report and reconcile the margin (DQ-002)", "ar": "تحميل تقرير أعمار المديونيات الحقيقي وتسوية الهامش (DQ-002)"},
    {"en": "Tender two collection agencies with a 3-month paid-on-results pilot on aged debt", "ar": "طرح مناقصة لشركتي تحصيل مع تجربة 3 أشهر على الديون القديمة والدفع حسب النتائج"},
    {"en": "Legal: data-processing agreement and fair-conduct clauses (GOV-015, GOV-016)", "ar": "الشؤون القانونية: اتفاقية معالجة البيانات وبنود التحصيل العادل (GOV-015 وGOV-016)"},
    {"en": "Launch e-invoicing, reminders and payment links for all customers", "ar": "إطلاق الفوترة الإلكترونية والتذكيرات وروابط الدفع لكل العملاء"},
    {"en": "Submit the selected future for approval by the required roles", "ar": "تقديم المستقبل المختار للاعتماد من الأدوار المطلوبة"},
]
ROADMAP = [
    {"phase": "0–1", "en": "Ageing review with sales; payment links and reminders; segment the overdue book",
     "ar": "مراجعة الأعمار مع المبيعات؛ روابط الدفع والتذكيرات؛ تقسيم المتأخرات"},
    {"phase": "1–3", "en": "Agency tender and pilot on debt over 90 days; data-processing agreement; team training",
     "ar": "مناقصة شركة التحصيل وتجربة على الديون الأقدم من 90 يوماً؛ اتفاقية معالجة البيانات؛ تدريب الفريق"},
    {"phase": "3–6", "en": "Scale what the pilot proves; early-payment offer; weekly collections dashboard",
     "ar": "توسيع ما تثبته التجربة؛ عرض السداد المبكر؛ لوحة متابعة أسبوعية للمتحصلات"},
    {"phase": "6–12", "en": "Monthly predicted-vs-actual review of collections, complaints and DSO; recalibrate",
     "ar": "مراجعة شهرية للمتوقع مقابل الفعلي في المتحصلات والشكاوى وفترة التحصيل؛ إعادة المعايرة"},
]
