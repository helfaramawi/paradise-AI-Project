"""SimPy discrete-event simulation of the active project portfolio.

Each project is a sequence of work packages. A work package requests a crew (FTE) from a
shared delivery capacity pool (simpy.Container), holds it for a sampled duration and returns
it. The baseline run and the scenario run use identical random draws (common random numbers);
only the pool capacity differs. Additional delay per project is therefore attributable to the
capacity reduction implied by the strategy.

Portfolio structure is SYNTHETIC: 5 work packages per project, crews of 4-9 FTE,
triangular(1.5, 2.5, 4) month durations, staggered starts.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import simpy

from .assumptions import Baseline

WORK_PACKAGES = 5


def _portfolio(n_projects: int, seed: int) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed + 7)
    projects = []
    for i in range(n_projects):
        crews = rng.integers(4, 10, size=WORK_PACKAGES)
        durations = rng.triangular(1.5, 2.5, 4.0, size=WORK_PACKAGES)
        planned = float(WORK_PACKAGES * 2.5 * 1.0)  # plan uses mode durations
        projects.append({
            "id": f"PRJ-{i + 1:02d}",
            "start": float(rng.uniform(0, 1.5)),
            "crews": crews.tolist(),
            "durations": durations.tolist(),
            "planned_duration": planned,
            "contract_value_share": float(rng.uniform(0.6, 1.4)),
        })
    total = sum(p["contract_value_share"] for p in projects)
    for p in projects:
        p["contract_value_share"] /= total
    return projects


def _run(projects: list[dict[str, Any]], capacity: float) -> dict[str, float]:
    env = simpy.Environment()
    cap = max(1.0, capacity)
    pool = simpy.Container(env, capacity=cap, init=cap)
    finish: dict[str, float] = {}

    def project(p: dict[str, Any]):
        yield env.timeout(p["start"])
        for crew, dur in zip(p["crews"], p["durations"], strict=True):
            need = min(float(crew), cap)
            yield pool.get(need)
            yield env.timeout(dur)
            yield pool.put(need)
        finish[p["id"]] = env.now

    for p in projects:
        env.process(project(p))
    env.run()
    return finish


def simulate_project_portfolio(
    b: Baseline, capacity_reduction_fte: float, seed: int, at_risk_threshold_pct: float = 2.0
) -> dict[str, Any]:
    projects = _portfolio(b.active_projects, seed)
    # Pool sized so the portfolio demand is ~91% of baseline capacity (contention exists today).
    avg_demand = float(np.mean([np.mean(p["crews"]) for p in projects])) * len(projects)
    base_capacity = avg_demand / 0.91
    scen_capacity = base_capacity * (1 - capacity_reduction_fte / b.delivery_workload_fte)
    base = _run(projects, base_capacity)
    scen = _run(projects, scen_capacity)
    rows = []
    for p in projects:
        bd = base[p["id"]] - p["start"]
        sd = scen[p["id"]] - p["start"]
        add = (sd - bd) / p["planned_duration"] * 100
        rows.append({
            "project_id": p["id"],
            "planned_months": round(p["planned_duration"], 2),
            "baseline_months": round(bd, 2),
            "scenario_months": round(sd, 2),
            "additional_delay_pct": round(add, 2),
            "contract_value_share": round(p["contract_value_share"], 4),
            "at_risk": bool(add > at_risk_threshold_pct),
        })
    at_risk = [r for r in rows if r["at_risk"]]
    return {
        "method": "SimPy discrete-event simulation, common random numbers",
        "capacity_reduction_fte": round(capacity_reduction_fte, 2),
        "baseline_capacity_fte": round(base_capacity, 1),
        "scenario_capacity_fte": round(scen_capacity, 1),
        "at_risk_threshold_pct": at_risk_threshold_pct,
        "projects_at_risk": len(at_risk),
        "revenue_share_at_risk": round(sum(r["contract_value_share"] for r in at_risk), 4),
        "projects": rows,
    }
