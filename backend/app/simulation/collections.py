"""Revenue collections improvement model (decision domain "collections").

Answers questions such as "what if we collect 30% more by contracting a collection agency?".
Same contract as the cost model in engine.py - a vectorised monthly model run deterministically
(expected case), as a Monte Carlo over triangular priors, and one-at-a-time for sensitivity -
and the same result shape, so every screen, agent and report reads it the same way. The
summary keys keep their generic names; in this domain they mean:

  savings_pct_at_deadline       uplift in monthly cash collections at the deadline (% vs no action)
  run_rate_savings_at_deadline  that uplift annualised (EGP M / year)
  realized_savings_12m          extra cash collected over 12 months before relationship losses
  implementation_cost_12m       agency fees + early-payment discounts + running + one-off costs
  delivery_loss_12m             collections lost to key-account attrition (relationship loss)
  max_delay_increase_pct        largest rise in the customer complaint rate (points)
  peak_utilization_pct          peak collections-team utilisation

Every number is SYNTHETIC demonstration data or a documented modelling assumption.
"""

from __future__ import annotations

import math
import time
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from .assumptions import Baseline, DecisionControls, SimulationConfig, Triangular, UncertainParameter

MODEL_ID = "collections-uplift"
MODEL_VERSION = "1.0.0"

TERMS_MONTHS = 1.5  # invoices on standard 45-day terms
DISCOUNT_RATE = 0.015  # early-payment discount given on invoices paid early


class CollectionsLevers(BaseModel):
    """Intensity of each collections lever in a strategy (0..1 unless stated)."""

    agency_placement: float = Field(0.0, ge=0, le=1, description="Share of overdue receivables placed with an agency")
    aggressive_tactics: float = Field(0.0, ge=0, le=1, description="High-frequency contact and early legal escalation")
    digital_collections: float = Field(0.0, ge=0, le=10, description="EGP M invested in reminders, payment links, e-invoicing")
    early_payment_discount: float = Field(0.0, ge=0, le=1, description="Offer a 1.5% discount for payment within terms")
    team_reallocation: float = Field(0.0, ge=0, le=1, description="Reassign finance staff to collections (1 = +3 FTE)")
    workforce_termination: float = Field(0.0, ge=0, le=1, description="Present so governance can test and block it")


class CollectionsEconomics(BaseModel):
    agency_onboarding_cost: float = 0.6   # EGP M at full placement: integration, data-protection agreement, legal
    reallocation_training_cost: float = 0.4  # EGP M at full reallocation
    digital_running_cost_rate: float = 0.12  # of investment per year
    complaint_handling_cost: float = 0.05  # EGP M per year per complaint-rate point
    reallocation_fte: float = 3.0


class CollectionsStrategy(BaseModel):
    key: str
    name_en: str
    name_ar: str
    tagline_en: str
    tagline_ar: str
    measures_en: list[str]
    measures_ar: list[str]
    levers: CollectionsLevers
    proposed_by: list[str]


def default_parameters() -> list[UncertainParameter]:
    P, T = UncertainParameter, Triangular
    return [
        P(key="agency_recovery_rate", label_en="Agency monthly recovery rate", label_ar="معدل استرداد شركة التحصيل الشهري",
          unit="share of placed balance per month", dist=T(low=0.05, mode=0.085, high=0.13),
          rationale="Typical contingency agencies recover 5-13% of a placed overdue book per month."),
        P(key="agency_fee_rate", label_en="Agency contingency fee", label_ar="عمولة شركة التحصيل",
          unit="share of amounts recovered", dist=T(low=0.15, mode=0.20, high=0.27),
          rationale="Market range for B2B contingency collection; older debt costs more."),
        P(key="inhouse_recovery_uplift", label_en="In-house recovery uplift from digital tools",
          label_ar="تحسن الاسترداد الداخلي بالأدوات الرقمية", unit="relative uplift at full adoption",
          dist=T(low=0.15, mode=0.35, high=0.60),
          rationale="Automated reminders and payment links speed up in-house follow-up. No pilot data."),
        P(key="ontime_uplift", label_en="On-time payment uplift from digital invoicing",
          label_ar="تحسن السداد في الموعد بالفوترة الرقمية", unit="share of billing at full adoption",
          dist=T(low=0.01, mode=0.025, high=0.04),
          rationale="E-invoicing and payment links reduce missed due dates."),
        P(key="discount_takeup", label_en="Early-payment discount take-up", label_ar="نسبة الاستفادة من خصم السداد المبكر",
          unit="share of late payers", dist=T(low=0.15, mode=0.30, high=0.45),
          rationale="Share of habitually late customers who switch to paying within terms for 1.5%."),
        P(key="complaint_sensitivity", label_en="Complaint sensitivity to collection pressure",
          label_ar="حساسية الشكاوى لضغط التحصيل", unit="complaint pts per unit of contact intensity",
          dist=T(low=0.8, mode=1.6, high=2.8),
          rationale="Third-party and high-frequency contact raise complaints, most of all on key accounts."),
        P(key="csat_complaint_sensitivity", label_en="CSAT sensitivity to complaints", label_ar="حساسية رضا العملاء للشكاوى",
          unit="CSAT pts per complaint pt", dist=T(low=0.6, mode=1.0, high=1.6),
          rationale="Customer satisfaction points lost per additional complaint point."),
        P(key="key_account_churn", label_en="Key-account attrition under aggressive collection",
          label_ar="فقد كبار العملاء تحت التحصيل الحاد", unit="share of key-account revenue per year",
          dist=T(low=0.01, mode=0.03, high=0.07),
          rationale="Government and key corporate clients may reduce business after aggressive third-party contact."),
        P(key="digital_adoption_months", label_en="Digital collections adoption time", label_ar="مدة تبني التحصيل الرقمي",
          unit="months", dist=T(low=3.0, mode=5.0, high=8.0),
          rationale="Months to full adoption (S-curve midpoint at half this value)."),
        P(key="agency_ramp_months", label_en="Agency onboarding time", label_ar="مدة تجهيز شركة التحصيل",
          unit="months", dist=T(low=1.0, mode=2.0, high=3.0),
          rationale="Contract, data-protection agreement, file transfer and first contact cycle."),
        P(key="impl_cost_overrun", label_en="Implementation cost overrun factor", label_ar="معامل تجاوز تكلفة التنفيذ",
          unit="multiplier", dist=T(low=0.95, mode=1.10, high=1.40),
          rationale="Right-skewed: integration projects rarely come in under budget."),
    ]


def build_futures(controls: DecisionControls) -> list[CollectionsStrategy]:
    inv = min(controls.automation_investment, 3.0)
    S, L = CollectionsStrategy, CollectionsLevers
    return [
        S(key="A", name_en="Full Outsourcing to a Collection Agency", name_ar="التعهيد الكامل لشركة تحصيل",
          tagline_en="Place the whole overdue book with an agency and escalate fast",
          tagline_ar="تسليم كل المتأخرات لشركة تحصيل مع تصعيد سريع",
          measures_en=["Place 100% of overdue receivables (31+ days) with one agency",
                       "High-frequency contact and early legal escalation", "Contingency fee on every amount recovered",
                       "Key and government accounts included"],
          measures_ar=["تسليم 100% من المتأخرات (أكثر من 31 يوماً) لشركة تحصيل واحدة",
                       "تواصل مكثف وتصعيد قانوني مبكر", "عمولة على كل مبلغ يتم تحصيله", "يشمل كبار العملاء والجهات الحكومية"],
          levers=L(agency_placement=1.0, aggressive_tactics=1.0), proposed_by=["cfo", "strategy"]),
        S(key="B", name_en="Hybrid: Agency for Aged Debt + Digital Collections", name_ar="النموذج الهجين: شركة للديون القديمة وتحصيل رقمي",
          tagline_en="Agency only for debt over 90 days; in-house digital follow-up for the rest",
          tagline_ar="شركة التحصيل للديون الأقدم من 90 يوماً فقط، والباقي بالتحصيل الرقمي الداخلي",
          measures_en=["Place debt over 90 days (≈55% of the overdue book) with an agency",
                       "Key and government accounts stay in-house", "Fair-conduct contact rules in the agency contract",
                       f"EGP {inv:.1f}M digital collections (reminders, payment links, e-invoicing)"],
          measures_ar=["تسليم الديون الأقدم من 90 يوماً (حوالي 55% من المتأخرات) لشركة تحصيل",
                       "كبار العملاء والجهات الحكومية يبقون داخلياً", "قواعد تواصل عادلة في عقد الشركة",
                       f"تحصيل رقمي بقيمة {inv:.1f} مليون جنيه (تذكيرات وروابط دفع وفوترة إلكترونية)"],
          levers=L(agency_placement=0.55, digital_collections=inv), proposed_by=["coo", "cfo"]),
        S(key="C", name_en="In-house Collections Transformation", name_ar="تطوير التحصيل داخلياً",
          tagline_en="No agency: strengthen the team, digitise follow-up and reward early payment",
          tagline_ar="بدون شركة تحصيل: تقوية الفريق ورقمنة المتابعة وتحفيز السداد المبكر",
          measures_en=["Reassign 3 finance staff to collections (no hiring, no terminations)",
                       f"EGP {inv:.1f}M digital collections", "1.5% early-payment discount",
                       "Weekly ageing review with sales"],
          measures_ar=["نقل 3 موظفين من المالية إلى التحصيل (بدون تعيين أو إنهاء خدمة)",
                       f"تحصيل رقمي بقيمة {inv:.1f} مليون جنيه", "خصم 1.5% للسداد المبكر", "مراجعة أسبوعية للأعمار مع المبيعات"],
          levers=L(digital_collections=inv, early_payment_discount=1.0, team_reallocation=1.0),
          proposed_by=["coo", "hr", "strategy"]),
    ]


TRAJECTORY_METRICS = ["opex_monthly", "savings_run_rate", "revenue_monthly", "cash_flow_monthly", "cash_balance",
                      "delay_pct", "utilization_pct", "csat_pct", "risk_exposure", "capacity_shortfall_fte",
                      "collections_monthly", "overdue_balance", "dso_days"]
SUMMARY_METRICS = ["savings_pct_at_deadline", "run_rate_savings_at_deadline", "realized_savings_12m",
                   "implementation_cost_12m", "one_off_implementation_cost", "delivery_loss_12m", "net_benefit_12m",
                   "steady_state_net_run_rate", "max_delay_increase_pct", "min_csat_pct", "peak_utilization_pct",
                   "min_cash_balance", "projected_operating_profit_12m", "agency_fees_12m", "writeoff_avoided_12m",
                   "dso_days_at_deadline", "relationship_loss_pct"]


def _path(b: Baseline, c: DecisionControls, lv: CollectionsLevers, econ: CollectionsEconomics,
          th: dict[str, np.ndarray], horizon: int) -> dict[str, np.ndarray]:
    """Month-by-month receivables flow for one lever set. Arrays are (N, H)."""
    n = len(next(iter(th.values())))
    months = np.arange(1, horizon + 1, dtype=float)[None, :]
    D = float(c.implementation_months)
    compression = 1.0 + 0.25 * max(0.0, 6.0 / D - 1.0)
    col = lambda k: th[k][:, None]  # noqa: E731

    billing_full = b.annual_revenue / 12.0
    ramp_a = np.clip(months / np.maximum(1.0, col("agency_ramp_months") * D / 6.0), 0, 1)
    am = col("digital_adoption_months") * max(1.0, D / 6.0)
    adopt = 1.0 / (1.0 + np.exp(-(months - am / 2.0) / (am / 8.0))) * (1.0 if lv.digital_collections > 0 else 0.0)
    dig = min(1.0, lv.digital_collections / 3.0)  # EGP 3M = full programme
    realloc_ramp = np.clip(months / 2.0, 0, 1)

    ontime0 = b.ontime_collection_rate_pct / 100.0
    ontime = (ontime0 + col("ontime_uplift") * dig * adopt
              + col("discount_takeup") * (1 - ontime0) * lv.early_payment_discount * np.clip(months / 2.0, 0, 1))
    ontime = np.clip(ontime, 0, 0.99)
    r_in = b.inhouse_recovery_rate_pct / 100.0 * (1 + col("inhouse_recovery_uplift") * dig * adopt
                                                  + 0.25 * lv.team_reallocation * realloc_ramp)
    r_ag = col("agency_recovery_rate") * (1 + 0.25 * lv.aggressive_tactics) * ramp_a
    w = b.writeoff_rate_pct / 100.0

    # Relationship effects: contact intensity drives complaints, CSAT and key-account attrition.
    intensity = (0.45 * lv.agency_placement + 1.0 * lv.aggressive_tactics) * ramp_a + 0.12 * dig * adopt
    complaints = b.complaint_rate_pct + col("complaint_sensitivity") * intensity
    csat = np.clip(b.csat_pct - col("csat_complaint_sensitivity") * (complaints - b.complaint_rate_pct), 0, 100)
    key_share = b.key_account_overdue_share_pct / 100.0
    churn_annual = (b.annual_revenue * key_share * col("key_account_churn") * lv.aggressive_tactics * ramp_a
                    + b.annual_revenue * 0.002 * np.maximum(0.0, complaints - b.complaint_rate_pct - 1.0))
    lag = np.concatenate([np.zeros((n, 2)), churn_annual[:, :-2]], axis=1)  # customers leave ~2 months later
    billing = billing_full - lag / 12.0

    pool = np.full(n, b.overdue_receivables)
    coll, rec_ag, wo, pools = (np.zeros((n, horizon)) for _ in range(4))
    for t in range(horizon):
        placed = pool * lv.agency_placement
        rec_a = placed * r_ag[:, t]
        rec_i = (pool - placed) * r_in[:, t]
        write = (pool - rec_a - rec_i) * w * (1 - 0.3 * lv.agency_placement * ramp_a[:, t])
        new = billing[:, t] * (1 - ontime[:, t])
        coll[:, t] = billing[:, t] * ontime[:, t] + rec_a + rec_i
        rec_ag[:, t], wo[:, t] = rec_a, write
        pool = np.maximum(0.0, pool + new - rec_a - rec_i - write)
        pools[:, t] = pool

    fees = rec_ag * col("agency_fee_rate")
    discounts = billing * col("discount_takeup") * (1 - ontime0) * lv.early_payment_discount * DISCOUNT_RATE
    one_off = np.zeros((n, horizon))
    if lv.agency_placement > 0:
        one_off[:, 0] += econ.agency_onboarding_cost * lv.agency_placement * compression
    if lv.digital_collections > 0:
        sm = max(1, math.ceil(D / 3))
        one_off[:, :sm] += lv.digital_collections * compression / sm
    if lv.team_reallocation > 0:
        one_off[:, 0] += econ.reallocation_training_cost * lv.team_reallocation
    one_off *= col("impl_cost_overrun")
    running = np.full((n, horizon), lv.digital_collections * econ.digital_running_cost_rate / 12.0) * np.clip(months / 2, 0, 1)
    handling = econ.complaint_handling_cost / 12.0 * np.maximum(0.0, complaints - b.complaint_rate_pct)

    # Collections team workload: agency placement removes accounts, digital tools remove manual chasing,
    # reallocation adds capacity, early-payment offers add some admin.
    team = b.collections_team_fte + econ.reallocation_fte * lv.team_reallocation * realloc_ramp
    load = b.collections_team_fte * b.collections_team_utilization_pct / 100.0 * (
        1 - 0.35 * lv.agency_placement * ramp_a - 0.20 * dig * adopt + 0.10 * lv.early_payment_discount
        + 0.30 * lv.team_reallocation * realloc_ramp)
    util = np.clip(load / team * 100.0, 0, 100)
    shortfall = np.maximum(0.0, load - team * c.max_utilization_pct / 100.0)
    return {"collections": coll, "billing": billing, "billing_full": np.full((n, horizon), billing_full),
            "ontime": ontime, "fees": fees, "discounts": discounts, "one_off": one_off, "running": running,
            "handling": handling, "complaints": complaints, "csat": csat, "churn_annual": churn_annual,
            "writeoff": wo, "pool": pools, "util": util, "shortfall": shortfall}


def run_model(b: Baseline, c: DecisionControls, levers: CollectionsLevers, econ: CollectionsEconomics,
              theta: dict[str, np.ndarray], horizon: int = 12) -> dict[str, Any]:
    n = len(next(iter(theta.values())))
    s = _path(b, c, levers, econ, theta, horizon)
    base = _path(b, c, CollectionsLevers(), econ, theta, horizon)
    uplift = s["collections"] - base["collections"]
    lost = (s["billing_full"] - s["billing"]) * s["ontime"]
    costs = s["fees"] + s["discounts"] + s["one_off"] + s["running"] + s["handling"]
    opex_m = b.annual_opex / 12.0 + costs
    cash_flow = s["collections"] - opex_m
    cash = b.opening_cash + np.cumsum(cash_flow, axis=1)
    dso = (s["billing"] * TERMS_MONTHS + s["pool"]) / (s["billing"] / 30.0)
    base_coll0 = b.annual_revenue / 12.0 * b.ontime_collection_rate_pct / 100.0 + \
        b.overdue_receivables * b.inhouse_recovery_rate_pct / 100.0
    dso0 = (b.annual_revenue / 12.0 * TERMS_MONTHS + b.overdue_receivables) / (b.annual_revenue / 360.0)
    risk = s["churn_annual"] + 0.8 * levers.aggressive_tactics * levers.agency_placement  # + regulatory proxy

    def t0(arr: np.ndarray, v0: float) -> np.ndarray:
        return np.concatenate([np.full((n, 1), v0), arr], axis=1)

    traj = {
        "opex_monthly": t0(opex_m, b.annual_opex / 12.0),
        "savings_run_rate": t0(uplift * 12.0, 0.0),
        "revenue_monthly": t0(s["billing"], b.annual_revenue / 12.0),
        "cash_flow_monthly": t0(cash_flow, base_coll0 - b.annual_opex / 12.0),
        "cash_balance": t0(cash, b.opening_cash),
        "delay_pct": t0(s["complaints"], b.complaint_rate_pct),
        "utilization_pct": t0(s["util"], b.collections_team_utilization_pct),
        "csat_pct": t0(s["csat"], b.csat_pct),
        "risk_exposure": t0(risk, 0.0),
        "capacity_shortfall_fte": t0(s["shortfall"], 0.0),
        "collections_monthly": t0(s["collections"], base_coll0),
        "overdue_balance": t0(s["pool"], b.overdue_receivables),
        "dso_days": t0(dso, dso0),
    }
    d = min(int(c.implementation_months), horizon) - 1
    impl = costs[:, :12].sum(axis=1) - s["handling"][:, :12].sum(axis=1)
    loss = lost[:, :12].sum(axis=1) + s["handling"][:, :12].sum(axis=1)
    realized = uplift[:, :12].sum(axis=1) + lost[:, :12].sum(axis=1)
    summary = {
        "savings_pct_at_deadline": uplift[:, d] / base["collections"][:, d] * 100.0,
        "run_rate_savings_at_deadline": uplift[:, d] * 12.0,
        "realized_savings_12m": realized,
        "implementation_cost_12m": impl,
        "one_off_implementation_cost": s["one_off"].sum(axis=1),
        "delivery_loss_12m": loss,
        "net_benefit_12m": realized - impl - loss,
        "steady_state_net_run_rate": (uplift[:, -1] - s["fees"][:, -1] - s["discounts"][:, -1] - s["running"][:, -1]) * 12
                                     - s["churn_annual"][:, -1],
        "max_delay_increase_pct": (s["complaints"] - b.complaint_rate_pct).max(axis=1),
        "min_csat_pct": s["csat"].min(axis=1),
        "peak_utilization_pct": s["util"].max(axis=1),
        "min_cash_balance": np.minimum(cash.min(axis=1), b.opening_cash),
        "projected_operating_profit_12m": (s["billing"] - opex_m)[:, :12].sum(axis=1),
        "agency_fees_12m": s["fees"][:, :12].sum(axis=1),
        "writeoff_avoided_12m": (base["writeoff"] - s["writeoff"])[:, :12].sum(axis=1),
        "dso_days_at_deadline": dso[:, d],
        "relationship_loss_pct": s["churn_annual"].max(axis=1) / b.annual_revenue * 100.0,
    }
    return {"trajectory": traj, "summary": summary}


def _pct(a: np.ndarray, q: float) -> float:
    return float(np.percentile(a, q))


def _r(x: float, nd: int = 3) -> float:
    return round(float(x), nd)


ATTRITION_LIMIT_PCT = 1.0  # key-account revenue lost per year, % of revenue


def evaluate_constraints(b: Baseline, c: DecisionControls, levers: CollectionsLevers,
                         s: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    req = c.required_probability

    def chk(code, name_en, name_ar, ok, metric, threshold, direction, hard, det=None):  # noqa: ANN001
        prob = (1.0 if det else 0.0) if det is not None else float(np.mean(ok))
        q_val = None
        if metric in s:
            q_val = _r(_pct(s[metric], (1 - req) * 100 if direction == ">=" else req * 100))
        return {"code": code, "name_en": name_en, "name_ar": name_ar, "metric": metric, "threshold": threshold,
                "direction": direction, "probability_satisfied": _r(prob), "required_probability": req,
                "value_at_tolerance": q_val, "status": "pass" if prob >= req else "fail", "hard": hard}

    t, D = c.cost_reduction_target_pct, c.implementation_months
    return [
        chk("C1", f"Collect {t:.0f}% more cash per month by month {D}", f"زيادة المتحصلات الشهرية {t:.0f}% بحلول الشهر {D}",
            s["savings_pct_at_deadline"] >= t, "savings_pct_at_deadline", t, ">=", False),
        chk("C2", "No employee terminations", "عدم إنهاء خدمة أي موظف", None, "workforce_termination", 0.0, "<=", True,
            det=(levers.workforce_termination == 0 or not c.no_terminations)),
        chk("C3", f"Complaint rate increase ≤ {c.acceptable_delay_increase_pct:.1f} pts",
            f"زيادة معدل الشكاوى ≤ {c.acceptable_delay_increase_pct:.1f} نقطة",
            s["max_delay_increase_pct"] <= c.acceptable_delay_increase_pct + 1e-9, "max_delay_increase_pct",
            c.acceptable_delay_increase_pct, "<=", True),
        chk("C4", f"Customer satisfaction ≥ {c.min_csat_pct:.0f}%", f"رضا العملاء ≥ {c.min_csat_pct:.0f}%",
            s["min_csat_pct"] >= c.min_csat_pct - 1e-9, "min_csat_pct", c.min_csat_pct, ">=", True),
        chk("C5", f"Key-account attrition ≤ {ATTRITION_LIMIT_PCT:.0f}% of revenue",
            f"فقد كبار العملاء ≤ {ATTRITION_LIMIT_PCT:.0f}% من الإيرادات",
            s["relationship_loss_pct"] <= ATTRITION_LIMIT_PCT + 1e-9, "relationship_loss_pct", ATTRITION_LIMIT_PCT, "<=", True),
        chk("C6", f"One-off implementation cost ≤ EGP {c.implementation_budget:.1f}M",
            f"تكلفة التنفيذ ≤ {c.implementation_budget:.1f} مليون جنيه",
            s["one_off_implementation_cost"] <= c.implementation_budget + 1e-9, "one_off_implementation_cost",
            c.implementation_budget, "<=", False),
    ]


def _segments(b: Baseline, levers: CollectionsLevers, exp_theta: dict[str, np.ndarray], c: DecisionControls) -> dict:
    """Debtor-segment view (shown where the cost model shows its project portfolio): months to clear each
    segment's overdue balance today vs under the strategy, and which client relationships are at risk."""
    segs = [  # id, share of overdue, relative payment speed, key/government relationship
        ("GOV", "Government entities", "جهات حكومية", 0.25, 0.6, True),
        ("KEY", "Key corporate accounts", "كبار العملاء من الشركات", 0.20, 0.9, True),
        ("SME", "SME accounts", "الشركات الصغيرة والمتوسطة", 0.30, 1.0, False),
        ("RET", "Retail and individual", "الأفراد", 0.10, 1.2, False),
        ("DSP", "Disputed invoices", "فواتير متنازع عليها", 0.10, 0.4, False),
        ("OLD", "Over 365 days", "أقدم من 365 يوماً", 0.05, 0.3, False),
    ]
    r_in = b.inhouse_recovery_rate_pct / 100.0
    r_ag = float(exp_theta["agency_recovery_rate"][0]) * (1 + 0.25 * levers.aggressive_tactics)
    dig = min(1.0, levers.digital_collections / 3.0)
    up = float(exp_theta["inhouse_recovery_uplift"][0]) * dig + 0.25 * levers.team_reallocation
    rows = []
    for sid, en, ar, share, speed, key in segs:
        placed = levers.agency_placement if not (key and levers.agency_placement < 1) else 0.0
        if sid in ("OLD", "DSP") and levers.agency_placement > 0:
            placed = 1.0
        rate_base = r_in * speed
        rate = (1 - placed) * r_in * speed * (1 + up) + placed * r_ag * speed
        base_m, scen_m = 1.0 / rate_base, 1.0 / max(rate, 1e-6)
        at_risk = bool(key and placed > 0 and levers.aggressive_tactics > 0)
        rows.append({"project_id": sid, "name_en": en, "name_ar": ar, "planned_months": round(base_m, 2),
                     "baseline_months": round(base_m, 2), "scenario_months": round(scen_m, 2),
                     "additional_delay_pct": round((scen_m - base_m) / base_m * 100, 2),
                     "contract_value_share": share, "at_risk": at_risk})
    risky = [r for r in rows if r["at_risk"]]
    return {"method": "Debtor-segment recovery model (expected case)", "capacity_reduction_fte": 0.0,
            "baseline_capacity_fte": float(b.collections_team_fte), "scenario_capacity_fte": float(b.collections_team_fte),
            "at_risk_threshold_pct": 0.0, "projects_at_risk": len(risky),
            "revenue_share_at_risk": round(sum(r["contract_value_share"] for r in risky), 4), "projects": rows,
            "kind": "debtor_segments"}


def sensitivity(b: Baseline, c: DecisionControls, levers: CollectionsLevers, econ: CollectionsEconomics,
                params: list[UncertainParameter], horizon: int) -> list[dict[str, Any]]:
    base_t = {p.key: np.array([p.dist.mode]) for p in params}
    base = run_model(b, c, levers, econ, base_t, horizon)["summary"]
    rows = []
    for p in params:
        vals = {}
        for side, v in (("low", p.dist.low), ("high", p.dist.high)):
            th = dict(base_t)
            th[p.key] = np.array([v])
            vals[side] = run_model(b, c, levers, econ, th, horizon)["summary"]
        lo, hi = float(vals["low"]["net_benefit_12m"][0]), float(vals["high"]["net_benefit_12m"][0])
        rows.append({"parameter": p.key, "label_en": p.label_en, "label_ar": p.label_ar, "low_value": p.dist.low,
                     "high_value": p.dist.high, "net_benefit_at_low": _r(lo), "net_benefit_at_high": _r(hi),
                     "savings_pct_at_low": _r(vals["low"]["savings_pct_at_deadline"][0]),
                     "savings_pct_at_high": _r(vals["high"]["savings_pct_at_deadline"][0]),
                     "delay_at_low": _r(vals["low"]["max_delay_increase_pct"][0]),
                     "delay_at_high": _r(vals["high"]["max_delay_increase_pct"][0]), "swing": _r(abs(hi - lo))})
    rows.sort(key=lambda r: r["swing"], reverse=True)
    return [{**r, "base_net_benefit": _r(base["net_benefit_12m"][0])} for r in rows]


def simulate_strategy(b: Baseline, c: DecisionControls, cfg: SimulationConfig, params: list[UncertainParameter],
                      econ: CollectionsEconomics, strategy: CollectionsStrategy | None, theta: dict[str, np.ndarray],
                      include_sensitivity: bool = True, include_des: bool = True) -> dict[str, Any]:
    levers = strategy.levers if strategy else CollectionsLevers()
    mc = run_model(b, c, levers, econ, theta, cfg.horizon_months)
    mode = {p.key: np.array([p.dist.mode]) for p in params}
    exp = run_model(b, c, levers, econ, mode, cfg.horizon_months)
    s = mc["summary"]
    summary = {m: {"expected": _r(exp["summary"][m][0]), "mean": _r(np.mean(s[m])), "p10": _r(_pct(s[m], 10)),
                   "p50": _r(_pct(s[m], 50)), "p90": _r(_pct(s[m], 90))} for m in SUMMARY_METRICS}
    req = c.required_probability
    cons = evaluate_constraints(b, c, levers, s)
    nb = s["net_benefit_12m"]
    counts, edges = np.histogram(nb, bins=24)
    order = np.argsort(nb)
    n = len(nb)
    scen = lambda i: {m: _r(s[m][i]) for m in SUMMARY_METRICS}  # noqa: E731
    traj = {m: {"expected": [_r(v) for v in exp["trajectory"][m][0]],
                "p10": [_r(v) for v in np.percentile(mc["trajectory"][m], 10, axis=0)],
                "p50": [_r(v) for v in np.percentile(mc["trajectory"][m], 50, axis=0)],
                "p90": [_r(v) for v in np.percentile(mc["trajectory"][m], 90, axis=0)]} for m in TRAJECTORY_METRICS}
    out: dict[str, Any] = {
        "strategy_key": strategy.key if strategy else "BASELINE",
        "levers": levers.model_dump(),
        "summary": summary,
        "probabilities": {
            "meet_target": _r(np.mean(s["savings_pct_at_deadline"] >= c.cost_reduction_target_pct)),
            "delay_within_acceptable": _r(np.mean(s["max_delay_increase_pct"] <= c.acceptable_delay_increase_pct + 1e-9)),
            "csat_maintained": _r(np.mean(s["min_csat_pct"] >= c.min_csat_pct - 1e-9)),
            "positive_net_benefit_12m": _r(np.mean(nb > 0)),
            "contractual_breach": _r(np.mean(s["relationship_loss_pct"] > ATTRITION_LIMIT_PCT + 1e-9)),
        },
        "achievable_reduction_pct_at_tolerance": _r(_pct(s["savings_pct_at_deadline"], (1 - req) * 100), 2),
        "constraints": cons,
        "constraints_violated": [x["code"] for x in cons if x["status"] == "fail"],
        "hard_constraints_violated": [x["code"] for x in cons if x["status"] == "fail" and x["hard"]],
        "cases": {"worst": scen(order[int(0.10 * (n - 1))]), "base": scen(order[int(0.50 * (n - 1))]),
                  "best": scen(order[int(0.90 * (n - 1))])},
        "net_benefit_histogram": {"counts": counts.tolist(), "edges": [_r(e) for e in edges]},
        "trajectory": traj,
    }
    if include_sensitivity:
        out["sensitivity"] = sensitivity(b, c, levers, econ, params, cfg.horizon_months)
    if include_des:
        out["project_portfolio"] = _segments(b, levers, mode, c)
    return out


def run_full_simulation(baseline: Baseline, controls: DecisionControls, config: SimulationConfig,
                        params: list[UncertainParameter] | None = None, economics: CollectionsEconomics | None = None,
                        include_sensitivity: bool = True, include_des: bool = True) -> dict[str, Any]:
    from .engine import _canonical_hash, sample_parameters

    t0 = time.perf_counter()
    params = params or default_parameters()
    econ = economics or CollectionsEconomics()
    theta = sample_parameters(params, config.iterations, config.seed)
    res: dict[str, Any] = {
        "baseline": simulate_strategy(baseline, controls, config, params, econ, None, theta, False, include_des),
        "futures": {},
    }
    for f in build_futures(controls):
        r = simulate_strategy(baseline, controls, config, params, econ, f, theta, include_sensitivity, include_des)
        r["definition"] = f.model_dump()
        res["futures"][f.key] = r
    res["meta"] = {
        "model_id": MODEL_ID, "model_version": MODEL_VERSION, "domain": "collections",
        "input_fingerprint": _canonical_hash({"model": MODEL_ID, "version": MODEL_VERSION,
                                              "baseline": baseline.model_dump(), "controls": controls.model_dump(),
                                              "config": config.model_dump(), "params": [p.model_dump() for p in params],
                                              "economics": econ.model_dump()}),
        "seed": config.seed, "iterations": config.iterations, "horizon_months": config.horizon_months,
        "controls": controls.model_dump(), "confidence_percentile": controls.confidence_percentile,
        "required_probability": controls.required_probability, "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "method": "Vectorised monthly receivables-flow model (on-time collection, overdue pool, agency and in-house "
                  "recovery, write-offs, relationship effects); Monte Carlo over triangular priors with common random "
                  "numbers; one-at-a-time sensitivity; debtor-segment recovery view.",
        "nature": "quantitative_simulation",
    }
    return res
