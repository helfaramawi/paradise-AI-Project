"""Reality Feedback Loop: predicted vs actual, calibration diagnostics and candidate models.

Model changes are never applied automatically. A calibration proposal creates a CANDIDATE
model version with a backtest; promotion to production requires an explicit, audited
approval by a user holding governance.manage.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import (
    ActualOutcome,
    ApprovalRequest,
    Decision,
    ForecastComparison,
    SimulationModel,
    SimulationResult,
    SimulationRun,
)
from .dossier import latest_run

METRICS = {
    "opex_monthly": ("Monthly operating cost (EGP M)", "التكلفة التشغيلية الشهرية"),
    "revenue_monthly": ("Monthly revenue (EGP M)", "الإيراد الشهري"),
    "savings_run_rate": ("Savings run-rate (EGP M/yr)", "معدل الوفورات السنوي"),
    "delay_pct": ("Average project delay (%)", "متوسط تأخير المشروعات"),
    "utilization_pct": ("Utilisation (%)", "الاستغلال"),
    "csat_pct": ("Customer satisfaction (%)", "رضا العملاء"),
    "cash_balance": ("Cash balance (EGP M)", "الرصيد النقدي"),
}
# Same metric keys, named for the collections domain (see simulation/collections.py).
METRICS_COLLECTIONS = {
    **METRICS,
    "opex_monthly": ("Monthly operating cost incl. fees (EGP M)", "التكلفة التشغيلية الشهرية شاملة العمولات"),
    "revenue_monthly": ("Monthly billing (EGP M)", "الفوترة الشهرية"),
    "savings_run_rate": ("Extra collections run-rate (EGP M/yr)", "معدل المتحصلات الإضافية السنوي"),
    "delay_pct": ("Customer complaint rate (%)", "معدل شكاوى العملاء"),
    "utilization_pct": ("Collections team utilisation (%)", "استغلال فريق التحصيل"),
}


def tracked_scenario(db: Session, decision: Decision) -> tuple[str, SimulationRun]:
    req = db.scalar(select(ApprovalRequest).where(ApprovalRequest.decision_id == decision.id,
                                                  ApprovalRequest.status == "approved")
                    .order_by(ApprovalRequest.created_at.desc()))
    run = latest_run(db, decision.id)
    if not run:
        raise HTTPException(409, "Decision has no completed analysis")
    sim = db.scalar(select(SimulationRun).where(SimulationRun.run_id == run.id))
    key = req.scenario_key if req else (decision.recommended_strategy or "B")
    return key, sim


def recompute(db: Session, decision: Decision) -> list[ForecastComparison]:
    key, sim = tracked_scenario(db, decision)
    res = db.scalar(select(SimulationResult).where(SimulationResult.simulation_run_id == sim.id,
                                                   SimulationResult.scenario_key == key))
    traj = res.data["trajectory"]
    db.execute(delete(ForecastComparison).where(ForecastComparison.decision_id == decision.id))
    out = []
    for a in db.scalars(select(ActualOutcome).where(ActualOutcome.decision_id == decision.id)):
        if a.metric not in traj or a.month >= len(traj[a.metric]["expected"]):
            continue
        t = traj[a.metric]
        pred, lo, hi = t["expected"][a.month], t["p10"][a.month], t["p90"][a.month]
        err = a.value - pred
        fc = ForecastComparison(decision_id=decision.id, simulation_run_id=sim.id, scenario_key=key, month=a.month,
                                metric=a.metric, predicted=pred, predicted_p10=lo, predicted_p90=hi, actual=a.value,
                                error=round(err, 4), error_pct=round(err / pred * 100, 2) if pred else 0.0,
                                within_interval=bool(min(lo, hi) - 1e-9 <= a.value <= max(lo, hi) + 1e-9))
        db.add(fc)
        out.append(fc)
    db.commit()
    return out


def calibration_summary(comps: list[ForecastComparison]) -> dict[str, Any]:
    by: dict[str, list[ForecastComparison]] = {}
    for c in comps:
        by.setdefault(c.metric, []).append(c)
    metrics = {}
    diagnostics = []
    for mtr, rows in by.items():
        errs = np.array([r.error_pct for r in rows])
        cover = float(np.mean([r.within_interval for r in rows]))
        above = sum(r.actual > max(r.predicted_p10, r.predicted_p90) for r in rows)
        below = sum(r.actual < min(r.predicted_p10, r.predicted_p90) for r in rows)
        metrics[mtr] = {"n": len(rows), "mape_pct": round(float(np.mean(np.abs(errs))), 2),
                        "bias_pct": round(float(np.mean(errs)), 2), "interval_coverage": round(cover, 3),
                        "above_p90": int(above), "below_p10": int(below)}
        if mtr == "delay_pct" and above:
            diagnostics.append({"metric": mtr, "parameter": "skill_match", "direction": "lower",
                                "en": "Actual delay exceeded the P90 band: internal skill match / delay elasticity "
                                      "assumptions appear optimistic.",
                                "ar": "تجاوز التأخير الفعلي نطاق P90: افتراضات توافق المهارات أو مرونة التأخير متفائلة."})
        if mtr == "savings_run_rate" and below:
            diagnostics.append({"metric": mtr, "parameter": "sw_savings_rate", "direction": "lower",
                                "en": "Savings realised below the P10 band: savings rates or ramp-up are optimistic.",
                                "ar": "الوفورات المحققة أقل من نطاق P10: معدلات الوفورات أو سرعة التحقق متفائلة."})
        if mtr == "csat_pct" and below:
            diagnostics.append({"metric": mtr, "parameter": "csat_delay_sensitivity", "direction": "higher",
                                "en": "CSAT fell below the P10 band: customer sensitivity to delay is under-estimated.",
                                "ar": "انخفض رضا العملاء تحت نطاق P10: حساسية العملاء للتأخير مقدرة بأقل من الواقع."})
    all_cov = float(np.mean([c.within_interval for c in comps])) if comps else None
    return {"metrics": metrics, "overall_interval_coverage": round(all_cov, 3) if all_cov is not None else None,
            "nominal_coverage": 0.8, "diagnostics": diagnostics,
            "calibrated": all_cov is not None and all_cov >= 0.6,
            "note_en": "Coverage compares how often actuals fall inside the P10–P90 band (nominal 80%).",
            "note_ar": "التغطية تقيس مدى وقوع القيم الفعلية داخل نطاق P10–P90 (الاسمي 80%)."}


def synthetic_actuals(db: Session, decision: Decision, months: int = 3, user_id: str | None = None) -> int:
    """Demo helper: create LABELLED synthetic actuals that deliberately deviate from the forecast."""
    key, sim = tracked_scenario(db, decision)
    res = db.scalar(select(SimulationResult).where(SimulationResult.simulation_run_id == sim.id,
                                                   SimulationResult.scenario_key == key))
    t = res.data["trajectory"]
    rng = np.random.default_rng(7)
    n = 0
    for mth in range(1, months + 1):
        vals = {
            "savings_run_rate": t["savings_run_rate"]["expected"][mth] * 0.82,
            "opex_monthly": t["opex_monthly"]["expected"][mth] * 1.015,
            "delay_pct": t["delay_pct"]["p90"][mth] + 0.4 + 0.2 * mth,
            "csat_pct": t["csat_pct"]["expected"][mth] - 0.3 + rng.normal(0, 0.1),
            "utilization_pct": t["utilization_pct"]["expected"][mth] + 1.5,
        }
        for mtr, v in vals.items():
            ex = db.scalar(select(ActualOutcome).where(ActualOutcome.decision_id == decision.id,
                                                       ActualOutcome.month == mth, ActualOutcome.metric == mtr))
            if ex:
                ex.value, ex.is_synthetic = round(float(v), 4), True
            else:
                db.add(ActualOutcome(decision_id=decision.id, month=mth, metric=mtr, value=round(float(v), 4),
                                     source="synthetic_demo", is_synthetic=True, recorded_by=user_id))
            n += 1
    db.commit()
    return n


def propose_calibration(db: Session, decision: Decision, summary: dict[str, Any]) -> SimulationModel | None:
    prod = db.scalar(select(SimulationModel).where(SimulationModel.status == "production")
                     .order_by(SimulationModel.created_at.desc()))
    if not summary["diagnostics"]:
        return None
    params = [dict(p) for p in prod.parameters]
    changes = []
    for d in summary["diagnostics"]:
        for p in params:
            if p["key"] == d["parameter"]:
                dist = dict(p["dist"])
                span = dist["high"] - dist["low"]
                shift = -0.15 * span if d["direction"] == "lower" else 0.15 * span
                new_mode = min(max(dist["mode"] + shift, dist["low"]), dist["high"])
                changes.append({"parameter": p["key"], "old_mode": dist["mode"], "new_mode": round(new_mode, 4)})
                dist["mode"] = round(new_mode, 4)
                p["dist"] = dist
                p["calibration"] = (f"Mode shifted from {changes[-1]['old_mode']} to {changes[-1]['new_mode']} based on "
                                    f"{summary['metrics'].get(d['metric'], {}).get('n', 0)} observed months "
                                    f"(decision {decision.id[:8]}). Candidate pending approval.")
    major, minor, patch = (int(x) for x in prod.version.split("."))
    cand = SimulationModel(key=prod.key, version=f"{major}.{minor}.{patch + 1}-cand", status="candidate",
                           description=f"Calibration candidate from observed outcomes. Changes: {changes}",
                           parameters=params, economics=prod.economics)
    db.add(cand)
    db.commit()
    return cand
