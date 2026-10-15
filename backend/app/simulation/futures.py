"""The Three Futures: strategy definitions composed from cost levers."""

from __future__ import annotations

from pydantic import BaseModel

from .assumptions import DecisionControls, Levers


class StrategyDefinition(BaseModel):
    key: str
    name_en: str
    name_ar: str
    tagline_en: str
    tagline_ar: str
    measures_en: list[str]
    measures_ar: list[str]
    levers: Levers
    proposed_by: list[str]  # agent keys whose findings motivated the levers


def build_futures(controls: DecisionControls) -> list[StrategyDefinition]:
    inv = controls.automation_investment
    return [
        StrategyDefinition(
            key="A",
            name_en="Aggressive Cost Reduction",
            name_ar="خفض التكاليف الحاد",
            tagline_en="Fast, deep cuts to non-personnel spend",
            tagline_ar="تخفيضات سريعة وعميقة في الإنفاق غير المتعلق بالموظفين",
            measures_en=["Immediate discretionary expense freeze", "60% contractor reduction",
                         "Software licence consolidation", "Vendor renegotiation",
                         "Partial facilities consolidation"],
            measures_ar=["تجميد فوري للإنفاق التقديري", "خفض المتعاقدين بنسبة 60%",
                         "دمج تراخيص البرمجيات", "إعادة التفاوض مع الموردين", "دمج جزئي للمرافق"],
            levers=Levers(software_consolidation=1.0, infra_optimization=0.8, vendor_renegotiation=1.0,
                          facilities_consolidation=0.5, expense_freeze=1.0, contractor_reduction=0.6,
                          automation_investment=0.0, operating_model_redesign=0.0),
            proposed_by=["cfo", "strategy"],
        ),
        StrategyDefinition(
            key="B",
            name_en="Intelligent Automation",
            name_ar="الأتمتة الذكية",
            tagline_en="Invest in automation to release capacity, then reduce contractors",
            tagline_ar="الاستثمار في الأتمتة لتحرير الطاقة ثم خفض المتعاقدين",
            measures_en=[f"EGP {inv:.1f}M AI process automation programme", "Automated reporting",
                         "Productivity-enabled 40% contractor reduction", "Infrastructure right-sizing",
                         "Gradual licence optimisation"],
            measures_ar=[f"برنامج أتمتة العمليات بالذكاء الاصطناعي بقيمة {inv:.1f} مليون جنيه", "التقارير الآلية",
                         "خفض المتعاقدين 40% بفضل الإنتاجية", "تحسين حجم البنية التحتية", "تحسين تدريجي للتراخيص"],
            levers=Levers(software_consolidation=0.6, infra_optimization=0.8, vendor_renegotiation=0.5,
                          facilities_consolidation=0.0, expense_freeze=0.4, contractor_reduction=0.40,
                          automation_investment=inv, operating_model_redesign=0.0),
            proposed_by=["coo", "cfo"],
        ),
        StrategyDefinition(
            key="C",
            name_en="Strategic Operating Model Redesign",
            name_ar="إعادة تصميم نموذج التشغيل الاستراتيجي",
            tagline_en="Restructure processes, shared services and resource allocation",
            tagline_ar="إعادة هيكلة العمليات والخدمات المشتركة وتوزيع الموارد",
            measures_en=["Business process restructuring", "Resource reallocation and retraining",
                         "Vendor portfolio optimisation", "Shared services and facilities consolidation",
                         "50% contractor reduction with revised delivery model",
                         f"Targeted automation (EGP {min(inv, 2.0):.1f}M)"],
            measures_ar=["إعادة هيكلة العمليات", "إعادة توزيع الموارد وإعادة التأهيل",
                         "تحسين محفظة الموردين", "الخدمات المشتركة ودمج المرافق",
                         "خفض المتعاقدين 50% مع نموذج تسليم معدل",
                         f"أتمتة موجهة ({min(inv, 2.0):.1f} مليون جنيه)"],
            levers=Levers(software_consolidation=0.8, infra_optimization=0.6, vendor_renegotiation=1.0,
                          facilities_consolidation=1.0, expense_freeze=0.5, contractor_reduction=0.5,
                          automation_investment=min(inv, 2.0), operating_model_redesign=1.0),
            proposed_by=["coo", "hr", "strategy"],
        ),
    ]
