# HAQQ — Implementation Plan & Status

## Repository inspection (start of work)
* **Existing content:** the repository holds *Future Mirror AI*, a separate PAIS decision-simulation product
  (FastAPI + SQLAlchemy + Alembic + LangGraph backend, React/Vite/Tailwind frontend, Docker Compose, CI, guides).
  Nothing in it implements contract or claims intelligence.
* **Decision:** build HAQQ as a self-contained module in `haqq/`, reusing the proven stack and conventions but none of
  Future Mirror's domain code, and leaving Future Mirror untouched (no rewrites, no shared database).
* **Environment found:** Python 3.13, Node 22, PostgreSQL 16 (installed, stopped), Docker CLI. Missing and added:
  FastAPI/SQLAlchemy libs, Tesseract with Arabic data, `pgvector`.
* **Main technical risks:** OCR quality on poor scans; Arabic contract layout variety; clause-boundary detection on
  real contracts; deadline semantics (day type, triggers); hallucination if an LLM were allowed to decide.
  **Main business risks:** buyer trust in AI findings; data-confidentiality objections; long enterprise sales cycles;
  over-promising recoveries. Mitigations: deterministic + cited findings, opt-in AI, human gates, honest status labels.

## Phases (all executed in this iteration)
| Phase | Deliverable | Status | Evidence |
|---|---|---|---|
| 1 Foundation | auth, sessions, MFA, multi-tenancy, RBAC, orgs/projects, migrations, design system | ✅ | `core/`, `api/auth.py`, `api/org.py`, `alembic/`, security tests |
| 2 Document intelligence | uploads, OCR, PDF/DOCX/XLSX/e-mail, classification, clause repository, search | ✅ | `engines/extraction.py`, `engines/contract.py`, scenario 1 |
| 3 Event & entitlement intelligence | events, evidence association, correlation, discovery, deadlines | ✅ | `engines/entitlement.py`, `engines/deadlines.py`, scenarios 2–4 |
| 4 Claims & financials | valuation, lifecycle, document generation, review workflow | ✅ | `engines/valuation.py`, `services/claims.py`, `services/claimdocs.py`, scenario 5 |
| 5 Executive dashboard | KPIs, charts, drill-down, AR/EN | ✅ | `services/dashboard.py`, `pages/Dashboard.tsx`, scenario 6 |
| 6 Hardening & demo | tests (39 + 3 e2e), eval set, docs, demo data, Docker | ✅ / ⚠️ Docker images not buildable in sandbox | this repository |

## Issues found and fixed during testing (selection)
* PDF soft line-wraps split sentences → missed the 28-day notice in Clause 20.1 → sentence unwrapping.
* Wrapped cross-reference ("Sub-Clause 20.1 to an extension…") parsed as a heading → truncated Clause 4.12.
* Procedure clause (13.2) chosen over the clause conferring the right (13.1) → "conferring clause" rule.
* Time-bar sentence treated as a blocking exclusion even when notice was given → handled by notice logic.
* Arabic keyword forms with the definite article missed → found by the evaluation set.
* Dashboard: RTL horizontal charts overlapped; trend dated by record creation; submitted claims left deadlines open.

## Next 6 weeks (proposed)
1. Pilot onboarding with 2 contractors: run on 3 real contracts each, measure clause/notice accuracy, tune taxonomy.
2. Live LLM validation (Claude) on pilot data with the tenant's consent; latency/cost measurement.
3. S3/MinIO storage backend, retention purge job, antivirus scan hook, httpOnly cookie sessions.
4. Container builds in CI with registry mirrors; staging environment in an Egyptian/regional cloud region.
