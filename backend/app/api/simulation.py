from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DatasetVersion, EnterpriseDataset, SimulationModel, SimulationRun, User
from ..security import require
from ..services.audit import audit
from ..services.dossier import get_decision, row
from ..services.pipeline import persist_simulation, production_model
from ..simulation.assumptions import (
    Baseline,
    DecisionControls,
    LeverEconomics,
    Levers,
    SimulationConfig,
    UncertainParameter,
)
from ..simulation.engine import ModelInputs, run_full_simulation, simulate_strategy
from ..simulation.engine import sample_parameters

router = APIRouter(prefix="/simulation", tags=["simulation"])
DB = Annotated[Session, Depends(get_db)]


class WhatIfIn(BaseModel):
    controls: DecisionControls = DecisionControls()
    dataset_version_id: str | None = None
    baseline_overrides: dict[str, float] = {}
    iterations: int = Field(1000, ge=100, le=20000)
    seed: int = 20260101
    include_sensitivity: bool = True
    include_des: bool = True
    persist: bool = False
    decision_id: str | None = None


class CustomIn(BaseModel):
    levers: dict[str, float]  # Levers (opex) or CollectionsLevers (collections), chosen by controls.domain
    controls: DecisionControls = DecisionControls()
    dataset_version_id: str | None = None
    iterations: int = Field(1000, ge=100, le=20000)
    seed: int = 20260101


def _dataset(db: Session, user: User, dv_id: str | None) -> DatasetVersion:
    q = select(DatasetVersion).join(EnterpriseDataset).where(EnterpriseDataset.tenant_id == user.tenant_id)
    if dv_id:
        q = q.where(DatasetVersion.id == dv_id)
    dv = db.scalar(q.order_by(DatasetVersion.created_at.desc()).limit(1))
    if not dv:
        raise HTTPException(404, "Dataset version not found")
    return dv


def _model(db: Session, domain: str = "opex") -> tuple[SimulationModel, list[UncertainParameter], LeverEconomics]:
    m = production_model(db, domain)
    econ = LeverEconomics(**m.economics) if domain == "opex" else LeverEconomics()
    return m, [UncertainParameter(**p) for p in m.parameters], econ


@router.get("/model")
def model_info(db: DB, user: Annotated[User, require("simulation.run")], domain: str = "opex") -> dict[str, Any]:
    from ..simulation.collections import CollectionsLevers

    m, params, econ = _model(db, domain)
    models = db.scalars(select(SimulationModel).order_by(SimulationModel.created_at.desc())).all()
    return {"production": row(m), "versions": [row(x, exclude=("parameters", "economics")) for x in models],
            "parameters": [p.model_dump() for p in params], "economics": econ.model_dump(),
            "controls_schema": DecisionControls.model_json_schema(), "levers_schema": (CollectionsLevers if domain == "collections" else Levers).model_json_schema()}


@router.post("/run")
def what_if(body: WhatIfIn, db: DB, user: Annotated[User, require("simulation.run")]) -> dict[str, Any]:
    dv = _dataset(db, user, body.dataset_version_id)
    try:
        base = Baseline(**{**dv.data, **body.baseline_overrides})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"Invalid baseline override: {exc}") from exc
    m, params, econ = _model(db, body.controls.domain)
    res = run_full_simulation(base, body.controls, SimulationConfig(iterations=body.iterations, seed=body.seed),
                              params, econ, include_sensitivity=body.include_sensitivity, include_des=body.include_des)
    res["meta"]["dataset_version_id"] = dv.id
    res["meta"]["model_record"] = {"id": m.id, "version": m.version}
    if body.persist:
        decision_id = None
        if body.decision_id:
            decision_id = get_decision(db, body.decision_id, user).id
        sr = persist_simulation(db, tenant_id=user.tenant_id, decision_id=decision_id, run_id=None, model=m,
                                dataset_version_id=dv.id, sim=res, kind="what_if", user_id=user.id)
        db.commit()
        audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="simulation.what_if_saved",
              entity_type="simulation_run", entity_id=sr.id, detail={"fingerprint": sr.input_fingerprint})
        res["meta"]["simulation_run_id"] = sr.id
    return res


@router.post("/custom")
def custom_strategy(body: CustomIn, db: DB, user: Annotated[User, require("simulation.run")]) -> dict[str, Any]:
    """Simulation Laboratory: evaluate an arbitrary lever combination."""
    dv = _dataset(db, user, body.dataset_version_id)
    _, params, econ = _model(db, body.controls.domain)
    if body.controls.domain == "collections":
        from ..simulation import collections as col

        try:
            lv = col.CollectionsLevers(**body.levers)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(422, f"Invalid levers: {exc}") from exc
        strat = col.CollectionsStrategy(key="LAB", name_en="Custom strategy", name_ar="استراتيجية مخصصة", tagline_en="",
                                        tagline_ar="", measures_en=[], measures_ar=[], levers=lv, proposed_by=["user"])
        cfg = SimulationConfig(iterations=body.iterations, seed=body.seed)
        theta = sample_parameters(params, body.iterations, body.seed)
        r = col.simulate_strategy(Baseline(**dv.data), body.controls, cfg, params, col.CollectionsEconomics(), strat, theta)
        r["meta"] = {"seed": body.seed, "iterations": body.iterations, "domain": "collections"}
        return r
    try:
        levers = Levers(**body.levers)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"Invalid levers: {exc}") from exc
    inputs = ModelInputs(Baseline(**dv.data), body.controls, SimulationConfig(iterations=body.iterations, seed=body.seed),
                         params, econ)
    theta = sample_parameters(params, body.iterations, body.seed)
    from ..simulation.futures import StrategyDefinition

    strat = StrategyDefinition(key="LAB", name_en="Custom strategy", name_ar="استراتيجية مخصصة", tagline_en="",
                               tagline_ar="", measures_en=[], measures_ar=[], levers=levers, proposed_by=["user"])
    r = simulate_strategy(inputs, strat, theta)
    r["meta"] = {"fingerprint": inputs.fingerprint(), "seed": body.seed, "iterations": body.iterations}
    return r


@router.get("/runs")
def list_runs(db: DB, user: Annotated[User, require("simulation.run")], limit: int = 30) -> list[dict[str, Any]]:
    rows = db.scalars(select(SimulationRun).where(SimulationRun.tenant_id == user.tenant_id)
                      .order_by(SimulationRun.created_at.desc()).limit(min(limit, 200))).all()
    return [row(r, exclude=("meta",)) for r in rows]
