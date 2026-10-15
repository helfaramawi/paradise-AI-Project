"""Future Collision Detector.

Detects situations where independently reasonable agent positions conflict. Each rule is a
structured predicate over agent stances AND quantitative simulation outputs - it never
depends on free-form LLM text. Severity is computed from measurable consequences.
"""

from __future__ import annotations

from typing import Any

from .base import AgentContext, Finding, m
from .domain import _fa, _fe


def _sev(score: float) -> str:
    return "critical" if score >= 0.75 else "high" if score >= 0.5 else "medium" if score >= 0.25 else "low"


def _stance(findings: list[Finding], agent: str, k: str) -> Finding | None:
    return next((f for f in findings if f.agent == agent and f.strategy_key == k and f.phase == "court"), None)


def detect_collisions(ctx: AgentContext, findings: list[Finding]) -> list[dict[str, Any]]:
    sim = ctx.simulation
    assert sim is not None
    b, c = ctx.baseline, ctx.controls
    out: list[dict[str, Any]] = []

    for k in "ABC":
        f = sim["futures"][k]
        cfo, dl, hr, lg = (_stance(findings, a, k) for a in ("cfo", "delivery", "hr", "legal"))
        n_risk = f["project_portfolio"]["projects_at_risk"]
        p_breach = f["probabilities"]["contractual_breach"]
        short = max(f["trajectory"]["capacity_shortfall_fte"]["expected"])

        # COL-01: savings vs delivery commitments (contractor reduction)
        if (f["levers"]["contractor_reduction"] > 0 and cfo and cfo.stance in ("support", "conditional")
                and dl and dl.stance == "oppose"):
            score = min(1.0, 0.25 + 0.06 * n_risk + 0.4 * p_breach + 0.02 * short)
            positions = [
                {"agent": "cfo", "stance": cfo.stance, "text_en": cfo.text_en, "text_ar": cfo.text_ar},
                {"agent": "delivery", "stance": dl.stance, "text_en": dl.text_en, "text_ar": dl.text_ar},
            ]
            if hr:
                positions.append({"agent": "hr", "stance": hr.stance, "text_en": hr.text_en, "text_ar": hr.text_ar})
            if lg:
                positions.append({"agent": "legal", "stance": lg.stance, "text_en": lg.text_en, "text_ar": lg.text_ar})
            out.append({
                "rule_code": "COL-01", "strategy_key": k, "severity_score": round(score, 3), "severity": _sev(score),
                "title_en": f"{_fe(k)}: contractor savings collide with project delivery commitments",
                "title_ar": f"{_fa(k)}: وفورات المتعاقدين تتصادم مع التزامات تسليم المشروعات",
                "positions": positions,
                "affected_objectives": ["cost_reduction", "project_delivery", "contractual_obligations", "customer_satisfaction"],
                "consequences": [
                    {"en": f"{n_risk} projects at risk of additional delay (SimPy)", "ar": f"{n_risk} مشروعات معرضة لتأخير إضافي"},
                    {"en": f"P(contractual tolerance breached) = {p_breach:.0%}", "ar": f"احتمال تجاوز حد التأخير التعاقدي = {p_breach:.0%}"},
                    {"en": f"Peak internal capacity shortfall {short:.1f} FTE", "ar": f"أقصى عجز في الطاقة الداخلية {short:.1f} موظف"},
                    {"en": f"Median 12-month delivery loss EGP {m(f['summary']['delivery_loss_12m']['p50'])}M",
                     "ar": f"خسارة التسليم الوسيطة خلال 12 شهراً {m(f['summary']['delivery_loss_12m']['p50'])} مليون"},
                ],
                "resolutions": [
                    {"en": "Phase contractor exit behind a verified skills inventory", "ar": "تقسيم خروج المتعاقدين بعد التحقق من المهارات"},
                    {"en": "Protect contractors on critical-path projects", "ar": "حماية المتعاقدين في مشروعات المسار الحرج"},
                    {"en": "Fund retraining / automation before reducing contractors", "ar": "تمويل التأهيل أو الأتمتة قبل خفض المتعاقدين"},
                    {"en": "Extend the implementation timeline", "ar": "مد الإطار الزمني للتنفيذ"},
                ],
                "requires_human": True,
            })

        # COL-04: timeline vs automation ramp
        if f["levers"]["automation_investment"] > 0:
            traj = f["trajectory"]["savings_run_rate"]["expected"]
            D = c.implementation_months
            at_d, at_end = traj[min(D, len(traj) - 1)], traj[-1]
            if at_end > 0 and at_d / at_end < 0.85:
                score = min(1.0, 0.2 + 0.5 * (1 - at_d / at_end))
                out.append({
                    "rule_code": "COL-04", "strategy_key": k, "severity_score": round(score, 3), "severity": _sev(score),
                    "title_en": f"{_fe(k)}: {D}-month deadline collides with automation adoption curve",
                    "title_ar": f"{_fa(k)}: مهلة {D} أشهر تتصادم مع منحنى تبني الأتمتة",
                    "positions": [
                        {"agent": "strategy", "stance": "support", "text_en": f"Savings required by month {D}.", "text_ar": f"الوفورات مطلوبة بحلول الشهر {D}."},
                        {"agent": "coo", "stance": "conditional", "text_en": f"Only {at_d / at_end:.0%} of steady-state savings realised by month {D}.",
                         "text_ar": f"يتحقق {at_d / at_end:.0%} فقط من الوفورات المستقرة بحلول الشهر {D}."},
                    ],
                    "affected_objectives": ["cost_reduction", "timeline"],
                    "consequences": [{"en": f"Run-rate at month {D}: EGP {m(at_d)}M vs EGP {m(at_end)}M at month 12",
                                      "ar": f"الوفورات في الشهر {D}: {m(at_d)} مليون مقابل {m(at_end)} مليون في الشهر 12"}],
                    "resolutions": [{"en": "Accept a later realisation date", "ar": "قبول موعد تحقق لاحق"},
                                    {"en": "Front-load quick-win levers alongside automation", "ar": "تقديم إجراءات سريعة الأثر بجانب الأتمتة"}],
                    "requires_human": True,
                })

        # COL-05: redesign disruption vs delivery during transition
        if f["levers"]["operating_model_redesign"] > 0 and f["summary"]["max_delay_increase_pct"]["p50"] > c.acceptable_delay_increase_pct:
            d = f["summary"]["max_delay_increase_pct"]["p50"]
            score = min(1.0, 0.2 + 0.08 * (d - c.acceptable_delay_increase_pct))
            out.append({
                "rule_code": "COL-05", "strategy_key": k, "severity_score": round(score, 3), "severity": _sev(score),
                "title_en": f"{_fe(k)}: operating-model transition disrupts delivery",
                "title_ar": f"{_fa(k)}: انتقال نموذج التشغيل يربك التسليم",
                "positions": [
                    {"agent": "coo", "stance": "conditional", "text_en": "Redesign yields long-term capacity gains.", "text_ar": "إعادة التصميم تحقق مكاسب طاقة على المدى الطويل."},
                    {"agent": "delivery", "stance": "oppose", "text_en": f"Transition raises median delay +{d:.1f} pts.", "text_ar": f"الانتقال يرفع التأخير الوسيط +{d:.1f} نقطة."},
                ],
                "affected_objectives": ["project_delivery", "customer_satisfaction"],
                "consequences": [{"en": f"Median peak delay increase +{d:.1f} pts", "ar": f"زيادة التأخير الوسيطة +{d:.1f} نقطة"}],
                "resolutions": [{"en": "Sequence redesign by business unit across delivery cycles", "ar": "تنفيذ إعادة التصميم تدريجياً حسب وحدات العمل"},
                                {"en": "Extend the timeline to reduce compression", "ar": "مد الإطار الزمني لتقليل الضغط"}],
                "requires_human": True,
            })

    # COL-02: target vs no-termination constraint (structural)
    ach = max(sim["futures"][k]["achievable_reduction_pct_at_tolerance"] for k in "ABC")
    if ach < c.cost_reduction_target_pct and c.no_terminations:
        gap = c.cost_reduction_target_pct - ach
        score = min(1.0, 0.5 + gap / 20)
        out.append({
            "rule_code": "COL-02", "strategy_key": None, "severity_score": round(score, 3), "severity": _sev(score),
            "title_en": f"{c.cost_reduction_target_pct:.0f}% target collides with the no-termination constraint",
            "title_ar": f"هدف {c.cost_reduction_target_pct:.0f}% يتصادم مع قيد عدم إنهاء الخدمة",
            "positions": [
                {"agent": "strategy", "stance": "support", "text_en": f"Board objective: {c.cost_reduction_target_pct:.0f}% reduction.", "text_ar": f"هدف مجلس الإدارة: خفض {c.cost_reduction_target_pct:.0f}%."},
                {"agent": "hr", "stance": "oppose", "text_en": f"Personnel cost (EGP {m(b.personnel_cost)}M) is protected.", "text_ar": f"تكلفة الموظفين ({m(b.personnel_cost)} مليون) محمية."},
                {"agent": "risk", "stance": "oppose", "text_en": f"Max achievable at tolerance: {ach:.1f}% (gap {gap:.1f} pts).", "text_ar": f"أقصى نسبة ممكنة: {ach:.1f}% (فجوة {gap:.1f} نقطة)."},
            ],
            "affected_objectives": ["cost_reduction", "workforce_protection"],
            "consequences": [{"en": f"Shortfall of EGP {m(b.annual_opex * gap / 100)}M vs target", "ar": f"عجز {m(b.annual_opex * gap / 100)} مليون عن الهدف"}],
            "resolutions": [{"en": f"Revise target to ≈{ach:.0f}%", "ar": f"تعديل الهدف إلى ≈{ach:.0f}%"},
                            {"en": "Extend timeline to 9–12 months", "ar": "مد الإطار الزمني إلى 9–12 شهراً"},
                            {"en": "Consider revenue levers in addition to cost", "ar": "النظر في روافع الإيرادات بجانب التكاليف"}],
            "requires_human": True,
        })

    # COL-03: expense freeze vs retraining dependency
    fa = sim["futures"]["A"]
    if fa["levers"]["expense_freeze"] >= 0.8 and fa["levers"]["contractor_reduction"] > 0:
        out.append({
            "rule_code": "COL-03", "strategy_key": "A", "severity_score": 0.35, "severity": "medium",
            "title_en": "Future A: expense freeze undermines the retraining its contractor cut depends on",
            "title_ar": "المستقبل أ: تجميد الإنفاق يقوض إعادة التأهيل التي يعتمد عليها خفض المتعاقدين",
            "positions": [
                {"agent": "cfo", "stance": "support", "text_en": "Freeze all discretionary spend.", "text_ar": "تجميد كل الإنفاق التقديري."},
                {"agent": "hr", "stance": "oppose", "text_en": "Training budget is needed to raise skill match.", "text_ar": "ميزانية التدريب ضرورية لرفع توافق المهارات."},
            ],
            "affected_objectives": ["cost_reduction", "project_delivery"],
            "consequences": [{"en": "Skill match reduced by up to 0.10 in the model", "ar": "انخفاض توافق المهارات حتى 0.10 في النموذج"}],
            "resolutions": [{"en": "Ring-fence training budget", "ar": "استثناء ميزانية التدريب من التجميد"}],
            "requires_human": False,
        })
    out.sort(key=lambda x: x["severity_score"], reverse=True)
    return out


def risk_register(ctx: AgentContext) -> list[dict[str, Any]]:
    """Quantified risks per future derived from Monte Carlo outputs (probability x impact)."""
    sim = ctx.simulation
    assert sim is not None
    b = ctx.baseline
    rows = []
    for k in "ABC":
        f = sim["futures"][k]
        p = f["probabilities"]
        s = f["summary"]
        items = [
            ("R-TGT", "Savings target missed", "عدم تحقيق هدف الوفورات", 1 - p["meet_target"],
             max(0.0, b.annual_opex * ctx.controls.cost_reduction_target_pct / 100 - s["run_rate_savings_at_deadline"]["p50"]),
             "P(savings_pct_at_deadline < target); impact = median run-rate gap",
             "Revise target or add levers; track monthly run-rate.", "تعديل الهدف أو إضافة روافع؛ متابعة الوفورات شهرياً."),
            ("R-DEL", "Delivery delay beyond acceptable", "تأخير التسليم فوق المقبول", 1 - p["delay_within_acceptable"],
             s["delivery_loss_12m"]["p90"], "P(max delay increase > acceptable); impact = P90 delivery loss",
             "Protect critical-path capacity; staged contractor exit.", "حماية طاقة المسار الحرج؛ خروج تدريجي للمتعاقدين."),
            ("R-CON", "Contractual penalties", "غرامات تعاقدية", p["contractual_breach"],
             s["delivery_loss_12m"]["p90"] * 0.4, "P(delay > contractual tolerance); impact = penalty share of P90 loss (proxy)",
             "Legal review of LD clauses; client communication plan.", "مراجعة قانونية لبنود التعويض؛ خطة تواصل مع العملاء."),
            ("R-CSAT", "Customer satisfaction decline", "تراجع رضا العملاء", 1 - p["csat_maintained"],
             b.annual_revenue * max(0.0, ctx.controls.min_csat_pct - s["min_csat_pct"]["p10"]) * 0.002,
             "P(min CSAT < floor); impact = churn proxy 0.2% revenue per CSAT pt below floor (assumption)",
             "Account-level service monitoring during transition.", "مراقبة الخدمة لكل عميل أثناء الانتقال."),
            ("R-IMP", "Implementation cost overrun", "تجاوز تكلفة التنفيذ",
             float(s["one_off_implementation_cost"]["p90"] > ctx.controls.implementation_budget) * 0.1 + 0.25,
             max(0.0, s["one_off_implementation_cost"]["p90"] - s["one_off_implementation_cost"]["expected"]),
             "Overrun prior (0.95–1.5x); impact = P90 minus expected cost",
             "Stage-gate funding; fixed-price where possible.", "تمويل على مراحل؛ عقود بسعر ثابت متى أمكن."),
        ]
        for code, en, ar, prob, impact, basis, mit_en, mit_ar in items:
            exp_loss = prob * impact
            sev = "critical" if exp_loss > 3 else "high" if exp_loss > 1 else "medium" if exp_loss > 0.3 else "low"
            rows.append({"scenario_key": k, "risk_code": code, "title_en": en, "title_ar": ar,
                         "probability": round(float(prob), 3), "impact_egp_m": round(float(impact), 2),
                         "severity": sev, "basis": basis, "mitigation_en": mit_en, "mitigation_ar": mit_ar})
    return rows
