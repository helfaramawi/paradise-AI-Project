"""Data quality and financial-consistency validation of the enterprise dataset.

Checks are deterministic. Each check returns a bilingual message, severity and the
values it was computed from, so findings are traceable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .assumptions import Baseline

Severity = Literal["ok", "info", "warning", "error"]


class ValidationCheck(BaseModel):
    code: str
    severity: Severity
    title_en: str
    title_ar: str
    detail_en: str
    detail_ar: str
    values: dict[str, float]


class ValidationReport(BaseModel):
    checks: list[ValidationCheck]
    quality_score: float  # share of checks without warning/error
    has_errors: bool
    interpretation_en: str
    interpretation_ar: str


def _fmt(x: float) -> str:
    return f"{x:,.1f}"


def validate_baseline(b: Baseline) -> ValidationReport:
    checks: list[ValidationCheck] = []
    gross_profit = b.annual_revenue * b.gross_margin_pct / 100
    cogs = b.annual_revenue - gross_profit
    op_profit_if_total = b.annual_revenue - b.annual_opex
    op_margin_if_total = op_profit_if_total / b.annual_revenue * 100
    op_profit_if_below_gp = gross_profit - b.annual_opex

    # 1. Sum of cost categories equals the stated cost base.
    cat_sum = sum(b.cost_categories.values())
    diff = cat_sum - b.annual_opex
    checks.append(ValidationCheck(
        code="DQ-001",
        severity="ok" if abs(diff) < 0.05 else "error",
        title_en="Cost categories reconcile to operating expense total",
        title_ar="تطابق فئات التكلفة مع إجمالي المصروفات التشغيلية",
        detail_en=f"Categories sum to EGP {_fmt(cat_sum)}M vs stated EGP {_fmt(b.annual_opex)}M "
                  f"(difference {_fmt(diff)}M).",
        detail_ar=f"مجموع الفئات {_fmt(cat_sum)} مليون جنيه مقابل {_fmt(b.annual_opex)} مليون "
                  f"(الفرق {_fmt(diff)} مليون).",
        values={"category_sum": cat_sum, "annual_opex": b.annual_opex, "difference": diff},
    ))

    # 2. Gross margin vs operating cost base consistency.
    if b.annual_opex > gross_profit:
        # Interpretation A (opex below gross profit) produces an operating loss.
        # Interpretation B (opex = total cost base) produces an operating margin
        # above the gross margin, which is arithmetically impossible.
        inconsistent = op_margin_if_total > b.gross_margin_pct
        checks.append(ValidationCheck(
            code="DQ-002",
            severity="error" if inconsistent else "warning",
            title_en="Gross margin is inconsistent with the operating cost base",
            title_ar="هامش الربح الإجمالي غير متسق مع قاعدة التكاليف التشغيلية",
            detail_en=(
                f"Gross margin {b.gross_margin_pct:.0f}% implies gross profit EGP {_fmt(gross_profit)}M "
                f"(cost of revenue {_fmt(cogs)}M). If the EGP {_fmt(b.annual_opex)}M operating expenses sit "
                f"below gross profit, operating profit = EGP {_fmt(op_profit_if_below_gp)}M (a loss). "
                f"If they are the total cost base, operating margin = {op_margin_if_total:.1f}%, which "
                f"cannot exceed the {b.gross_margin_pct:.0f}% gross margin. The dataset cannot be "
                f"consistent under either reading."
            ),
            detail_ar=(
                f"هامش ربح إجمالي {b.gross_margin_pct:.0f}% يعني ربحاً إجمالياً {_fmt(gross_profit)} مليون "
                f"(تكلفة الإيرادات {_fmt(cogs)} مليون). إذا كانت المصروفات التشغيلية ({_fmt(b.annual_opex)} مليون) "
                f"تأتي بعد الربح الإجمالي فإن الربح التشغيلي = {_fmt(op_profit_if_below_gp)} مليون (خسارة). "
                f"وإذا كانت تمثل إجمالي التكاليف فإن الهامش التشغيلي = {op_margin_if_total:.1f}% وهو لا يمكن أن "
                f"يتجاوز الهامش الإجمالي {b.gross_margin_pct:.0f}%. البيانات غير متسقة في الحالتين."
            ),
            values={
                "gross_profit": gross_profit,
                "cost_of_revenue": cogs,
                "operating_profit_if_opex_below_gp": op_profit_if_below_gp,
                "operating_profit_if_total_cost_base": op_profit_if_total,
                "operating_margin_if_total_cost_base_pct": op_margin_if_total,
            },
        ))
    else:
        checks.append(ValidationCheck(
            code="DQ-002", severity="ok",
            title_en="Gross margin consistent with operating cost base",
            title_ar="هامش الربح الإجمالي متسق مع قاعدة التكاليف",
            detail_en=f"Operating profit EGP {_fmt(op_profit_if_below_gp)}M after operating expenses.",
            detail_ar=f"الربح التشغيلي {_fmt(op_profit_if_below_gp)} مليون بعد المصروفات التشغيلية.",
            values={"gross_profit": gross_profit, "operating_profit": op_profit_if_below_gp},
        ))

    # 3. Personnel cost per employee plausibility.
    per_emp = b.personnel_cost / b.employees * 1000  # EGP thousands
    checks.append(ValidationCheck(
        code="DQ-003",
        severity="info",
        title_en="Personnel cost decomposition is a synthetic assumption",
        title_ar="تفصيل تكلفة الموظفين افتراض تجريبي",
        detail_en=f"Personnel cost EGP {_fmt(b.personnel_cost)}M implies ~EGP {per_emp:,.0f}K loaded cost "
                  f"per employee per year. Not provided in the source data; replace with payroll data.",
        detail_ar=f"تكلفة الموظفين {_fmt(b.personnel_cost)} مليون تعني حوالي {per_emp:,.0f} ألف جنيه سنوياً "
                  f"للموظف. هذه القيمة غير موجودة في البيانات المصدر ويجب استبدالها ببيانات الرواتب.",
        values={"personnel_cost": b.personnel_cost, "loaded_cost_per_employee_k": per_emp},
    ))

    # 4. Utilisation headroom.
    headroom = b.max_sustainable_utilization_pct - b.utilization_pct
    checks.append(ValidationCheck(
        code="DQ-004",
        severity="ok" if headroom > 0 else "warning",
        title_en="Workforce utilisation headroom",
        title_ar="هامش استغلال القوى العاملة",
        detail_en=f"Utilisation {b.utilization_pct:.0f}% vs sustainable ceiling "
                  f"{b.max_sustainable_utilization_pct:.0f}% gives {headroom:.0f} pts headroom "
                  f"(~{b.employees * headroom / 100:.1f} FTE before skill matching).",
        detail_ar=f"الاستغلال {b.utilization_pct:.0f}% مقابل حد مستدام {b.max_sustainable_utilization_pct:.0f}% "
                  f"أي هامش {headroom:.0f} نقطة (حوالي {b.employees * headroom / 100:.1f} موظف قبل مطابقة المهارات).",
        values={"headroom_pts": headroom, "headroom_fte": b.employees * headroom / 100},
    ))

    # 5. Missing data needed for high-confidence analysis.
    checks.append(ValidationCheck(
        code="DQ-005",
        severity="warning",
        title_en="No historical outcome data or skills inventory",
        title_ar="لا توجد بيانات تاريخية للنتائج أو سجل للمهارات",
        detail_en="Distributions use expert-judgement priors. Skill-match, penalty terms and "
                  "automation productivity are unverified and drive most of the uncertainty.",
        detail_ar="التوزيعات الاحتمالية مبنية على تقديرات الخبراء. توافق المهارات وشروط الغرامات وإنتاجية "
                  "الأتمتة غير متحقق منها وهي مصدر معظم عدم اليقين.",
        values={},
    ))

    # 6. Contractor dependency.
    c_share = b.contractor_fte / b.delivery_workload_fte * 100
    checks.append(ValidationCheck(
        code="DQ-006",
        severity="info" if c_share < 25 else "warning",
        title_en="Delivery dependency on contractors",
        title_ar="اعتماد التسليم على المتعاقدين",
        detail_en=f"Contractors provide ~{b.contractor_fte:.0f} FTE ({c_share:.0f}% of delivery workload) "
                  f"at an assumed EGP {b.contractor_fte_cost:.2f}M per FTE-year.",
        detail_ar=f"يوفر المتعاقدون حوالي {b.contractor_fte:.0f} موظف مكافئ ({c_share:.0f}% من عبء التسليم) "
                  f"بتكلفة مفترضة {b.contractor_fte_cost:.2f} مليون لكل موظف مكافئ سنوياً.",
        values={"contractor_fte": b.contractor_fte, "contractor_share_pct": c_share},
    ))

    bad = sum(1 for c in checks if c.severity in ("warning", "error"))
    return ValidationReport(
        checks=checks,
        quality_score=round(1 - bad / len(checks), 3),
        has_errors=any(c.severity == "error" for c in checks),
        interpretation_en=(
            "Modelling interpretation used: 'operating expenses' = total annual cost base "
            f"(EGP {_fmt(b.annual_opex)}M). The stated gross margin is flagged as unverified and is "
            "NOT used in calculations. Edit the dataset to resolve the inconsistency."
        ),
        interpretation_ar=(
            "التفسير المستخدم في النموذج: 'المصروفات التشغيلية' = إجمالي قاعدة التكاليف السنوية "
            f"({_fmt(b.annual_opex)} مليون جنيه). هامش الربح الإجمالي المذكور غير متحقق منه ولا يُستخدم في "
            "الحسابات. عدّل البيانات لحل التعارض."
        ),
    )
