"""Revenue collections decision domain: intake, receivables model, agents, governance and lab."""

import numpy as np
import pytest

from app.agents.intake import parse_decision
from app.simulation import collections as col
from app.simulation.assumptions import Baseline, DecisionControls, SimulationConfig
from app.simulation.engine import run_full_simulation

from .conftest import wait_run

QUESTION_AR = "ماذا لو حققنا متحصلات إيرادات أكبر بنسبة 30 % من خلال التعاقد مع شركة تحصيل؟"


def test_intake_detects_collections_question():
    p = parse_decision(QUESTION_AR)
    assert p["category"] == "collections_improvement" and p["domain"] == "collections"
    assert p["cost_reduction_target_pct"] == 30 and p["mentions_agency"] is True
    en = parse_decision("What if we collect 25% more overdue receivables with a collection agency within 9 months?")
    assert en["domain"] == "collections" and en["implementation_months"] == 9
    assert parse_decision("Reduce operating costs by 20% within six months")["domain"] == "opex"


@pytest.fixture(scope="module")
def sim():
    c = DecisionControls(domain="collections", cost_reduction_target_pct=30)
    return run_full_simulation(Baseline(), c, SimulationConfig(iterations=800))


def test_receivables_model_is_consistent(sim):
    assert sim["meta"]["model_id"] == col.MODEL_ID and set(sim["futures"]) == {"A", "B", "C"}
    for k, f in sim["futures"].items():
        s = f["summary"]
        nb = s["realized_savings_12m"]["expected"] - s["implementation_cost_12m"]["expected"] - s["delivery_loss_12m"]["expected"]
        assert s["net_benefit_12m"]["expected"] == pytest.approx(nb, abs=0.01), k
        assert s["savings_pct_at_deadline"]["p10"] <= s["savings_pct_at_deadline"]["p50"] <= s["savings_pct_at_deadline"]["p90"]
        assert len(f["trajectory"]["dso_days"]["expected"]) == 13
    # The baseline's overdue book grows (more slips into overdue than is recovered) ...
    pool = sim["baseline"]["trajectory"]["overdue_balance"]["expected"]
    assert pool[-1] > pool[0]
    # ... an agency drains it, and the in-house option pays no agency fees.
    assert sim["futures"]["A"]["trajectory"]["overdue_balance"]["expected"][-1] < pool[-1]
    assert sim["futures"]["C"]["summary"]["agency_fees_12m"]["p90"] == 0


def test_thirty_percent_is_not_reachable_and_aggression_breaks_constraints(sim):
    ach = {k: f["achievable_reduction_pct_at_tolerance"] for k, f in sim["futures"].items()}
    assert max(ach.values()) < 30
    a = sim["futures"]["A"]
    assert {"C3", "C5"} <= set(a["hard_constraints_violated"])
    assert not sim["futures"]["C"]["hard_constraints_violated"]


def test_baseline_draws_are_reproducible():
    c = DecisionControls(domain="collections")
    r1 = run_full_simulation(Baseline(), c, SimulationConfig(iterations=300, seed=7), include_sensitivity=False)
    r2 = run_full_simulation(Baseline(), c, SimulationConfig(iterations=300, seed=7), include_sensitivity=False)
    assert r1["meta"]["input_fingerprint"] == r2["meta"]["input_fingerprint"]
    assert np.isclose(r1["futures"]["B"]["summary"]["net_benefit_12m"]["p50"], r2["futures"]["B"]["summary"]["net_benefit_12m"]["p50"])


def test_collections_pipeline_end_to_end(client, analyst):
    d = client.post("/api/v1/decisions", json={"title": "Collection agency", "question": QUESTION_AR}, headers=analyst).json()
    assert d["controls"]["domain"] == "collections"
    assert any(o["key"] == "collections_uplift" for o in d["objectives"])
    run = client.post(f"/api/v1/decisions/{d['id']}/runs", json={"pacing_ms": 0}, headers=analyst).json()
    res = wait_run(client, analyst, run["run_id"])
    assert res["status"] == "completed", res.get("error")
    ds = client.get(f"/api/v1/decisions/{d['id']}/dossier", headers=analyst).json()
    assert ds["simulation"]["model"]["key"] == col.MODEL_ID
    codes = {f["code"] for f in ds["findings"]}
    assert {"STR-01", "CFO-01", "COO-02", "LEG-01", "DEL-FA", "ETH-CA"} <= codes
    assert {c["rule_code"] for c in ds["collisions"]} >= {"COL-11", "COL-14"}
    rec = ds["run"]["result"]["recommendation"]
    gov_a = rec["per_future"]["A"]
    assert gov_a["governance_outcome"] == "denied"
    assert "legal" in rec["per_future"]["B"]["required_roles"]  # GOV-015: customer data shared with an agency
    assert any("collection agencies" in s["en"] for s in rec["next_steps"])


def test_collections_lab_and_what_if(client, analyst):
    controls = {"domain": "collections", "cost_reduction_target_pct": 30}
    r = client.post("/api/v1/simulation/custom", json={"levers": {"agency_placement": 0.5, "digital_collections": 2},
                                                       "controls": controls, "iterations": 300}, headers=analyst)
    assert r.status_code == 200, r.text
    assert r.json()["project_portfolio"]["kind"] == "debtor_segments"
    bad = client.post("/api/v1/simulation/custom", json={"levers": {"agency_placement": 2}, "controls": controls},
                      headers=analyst)
    assert bad.status_code == 422
    w = client.post("/api/v1/simulation/run", json={"controls": controls, "iterations": 300}, headers=analyst).json()
    assert w["meta"]["domain"] == "collections"
