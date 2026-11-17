"""HAQQ API application."""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import __version__
from .api import auth, claims, contracts, dashboard, deadlines, documents, entitlements, events, org, projects
from .config import get_settings
from .core.ratelimit import limiter
from .db import SessionLocal
from .engines.extraction import ocr_available
from .services import jobs, pipeline  # noqa: F401  (pipeline registers job handlers)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": self.formatTime(record), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for k in ("request_id", "path", "status", "ms"):
            if hasattr(record, k):
                out[k] = getattr(record, k)
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


def _setup_logging() -> None:
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(logging.INFO)


log = logging.getLogger("haqq.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    s = get_settings()
    from .seed import seed_base

    with SessionLocal() as db:
        seed_base(db)
        db.commit()
    if s.worker_mode == "thread":
        jobs.start_thread_worker()
    log.info("HAQQ API %s started (env=%s, llm=%s, ocr=%s)", __version__, s.environment, s.llm_provider, ocr_available())
    yield
    jobs.stop_worker()


app = FastAPI(title="HAQQ API — حقّك", version=__version__, lifespan=lifespan,
              description="AI Contractual Rights & Revenue Recovery Intelligence Platform (Paradise AI Solutions).",
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def security_and_logging(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    t0 = time.monotonic()
    ip = request.client.host if request.client else "?"
    if request.url.path.startswith("/api/v1") and not limiter.allow(f"api:{ip}", get_settings().rate_limit_api_per_minute):
        return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
    try:
        response = await call_next(request)
    except Exception:
        log.exception("Unhandled error", extra={"request_id": rid, "path": request.url.path})
        response = JSONResponse({"detail": "Internal server error", "request_id": rid}, status_code=500)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not request.url.path.startswith("/api/docs"):
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if get_settings().is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/v1"):
        log.info("%s %s", request.method, request.url.path,
                 extra={"request_id": rid, "path": request.url.path, "status": response.status_code,
                        "ms": int((time.monotonic() - t0) * 1000)})
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


@app.get("/api/health/ready")
def ready():
    s = get_settings()
    checks = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            checks["database"] = "ok"
            checks["pgvector"] = "ok" if db.execute(text("SELECT 1 FROM pg_extension WHERE extname='vector'")).first() else "missing"
            checks["queued_jobs"] = db.execute(text("SELECT count(*) FROM jobs WHERE status='queued'")).scalar()
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc.__class__.__name__}"
    checks["ocr"] = "available" if ocr_available() else "unavailable"
    checks["llm_provider"] = s.llm_provider
    checks["llm_configured"] = s.llm_provider == "anthropic" and bool(s.anthropic_api_key)
    checks["email"] = "configured" if s.smtp_host else "not_configured"
    checks["storage"] = s.storage_backend
    ok = checks.get("database") == "ok"
    return JSONResponse({"status": "ready" if ok else "degraded", "checks": checks}, status_code=200 if ok else 503)


for r in (auth.router, org.router, projects.router, documents.router, contracts.router, events.router,
          entitlements.router, claims.router, deadlines.router, dashboard.router):
    app.include_router(r, prefix="/api/v1")
