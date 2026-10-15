import numpy as np

from app.simulation.assumptions import Baseline, DecisionControls, LeverEconomics, Levers, SimulationConfig
from app.simulation.assumptions import default_uncertain_parameters
from app.simulation.delivery_des import simulate_project_portfolio
from app.simulation.engine import ModelInputs, mode_parameters, run_full_simulation, run_model
from app.simulation.validation import validate_baseline


def _quick(**kw):
    return run_full_simulation(config=SimulationConfig(iterations=400, seed=kw.pop("seed", 11)),
                               include_sensitivity=False, **kw)


def test_reproducible_with_same_seed():
    a, b = _quick(seed=5), _quick(seed=5)
    assert a["meta"]["input_fingerprint"] == b["meta"]["input_fingerprint"]
    for k in "ABC":
        assert a["futures"][k]["summary"] == b["futures"][k]["summary"]
        assert a["futures"][k]["trajectory"] == b["futures"][k]["trajectory"]


def test_different_seed_changes_samples_not_expected_case():
    a, b = _quick(seed=5), _quick(seed=6)
    assert a["meta"]["input_fingerprint"] != b["meta"]["input_fingerprint"]
    assert a["futures"]["A"]["summary"]["net_benefit_12m"]["p10"] != b["futures"]["A"]["summary"]["net_benefit_12m"]["p10"]
    # deterministic expected case does not depend on the seed
    assert a["futures"]["A"]["summary"]["net_benefit_12m"]["expected"] == b["futures"]["A"]["summary"]["net_benefit_12m"]["expected"]


def test_baseline_has_no_savings_and_no_delay_change():
    r = _quick()
    s = r["baseline"]["summary"]
    assert s["realized_savings_12m"]["p90"] == 0
    assert s["max_delay_increase_pct"]["p90"] == 0
    assert r["baseline"]["project_portfolio"]["projects_at_risk"] == 0


def test_contractor_reduction_monotonically_increases_shortfall():
    b, c, econ = Baseline(), DecisionControls(), LeverEconomics()
    theta = mode_parameters(default_uncertain_parameters())
    delays = []
    for x in (0.0, 0.3, 0.6, 0.9):
        out = run_model(b, c, Levers(contractor_reduction=x), econ, theta)
        delays.append(float(out["summary"]["max_delay_increase_pct"][0]))
    assert delays == sorted(delays) and delays[-1] > delays[0]


def test_savings_accounting_identity():
    """Savings run-rate equals the sum of category savings at the modal parameters."""
    b, c, econ = Baseline(), DecisionControls(), LeverEconomics()
    theta = mode_parameters(default_uncertain_parameters())
    out = run_model(b, c, Levers(software_consolidation=1.0), econ, theta)
    assert np.isclose(out["trajectory"]["savings_run_rate"][0, -1], b.software_cost * 0.22)


def test_target_infeasible_without_terminations_is_reported():
    r = _quick()
    best = max(r["futures"][k]["achievable_reduction_pct_at_tolerance"] for k in "ABC")
    assert best < 20  # 20% target is not reachable from non-personnel spend in the demo data
    assert all("C1" in r["futures"][k]["constraints_violated"] for k in "ABC")


def test_lower_target_can_be_met():
    r = _quick(controls=DecisionControls(cost_reduction_target_pct=8))
    assert r["futures"]["A"]["probabilities"]["meet_target"] > 0.9
    assert "C1" not in r["futures"]["A"]["constraints_violated"]


def test_termination_lever_violates_hard_constraint():
    from app.simulation.engine import evaluate_constraints, sample_parameters
    b, c, econ = Baseline(), DecisionControls(), LeverEconomics()
    lev = Levers(workforce_termination=0.1)
    theta = sample_parameters(default_uncertain_parameters(), 200, 1)
    out = run_model(b, c, lev, econ, theta)
    cons = {x["code"]: x for x in evaluate_constraints(b, c, lev, out["summary"])}
    assert cons["C2"]["status"] == "fail"


def test_sensitivity_sorted_and_documented():
    r = run_full_simulation(config=SimulationConfig(iterations=200))
    sens = r["futures"]["A"]["sensitivity"]
    swings = [s["swing"] for s in sens]
    assert swings == sorted(swings, reverse=True)
    assert {s["parameter"] for s in sens} == {p.key for p in default_uncertain_parameters()}


def test_des_common_random_numbers():
    b = Baseline()
    zero = simulate_project_portfolio(b, 0.0, seed=3)
    assert zero["projects_at_risk"] == 0
    assert all(abs(p["additional_delay_pct"]) < 1e-9 for p in zero["projects"])
    big = simulate_project_portfolio(b, 20.0, seed=3)
    assert big["projects_at_risk"] > 0


def test_validation_detects_margin_inconsistency_and_accepts_consistent_data():
    rep = validate_baseline(Baseline())
    dq2 = next(c for c in rep.checks if c.code == "DQ-002")
    assert dq2.severity == "error" and rep.has_errors
    ok = Baseline(annual_revenue=180, gross_margin_pct=80, annual_opex=120)
    assert next(c for c in validate_baseline(ok).checks if c.code == "DQ-002").severity == "ok"


def test_category_mismatch_detected():
    rep = validate_baseline(Baseline(personnel_cost=70))
    assert next(c for c in rep.checks if c.code == "DQ-001").severity == "error"


def test_compressed_timeline_raises_cost():
    a = _quick(controls=DecisionControls(implementation_months=6))
    b = _quick(controls=DecisionControls(implementation_months=3))
    assert (b["futures"]["C"]["summary"]["one_off_implementation_cost"]["expected"]
            > a["futures"]["C"]["summary"]["one_off_implementation_cost"]["expected"])


def test_fingerprint_changes_with_inputs():
    i1 = ModelInputs(Baseline(), DecisionControls(), SimulationConfig(), default_uncertain_parameters(), LeverEconomics())
    i2 = ModelInputs(Baseline(utilization_pct=70), DecisionControls(), SimulationConfig(), default_uncertain_parameters(),
                     LeverEconomics())
    assert i1.fingerprint() != i2.fingerprint()
