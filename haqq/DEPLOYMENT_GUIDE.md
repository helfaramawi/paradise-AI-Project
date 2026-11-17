# HAQQ — Deployment Guide

## 1. Docker Compose (recommended target)
Services: `db` (pgvector/pgvector:pg16), `backend` (runs `alembic upgrade head` then uvicorn), `worker`
(`python -m app.worker`), `frontend` (nginx serving the SPA and proxying `/api`).

```bash
cd haqq && cp .env.example .env
```
Edit `.env`: set `HAQQ_ENVIRONMENT=production`, a random `HAQQ_SECRET_KEY` (`openssl rand -hex 32`), `HAQQ_DB_PASSWORD`.
```bash
docker compose up -d --build
```
```bash
docker compose exec backend python -m app.demo.seed
```
(optional DEMO data) → open `http://localhost:8090`.

> **Verification status:** the Dockerfiles and compose file were written for this release but the images could not be
> built in the development sandbox (no network route to Debian package mirrors). Build them once in CI or on a
> machine with registry access before the first customer deployment. Behind a TLS-intercepting proxy pass
> `--build-arg http_proxy=… --build-arg https_proxy=…` and add your CA to the images.

## 2. Native installation (verified)
Ubuntu 24.04: `apt install postgresql-16 postgresql-16-pgvector tesseract-ocr tesseract-ocr-ara poppler-utils`, Python
3.13, Node 22. Then follow README "Quick start". For production run the API with
`uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --workers 2` with `HAQQ_WORKER_MODE=external`, plus one
or more `python -m app.worker` processes, behind nginx (see `frontend/nginx.conf`) with TLS.

## 3. Configuration (environment variables, prefix `HAQQ_`)
| Variable | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | development | `production` enforces a real secret key and HSTS |
| `DATABASE_URL` | local | `postgresql+psycopg2://…` |
| `SECRET_KEY` | dev value | **required** in production |
| `WORKER_MODE` | thread | `thread` (in API), `external` (separate worker), `inline` (tests) |
| `STORAGE_PATH` | `backend/var/storage` | object store root (`/data/storage` in Docker) |
| `MAX_UPLOAD_MB` | 50 | |
| `OCR_ENABLED`, `OCR_LANGUAGES` | true, `ara+eng` | |
| `LLM_PROVIDER` | none | `anthropic` to enable; tenants must also opt in |
| `LLM_MODEL`, `LLM_EFFORT` | claude-opus-5-5, medium | |
| `ANTHROPIC_API_KEY` | – | inject from a secrets manager |
| `SMTP_HOST/PORT/USER/PASSWORD/FROM` | – | empty host = in-app notifications only (reported as `not_configured`) |
| `CORS_ORIGINS` | localhost | JSON list |
| `RATE_LIMIT_LOGIN_PER_MINUTE`, `RATE_LIMIT_API_PER_MINUTE` | 10, 600 | per IP, per process |
| `PLATFORM_ADMIN_EMAIL/PASSWORD` | – | creates the PAIS operator account at start-up |

## 4. Operations
* Health: `GET /api/health` (liveness), `GET /api/health/ready` (DB, pgvector, queue depth, OCR, LLM, e-mail).
* Logs: JSON lines on stdout with request id, path, status, latency.
* Deadline alerts: call `POST /api/v1/deadlines/scan` per organisation (button in the UI) or schedule it (cron /
  n8n) daily. *A built-in scheduler is not yet included.*
* Backups and recovery: `ops\backup.bat` / `ops/backup.sh` create a verified backup (database dump test-restored
  into a scratch database; every stored file checked against its SHA-256); `ops\schedule-backup.bat` schedules it
  daily; `ops\restore.bat` / `ops/restore.sh` restore with a safety backup first and an integrity check after.
  Full procedures, including disaster recovery on a new machine: `docs/OPERATIONS_GUIDE.md`. Recommended: nightly
  backup, 30-day retention, an off-machine copy (`HAQQ_BACKUP_COPY_TO`), quarterly restore drill.
* Migrations: `alembic upgrade head` (runs automatically in the backend container).
* Scaling: stateless API (except the in-process rate limiter) → horizontal; add workers for OCR-heavy tenants.
