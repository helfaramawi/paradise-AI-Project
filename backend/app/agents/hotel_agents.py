"""Agents, court rules, collision rules and risk register for the hotel asset decision domain.

Same contracts as domain.py / court.py / collision.py (structured, bilingual, evidence-linked findings
computed from the dataset and the hotel simulation); only the business questions differ: which proposal
gets the most out of a state-owned hotel - a long-term lease, a renovation under a brand management
contract, or a mixed-use repositioning for Free Zone investors - and at what cost to capital, staff,
service continuity and control of a public asset.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..simulation.hotel import REDEPLOY_CAPACITY_FTE
from .base import AgentContext, Evidence, Finding, Objection, m
from .domain import _fa, _fe


def _ds(ref: str, label: str, value: str) -> Evidence:
    return Evidence("dataset", ref, label, value, verified=False)


def _sim(ref: str, label: str, value: str) -> Evidence:
    return Evidence("simulation", ref, label, value)


def _s(f: dict, k: str, q: str = "p50") -> float:
    return f["summary"][k][q]


def _base_net(ctx: AgentContext) -> float:
    """Owner's annual net result today (hotel revenue minus staff, fixed and variable costs)."""
    b = ctx.baseline
    rooms_rev = b.hotel_rooms * 365 * b.hotel_occupancy_pct / 100 * b.hotel_adr_egp / 1e6
    rev = rooms_rev * 1.30
    return rev - b.hotel_staff_fte * 0.18 - b.hotel_fixed_opex - 0.32 * rev


def _base_rev(ctx: AgentContext) -> float:
    b = ctx.baseline
    return b.hotel_rooms * 365 * b.hotel_occupancy_pct / 100 * b.hotel_adr_egp / 1e6 * 1.30


# ======================================================================== phase 1
def strategy_analyze(ctx: AgentContext) -> list[Finding]:
    b, c = ctx.baseline, ctx.controls
    goal = b.hotel_asset_value * c.cost_reduction_target_pct / 100
    stated = "target" in (ctx.intake.get("detected") or [])
    return [
        Finding("strategy", "STR-01", "fact", "objective",
                f"Objective: get the most out of the {b.hotel_rooms}-room hotel owned by the Authority: turn today's annual "
                f"result (EGP {m(_base_net(ctx))}M) into a net return of {c.cost_reduction_target_pct:.0f}% of the asset value "
                f"(EGP {m(goal)}M a year) within {c.implementation_months} months, without terminations"
                + ("" if stated else " (the question states no target; 6% is an assumed benchmark the executive can change)") + ".",
                f"الهدف: تعظيم الاستفادة من الفندق المملوك للجهاز ({b.hotel_rooms} غرفة): تحويل النتيجة السنوية الحالية "
                f"({m(_base_net(ctx))} مليون جنيه) إلى عائد صافٍ {c.cost_reduction_target_pct:.0f}% من قيمة الأصل "
                f"({m(goal)} مليون سنوياً) خلال {c.implementation_months} شهراً، دون إنهاء خدمة أحد"
                + ("" if stated else " (السؤال لم يحدد هدفاً رقمياً؛ نسبة 6% افتراض مرجعي يمكن للإدارة تعديله)") + ".",
                0.9, [_ds("baseline.hotel_asset_value", "Indicative asset value", f"EGP {m(b.hotel_asset_value)}M"),
                      Evidence("assumption", "controls.cost_reduction_target_pct", "Target return", f"{c.cost_reduction_target_pct:.0f}%")]),
        Finding("strategy", "STR-02", "estimate", "options",
                "Three structurally different proposals are compared: lease the asset to a private operator, invest and "
                "keep the revenue under a brand management contract, or reposition the building for Free Zone investors "
                "(serviced apartments and a business centre) while keeping a smaller hotel.",
                "تتم مقارنة ثلاثة مقترحات مختلفة جذرياً: تأجير الأصل لمشغل خاص، أو الاستثمار مع الاحتفاظ بالإيراد عبر "
                "عقد إدارة مع علامة فندقية، أو إعادة توظيف المبنى لخدمة مستثمري المنطقة الحرة (شقق فندقية ومركز أعمال) "
                "مع الإبقاء على فندق أصغر.",
                0.8, [Evidence("assumption", "futures", "Proposals A, B, C", "generated from the question")]),
        Finding("strategy", "STR-03", "recommendation", "success_criteria",
                f"Success criteria: net return ≥ {c.cost_reduction_target_pct:.0f}% of the asset value by month "
                f"{c.implementation_months}; rooms out of service ≤ {c.acceptable_delay_increase_pct:.0f}% at any time; guest "
                f"score ≥ {c.min_csat_pct:.0f}%; surplus staff ≤ {REDEPLOY_CAPACITY_FTE:.0f}; zero terminations; capital "
                f"investment ≤ EGP {m(c.implementation_budget)}M.",
                f"معايير النجاح: عائد صافٍ ≥ {c.cost_reduction_target_pct:.0f}% من قيمة الأصل بحلول الشهر {c.implementation_months}؛ "
                f"الغرف خارج الخدمة ≤ {c.acceptable_delay_increase_pct:.0f}% في أي وقت؛ تقييم النزلاء ≥ {c.min_csat_pct:.0f}%؛ "
                f"العمالة الزائدة ≤ {REDEPLOY_CAPACITY_FTE:.0f}؛ صفر إنهاء خدمة؛ استثمار رأسمالي ≤ {m(c.implementation_budget)} مليون.",
                0.9, [Evidence("assumption", "controls", "Executive controls", "user-defined")]),
    ]


def cfo_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    rev, net = _base_rev(ctx), _base_net(ctx)
    staff = b.hotel_staff_fte * 0.18
    return [
        Finding("cfo", "CFO-01", "fact", "asset_economics",
                f"At {b.hotel_occupancy_pct:.0f}% occupancy and an average rate of EGP {b.hotel_adr_egp:,.0f}, the hotel earns "
                f"about EGP {m(rev)}M a year and records a result of EGP {m(net)}M: staff alone cost EGP {m(staff)}M. "
                f"Against an indicative value of EGP {m(b.hotel_asset_value)}M the asset returns {net / b.hotel_asset_value * 100:.1f}%.",
                f"عند إشغال {b.hotel_occupancy_pct:.0f}% ومتوسط سعر {b.hotel_adr_egp:,.0f} جنيه يحقق الفندق نحو {m(rev)} مليون "
                f"سنوياً بنتيجة {m(net)} مليون: تكلفة العاملين وحدها {m(staff)} مليون. ومقابل قيمة تقديرية "
                f"{m(b.hotel_asset_value)} مليون فإن عائد الأصل {net / b.hotel_asset_value * 100:.1f}%.",
                0.8, [_ds("baseline.hotel_occupancy_pct", "Occupancy", f"{b.hotel_occupancy_pct:.0f}%"),
                      _ds("baseline.hotel_adr_egp", "Average daily rate", f"EGP {b.hotel_adr_egp:,.0f}"),
                      _ds("baseline.hotel_staff_fte", "Hotel staff", f"{b.hotel_staff_fte:.0f}")]),
        Finding("cfo", "CFO-02", "estimate", "capital",
                f"The Authority has EGP {m(b.hotel_capex_reserve)}M allocated to the hotel. Any proposal that needs more must "
                f"be funded from other budgets or financing, and should be judged on return per pound invested, not only on "
                f"its final return.",
                f"خصص الجهاز {m(b.hotel_capex_reserve)} مليون جنيه للفندق. أي مقترح يحتاج أكثر من ذلك يجب تمويله من موازنات "
                f"أخرى أو بالاقتراض، ويجب الحكم عليه بالعائد على كل جنيه مستثمر وليس بالعائد النهائي وحده.",
                0.7, [_ds("baseline.hotel_capex_reserve", "Funds allocated", f"EGP {m(b.hotel_capex_reserve)}M")]),
        Finding("cfo", "CFO-03", "assumption", "valuation",
                "The asset value, room rate and occupancy are illustrative assumptions; no audited hotel accounts or "
                "independent valuation have been loaded. A valuation is required before any tender or investment.",
                "قيمة الأصل وسعر الغرفة والإشغال افتراضات توضيحية؛ لم تُحمّل حسابات مدققة للفندق ولا تقييم مستقل. "
                "يلزم تقييم مستقل قبل أي مناقصة أو استثمار.",
                0.5, [Evidence("assumption", "baseline.hotel_asset_value", "Indicative value", "assumption")],
                ["Figures are illustrative"]),
    ]


def coo_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    return [
        Finding("coo", "COO-01", "fact", "operations",
                f"{b.hotel_staff_fte:.0f} staff run {b.hotel_rooms} rooms at {b.hotel_staff_utilization_pct:.0f}% utilisation: the "
                f"team is sized for a busier hotel. Selling more room-nights is the main lever, not cutting costs.",
                f"يدير {b.hotel_staff_fte:.0f} عاملاً {b.hotel_rooms} غرفة باستغلال {b.hotel_staff_utilization_pct:.0f}%: الفريق "
                f"مُعدّ لفندق أكثر نشاطاً. بيع ليالٍ أكثر هو الرافعة الأساسية وليس خفض التكاليف.",
                0.8, [_ds("baseline.hotel_staff_utilization_pct", "Staff utilisation", f"{b.hotel_staff_utilization_pct:.0f}%")]),
        Finding("coo", "COO-02", "hypothesis", "demand",
                "Free Zone companies bring visiting investors, technicians and expatriate staff who need long stays, "
                "meeting rooms and services near the port. No survey of this demand exists yet.",
                "شركات المنطقة الحرة تجلب مستثمرين زائرين وفنيين وعاملين أجانب يحتاجون إقامات طويلة وقاعات اجتماعات "
                "وخدمات قريبة من الميناء. لا يوجد بعدُ مسح لهذا الطلب.",
                0.45, [Evidence("assumption", "params.apartment_occupancy", "Serviced-apartment occupancy prior", "65% / 85% / 95%")],
                ["Demand from Free Zone companies is not yet measured"]),
    ]


def hr_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    return [
        Finding("hr", "HR-01", "fact", "constraint",
                f"The no-termination constraint protects the {b.hotel_staff_fte:.0f} hotel employees. The Authority can absorb "
                f"about {REDEPLOY_CAPACITY_FTE:.0f} of them in other departments; any larger surplus stays on the payroll idle.",
                f"قيد عدم الإنهاء يحمي {b.hotel_staff_fte:.0f} من العاملين بالفندق. يستطيع الجهاز استيعاب نحو "
                f"{REDEPLOY_CAPACITY_FTE:.0f} منهم في إدارات أخرى؛ وأي فائض أكبر يبقى على قوة العمل دون مهام.",
                0.85, [_ds("baseline.hotel_staff_fte", "Hotel staff", f"{b.hotel_staff_fte:.0f}")]),
    ]


def delivery_analyze(ctx: AgentContext) -> list[Finding]:
    b = ctx.baseline
    return [
        Finding("delivery", "DEL-01", "fact", "guest_experience",
                f"Guest score is {b.hotel_guest_score_pct:.0f}%. Rooms out of service during works lose revenue and reviews; the "
                f"hotel also hosts official Free Zone visitors, so service continuity matters beyond money.",
                f"تقييم النزلاء {b.hotel_guest_score_pct:.0f}%. الغرف خارج الخدمة أثناء الأعمال تفقد إيراداً وتقييمات؛ كما "
                f"يستضيف الفندق زوار المنطقة الحرة الرسميين، فاستمرارية الخدمة مهمة بما يتجاوز المال.",
                0.7, [_ds("baseline.hotel_guest_score_pct", "Guest score", f"{b.hotel_guest_score_pct:.0f}%")]),
    ]


def legal_analyze(ctx: AgentContext) -> list[Finding]:
    return [
        Finding("legal", "LEG-01", "hypothesis", "public_assets",
                "Leasing or granting usufruct of a state-owned asset must follow the Public Contracts Law (Law 182 of 2018): "
                "public tender, independent valuation and approval by the competent authority.",
                "تأجير أصل مملوك للدولة أو منح حق انتفاع به يجب أن يتبع قانون التعاقدات العامة (القانون 182 لسنة 2018): "
                "مناقصة عامة وتقييم مستقل وموافقة السلطة المختصة.",
                0.55, [Evidence("policy", "GOV-017", "Long-term use of a state-owned asset", "require_approval", verified=True)]),
        Finding("legal", "LEG-02", "hypothesis", "contracts",
                "A brand management contract and large works contracts also need procurement and legal review; serviced-"
                "apartment and retail leases to Free Zone companies need standard lease terms.",
                "عقد الإدارة مع علامة فندقية وعقود الأعمال الكبيرة تحتاج أيضاً إجراءات تعاقد ومراجعة قانونية؛ وعقود تأجير "
                "الشقق والوحدات التجارية لشركات المنطقة الحرة تحتاج شروط إيجار موحدة.",
                0.45, [Evidence("policy", "GOV-018", "Capital investment in a state-owned asset", "require_approval", verified=True)]),
    ]


def risk_analyze(ctx: AgentContext) -> list[Finding]:
    v = ctx.validation
    errors = [x.code for x in v.checks if x.severity == "error"]
    return [
        Finding("risk", "RSK-01", "fact", "data_quality",
                f"Data quality score {v.quality_score:.0%}. Errors: {', '.join(errors) or 'none'}. The hotel figures are "
                f"illustrative assumptions; there is no trading history to calibrate occupancy or rate forecasts.",
                f"درجة جودة البيانات {v.quality_score:.0%}. الأخطاء: {', '.join(errors) or 'لا يوجد'}. أرقام الفندق افتراضات "
                f"توضيحية؛ ولا يوجد سجل تشغيل لمعايرة توقعات الإشغال والسعر.",
                0.9, [Evidence("validation", c, "Validation check", "error", verified=True) for c in errors]
                or [Evidence("validation", "DQ", "Validation", "ok", verified=True)]),
    ]


# ======================================================================== phase 2 (with simulation)
def _within_budget(ctx: AgentContext, f: dict) -> bool:
    return _s(f, "one_off_implementation_cost") <= ctx.controls.implementation_budget and _s(f, "min_cash_balance") >= 0


def cfo_evaluate(ctx: AgentContext) -> list[Finding]:
    fs = {k: ctx.fut(k) for k in "ABC"}
    funded = [k for k in "ABC" if _within_budget(ctx, fs[k]) and _s(fs[k], "one_off_implementation_cost") > 1]
    best = max(funded, key=lambda k: _s(fs[k], "stabilised_yield_pct")) if funded else None
    out = []
    for k in "ABC":
        f = fs[k]
        y, ys, capex, pb = (_s(f, "savings_pct_at_deadline"), _s(f, "stabilised_yield_pct"),
                            _s(f, "one_off_implementation_cost"), _s(f, "payback_years"))
        if k == best:
            stance = "support"
        elif f["levers"]["lease_to_operator"] > 0 or not _within_budget(ctx, f):
            stance = "conditional"
        else:
            stance = "conditional" if ys > 0 else "oppose"
        cap_en = (f"needs no capital (rent from month {6 if k == 'A' else 0})" if capex < 2
                  else f"needs EGP {m(capex)}M of capital (payback about {pb:.1f} years)")
        cap_ar = ("لا يحتاج رأس مال" if capex < 2 else f"يحتاج استثماراً {m(capex)} مليون (استرداد خلال نحو {pb:.1f} سنة)")
        out.append(Finding(
            "cfo", f"CFO-F{k}", "estimate", "return", strategy_key=k, stance=stance, phase="court",
            text_en=f"{_fe(k)} {cap_en}. Median net return {y:.1f}% of the asset value at month "
                    f"{ctx.controls.implementation_months}, {ys:.1f}% once stabilised (EGP {m(_s(f, 'steady_state_net_run_rate'))}M "
                    f"a year); lowest cash balance EGP {m(_s(f, 'min_cash_balance'))}M.",
            text_ar=f"{_fa(k)} {cap_ar}. العائد الصافي الوسيط {y:.1f}% من قيمة الأصل في الشهر {ctx.controls.implementation_months}، "
                    f"و{ys:.1f}% بعد الاستقرار ({m(_s(f, 'steady_state_net_run_rate'))} مليون سنوياً)؛ أدنى رصيد نقدي "
                    f"{m(_s(f, 'min_cash_balance'))} مليون.",
            confidence=0.7,
            evidence=[_sim(f"futures.{k}.summary.savings_pct_at_deadline.p50", "Median return at deadline", f"{y:.1f}%"),
                      _sim(f"futures.{k}.summary.stabilised_yield_pct.p50", "Stabilised return", f"{ys:.1f}%"),
                      _sim(f"futures.{k}.summary.one_off_implementation_cost.p50", "Capital investment", f"EGP {m(capex)}M")]))
    return out


def delivery_evaluate(ctx: AgentContext) -> list[Finding]:
    out, acc = [], ctx.controls.acceptable_delay_increase_pct
    for k in "ABC":
        f = ctx.fut(k)
        pp = f["project_portfolio"]
        peak, guest = _s(f, "max_delay_increase_pct"), _s(f, "min_csat_pct")
        stance = "oppose" if peak > acc else ("conditional" if pp["projects_at_risk"] > 0 else "support")
        spaces = ", ".join(r["name_en"] for r in pp["projects"] if r["at_risk"]) or "none"
        spaces_ar = "، ".join(r["name_ar"] for r in pp["projects"] if r["at_risk"]) or "لا يوجد"
        out.append(Finding(
            "delivery", f"DEL-F{k}", "estimate", "service_continuity", strategy_key=k, stance=stance, phase="court",
            text_en=f"{_fe(k)}: up to {peak:.0f}% of rooms out of service (limit {acc:.0f}%); lowest guest score {guest:.0f}%. "
                    f"Spaces closed more than 3 months: {spaces}.",
            text_ar=f"{_fa(k)}: حتى {peak:.0f}% من الغرف خارج الخدمة (الحد {acc:.0f}%)؛ أدنى تقييم للنزلاء {guest:.0f}%. "
                    f"المساحات المغلقة أكثر من 3 أشهر: {spaces_ar}.",
            confidence=0.6,
            evidence=[_sim(f"futures.{k}.summary.max_delay_increase_pct.p50", "Peak rooms out of service", f"{peak:.0f}%"),
                      Evidence("des", f"futures.{k}.project_portfolio.projects_at_risk", "Spaces closed > 3 months",
                               str(pp["projects_at_risk"]))]))
    return out


def hr_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in "ABC":
        f = ctx.fut(k)
        surplus, util = _s(f, "staff_surplus_fte"), _s(f, "peak_utilization_pct")
        if surplus > 0:
            stance = "oppose" if surplus > REDEPLOY_CAPACITY_FTE else "conditional"
            en = (f"{_fe(k)}: the operator takes over part of the team; about {surplus:.0f} employees stay with the Authority "
                  f"against a redeployment capacity of {REDEPLOY_CAPACITY_FTE:.0f}. The rest would be paid without work.")
            ar = (f"{_fa(k)}: المشغل ينقل جزءاً من الفريق؛ ويبقى نحو {surplus:.0f} موظفاً على قوة الجهاز مقابل طاقة إعادة توزيع "
                  f"{REDEPLOY_CAPACITY_FTE:.0f} فقط. والباقون سيتقاضون أجوراً دون عمل.")
        else:
            stance = "support" if util <= ctx.controls.max_utilization_pct else "conditional"
            en = (f"{_fe(k)} keeps all employees; peak utilisation {util:.0f}%. Part of the team needs retraining "
                  f"(brand standards, apartments, business centre).")
            ar = (f"{_fa(k)} يحتفظ بجميع العاملين؛ الاستغلال الأقصى {util:.0f}%. يحتاج جزء من الفريق إلى إعادة تأهيل "
                  f"(معايير العلامة، الشقق، مركز الأعمال).")
        out.append(Finding("hr", f"HR-F{k}", "estimate", "workforce", strategy_key=k, stance=stance, phase="court",
                           text_en=en, text_ar=ar, confidence=0.6,
                           evidence=[_sim(f"futures.{k}.summary.staff_surplus_fte.p50", "Surplus staff", f"{surplus:.0f}"),
                                     _sim(f"futures.{k}.summary.peak_utilization_pct.p50", "Peak utilisation", f"{util:.0f}%")],
                           assumptions=[f"Redeployment capacity {REDEPLOY_CAPACITY_FTE:.0f} employees"]))
    return out


def coo_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in "ABC":
        f = ctx.fut(k)
        occ = f["trajectory"]["occupancy_pct"]["expected"]
        stance = "conditional" if f["levers"]["lease_to_operator"] > 0 else "support"
        out.append(Finding(
            "coo", f"COO-F{k}", "estimate", "trading", strategy_key=k, stance=stance, phase="court",
            text_en=f"{_fe(k)}: occupancy {occ[0]:.0f}% → {occ[-1]:.0f}% by month 12"
                    + (" under the operator; the Authority no longer runs the hotel." if stance == "conditional"
                       else "; demand still has to be proven by the first months of sales."),
            text_ar=f"{_fa(k)}: الإشغال {occ[0]:.0f}% ← {occ[-1]:.0f}% بحلول الشهر 12"
                    + (" تحت إدارة المشغل؛ ولن يدير الجهاز الفندق بعد ذلك." if stance == "conditional"
                       else "؛ ويبقى إثبات الطلب في أشهر البيع الأولى."),
            confidence=0.55,
            evidence=[_sim(f"futures.{k}.trajectory.occupancy_pct.expected", "Occupancy path", f"{occ[-1]:.0f}% at month 12")],
            assumptions=["Occupancy ramps over 8-18 months after works"]))
    return out


def legal_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in "ABC":
        lv = ctx.fut(k)["levers"]
        if lv["lease_to_operator"] > 0:
            en = (f"{_fe(k)} grants a 15-year usufruct of a state-owned asset: public tender under Law 182 of 2018, independent "
                  f"valuation, rent review clauses and approval by the competent authority are required (GOV-017).")
            ar = (f"{_fa(k)} يمنح حق انتفاع 15 عاماً بأصل مملوك للدولة: يلزم مناقصة عامة وفق القانون 182 لسنة 2018 وتقييم مستقل "
                  f"وبنود لمراجعة الإيجار وموافقة السلطة المختصة (GOV-017).")
            ev = [Evidence("policy", "GOV-017", "Long-term use of a state-owned asset", "require_approval", verified=True)]
        elif lv["brand_management"] > 0:
            en = (f"{_fe(k)} needs a management contract (fees, performance tests, exit clauses) and works procured under the "
                  f"public contracts rules; capital above EGP 50M needs CFO and CEO approval (GOV-018).")
            ar = (f"{_fa(k)} يحتاج عقد إدارة (أتعاب واختبارات أداء وبنود إنهاء) وطرح الأعمال وفق قواعد التعاقدات العامة؛ "
                  f"والاستثمار فوق 50 مليون يحتاج موافقة المدير المالي والرئيس التنفيذي (GOV-018).")
            ev = [Evidence("policy", "GOV-018", "Capital investment in a state-owned asset", "require_approval", verified=True)]
        else:
            en = f"{_fe(k)} keeps ownership and operation; apartment and retail leases need standard short-term terms."
            ar = f"{_fa(k)} يحتفظ بالملكية والتشغيل؛ وتحتاج عقود الشقق والوحدات التجارية شروط إيجار قصيرة الأجل موحدة."
            ev = [Evidence("assumption", "contracts", "Short-term leases", "standard terms")]
        out.append(Finding("legal", f"LEG-F{k}", "hypothesis", "compliance", strategy_key=k,
                           stance="conditional" if lv["lease_to_operator"] or lv["brand_management"] else "support",
                           phase="court", text_en=en, text_ar=ar, confidence=0.45, evidence=ev,
                           assumptions=["Contracts not yet drafted"]))
    return out


def strategy_evaluate(ctx: AgentContext) -> list[Finding]:
    c = ctx.controls
    ach = {k: ctx.fut(k)["achievable_reduction_pct_at_tolerance"] for k in "ABC"}
    stab = {k: _s(ctx.fut(k), "stabilised_yield_pct") for k in "ABC"}
    best = max(ach, key=ach.get)
    feasible = [k for k in "ABC" if ach[k] >= c.cost_reduction_target_pct]
    if feasible:
        en = f"The target return is achievable at the {c.risk_tolerance} risk tolerance in: {', '.join(_fe(k) for k in feasible)}."
        ar = f"العائد المستهدف قابل للتحقيق عند مستوى المخاطرة المختار في: {'، '.join(_fa(k) for k in feasible)}."
        ct = "estimate"
    else:
        later = [k for k in "ABC" if stab[k] >= c.cost_reduction_target_pct]
        en = (f"No proposal returns {c.cost_reduction_target_pct:.0f}% of the asset value within {c.implementation_months} months "
              f"at the {c.risk_tolerance} risk tolerance (highest {ach[best]:.1f}%, {_fe(best)}): works and ramp-up take time."
              + (f" Once stabilised, {', '.join(_fe(k) for k in later)} exceeds it." if later else ""))
        ar = (f"لا يحقق أي مقترح عائداً {c.cost_reduction_target_pct:.0f}% من قيمة الأصل خلال {c.implementation_months} شهراً عند "
              f"مستوى المخاطرة المختار (الأعلى {ach[best]:.1f}%، {_fa(best)}): الأعمال ومرحلة الانطلاق تحتاج وقتاً."
              + (f" وبعد الاستقرار يتجاوزه {'، '.join(_fa(k) for k in later)}." if later else ""))
        ct = "recommendation"
    return [Finding("strategy", "STR-F", ct, "feasibility", en, ar, 0.7,
                    [_sim(f"futures.{k}.achievable_reduction_pct_at_tolerance", f"Achievable return {_fe(k)}", f"{ach[k]:.1f}%")
                     for k in "ABC"], phase="court")]


def risk_evaluate(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in "ABC":
        f = ctx.fut(k)
        top, p = f["sensitivity"][0], f["probabilities"]
        out.append(Finding(
            "risk", f"RSK-F{k}", "estimate", "uncertainty", strategy_key=k, phase="court",
            stance=("oppose" if f["hard_constraints_violated"] else "conditional"
                    if _s(f, "one_off_implementation_cost", "p90") > ctx.controls.implementation_budget
                    or _s(f, "min_cash_balance") < 0 else "support"),
            text_en=f"{_fe(k)}: P(meet target) {p['meet_target']:.0%}, P(rooms out of service within limit) "
                    f"{p['delay_within_acceptable']:.0%}, P(guest score maintained) {p['csat_maintained']:.0%}. Largest "
                    f"uncertainty driver: {top['label_en']} (net-benefit swing EGP {m(top['swing'])}M).",
            text_ar=f"{_fa(k)}: احتمال تحقيق الهدف {p['meet_target']:.0%}، احتمال بقاء الغرف خارج الخدمة ضمن الحد "
                    f"{p['delay_within_acceptable']:.0%}، احتمال الحفاظ على تقييم النزلاء {p['csat_maintained']:.0%}. أكبر مصدر "
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
    fut = sim["futures"]
    # R1: the brand's occupancy gain behind Future B is an unvalidated prior
    sens = {s["parameter"]: s for s in fut["B"]["sensitivity"]}
    occ = sens.get("brand_occupancy_gain")
    if occ:
        obs.append(Objection(
            "redteam", "cfo", "CFO-FB", "B", "unsupported_assumption", "high",
            f"Future B's return rests on a brand lifting occupancy by 24 points. No branded hotel operates downtown to "
            f"benchmark it. At +16 points the 12-month net benefit falls to EGP {m(occ['net_benefit_at_low'])}M.",
            f"عائد المستقبل ب يعتمد على أن ترفع العلامة الإشغال 24 نقطة. لا يوجد فندق بعلامة عالمية في وسط البلد للمقارنة. "
            f"عند 16 نقطة فقط ينخفض صافي المنفعة خلال 12 شهراً إلى {m(occ['net_benefit_at_low'])} مليون."))
    # R2: capital overrun on the investment futures
    for k in "BC":
        s = fut[k]["summary"]["one_off_implementation_cost"]
        if s["p90"] > s["expected"] * 1.12:
            obs.append(Objection(
                "redteam", "cfo", f"CFO-F{k}", k, "optimism", "medium",
                f"{_fe(k)} capital: expected EGP {m(s['expected'])}M but P90 EGP {m(s['p90'])}M. Old buildings hide electrical, "
                f"plumbing and fire-code works; budget at P90.",
                f"استثمار {_fa(k)}: المتوقع {m(s['expected'])} مليون لكن P90 يبلغ {m(s['p90'])} مليون. المباني القديمة تخفي أعمال "
                f"كهرباء وسباكة واشتراطات حماية مدنية؛ يجب الموازنة عند P90."))
    # R3: lease lock-in
    fa = fut["A"]["summary"]
    obs.append(Objection(
        "redteam", "cfo", "CFO-FA", "A", "hidden_dependency", "high",
        f"Future A locks the asset for 15 years at a rent bid today (median return {fa['stabilised_yield_pct']['p50']:.1f}%). "
        f"If Port Said's Free Zone grows, the upside goes to the operator; the CFO case does not price this lock-in.",
        f"المستقبل أ يربط الأصل 15 عاماً بإيجار يُعرض اليوم (عائد وسيط {fa['stabilised_yield_pct']['p50']:.1f}%). إذا نمت "
        f"المنطقة الحرة ببورسعيد يذهب المكسب للمشغل؛ وحجة المدير المالي لا تحسب تكلفة هذا الارتباط."))
    # R4: CFO supports, HR or Delivery opposes the same future
    for k in "ABC":
        cf = _find(findings, f"CFO-F{k}")
        opp = [f for f in (_find(findings, f"HR-F{k}"), _find(findings, f"DEL-F{k}")) if f and f.stance == "oppose"]
        if cf and cf.stance in ("support", "conditional") and opp:
            obs.append(Objection(
                "redteam", "cfo", cf.code, k, "contradiction", "high",
                f"Contradiction on {_fe(k)}: the CFO Agent accepts it for its income, while "
                f"{' and '.join(o.agent.upper() for o in opp)} oppose it (surplus staff or a closed hotel). The income figure "
                f"does not price those costs.",
                f"تناقض حول {_fa(k)}: وكيل المدير المالي يقبله بسبب دخله، بينما يعارضه "
                f"{' و'.join('الموارد البشرية' if o.agent == 'hr' else 'التشغيل' for o in opp)} (عمالة زائدة أو فندق مغلق). "
                f"رقم الدخل لا يحسب هذه التكاليف."))
    # R5: data integrity
    obs.append(Objection(
        "redteam", "cfo", "CFO-03", None, "data_integrity", "high",
        "Every projection rests on illustrative hotel figures: no audited accounts, no independent valuation and no trading "
        "history have been loaded.",
        "كل التوقعات تعتمد على أرقام توضيحية للفندق: لم تُحمّل حسابات مدققة ولا تقييم مستقل ولا سجل تشغيل."))
    # R6: target infeasible within the timeline
    ach = {k: fut[k]["achievable_reduction_pct_at_tolerance"] for k in "ABC"}
    if max(ach.values()) < ctx.controls.cost_reduction_target_pct:
        obs.append(Objection(
            "redteam", "strategy", "STR-01", None, "infeasible_objective", "critical",
            f"The {ctx.controls.cost_reduction_target_pct:.0f}% return is not reached by any proposal within "
            f"{ctx.controls.implementation_months} months (max {max(ach.values()):.1f}%). Hotels need works and a ramp-up; "
            f"judge them on a multi-year horizon.",
            f"عائد {ctx.controls.cost_reduction_target_pct:.0f}% لا يتحقق في أي مقترح خلال {ctx.controls.implementation_months} "
            f"شهراً (الأقصى {max(ach.values()):.1f}%). الفنادق تحتاج أعمالاً وفترة انطلاق؛ ويجب تقييمها على أفق عدة سنوات."))
    # R7: demand behind Future C
    sc = {s["parameter"]: s for s in fut["C"]["sensitivity"]}.get("apartment_occupancy")
    if sc:
        obs.append(Objection(
            "redteam", "coo", "COO-FC", "C", "unsupported_assumption", "medium",
            f"Future C assumes 85% of the serviced apartments are let to Free Zone companies. No demand survey exists; at 65% "
            f"the 12-month net benefit is EGP {m(sc['net_benefit_at_low'])}M.",
            f"المستقبل ج يفترض تأجير 85% من الشقق الفندقية لشركات المنطقة الحرة. لا يوجد مسح للطلب؛ وعند 65% يكون صافي "
            f"المنفعة خلال 12 شهراً {m(sc['net_benefit_at_low'])} مليون."))
    return obs


def respond(ctx: AgentContext, obs: list[Objection]) -> list[Objection]:
    for o in obs:
        o.response_by = o.target_agent
        t = o.objection_type
        if t == "unsupported_assumption" and o.strategy_key == "B":
            o.response_en = ("Conceded in part. Mitigation: invite brand proposals with guaranteed minimum performance and test "
                             "the occupancy case with two operators before committing capital.")
            o.response_ar = ("أُقرّ جزئياً. التخفيف: طلب عروض من علامات فندقية مع حد أدنى مضمون للأداء، واختبار افتراض الإشغال "
                             "مع مشغلَين قبل الالتزام برأس المال.")
            o.resolution = "partially"
        elif t == "unsupported_assumption":
            o.response_en = ("Agreed. Mitigation: sign letters of intent with Free Zone companies for the apartments before "
                             "starting the conversion; convert in two phases of 10 apartments.")
            o.response_ar = ("موافق. التخفيف: توقيع خطابات نوايا مع شركات المنطقة الحرة للشقق قبل بدء التحويل، والتحويل على "
                             "مرحلتين من 10 شقق.")
            o.resolution = "partially"
        elif t == "optimism":
            o.response_en = "Agreed. Capital is reported at P90 next to the expected value and released in stage gates after a building survey."
            o.response_ar = "موافق. يُعرض الاستثمار عند P90 بجانب القيمة المتوقعة ويُصرف على مراحل بعد مسح إنشائي للمبنى."
            o.resolution = "resolved"
        elif t == "hidden_dependency":
            o.response_en = ("Acknowledged. A lease would need rent reviews every 3 years, a minimum investment obligation and a "
                             "revenue share; even so the Authority gives up control for 15 years.")
            o.response_ar = ("تم الإقرار. التأجير يحتاج مراجعة للإيجار كل 3 سنوات والتزاماً بحد أدنى للاستثمار ونسبة من الإيراد؛ "
                             "ومع ذلك يتخلى الجهاز عن السيطرة 15 عاماً.")
            o.resolution = "partially"
        elif t == "contradiction":
            o.response_en = "Acknowledged. The CFO position becomes conditional on a staff-transfer plan and service continuity."
            o.response_ar = "تم الإقرار. يصبح موقف المدير المالي مشروطاً بخطة لنقل العاملين واستمرارية الخدمة."
            o.resolution = "partially"
        elif t == "data_integrity":
            o.response_en = ("Cannot be resolved by analysis. Load the hotel's audited accounts and commission an independent "
                             "valuation; governance requires approvers to acknowledge this (GOV-011).")
            o.response_ar = ("لا يمكن حله بالتحليل. يجب تحميل الحسابات المدققة للفندق وطلب تقييم مستقل؛ وتشترط الحوكمة إقرار "
                             "المعتمدين بذلك (GOV-011).")
            o.resolution = "unresolved"
        elif t == "infeasible_objective":
            o.response_en = ("Accepted. The orchestrator presents the return at month 12 and once stabilised, so the executive can "
                             "set a realistic target and horizon.")
            o.response_ar = ("مقبول. يعرض المنسق العائد في الشهر 12 وبعد الاستقرار، ليحدد التنفيذيون هدفاً وأفقاً زمنياً واقعيين.")
            o.resolution = "unresolved"
    return obs


def ethics_findings(ctx: AgentContext) -> list[Finding]:
    out = []
    for k in "ABC":
        f = ctx.fut(k)
        if _s(f, "staff_surplus_fte") > REDEPLOY_CAPACITY_FTE:
            out.append(Finding(
                "governance", f"ETH-H{k}", "hypothesis", "ethics", strategy_key=k, stance="oppose", phase="governance",
                text_en=f"Ethical concern: {_fe(k)} leaves about {_s(f, 'staff_surplus_fte'):.0f} public employees without work "
                        f"for an extended period. A transfer and retraining plan is required before any tender.",
                text_ar=f"مخاوف أخلاقية: {_fa(k)} يترك نحو {_s(f, 'staff_surplus_fte'):.0f} موظفاً عاماً دون عمل لفترة طويلة. "
                        f"يلزم خطة نقل وإعادة تأهيل قبل أي مناقصة.",
                confidence=0.6,
                evidence=[Evidence("policy", "GOV-001", "No employee terminations", "deny", verified=True)]))
    return out


# ======================================================================== collisions and risks
def _sev(score: float) -> str:
    return "critical" if score >= 0.75 else "high" if score >= 0.5 else "medium" if score >= 0.25 else "low"


def _stance(findings: list[Finding], agent: str, k: str) -> Finding | None:
    return next((f for f in findings if f.agent == agent and f.strategy_key == k and f.phase == "court"), None)


def _pos(*fs: Finding | None) -> list[dict[str, Any]]:
    return [{"agent": a.agent, "stance": a.stance, "text_en": a.text_en, "text_ar": a.text_ar} for a in fs if a]


def detect_collisions(ctx: AgentContext, findings: list[Finding]) -> list[dict[str, Any]]:
    sim = ctx.simulation
    assert sim is not None
    c, out = ctx.controls, []
    for k in "ABC":
        f = sim["futures"][k]
        lv, s = f["levers"], f["summary"]
        cfo, hr, dl = (_stance(findings, a, k) for a in ("cfo", "hr", "delivery"))
        # COL-21: lease income vs staff and service continuity
        if lv["lease_to_operator"] > 0:
            surplus = s["staff_surplus_fte"]["p50"]
            score = min(1.0, 0.35 + 0.3 * max(0.0, surplus / REDEPLOY_CAPACITY_FTE - 1) + 0.2 * (s["max_delay_increase_pct"]["p50"] > c.acceptable_delay_increase_pct))
            out.append({
                "rule_code": "COL-21", "strategy_key": k, "severity_score": round(score, 3), "severity": _sev(score),
                "title_en": f"{_fe(k)}: lease income collides with the hotel staff and service continuity",
                "title_ar": f"{_fa(k)}: دخل التأجير يتصادم مع العاملين بالفندق واستمرارية الخدمة",
                "positions": _pos(cfo, hr, dl),
                "affected_objectives": ["asset_return", "staff", "service_continuity"],
                "consequences": [
                    {"en": f"About {surplus:.0f} employees stay with the Authority (redeployment capacity {REDEPLOY_CAPACITY_FTE:.0f})",
                     "ar": f"يبقى نحو {surplus:.0f} موظفاً على قوة الجهاز (طاقة إعادة التوزيع {REDEPLOY_CAPACITY_FTE:.0f})"},
                    {"en": "Hotel closed about 6 months for the operator's refurbishment", "ar": "إغلاق الفندق نحو 6 أشهر لتجديد المشغل"},
                    {"en": "Asset committed for 15 years", "ar": "الأصل مرتبط لمدة 15 عاماً"},
                ],
                "resolutions": [
                    {"en": "Require the operator to take at least 80% of the staff", "ar": "إلزام المشغل بنقل 80% على الأقل من العاملين"},
                    {"en": "Shorter term (7-10 years) with rent reviews", "ar": "مدة أقصر (7-10 سنوات) مع مراجعة الإيجار"},
                    {"en": "Refurbish in phases while open", "ar": "التجديد على مراحل مع استمرار التشغيل"},
                ],
                "requires_human": True,
            })
        # COL-22: return vs capital budget
        capex = s["one_off_implementation_cost"]["p50"]
        if capex > c.implementation_budget:
            score = min(1.0, 0.4 + 0.25 * (capex / max(c.implementation_budget, 1) - 1))
            coo = _stance(findings, "coo", k)
            out.append({
                "rule_code": "COL-22", "strategy_key": k, "severity_score": round(score, 3), "severity": _sev(score),
                "title_en": f"{_fe(k)}: the highest return collides with the capital budget",
                "title_ar": f"{_fa(k)}: العائد الأعلى يتصادم مع الموازنة الاستثمارية",
                "positions": _pos(coo, cfo),
                "affected_objectives": ["asset_return", "capital_budget"],
                "consequences": [
                    {"en": f"Capital EGP {m(capex)}M vs budget EGP {m(c.implementation_budget)}M",
                     "ar": f"الاستثمار {m(capex)} مليون مقابل موازنة {m(c.implementation_budget)} مليون"},
                    {"en": f"Lowest cash balance EGP {m(s['min_cash_balance']['p50'])}M", "ar": f"أدنى رصيد نقدي {m(s['min_cash_balance']['p50'])} مليون"},
                    {"en": f"Stabilised return {s['stabilised_yield_pct']['p50']:.1f}% of the asset value",
                     "ar": f"العائد بعد الاستقرار {s['stabilised_yield_pct']['p50']:.1f}% من قيمة الأصل"},
                ],
                "resolutions": [
                    {"en": "Stage the investment: start with the proposal within budget, add the brand later", "ar": "الاستثمار على مراحل: البدء بالمقترح داخل الموازنة وإضافة العلامة لاحقاً"},
                    {"en": "Ask the brand to co-invest (key money)", "ar": "مطالبة العلامة بالمشاركة في التمويل"},
                    {"en": "Approve additional funding", "ar": "اعتماد تمويل إضافي"},
                ],
                "requires_human": True,
            })
        # COL-23: works disruption vs guests and revenue
        peak = s["max_delay_increase_pct"]["p50"]
        if 0 < peak <= c.acceptable_delay_increase_pct and peak >= 20:
            score = min(0.7, 0.2 + peak / 100)
            out.append({
                "rule_code": "COL-23", "strategy_key": k, "severity_score": round(score, 3), "severity": _sev(score),
                "title_en": f"{_fe(k)}: works schedule collides with guests and revenue",
                "title_ar": f"{_fa(k)}: جدول الأعمال يتصادم مع النزلاء والإيراد",
                "positions": _pos(dl, _stance(findings, "coo", k)),
                "affected_objectives": ["service_continuity", "guest_experience"],
                "consequences": [
                    {"en": f"Up to {peak:.0f}% of rooms out of service", "ar": f"حتى {peak:.0f}% من الغرف خارج الخدمة"},
                    {"en": f"Contribution lost during works EGP {m(s['delivery_loss_12m']['p50'])}M",
                     "ar": f"مساهمة مفقودة أثناء الأعمال {m(s['delivery_loss_12m']['p50'])} مليون"},
                ],
                "resolutions": [
                    {"en": "Work one floor at a time in the low season", "ar": "العمل طابقاً واحداً في كل مرة في موسم الركود"},
                    {"en": "Quiet hours and guest compensation policy", "ar": "ساعات هدوء وسياسة تعويض للنزلاء"},
                ],
                "requires_human": False,
            })
    # COL-24: target return vs timeline
    ach = max(sim["futures"][k]["achievable_reduction_pct_at_tolerance"] for k in "ABC")
    if ach < c.cost_reduction_target_pct:
        gap = c.cost_reduction_target_pct - ach
        score = min(1.0, 0.5 + gap / 10)
        stab = max(sim["futures"][k]["summary"]["stabilised_yield_pct"]["p50"] for k in "ABC")
        out.append({
            "rule_code": "COL-24", "strategy_key": None, "severity_score": round(score, 3), "severity": _sev(score),
            "title_en": f"A {c.cost_reduction_target_pct:.0f}% return within {c.implementation_months} months collides with works and ramp-up time",
            "title_ar": f"عائد {c.cost_reduction_target_pct:.0f}% خلال {c.implementation_months} شهراً يتصادم مع مدة الأعمال والانطلاق",
            "positions": [
                {"agent": "strategy", "stance": "support", "text_en": f"Target: {c.cost_reduction_target_pct:.0f}% of the asset value a year.",
                 "text_ar": f"الهدف: {c.cost_reduction_target_pct:.0f}% من قيمة الأصل سنوياً."},
                {"agent": "risk", "stance": "oppose", "text_en": f"Max achievable at tolerance: {ach:.1f}% at month {c.implementation_months} (gap {gap:.1f} pts).",
                 "text_ar": f"أقصى عائد ممكن: {ach:.1f}% في الشهر {c.implementation_months} (فجوة {gap:.1f} نقطة)."},
                {"agent": "cfo", "stance": "conditional", "text_en": f"Best stabilised return {stab:.1f}% after 2-3 years.",
                 "text_ar": f"أفضل عائد بعد الاستقرار {stab:.1f}% بعد 2-3 سنوات."},
            ],
            "affected_objectives": ["asset_return"],
            "consequences": [{"en": f"Return gap of {gap:.1f} pts at month {c.implementation_months}",
                              "ar": f"فجوة عائد {gap:.1f} نقطة في الشهر {c.implementation_months}"}],
            "resolutions": [{"en": f"Set a month-12 target of ≈{ach:.0f}% and a stabilised target", "ar": f"تحديد هدف ≈{ach:.0f}% للشهر 12 وهدف بعد الاستقرار"},
                            {"en": "Judge proposals on a 3-year horizon", "ar": "تقييم المقترحات على أفق 3 سنوات"}],
            "requires_human": True,
        })
    out.sort(key=lambda x: x["severity_score"], reverse=True)
    return out


def risk_register(ctx: AgentContext) -> list[dict[str, Any]]:
    sim = ctx.simulation
    assert sim is not None
    c, b, rows = ctx.controls, ctx.baseline, []
    for k in "ABC":
        f = sim["futures"][k]
        p, s, lv = f["probabilities"], f["summary"], f["levers"]
        items = [
            ("R-TGT", "Target return missed", "عدم تحقيق العائد المستهدف", 1 - p["meet_target"],
             max(0.0, b.hotel_asset_value * c.cost_reduction_target_pct / 100 - s["owner_net_return_at_deadline"]["p50"]),
             "P(return < target); impact = median annual gap", "Stage targets: month 12 and stabilised.", "أهداف مرحلية: الشهر 12 وبعد الاستقرار."),
            ("R-DEM", "Demand below plan", "طلب أقل من المخطط", 0.3 if not lv["lease_to_operator"] else 0.15,
             max(0.0, s["steady_state_net_run_rate"]["p50"] - s["steady_state_net_run_rate"]["p10"]),
             "Expert prior; impact = P50 minus P10 stabilised return", "Letters of intent with Free Zone companies; phased opening.",
             "خطابات نوايا مع شركات المنطقة الحرة؛ افتتاح على مراحل."),
            ("R-CAP", "Capital cost overrun", "تجاوز التكلفة الاستثمارية",
             0.25 + 0.1 * float(s["one_off_implementation_cost"]["p90"] > c.implementation_budget),
             max(0.0, s["one_off_implementation_cost"]["p90"] - s["one_off_implementation_cost"]["expected"]),
             "Overrun prior (0.95-1.5x); impact = P90 minus expected capital", "Building survey first; stage-gate funding.",
             "مسح إنشائي أولاً؛ تمويل على مراحل."),
            ("R-STF", "Surplus staff without work", "عمالة زائدة دون عمل", p["contractual_breach"],
             max(0.0, s["staff_surplus_fte"]["p90"] - REDEPLOY_CAPACITY_FTE) * 0.18 * 3,
             "P(surplus > redeployment capacity); impact = 3 years of idle salaries", "Transfer quotas in the tender; retraining.",
             "حصص نقل إلزامية في المناقصة؛ إعادة تأهيل."),
            ("R-LCK", "15-year lock-in below market", "ارتباط 15 عاماً بأقل من السوق", 0.35 * lv["lease_to_operator"],
             0.02 * b.hotel_asset_value * 5 * lv["lease_to_operator"], "Expert prior; impact = 2% of value a year for 5 years",
             "Rent reviews every 3 years; revenue share.", "مراجعة الإيجار كل 3 سنوات؛ نسبة من الإيراد."),
            ("R-WRK", "Works delay", "تأخر الأعمال", 0.3 if s["max_delay_increase_pct"]["p50"] > 0 else 0.0,
             s["delivery_loss_12m"]["p90"], "Works-delay prior (0.9-1.5x); impact = P90 lost contribution",
             "Penalties in the works contract; one floor at a time.", "غرامات في عقد الأعمال؛ طابق واحد في كل مرة."),
        ]
        for code, en, ar, prob, impact, basis, mit_en, mit_ar in items:
            if prob <= 0:
                continue
            exp_loss = prob * impact
            sev = "critical" if exp_loss > 5 else "high" if exp_loss > 2 else "medium" if exp_loss > 0.5 else "low"
            rows.append({"scenario_key": k, "risk_code": code, "title_en": en, "title_ar": ar,
                         "probability": round(float(prob), 3), "impact_egp_m": round(float(impact), 2), "severity": sev,
                         "basis": basis, "mitigation_en": mit_en, "mitigation_ar": mit_ar})
    return rows


# ======================================================================== recommendation text
NEXT_STEPS = [
    {"en": "Load the hotel's audited accounts and commission an independent valuation", "ar": "تحميل الحسابات المدققة للفندق وطلب تقييم مستقل"},
    {"en": "Building survey (structure, electrical, fire code) before committing capital", "ar": "مسح إنشائي للمبنى (الإنشاءات والكهرباء والحماية المدنية) قبل الالتزام برأس المال"},
    {"en": "Demand survey and letters of intent with Free Zone companies", "ar": "مسح للطلب وخطابات نوايا مع شركات المنطقة الحرة"},
    {"en": "Legal: procurement route under Law 182 of 2018 (GOV-017, GOV-018)", "ar": "الشؤون القانونية: مسار التعاقد وفق القانون 182 لسنة 2018 (GOV-017 وGOV-018)"},
    {"en": "Submit the selected proposal for approval by the required roles", "ar": "تقديم المقترح المختار للاعتماد من الأدوار المطلوبة"},
]
ROADMAP = [
    {"phase": "0–2", "en": "Valuation, building survey, demand survey; online booking and corporate rates start",
     "ar": "التقييم والمسح الإنشائي ومسح الطلب؛ بدء الحجز الإلكتروني وأسعار الشركات"},
    {"phase": "2–6", "en": "First phase of works one floor at a time; letters of intent for apartments and business centre",
     "ar": "المرحلة الأولى من الأعمال طابقاً بطابق؛ خطابات نوايا للشقق ومركز الأعمال"},
    {"phase": "6–12", "en": "Open the new spaces; staff retraining; monthly predicted-vs-actual review of occupancy and return",
     "ar": "افتتاح المساحات الجديدة؛ إعادة تأهيل العاملين؛ مراجعة شهرية للمتوقع مقابل الفعلي في الإشغال والعائد"},
    {"phase": "12–24", "en": "Decide on phase 2 (brand management) on the evidence of the first year",
     "ar": "اتخاذ قرار المرحلة الثانية (إدارة العلامة) بناءً على نتائج السنة الأولى"},
]
