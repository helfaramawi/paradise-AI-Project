"""Thread-safe workflow event sink. Events are persisted (replayable after restart) and
streamed to clients via Server-Sent Events by polling the workflow_events table."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ..db import SessionLocal
from ..models import AgentExecution, DecisionRun, Tenant, WorkflowEvent


class RunCancelled(Exception):
    pass


class RunTimeout(Exception):
    pass


class EventSink:
    def __init__(self, run_id: str, tenant_id: str, pacing_ms: int = 0, timeout_s: float = 180.0):
        self.run_id = run_id
        self.tenant_id = tenant_id
        self.pacing_ms = pacing_ms
        self.timeout_s = timeout_s
        self._lock = threading.Lock()
        self._t0 = time.perf_counter()
        self.paced_ms = 0.0

    # ------------------------------------------------------------- events
    def emit(self, stage: str, event_type: str, message_en: str = "", message_ar: str = "",
             agent_key: str | None = None, payload: dict[str, Any] | None = None) -> None:
        with self._lock, SessionLocal() as db:
            db.add(WorkflowEvent(run_id=self.run_id, stage=stage, event_type=event_type, agent_key=agent_key,
                                 message_en=message_en, message_ar=message_ar, payload=payload or {}))
            if event_type == "stage_started":
                run = db.get(DecisionRun, self.run_id)
                if run:
                    run.current_stage = stage
            db.commit()

    # ------------------------------------------------------------- agent executions
    def start_execution(self, agent_key: str, phase: str, mode: str) -> str:
        with self._lock, SessionLocal() as db:
            ex = AgentExecution(run_id=self.run_id, agent_key=agent_key, phase=phase, status="running", mode=mode)
            db.add(ex)
            db.commit()
            return ex.id

    def finish_execution(self, ex_id: str, status: str, duration_ms: float, attempts: int,
                         error: str | None = None, narrative: dict[str, str] | None = None) -> None:
        with self._lock, SessionLocal() as db:
            ex = db.get(AgentExecution, ex_id)
            if ex:
                ex.status = status
                ex.duration_ms = duration_ms
                ex.attempts = attempts
                ex.error = error
                ex.finished_at = datetime.now(UTC)
                if narrative:
                    ex.llm_narrative_en = narrative.get("en")
                    ex.llm_narrative_ar = narrative.get("ar")
                db.commit()

    # ------------------------------------------------------------- control
    def check(self) -> None:
        """Raise if the run was cancelled, the platform emergency stop is active, or timed out."""
        if time.perf_counter() - self._t0 > self.timeout_s:
            raise RunTimeout(f"Pipeline exceeded {self.timeout_s}s")
        with SessionLocal() as db:
            run = db.get(DecisionRun, self.run_id)
            tenant = db.scalar(select(Tenant).where(Tenant.id == self.tenant_id))
            if run and run.cancel_requested:
                raise RunCancelled("Cancelled by user")
            if tenant and (tenant.settings or {}).get("emergency_stop"):
                raise RunCancelled("Platform emergency stop is active")

    def pace(self) -> None:
        """Visible presentation pause between stages. Reported separately from compute time."""
        if self.pacing_ms > 0:
            time.sleep(self.pacing_ms / 1000)
            self.paced_ms += self.pacing_ms

    @property
    def compute_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000 - self.paced_ms
