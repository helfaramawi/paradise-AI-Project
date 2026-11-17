# HAQQ — Architecture

## 1. Shape: a modular monolith

```
                ┌──────────────────────── Browser (React SPA, AR-RTL / EN-LTR) ───────────────────────┐
                │ dashboard · projects · documents · clauses · events · entitlements · valuation · claims │
                └───────────────────────────────────────┬─────────────────────────────────────────────┘
                                                        │ HTTPS  /api/v1  (JWT)
┌──────────────────────────────── FastAPI application (app/) ─────────────────────────────────────────┐
│ api/        thin routers: validation (Pydantic), permission checks, tenant scoping, audit            │
│ core/       security (PBKDF2, JWT+sessions, TOTP) · rbac · deps (tenancy) · audit chain · rate limit │
│ services/   pipeline · discovery · claims · claimdocs · dashboard · notify · subscription · jobs      │
│ engines/    PURE, deterministic, unit-tested: extraction · contract · entitlement · deadlines ·       │
│             valuation · embeddings · bm25 · taxonomy (EN/AR knowledge base)                          │
│ ai/         provider abstraction · versioned prompts · injection guard · task runner (logging)       │
└───────────────┬───────────────────────────────┬──────────────────────────────┬──────────────────────┘
                │ SQLAlchemy 2                  │ object store (S3-style keys) │ optional
        PostgreSQL 16 + pgvector        local filesystem (SHA-256 verified)    Anthropic API (Claude)
        (30 tables, HNSW indexes,       tenant-prefixed keys                    only if configured AND
         jobs table = work queue)                                                allowed by the tenant
                ▲
                │ SELECT … FOR UPDATE SKIP LOCKED
        Job worker (thread in API, or `python -m app.worker`)
```

Module boundaries are deliberate seams for later extraction (e.g. the document pipeline or the AI runner can
become separate services) without introducing microservices in the MVP.

## 2. Request → insight flow

1. **Upload** (`services/pipeline.upload_document`) validates size, extension *and* magic bytes, rejects duplicates,
   versions same-named files, stores the blob, meters usage, writes an audit entry and enqueues `process_document`.
2. **Process** (job): extract pages (PDF text layer; pages with < 40 chars are rendered at 300 dpi and OCR'd with
   Tesseract `ara+eng`; DOCX/e-mail are paginated into *estimated* pages and flagged); classify; scan for
   prompt-injection text; detect date and author; chunk + embed into pgvector; parse BOQ rows; for contracts,
   segment and analyse clauses.
3. **Event** registered by a user (category suggested by the classifier), evidence linked by the user;
   HAQQ *suggests* related documents but suggestions never count as evidence until linked.
4. **Discover** (`services/discovery.run_for_event` → `engines/entitlement.discover`): rank clauses, choose the
   clause that confers the right, assess evidence rules, evaluate notice / detailed-claim deadlines, quantify,
   score risk and confidence, write explanation + facts + assumptions + actions; upsert entitlements (human
   decisions are preserved) and deadlines.
5. **Review / value / claim**: human review, Decimal valuation with separation of duties, role-gated claim
   lifecycle, document generation; dashboard aggregates stored records.

## 3. Key decisions

| Decision | Choice | Why |
|---|---|---|
| Frontend framework | **React + Vite SPA** instead of Next.js | HAQQ is a fully authenticated app behind a separate FastAPI API: no SEO, no SSR need. The PAIS team already runs this exact stack (Future Mirror AI), which cuts build/ops cost. A move to Next.js remains possible since pages are plain React. |
| Architecture | Modular monolith | Lowest operating cost for an MVP; clean module seams. |
| Queue | PostgreSQL `jobs` table + `SKIP LOCKED` | No Redis/RabbitMQ to operate; transactional with the data; retries + failure handler. Move to a broker when throughput requires. |
| Intelligence | **Deterministic engines first**, LLM optional | Traceable, testable, zero hallucination risk on clause numbers, pages, dates and money; works with no external AI (important for Egyptian enterprise data-residency concerns). LLM adds cited narrative / Q&A only. |
| Embeddings | Local feature-hashing vectors (256-d) in pgvector | Works offline for Arabic and English; same schema accepts a neural embedding provider later. Honest limitation: lexical-semantic, not neural. |
| Money | `Decimal` everywhere, server-side | Exactness; LLM never calculates. |
| Storage | S3-style key abstraction, local FS backend | Swap to S3/MinIO by implementing `put/get/delete`. |
| Calendar | Egypt Fri/Sat weekend + per-org holidays | Contract day counting must match the market. |

## 4. Repository layout

```
haqq/
  backend/   app/{api,core,services,engines,ai,demo} · alembic/ · tests/ · eval/ · Dockerfile
  frontend/  src/{pages,components,lib} · e2e/ · Dockerfile · nginx.conf
  docs/      API, guides, demo script, roadmap, limitations, screenshots
  ops/       backup.sh · restore.sh
  docker-compose.yml · .env.example
```
