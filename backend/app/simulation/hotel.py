"""State-owned hotel asset utilisation model (decision domain "hotel").

Answers questions such as "how do we get the most out of the 148-room hotel the Authority owns downtown,
through different proposals?". Same contract as the cost model in engine.py - a vectorised monthly model
run deterministically (expected case), as a Monte Carlo over triangular priors, and one-at-a-time for
sensitivity - and the same result shape, so every screen, agent and report reads it the same way. The
summary keys keep their generic names; in this domain they mean:

  savings_pct_at_deadline       the owner's annualised net return at the deadline, % of the asset value (yield)
  run_rate_savings_at_deadline  improvement of the owner's annual net return vs today (EGP M / year)
  realized_savings_12m          operating improvement over 12 months before disruption losses
  implementation_cost_12m       capital works, fit-out, tender/onboarding, management fees, running costs
  delivery_loss_12m             contribution lost while rooms are out of service, plus idle surplus staff
  max_delay_increase_pct        peak share of rooms out of service (%)
  peak_utilization_pct          peak utilisation of the hotel workforce
  min_csat_pct                  lowest guest review score (%)

Every number is SYNTHETIC demonstration data or a documented modelling assumption.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from .assumptions import Baseline, DecisionControls, SimulationConfig, Triangular, UncertainParameter

MODEL_ID = "hotel-asset-utilisation"
MODEL_VERSION = "1.0.0"

DAYS = 30.4
APT_ROOMS = 40          # rooms merged into serviced apartments (2 rooms per apartment)
APT_UNITS = 20
REDEPLOY_CAPACITY_FTE = 25.0  # surplus hotel staff the Authority can absorb in other departments
STABLE_MONTH = 36       # month used for the stabilised view


class HotelLevers(BaseModel):
    """Intensity of each lever in a proposal (0..1 unless stated)."""

    lease_to_operator: float = Field(0.0, ge=0, le=1, description="Long-term lease (usufruct) of the whole hotel to a private operator")
    brand_management: float = Field(0.0, ge=0, le=1, description="Management contract with a hotel brand; the Authority keeps the revenue")
    renovation_capex: float = Field(0.0, ge=0, le=100, description="EGP M invested in renovating the rooms and public areas")
    serviced_apartments: float = Field(0.0, ge=0, le=1, description="Convert 40 rooms into 20 serviced apartments for Free Zone investors")
    business_center: float = Field(0.0, ge=0, le=1, description="Ground floor: investor business centre, meeting rooms and retail units")
    digital_distribution: float = Field(0.0, ge=0, le=1, description="Online booking channels and corporate contracts with Free Zone companies")
    workforce_termination: float = Field(0.0, ge=0, le=1, description="Present so governance can test and block it")


class HotelEconomics(BaseModel):
    staff_cost_per_fte: float = 0.18      # EGP M per employee a year
    variable_cost_rate: float = 0.32      # of rooms + F&B revenue
    other_revenue_share: float = 0.30     # F&B, halls, laundry as a share of rooms revenue
    apartment_rent_month: float = 0.065   # EGP M per apartment per month
    apartment_variable_rate: float = 0.15
    retail_rent_year: float = 3.6         # EGP M a year for the ground-floor retail units
    bc_variable_rate: float = 0.25
    apartment_conversion_cost: float = 10.0  # EGP M for all 40 rooms
    business_center_fitout: float = 6.0   # EGP M
    brand_onboarding_cost: float = 3.0    # pre-opening, systems, brand standards
    lease_tender_cost: float = 0.8        # tender, valuation, legal
    distribution_setup_cost: float = 0.6  # channel manager, website, corporate sales
    mgmt_fee_revenue: float = 0.03
    mgmt_fee_gop: float = 0.08
    lease_revenue_share: float = 0.08     # of the operator's revenue above the threshold
    lease_share_threshold_month: float = 5.0
    lease_grace_months: float = 6.0       # rent-free while the operator refurbishes
    owner_residual_cost_year: float = 1.0  # insurance and structure, kept by the owner under a lease
    full_renovation_capex: float = 75.0   # capex that buys the full ADR uplift


class HotelProposal(BaseModel):
    key: str
    name_en: str
    name_ar: str
    tagline_en: str
    tagline_ar: str
    measures_en: list[str]
    measures_ar: list[str]
    levers: HotelLevers
    proposed_by: list[str]


def default_parameters() -> list[UncertainParameter]:
    P, T = UncertainParameter, Triangular
    return [
        P(key="lease_rent", label_en="Tendered annual rent", label_ar="الإيجار السنوي في المناقصة", unit="EGP M / year",
          dist=T(low=13.0, mode=17.0, high=22.0),
          rationale="Fixed rent a private operator would bid for a 148-room downtown hotel in its current state."),
        P(key="operator_retention", label_en="Staff the operator takes over", label_ar="نسبة العاملين التي ينقلها المشغل",
          unit="share of hotel staff", dist=T(low=0.45, mode=0.60, high=0.75),
          rationale="Private operators run leaner teams; the rest stays on the Authority's payroll."),
        P(key="brand_occupancy_gain", label_en="Occupancy gain from a hotel brand", label_ar="زيادة الإشغال بعلامة فندقية",
          unit="occupancy points at stabilisation", dist=T(low=16.0, mode=24.0, high=32.0),
          rationale="Brand distribution and loyalty programmes; no local benchmark for a branded hotel in downtown Port Said."),
        P(key="adr_uplift", label_en="Room-rate uplift after full renovation", label_ar="زيادة سعر الغرفة بعد التجديد الكامل",
          unit="share of today's average rate", dist=T(low=0.25, mode=0.40, high=0.55),
          rationale="Renovated rooms command higher rates; scaled down for a partial refresh."),
        P(key="corporate_occupancy_gain", label_en="Occupancy gain from online and corporate sales",
          label_ar="زيادة الإشغال بالحجز الإلكتروني وعقود الشركات", unit="occupancy points at stabilisation",
          dist=T(low=12.0, mode=20.0, high=26.0),
          rationale="Online channels plus corporate rates for Free Zone companies and their visitors."),
        P(key="apartment_occupancy", label_en="Serviced-apartment occupancy", label_ar="إشغال الشقق الفندقية",
          unit="share of units let", dist=T(low=0.65, mode=0.85, high=0.95),
          rationale="Long-stay demand from Free Zone investors and expatriate staff; no waiting list exists yet."),
        P(key="business_center_revenue", label_en="Business-centre revenue", label_ar="إيرادات مركز الأعمال",
          unit="EGP M / year", dist=T(low=2.0, mode=4.0, high=5.5),
          rationale="Meeting rooms, co-working and investor services; depends on Free Zone footfall."),
        P(key="ramp_months", label_en="Time to stabilised trading", label_ar="مدة الوصول إلى التشغيل المستقر",
          unit="months after works", dist=T(low=8.0, mode=12.0, high=18.0),
          rationale="Months for occupancy to reach its new level once rooms are back in service."),
        P(key="works_delay", label_en="Works duration factor", label_ar="معامل مدة الأعمال", unit="multiplier",
          dist=T(low=0.9, mode=1.1, high=1.5),
          rationale="Right-skewed: renovation of an old building rarely finishes early."),
        P(key="capex_overrun", label_en="Capital cost overrun factor", label_ar="معامل تجاوز التكلفة الاستثمارية",
          unit="multiplier", dist=T(low=0.95, mode=1.15, high=1.50),
          rationale="Old structures reveal hidden works (electrical, plumbing, fire code)."),
        P(key="guest_disruption", label_en="Guest-score drop during works", label_ar="انخفاض تقييم النزلاء أثناء الأعمال",
          unit="score points", dist=T(low=1.0, mode=3.0, high=6.0),
          rationale="Noise and closed areas lower reviews while guests stay during the works."),
    ]


def build_futures(controls: DecisionControls) -> list[HotelProposal]:
    S, L = HotelProposal, HotelLevers
    return [
        S(key="A", name_en="Long-term Lease to a Private Operator", name_ar="التأجير طويل الأجل لمشغل خاص",
          tagline_en="15-year usufruct through a public tender: fixed rent plus a revenue share, no investment by the Authority",
          tagline_ar="حق انتفاع 15 عاماً عبر مناقصة عامة: إيجار ثابت ونسبة من الإيراد، دون استثمار من الجهاز",
          measures_en=["Public tender for a 15-year usufruct of the whole hotel",
                       "Fixed annual rent plus 8% of revenue above a threshold",
                       "The operator refurbishes at its own cost (hotel closed about 6 months, rent-free)",
                       "The operator takes over part of the staff; the rest stay with the Authority"],
          measures_ar=["مناقصة عامة لحق انتفاع الفندق بالكامل لمدة 15 عاماً", "إيجار سنوي ثابت مع 8% من الإيراد فوق حد معين",
                       "المشغل يجدد على نفقته (إغلاق الفندق نحو 6 أشهر دون إيجار)",
                       "المشغل ينقل جزءاً من العاملين ويبقى الباقون على قوة الجهاز"],
          levers=L(lease_to_operator=1.0), proposed_by=["cfo", "strategy"]),
        S(key="B", name_en="Full Renovation + Hotel Brand Management", name_ar="التجديد الشامل مع إدارة علامة فندقية",
          tagline_en="The Authority funds a full renovation and keeps the revenue; a hotel brand manages it for a fee",
          tagline_ar="الجهاز يموّل تجديداً شاملاً ويحتفظ بالإيراد، وتديره علامة فندقية مقابل أتعاب",
          measures_en=["Full renovation of rooms and public areas (EGP 75M), two floors at a time",
                       "Management contract: 3% of revenue + 8% of gross operating profit",
                       "All current staff kept and retrained to brand standards",
                       "Brand booking system and loyalty programme"],
          measures_ar=["تجديد شامل للغرف والمناطق العامة (75 مليون جنيه) بواقع طابقين في كل مرحلة",
                       "عقد إدارة: 3% من الإيراد + 8% من إجمالي الربح التشغيلي",
                       "الإبقاء على جميع العاملين وتدريبهم على معايير العلامة", "نظام حجز العلامة وبرنامج الولاء"],
          levers=L(brand_management=1.0, renovation_capex=75.0, digital_distribution=0.5), proposed_by=["coo", "cfo"]),
        S(key="C", name_en="Mixed-use Repositioning for the Free Zone", name_ar="إعادة التوظيف متعدد الاستخدامات لخدمة المنطقة الحرة",
          tagline_en="Serviced apartments for investors, an investor business centre and a refreshed 108-room hotel",
          tagline_ar="شقق فندقية للمستثمرين ومركز أعمال للمستثمرين وفندق مجدد من 108 غرف",
          measures_en=["Convert 40 rooms into 20 serviced apartments let to Free Zone companies",
                       "Ground floor: investor business centre, meeting rooms and retail units",
                       "Refresh the remaining 108 rooms (EGP 12M) and sell them online and on corporate contracts",
                       "All staff kept; part retrained for the apartments and the business centre"],
          measures_ar=["تحويل 40 غرفة إلى 20 شقة فندقية تؤجر لشركات المنطقة الحرة",
                       "الدور الأرضي: مركز أعمال للمستثمرين وقاعات اجتماعات ووحدات تجارية",
                       "تحديث الغرف الـ108 الباقية (12 مليون جنيه) وتسويقها إلكترونياً وبعقود الشركات",
                       "الإبقاء على جميع العاملين وتأهيل جزء منهم للشقق ومركز الأعمال"],
          levers=L(renovation_capex=12.0, serviced_apartments=1.0, business_center=1.0, digital_distribution=1.0),
          proposed_by=["coo", "hr", "strategy"]),
    ]


TRAJECTORY_METRICS = ["opex_monthly", "savings_run_rate", "revenue_monthly", "cash_flow_monthly", "cash_balance",
                      "delay_pct", "utilization_pct", "csat_pct", "risk_exposure", "capacity_shortfall_fte",
                      "occupancy_pct", "owner_net_return", "adr_egp"]
SUMMARY_METRICS = ["savings_pct_at_deadline", "run_rate_savings_at_deadline", "realized_savings_12m",
                   "implementation_cost_12m", "one_off_implementation_cost", "delivery_loss_12m", "net_benefit_12m",
                   "steady_state_net_run_rate", "max_delay_increase_pct", "min_csat_pct", "peak_utilization_pct",
                   "min_cash_balance", "projected_operating_profit_12m", "owner_net_return_at_deadline",
                   "stabilised_yield_pct", "occupancy_at_deadline_pct", "staff_surplus_fte", "management_fees_12m",
                   "payback_years"]


def _s_curve(months: np.ndarray, start: np.ndarray, length: np.ndarray) -> np.ndarray:
    """0 before start, rising to 1 about `length` months after it."""
    x = (months - start - length / 2.0) / np.maximum(length / 8.0, 0.5)
    return np.where(months <= start, 0.0, 1.0 / (1.0 + np.exp(-x)))


def _path(b: Baseline, c: DecisionControls, lv: HotelLevers, econ: HotelEconomics,
          th: dict[str, np.ndarray], horizon: int) -> dict[str, np.ndarray]:
    """Month-by-month owner economics for one lever set. Arrays are (N, H)."""
    n = len(next(iter(th.values())))
    months = np.arange(1, horizon + 1, dtype=float)[None, :]
    col = lambda k: th[k][:, None]  # noqa: E731
    D = float(c.implementation_months)
    compression = 1.0 + 0.15 * max(0.0, 12.0 / D - 1.0)  # rushing works costs more
    delay = col("works_delay")
    rooms = float(b.hotel_rooms)
    occ0, adr0 = b.hotel_occupancy_pct / 100.0, b.hotel_adr_egp / 1e6
    lease = lv.lease_to_operator > 0
    reno = min(1.0, lv.renovation_capex / econ.full_renovation_capex)

    # ---- works schedule and rooms out of service
    apt_months = 5.0 * delay * lv.serviced_apartments
    reno_months = (3.0 + 6.0 * reno) * delay if lv.renovation_capex > 0 else 0.0 * delay
    reno_start = apt_months  # the refresh follows the conversion
    reno_share = (0.12 + 0.16 * reno) * (1.0 if lv.renovation_capex > 0 else 0.0)
    out = np.zeros((n, horizon))
    out = np.where(months <= apt_months, APT_ROOMS / rooms * lv.serviced_apartments, out)
    in_reno = (months > reno_start) & (months <= reno_start + reno_months)
    out = np.where(in_reno, np.maximum(out, reno_share), out)
    closure = 6.0 * delay * lv.lease_to_operator
    if lease:
        out = np.where(months <= closure, 1.0, 0.0)
    works_end = np.maximum(apt_months, reno_start + reno_months)

    hotel_rooms = rooms - APT_ROOMS * lv.serviced_apartments
    avail = hotel_rooms * (1.0 - np.minimum(1.0, out * rooms / max(hotel_rooms, 1.0))) if not lease else hotel_rooms * (1 - out)
    avail = np.clip(avail, 0, hotel_rooms)

    # ---- demand: occupancy and rate
    ramp = col("ramp_months")
    dig_start = np.zeros((n, 1)) + 1.0
    occ_gain = (col("brand_occupancy_gain") * lv.brand_management * _s_curve(months, works_end * 0.6, ramp)
                + col("corporate_occupancy_gain") * lv.digital_distribution * (1 - 0.5 * lv.brand_management)
                * _s_curve(months, dig_start, ramp * 0.75)) / 100.0
    occ = np.clip(occ0 + occ_gain, 0, 0.9)
    renovated = np.clip((months - reno_start) / np.maximum(reno_months, 1e-6), 0, 1) if lv.renovation_capex > 0 else 0.0 * months
    adr = adr0 * (1 + col("adr_uplift") * reno * renovated + 0.05 * lv.brand_management * renovated)

    rooms_rev_full = hotel_rooms * DAYS * occ * adr
    rooms_rev = avail * DAYS * occ * adr
    other_share = econ.other_revenue_share + 0.05 * lv.brand_management
    hotel_rev, hotel_rev_full = rooms_rev * (1 + other_share), rooms_rev_full * (1 + other_share)
    apt_live = np.clip((months - apt_months) / 2.0, 0, 1) * lv.serviced_apartments
    apt_rev = APT_UNITS * col("apartment_occupancy") * econ.apartment_rent_month * apt_live
    bc_live = np.clip((months - 3.0 * delay) / 3.0, 0, 1) * lv.business_center
    bc_rev = (col("business_center_revenue") + econ.retail_rent_year) / 12.0 * bc_live

    staff0 = float(b.hotel_staff_fte)
    staff_cost = staff0 * econ.staff_cost_per_fte / 12.0
    fixed = b.hotel_fixed_opex / 12.0
    if lease:
        # The operator trades the hotel; the owner gets rent (after a rent-free refurbishment) and a revenue share,
        # and keeps paying the staff the operator does not take until they are redeployed.
        op_occ = np.clip(occ0 + 0.18 * _s_curve(months, closure, ramp), 0, 0.9)
        op_rev = hotel_rooms * DAYS * op_occ * adr0 * 1.3 * (1 + econ.other_revenue_share) * (months > closure)
        rent_on = months > np.maximum(closure, econ.lease_grace_months)
        owner_rev = (col("lease_rent") / 12.0 * rent_on
                     + econ.lease_revenue_share * np.maximum(0.0, op_rev - econ.lease_share_threshold_month))
        surplus = staff0 * (1 - col("operator_retention")) * np.ones_like(months)
        absorbed = np.minimum(surplus, REDEPLOY_CAPACITY_FTE * np.clip(months / 6.0, 0, 1))
        idle = surplus - absorbed
        owner_cost = idle * econ.staff_cost_per_fte / 12.0 + econ.owner_residual_cost_year / 12.0
        variable = np.zeros((n, horizon))
        fees = np.zeros((n, horizon))
        owner_rev_full = owner_rev
        on_payroll = staff0 * col("operator_retention") * np.ones_like(months)
        load = (0.45 * on_payroll + 0.35 * on_payroll * op_occ / max(occ0, 0.05)) * (months > closure)
        lost_contrib = np.zeros((n, horizon))
    else:
        owner_rev = hotel_rev + apt_rev + bc_rev
        owner_rev_full = hotel_rev_full + apt_rev + bc_rev
        variable = econ.variable_cost_rate * hotel_rev + econ.apartment_variable_rate * apt_rev + econ.bc_variable_rate * bc_rev
        gop = owner_rev - variable - staff_cost - fixed
        fees = lv.brand_management * (econ.mgmt_fee_revenue * owner_rev + econ.mgmt_fee_gop * np.maximum(gop, 0.0))
        owner_cost = staff_cost + fixed + variable
        surplus = np.zeros((n, horizon))
        idle = surplus
        on_payroll = staff0 * np.ones_like(months)
        # Workload: a fixed core plus a part that follows occupied rooms, apartments and the business centre.
        occupied = avail * occ / max(rooms * occ0, 1.0)
        load = staff0 * b.hotel_staff_utilization_pct / 100.0 * (0.55 + 0.45 * occupied) \
            + 6.0 * apt_live + 5.0 * bc_live - 4.0 * lv.brand_management * renovated
        lost_contrib = (hotel_rev_full - hotel_rev) * (1 - econ.variable_cost_rate)

    one_off = np.zeros((n, horizon))
    if lv.renovation_capex > 0:
        span = np.maximum(1, np.ceil(reno_months))
        one_off += np.where(in_reno, lv.renovation_capex / span, 0.0) * compression
    if lv.serviced_apartments > 0:
        one_off += np.where(months <= apt_months, econ.apartment_conversion_cost * lv.serviced_apartments
                            / np.maximum(1, np.ceil(apt_months)), 0.0) * compression
    if lv.business_center > 0:
        one_off[:, :3] += econ.business_center_fitout * lv.business_center / 3.0
    if lv.brand_management > 0:
        one_off[:, 0] += econ.brand_onboarding_cost * lv.brand_management
    if lv.digital_distribution > 0:
        one_off[:, 0] += econ.distribution_setup_cost * lv.digital_distribution
    if lease:
        one_off[:, 0] += econ.lease_tender_cost
    one_off *= col("capex_overrun")
    running = np.full((n, horizon), 0.04 * lv.digital_distribution)  # channel commissions above today's

    guest = (b.hotel_guest_score_pct - col("guest_disruption") * (out > 0) * (out < 1)
             + 6.0 * reno * renovated + 3.0 * lv.brand_management * renovated + 2.0 * lv.digital_distribution
             * np.clip(months / 6, 0, 1))
    guest = np.clip(guest, 0, 100)
    util = np.where(on_payroll > 0, np.clip(load / np.maximum(on_payroll, 1e-6) * 100.0, 0, 100), 0.0)
    shortfall = np.maximum(0.0, load - on_payroll * c.max_utilization_pct / 100.0)
    return {"owner_rev": owner_rev, "owner_rev_full": owner_rev_full, "owner_cost": owner_cost, "fees": fees,
            "one_off": one_off, "running": running, "out": out, "occ": occ if not lease else op_occ, "adr": adr,
            "guest": guest, "util": util, "shortfall": shortfall, "surplus": surplus, "idle": idle,
            "lost_contrib": lost_contrib, "variable": variable}


def _owner_net(s: dict[str, np.ndarray]) -> np.ndarray:
    """Owner's monthly net operating result (before one-off capital spend)."""
    return s["owner_rev"] - s["owner_cost"] - s["fees"] - s["running"]


def run_model(b: Baseline, c: DecisionControls, levers: HotelLevers, econ: HotelEconomics,
              theta: dict[str, np.ndarray], horizon: int = 12) -> dict[str, Any]:
    n = len(next(iter(theta.values())))
    long = max(horizon, STABLE_MONTH)
    s_long = _path(b, c, levers, econ, theta, long)
    base_long = _path(b, c, HotelLevers(), econ, theta, long)
    s = {k: v[:, :horizon] for k, v in s_long.items()}
    base = {k: v[:, :horizon] for k, v in base_long.items()}
    net, net0 = _owner_net(s), _owner_net(base)
    uplift = net - net0
    asset = b.hotel_asset_value
    opex_m = s["owner_cost"] + s["fees"] + s["running"]
    cash_flow = net - s["one_off"]
    cash = b.hotel_capex_reserve + np.cumsum(cash_flow, axis=1)
    idle_cost = s["idle"] * econ.staff_cost_per_fte / 12.0
    exposure = idle_cost * 12.0 + s["lost_contrib"] * 12.0 + 0.02 * levers.lease_to_operator * asset

    def t0(arr: np.ndarray, v0: float) -> np.ndarray:
        return np.concatenate([np.full((n, 1), v0), arr], axis=1)

    net_today = float(_owner_net({k: v[:1, :1] for k, v in base.items()})[0, 0])
    rev_today = float(base["owner_rev"][0, 0])
    traj = {
        "opex_monthly": t0(opex_m, float((base["owner_cost"] + base["fees"])[0, 0])),
        "savings_run_rate": t0(uplift * 12.0, 0.0),
        "revenue_monthly": t0(s["owner_rev"], rev_today),
        "cash_flow_monthly": t0(cash_flow, net_today),
        "cash_balance": t0(cash, b.hotel_capex_reserve),
        "delay_pct": t0(s["out"] * 100.0, 0.0),
        "utilization_pct": t0(s["util"], b.hotel_staff_utilization_pct),
        "csat_pct": t0(s["guest"], b.hotel_guest_score_pct),
        "risk_exposure": t0(exposure, 0.0),
        "capacity_shortfall_fte": t0(s["shortfall"], 0.0),
        "occupancy_pct": t0(s["occ"] * 100.0, b.hotel_occupancy_pct),
        "owner_net_return": t0(net * 12.0, net_today * 12.0),
        "adr_egp": t0(s["adr"] * 1e6, b.hotel_adr_egp),
    }
    d = min(int(c.implementation_months), horizon) - 1
    loss = s["lost_contrib"][:, :12].sum(axis=1) + idle_cost[:, :12].sum(axis=1)
    impl = (s["one_off"] + s["fees"] + s["running"])[:, :12].sum(axis=1)
    realized = uplift[:, :12].sum(axis=1) + s["fees"][:, :12].sum(axis=1) + s["running"][:, :12].sum(axis=1) + loss
    stable = _owner_net(s_long)[:, STABLE_MONTH - 1] * 12.0
    gain = stable - _owner_net(base_long)[:, STABLE_MONTH - 1] * 12.0
    capex = s_long["one_off"].sum(axis=1)
    summary = {
        "savings_pct_at_deadline": net[:, d] * 12.0 / asset * 100.0,
        "run_rate_savings_at_deadline": uplift[:, d] * 12.0,
        "realized_savings_12m": realized,
        "implementation_cost_12m": impl,
        "one_off_implementation_cost": capex,
        "delivery_loss_12m": loss,
        "net_benefit_12m": realized - impl - loss,
        "steady_state_net_run_rate": stable,
        "max_delay_increase_pct": s["out"].max(axis=1) * 100.0,
        "min_csat_pct": s["guest"].min(axis=1),
        "peak_utilization_pct": s["util"].max(axis=1),
        "min_cash_balance": np.minimum(cash.min(axis=1), b.hotel_capex_reserve),
        "projected_operating_profit_12m": net[:, :12].sum(axis=1),
        "owner_net_return_at_deadline": net[:, d] * 12.0,
        "stabilised_yield_pct": stable / asset * 100.0,
        "occupancy_at_deadline_pct": s["occ"][:, d] * 100.0,
        "staff_surplus_fte": s["surplus"].max(axis=1),
        "management_fees_12m": s["fees"][:, :12].sum(axis=1),
        "payback_years": np.clip(capex / np.maximum(gain, 0.1), 0, 30),
    }
    return {"trajectory": traj, "summary": summary}


def _pct(a: np.ndarray, q: float) -> float:
    return float(np.percentile(a, q))


def _r(x: float, nd: int = 3) -> float:
    return round(float(x), nd)


def evaluate_constraints(b: Baseline, c: DecisionControls, levers: HotelLevers,
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
        chk("C1", f"Annual net return ≥ {t:.0f}% of the asset value by month {D}",
            f"عائد سنوي صافٍ ≥ {t:.0f}% من قيمة الأصل بحلول الشهر {D}",
            s["savings_pct_at_deadline"] >= t, "savings_pct_at_deadline", t, ">=", False),
        chk("C2", "No employee terminations", "عدم إنهاء خدمة أي موظف", None, "workforce_termination", 0.0, "<=", True,
            det=(levers.workforce_termination == 0 or not c.no_terminations)),
        chk("C3", f"Rooms out of service ≤ {c.acceptable_delay_increase_pct:.0f}% at any time",
            f"الغرف خارج الخدمة ≤ {c.acceptable_delay_increase_pct:.0f}% في أي وقت",
            s["max_delay_increase_pct"] <= c.acceptable_delay_increase_pct + 1e-9, "max_delay_increase_pct",
            c.acceptable_delay_increase_pct, "<=", True),
        chk("C4", f"Guest score ≥ {c.min_csat_pct:.0f}%", f"تقييم النزلاء ≥ {c.min_csat_pct:.0f}%",
            s["min_csat_pct"] >= c.min_csat_pct - 1e-9, "min_csat_pct", c.min_csat_pct, ">=", True),
        chk("C5", f"Surplus staff ≤ {REDEPLOY_CAPACITY_FTE:.0f} (redeployment capacity)",
            f"العمالة الزائدة ≤ {REDEPLOY_CAPACITY_FTE:.0f} موظفاً (طاقة إعادة التوزيع)",
            s["staff_surplus_fte"] <= REDEPLOY_CAPACITY_FTE + 1e-9, "staff_surplus_fte", REDEPLOY_CAPACITY_FTE, "<=", True),
        chk("C6", f"Capital investment ≤ EGP {c.implementation_budget:.0f}M",
            f"الاستثمار الرأسمالي ≤ {c.implementation_budget:.0f} مليون جنيه",
            s["one_off_implementation_cost"] <= c.implementation_budget + 1e-9, "one_off_implementation_cost",
            c.implementation_budget, "<=", False),
    ]


def _spaces(b: Baseline, levers: HotelLevers, exp_theta: dict[str, np.ndarray], c: DecisionControls) -> dict:
    """Hotel spaces (shown where the cost model shows its project portfolio): months each space is out of
    service during the works, today (0) vs under the proposal; a space is at risk if it closes > 3 months."""
    delay = float(exp_theta["works_delay"][0])
    reno = min(1.0, levers.renovation_capex / HotelEconomics().full_renovation_capex)
    lease = levers.lease_to_operator > 0
    closure = 6.0 * delay if lease else 0.0
    apt = 5.0 * delay * levers.serviced_apartments
    floor_m = ((3.0 + 6.0 * reno) * delay / 3.5) if levers.renovation_capex > 0 else 0.0  # each floor closes in turn
    rows_def = [  # id, en, ar, share of revenue, months closed
        ("F1-2", "Floors 1-2 (rooms)", "الطابقان 1-2 (غرف)", 0.16, max(closure, apt if levers.serviced_apartments else floor_m)),
        ("F3-4", "Floors 3-4 (rooms)", "الطابقان 3-4 (غرف)", 0.16, max(closure, floor_m)),
        ("F5-6", "Floors 5-6 (rooms)", "الطابقان 5-6 (غرف)", 0.16, max(closure, floor_m)),
        ("F7", "Floor 7 and suites", "الطابق 7 والأجنحة", 0.12, max(closure, floor_m)),
        ("FB", "Restaurant and café", "المطعم والكافيه", 0.15, max(closure, 2.0 * delay * reno)),
        ("HALL", "Banquet hall", "قاعة المناسبات", 0.10, max(closure, 1.5 * delay * reno)),
        ("GF", "Ground floor and lobby", "الدور الأرضي والردهة", 0.08, max(closure, 3.0 * delay * levers.business_center, 1.0 * reno)),
        ("APT", "Serviced apartments (new)", "الشقق الفندقية (جديدة)", 0.0, apt),
        ("BC", "Business centre (new)", "مركز الأعمال (جديد)", 0.0, 3.0 * delay * levers.business_center),
    ]
    rows = []
    for sid, en, ar, share, closed in rows_def:
        if sid in ("APT", "BC") and closed <= 0:
            continue
        rows.append({"project_id": sid, "name_en": en, "name_ar": ar, "planned_months": 0.0, "baseline_months": 0.0,
                     "scenario_months": round(closed, 2), "additional_delay_pct": round(closed / 12 * 100, 2),
                     "contract_value_share": share, "at_risk": bool(closed > 3.0 and share > 0)})
    risky = [r for r in rows if r["at_risk"]]
    return {"method": "Works schedule by hotel space (expected case)", "capacity_reduction_fte": 0.0,
            "baseline_capacity_fte": float(b.hotel_staff_fte), "scenario_capacity_fte": float(b.hotel_staff_fte),
            "at_risk_threshold_pct": 25.0, "projects_at_risk": len(risky),
            "revenue_share_at_risk": round(sum(r["contract_value_share"] for r in risky), 4), "projects": rows,
            "kind": "hotel_spaces"}


def sensitivity(b: Baseline, c: DecisionControls, levers: HotelLevers, econ: HotelEconomics,
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
                      econ: HotelEconomics, strategy: HotelProposal | None, theta: dict[str, np.ndarray],
                      include_sensitivity: bool = True, include_des: bool = True) -> dict[str, Any]:
    levers = strategy.levers if strategy else HotelLevers()
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
            "contractual_breach": _r(np.mean(s["staff_surplus_fte"] > REDEPLOY_CAPACITY_FTE + 1e-9)),
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
        out["project_portfolio"] = _spaces(b, levers, mode, c)
    return out


def run_full_simulation(baseline: Baseline, controls: DecisionControls, config: SimulationConfig,
                        params: list[UncertainParameter] | None = None, economics: HotelEconomics | None = None,
                        include_sensitivity: bool = True, include_des: bool = True) -> dict[str, Any]:
    from .engine import _canonical_hash, sample_parameters

    t0 = time.perf_counter()
    params = params or default_parameters()
    econ = economics or HotelEconomics()
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
        "model_id": MODEL_ID, "model_version": MODEL_VERSION, "domain": "hotel",
        "input_fingerprint": _canonical_hash({"model": MODEL_ID, "version": MODEL_VERSION,
                                              "baseline": baseline.model_dump(), "controls": controls.model_dump(),
                                              "config": config.model_dump(), "params": [p.model_dump() for p in params],
                                              "economics": econ.model_dump()}),
        "seed": config.seed, "iterations": config.iterations, "horizon_months": config.horizon_months,
        "controls": controls.model_dump(), "confidence_percentile": controls.confidence_percentile,
        "required_probability": controls.required_probability, "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "method": "Vectorised monthly owner-economics model of a hotel asset (works schedule and rooms out of service, "
                  "occupancy and room-rate ramp, serviced apartments, business centre, lease rent and revenue share, "
                  "management fees, staff redeployment); Monte Carlo over triangular priors with common random numbers; "
                  "one-at-a-time sensitivity; works schedule by hotel space.",
        "nature": "quantitative_simulation",
    }
    return res
