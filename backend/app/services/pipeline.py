"""Launches orchestrated decision analyses and persists every artefact with traceability."""

from __future__ import annotations

import logging
import threading
import traceback
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.llm import get_provider
from ..agents.orchestrator import Runtime, run_pipeline
from ..config import get_settings
from ..db import SessionLocal
from ..governance.service import load_policies
from ..models import (
    AgentFinding,
    AgentObjection,
    Decision,
    DecisionCollision,
    DecisionRun,
    DatasetVersion,
    EvidenceRecord,
    GovernanceEvaluation,
    RiskAssessment,
    Scenario,
    SimulationModel,
    SimulationResult,
    SimulationRun,
)
from ..simulation.assumptions import (
    MODEL_ID,
    MODEL_VERSION,
    LeverEconomics,
    SimulationConfig,
    UncertainParameter,
    default_uncertain_parameters,
)
from .audit import audit
from .events import EventSink, RunCancelled, RunTimeout

log = logging.getLogger("future_mirror.pipeline")


def production_model(db: Session, domain: str = "opex") -> SimulationModel:
    from ..simulation import collections

    key = collections.MODEL_ID if domain == "collections" else MODEL_ID
    m = db.scalar(select(SimulationModel).where(SimulationModel.key == key, SimulationModel.status == "production")
                  .order_by(SimulationModel.created_at.desc()))
    if m is None:
        if domain == "collections":
            m = SimulationModel(key=key, version=collections.MODEL_VERSION, status="production",
                                description="Revenue collections improvement: monthly receivables-flow model with Monte Carlo",
                                parameters=[p.model_dump() for p in collections.default_parameters()],
                                economics=collections.CollectionsEconomics().model_dump())
        else:
            m = SimulationModel(key=MODEL_ID, version=MODEL_VERSION, status="production",
                                description="Operating cost optimisation: monthly cost/capacity model with Monte Carlo",
                                parameters=[p.model_dump() for p in default_uncertain_parameters()],
                                economics=LeverEconomics().model_dump())
        db.add(m)
        db.commit()
    return m


def persist_simulation(db: Session, *, tenant_id: str, decision_id: str | None, run_id: str | None,
                       model: SimulationModel, dataset_version_id: str, sim: dict[str, Any], kind: str,
                       user_id: str | None) -> SimulationRun:
    meta = sim["meta"]
    sr = SimulationRun(tenant_id=tenant_id, decision_id=decision_id, run_id=run_id, model_id=model.id,
                       dataset_version_id=dataset_version_id, kind=kind, controls=meta["controls"], seed=meta["seed"],
                       iterations=meta["iterations"], input_fingerprint=meta["input_fingerprint"],
                       elapsed_ms=meta["elapsed_ms"], meta=meta, created_by=user_id)
    db.add(sr)
    db.flush()
    db.add(SimulationResult(simulation_run_id=sr.id, scenario_key="BASELINE", data=sim["baseline"]))
    for k, f in sim["futures"].items():
        db.add(SimulationResult(simulation_run_id=sr.id, scenario_key=k, data=f))
    return sr


def _persist_results(run_id: str, state: dict[str, Any]) -> None:
    with SessionLocal() as db:
        run = db.get(DecisionRun, run_id)
        decision = db.get(Decision, run.decision_id)
        model = production_model(db, decision.controls.get("domain", "opex"))
        sim = state["simulation"]
        persist_simulation(db, tenant_id=decision.tenant_id, decision_id=decision.id, run_id=run.id, model=model,
                           dataset_version_id=decision.dataset_version_id, sim=sim, kind="pipeline",
                           user_id=run.created_by)
        for s in state.get("scenarios", []):
            db.add(Scenario(decision_id=decision.id, run_id=run.id, key=s["key"], name_en=s["name_en"],
                            name_ar=s["name_ar"], definition=s))
        code_to_id: dict[str, str] = {}
        for i, f in enumerate(state.get("findings", [])):
            if not f.get("execution_id"):
                continue
            from ..agents.base import Evidence, Finding

            fobj = Finding(**{k: v for k, v in f.items() if k not in ("evidence", "execution_id")},
                           evidence=[Evidence(**e) for e in f.get("evidence", [])])
            af = AgentFinding(run_id=run.id, execution_id=f["execution_id"], agent_key=f["agent"], phase=f["phase"],
                              code=f["code"], claim_type=f["claim_type"], topic=f["topic"],
                              strategy_key=f.get("strategy_key"), stance=f["stance"], text_en=f["text_en"],
                              text_ar=f["text_ar"], confidence=f["confidence"], evidence_quality=fobj.evidence_quality,
                              assumptions=f.get("assumptions", []), seq=i)
            af.evidence = [EvidenceRecord(**e) for e in f.get("evidence", [])]
            db.add(af)
            db.flush()
            code_to_id[f["code"]] = af.id
        for i, o in enumerate(state.get("objections", [])):
            db.add(AgentObjection(run_id=run.id, raised_by=o["raised_by"], target_agent=o["target_agent"],
                                  target_finding_id=code_to_id.get(o.get("target_code") or ""),
                                  strategy_key=o.get("strategy_key"), objection_type=o["objection_type"],
                                  severity=o["severity"], text_en=o["text_en"], text_ar=o["text_ar"],
                                  response_by=o.get("response_by"), response_en=o.get("response_en"),
                                  response_ar=o.get("response_ar"), resolution=o["resolution"], seq=i))
        for c in state.get("collisions", []):
            db.add(DecisionCollision(run_id=run.id, rule_code=c["rule_code"], strategy_key=c["strategy_key"],
                                     severity=c["severity"], severity_score=c["severity_score"], title_en=c["title_en"],
                                     title_ar=c["title_ar"], positions=c["positions"],
                                     affected_objectives=c["affected_objectives"], consequences=c["consequences"],
                                     resolutions=c["resolutions"], requires_human=c["requires_human"]))
        for r in state.get("risks", []):
            db.add(RiskAssessment(run_id=run.id, **r))
        for k, g in state["governance"]["futures"].items():
            db.add(GovernanceEvaluation(run_id=run.id, decision_id=decision.id, scenario_key=k,
                                        action="strategy.approve", outcome=g["outcome"],
                                        required_roles=g["required_roles"], policy_results=g["policy_results"]))
        rec = state["recommendation"]
        run.result = {
            "recommendation": rec,
            "governance_probe": state["governance"]["agent_execution_probe"],
            "validation": state["validation"],
            "warnings": state.get("warnings", []),
        }
        decision.recommended_strategy = rec["recommended_strategy"]
        decision.status = "analyzed"
        db.commit()


def execute_run(run_id: str, fail_injection: dict[str, int] | None = None) -> None:
    s = get_settings()
    with SessionLocal() as db:
        run = db.get(DecisionRun, run_id)
        decision = db.get(Decision, run.decision_id)
        dv = db.get(DatasetVersion, decision.dataset_version_id)
        domain = decision.controls.get("domain", "opex")
        model = production_model(db, domain)
        policies = load_policies(db, decision.tenant_id)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        decision.status = "analyzing"
        db.commit()
        tenant_id, question, controls, baseline, intake = (decision.tenant_id, decision.question, decision.controls,
                                                           dv.data, decision.intake)
        params = [UncertainParameter(**p) for p in model.parameters]
        economics = LeverEconomics(**model.economics) if domain == "opex" else LeverEconomics()
        pacing = run.pacing_ms

    provider = get_provider(s)
    sink = EventSink(run_id, tenant_id, pacing_ms=pacing, timeout_s=s.pipeline_timeout_seconds)
    rt = Runtime(sink=sink, policies=policies, sim_config=SimulationConfig(seed=controls.get("seed", 20260101),
                 iterations=controls.get("iterations", 2000)), params=params, economics=economics, llm=provider,
                 agent_timeout_s=s.agent_timeout_seconds, fail_injection=fail_injection)
    status, error = "completed", None
    try:
        state = run_pipeline(rt, {"run_id": run_id, "question": question, "baseline": baseline,
                                  "controls": {k: v for k, v in controls.items() if k not in ("seed", "iterations")},
                                  "intake": {**intake, "question": question}, "findings": [], "warnings": []})
        _persist_results(run_id, state)
        sink.emit("executive_recommendation", "run_completed", "Decision dossier ready", "ملف القرار جاهز",
                  payload={"compute_ms": round(sink.compute_ms, 1), "paced_ms": sink.paced_ms})
    except RunCancelled as exc:
        status, error = "cancelled", str(exc)
        sink.emit("control", "run_cancelled", f"Run stopped: {exc}", "تم إيقاف التشغيل")
    except RunTimeout as exc:
        status, error = "failed", str(exc)
        sink.emit("control", "error", f"Run timed out: {exc}", "انتهت مهلة التشغيل")
    except Exception as exc:  # noqa: BLE001
        status, error = "failed", f"{type(exc).__name__}: {exc}"
        log.error("pipeline failed: %s\n%s", exc, traceback.format_exc())
        sink.emit("control", "error", f"Run failed: {error}", "فشل التشغيل", payload={"error": error})
    with SessionLocal() as db:
        run = db.get(DecisionRun, run_id)
        run.status = status
        run.error = error
        run.finished_at = datetime.now(UTC)
        run.compute_ms = round(sink.compute_ms, 1)
        run.mode = "llm_augmented" if provider else "rule_based"
        run.llm_provider = provider.name if provider else "none"
        run.llm_model = provider.model if provider else ""
        decision = db.get(Decision, run.decision_id)
        if status != "completed":
            decision.status = "failed" if status == "failed" else "draft"
        audit(db, tenant_id=tenant_id, actor_type="system", actor_id="orchestrator", action=f"run.{status}",
              entity_type="decision_run", entity_id=run_id,
              detail={"compute_ms": run.compute_ms, "mode": run.mode, "error": error})


def start_run(db: Session, decision: Decision, user_id: str, pacing_ms: int | None = None,
              background: bool = True) -> DecisionRun:
    s = get_settings()
    run = DecisionRun(decision_id=decision.id, created_by=user_id, status="queued",
                      pacing_ms=s.presentation_pacing_ms if pacing_ms is None else pacing_ms)
    db.add(run)
    db.commit()
    audit(db, tenant_id=decision.tenant_id, actor_type="user", actor_id=user_id, action="run.started",
          entity_type="decision_run", entity_id=run.id, detail={"decision_id": decision.id})
    if background:
        threading.Thread(target=execute_run, args=(run.id,), daemon=True, name=f"run-{run.id[:8]}").start()
    else:
        execute_run(run.id)
    return run
