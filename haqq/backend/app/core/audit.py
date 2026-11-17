"""Tamper-evident audit trail: each entry hashes its content together with the previous entry's hash."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog, DocumentAccessLog, now


def _digest(prev: str | None, payload: dict) -> str:
    return hashlib.sha256(((prev or "") + json.dumps(payload, sort_keys=True, default=str)).encode()).hexdigest()


def audit(db: Session, *, org_id: str | None, user_id: str | None, action: str, entity_type: str | None = None,
          entity_id: str | None = None, detail: dict | None = None, ip: str | None = None) -> AuditLog:
    prev = db.execute(select(AuditLog.hash).order_by(AuditLog.seq.desc()).limit(1).with_for_update()).scalar()
    created = now()
    payload = {"org": org_id, "user": user_id, "action": action, "type": entity_type, "id": entity_id,
               "detail": detail or {}, "at": created.astimezone(UTC).isoformat()}
    entry = AuditLog(org_id=org_id, user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id,
                     detail=detail or {}, ip=ip, prev_hash=prev, hash=_digest(prev, payload), created_at=created)
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session) -> dict:
    prev = None
    count = 0
    for e in db.execute(select(AuditLog).order_by(AuditLog.seq)).scalars():
        payload = {"org": e.org_id, "user": e.user_id, "action": e.action, "type": e.entity_type, "id": e.entity_id,
                   "detail": e.detail or {}, "at": e.created_at.astimezone(UTC).isoformat()}
        if e.prev_hash != prev or e.hash != _digest(prev, payload):
            return {"valid": False, "broken_at_seq": e.seq, "checked": count}
        prev = e.hash
        count += 1
    return {"valid": True, "checked": count}


def log_document_access(db: Session, *, org_id: str, user_id: str | None, document_id: str, action: str,
                        ip: str | None = None) -> None:
    db.add(DocumentAccessLog(org_id=org_id, user_id=user_id, document_id=document_id, action=action, ip=ip))
