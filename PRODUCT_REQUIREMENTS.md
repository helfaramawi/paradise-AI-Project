# Product Requirements & Traceability

## 1. Product

**Future Mirror AI** is an enterprise decision-intelligence and simulation platform. It turns a strategic question into a structured case, analyses it with specialist agents, simulates alternative futures quantitatively, challenges the result adversarially, and gates every consequential action behind enforceable policy and human approval. It then compares the forecast with reality.

**MVP decision type:** Enterprise Operating Cost Optimisation (synthetic demo company: EGP 120M operating costs, 150 employees, 18 projects, EGP 180M revenue).

## 2. Personas

CEO (decides; approves above EGP 5M), CFO (financial approval), COO (delivery sign-off), General Counsel (contract review), HR Director (workforce review), Decision Analyst (prepares cases), Platform Admin (users, policies, emergency stop), Viewer (board observer).

## 3. Requirements

| ID | Requirement |
|---|---|
| R1 | Structured decision intake (EN/AR) with confirmed interpretation |
| R2 | Validate enterprise data, including financial consistency; label synthetic data |
| R3 | ≥ 9 specialist agents + orchestrator; real orchestration framework |
| R4 | Agents run independently (in parallel); structured, evidenced findings with claim types |
| R5 | Agent Court: positions, evidence, assumptions, confidence, objections, responses, unresolved conflicts, verdict, required approvals |
| R6 | Disagreement resolved by evidence quality, policy, uncertainty and authority — not majority vote |
| R7 | Quantitative simulation separate from LLMs: Monte Carlo, best/base/worst, sensitivity, constraints, reproducible seeds, documented distributions |
| R8 | Three Futures (A/B/C) with all listed metrics, side-by-side comparison, interactive sliders that trigger recalculation |
| R9 | Live execution visualisation with real progress (SSE/WebSocket), warnings, failures, retries |
| R10 | Future Collision Detector based on structured rules |
| R11 | Decision Time Machine (today, months 1/3/6/12) driven by the model; compare futures at the same month |
| R12 | Governance: RBAC, agent authority limits, policy enforcement outside prompts, human-in-the-loop, separation of duties, audit trail, emergency stop, timeouts, budget limits, prompt-injection defences, tenant isolation; can deny what all agents recommend |
| R13 | Human approval workflow |
| R14 | Reality Feedback Loop: predicted vs actual, forecast error, calibration, explanations; no automatic production model changes |
| R15 | Bilingual EN/AR across UI, findings and reports; RTL; localised numbers |
| R16 | Executive reports (PDF + Excel) distinguishing facts, estimates, assumptions and recommendations |
| R17 | Connectors: working synthetic ERP, CSV/Excel import, Odoo, Dynamics 365, SAP S/4HANA, REST and SQL adapters; mapping, validation and reconciliation; read-only |
| R18 | Automation via n8n: dry-run, approval gates, idempotency, retries, audit; no autonomous consequential execution |
| R19 | Persistence with migrations, referential integrity and traceability to data and model versions |
| R20 | Authentication, organisation/tenant workspace |
| R21 | 16 functional screens; premium dark theme plus light theme; responsive (desktop/tablet) |
| R22 | Docker deployment, environment configuration, reverse proxy, health checks, volumes |
| R23 | Automated tests; never disguise mock results as real AI execution |

## 4. Requirements traceability matrix

| Req | Implementation | Verification |
|---|---|---|
| R1 | `agents/intake.py`, `api/decisions.py` (`/decisions/parse`, `/decisions`), `pages/IntakeWizard.tsx` | `test_intake_parser_english_and_arabic`, `test_intake_strips_control_chars`, E2E scene 1 |
| R2 | `simulation/validation.py`, `dataset_versions.provenance`, header chip *Synthetic data* | `test_validation_detects_margin_inconsistency_and_accepts_consistent_data`, `test_category_mismatch_detected`, `test_dataset_versioning_and_import` |
| R3 | `agents/orchestrator.py` (LangGraph `StateGraph`), `agents/domain.py`, `agents/court.py`, `agents/base.py` (`AGENT_CATALOG`) | `test_pipeline_produces_full_dossier`, `test_events_cover_all_stages_and_are_real` |
| R4 | parallel fan-out edges + `operator.add` reducer; `Finding`/`Evidence` dataclasses | `test_findings_are_bilingual_and_evidenced` |
| R5 | `court.py` (`redteam_challenge`, `respond`, `governance_findings`), `pages/AgentCourt.tsx` | `test_red_team_challenges_unverified_skill_assumption`, E2E scene 3 |
| R6 | `agents/recommend.py` | `test_recommendation_is_not_majority_vote`, `test_governance_blocks_termination_even_if_every_agent_supports` |
| R7 | `simulation/engine.py`, `delivery_des.py`, `assumptions.py`, SIMULATION_MODEL.md | `test_reproducible_with_same_seed`, `test_different_seed_changes_samples_not_expected_case`, `test_sensitivity_sorted_and_documented`, `test_des_common_random_numbers`, `test_savings_accounting_identity`, `test_contractor_reduction_monotonically_increases_shortfall`, `test_compressed_timeline_raises_cost`, `test_fingerprint_changes_with_inputs` |
| R8 | `simulation/futures.py`, `/simulation/run`, `pages/ThreeFutures.tsx`, `components/Controls.tsx` | `test_what_if_recalculates`, `test_invalid_controls_rejected`, E2E scene 5 (slider → "What-if mode") |
| R9 | `services/events.py`, SSE `/runs/{id}/events`, `pages/ExecutionRoom.tsx` | `test_sse_stream_replays_events`, `test_agent_retry_and_failure_handling`, E2E scene 2 |
| R10 | `agents/collision.py` | `test_collision_detector_finds_contractor_delivery_conflict`, `test_collisions_disappear_when_strategy_is_safe`, E2E scene 4 |
| R11 | trajectories in `engine.py`, `pages/TimeMachine.tsx` | E2E scene 6 |
| R12 | `governance/engine.py` (14 policies), `governance/service.py`, `security.py` (RBAC), `services/audit.py`, `/admin/emergency-stop`, `events.EventSink.check`, `intake.sanitize`, `llm.py` prompt hardening | `test_agent_execution_always_denied`, `test_locked_policy_cannot_be_changed`, `test_disabled_policy_is_skipped`, `test_rbac_viewer_cannot_create_or_run`, `test_tenant_isolation`, `test_emergency_stop_blocks_runs`, `test_concurrent_run_rejected_and_cancel`, `test_audit_chain_valid`, `test_requires_auth`, `test_bad_password_rejected`, `test_security_headers` |
| R13 | `api/governance.py` (approval requests, decide), `pages/ApprovalCenter.tsx` | `test_approval_workflow_with_separation_of_duties`, `test_requester_cannot_approve_own_request`, `test_blocked_strategy_cannot_enter_approval`, `test_acknowledgement_required`, E2E scenes 7–8 |
| R14 | `services/feedback.py`, `/outcomes`, `/calibration-proposal`, `/models/{id}/promote`, `pages/Outcomes.tsx` | `test_reality_feedback_loop_and_model_governance` |
| R15 | `i18n/dict.ts` (≈350 keys × 2), `lib/app.tsx` (dir, `Intl` ar-EG), bilingual findings, `reports.py` Arabic shaping | `test_findings_are_bilingual_and_evidenced`, `test_reports_pdf_and_excel_both_languages`, E2E Arabic RTL screenshots |
| R16 | `services/reports.py` | `test_reports_pdf_and_excel_both_languages` |
| R17 | `connectors/*` (`d365.py`, `sap_rest.py`, `sql_source.py`), `api/data.py`, `pages/DataConnections.tsx`, `components/ConnectorSettings.tsx` | `test_connectors_honest_status`, `test_connector_settings_validation_and_d365`, `tests/test_connectors_d365.py`, `tests/test_connectors_more.py`, `test_dataset_versioning_and_import` |
| R18 | `automation/n8n.py`, `api/operations.py`, `automation/n8n/*.json`, `pages/Automation.tsx` | `test_automation_dry_run_idempotent_and_live_blocked`, `test_automation_live_consequential_blocked` |
| R19 | `models.py` (35 tables), `alembic/versions/0001_initial_schema.py` | whole suite on SQLite **and** PostgreSQL; `test_persistence_survives_restart`; Docker restart check |
| R20 | `api/auth.py`, `security.py`, tenants/organisations | `test_requires_auth`, `test_tenant_isolation` |
| R21 | `frontend/src/pages/*` (17 screens), `components/AppShell.tsx`, theme toggle | E2E demo (26 screenshots), `tablet layout renders core screens` (no horizontal overflow at 820 px) |
| R22 | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `.env.example` | images built; stack healthy; E2E passed against the Docker stack; data persisted across `docker compose restart` |
| R23 | test suites; run `mode` labels; `paced_ms` vs `compute_ms`; synthetic labels | TEST_REPORT.md |

## 5. Required screens → implementation

| # | Screen | Route | File |
|---|---|---|---|
| 1 | Executive Command Center | `/` | `CommandCenter.tsx` |
| 2 | New Decision Workspace | `/decisions` | `Workspace.tsx` |
| 3 | Decision Intake Wizard | `/decisions/new` | `IntakeWizard.tsx` |
| 4 | Live Agent Execution Room | `/execution/:runId` | `ExecutionRoom.tsx` |
| 5 | AI Agent Court (+ Collision Detector) | `/court` | `AgentCourt.tsx` |
| 6 | Three Futures Comparison | `/futures` | `ThreeFutures.tsx` |
| 7 | Simulation Laboratory | `/lab` | `SimulationLab.tsx` |
| 8 | Financial Impact Dashboard | `/financial` | `FinancialImpact.tsx` |
| 9 | Risk and Uncertainty Explorer | `/risk` | `RiskExplorer.tsx` |
| 10 | Decision Approval Center | `/approvals` | `ApprovalCenter.tsx` |
| 11 | Decision History | `/history` | `History.tsx` |
| 12 | Actual vs Predicted Outcomes | `/outcomes` | `Outcomes.tsx` |
| 13 | Enterprise Data Connections | `/data` | `DataConnections.tsx` |
| 14 | Automation Workflow Center | `/automation` | `Automation.tsx` |
| 15 | AI Governance and Policy Center | `/governance` | `Governance.tsx` |
| 16 | Administration and Security | `/admin` | `Admin.tsx` |
| + | Decision Time Machine | `/time-machine` | `TimeMachine.tsx` |

## 6. Out of scope for the MVP

Additional decision categories; live ERP writes; SSO; durable mid-run resume; certified legal or financial advice.
