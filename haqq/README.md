# HAQQ · حقّك
### AI Contractual Rights & Revenue Recovery Intelligence Platform — by Paradise AI Solutions (PAIS)

> **Don't lose what your contract entitles you to.** · **حقّك – اكتشف مستحقاتك التعاقدية قبل أن تضيع.**

HAQQ is a revenue-protection platform for construction contractors. It reads the contract, connects what the
contract says to what actually happened on site and to the evidence on file, and surfaces **potential**
contractual entitlements — with the applicable clause, the supporting and missing evidence, the notice deadline,
the financial impact and a draft claim package. Every conclusion is traceable to a document and page.
Humans decide; HAQQ never sends a claim and never presents a potential entitlement as a guaranteed recovery.

![Explainable entitlement](docs/screenshots/entitlement-en.jpg)

## The core journey (works end to end today)

**Upload contract → add project documents → analyse → discover potential entitlements → review evidence → prepare claim.**

With the bundled DEMO dataset (fictional, clearly labelled) a commercial director sees, for example:

> *ENT-001 · Variation / additional work valuation — EGP 2,000,000 (valuation draft).* Clause 13.1 (p.2) confers
> the right; the engineer's scanned Site Instruction SI-014 (read by OCR), Minutes of Meeting No. 22 and the BOQ
> support it; the **contractor's notice is missing**; Clause 20.1 requires notice within 28 days (time-barred) →
> **due in 7 days**, certainty *estimated* because the clause doesn't say calendar vs working days. Recommended
> action #1: issue the notice before the due date. One click prepares the claim and generates an Arabic or English
> notice / claim package (DOCX, PDF) and an Excel valuation worksheet.

## What is implemented

| Area | Status |
|---|---|
| Multi-tenant organisations, projects, team assignment, self-service onboarding | ✅ implemented & tested |
| Auth: PBKDF2 passwords, JWT bound to revocable server sessions, lockout, TOTP MFA, rate limits | ✅ implemented & tested |
| RBAC — 8 roles, 26 permissions, project-level visibility for site roles | ✅ implemented & tested |
| Document pipeline — PDF text layer + Tesseract OCR fallback (Arabic+English), scanned images, DOCX, XLSX BOQ, e-mail (.eml), text; SHA-256 integrity, versioning, DB-backed job queue | ✅ implemented & tested |
| Contract intelligence — EN/AR clause segmentation with page references, 18 categories, obligations, rights, conditions, exclusions, time limits (notice / detailed claim / payment), time-bars, risk flags, human verification | ✅ deterministic engine, tested; 100 % on the (small, synthetic) labelled eval set |
| Event intelligence — register, keyword classification, evidence linking, document suggestions (pgvector + date proximity), clause correlation | ✅ implemented & tested |
| **Entitlement discovery engine** — clause × event × evidence × money × deadline, explainable, statuses potential / insufficient evidence / requires expert verification; substantiated/rejected only by humans | ✅ implemented & tested |
| Deadline intelligence — Egyptian working-day calendar (Fri/Sat, configurable holidays), conflicting periods flagged *ambiguous*, assumptions stated, escalation & in-app alerts | ✅ implemented & tested; e-mail via SMTP **only if configured** |
| Valuation — Decimal engine, formulas, BOQ-rate lines, overhead/profit/VAT flagged as needing contractual basis, separation of duties for verification | ✅ implemented & tested |
| Claims — 15-stage lifecycle with role gates; DOCX / PDF (Arabic RTL & English) and XLSX generation with draft banners, citations and [VERIFY] markers; never sent automatically | ✅ implemented & tested |
| Executive dashboard — 13 KPIs computed from stored records with drill-down; 8 visualisations; Excel export | ✅ implemented & tested |
| AI layer — provider abstraction, Claude via the official Anthropic SDK, structured outputs, prompt versioning, citation validation, injection guard, AI run log, token metering, per-organisation data policy | ✅ implemented & tested with a provider double; **not exercised against the live API here (no key in this environment)** |
| Subscription — plans, limits enforcement, usage metering, billing records, PAIS commercial (MRR) report | ✅ implemented; payment gateway **not integrated** (interface only) |
| Docker / Compose (pgvector, API, worker, nginx) | ⚠️ written; images **could not be built in the development sandbox** (no access to Debian mirrors). Stack verified natively. |

See [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) for the full list of limitations and risks.

## Quick start (native, verified)

Prerequisites: Python 3.13, Node 22, PostgreSQL 16 with `pgvector`, Tesseract (`tesseract-ocr`, `tesseract-ocr-ara`).

```bash
cd haqq/backend && pip install -r requirements-dev.txt
```
```bash
createdb haqq && psql haqq -c "CREATE EXTENSION vector"
```
```bash
cd haqq/backend && export HAQQ_DATABASE_URL=postgresql+psycopg2://USER:PASS@localhost:5432/haqq && alembic upgrade head && python -m app.demo.seed && uvicorn app.main:app --port 8000
```
```bash
cd haqq/frontend && npm install && npm run dev
```

Open http://localhost:5173 — demo accounts `ceo@haqq.demo`, `commercial@haqq.demo`, `contracts@haqq.demo`,
`cfo@haqq.demo`, `legal@haqq.demo`, `site@haqq.demo`, `admin@haqq.demo`; password `HaqqDemo!2026`.
API docs: http://localhost:8000/api/docs.

Docker: `cp .env.example .env && docker compose up -d --build` (see [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md)).

## Operations scripts (`haqq/ops`)

| Task | Windows | macOS / Linux |
|---|---|---|
| Start and open HAQQ | `ops\start.bat` | `ops/start.sh` |
| Stop (data kept) | `ops\stop.bat` | `ops/stop.sh` |
| Verified backup (database + documents + settings) | `ops\backup.bat` | `ops/backup.sh` |
| Daily automatic backup | `ops\schedule-backup.bat [HH:MM]` | cron |
| Restore (safety backup first, integrity re-check after) | `ops\restore.bat [name]` | `ops/restore.sh [name]` |
| Update (verified backup → git pull → rebuild) | `ops\update.bat` | `ops/update.sh` |
| Load / reset DEMO data | `ops\seed-demo.bat [reset]` | `ops/seed-demo.sh [reset]` |
| Record the Arabic demo video | `ops\record-demo.bat` | `ops/record-demo.sh` |
| Add the Egyptian Arabic voice-over | `ops\make-voiceover.bat [female]` | `ops/make-voiceover.sh [female]` |

Every backup is **verified before it is reported complete**: the database dump is test-restored into a scratch
database and compared table by table, and every stored document is checked against the SHA-256 recorded when it was
uploaded. Full procedures: [docs/OPERATIONS_GUIDE.md](docs/OPERATIONS_GUIDE.md) ·
[الدليل بالعربية](docs/OPERATIONS_GUIDE_AR.md). Word editions of the user and operations guides (English and
Arabic) are in [`docs/word`](docs/word) (rebuild with `python docs/build_word.py`).

## Tests

```bash
cd haqq/backend && pytest -q          # 42 tests: engines, 8 acceptance scenarios, security, AI layer, backup integrity, eval gate
```
```bash
cd haqq/frontend && npx playwright test   # 3 browser journeys (needs API + dev server + demo data)
```
```bash
cd haqq/backend && python -m eval.run_eval  # contract-engine evaluation report
```

## Documentation

| Document | |
|---|---|
| [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) | personas, modules, acceptance criteria |
| [ARCHITECTURE.md](ARCHITECTURE.md) | modular monolith, decisions (incl. Vite vs Next.js) |
| [DATABASE_DESIGN.md](DATABASE_DESIGN.md) | 30 tables, tenancy, indexes |
| [AI_DESIGN.md](AI_DESIGN.md) | deterministic engines + LLM layer, explainability, evaluation |
| [SECURITY_DESIGN.md](SECURITY_DESIGN.md) | tenancy, RBAC, audit, injection defence, PDPL 151/2020 considerations |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | repository inspection, phases, status per phase |
| [TESTING_STRATEGY.md](TESTING_STRATEGY.md) | test layers, results, requirements traceability matrix |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Docker, native, configuration, backup/restore, operations |
| [COMMERCIAL_MODEL.md](COMMERCIAL_MODEL.md) | pricing hypotheses, MRR target, pilot plan |
| [docs/API.md](docs/API.md) | endpoint reference |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) · [docs/USER_GUIDE_AR.md](docs/USER_GUIDE_AR.md) · [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) | user guide (EN, AR) & administrator guide |
| [docs/OPERATIONS_GUIDE.md](docs/OPERATIONS_GUIDE.md) · [docs/OPERATIONS_GUIDE_AR.md](docs/OPERATIONS_GUIDE_AR.md) | installation, backup, recovery, demo video (EN, AR) |
| [docs/word](docs/word) | the user and operations guides as Word documents (EN, AR) |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | 15-minute live business demonstration |
| [docs/ROADMAP.md](docs/ROADMAP.md) · [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) | roadmap, limitations & risk register |

---
HAQQ lives in `haqq/` inside the PAIS monorepo and is independent of the Future Mirror AI product in the repository root.
