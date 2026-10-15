from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..automation.n8n import trigger_workflow
from ..db import get_db
from ..governance.engine import evaluate_policies
from ..governance.service import evaluate_strategy, load_policies
from ..models import (
    ApprovalDecision,
    ApprovalRequest,
    AutomationWorkflow,
    DecisionCollision,
    GovernancePolicy,
    SimulationResult,
    SimulationRun,
    User,
)
from ..security import CurrentUser, require, user_role_keys
from ..services.audit import audit
from ..services.dossier import approval_dict, get_decision, latest_run, row

router = APIRouter(tags=["governance"])
DB = Annotated[Session, Depends(get_db)]


@router.get("/governance/policies")
def policies(db: DB, user: Annotated[User, require("governance.read")]) -> list[dict[str, Any]]:
    return [row(p) for p in db.scalars(select(GovernancePolicy).where(GovernancePolicy.tenant_id == user.tenant_id)
                                       .order_by(GovernancePolicy.code))]


class PolicyPatch(BaseModel):
    enabled: bool | None = None
    rule: dict[str, Any] | None = None


@router.patch("/governance/policies/{pid}")
def patch_policy(pid: str, body: PolicyPatch, db: DB, user: Annotated[User, require("governance.manage")]) -> dict[str, Any]:
    p = db.get(GovernancePolicy, pid)
    if not p or p.tenant_id != user.tenant_id:
        raise HTTPException(404)
    if p.locked:
        raise HTTPException(403, "This policy is locked (non-negotiable) and cannot be modified")
    if body.rule is not None:
        try:
            evaluate_policies([{"code": p.code, "effect": p.effect, "rule": body.rule}], {})
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(422, f"Invalid rule: {exc}") from exc
        p.rule = body.rule
    if body.enabled is not None:
        p.enabled = body.enabled
    p.version += 1
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="policy.updated",
          entity_type="governance_policy", entity_id=p.id, detail={"code": p.code, "version": p.version,
                                                                   "enabled": p.enabled})
    return row(p)


class EvalIn(BaseModel):
    context: dict[str, Any]


@router.post("/governance/evaluate")
def evaluate(body: EvalIn, db: DB, user: Annotated[User, require("governance.read")]) -> dict[str, Any]:
    """Policy sandbox: evaluate an arbitrary input document against the tenant's policies."""
    return evaluate_policies(load_policies(db, user.tenant_id), body.context)


# ------------------------------------------------------------------ approvals
class ApprovalIn(BaseModel):
    scenario_key: str = Field(pattern="^[ABC]$")
    justification: str = Field("", max_length=2000)
    acknowledged: list[str] = []


def _gov_for(db: Session, decision, key: str) -> tuple[dict[str, Any], Any]:  # noqa: ANN001
    run = latest_run(db, decision.id)
    if not run:
        raise HTTPException(409, "Run an analysis before requesting approval")
    sim = db.scalar(select(SimulationRun).where(SimulationRun.run_id == run.id))
    res = db.scalar(select(SimulationResult).where(SimulationResult.simulation_run_id == sim.id,
                                                   SimulationResult.scenario_key == key))
    cols = [row(c) for c in db.scalars(select(DecisionCollision).where(DecisionCollision.run_id == run.id))]
    has_err = bool((run.result or {}).get("validation", {}).get("has_errors"))
    g = evaluate_strategy(load_policies(db, decision.tenant_id), future=res.data, controls=decision.controls,
                          collisions=cols, dataset_has_errors=has_err)
    return g, run


@router.post("/decisions/{decision_id}/approval-requests", status_code=201)
def request_approval(decision_id: str, body: ApprovalIn, db: DB,
                     user: Annotated[User, require("approval.request")]) -> dict[str, Any]:
    d = get_decision(db, decision_id, user)
    pending = db.scalar(select(ApprovalRequest).where(ApprovalRequest.decision_id == d.id,
                                                      ApprovalRequest.status == "pending"))
    if pending:
        raise HTTPException(409, "An approval request is already pending for this decision")
    g, run = _gov_for(db, d, body.scenario_key)
    missing_ack = [c for c in g["acknowledgements"] if c not in body.acknowledged]
    if missing_ack:
        raise HTTPException(422, {"message": "Acknowledgement required", "policies": missing_ack})
    status = "blocked" if g["outcome"] == "denied" else "pending"
    req = ApprovalRequest(tenant_id=user.tenant_id, decision_id=d.id, run_id=run.id, scenario_key=body.scenario_key,
                          status=status, required_roles=g["required_roles"], justification=body.justification,
                          governance_snapshot={k: g[k] for k in ("outcome", "required_roles", "acknowledgements",
                                                                 "policy_results", "deny_reasons")},
                          requested_by=user.id)
    db.add(req)
    if status == "pending":
        d.status = "pending_approval"
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action=f"approval.{status}",
          entity_type="approval_request", entity_id=req.id,
          detail={"scenario": body.scenario_key, "roles": g["required_roles"],
                  "deny": [x["code"] for x in g["deny_reasons"]]})
    if status == "pending":
        wf = db.scalar(select(AutomationWorkflow).where(AutomationWorkflow.tenant_id == user.tenant_id,
                                                        AutomationWorkflow.key == "review_notification"))
        if wf:
            trigger_workflow(db, wf, payload={"approval_request_id": req.id, "roles": g["required_roles"],
                                              "decision": d.title}, dry_run=True, user_id=user.id, decision=d)
    return approval_dict(db, req)


@router.get("/approvals")
def list_approvals(db: DB, user: Annotated[User, require("decision.read")], status: str | None = None) -> list[dict[str, Any]]:
    q = select(ApprovalRequest).where(ApprovalRequest.tenant_id == user.tenant_id)
    if status:
        q = q.where(ApprovalRequest.status == status)
    return [approval_dict(db, a) for a in db.scalars(q.order_by(ApprovalRequest.created_at.desc()))]


class VerdictIn(BaseModel):
    verdict: str = Field(pattern="^(approve|reject|request_analysis)$")
    role_key: str
    comment: str = Field("", max_length=2000)


@router.post("/approvals/{rid}/decide")
def decide(rid: str, body: VerdictIn, db: DB, user: Annotated[User, require("approval.decide")]) -> dict[str, Any]:
    req = db.get(ApprovalRequest, rid)
    if not req or req.tenant_id != user.tenant_id:
        raise HTTPException(404)
    if req.status != "pending":
        raise HTTPException(409, f"Request is {req.status}")
    if body.role_key not in user_role_keys(user):
        raise HTTPException(403, "You do not hold the role you are approving for")
    # GOV-013 separation of duties
    if req.requested_by == user.id:
        raise HTTPException(403, "Separation of duties (GOV-013): the requester cannot approve their own request")
    if any(x.approver_id == user.id for x in req.decisions):
        raise HTTPException(403, "Separation of duties (GOV-013): one approver cannot satisfy multiple roles")
    if body.verdict == "approve" and body.role_key not in req.required_roles:
        raise HTTPException(422, "This role is not required for this request")
    if any(x.role_key == body.role_key and x.verdict == "approve" for x in req.decisions):
        raise HTTPException(409, "This role has already approved")
    db.add(ApprovalDecision(request_id=req.id, approver_id=user.id, role_key=body.role_key, verdict=body.verdict,
                            comment=body.comment))
    db.flush()
    db.refresh(req)
    d = get_decision(db, req.decision_id, user)
    if body.verdict == "reject":
        req.status, d.status = "rejected", "rejected"
    elif body.verdict == "request_analysis":
        req.status, d.status = "needs_analysis", "needs_analysis"
    else:
        approved = {x.role_key for x in req.decisions if x.verdict == "approve"}
        if set(req.required_roles) <= approved:
            # Re-check governance at final approval time (state may have changed).
            g, _ = _gov_for(db, d, req.scenario_key)
            if g["outcome"] == "denied":
                req.status = "blocked"
            else:
                req.status, d.status = "approved", "approved"
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action=f"approval.verdict.{body.verdict}",
          entity_type="approval_request", entity_id=req.id, detail={"role": body.role_key, "status": req.status})
    return approval_dict(db, req)


@router.get("/me/approval-inbox")
def inbox(db: DB, user: CurrentUser) -> list[dict[str, Any]]:
    roles = user_role_keys(user)
    out = []
    for a in db.scalars(select(ApprovalRequest).where(ApprovalRequest.tenant_id == user.tenant_id,
                                                      ApprovalRequest.status == "pending")):
        d = approval_dict(db, a)
        if set(d["pending_roles"]) & roles and a.requested_by != user.id:
            out.append(d)
    return out
