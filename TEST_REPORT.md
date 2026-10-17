# Test Report

**Date:** 2026-10-15 · **Commit:** see `git log` · **Environment:** Linux container, Python 3.13, Node 22, PostgreSQL 16, Docker 29, Chromium (Playwright 1.56).

Everything below was actually executed in this environment. Results are reported as observed.

## 1. Summary

| Suite | Command | Result |
|---|---|---|
| Lint (ruff E/F/W/B) | `cd backend && ruff check app tests` | ✅ all checks passed |
| Backend unit + integration + security (SQLite) | `cd backend && pytest -q` | ✅ **71 passed**, 1 opt-in live test skipped (≈12 s) |
| Same suite on **PostgreSQL 16** | `FM_DATABASE_URL=postgresql+psycopg2://… pytest -q` | ✅ **71 passed**, 1 opt-in live test skipped (≈12 s) |
| Frontend type check (strict) + production build | `npm run build` | ✅ no type errors, build OK |
| End-to-end, dev stack (Vite + uvicorn + PostgreSQL) | `npx playwright test` | ✅ 2/2 passed (8-scene demo ≈ 50 s; tablet layout) |
| End-to-end, **Docker stack** (nginx + API + PostgreSQL, fresh volume) | `E2E_BASE_URL=http://localhost:8080 npx playwright test` | ✅ 2/2 passed |
| Restart persistence (Docker) | `docker compose restart`, then compare decisions + audit chain | ✅ identical data; hash chain valid |
| Performance smoke test | `python scripts/perf_test.py http://localhost:8080` | ✅ see §5 |

One defect was found **only by running against PostgreSQL** (a `VARCHAR(20)` column too short for `require_acknowledgement`; SQLite does not enforce lengths). It was fixed and the migration regenerated. Both databases now run in CI.

## 2. Backend tests (71 + 1 opt-in)

**Simulation (`test_simulation.py`, 14)**
- reproducibility (same seed → identical summaries and trajectories);
- seed changes affect samples but not the deterministic expected case;
- status-quo baseline has zero savings and zero delay;
- monotonic delay increase with contractor reduction;
- savings accounting identity (software 12 × 0.22);
- infeasible 20% target reported; lower target can be met;
- termination lever violates C2;
- sensitivity sorted and covering all 14 parameters;
- DES common random numbers (zero reduction → zero extra delay; large reduction → projects at risk);
- data validation detects the margin inconsistency and accepts consistent data;
- category mismatch detected;
- compressed timeline raises cost;
- input fingerprint changes with inputs.

**Agents and governance (`test_governance_agents.py`, 14)**
- condition operators;
- **governance blocks terminations even when every agent supports them**, and the recommendation then returns no strategy;
- agent-originated execution always denied;
- approval roles scale with impact plus the GOV-011 acknowledgement;
- disabled policy skipped;
- live consequential automation denied (GOV-003 + GOV-014);
- collision detector finds COL-01 (A) and COL-02, with the positions of CFO and Delivery;
- collisions disappear under a safe configuration;
- Red Team challenges the unverified skill assumption and the data integrity, every objection gets a response, and some remain unresolved;
- all findings bilingual (Arabic script verified) and evidenced;
- **recommendation ≠ majority vote** (three weak supporters vs one strong);
- EN/AR intake parsing (Eastern Arabic digits);
- control-character sanitisation;
- lever range validation.

**Dynamics 365 connectors (`test_connectors_d365.py`, 5)**, run against a mocked Entra ID token endpoint and OData service:
- longest-prefix account mapping, with unmatched accounts ignored and reported;
- F&O client-credentials token request (scope `<env>/.default`), legal-entity filter with `cross-company`, `@odata.nextLink` paging, main-account segment parsing, reconciliation;
- authentication failure, missing settings and missing secret reported without raising;
- the row limit is enforced;
- Business Central `generalLedgerEntries` URL, date filter and debit − credit amounts.

**SAP, REST and SQL connectors (`test_connectors_more.py`, 9 + 1 opt-in live test)**:
- SAP S/4HANA: OData v2 `A_JournalEntryItemBasic` filter (company code, ledger, posting-date range, `sap-client`), basic auth, `__next` paging, leading-zero stripping of G/L accounts; missing password and HTTP 401 reported;
- REST: nested records path, dotted account/amount fields, relative next-page links, bearer token only when configured;
- SQL: a real SQLite ledger: grouped sums within the period, out-of-period and unmapped rows excluded; identifier injection (`table; DROP TABLE`) rejected and the data left untouched; missing host/password and a missing view reported.

- SQL Server: the `pymssql` driver is installed (fails if it is missing from the image); driver errors become readable messages (permission denied, login failed, server unreachable).
- `test_sql_server_live` runs when `FM_TEST_MSSQL_HOST/PORT/USER/PASSWORD` are set. It passed against **SQL Server 2022** with a login that may only SELECT from one view.

The SQL connector was also run **end to end through the UI against a PostgreSQL 16 database** (read-only transaction): Test succeeded, and Sync produced the expected category totals as a new dataset version tagged `imported`. Inside the rebuilt backend image it read the same totals from **SQL Server 2022**, and reading the underlying table was refused for the least-privilege login.

**API, security and integration (`test_api.py`, 29)**
- health and readiness; 401 without or with a bad token; bad password; RBAC (viewer → 403); security headers;
- **tenant isolation** (a second tenant gets 404 and an empty list);
- full pipeline dossier (8 agent types, ≥ 3 Red Team objections, COL-01, 4 scenarios, model version, ≥ 15 executions, A denied, agent probe denied);
- events cover all 10 stages with real compute time; SSE stream replays history and ends;
- concurrent run rejected (409) and cancellation → `cancelled`;
- **retry and failure handling** (injected failures: HR recovers on retry, Legal fails after 3 attempts, the run still completes);
- emergency stop blocks runs (423) and releases;
- what-if recalculation changes the fingerprint and the outputs; invalid controls → 422; custom lab strategy;
- locked policy → 403; blocked strategy → `blocked` approval; acknowledgement required → 422;
- **approval workflow with separation of duties** (wrong role 403, viewer 403, all roles → approved, double approval 409); the requester cannot approve their own request (GOV-013);
- automation dry-run is idempotent (same run id) and live consequential is blocked;
- reality feedback loop (synthetic actuals labelled, delay above P90 → skill-match diagnostic, manual outcome, candidate model, analyst promotion 403, admin promotion 200);
- PDF and Excel in EN and AR;
- dataset versioning (provenance → user_input, DQ-002 cleared) and CSV import reconciliation (unmapped category reported, bad file 422);
- connector honesty (unconfigured adapters report missing settings, Odoo not verified, synthetic ERP reconciles to 0, secret keys rejected);
- connector settings validation (bad URL, bad date, reversed period, unknown category, OData-injection characters and secret keys all rejected with 422; analyst gets 403; secret presence is reported without ever returning the value);
- audit chain valid; persistence across a new application instance; dashboard.

## 3. End-to-end demo (`frontend/e2e/demo.spec.ts`)

Drives the real UI against the real API:

1. login → chips show *Synthetic data* and *no LLM*;
2. intake wizard (demo question → parse → controls → launch);
3. Live Execution Room receives SSE events until the dossier is ready;
4. Agent Court shows the rule-based mode banner and the verdict; the Collision Detector cards appear;
5. Three Futures: a slider change triggers recalculation ("What-if mode");
6. Time Machine month 6;
7. Financial, Risk, Lab (run a custom strategy), History, Data, Automation, Governance;
8. Approval Center: Future A shows GOV-009, Future B submitted with acknowledgement → Pending;
9. sign out → CFO approves (role badge updates);
10. Actual vs Predicted: synthetic actuals plus diagnostics;
11. Arabic: `<html dir="rtl">`, Court, Futures and Time Machine in Arabic;
12. admin screen, light theme.

The test **asserts that no uncaught page errors occurred** during the run. A second test checks the tablet viewport (820 × 1180): no horizontal overflow on Three Futures. It produced the 27 screenshots in `docs/screenshots/`.

## 4. Security tests (subset of the above)

Authentication required · invalid token · wrong password · login rate limiting (implemented, not load-tested) · RBAC per route · tenant isolation · separation of duties · locked policies · agent execution denial · external-write denial · consequential automation denial · emergency stop · secret keys refused in connector config · upload size/type/row limits and malformed-file rejection · control-character sanitisation of decision text · hash-chained audit verification · security headers.

**Not performed:** penetration test, dependency CVE scan, fuzzing, load test beyond the smoke test below.

## 5. Performance (Docker stack, single uvicorn worker, 4 vCPU)

| Scenario | Result |
|---|---|
| What-if simulation, 3 futures + baseline, 1 000 iterations, with sensitivity (14 × 2 deterministic runs per future) and SimPy DES — sequential n=10 | p50 **149 ms**, max 200 ms |
| What-if with 10 000 iterations | 408 ms |
| 24 concurrent what-if requests (8 workers) | 5.7 req/s, p95 1.76 s (single worker; CPU-bound) |
| Full multi-agent pipeline (10 stages, 16 agent executions, 2 000-iteration MC + sensitivity + DES + 9-run feasibility search), no pacing | compute **≈ 1.0 s**, 124 events |

## 6. Acceptance criteria (brief §22)

| # | Criterion | Evidence |
|---|---|---|
| 1 | Starts with documented commands | README / DEPLOYMENT_GUIDE; Docker stack healthy |
| 2 | Frontend talks to the real backend | E2E on both stacks |
| 3 | DB persists decisions and results | 35-table schema; restart test |
| 4 | User can create a decision | E2E scene 1 |
| 5 | Agents run through working orchestration | LangGraph pipeline; `test_pipeline_produces_full_dossier` |
| 6 | Real execution status visible | SSE Execution Room; `test_sse_stream_replays_events` |
| 7 | Scenarios generated and stored | `scenarios`, `simulation_results` |
| 8 | Reproducible simulation | `test_reproducible_with_same_seed` |
| 9 | Constraints enforced | C1–C6, GOV policies, tests |
| 10 | Disagreements displayed | Agent Court, objections, collisions |
| 11 | Governance can block prohibited actions | GOV-001/002/009 tests; Future A blocked in the E2E |
| 12 | Human approval required where configured | approval workflow tests |
| 13 | Arabic and English work | E2E RTL; bilingual findings and reports |
| 14 | Demo runs on synthetic data | seed workspace, labels |
| 15 | Restart without data loss | Docker restart; `test_persistence_survives_restart` |
| 16 | Automated tests pass | §1 |
| 17 | Errors handled gracefully | 4xx contracts, agent-failure degradation, UI error boxes, global 500 handler |
| 18 | Desktop and tablet | 1440 px E2E + 820 px test |
| 19 | No mock results disguised as real AI | `mode` labels, rule-based banner, pacing disclosure, synthetic labels |
| 20 | Essential functionality demonstrable end to end | E2E demo |

## 7. Known gaps in testing

- The LLM providers (Anthropic, OpenAI, Ollama) are implemented but **not exercised against live endpoints** (no credentials in this environment). The narration path is covered only by its failure handling (a warning, with the structured findings kept).
- The Odoo, Dynamics 365, SAP and REST adapters have not been run against real customer systems (D365/SAP/REST are covered by mocked HTTP tests). The MySQL driver is not in the image. n8n live delivery has not been run against a real n8n instance (the dry-run path is tested).
- No frontend unit tests (components are covered through E2E).
- Visual review covered the screens in the screenshot set; there are no formal accessibility audits (axe) or cross-browser runs (Chromium only).
