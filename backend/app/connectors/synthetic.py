"""Synthetic ERP connector and data generator (fully working, clearly labelled synthetic).

Generates a 12-month general-ledger extract whose category totals reconcile exactly to the
demonstration baseline, plus a project register. Deterministic for a given seed.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..simulation.assumptions import Baseline
from .base import ConnectorResult, ReadOnlyConnector, reconcile

ACCOUNTS = {
    "personnel": ("6100", "Salaries & benefits"),
    "contractors": ("6200", "External contractors"),
    "software": ("6300", "Software licensing"),
    "infrastructure": ("6400", "Cloud & infrastructure"),
    "facilities": ("6500", "Facilities & rent"),
    "vendor services": ("6600", "Vendor services"),
    "other g&a": ("6900", "Other G&A (travel, training, misc.)"),
}

_CAT_FIELD = {
    "personnel": "personnel_cost", "contractors": "contractor_cost", "software": "software_cost",
    "infrastructure": "infrastructure_cost", "facilities": "facilities_cost",
    "vendor services": "vendor_services_cost", "other g&a": "other_ga_cost",
}


def generate_gl(base: Baseline | None = None, seed: int = 42, year: int = 2026) -> list[dict[str, Any]]:
    b = base or Baseline()
    rng = np.random.default_rng(seed)
    rows = []
    for cat, field in _CAT_FIELD.items():
        annual = getattr(b, field)
        w = rng.dirichlet(np.full(12, 40.0))  # mild monthly seasonality, sums to 1
        amounts = np.round(annual * w, 4)
        amounts[-1] = round(annual - amounts[:-1].sum(), 4)  # exact reconciliation
        acct, name = ACCOUNTS[cat]
        for mth, amt in enumerate(amounts, start=1):
            rows.append({"period": f"{year}-{mth:02d}", "account": acct, "account_name": name,
                         "category": cat, "amount_egp_m": float(amt), "synthetic": True})
    return rows


def generate_projects(base: Baseline | None = None, seed: int = 42) -> list[dict[str, Any]]:
    b = base or Baseline()
    rng = np.random.default_rng(seed + 1)
    vals = rng.dirichlet(np.full(b.active_projects, 5.0)) * b.annual_revenue
    out = []
    for i in range(b.active_projects):
        out.append({"project_id": f"PRJ-{i + 1:02d}", "annual_revenue_egp_m": round(float(vals[i]), 3),
                    "delay_pct": round(float(max(0, rng.normal(b.avg_project_delay_pct, 4))), 1),
                    "contractor_dependency_pct": round(float(rng.uniform(5, 45)), 1),
                    "critical_path": bool(rng.random() < 0.35), "synthetic": True})
    return out


class SyntheticERPConnector(ReadOnlyConnector):
    kind = "synthetic_erp"
    implementation = "working"

    def test_connection(self) -> dict[str, Any]:
        return {"ok": True, "message": "Synthetic ERP available (demonstration data)", "verified_live": False}

    def fetch_cost_profile(self, base: Baseline | None = None) -> ConnectorResult:
        b = base or Baseline()
        gl = generate_gl(b, seed=int(self.config.get("seed", 42)))
        totals: dict[str, float] = {}
        for r in gl:
            totals[r["category"]] = totals.get(r["category"], 0.0) + r["amount_egp_m"]
        profile, rec = reconcile(totals, b)
        rec["gl_total"] = round(sum(totals.values()), 4)
        rec["baseline_total"] = b.annual_opex
        rec["difference"] = round(rec["gl_total"] - b.annual_opex, 6)
        return ConnectorResult(profile=profile, reconciliation=rec, rows_read=len(gl), source="synthetic_erp",
                               verified_live=False)
