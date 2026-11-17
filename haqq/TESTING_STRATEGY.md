# HAQQ — Testing Strategy & Results

## Layers
| Layer | Where | What |
|---|---|---|
| Engine unit tests | `backend/tests/test_engines.py` (15) | clause extraction & pages, categories, Arabic clauses, number words & Arabic-Indic digits, classification, OCR of a scanned instruction, BOQ parsing, file sniffing, dates, Egyptian working days & holidays, deadline uncertainty, valuation arithmetic, event classification, injection guard, heading guard |
| Acceptance scenarios (API, real PostgreSQL, real files) | `backend/tests/test_scenarios.py` (7) | PRD scenarios 1–6 and 8 |
| Security | `backend/tests/test_security.py` (11) | scenario 7 tenant isolation (read, write, aggregates), RBAC, lockout, session revocation, MFA, rate limiting, upload validation, injection flag, versioning, audit chain, headers, separation of duties, plan limits |
| AI layer | `backend/tests/test_ai.py` (5) | not-configured path, tenant policy, structured output + citations + token metering, hallucinated citation rejection, RAG with LLM — using a provider *test double* (no network) |
| Evaluation gate | `backend/tests/test_eval.py` + `eval/` | labelled EN/AR clause set; accuracy thresholds |
| Browser e2e | `frontend/e2e/journey.spec.ts` (3) | AR-RTL default and EN-LTR switch, KPI drill-down, explainable entitlement → claim → document generation, site-engineer visibility |
| Static | `ruff`, `tsc --strict` | lint/type checks |

Tests run against a dedicated database rebuilt from the Alembic migration each session (so migrations are tested too),
with synchronous job processing and isolated storage.

## Latest results (this iteration)
* `pytest -q` → **39 passed**
* `npx playwright test` → **3 passed**
* `ruff check app tests eval` → clean; `tsc -b` → clean; `vite build` → OK
* `python -m eval.run_eval` → category 1.00 · notice period 1.00 · time-bar 1.00 · exclusion 1.00 · payment period 1.00 (n=19, synthetic)
* Not executed: live Anthropic API calls (no credentials in the environment); Docker image builds (sandbox has no access
  to Debian package mirrors); load/performance testing beyond functional runs (demo seed processes 25 documents incl.
  OCR in ≈6 s on 4 vCPU).

## Requirements traceability matrix
| Requirement | Implementation | Test(s) |
|---|---|---|
| S1 Contract analysis with source references | `engines/contract.py`, `services/pipeline.py` | `test_s1_contract_analysis_with_source_references`, `test_contract_clause_extraction_with_pages`, `test_arabic_contract_clauses` |
| S2 Additional works → provisions, conditions, missing evidence, explainable | `engines/entitlement.py` | `test_s2_additional_work_explainable_finding` |
| S3 Delay — relevant provisions & notice, **no automatic EOT** | `engines/entitlement.py` (`no_eot_conclusion`, status ceiling) | `test_s3_delay_event_does_not_conclude_eot` |
| S4 Missing notice — deadline + uncertainty | `engines/deadlines.py`, `services/discovery._sync_deadlines`, `services/notify.py` | `test_s4_notice_deadline_and_uncertainty`, `test_deadline_uncertainty_is_explicit`, `test_working_days_egypt_weekend_and_holidays` |
| S5 Claim draft with clauses, chronology, evidence, financials, missing info, review status | `services/claimdocs.py`, `services/claims.py` | `test_s5_full_journey_to_claim_package` |
| S6 Dashboard = database, drill-down | `services/dashboard.py` | `test_s6_dashboard_matches_database` |
| S7 Multi-tenant security | `core/deps.py` | `test_s7_*` (3 tests) |
| S8 Arabic & English incl. RTL documents | i18n, `claimdocs` RTL | `test_s8_*`, `test_s5_*` (Arabic DOCX bidi), Playwright RTL test |
| Never fabricate citations (AI) | `ai/service.py` | `test_hallucinated_citation_is_rejected` |
| Tenant AI data policy | `ai/service.py` | `test_org_policy_blocks_external_processing` |
| Uploaded documents untrusted | `ai/guard.py`, `pipeline` | `test_upload_validation_and_injection_flag`, `test_prompt_injection_guard` |
| Deterministic money | `engines/valuation.py` | `test_valuation_math_is_exact_and_transparent` |
| Subscription limits & usage | `services/subscription.py` | `test_plan_limits_enforced`, `test_valid_structured_output_*` (token metering) |
| Audit trail integrity | `core/audit.py` | `test_audit_chain_and_security_headers` |
