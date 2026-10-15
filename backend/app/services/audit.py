"""Tamper-evident audit trail: each event hashes its content with the previous event's hash."""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditEvent

_lock = threading.Lock()


def _digest(prev: str, body: dict[str, Any]) -> str:
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True, default=str)).encode()).hexdigest()


def audit(
    db: Session,
    *,
    tenant_id: str | None,
    actor_type: str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    detail: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditEvent:
    with _lock:
        last = db.scalar(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1))
        prev = last.hash if last else ""
        body = {
            "tenant_id": tenant_id, "actor_type": actor_type, "actor_id": actor_id, "action": action,
            "entity_type": entity_type, "entity_id": entity_id, "detail": detail or {},
        }
        ev = AuditEvent(**body, prev_hash=prev, hash=_digest(prev, body))
        db.add(ev)
        if commit:
            db.commit()
        else:
            db.flush()
        return ev


def verify_chain(db: Session) -> dict[str, Any]:
    prev = ""
    count = 0
    for ev in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        body = {
            "tenant_id": ev.tenant_id, "actor_type": ev.actor_type, "actor_id": ev.actor_id,
            "action": ev.action, "entity_type": ev.entity_type, "entity_id": ev.entity_id,
            "detail": ev.detail or {},
        }
        if ev.prev_hash != prev or ev.hash != _digest(prev, body):
            return {"valid": False, "broken_at": ev.id, "checked": count}
        prev = ev.hash
        count += 1
    return {"valid": True, "checked": count}
