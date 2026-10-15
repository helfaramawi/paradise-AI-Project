# Deployment Guide

## 1. Components

| Service | Image | Port | Notes |
|---|---|---|---|
| db | postgres:16-alpine | internal | volume `pgdata`, `pg_isready` health check |
| backend | `future-mirror-backend` (python:3.13-slim, non-root uid 10001) | internal 8000 | runs Alembic migrations and seeds the demo on start; `/api/ready` health check |
| frontend | `future-mirror-frontend` (nginx 1.27) | **8080** → 80 | serves the SPA, reverse-proxies `/api`, SSE buffering disabled |
| n8n *(optional, profile `automation`)* | n8nio/n8n | 5678 | volume `n8ndata` |

## 2. Docker Compose

```bash
cp .env.example .env            # edit secrets
docker compose up -d --build
docker compose ps               # wait for all services to be healthy
open http://localhost:8080      # API docs: http://localhost:8080/api/docs
docker compose --profile automation up -d     # add n8n
docker compose logs -f backend                # structured JSON logs
docker compose down                           # stop (data kept in volumes)
docker compose down -v                        # stop and DELETE all data
```

Data persists in named volumes across restarts and rebuilds. This was verified: decisions and the audit chain survive `docker compose restart`.

### Building behind a proxy

If outbound traffic goes through an HTTP proxy with a private CA:

```bash
CA_BUNDLE=/path/to/corporate-ca.crt ./scripts/docker-build-behind-proxy.sh
docker compose up -d --no-build
```

The CA is passed as a BuildKit secret and is **not** stored in the images. The images need no OS packages at build time; the Arabic-capable PDF font (DejaVu Sans) is vendored in `backend/app/assets/fonts`, so builds also work in air-gapped environments with a PyPI/npm mirror.

## 3. Configuration (`.env`, prefix `FM_`)

| Variable | Default | Purpose |
|---|---|---|
| `FM_DATABASE_URL` | sqlite (dev) / set by compose | SQLAlchemy URL |
| `FM_SECRET_KEY` | dev value | JWT signing key — **required** in production (startup fails if it is still the dev value) |
| `FM_ENVIRONMENT` | development | `production` enables the secret check |
| `FM_ACCESS_TOKEN_MINUTES` | 480 | token lifetime |
| `FM_CORS_ORIGINS` | localhost dev origins | JSON list |
| `FM_SEED_DEMO_DATA` | true | seed the synthetic workspace and demo users |
| `FM_DEMO_PASSWORD` | FutureMirror!2026 | demo user password |
| `FM_PRESENTATION_PACING_MS` | 450 | visible pause between stages (reported separately) |
| `FM_LLM_PROVIDER` | none | `none` / `anthropic` / `openai` / `ollama` |
| `FM_LLM_MODEL` | provider default | e.g. `claude-sonnet-5-5` |
| `FM_ANTHROPIC_API_KEY` / `FM_OPENAI_API_KEY` / `FM_OLLAMA_BASE_URL` | — | provider credentials |
| `FM_AGENT_TIMEOUT_SECONDS` / `FM_PIPELINE_TIMEOUT_SECONDS` | 20 / 180 | execution limits |
| `FM_N8N_BASE_URL` / `FM_N8N_API_KEY` | — | enables live webhook delivery |
| `FM_EXTERNAL_ACTIONS_ENABLED` | **false** | keep false in the MVP (GOV-003 / GOV-014) |
| `FM_<CONNECTOR>_API_KEY` | — | connector secrets (e.g. `FM_ODOO_API_KEY`) |
| `FM_SKIP_STARTUP_MIGRATIONS` | — | set `1` to run migrations as a separate job |

## 4. Production hardening checklist

- [ ] Set a random 64-character `FM_SECRET_KEY` and `FM_ENVIRONMENT=production`.
- [ ] Set `FM_SEED_DEMO_DATA=false` and create real users via `/admin/users`.
- [ ] Change `POSTGRES_PASSWORD`; restrict network access to the database.
- [ ] Terminate TLS in front of nginx (or add certificates to `frontend/nginx.conf`).
- [ ] Set `FM_CORS_ORIGINS` to the real origin.
- [ ] Back up the `pgdata` volume (`pg_dump`), and test the restore.
- [ ] Run more than one uvicorn worker (`--workers`), or several backend replicas behind nginx; SSE works from any replica because events are read from the database.
- [ ] Add a queue and a durable LangGraph checkpointer if runs must survive restarts (see ARCHITECTURE §7).
- [ ] Ship logs (stdout JSON) to your SIEM; alert on `platform.emergency_stop_on` and `approval.blocked` audit actions.

## 5. On-premises / SaaS

- **On-prem:** the same compose file. With `FM_LLM_PROVIDER=ollama` (or `none`), no data leaves the network. The PDF font is vendored.
- **SaaS:** tenants are isolated by `tenant_id` in every query. Each tenant gets its own policies, datasets, connectors and workflows (`seed_tenant`). Use one database per region for data residency.

## 6. Local development without Docker

```bash
cd backend && pip install -r requirements-dev.txt && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev        # http://localhost:5173
```

## 7. n8n integration

1. `docker compose --profile automation up -d`, then open n8n at :5678.
2. Import `automation/n8n/decision_review_notification.json` and activate it.
3. Set `FM_N8N_BASE_URL=http://n8n:5678` and restart the backend.
4. In the Automation Center, a **Live run** of a non-consequential workflow posts to `…/webhook/future-mirror/<key>` with an idempotency key. Consequential workflows remain blocked by GOV-014.
