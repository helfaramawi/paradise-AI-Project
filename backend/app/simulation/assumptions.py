"""Versioned, editable model inputs for the Operating Cost Optimization simulation.

Every number in this module is SYNTHETIC demonstration data or a documented
modelling assumption. Nothing here is a verified company fact. Each field carries
provenance metadata so the UI and reports can label it correctly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

MODEL_ID = "opex-optimization"
MODEL_VERSION = "1.3.0"

Provenance = Literal["synthetic_given", "synthetic_assumption", "user_input", "imported"]


class Baseline(BaseModel):
    """Baseline enterprise profile. Monetary values are EGP millions per year."""

    currency: str = "EGP"
    annual_opex: float = Field(120.0, gt=0, description="Total annual operating cost base")
    employees: int = Field(150, gt=0)
    active_projects: int = Field(18, ge=1)
    annual_revenue: float = Field(180.0, gt=0)
    gross_margin_pct: float = Field(28.0, ge=0, le=100)
    utilization_pct: float = Field(72.0, ge=0, le=100)
    avg_project_delay_pct: float = Field(8.0, ge=0)
    csat_pct: float = Field(86.0, ge=0, le=100)
    software_cost: float = Field(12.0, ge=0)
    infrastructure_cost: float = Field(9.0, ge=0)
    contractor_cost: float = Field(18.0, ge=0)
    # Synthetic decomposition of the remaining cost base (assumption, editable).
    personnel_cost: float = Field(66.0, ge=0)
    facilities_cost: float = Field(6.0, ge=0)
    vendor_services_cost: float = Field(5.0, ge=0)
    other_ga_cost: float = Field(4.0, ge=0)
    # Operating parameters (assumptions).
    contractor_fte_cost: float = Field(0.6, gt=0, description="EGP M per contractor FTE-year")
    max_sustainable_utilization_pct: float = Field(85.0, gt=0, le=100)
    contractual_delay_tolerance_pct: float = Field(10.0, ge=0)
    opening_cash: float = Field(25.0)
    training_share_of_other_ga: float = Field(0.25, ge=0, le=1)
    # Receivables and collections (assumptions; used by the collections decision domain).
    overdue_receivables: float = Field(32.0, ge=0, description="Overdue receivables (31+ days), EGP M")
    ontime_collection_rate_pct: float = Field(86.0, ge=0, le=100, description="Share of billing collected within terms")
    inhouse_recovery_rate_pct: float = Field(3.5, ge=0, le=100, description="Overdue balance recovered in-house per month")
    writeoff_rate_pct: float = Field(0.8, ge=0, le=100, description="Overdue balance written off per month")
    key_account_overdue_share_pct: float = Field(45.0, ge=0, le=100, description="Overdue owed by key/government accounts")
    collections_team_fte: float = Field(6.0, gt=0)
    collections_team_utilization_pct: float = Field(82.0, ge=0, le=100)
    complaint_rate_pct: float = Field(3.0, ge=0, le=100, description="Customer complaints per 100 active accounts")
    # State-owned hotel asset (assumptions; used by the hotel decision domain). Illustrative, not real figures.
    hotel_rooms: int = Field(148, gt=0)
    hotel_occupancy_pct: float = Field(34.0, ge=0, le=100, description="Average annual room occupancy")
    hotel_adr_egp: float = Field(1600.0, gt=0, description="Average daily room rate, EGP")
    hotel_staff_fte: float = Field(120.0, gt=0)
    hotel_staff_utilization_pct: float = Field(58.0, ge=0, le=100)
    hotel_fixed_opex: float = Field(10.0, ge=0, description="Utilities, maintenance, insurance, admin, EGP M / year")
    hotel_guest_score_pct: float = Field(66.0, ge=0, le=100, description="Average guest review score")
    hotel_asset_value: float = Field(420.0, gt=0, description="Indicative market value of the hotel, EGP M")
    hotel_capex_reserve: float = Field(40.0, description="Funds allocated to the hotel, EGP M")

    @property
    def cost_categories(self) -> dict[str, float]:
        return {
            "personnel": self.personnel_cost,
            "contractors": self.contractor_cost,
            "software": self.software_cost,
            "infrastructure": self.infrastructure_cost,
            "facilities": self.facilities_cost,
            "vendor_services": self.vendor_services_cost,
            "other_ga": self.other_ga_cost,
        }

    @property
    def contractor_fte(self) -> float:
        return self.contractor_cost / self.contractor_fte_cost

    @property
    def delivery_workload_fte(self) -> float:
        """Productive workload currently delivered (internal utilised FTE + contractors)."""
        return self.employees * self.utilization_pct / 100.0 + self.contractor_fte


BASELINE_PROVENANCE: dict[str, Provenance] = {
    "annual_opex": "synthetic_given",
    "employees": "synthetic_given",
    "active_projects": "synthetic_given",
    "annual_revenue": "synthetic_given",
    "gross_margin_pct": "synthetic_given",
    "utilization_pct": "synthetic_given",
    "avg_project_delay_pct": "synthetic_given",
    "csat_pct": "synthetic_given",
    "software_cost": "synthetic_given",
    "infrastructure_cost": "synthetic_given",
    "contractor_cost": "synthetic_given",
    "personnel_cost": "synthetic_assumption",
    "facilities_cost": "synthetic_assumption",
    "vendor_services_cost": "synthetic_assumption",
    "other_ga_cost": "synthetic_assumption",
    "contractor_fte_cost": "synthetic_assumption",
    "max_sustainable_utilization_pct": "synthetic_assumption",
    "contractual_delay_tolerance_pct": "synthetic_assumption",
    "opening_cash": "synthetic_assumption",
    "training_share_of_other_ga": "synthetic_assumption",
    "overdue_receivables": "synthetic_assumption",
    "ontime_collection_rate_pct": "synthetic_assumption",
    "inhouse_recovery_rate_pct": "synthetic_assumption",
    "writeoff_rate_pct": "synthetic_assumption",
    "key_account_overdue_share_pct": "synthetic_assumption",
    "collections_team_fte": "synthetic_assumption",
    "collections_team_utilization_pct": "synthetic_assumption",
    "complaint_rate_pct": "synthetic_assumption",
    "hotel_rooms": "synthetic_assumption",
    "hotel_occupancy_pct": "synthetic_assumption",
    "hotel_adr_egp": "synthetic_assumption",
    "hotel_staff_fte": "synthetic_assumption",
    "hotel_staff_utilization_pct": "synthetic_assumption",
    "hotel_fixed_opex": "synthetic_assumption",
    "hotel_guest_score_pct": "synthetic_assumption",
    "hotel_asset_value": "synthetic_assumption",
    "hotel_capex_reserve": "synthetic_assumption",
}


class Triangular(BaseModel):
    """Triangular distribution (low, mode, high). Used where only expert ranges exist."""

    low: float
    mode: float
    high: float

    @model_validator(mode="after")
    def _ordered(self) -> "Triangular":
        if not (self.low <= self.mode <= self.high):
            raise ValueError("Triangular requires low <= mode <= high")
        return self


class UncertainParameter(BaseModel):
    key: str
    label_en: str
    label_ar: str
    unit: str
    dist: Triangular
    rationale: str
    calibration: str = (
        "Expert-judgement prior. No historical outcome data available for calibration; "
        "range intentionally wide."
    )


def default_uncertain_parameters() -> list[UncertainParameter]:
    P = UncertainParameter
    T = Triangular
    return [
        P(key="sw_savings_rate", label_en="Software consolidation savings rate",
          label_ar="نسبة وفورات دمج التراخيص", unit="share of software spend",
          dist=T(low=0.12, mode=0.22, high=0.32),
          rationale="Typical licence rationalisation removes duplicate/unused seats."),
        P(key="infra_savings_rate", label_en="Infrastructure optimisation savings rate",
          label_ar="نسبة وفورات تحسين البنية التحتية", unit="share of infrastructure spend",
          dist=T(low=0.12, mode=0.25, high=0.35),
          rationale="Right-sizing, reserved capacity and decommissioning idle assets."),
        P(key="vendor_savings_rate", label_en="Vendor renegotiation savings rate",
          label_ar="نسبة وفورات إعادة التفاوض مع الموردين", unit="share of vendor spend",
          dist=T(low=0.04, mode=0.08, high=0.14),
          rationale="Depends on contract renewal dates and market alternatives."),
        P(key="facilities_savings_rate", label_en="Facilities consolidation savings rate",
          label_ar="نسبة وفورات دمج المرافق", unit="share of facilities spend",
          dist=T(low=0.08, mode=0.18, high=0.28),
          rationale="Space consolidation / shared services; lease terms constrain timing."),
        P(key="discretionary_savings_rate", label_en="Discretionary spend freeze savings rate",
          label_ar="نسبة وفورات تجميد الإنفاق التقديري", unit="share of other G&A",
          dist=T(low=0.20, mode=0.30, high=0.45),
          rationale="Travel, events and non-critical purchases."),
        P(key="skill_match", label_en="Internal skill match for contractor work",
          label_ar="مدى توافق مهارات الموظفين مع أعمال المتعاقدين", unit="fraction",
          dist=T(low=0.35, mode=0.55, high=0.75),
          rationale="Share of spare internal capacity that has the skills to absorb "
                    "contractor work. NOT verified - no skills inventory available."),
        P(key="automation_productivity", label_en="Automation capacity release",
          label_ar="الطاقة المحررة بالأتمتة", unit="FTE per EGP 1M invested",
          dist=T(low=1.0, mode=1.8, high=2.6),
          rationale="Capacity freed at full adoption per EGP 1M of automation investment."),
        P(key="automation_adoption_months", label_en="Automation adoption time",
          label_ar="مدة تبني الأتمتة", unit="months",
          dist=T(low=4.0, mode=6.0, high=9.0),
          rationale="Months to reach full adoption (S-curve midpoint at half this value)."),
        P(key="reallocation_gain_pct", label_en="Resource reallocation utilisation gain",
          label_ar="مكسب الاستغلال من إعادة توزيع الموارد", unit="utilisation points",
          dist=T(low=3.0, mode=6.0, high=9.0),
          rationale="Effective capacity gained by operating model redesign at full effect."),
        P(key="delay_elasticity", label_en="Delay elasticity to capacity shortfall",
          label_ar="مرونة التأخير لعجز الطاقة", unit="delay pts per 1% shortfall",
          dist=T(low=0.8, mode=1.2, high=1.8),
          rationale="Portfolio delay points added per 1% of delivery capacity shortfall."),
        P(key="csat_delay_sensitivity", label_en="CSAT sensitivity to delay",
          label_ar="حساسية رضا العملاء للتأخير", unit="CSAT pts per delay pt",
          dist=T(low=0.25, mode=0.45, high=0.70),
          rationale="Customer satisfaction points lost per additional delay point."),
        P(key="penalty_rate_pct", label_en="Contractual penalty rate",
          label_ar="معدل الغرامات التعاقدية", unit="% revenue per delay pt over tolerance",
          dist=T(low=0.05, mode=0.10, high=0.20),
          rationale="Liquidated damages proxy. Real contracts must be reviewed by Legal."),
        P(key="change_disruption_pct", label_en="Change disruption",
          label_ar="اضطراب التغيير", unit="% capacity lost during transition",
          dist=T(low=1.0, mode=3.0, high=6.0),
          rationale="Temporary productivity loss while redesigning the operating model."),
        P(key="impl_cost_overrun", label_en="Implementation cost overrun factor",
          label_ar="معامل تجاوز تكلفة التنفيذ", unit="multiplier",
          dist=T(low=0.95, mode=1.10, high=1.50),
          rationale="Right-skewed: transformation programmes rarely come in under budget."),
    ]


class Levers(BaseModel):
    """Intensity of each cost lever in a strategy (0..1 unless stated)."""

    software_consolidation: float = Field(0.0, ge=0, le=1)
    infra_optimization: float = Field(0.0, ge=0, le=1)
    vendor_renegotiation: float = Field(0.0, ge=0, le=1)
    facilities_consolidation: float = Field(0.0, ge=0, le=1)
    expense_freeze: float = Field(0.0, ge=0, le=1)
    contractor_reduction: float = Field(0.0, ge=0, le=1, description="Share of contractor spend removed")
    automation_investment: float = Field(0.0, ge=0, le=50, description="EGP M")
    operating_model_redesign: float = Field(0.0, ge=0, le=1)
    workforce_termination: float = Field(
        0.0, ge=0, le=1,
        description="Share of headcount terminated. Present so governance can test and block it.",
    )


class LeverEconomics(BaseModel):
    """Implementation cost (EGP M at intensity 1) and ramp months at a 6-month programme."""

    impl_cost: dict[str, float] = {
        "software_consolidation": 0.5,
        "infra_optimization": 0.7,
        "vendor_renegotiation": 0.2,
        "facilities_consolidation": 0.9,
        "expense_freeze": 0.0,
        "contractor_reduction": 0.6,  # knowledge transfer / transition
        "operating_model_redesign": 2.5,
    }
    ramp_months: dict[str, float] = {
        "software_consolidation": 3,
        "infra_optimization": 4,
        "vendor_renegotiation": 2,
        "facilities_consolidation": 6,
        "expense_freeze": 1,
        "contractor_reduction": 2,
        "operating_model_redesign": 5,
    }
    automation_running_cost_rate: float = 0.15  # of investment per year


class DecisionControls(BaseModel):
    """Executive sliders. Changing any of these triggers recalculation.

    domain selects the decision model: "opex" (operating cost reduction), "collections" (revenue
    collections improvement) or "hotel" (getting the most out of a state-owned hotel). In the collections
    domain cost_reduction_target_pct is the collections uplift target and acceptable_delay_increase_pct the
    acceptable rise in the complaint rate; in the hotel domain they are the target annual return (% of the
    asset value) and the largest acceptable share of rooms out of service.
    """

    domain: Literal["opex", "collections", "hotel"] = "opex"
    cost_reduction_target_pct: float = Field(20.0, ge=1, le=60)
    implementation_months: int = Field(6, ge=2, le=18)
    no_terminations: bool = True
    max_utilization_pct: float = Field(85.0, ge=60, le=100)
    automation_investment: float = Field(6.0, ge=0, le=30)
    acceptable_delay_increase_pct: float = Field(2.0, ge=0, le=100)
    min_csat_pct: float = Field(85.0, ge=0, le=100)
    risk_tolerance: Literal["low", "medium", "high"] = "medium"
    implementation_budget: float = Field(12.0, ge=0, le=100, description="EGP M cap")

    @property
    def confidence_percentile(self) -> int:
        """Percentile of the outcome distribution that must satisfy each constraint."""
        return {"low": 10, "medium": 30, "high": 50}[self.risk_tolerance]

    @property
    def required_probability(self) -> float:
        return {"low": 0.9, "medium": 0.7, "high": 0.5}[self.risk_tolerance]


class SimulationConfig(BaseModel):
    iterations: int = Field(2000, ge=100, le=20000)
    seed: int = 20260101
    horizon_months: int = Field(12, ge=6, le=36)
