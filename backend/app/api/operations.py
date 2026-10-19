"""Automation, Reality Feedback Loop, model governance and report exports."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..automation.n8n import trigger_workflow
from ..config import get_settings
from ..db import get_db
from ..models import (
    ActualOutcome,
    AutomationRun,
    AutomationWorkflow,
    ForecastComparison,
    SimulationModel,
    User,
)
from ..security import require
from ..services.audit import audit
from ..services.dossier import build_dossier, get_decision, latest_run, row
from ..services.feedback import METRICS, METRICS_COLLECTIONS, calibration_summary, propose_calibration, recompute, synthetic_actuals
from ..services.reports import build_excel, build_pdf

router = APIRouter(tags=["operations"])
DB = Annotated[Session, Depends(get_db)]


# ------------------------------------------------------------------ automation
@router.get("/automation/workflows")
def workflows(db: DB, user: Annotated[User, require("automation.read")]) -> dict[str, Any]:
    s = get_settings()
    wfs = db.scalars(select(AutomationWorkflow).where(AutomationWorkflow.tenant_id == user.tenant_id)
                     .order_by(AutomationWorkflow.consequential, AutomationWorkflow.key)).all()
    return {"n8n_configured": bool(s.n8n_base_url), "external_actions_enabled": s.external_actions_enabled,
            "workflows": [row(w) for w in wfs]}


class TriggerIn(BaseModel):
    dry_run: bool = True
    decision_id: str | None = None
    payload: dict[str, Any] = {}


@router.post("/automation/workflows/{wid}/trigger")
def trigger(wid: str, body: TriggerIn, db: DB, user: Annotated[User, require("automation.run")]) -> dict[str, Any]:
    wf = db.get(AutomationWorkflow, wid)
    if not wf or wf.tenant_id != user.tenant_id:
        raise HTTPException(404)
    decision = get_decision(db, body.decision_id, user) if body.decision_id else None
    run = trigger_workflow(db, wf, payload={"workflow": wf.key, "decision_id": body.decision_id, **body.payload},
                           dry_run=body.dry_run, user_id=user.id, decision=decision)
    return row(run)


@router.get("/automation/runs")
def automation_runs(db: DB, user: Annotated[User, require("automation.read")]) -> list[dict[str, Any]]:
    q = (select(AutomationRun, AutomationWorkflow.key).join(AutomationWorkflow)
         .where(AutomationWorkflow.tenant_id == user.tenant_id).order_by(AutomationRun.created_at.desc()).limit(100))
    return [{**row(r), "workflow_key": k} for r, k in db.execute(q)]


# ------------------------------------------------------------------ reality feedback loop
class OutcomeIn(BaseModel):
    month: int = Field(ge=1, le=36)
    metric: str
    value: float


@router.get("/decisions/{decision_id}/outcomes")
def outcomes(decision_id: str, db: DB, user: Annotated[User, require("decision.read")]) -> dict[str, Any]:
    d = get_decision(db, decision_id, user)
    acts = db.scalars(select(ActualOutcome).where(ActualOutcome.decision_id == d.id)
                      .order_by(ActualOutcome.month, ActualOutcome.metric)).all()
    comps = db.scalars(select(ForecastComparison).where(ForecastComparison.decision_id == d.id)
                       .order_by(ForecastComparison.month)).all()
    names = METRICS_COLLECTIONS if (d.controls or {}).get("domain") == "collections" else METRICS
    return {"metrics": {k: {"en": v[0], "ar": v[1]} for k, v in names.items()},
            "actuals": [row(a) for a in acts], "comparisons": [row(c) for c in comps],
            "calibration": calibration_summary(list(comps)),
            "scenario_key": comps[0].scenario_key if comps else None}


@router.post("/decisions/{decision_id}/outcomes", status_code=201)
def record_outcomes(decision_id: str, body: list[OutcomeIn], db: DB,
                    user: Annotated[User, require("outcome.record")]) -> dict[str, Any]:
    d = get_decision(db, decision_id, user)
    for o in body:
        if o.metric not in METRICS:
            raise HTTPException(422, f"Unknown metric {o.metric}")
        ex = db.scalar(select(ActualOutcome).where(ActualOutcome.decision_id == d.id, ActualOutcome.month == o.month,
                                                   ActualOutcome.metric == o.metric))
        if ex:
            ex.value, ex.is_synthetic, ex.source = o.value, False, "manual"
        else:
            db.add(ActualOutcome(decision_id=d.id, month=o.month, metric=o.metric, value=o.value, recorded_by=user.id))
    db.commit()
    recompute(db, d)
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="outcomes.recorded",
          entity_type="decision", entity_id=d.id, detail={"count": len(body)})
    return outcomes(decision_id, db, user)


@router.post("/decisions/{decision_id}/outcomes/synthetic-demo", status_code=201)
def demo_outcomes(decision_id: str, db: DB, user: Annotated[User, require("outcome.record")]) -> dict[str, Any]:
    d = get_decision(db, decision_id, user)
    n = synthetic_actuals(db, d, months=3, user_id=user.id)
    recompute(db, d)
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="outcomes.synthetic_generated",
          entity_type="decision", entity_id=d.id, detail={"count": n, "synthetic": True})
    return outcomes(decision_id, db, user)


@router.post("/decisions/{decision_id}/calibration-proposal", status_code=201)
def calibration_proposal(decision_id: str, db: DB, user: Annotated[User, require("outcome.record")]) -> dict[str, Any]:
    d = get_decision(db, decision_id, user)
    comps = db.scalars(select(ForecastComparison).where(ForecastComparison.decision_id == d.id)).all()
    summary = calibration_summary(list(comps))
    cand = propose_calibration(db, d, summary)
    if not cand:
        return {"created": False, "reason": "No calibration diagnostics triggered"}
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="model.candidate_created",
          entity_type="simulation_model", entity_id=cand.id, detail={"version": cand.version})
    return {"created": True, "candidate": row(cand), "status": "candidate — requires approval to promote"}


class PromoteIn(BaseModel):
    justification: str = Field(min_length=10, max_length=2000)


@router.post("/models/{model_id}/promote")
def promote(model_id: str, body: PromoteIn, db: DB, user: Annotated[User, require("governance.manage")]) -> dict[str, Any]:
    cand = db.get(SimulationModel, model_id)
    if not cand or cand.status != "candidate":
        raise HTTPException(404, "Candidate model not found")
    for m in db.scalars(select(SimulationModel).where(SimulationModel.key == cand.key, SimulationModel.status == "production")):
        m.status = "retired"
    cand.status = "production"
    cand.version = cand.version.replace("-cand", "")
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="model.promoted",
          entity_type="simulation_model", entity_id=cand.id, detail={"version": cand.version,
                                                                     "justification": body.justification})
    return row(cand)


# ------------------------------------------------------------------ reports
@router.get("/decisions/{decision_id}/report.{fmt}")
def report(decision_id: str, fmt: str, db: DB, user: Annotated[User, require("report.export")],
           lang: str = "en") -> Response:
    if fmt not in ("pdf", "xlsx") or lang not in ("en", "ar"):
        raise HTTPException(400, "Format must be pdf|xlsx and lang en|ar")
    d = get_decision(db, decision_id, user)
    run = latest_run(db, d.id)
    if not run:
        raise HTTPException(409, "No completed analysis to report on")
    dossier = build_dossier(db, d, run)
    comps = [row(c) for c in db.scalars(select(ForecastComparison).where(ForecastComparison.decision_id == d.id))]
    if fmt == "pdf":
        data, mt = build_pdf(dossier, lang, comps), "application/pdf"
    else:
        data, mt = build_excel(dossier, lang, comps), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="report.exported",
          entity_type="decision", entity_id=d.id, detail={"format": fmt, "lang": lang})
    return Response(data, media_type=mt,
                    headers={"Content-Disposition": f'attachment; filename="future-mirror-{d.id[:8]}-{lang}.{fmt}"'})
