from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import db as dbmod
from .api import admin, auth, data, decisions, governance, operations, simulation
from .config import get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {"ts": self.formatTime(record), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for k in ("request_id", "path", "status", "duration_ms", "method"):
            if hasattr(record, k):
                base[k] = getattr(record, k)
        return json.dumps(base)


def configure_logging() -> None:
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(os.environ.get("FM_LOG_LEVEL", "INFO"))


log = logging.getLogger("future_mirror")


def migrate_and_seed() -> None:
    s = get_settings()
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", s.database_url)
    command.upgrade(cfg, "head")
    if s.seed_demo_data:
        from .seed import seed_all
        with dbmod.SessionLocal() as db:
            seed_all(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    if os.environ.get("FM_SKIP_STARTUP_MIGRATIONS") != "1":
        migrate_and_seed()
    # Runs interrupted by a restart cannot resume mid-thread: mark them failed explicitly.
    from sqlalchemy import update

    from .models import DecisionRun
    with dbmod.SessionLocal() as db:
        db.execute(update(DecisionRun).where(DecisionRun.status.in_(["queued", "running"]))
                   .values(status="failed", error="Interrupted by service restart"))
        db.commit()
    log.info("Future Mirror AI started")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Future Mirror AI API", version="1.0.0", lifespan=lifespan,
                  description="Enterprise Decision Intelligence & Autonomous Simulation Platform",
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url="/api/redoc")
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not request.url.path.endswith("/events"):
            log.info("request", extra={"request_id": rid, "path": request.url.path, "method": request.method,
                                       "status": response.status_code,
                                       "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": "Validation error", "errors": json.loads(
            json.dumps(exc.errors(), default=str))})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/api/health", tags=["ops"])
    def health():
        return {"status": "ok"}

    @app.get("/api/ready", tags=["ops"])
    def ready():
        try:
            with dbmod.engine.connect() as c:
                c.execute(text("SELECT 1"))
            return {"status": "ready", "database": "ok"}
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(status_code=503, content={"status": "not_ready", "database": str(exc)[:200]})

    for r in (auth.router, decisions.router, simulation.router, data.router, governance.router,
              operations.router, admin.router):
        app.include_router(r, prefix="/api/v1")
    return app


app = create_app()
