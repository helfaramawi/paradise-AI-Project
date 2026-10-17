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
| `FM_ODOO_API_KEY`, `FM_D365_FO_CLIENT_SECRET`, `FM_D365_BC_CLIENT_SECRET`, `FM_SAP_PASSWORD`, `FM_REST_TOKEN`, `FM_SQL_PASSWORD` | — | connector secrets (see §8) |
| `FM_SKIP_STARTUP_MIGRATIONS` | — | set `1` to run migrations as a separate job |

## 4. Production hardening checklist

- [ ] Set a random 64-character `FM_SECRET_KEY` and `FM_ENVIRONMENT=production`.
- [ ] Set `FM_SEED_DEMO_DATA=false` and create real users via `/admin/users`.
- [ ] Change `POSTGRES_PASSWORD`; restrict network access to the database.
- [ ] Terminate TLS in front of nginx (or add certificates to `frontend/nginx.conf`).
- [ ] Set `FM_CORS_ORIGINS` to the real origin.
- [ ] Back up the database on a schedule (`ops/backup.sh` or `ops\backup.bat /nopause`, e.g. from cron or Windows Task Scheduler), copy `backups/` off the machine, and test `ops/restore.sh` / `ops\restore.bat` on a spare machine.
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

## 8. Enterprise connectors (read-only)

Configure connectors in **Data Connections → Settings** (permission `connector.manage`, the admin role by default). The form stores non-secret settings only. Every save is audited, and the API rejects any key that looks like a secret. Secrets come from the server environment:

| Connector | Secret variable | Settings in the form |
|---|---|---|
| Odoo (XML-RPC) | `FM_ODOO_API_KEY` | URL, database, username, period, account mapping |
| Dynamics 365 Finance & Operations (OData) | `FM_D365_FO_CLIENT_SECRET` | environment URL, Entra tenant ID, app (client) ID, legal entity, period, account mapping; optional entity/field overrides |
| Dynamics 365 Business Central (API v2.0) | `FM_D365_BC_CLIENT_SECRET` | Entra tenant ID, app (client) ID, environment name, company ID, period, account mapping |
| SAP S/4HANA (OData v2) | `FM_SAP_PASSWORD` | S/4HANA URL, communication user, company code, ledger (default `0L`), period, SAP client (optional), account mapping |
| Generic REST API (JSON) | `FM_REST_TOKEN` (optional) | endpoint URL, records path, account field, amount field, next-page link path, auth header/scheme, account mapping |
| SQL database (PostgreSQL; SQL Server/MySQL with driver) | `FM_SQL_PASSWORD` | database type, host, port, database, username, schema, table or view, account/amount/date columns, period, account mapping |

After setting a secret, restart the backend with `docker compose up -d backend`. The settings card shows whether the secret is present, never its value. Then press **Test** and, once it reports success, press **Sync**. A sync that changes figures creates a new dataset version, with those fields tagged `imported`.

**Account mapping.** Each row maps an account-code prefix to a cost category (personnel, contractors, software, infrastructure, facilities, vendor services, other G&A), and the longest matching prefix wins. For D365, accounts that match no prefix (balance sheet, revenue) are ignored and reported as `ignored_accounts` / `ignored_total`. For F&O the main account is the first segment of `LedgerAccount`. Amounts are divided by `amount_divisor` (default 1,000,000) to give EGP millions.

**Dynamics 365 app registration** (one-time, done by the customer's Entra ID admin):
1. Entra admin center → App registrations → New registration. Copy the *Application (client) ID* and *Directory (tenant) ID*.
2. Certificates & secrets → New client secret. Put its value in `FM_D365_FO_CLIENT_SECRET` or `FM_D365_BC_CLIENT_SECRET`.
3. **F&O:** System administration → Setup → Microsoft Entra ID applications → add the client ID, mapped to a user with read-only access to general-ledger data.
   **Business Central:** Microsoft Entra applications → add the client ID, grant consent and assign read-only permission sets (e.g. `D365 READ`).
4. Allow outbound HTTPS from the backend to `login.microsoftonline.com` and to the F&O environment or `api.businesscentral.dynamics.com`.

The connectors use the client-credentials flow, read `GeneralJournalAccountEntries` (F&O) or `generalLedgerEntries` (BC) for the configured period, follow `@odata.nextLink` paging and stop at `max_rows` (default 500,000). They never write to the ERP. **Status: implemented and tested against mocked Entra ID / OData responses; not yet verified against a live tenant.**

**SAP S/4HANA.** Create a communication arrangement for scenario `SAP_COM_0002` (Finance – Posting Integration) or any arrangement that exposes `API_JOURNALENTRYITEMBASIC_SRV`, with a communication user that has read access. The connector reads `A_JournalEntryItemBasic` (`GLAccount`, `AmountInCompanyCodeCurrency`) filtered by company code, ledger and posting date. Leading zeros are stripped from G/L accounts (`0061000000` → `61000000`), so map prefixes such as `61`.

**Generic REST API.** Any JSON endpoint that returns ledger lines. Set the records path (for example `data.items`, empty when the response is the list itself), the account and amount fields (dotted paths allowed, such as `gl.code`), and optionally the path to a next-page link (absolute or relative). When `FM_REST_TOKEN` is set, it is sent as `<auth header>: <auth scheme> <token>` (default `Authorization: Bearer …`). Put period filters in the URL query string.

**SQL database.** Point it at a table or, better, a view with one row per ledger line. The connector runs `SELECT account, SUM(amount) … WHERE date BETWEEN … GROUP BY account` built from validated identifiers (no free-text SQL); on PostgreSQL the transaction is read-only. Create a dedicated user with `SELECT` on that view only. SQL Server needs `pymssql` and MySQL needs `pymysql` added to `backend/requirements.txt`.
