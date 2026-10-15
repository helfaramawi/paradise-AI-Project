"""Executive recommendation: evidence-weighted, policy-gated, uncertainty-aware.

Agent disagreement is NOT resolved by majority vote. The procedure is:
  1. Governance verdict is a veto (denied futures are never recommended).
  2. Hard constraints evaluated on Monte Carlo output at the chosen risk tolerance.
  3. Unresolved critical collisions downgrade a future to 'conditional'.
  4. Remaining ties are ranked by evidence-weighted agent support
     (stance x confidence x evidence quality) and by quantitative outcomes.
A naive vote count is reported alongside for transparency only.
"""

from __future__ import annotations

from typing import Any

from ..simulation.assumptions import DecisionControls
from ..simulation.engine import ModelInputs, run_full_simulation
from .base import AgentContext, Finding
from .domain import _fa, _fe

STANCE_W = {"support": 1.0, "conditional": 0.25, "neutral": 0.0, "oppose": -1.0}


def feasibility_search(ctx: AgentContext, params, economics) -> list[dict[str, Any]]:  # noqa: ANN001
    """Scan implementation timelines to find realistic options (reduced iterations, same seed)."""
    from ..simulation.assumptions import SimulationConfig

    rows = []
    for months in (6, 9, 12):
        c2 = ctx.controls.model_copy(update={"implementation_months": months})
        cfg = SimulationConfig(iterations=600, seed=ctx.simulation["meta"]["seed"])
        r = run_full_simulation(ctx.baseline, c2, cfg, params, economics, include_sensitivity=False, include_des=False)
        for k, f in r["futures"].items():
            rows.append({
                "strategy_key": k, "implementation_months": months,
                "achievable_reduction_pct": f["achievable_reduction_pct_at_tolerance"],
                "hard_constraints_violated": f["hard_constraints_violated"],
                "constraints_violated": f["constraints_violated"],
                "net_benefit_12m_p50": f["summary"]["net_benefit_12m"]["p50"],
                "p_delay_ok": f["probabilities"]["delay_within_acceptable"],
            })
    return rows


def build_recommendation(
    ctx: AgentContext, findings: list[Finding], collisions: list[dict], gov: dict[str, dict],
    feasibility: list[dict[str, Any]],
) -> dict[str, Any]:
    sim = ctx.simulation
    assert sim is not None
    per: dict[str, dict[str, Any]] = {}
    for k in "ABC":
        f = sim["futures"][k]
        court = [x for x in findings if x.strategy_key == k and x.phase in ("court", "governance")]
        weighted = sum(STANCE_W[x.stance] * x.confidence * x.evidence_quality for x in court)
        votes = {s: sum(1 for x in court if x.stance == s) for s in STANCE_W}
        crit = [c for c in collisions if c["strategy_key"] in (k, None) and c["severity"] == "critical"]
        g = gov[k]
        if g["outcome"] == "denied":
            status = "not_acceptable"
        elif f["hard_constraints_violated"] or crit:
            status = "conditional"
        else:
            status = "acceptable"
        per[k] = {
            "status": status,
            "governance_outcome": g["outcome"],
            "required_roles": g["required_roles"],
            "hard_constraints_violated": f["hard_constraints_violated"],
            "constraints_violated": f["constraints_violated"],
            "critical_collisions": [c["rule_code"] for c in crit],
            "evidence_weighted_support": round(weighted, 3),
            "naive_vote": votes,
            "achievable_reduction_pct": f["achievable_reduction_pct_at_tolerance"],
            "net_benefit_12m_p50": f["summary"]["net_benefit_12m"]["p50"],
            "p_delay_ok": f["probabilities"]["delay_within_acceptable"],
        }

    def rank(k: str) -> tuple:
        p = per[k]
        return (
            {"acceptable": 2, "conditional": 1, "not_acceptable": 0}[p["status"]],
            -len(p["hard_constraints_violated"]),
            p["evidence_weighted_support"],
            p["p_delay_ok"],
            p["net_benefit_12m_p50"],
        )

    ordered = sorted("ABC", key=rank, reverse=True)
    best = ordered[0]
    naive_winner = max("ABC", key=lambda k: per[k]["naive_vote"]["support"] - per[k]["naive_vote"]["oppose"])

    # Realistic options from feasibility search: hard constraints satisfied
    viable = [r for r in feasibility if not r["hard_constraints_violated"]]
    viable.sort(key=lambda r: (r["achievable_reduction_pct"], -r["implementation_months"]), reverse=True)
    options, seen = [], set()
    for r in viable:  # best (highest reduction, shortest timeline) option per strategy
        if r["strategy_key"] not in seen:
            seen.add(r["strategy_key"])
            options.append(r)

    c: DecisionControls = ctx.controls
    if per[best]["status"] == "acceptable":
        headline_en = f"Recommended for approval review: {_fe(best)} satisfies all hard constraints at the {c.risk_tolerance} risk tolerance."
        headline_ar = f"موصى به للمراجعة والاعتماد: {_fa(best)} يستوفي جميع القيود الإلزامية عند مستوى المخاطرة المختار."
    elif per[best]["status"] == "conditional":
        headline_en = (f"No future satisfies every objective as stated. {_fe(best)} is the strongest basis, conditional on "
                       f"executive changes to the target, timeline or delivery tolerance.")
        headline_ar = (f"لا يوجد مستقبل يحقق كل الأهداف كما صيغت. {_fa(best)} هو الأساس الأقوى، بشرط إجراء تعديلات تنفيذية "
                       f"على الهدف أو الإطار الزمني أو حد التأخير.")
    else:
        headline_en = "All futures are blocked by governance policy. Revise the decision scope."
        headline_ar = "جميع الخيارات مرفوضة بموجب سياسات الحوكمة. يجب تعديل نطاق القرار."

    next_steps = [
        {"en": "Reconcile gross margin vs cost base in the dataset (DQ-002)", "ar": "تسوية الهامش الإجمالي مع قاعدة التكاليف (DQ-002)"},
        {"en": "Commission a skills inventory to verify contractor-absorption capacity", "ar": "إجراء حصر للمهارات للتحقق من القدرة على استيعاب أعمال المتعاقدين"},
        {"en": "Legal review of contractor, vendor and customer delay clauses", "ar": "مراجعة قانونية لبنود المتعاقدين والموردين وتأخير العملاء"},
        {"en": "Run a 6–8 week automation pilot to measure released capacity", "ar": "تنفيذ تجربة أتمتة لمدة 6–8 أسابيع لقياس الطاقة المحررة"},
        {"en": "Submit the selected future for approval by the required roles", "ar": "تقديم المستقبل المختار للاعتماد من الأدوار المطلوبة"},
    ]
    roadmap = [
        {"phase": "0–1", "en": "Quick wins: licence consolidation, discretionary freeze (training ring-fenced), vendor renegotiation",
         "ar": "مكاسب سريعة: دمج التراخيص، تجميد تقديري (مع استثناء التدريب)، إعادة التفاوض مع الموردين"},
        {"phase": "1–3", "en": "Skills inventory, automation pilot, legal contract review, infrastructure right-sizing",
         "ar": "حصر المهارات، تجربة الأتمتة، مراجعة العقود، تحسين البنية التحتية"},
        {"phase": "3–6", "en": "Staged contractor transition on non-critical projects; scale automation if pilot validates",
         "ar": "انتقال تدريجي للمتعاقدين في المشروعات غير الحرجة؛ توسيع الأتمتة إذا نجحت التجربة"},
        {"phase": "6–12", "en": "Operating model adjustments; monthly predicted-vs-actual review and recalibration",
         "ar": "تعديلات نموذج التشغيل؛ مراجعة شهرية للمتوقع مقابل الفعلي وإعادة المعايرة"},
    ]
    return {
        "recommended_strategy": best if per[best]["status"] != "not_acceptable" else None,
        "status": per[best]["status"],
        "headline_en": headline_en,
        "headline_ar": headline_ar,
        "ranking": ordered,
        "per_future": per,
        "method_en": "Governance veto → hard constraints at risk tolerance → critical collisions → evidence-weighted "
                     "support (stance × confidence × evidence quality) → quantitative outcomes. No majority vote.",
        "method_ar": "فيتو الحوكمة ← القيود الإلزامية عند مستوى المخاطرة ← التعارضات الحرجة ← الدعم المرجح بالأدلة "
                     "(الموقف × الثقة × جودة الأدلة) ← النتائج الكمية. لا تصويت بالأغلبية.",
        "naive_majority_winner": naive_winner,
        "majority_differs": naive_winner != best,
        "realistic_options": options,
        "feasibility_grid": feasibility,
        "next_steps": next_steps,
        "roadmap": roadmap,
        "disclaimer_en": "Recommendations are model-based estimates under synthetic data, not certainties or professional "
                         "legal/financial advice. Human approval is required before any action.",
        "disclaimer_ar": "التوصيات تقديرات مبنية على نماذج وبيانات افتراضية وليست يقيناً أو استشارة قانونية أو مالية. "
                         "يلزم اعتماد بشري قبل أي إجراء.",
    }


__all__ = ["build_recommendation", "feasibility_search", "ModelInputs"]
