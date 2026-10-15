"""Assembles the complete decision dossier for a run from persisted records."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AgentDefinition,
    AgentExecution,
    AgentFinding,
    AgentObjection,
    ApprovalRequest,
    Decision,
    DecisionCollision,
    DecisionRun,
    DatasetVersion,
    EnterpriseDataset,
    GovernanceEvaluation,
    RiskAssessment,
    SimulationModel,
    SimulationRun,
    User,
)


def get_decision(db: Session, decision_id: str, user: User) -> Decision:
    d = db.get(Decision, decision_id)
    if not d or d.tenant_id != user.tenant_id:
        raise HTTPException(404, "Decision not found")
    return d


def latest_run(db: Session, decision_id: str, completed_only: bool = True) -> DecisionRun | None:
    q = select(DecisionRun).where(DecisionRun.decision_id == decision_id)
    if completed_only:
        q = q.where(DecisionRun.status == "completed")
    return db.scalar(q.order_by(DecisionRun.created_at.desc()).limit(1))


def row(o: Any, exclude: tuple[str, ...] = ()) -> dict[str, Any]:
    return {c.name: getattr(o, c.name) for c in o.__table__.columns if c.name not in exclude}


def decision_dict(d: Decision) -> dict[str, Any]:
    out = row(d)
    out["objectives"] = [row(o) for o in d.objectives]
    out["constraints"] = [row(c) for c in d.constraints]
    return out


def build_dossier(db: Session, decision: Decision, run: DecisionRun | None) -> dict[str, Any]:
    dv = db.get(DatasetVersion, decision.dataset_version_id)
    ds = db.get(EnterpriseDataset, dv.dataset_id)
    out: dict[str, Any] = {
        "decision": decision_dict(decision),
        "dataset": {"id": ds.id, "name": ds.name, "is_synthetic": ds.is_synthetic, "source": ds.source,
                    "version": dv.version, "version_id": dv.id, "checksum": dv.checksum, "data": dv.data,
                    "provenance": dv.provenance, "validation": dv.validation},
        "run": None,
    }
    approvals = db.scalars(select(ApprovalRequest).where(ApprovalRequest.decision_id == decision.id)
                           .order_by(ApprovalRequest.created_at.desc())).all()
    out["approvals"] = [approval_dict(db, a) for a in approvals]
    if not run:
        return out
    agents = {a.key: row(a) for a in db.scalars(select(AgentDefinition))}
    sim_run = db.scalar(select(SimulationRun).where(SimulationRun.run_id == run.id))
    model = db.get(SimulationModel, sim_run.model_id) if sim_run else None
    findings = db.scalars(select(AgentFinding).where(AgentFinding.run_id == run.id).order_by(AgentFinding.seq)).all()
    out.update({
        "run": row(run),
        "agents": agents,
        "executions": [row(e) for e in db.scalars(select(AgentExecution).where(AgentExecution.run_id == run.id)
                                                    .order_by(AgentExecution.started_at))],
        "findings": [{**row(f), "evidence": [row(e) for e in f.evidence]} for f in findings],
        "objections": [row(o) for o in db.scalars(select(AgentObjection).where(AgentObjection.run_id == run.id)
                                                    .order_by(AgentObjection.seq))],
        "collisions": [row(c) for c in db.scalars(select(DecisionCollision).where(DecisionCollision.run_id == run.id)
                                                    .order_by(DecisionCollision.severity_score.desc()))],
        "risks": [row(r) for r in db.scalars(select(RiskAssessment).where(RiskAssessment.run_id == run.id))],
        "governance": [row(g) for g in db.scalars(select(GovernanceEvaluation).where(GovernanceEvaluation.run_id == run.id))],
        "simulation": None,
    })
    if sim_run:
        out["simulation"] = {
            "id": sim_run.id, "seed": sim_run.seed, "iterations": sim_run.iterations,
            "input_fingerprint": sim_run.input_fingerprint, "elapsed_ms": sim_run.elapsed_ms, "meta": sim_run.meta,
            "model": {"key": model.key, "version": model.version, "id": model.id} if model else None,
            "results": {r.scenario_key: r.data for r in sim_run.results},
        }
    return out


def approval_dict(db: Session, a: ApprovalRequest) -> dict[str, Any]:
    d = row(a)
    users = {u.id: u for u in db.scalars(select(User).where(User.tenant_id == a.tenant_id))}
    d["decisions"] = [{**row(x), "approver_name": users[x.approver_id].full_name if x.approver_id in users else ""}
                      for x in a.decisions]
    d["requested_by_name"] = users[a.requested_by].full_name if a.requested_by in users else ""
    satisfied = {x.role_key for x in a.decisions if x.verdict == "approve"}
    d["pending_roles"] = [r for r in a.required_roles if r not in satisfied]
    dec = db.get(Decision, a.decision_id)
    d["decision_title"] = dec.title if dec else ""
    return d
