"""Chief Decision Orchestrator implemented as a LangGraph state machine.

Workflow:
  intake -> data_validation -> agent_assignment -> [7 domain agents in parallel]
  -> scenario_generation -> quantitative_simulation -> agent_court (+ collision detection)
  -> risk_assessment -> governance_review -> executive_recommendation

The orchestrator handles retries, per-agent timeouts, cancellation/emergency stop and
emits a persisted event for every real state transition (no simulated progress).
State is checkpointed per run (thread_id = run_id).
"""

from __future__ import annotations

import concurrent.futures
import operator
import time
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from ..simulation.assumptions import (
    Baseline,
    DecisionControls,
    LeverEconomics,
    SimulationConfig,
    UncertainParameter,
)
from ..simulation.engine import run_full_simulation
from ..simulation.futures import build_futures
from ..simulation.validation import ValidationReport, validate_baseline
from . import collections_agents, domain, hotel_agents
from .base import AGENT_CATALOG, AgentContext, Evidence, Finding, Objection
from .collision import detect_collisions, risk_register
from .court import governance_findings, redteam_challenge, respond
from .llm import LLMProvider, narrate
from .recommend import build_recommendation, feasibility_search

PHASE1_AGENTS = ["strategy", "cfo", "coo", "hr", "delivery", "legal", "risk"]

STAGES = [
    ("intake", "Decision received", "استلام القرار"),
    ("data_validation", "Data validation", "التحقق من البيانات"),
    ("agent_assignment", "Agent assignment", "تكليف الوكلاء"),
    ("independent_analysis", "Independent analysis", "التحليل المستقل"),
    ("scenario_generation", "Scenario generation", "توليد السيناريوهات"),
    ("quantitative_simulation", "Quantitative simulation", "المحاكاة الكمية"),
    ("agent_court", "Agent Court", "محكمة الوكلاء"),
    ("risk_assessment", "Risk assessment", "تقييم المخاطر"),
    ("governance_review", "Governance review", "مراجعة الحوكمة"),
    ("executive_recommendation", "Executive recommendation", "التوصية التنفيذية"),
]
STAGE_LABEL = {k: (en, ar) for k, en, ar in STAGES}


class PipelineState(TypedDict, total=False):
    run_id: str
    question: str
    baseline: dict[str, Any]
    controls: dict[str, Any]
    intake: dict[str, Any]
    validation: dict[str, Any]
    findings: Annotated[list[dict[str, Any]], operator.add]
    scenarios: list[dict[str, Any]]
    simulation: dict[str, Any]
    objections: list[dict[str, Any]]
    collisions: list[dict[str, Any]]
    risks: list[dict[str, Any]]
    governance: dict[str, Any]
    recommendation: dict[str, Any]
    feasibility: list[dict[str, Any]]
    warnings: Annotated[list[str], operator.add]


@dataclass
class Runtime:
    sink: Any  # EventSink
    policies: list[dict[str, Any]]
    sim_config: SimulationConfig
    params: list[UncertainParameter]
    economics: LeverEconomics
    llm: LLMProvider | None
    agent_timeout_s: float
    dataset_has_errors_ack: bool = False
    fail_injection: dict[str, int] | None = None  # test hook: agent_key -> number of failures to inject


def _finding_from(d: dict[str, Any]) -> Finding:
    ev = [Evidence(**e) for e in d.get("evidence", [])]
    kw = {k: v for k, v in d.items() if k not in ("evidence", "evidence_quality", "execution_id")}
    f = Finding(**kw, evidence=ev)
    f.__dict__["execution_id"] = d.get("execution_id")
    return f


def _ctx(state: PipelineState) -> AgentContext:
    return AgentContext(
        baseline=Baseline(**state["baseline"]),
        controls=DecisionControls(**state["controls"]),
        validation=ValidationReport(**state["validation"]) if state.get("validation") else validate_baseline(Baseline(**state["baseline"])),
        intake=state.get("intake", {}),
        simulation=state.get("simulation"),
        findings=[_finding_from(f) for f in state.get("findings", [])],
    )


class _OpexRules:
    """The cost-reduction domain's agents and court/collision rules (collections and hotel have their own)."""

    PHASE1, PHASE2 = domain.PHASE1, domain.PHASE2
    redteam_challenge, respond = staticmethod(redteam_challenge), staticmethod(respond)
    detect_collisions, risk_register = staticmethod(detect_collisions), staticmethod(risk_register)

    @staticmethod
    def ethics_findings(ctx: AgentContext) -> list[Finding]:
        return []


def rules_for(state: PipelineState):
    d = (state.get("controls") or {}).get("domain")
    return collections_agents if d == "collections" else hotel_agents if d == "hotel" else _OpexRules


def build_graph(rt: Runtime):
    sink = rt.sink
    mode = "llm_augmented" if rt.llm else "rule_based"

    def stage(name: str):
        def deco(fn):
            def wrapper(state: PipelineState) -> dict[str, Any]:
                sink.check()
                en, ar = STAGE_LABEL[name]
                sink.emit(name, "stage_started", f"{en} started", f"بدء: {ar}")
                t0 = time.perf_counter()
                out = fn(state) or {}
                ms = (time.perf_counter() - t0) * 1000
                sink.emit(name, "stage_completed", f"{en} completed", f"اكتمل: {ar}",
                          payload={"duration_ms": round(ms, 1), **out.pop("_event_payload", {})})
                sink.pace()
                return out
            return wrapper
        return deco

    def run_agent(key: str, phase: str, fn, ctx: AgentContext) -> list[Finding]:
        """Execute one agent with timeout and retry; persist an AgentExecution record."""
        sink.check()
        name_en, name_ar = AGENT_CATALOG[key]["name_en"], AGENT_CATALOG[key]["name_ar"]
        ex_id = sink.start_execution(key, phase, mode)
        sink.emit(phase, "agent_started", f"{name_en} analysing", f"{name_ar} يحلل", agent_key=key)
        attempts, last_err = 0, None
        t0 = time.perf_counter()
        while attempts < 3:
            attempts += 1
            try:
                if rt.fail_injection and rt.fail_injection.get(key, 0) >= attempts:
                    raise RuntimeError(f"Injected failure for {key} (attempt {attempts})")
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    findings = pool.submit(fn, ctx).result(timeout=rt.agent_timeout_s)
                break
            except Exception as exc:  # noqa: BLE001
                last_err = f"{type(exc).__name__}: {exc}"
                if attempts < 3:
                    sink.emit(phase, "agent_retry", f"{name_en}: attempt {attempts} failed, retrying ({last_err})",
                              f"{name_ar}: فشلت المحاولة {attempts}، إعادة المحاولة", agent_key=key,
                              payload={"attempt": attempts, "error": last_err})
        else:
            ms = (time.perf_counter() - t0) * 1000
            sink.finish_execution(ex_id, "failed", ms, attempts, last_err)
            sink.emit(phase, "agent_failed", f"{name_en} failed after {attempts} attempts",
                      f"فشل {name_ar} بعد {attempts} محاولات", agent_key=key, payload={"error": last_err})
            return []

        narrative = None
        if rt.llm and findings:
            try:
                narrative = narrate(rt.llm, name_en, ctx.intake.get("question", ""), [f.to_dict() for f in findings])
            except Exception as exc:  # noqa: BLE001
                sink.emit(phase, "warning", f"{name_en}: LLM narrative unavailable ({type(exc).__name__}); "
                          f"structured findings retained", f"{name_ar}: السرد اللغوي غير متاح؛ تم الاحتفاظ بالنتائج المنظمة",
                          agent_key=key)
        ms = (time.perf_counter() - t0) * 1000
        sink.finish_execution(ex_id, "completed", ms, attempts, narrative=narrative)
        for f in findings:
            f.phase = phase if phase != "independent_analysis" else f.phase
            sink.emit(phase, "agent_finding", f.text_en, f.text_ar, agent_key=key,
                      payload={"code": f.code, "claim_type": f.claim_type, "stance": f.stance,
                               "strategy_key": f.strategy_key, "confidence": f.confidence,
                               "execution_id": ex_id})
        sink.emit(phase, "agent_completed", f"{name_en} completed ({len(findings)} findings, {ms:.0f} ms)",
                  f"اكتمل {name_ar} ({len(findings)} نتائج)", agent_key=key,
                  payload={"findings": len(findings), "duration_ms": round(ms, 1), "attempts": attempts,
                           "execution_id": ex_id, "narrative": narrative})
        for f in findings:
            f.__dict__["execution_id"] = ex_id
        return findings

    def fdicts(fs: list[Finding]) -> list[dict[str, Any]]:
        out = []
        for f in fs:
            d = f.to_dict()
            d.pop("evidence_quality", None)
            out.append({**d, "execution_id": f.__dict__.get("execution_id")})
        return out

    # ------------------------------------------------------------------ nodes
    @stage("intake")
    def intake(state: PipelineState):
        return {"_event_payload": {"intake": state.get("intake", {})}}

    @stage("data_validation")
    def data_validation(state: PipelineState):
        rep = validate_baseline(Baseline(**state["baseline"]))
        for c in rep.checks:
            if c.severity in ("warning", "error"):
                sink.emit("data_validation", "warning", f"{c.code}: {c.title_en}", f"{c.code}: {c.title_ar}",
                          payload={"severity": c.severity, "code": c.code})
        return {"validation": rep.model_dump(),
                "_event_payload": {"quality_score": rep.quality_score, "has_errors": rep.has_errors}}

    @stage("agent_assignment")
    def agent_assignment(state: PipelineState):
        sink.emit("agent_assignment", "message",
                  f"Assigned {len(PHASE1_AGENTS)} specialist agents for parallel independent analysis "
                  f"(mode: {mode.replace('_', ' ')})",
                  f"تم تكليف {len(PHASE1_AGENTS)} وكلاء متخصصين للتحليل المستقل المتوازي",
                  payload={"agents": PHASE1_AGENTS, "mode": mode})
        sink.emit("independent_analysis", "stage_started", "Independent analysis started", "بدء: التحليل المستقل")
        return {}

    def make_phase1(key: str):
        def node(state: PipelineState):
            fs = run_agent(key, "independent_analysis", rules_for(state).PHASE1[key], _ctx(state))
            if not fs:
                return {"warnings": [f"{key} produced no findings"]}
            return {"findings": fdicts(fs)}
        return node

    @stage("scenario_generation")
    def scenario_generation(state: PipelineState):
        sink.emit("independent_analysis", "stage_completed", "Independent analysis completed", "اكتمل: التحليل المستقل",
                  payload={"findings": len(state.get("findings", []))})
        futures = build_futures(DecisionControls(**state["controls"]))
        for f in futures:
            sink.emit("scenario_generation", "message", f"Composed {f.key}: {f.name_en} (levers proposed by "
                      f"{', '.join(f.proposed_by)})", f"تكوين {f.name_ar}", agent_key="orchestrator",
                      payload={"key": f.key, "levers": f.levers.model_dump()})
        return {"scenarios": [f.model_dump() for f in futures]}

    @stage("quantitative_simulation")
    def quantitative_simulation(state: PipelineState):
        sim = run_full_simulation(Baseline(**state["baseline"]), DecisionControls(**state["controls"]),
                                  rt.sim_config, rt.params, rt.economics)
        summary = {k: {"savings_pct_p50": f["summary"]["savings_pct_at_deadline"]["p50"],
                       "net_benefit_p50": f["summary"]["net_benefit_12m"]["p50"]} for k, f in sim["futures"].items()}
        sink.emit("quantitative_simulation", "message",
                  f"Monte Carlo: {sim['meta']['iterations']} iterations × 3 futures + baseline, seed {sim['meta']['seed']}, "
                  f"{sim['meta']['elapsed_ms']:.0f} ms (fingerprint {sim['meta']['input_fingerprint']})",
                  f"مونت كارلو: {sim['meta']['iterations']} تكرار × 3 خيارات، البذرة {sim['meta']['seed']}",
                  payload={"meta": sim["meta"], "summary": summary})
        return {"simulation": sim}

    @stage("agent_court")
    def agent_court(state: PipelineState):
        ctx = _ctx(state)
        rules = rules_for(state)
        new: list[Finding] = []
        for key in ["cfo", "delivery", "hr", "coo", "legal", "strategy", "risk"]:
            ctx.findings = [_finding_from(f) for f in state.get("findings", [])] + new
            new += run_agent(key, "court", rules.PHASE2[key], ctx)
        all_f = [_finding_from(f) for f in state.get("findings", [])] + new
        ctx.findings = all_f

        ex_id = sink.start_execution("redteam", "court", mode)
        sink.emit("agent_court", "agent_started", "Red Team Agent challenging positions", "الفريق الأحمر يتحدى المواقف",
                  agent_key="redteam")
        t0 = time.perf_counter()
        objections = rules.redteam_challenge(ctx, all_f)
        for o in objections:
            sink.emit("agent_court", "objection", o.text_en, o.text_ar, agent_key="redteam",
                      payload={"target_agent": o.target_agent, "severity": o.severity, "type": o.objection_type,
                               "strategy_key": o.strategy_key})
        objections = rules.respond(ctx, objections)
        for o in objections:
            sink.emit("agent_court", "response", o.response_en or "", o.response_ar or "", agent_key=o.response_by,
                      payload={"resolution": o.resolution, "type": o.objection_type})
        sink.finish_execution(ex_id, "completed", (time.perf_counter() - t0) * 1000, 1)

        collisions = rules.detect_collisions(ctx, all_f)
        for c in collisions:
            sink.emit("agent_court", "collision", c["title_en"], c["title_ar"], agent_key="orchestrator",
                      payload={"rule_code": c["rule_code"], "severity": c["severity"], "strategy_key": c["strategy_key"]})
        return {"findings": fdicts(new), "objections": [o.to_dict() for o in objections], "collisions": collisions,
                "_event_payload": {"objections": len(objections), "collisions": len(collisions)}}

    @stage("risk_assessment")
    def risk_assessment(state: PipelineState):
        ctx = _ctx(state)
        risks = rules_for(state).risk_register(ctx)
        high = [r for r in risks if r["severity"] in ("high", "critical")]
        sink.emit("risk_assessment", "message", f"{len(risks)} quantified risks; {len(high)} high/critical",
                  f"{len(risks)} مخاطر محسوبة؛ {len(high)} عالية/حرجة", agent_key="risk")
        feas = feasibility_search(ctx, rt.params, rt.economics)
        sink.emit("risk_assessment", "message", f"Feasibility search: {len(feas)} timeline/strategy combinations simulated",
                  f"بحث الجدوى: محاكاة {len(feas)} تركيبة", agent_key="orchestrator")
        return {"risks": risks, "feasibility": feas}

    @stage("governance_review")
    def governance_review(state: PipelineState):
        from ..governance.service import evaluate_strategy

        ctx = _ctx(state)
        gov = {}
        for k, f in state["simulation"]["futures"].items():
            g = evaluate_strategy(rt.policies, future=f, controls=state["controls"], collisions=state["collisions"],
                                  dataset_has_errors=ctx.validation.has_errors)
            gov[k] = g
            sink.emit("governance_review", "policy_decision",
                      f"Future {k}: {g['outcome'].replace('_', ' ')}" + (f" — roles: {', '.join(g['required_roles'])}" if g['required_roles'] else ""),
                      f"المستقبل {k}: {g['outcome']}", agent_key="governance",
                      payload={"strategy_key": k, "outcome": g["outcome"], "roles": g["required_roles"],
                               "deny": [d["code"] for d in g["deny_reasons"]]})
        # Proof that agents cannot self-execute: evaluate an agent-originated execute request.
        probe = evaluate_strategy(rt.policies, future=state["simulation"]["futures"]["A"], controls=state["controls"],
                                  collisions=state["collisions"], dataset_has_errors=ctx.validation.has_errors,
                                  actor_type="agent", mode="execute")
        sink.emit("governance_review", "policy_decision",
                  f"Agent-initiated execution request: {probe['outcome']} ({', '.join(d['code'] for d in probe['deny_reasons'])})",
                  f"طلب تنفيذ من وكيل: {probe['outcome']}", agent_key="governance",
                  payload={"probe": True, "outcome": probe["outcome"]})
        ex_id = sink.start_execution("governance", "governance", mode)
        gf = governance_findings(ctx, gov) + rules_for(state).ethics_findings(ctx)
        sink.finish_execution(ex_id, "completed", 0.0, 1)
        for f in gf:
            f.__dict__["execution_id"] = ex_id
            sink.emit("governance_review", "agent_finding", f.text_en, f.text_ar, agent_key="governance",
                      payload={"code": f.code, "strategy_key": f.strategy_key, "stance": f.stance})
        return {"governance": {"futures": gov, "agent_execution_probe": {"outcome": probe["outcome"],
                                                                        "deny": [d["code"] for d in probe["deny_reasons"]]}},
                "findings": fdicts(gf)}

    @stage("executive_recommendation")
    def executive_recommendation(state: PipelineState):
        ctx = _ctx(state)
        rec = build_recommendation(ctx, ctx.findings, state["collisions"], state["governance"]["futures"],
                                   state["feasibility"])
        sink.emit("executive_recommendation", "message", rec["headline_en"], rec["headline_ar"], agent_key="orchestrator",
                  payload={"recommended_strategy": rec["recommended_strategy"], "status": rec["status"],
                           "majority_differs": rec["majority_differs"]})
        return {"recommendation": rec}

    g = StateGraph(PipelineState)
    for name, fn in [("intake", intake), ("data_validation", data_validation), ("agent_assignment", agent_assignment),
                     ("scenario_generation", scenario_generation), ("quantitative_simulation", quantitative_simulation),
                     ("agent_court", agent_court), ("risk_assessment", risk_assessment),
                     ("governance_review", governance_review), ("executive_recommendation", executive_recommendation)]:
        g.add_node(name, fn)
    for key in PHASE1_AGENTS:
        g.add_node(f"agent_{key}", make_phase1(key))
    g.add_edge(START, "intake")
    g.add_edge("intake", "data_validation")
    g.add_edge("data_validation", "agent_assignment")
    for key in PHASE1_AGENTS:
        g.add_edge("agent_assignment", f"agent_{key}")
    g.add_edge([f"agent_{k}" for k in PHASE1_AGENTS], "scenario_generation")
    g.add_edge("scenario_generation", "quantitative_simulation")
    g.add_edge("quantitative_simulation", "agent_court")
    g.add_edge("agent_court", "risk_assessment")
    g.add_edge("risk_assessment", "governance_review")
    g.add_edge("governance_review", "executive_recommendation")
    g.add_edge("executive_recommendation", END)
    return g.compile(checkpointer=InMemorySaver())


def run_pipeline(rt: Runtime, initial: PipelineState) -> PipelineState:
    graph = build_graph(rt)
    return graph.invoke(initial, config={"configurable": {"thread_id": initial["run_id"]}, "recursion_limit": 50})


__all__ = ["run_pipeline", "Runtime", "STAGES", "PipelineState", "Objection"]
