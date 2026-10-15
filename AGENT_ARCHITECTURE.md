# Agent Architecture

Source: `backend/app/agents/`.

## 1. Agents

| Key | Agent | Phase 1 (baseline analysis) | Phase 2 (simulated futures) |
|---|---|---|---|
| strategy | Chief Executive Strategy | objective, structural feasibility, success criteria | target feasibility across futures |
| cfo | CFO | addressable spend, profitability (flags DQ-002), cash | savings and net benefit per future (stance) |
| coo | COO | utilisation headroom, delay bottleneck, automation hypothesis | automation timing (B), transition disruption (C) |
| hr | HR | no-termination scope, unverified skills, retraining | capacity shortfall and utilisation per future |
| delivery | Project Delivery | contractor dependency | projects at risk (SimPy) and delay per future |
| legal | Legal & Compliance | missing contracts → review required; labour exposure | probability of contractual breach (as a *hypothesis*) |
| risk | Risk Management | data quality, uncertainty | Monte Carlo probabilities, top sensitivity driver |
| redteam | Red Team | — | objections (see §3) |
| governance | Ethics & Governance | — | reports policy-engine verdicts and ethical concerns (utilisation overload) |
| orchestrator | Chief Decision Orchestrator | graph control, scenario composition, recommendation | |

Every agent is a **deterministic analytical module**. Through read-only "tools" (dataset, validation, simulation, policies) it computes structured findings:

```
Finding = {agent, code, claim_type ∈ {fact, estimate, assumption, hypothesis, recommendation},
           topic, strategy_key, stance ∈ {support, oppose, conditional, neutral},
           text_en, text_ar, confidence, evidence[], assumptions[]}
Evidence = {source_type ∈ {dataset, validation, simulation, des, policy, assumption}, reference, label, value, verified}
```

`evidence_quality` is derived from the evidence mix: policy and dataset evidence weigh more than assumptions, and verified evidence gets a bonus. All statements are generated from the current inputs in both languages. **Nothing is a pre-written transcript**: change the dataset or the controls and the statements change.

**Authority:** every agent definition carries `{"can_execute": false, "can_write_external": false, "tools": [read-only…]}`. Agents have no execute tool, and the orchestrator probes the policy engine with an agent-originated execute request on every run (always denied by GOV-002) and logs the result.

## 2. Orchestration (LangGraph)

```
START → intake → data_validation → agent_assignment ─┬─ agent_strategy ─┐
                                                      ├─ agent_cfo      │
                                                      ├─ agent_coo      │  (parallel superstep;
                                                      ├─ agent_hr       │   findings merged by an
                                                      ├─ agent_delivery │   operator.add reducer)
                                                      ├─ agent_legal    │
                                                      └─ agent_risk ────┴─► scenario_generation
 → quantitative_simulation → agent_court → risk_assessment → governance_review → executive_recommendation → END
```

- **Ordering decision:** the brief lists *Agent Court* before *Scenario generation*. In this implementation agents first analyse the baseline independently, then the orchestrator composes the futures from the levers the agents motivated, simulates them, and **then** convenes the court. This way the debate is grounded in quantitative evidence rather than intuition.
- **Retries and timeouts:** each agent call runs in a worker with `agent_timeout_seconds` and up to 3 attempts. It emits `agent_retry` / `agent_failed` events. A failed agent degrades the run (a warning is recorded) rather than crashing it; this is tested with injected failures.
- **Cancellation and emergency stop:** checked before every stage and agent; `RunCancelled` ends the run as `cancelled`.
- **Pipeline timeout:** `pipeline_timeout_seconds`.
- **Checkpointing:** `InMemorySaver` with `thread_id = run_id`. Durable state is the persisted events and results. A restart marks in-flight runs `failed` explicitly.
- **Events:** every transition is a `workflow_events` row (stage started/completed, agent started/finding/completed/retry/failed, warnings, objections, responses, collisions, policy decisions, run_completed), streamed over SSE.
- **Presentation pacing:** an optional visible pause between stages. It is reported as `paced_ms` and is **excluded** from `compute_ms`.

## 3. AI Agent Court

1. **Positions:** phase-2 findings with stances per future.
2. **Red Team challenge rules** (`court.py`): explicit predicates that compute counter-evidence:
   - *unsupported_assumption*: the highest-savings case relies on skill match; quotes the delay and net benefit at the low bound from sensitivity.
   - *contradiction*: CFO supports while Delivery opposes the same future.
   - *optimism*: automation productivity (B) and implementation cost P90 ≫ expected.
   - *data_integrity*: the dataset fails DQ-002.
   - *infeasible_objective*: no future reaches the target.
   - *hidden_dependency*: the expense freeze cuts the training that the skill match depends on.
   - *adverse_scenario*: the P90 delay of the safest future.
3. **Responses:** the challenged agent answers with a quantified mitigation (for example, including the delivery loss in the case) and a resolution: `resolved` / `partially` / `unresolved`.
4. **Verdict:** §5.

## 4. Future Collision Detector (`collision.py`)

Structured rules over agent stances **and** simulation outputs (no free text):

| Rule | Condition | Severity score |
|---|---|---|
| COL-01 | contractor reduction > 0 ∧ CFO supports/conditional ∧ Delivery opposes | 0.25 + 0.06·projects_at_risk + 0.4·P(breach) + 0.02·peak shortfall |
| COL-02 | max achievable < target ∧ no-terminations | 0.5 + gap/20 |
| COL-03 | Future A: freeze ≥ 0.8 ∧ contractor cut | 0.35 |
| COL-04 | automation run-rate at deadline < 85% of month-12 | 0.2 + 0.5·(1 − ratio) |
| COL-05 | redesign ∧ median delay > acceptable | 0.2 + 0.08·excess |

Bands: ≥ 0.75 critical, ≥ 0.5 high, ≥ 0.25 medium. Each collision lists the conflicting positions, affected objectives, quantified consequences, alternative resolutions and whether human intervention is required. Strategy-specific critical collisions trigger GOV-009.

## 5. Recommendation (no majority vote)

`recommend.py`, in order:

1. **Governance veto:** denied futures are `not_acceptable`.
2. **Hard constraints** at the risk tolerance, plus any critical collision → `conditional`.
3. **Evidence-weighted support** = Σ stance_weight × confidence × evidence_quality (support +1, conditional +0.25, oppose −1).
4. **Quantitative tie-breakers:** P(delay acceptable), median net benefit.

A naive vote count is computed **only for transparency** (`naive_majority_winner`, `majority_differs`). A unit test constructs a case where three weak supporters would win a vote but one strong, well-evidenced position wins the recommendation. The output also includes realistic options from the feasibility search, next steps, a roadmap and a disclaimer.

## 6. LLM layer (optional)

`llm.py` provides `AnthropicProvider`, `OpenAIProvider` and `OllamaProvider`, selected by `FM_LLM_PROVIDER`. When one is configured, each agent's structured findings are sent with a system prompt that forbids inventing numbers, legal advice and action proposals. The user's question is wrapped in `<user_decision>` and declared untrusted. The JSON response `{en, ar}` is stored on `agent_executions.llm_narrative_*`, and the run is labelled `llm_augmented`. LLM failures emit a warning and keep the structured findings. **LLM output never changes numbers, stances or policy outcomes.** This path is implemented but was **not exercised against a live provider** in this environment (no API key).

## 7. Decision intake

`intake.py` uses regex/keyword parsing of English and Arabic (including Eastern Arabic digits) to extract the target, timeline, cost base and constraint flags. The wizard shows what was detected and the user confirms every field. Input is sanitised (control characters stripped, length capped).
