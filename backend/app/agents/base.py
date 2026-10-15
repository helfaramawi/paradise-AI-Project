"""Shared structures for agent findings, evidence, objections and context."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ..simulation.assumptions import Baseline, DecisionControls
from ..simulation.validation import ValidationReport

ClaimType = Literal["fact", "estimate", "assumption", "hypothesis", "recommendation"]
Stance = Literal["support", "oppose", "conditional", "neutral"]

AGENT_CATALOG: dict[str, dict[str, str]] = {
    "orchestrator": {"name_en": "Chief Decision Orchestrator", "name_ar": "منسق القرار الرئيسي",
                     "role_en": "Routes work, controls dependencies, initiates adversarial review and assembles the dossier.",
                     "role_ar": "يوزع المهام ويدير الاعتماديات ويطلق المراجعة النقدية ويجمع ملف القرار."},
    "strategy": {"name_en": "Chief Executive Strategy Agent", "name_ar": "وكيل الاستراتيجية التنفيذية",
                 "role_en": "Interprets objectives, defines success criteria and weighs strategic trade-offs.",
                 "role_ar": "يفسر الأهداف ويحدد معايير النجاح ويوازن المفاضلات الاستراتيجية."},
    "cfo": {"name_en": "Chief Financial Officer Agent", "name_ar": "وكيل المدير المالي",
            "role_en": "Analyses cost structure, cash flow, profitability and financial risk.",
            "role_ar": "يحلل هيكل التكاليف والتدفق النقدي والربحية والمخاطر المالية."},
    "coo": {"name_en": "Chief Operating Officer Agent", "name_ar": "وكيل مدير العمليات",
            "role_en": "Evaluates capacity, process efficiency, bottlenecks and automation feasibility.",
            "role_ar": "يقيّم الطاقة وكفاءة العمليات والاختناقات وجدوى الأتمتة."},
    "hr": {"name_en": "Human Resources Agent", "name_ar": "وكيل الموارد البشرية",
           "role_en": "Analyses utilisation, skills, workload distribution and employee consequences.",
           "role_ar": "يحلل الاستغلال والمهارات وتوزيع العمل والأثر على الموظفين."},
    "delivery": {"name_en": "Project Delivery Agent", "name_ar": "وكيل تسليم المشروعات",
                 "role_en": "Evaluates commitments, schedules, resource conflicts and delay risk.",
                 "role_ar": "يقيّم الالتزامات والجداول وتعارض الموارد ومخاطر التأخير."},
    "legal": {"name_en": "Legal & Compliance Agent", "name_ar": "وكيل الشؤون القانونية والامتثال",
              "role_en": "Flags contractual and regulatory constraints requiring qualified legal review. "
                         "Does not provide legal advice.",
              "role_ar": "ينبه إلى القيود التعاقدية والتنظيمية التي تتطلب مراجعة قانونية متخصصة. لا يقدم استشارة قانونية."},
    "risk": {"name_en": "Risk Management Agent", "name_ar": "وكيل إدارة المخاطر",
             "role_en": "Quantifies exposures, dependencies and uncertainty; recommends mitigations.",
             "role_ar": "يقيس التعرض للمخاطر والاعتماديات وعدم اليقين ويقترح إجراءات التخفيف."},
    "redteam": {"name_en": "Red Team Agent", "name_ar": "وكيل الفريق الأحمر",
                "role_en": "Challenges assumptions, unsupported claims, optimism and contradictions.",
                "role_ar": "يتحدى الافتراضات والادعاءات غير المدعومة والتفاؤل والتناقضات."},
    "governance": {"name_en": "Ethics & Governance Agent", "name_ar": "وكيل الأخلاقيات والحوكمة",
                   "role_en": "Reports decision authority, required approvals and ethical concerns from the policy engine.",
                   "role_ar": "يعرض صلاحيات القرار والموافقات المطلوبة والمخاوف الأخلاقية من محرك السياسات."},
}

DEFAULT_AUTHORITY = {
    "tools": ["read_dataset", "read_simulation", "read_validation", "read_policies"],
    "can_execute": False,
    "can_write_external": False,
    "max_runtime_seconds": 20,
}


@dataclass
class Evidence:
    source_type: str
    reference: str
    label: str
    value: str
    verified: bool = False


@dataclass
class Finding:
    agent: str
    code: str
    claim_type: ClaimType
    topic: str
    text_en: str
    text_ar: str
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    strategy_key: str | None = None
    stance: Stance = "neutral"
    phase: str = "independent_analysis"

    @property
    def evidence_quality(self) -> float:
        """Share of evidence that is computed from data/simulation rather than assumed,
        discounted when the evidence is synthetic/unverified."""
        if not self.evidence:
            return 0.2
        w = {"dataset": 0.8, "validation": 0.8, "simulation": 0.7, "des": 0.7, "policy": 1.0, "assumption": 0.3}
        base = sum(w.get(e.source_type, 0.4) for e in self.evidence) / len(self.evidence)
        verified_bonus = 0.2 * sum(e.verified for e in self.evidence) / len(self.evidence)
        return round(min(1.0, base * 0.8 + verified_bonus), 3)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence_quality"] = self.evidence_quality
        return d


@dataclass
class Objection:
    raised_by: str
    target_agent: str
    target_code: str | None
    strategy_key: str | None
    objection_type: str
    severity: str
    text_en: str
    text_ar: str
    response_by: str | None = None
    response_en: str | None = None
    response_ar: str | None = None
    resolution: str = "unresolved"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentContext:
    baseline: Baseline
    controls: DecisionControls
    validation: ValidationReport
    intake: dict[str, Any]
    simulation: dict[str, Any] | None = None
    findings: list[Finding] = field(default_factory=list)

    def fut(self, key: str) -> dict[str, Any]:
        assert self.simulation is not None
        return self.simulation["futures"][key]


def m(x: float, nd: int = 1) -> str:
    """Format EGP millions."""
    return f"{x:,.{nd}f}"
