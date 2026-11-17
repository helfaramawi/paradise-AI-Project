"""PostgreSQL-backed job queue (SELECT … FOR UPDATE SKIP LOCKED) with retries.

Runs inside the API process in a daemon thread (HAQQ_WORKER_MODE=thread), as a separate process
(`python -m app.worker`, mode=external) or synchronously (mode=inline, used by tests)."""

from __future__ import annotations

import logging
import threading
import time
import traceback
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..models import Job, now

log = logging.getLogger("haqq.jobs")
HANDLERS: dict[str, Callable[[Session, dict], dict | None]] = {}


def handler(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn
    return deco


def enqueue(db: Session, org_id: str, kind: str, payload: dict) -> Job:
    job = Job(org_id=org_id, kind=kind, payload=payload)
    db.add(job)
    db.flush()
    if get_settings().worker_mode == "inline":
        db.commit()
        run_job(job.id)
        db.refresh(job)
    return job


def run_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.execute(select(Job).where(Job.id == job_id).with_for_update(skip_locked=True)).scalar_one_or_none()
        if job is None or job.status not in ("queued",):
            return
        job.status, job.started_at, job.attempts = "running", now(), job.attempts + 1
        db.commit()
        try:
            result = HANDLERS[job.kind](db, job.payload)
            job.status, job.result, job.finished_at, job.error = "done", result or {}, now(), None
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            job = db.get(Job, job_id)
            job.error = f"{exc}\n{traceback.format_exc()[-1500:]}"
            job.status = "queued" if job.attempts < job.max_attempts else "failed"
            job.finished_at = now()
            db.commit()
            log.exception("Job %s (%s) failed", job_id, job.kind)
            if job.status == "failed":
                fail = HANDLERS.get(job.kind + ":failed")
                if fail:
                    fail(db, job.payload)
                    db.commit()
    finally:
        db.close()


def poll_once() -> bool:
    db = SessionLocal()
    try:
        job_id = db.execute(select(Job.id).where(Job.status == "queued").order_by(Job.created_at).limit(1)
                            .with_for_update(skip_locked=True)).scalar()
    finally:
        db.close()
    if job_id:
        run_job(job_id)
        return True
    return False


_stop = threading.Event()


def worker_loop(interval: float = 1.0) -> None:
    log.info("HAQQ job worker started")
    while not _stop.is_set():
        try:
            if not poll_once():
                _stop.wait(interval)
        except Exception:  # noqa: BLE001
            log.exception("Worker loop error")
            time.sleep(interval)


def start_thread_worker() -> threading.Thread:
    t = threading.Thread(target=worker_loop, name="haqq-worker", daemon=True)
    t.start()
    return t


def stop_worker() -> None:
    _stop.set()
