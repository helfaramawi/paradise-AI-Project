# Project Status

**Current phase:** Phase 6 (Quality & Release) completed for the MVP scope. **Overall:** MVP functional, tested and deployable.

## Phase summary

| Phase | Deliverables | Status |
|---|---|---|
| 1 Architecture & foundation | architecture spec, technology decisions, repo structure, DB design + migration, API contracts (OpenAPI), security model, Docker, app shell | ✅ |
| 2 Core decision engine | intake, data validation, LangGraph orchestration, structured findings, scenario generation, persisted execution history | ✅ |
| 3 Simulation & intelligence | monthly model, Monte Carlo, constraints, comparison, sensitivity, SimPy DES, collision detection, governance evaluation, feasibility search | ✅ |
| 4 Premium executive experience | cockpit, Agent Court, Three Futures, Time Machine, charts, EN/AR + RTL, dark/light | ✅ |
| 5 Automation & integration | n8n client (dry-run, idempotency, gates, retries), synthetic ERP, CSV/Excel import, Odoo adapter, approval workflow, notifications (dry-run) | ✅ (live n8n/Odoo unverified) |
| 6 Quality & release | 56 backend tests (SQLite + PostgreSQL), Playwright E2E (dev + Docker), security tests, perf smoke, deployment verification, docs, demo script, screenshots | ✅ |

## Technical decisions (log)

1. Rule-based analytical agents by default, with an optional LLM narration layer. Keeps numbers deterministic and honest, and works on-prem and offline.
2. LangGraph for orchestration (parallel fan-out, reducers, checkpointer); events persisted to the database and streamed by SSE.
3. Court convened **after** simulation, so the debate cites quantitative evidence (see AGENT_ARCHITECTURE §2).
4. In-process declarative policy engine modelled on OPA, to avoid an extra service in the MVP.
5. The dataset inconsistency (gross margin vs cost base) is surfaced, not hidden. Interpretation: opex = total cost base.
6. No Redis in the MVP (not justified yet); a daemon thread per run; a restart marks in-flight runs failed.
7. Arabic-capable font vendored so PDF reports work in air-gapped builds.

## Known limitations

- **LLM providers** implemented but not validated against live APIs in this environment. Default mode is rule-based and labelled as such.
- **Agent narratives** without an LLM are templated text generated from computed values. They are accurate and dynamic, but less varied than LLM prose.
- **Run durability:** the LangGraph checkpointer is in memory. A backend restart during a run marks it `failed`; the run does not resume.
- **Single decision category** (operating cost optimisation) and fixed A/B/C lever mixes; custom mixes only in the Simulation Lab.
- **Model:** uncalibrated priors; independent parameters (no correlations); linear ramps; proxy revenue effects; the DES uses mean shortfall.
- **Connectors:** Odoo adapter unverified; D365/SAP/REST/SQL are interfaces only. Read-only by design.
- **Automation:** live n8n delivery requires configuration and is untested here; schedules are metadata (no scheduler runs them yet).
- **Auth:** local accounts + JWT. No SSO/MFA; tokens are stored in `localStorage`.
- **Scale:** a single uvicorn worker in compose; concurrent heavy simulations are CPU-bound.
- **Frontend:** a ~400 KB vendor bundle (Recharts); no component unit tests; Chromium-only E2E.
- What-if slider results are not re-evaluated by agents or governance until the analysis is re-run (the UI states this).

## Known defects

None open. Fixed during verification:
- PostgreSQL varchar length on `governance_policies.effect`;
- Vite path alias;
- React Flow node measurement under rapid updates;
- Three Futures layout at 1440 px;
- Simulation Lab legend labels;
- oversized Recharts legends;
- governance over-blocking from decision-level collisions.

## Next-release backlog (prioritised)

1. Durable execution: queue (Redis + RQ/Celery) + `langgraph-checkpoint-postgres` for resumable runs.
2. Validate the LLM narration against Anthropic / OpenAI / Ollama; add LLM-generated *hypotheses* to the Red Team (clearly labelled), with evaluation sets.
3. Scheduler for automation workflows (scheduled analysis, KPI monitoring) and verified n8n delivery with signed webhooks.
4. Verify the Odoo connector against a test instance; implement D365 F&O / Business Central (OData) and SAP adapters.
5. Agent re-evaluation of what-if configurations ("promote what-if to analysis").
6. Parameter correlation (Gaussian copula) and Bayesian updating from observed outcomes; backtesting dashboard for candidate models.
7. SSO (OIDC/SAML), MFA, httpOnly-cookie sessions, per-tenant encryption keys.
8. Additional decision categories (pricing, capex, hiring plans, M&A screening).
9. OPA/Rego policy backend option; policy versioning UI with diff and approval.
10. Accessibility audit (axe), cross-browser E2E, frontend unit tests, bundle splitting.

## How to run

```bash
docker compose up -d --build            # http://localhost:8080 — demo users in README
cd backend && pytest -q                 # tests
cd frontend && npx playwright test      # E2E (stack running on :5173 or set E2E_BASE_URL)
```
