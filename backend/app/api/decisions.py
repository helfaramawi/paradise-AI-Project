from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agents.intake import objectives_and_constraints, parse_decision, sanitize
from ..db import SessionLocal, get_db
from ..models import (
    Decision,
    DecisionConstraint,
    DecisionObjective,
    DecisionRun,
    DatasetVersion,
    EnterpriseDataset,
    User,
    WorkflowEvent,
)
from ..security import CurrentUser, require
from ..services.audit import audit
from ..services.dossier import build_dossier, decision_dict, get_decision, latest_run, row
from ..services.pipeline import start_run
from ..simulation.assumptions import DecisionControls

router = APIRouter(tags=["decisions"])
DB = Annotated[Session, Depends(get_db)]

DEMO_QUESTION = (
    "Our company has annual operating expenses of EGP 120 million. We want to reduce operating costs by 20% "
    "within six months without terminating employees or negatively affecting project delivery, contractual "
    "obligations, or customer satisfaction. What are our realistic options?"
)


class ParseIn(BaseModel):
    question: str = Field(min_length=10, max_length=4000)


class DecisionIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    question: str = Field(min_length=10, max_length=4000)
    language: str = "en"
    dataset_version_id: str | None = None
    controls: DecisionControls = DecisionControls()
    seed: int = 20260101
    iterations: int = Field(2000, ge=200, le=20000)
    auto_run: bool = False


class RunIn(BaseModel):
    pacing_ms: int | None = Field(None, ge=0, le=3000)


@router.post("/decisions/parse")
def parse(body: ParseIn, user: Annotated[User, require("decision.create")]) -> dict[str, Any]:
    p = parse_decision(body.question)
    c = DecisionControls()
    controls = c.model_copy(update={k: p[k] for k in ("cost_reduction_target_pct", "implementation_months") if k in p})
    if p.get("no_terminations") is not None:
        controls = controls.model_copy(update={"no_terminations": bool(p.get("no_terminations"))})
    return {"parsed": p, "suggested_controls": controls.model_dump(),
            "supported": p["category"] == "opex_optimization",
            "note_en": "Interpretation produced by a deterministic intake parser. Please confirm every field.",
            "note_ar": "التفسير ناتج عن محلل إدخال قائم على القواعد. يرجى تأكيد كل حقل."}


@router.get("/decisions/demo-question")
def demo_question(user: CurrentUser) -> dict[str, str]:
    return {"question_en": DEMO_QUESTION,
            "question_ar": "تبلغ المصروفات التشغيلية السنوية لشركتنا 120 مليون جنيه. نريد خفض التكاليف التشغيلية بنسبة 20% "
                           "خلال ستة أشهر دون إنهاء خدمة الموظفين أو التأثير سلباً على تسليم المشروعات أو الالتزامات "
                           "التعاقدية أو رضا العملاء. ما هي خياراتنا الواقعية؟"}


@router.get("/decisions")
def list_decisions(db: DB, user: Annotated[User, require("decision.read")]) -> list[dict[str, Any]]:
    rows = db.scalars(select(Decision).where(Decision.tenant_id == user.tenant_id)
                      .order_by(Decision.created_at.desc())).all()
    out = []
    for d in rows:
        lr = latest_run(db, d.id, completed_only=False)
        out.append({**row(d, exclude=("intake",)), "latest_run": row(lr, exclude=("result",)) if lr else None,
                    "run_count": db.scalar(select(func.count()).select_from(DecisionRun).where(DecisionRun.decision_id == d.id))})
    return out


@router.post("/decisions", status_code=201)
def create_decision(body: DecisionIn, db: DB, user: Annotated[User, require("decision.create")]) -> dict[str, Any]:
    if body.dataset_version_id:
        dv = db.get(DatasetVersion, body.dataset_version_id)
        if not dv or db.get(EnterpriseDataset, dv.dataset_id).tenant_id != user.tenant_id:
            raise HTTPException(404, "Dataset version not found")
    else:
        dv = db.scalar(select(DatasetVersion).join(EnterpriseDataset)
                       .where(EnterpriseDataset.tenant_id == user.tenant_id)
                       .order_by(DatasetVersion.created_at.desc()).limit(1))
        if not dv:
            raise HTTPException(400, "No dataset available")
    question = sanitize(body.question)
    controls = {**body.controls.model_dump(), "seed": body.seed, "iterations": body.iterations}
    d = Decision(tenant_id=user.tenant_id, title=sanitize(body.title), question=question, language=body.language,
                 controls=controls, intake=parse_decision(question), dataset_version_id=dv.id, created_by=user.id)
    objs, cons = objectives_and_constraints(controls, dv.data)
    d.objectives = [DecisionObjective(**o) for o in objs]
    d.constraints = [DecisionConstraint(**c) for c in cons if c["key"] != "no_terminations" or controls["no_terminations"]]
    db.add(d)
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="decision.created",
          entity_type="decision", entity_id=d.id, detail={"title": d.title, "dataset_version": dv.id})
    out = decision_dict(d)
    if body.auto_run:
        run = start_run(db, d, user.id)
        out["run_id"] = run.id
    return out


@router.get("/decisions/{decision_id}")
def get_one(decision_id: str, db: DB, user: Annotated[User, require("decision.read")]) -> dict[str, Any]:
    d = get_decision(db, decision_id, user)
    runs = db.scalars(select(DecisionRun).where(DecisionRun.decision_id == d.id).order_by(DecisionRun.created_at.desc())).all()
    return {**decision_dict(d), "runs": [row(r, exclude=("result",)) for r in runs]}


@router.patch("/decisions/{decision_id}/controls")
def update_controls(decision_id: str, body: DecisionControls, db: DB,
                    user: Annotated[User, require("decision.create")]) -> dict[str, Any]:
    d = get_decision(db, decision_id, user)
    if d.status in ("approved", "pending_approval"):
        raise HTTPException(409, "Controls are frozen once a strategy is submitted for approval")
    d.controls = {**d.controls, **body.model_dump()}
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="decision.controls_updated",
          entity_type="decision", entity_id=d.id, detail=body.model_dump())
    return decision_dict(d)


@router.post("/decisions/{decision_id}/runs", status_code=202)
def run_decision(decision_id: str, body: RunIn, db: DB, user: Annotated[User, require("decision.run")]) -> dict[str, Any]:
    d = get_decision(db, decision_id, user)
    active = db.scalar(select(DecisionRun).where(DecisionRun.decision_id == d.id,
                                                 DecisionRun.status.in_(["queued", "running"])))
    if active:
        raise HTTPException(409, "An analysis is already running for this decision")
    from ..models import Tenant
    if (db.get(Tenant, user.tenant_id).settings or {}).get("emergency_stop"):
        raise HTTPException(423, "Platform emergency stop is active")
    run = start_run(db, d, user.id, pacing_ms=body.pacing_ms)
    return {"run_id": run.id, "status": run.status}


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, db: DB, user: Annotated[User, require("decision.cancel")]) -> dict[str, Any]:
    run = db.get(DecisionRun, run_id)
    if not run:
        raise HTTPException(404)
    get_decision(db, run.decision_id, user)
    run.cancel_requested = True
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="run.cancel_requested",
          entity_type="decision_run", entity_id=run.id)
    return {"run_id": run.id, "cancel_requested": True}


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: DB, user: Annotated[User, require("decision.read")]) -> dict[str, Any]:
    run = db.get(DecisionRun, run_id)
    if not run:
        raise HTTPException(404)
    get_decision(db, run.decision_id, user)
    events = db.scalars(select(WorkflowEvent).where(WorkflowEvent.run_id == run.id).order_by(WorkflowEvent.id)).all()
    return {**row(run, exclude=("result",)), "events": [row(e) for e in events]}


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: str, request: Request, user: Annotated[User, require("decision.read")],
                        after: int = 0) -> StreamingResponse:
    """Server-Sent Events stream of persisted workflow events (replays history, then follows live)."""
    with SessionLocal() as db:
        run = db.get(DecisionRun, run_id)
        if not run:
            raise HTTPException(404)
        get_decision(db, run.decision_id, user)

    async def gen():
        last = after
        idle_after_done = 0
        while True:
            if await request.is_disconnected():
                break
            def fetch():
                with SessionLocal() as db:
                    evs = db.scalars(select(WorkflowEvent).where(WorkflowEvent.run_id == run_id, WorkflowEvent.id > last)
                                     .order_by(WorkflowEvent.id).limit(200)).all()
                    r = db.get(DecisionRun, run_id)
                    return [row(e) for e in evs], r.status
            evs, status = await asyncio.to_thread(fetch)
            for e in evs:
                last = e["id"]
                e["ts"] = e["ts"].isoformat()
                yield f"id: {e['id']}\nevent: workflow\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
            if status in ("completed", "failed", "cancelled") and not evs:
                idle_after_done += 1
                if idle_after_done > 2:
                    yield f"event: end\ndata: {json.dumps({'status': status})}\n\n"
                    break
            else:
                yield ": keep-alive\n\n" if not evs else ""
            await asyncio.sleep(0.25)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/decisions/{decision_id}/dossier")
def dossier(decision_id: str, db: DB, user: Annotated[User, require("decision.read")],
            run_id: str | None = None) -> dict[str, Any]:
    d = get_decision(db, decision_id, user)
    if run_id:
        run = db.get(DecisionRun, run_id)
        if not run or run.decision_id != d.id:
            raise HTTPException(404, "Run not found")
    else:
        run = latest_run(db, d.id)
    return build_dossier(db, d, run)
