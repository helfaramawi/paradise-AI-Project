from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import (
    AgentDefinition,
    ApprovalRequest,
    AuditEvent,
    Decision,
    DecisionRun,
    Role,
    Tenant,
    User,
)
from ..security import CurrentUser, hash_password, require
from ..services.audit import audit, verify_chain
from ..services.dossier import latest_run, row

router = APIRouter(tags=["admin"])
DB = Annotated[Session, Depends(get_db)]


@router.get("/platform/status")
def platform_status(db: DB, user: CurrentUser) -> dict[str, Any]:
    s = get_settings()
    t = db.get(Tenant, user.tenant_id)
    return {
        "tenant": {"id": t.id, "name": t.name, "slug": t.slug},
        "llm": {"provider": s.llm_provider, "mode": "rule_based" if s.llm_provider == "none" else "llm_augmented",
                "model": s.llm_model},
        "external_actions_enabled": s.external_actions_enabled,
        "emergency_stop": bool((t.settings or {}).get("emergency_stop")),
        "n8n_configured": bool(s.n8n_base_url),
        "presentation_pacing_ms": s.presentation_pacing_ms,
        "environment": s.environment,
        "database": s.database_url.split(":")[0],
    }


@router.get("/dashboard")
def dashboard(db: DB, user: Annotated[User, require("decision.read")]) -> dict[str, Any]:
    tid = user.tenant_id
    counts = dict(db.execute(select(Decision.status, func.count()).where(Decision.tenant_id == tid)
                             .group_by(Decision.status)).all())
    pending = db.scalar(select(func.count()).select_from(ApprovalRequest)
                        .where(ApprovalRequest.tenant_id == tid, ApprovalRequest.status == "pending"))
    latest = db.scalar(select(Decision).where(Decision.tenant_id == tid, Decision.status.in_(
        ["analyzed", "pending_approval", "approved", "rejected", "needs_analysis"])).order_by(Decision.updated_at.desc()))
    latest_summary = None
    if latest:
        run = latest_run(db, latest.id)
        if run and run.result:
            rec = run.result.get("recommendation", {})
            latest_summary = {"decision_id": latest.id, "title": latest.title, "status": latest.status,
                              "run_id": run.id, "recommended_strategy": rec.get("recommended_strategy"),
                              "headline_en": rec.get("headline_en"), "headline_ar": rec.get("headline_ar"),
                              "per_future": rec.get("per_future"), "finished_at": run.finished_at}
    runs = db.scalar(select(func.count()).select_from(DecisionRun).join(Decision).where(Decision.tenant_id == tid))
    recent = db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == tid).order_by(AuditEvent.id.desc()).limit(8)).all()
    return {"decision_counts": counts, "pending_approvals": pending, "total_runs": runs,
            "latest": latest_summary, "recent_activity": [row(a, exclude=("prev_hash", "hash")) for a in recent]}


@router.get("/agents")
def agents(db: DB, user: CurrentUser) -> list[dict[str, Any]]:
    return [row(a) for a in db.scalars(select(AgentDefinition))]


@router.get("/admin/users")
def users(db: DB, user: Annotated[User, require("admin.users")]) -> list[dict[str, Any]]:
    out = []
    for u in db.scalars(select(User).where(User.tenant_id == user.tenant_id).order_by(User.email)):
        out.append({**row(u, exclude=("password_hash",)), "roles": [r.key for r in u.roles]})
    return out


class UserIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str
    title: str = ""
    password: str = Field(min_length=10)
    roles: list[str]


@router.post("/admin/users", status_code=201)
def create_user(body: UserIn, db: DB, user: Annotated[User, require("admin.users")]) -> dict[str, Any]:
    if db.scalar(select(User).where(User.tenant_id == user.tenant_id, User.email == body.email.lower())):
        raise HTTPException(409, "User exists")
    roles = db.scalars(select(Role).where(Role.tenant_id == user.tenant_id, Role.key.in_(body.roles))).all()
    if len(roles) != len(set(body.roles)):
        raise HTTPException(422, "Unknown role")
    u = User(tenant_id=user.tenant_id, email=body.email.lower(), full_name=body.full_name, title=body.title,
             password_hash=hash_password(body.password))
    u.roles = list(roles)
    db.add(u)
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="admin.user_created",
          entity_type="user", entity_id=u.id, detail={"email": u.email, "roles": body.roles})
    return {**row(u, exclude=("password_hash",)), "roles": body.roles}


class ActiveIn(BaseModel):
    is_active: bool


@router.patch("/admin/users/{uid}")
def set_active(uid: str, body: ActiveIn, db: DB, user: Annotated[User, require("admin.users")]) -> dict[str, Any]:
    u = db.get(User, uid)
    if not u or u.tenant_id != user.tenant_id:
        raise HTTPException(404)
    if u.id == user.id:
        raise HTTPException(409, "Cannot deactivate yourself")
    u.is_active = body.is_active
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="admin.user_active_changed",
          entity_type="user", entity_id=u.id, detail={"is_active": body.is_active})
    return {**row(u, exclude=("password_hash",)), "roles": [r.key for r in u.roles]}


@router.get("/admin/roles")
def roles(db: DB, user: Annotated[User, require("admin.users")]) -> list[dict[str, Any]]:
    return [{**row(r), "permissions": [p.key for p in r.permissions]}
            for r in db.scalars(select(Role).where(Role.tenant_id == user.tenant_id))]


@router.get("/admin/audit")
def audit_log(db: DB, user: Annotated[User, require("admin.audit")], limit: int = 200) -> dict[str, Any]:
    rows = db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == user.tenant_id)
                      .order_by(AuditEvent.id.desc()).limit(min(limit, 1000))).all()
    return {"events": [row(e) for e in rows], "chain": verify_chain(db)}


class StopIn(BaseModel):
    active: bool
    reason: str = Field("", max_length=500)


@router.post("/admin/emergency-stop")
def emergency_stop(body: StopIn, db: DB, user: Annotated[User, require("admin.emergency_stop")]) -> dict[str, Any]:
    t = db.get(Tenant, user.tenant_id)
    t.settings = {**(t.settings or {}), "emergency_stop": body.active}
    cancelled = 0
    if body.active:
        for r in db.scalars(select(DecisionRun).join(Decision).where(Decision.tenant_id == t.id,
                                                                    DecisionRun.status.in_(["queued", "running"]))):
            r.cancel_requested = True
            cancelled += 1
    db.commit()
    audit(db, tenant_id=t.id, actor_type="user", actor_id=user.id,
          action="platform.emergency_stop_on" if body.active else "platform.emergency_stop_off",
          entity_type="tenant", entity_id=t.id, detail={"reason": body.reason, "runs_cancelled": cancelled})
    return {"emergency_stop": body.active, "runs_cancelled": cancelled}
