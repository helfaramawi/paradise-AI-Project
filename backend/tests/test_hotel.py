"""State-owned hotel decision domain: intake, owner-economics model, agents, governance and lab."""

import numpy as np
import pytest

from app.agents.intake import parse_decision
from app.simulation import hotel as ht
from app.simulation.assumptions import Baseline, DecisionControls, SimulationConfig
from app.simulation.engine import run_full_simulation

from .conftest import wait_run

QUESTION_AR = ("الاستفاده القصوي من فندق أراكان ١٤٨ غرفه بوسط البلد (بورسعيد) ملك للجهاز التنفيذي للمنطقة الحرة "
               "محافظة بورسعيد من خلال مقترحات مختلفة")
HOTEL_CONTROLS = {"domain": "hotel", "cost_reduction_target_pct": 6, "implementation_months": 12,
                  "acceptable_delay_increase_pct": 35, "min_csat_pct": 60, "implementation_budget": 40,
                  "automation_investment": 0}


def test_intake_detects_hotel_question():
    p = parse_decision(QUESTION_AR)
    assert p["domain"] == "hotel" and p["category"] == "asset_utilization"
    assert p["hotel_rooms"] == 148 and p["asset_name"] == "أراكان"
    # No number in the question: documented defaults, not detected values.
    assert p["cost_reduction_target_pct"] == 6 and "target" not in p["detected"]
    assert p["implementation_months"] == 12 and p["acceptable_delay_increase_pct"] == 35
    assert parse_decision("Make the most of our 120-room hotel downtown")["domain"] == "hotel"
    assert parse_decision("Reduce operating costs by 20% within six months")["domain"] == "opex"


@pytest.fixture(scope="module")
def sim():
    return run_full_simulation(Baseline(), DecisionControls(**HOTEL_CONTROLS), SimulationConfig(iterations=800))


def test_owner_economics_are_consistent(sim):
    assert sim["meta"]["model_id"] == ht.MODEL_ID and set(sim["futures"]) == {"A", "B", "C"}
    assert sim["baseline"]["summary"]["owner_net_return_at_deadline"]["expected"] < 0  # loss-making today
    for k, f in sim["futures"].items():
        s = f["summary"]
        nb = s["realized_savings_12m"]["expected"] - s["implementation_cost_12m"]["expected"] - s["delivery_loss_12m"]["expected"]
        assert s["net_benefit_12m"]["expected"] == pytest.approx(nb, abs=0.01), k
        assert s["stabilised_yield_pct"]["p10"] <= s["stabilised_yield_pct"]["p50"] <= s["stabilised_yield_pct"]["p90"]
        assert len(f["trajectory"]["occupancy_pct"]["expected"]) == 13
        assert f["project_portfolio"]["kind"] == "hotel_spaces"


def test_trade_offs_between_proposals(sim):
    a, b, c = (sim["futures"][k] for k in "ABC")
    # The lease closes the hotel and leaves more surplus staff than the Authority can absorb.
    assert {"C3", "C5"} <= set(a["hard_constraints_violated"])
    assert a["summary"]["one_off_implementation_cost"]["p50"] < 2
    # The brand renovation has the highest stabilised return but needs more capital than the budget.
    assert b["summary"]["stabilised_yield_pct"]["p50"] > max(a["summary"]["stabilised_yield_pct"]["p50"],
                                                             c["summary"]["stabilised_yield_pct"]["p50"])
    assert "C6" in b["constraints_violated"] and not b["hard_constraints_violated"]
    # The mixed-use repositioning stays within budget and keeps every employee.
    assert not c["hard_constraints_violated"] and "C6" not in c["constraints_violated"]
    assert c["summary"]["staff_surplus_fte"]["p90"] == 0
    # A 6% return is not reachable within 12 months.
    assert max(f["achievable_reduction_pct_at_tolerance"] for f in (a, b, c)) < 6


def test_reproducible():
    c = DecisionControls(**HOTEL_CONTROLS)
    r1 = run_full_simulation(Baseline(), c, SimulationConfig(iterations=300, seed=7), include_sensitivity=False)
    r2 = run_full_simulation(Baseline(), c, SimulationConfig(iterations=300, seed=7), include_sensitivity=False)
    assert r1["meta"]["input_fingerprint"] == r2["meta"]["input_fingerprint"]
    assert np.isclose(r1["futures"]["C"]["summary"]["net_benefit_12m"]["p50"], r2["futures"]["C"]["summary"]["net_benefit_12m"]["p50"])


def test_hotel_pipeline_end_to_end(client, analyst):
    parsed = client.post("/api/v1/decisions/parse", json={"question": QUESTION_AR}, headers=analyst).json()
    assert parsed["supported"] and parsed["suggested_controls"]["domain"] == "hotel"
    assert parsed["suggested_controls"]["implementation_budget"] == 40
    d = client.post("/api/v1/decisions", json={"title": "Hotel", "question": QUESTION_AR}, headers=analyst).json()
    assert d["controls"]["domain"] == "hotel" and d["controls"]["acceptable_delay_increase_pct"] == 35
    assert any(o["key"] == "asset_return" for o in d["objectives"])
    run = client.post(f"/api/v1/decisions/{d['id']}/runs", json={"pacing_ms": 0}, headers=analyst).json()
    res = wait_run(client, analyst, run["run_id"])
    assert res["status"] == "completed", res.get("error")
    ds = client.get(f"/api/v1/decisions/{d['id']}/dossier", headers=analyst).json()
    assert ds["simulation"]["model"]["key"] == ht.MODEL_ID
    codes = {f["code"] for f in ds["findings"]}
    assert {"STR-01", "CFO-01", "HR-01", "LEG-01", "CFO-FC", "ETH-HA"} <= codes
    assert {c["rule_code"] for c in ds["collisions"]} >= {"COL-21", "COL-22", "COL-24"}
    rec = ds["run"]["result"]["recommendation"]
    assert rec["recommended_strategy"] == "C"
    gov = {g["scenario_key"]: g for g in ds["governance"]}
    matched = {k: {r["code"] for r in g["policy_results"] if r.get("matched")} for k, g in gov.items()}
    # The lease is blocked by its critical collision (staff and closure) and needs a public tender (GOV-017).
    assert gov["A"]["outcome"] == "denied" and {"GOV-009", "GOV-017"} <= matched["A"]
    assert "GOV-018" in matched["B"] and {"cfo", "ceo"} <= set(rec["per_future"]["B"]["required_roles"])
    assert "GOV-012" not in matched["B"] | matched["C"]  # capital works are not "implementation spend"
    assert any("valuation" in s["en"] for s in rec["next_steps"])


def test_hotel_lab(client, analyst):
    r = client.post("/api/v1/simulation/custom", json={"levers": {"serviced_apartments": 1, "digital_distribution": 1,
                                                                  "renovation_capex": 20},
                                                       "controls": HOTEL_CONTROLS, "iterations": 300}, headers=analyst)
    assert r.status_code == 200, r.text
    assert r.json()["project_portfolio"]["kind"] == "hotel_spaces"
    bad = client.post("/api/v1/simulation/custom", json={"levers": {"lease_to_operator": 2}, "controls": HOTEL_CONTROLS},
                      headers=analyst)
    assert bad.status_code == 422
    m = client.get("/api/v1/simulation/model?domain=hotel", headers=analyst).json()
    assert "serviced_apartments" in m["levers_schema"]["properties"]
