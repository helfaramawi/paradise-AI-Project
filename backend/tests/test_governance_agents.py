import copy

from app.agents.base import AgentContext, Finding
from app.agents.collision import detect_collisions
from app.agents.court import redteam_challenge, respond
from app.agents.domain import PHASE1, PHASE2
from app.agents.intake import parse_decision
from app.agents.recommend import build_recommendation
from app.governance.engine import DEFAULT_POLICIES, evaluate_condition, evaluate_policies
from app.governance.service import evaluate_strategy
from app.simulation.assumptions import Baseline, DecisionControls, Levers, SimulationConfig
from app.simulation.engine import run_full_simulation
from app.simulation.validation import validate_baseline

POL = [dict(p, enabled=True) for p in DEFAULT_POLICIES]
SIM = run_full_simulation(config=SimulationConfig(iterations=500))


def _ctx(sim=SIM, controls=None):
    return AgentContext(Baseline(), controls or DecisionControls(), validate_baseline(Baseline()), {}, sim)


def _all_findings(ctx):
    fs = []
    for fn in PHASE1.values():
        fs += fn(ctx)
    for fn in PHASE2.values():
        fs += fn(ctx)
    return fs


def test_condition_operators():
    ctx = {"a": {"b": 3, "l": [1, 2]}, "t": True}
    assert evaluate_condition({"fact": "a.b", "op": "gt", "value": 2}, ctx)
    assert evaluate_condition({"all": [{"fact": "t", "op": "truthy"}, {"fact": "a.l", "op": "len_gt", "value": 1}]}, ctx)
    assert evaluate_condition({"not": {"fact": "a.missing", "op": "exists"}}, ctx)
    assert evaluate_condition({"any": [{"fact": "a.b", "op": "eq", "value": 9}, {"fact": "a.b", "op": "in", "value": [3]}]}, ctx)


def test_governance_blocks_termination_even_if_every_agent_supports():
    fut = copy.deepcopy(SIM["futures"]["B"])
    fut["levers"]["workforce_termination"] = 0.05
    fut["hard_constraints_violated"] = []
    g = evaluate_strategy(POL, future=fut, controls=DecisionControls().model_dump(), collisions=[], dataset_has_errors=False)
    assert g["outcome"] == "denied"
    assert "GOV-001" in [d["code"] for d in g["deny_reasons"]]
    # recommendation must not choose a denied future even with unanimous, high-quality support
    ctx = _ctx()
    support = [Finding(a, f"X-{a}", "estimate", "t", "s", "s", 1.0, strategy_key="B", stance="support", phase="court")
               for a in ("cfo", "coo", "hr", "delivery", "legal", "risk", "strategy")]
    gov = {"A": {"outcome": "denied", "required_roles": []}, "B": g, "C": {"outcome": "denied", "required_roles": []}}
    rec = build_recommendation(ctx, support, [], gov, [])
    assert rec["recommended_strategy"] is None and rec["status"] == "not_acceptable"


def test_agent_execution_always_denied():
    g = evaluate_strategy(POL, future=SIM["futures"]["B"], controls=DecisionControls().model_dump(), collisions=[],
                          dataset_has_errors=False, actor_type="agent", mode="execute")
    assert g["outcome"] == "denied" and "GOV-002" in [d["code"] for d in g["deny_reasons"]]


def test_approval_roles_scale_with_impact():
    g = evaluate_strategy(POL, future=SIM["futures"]["B"], controls=DecisionControls().model_dump(), collisions=[],
                          dataset_has_errors=True)
    assert "cfo" in g["required_roles"] and "legal" in g["required_roles"]
    assert "GOV-011" in g["acknowledgements"]


def test_disabled_policy_is_skipped():
    pols = [dict(p, enabled=(p["code"] != "GOV-006")) for p in DEFAULT_POLICIES]
    g = evaluate_strategy(pols, future=SIM["futures"]["B"], controls=DecisionControls().model_dump(), collisions=[],
                          dataset_has_errors=False)
    assert "legal" not in g["required_roles"]


def test_automation_live_consequential_blocked():
    ctx = {"action": {"type": "automation.run", "consequential": True, "dry_run": False, "external_write": True},
           "decision": {"status": "approved"}, "platform": {"external_actions_enabled": False}}
    g = evaluate_policies(POL, ctx)
    codes = {d["code"] for d in g["deny_reasons"]}
    assert g["outcome"] == "denied" and {"GOV-003", "GOV-014"} <= codes


def test_collision_detector_finds_contractor_delivery_conflict():
    ctx = _ctx()
    fs = _all_findings(ctx)
    cols = detect_collisions(ctx, fs)
    codes = {(c["rule_code"], c["strategy_key"]) for c in cols}
    assert ("COL-01", "A") in codes
    assert ("COL-02", None) in codes
    col = next(c for c in cols if c["rule_code"] == "COL-01" and c["strategy_key"] == "A")
    assert {p["agent"] for p in col["positions"]} >= {"cfo", "delivery"}
    assert col["requires_human"]


def test_collisions_disappear_when_strategy_is_safe():
    sim = run_full_simulation(controls=DecisionControls(cost_reduction_target_pct=5, acceptable_delay_increase_pct=20,
                                                        min_csat_pct=50), config=SimulationConfig(iterations=300))
    ctx = _ctx(sim, DecisionControls(cost_reduction_target_pct=5, acceptable_delay_increase_pct=20, min_csat_pct=50))
    cols = detect_collisions(ctx, _all_findings(ctx))
    assert not any(c["rule_code"] == "COL-02" for c in cols)


def test_red_team_challenges_unverified_skill_assumption():
    ctx = _ctx()
    obs = respond(ctx, redteam_challenge(ctx, _all_findings(ctx)))
    types = {o.objection_type for o in obs}
    assert "unsupported_assumption" in types and "data_integrity" in types
    assert all(o.response_en for o in obs)
    assert any(o.resolution == "unresolved" for o in obs)


def test_findings_are_bilingual_and_evidenced():
    ctx = _ctx()
    for f in _all_findings(ctx):
        assert f.text_en and f.text_ar and f.evidence, f.code
        assert 0 <= f.confidence <= 1 and 0 <= f.evidence_quality <= 1
        assert any("؀" <= ch <= "ۿ" for ch in f.text_ar)


def test_recommendation_is_not_majority_vote():
    # 3 low-quality supports for C vs 1 high-quality support for B
    weak = [Finding(a, f"W-{a}", "hypothesis", "t", "s", "s", 0.2, strategy_key="C", stance="support", phase="court")
            for a in ("cfo", "coo", "hr")]
    from app.agents.base import Evidence
    strong = [Finding("risk", "S-1", "estimate", "t", "s", "s", 0.95, strategy_key="B", stance="support", phase="court",
                      evidence=[Evidence("policy", "x", "x", "x", True)] * 2)]
    gov = {k: {"outcome": "requires_approval", "required_roles": ["cfo"]} for k in "ABC"}
    sim = copy.deepcopy(SIM)
    for k in "ABC":
        sim["futures"][k]["hard_constraints_violated"] = []
    rec = build_recommendation(_ctx(sim), weak + strong, [], gov, [])
    assert rec["naive_majority_winner"] == "C"
    assert rec["recommended_strategy"] == "B" and rec["majority_differs"]


def test_intake_parser_english_and_arabic():
    en = parse_decision("Reduce operating costs by 15% within nine months without layoffs, protect project delivery")
    assert en["cost_reduction_target_pct"] == 15 and en["implementation_months"] == 9 and en["no_terminations"]
    ar = parse_decision("نريد خفض التكاليف التشغيلية بنسبة ٢٠٪ خلال ستة أشهر دون إنهاء خدمة الموظفين مع الحفاظ على رضا العملاء")
    assert ar["language"] == "ar" and ar["cost_reduction_target_pct"] == 20 and ar["implementation_months"] == 6
    assert ar["no_terminations"] and ar["protect_csat"]


def test_intake_strips_control_chars():
    from app.agents.intake import sanitize
    assert "\x00" not in sanitize("abc\x00def\x1b[31m")


def test_levers_validation_rejects_out_of_range():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Levers(contractor_reduction=1.5)
