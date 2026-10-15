"""Automation execution through n8n webhooks with dry-run, approval gates, idempotency,
retries and audit logging. Consequential workflows are blocked by policy GOV-014 unless
live execution is explicitly enabled AND the related decision is approved."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..governance.engine import evaluate_policies
from ..governance.service import load_policies
from ..models import AutomationRun, AutomationWorkflow, Decision
from ..services.audit import audit


def idempotency_key(workflow_key: str, payload: dict[str, Any], dry_run: bool) -> str:
    body = json.dumps(payload, sort_keys=True, default=str)
    return f"{workflow_key}:{'dry' if dry_run else 'live'}:{hashlib.sha256(body.encode()).hexdigest()[:24]}"


def trigger_workflow(db: Session, wf: AutomationWorkflow, *, payload: dict[str, Any], dry_run: bool,
                     user_id: str | None, decision: Decision | None = None) -> AutomationRun:
    s = get_settings()
    key = idempotency_key(wf.key, payload, dry_run)
    existing = db.scalar(select(AutomationRun).where(AutomationRun.idempotency_key == key))
    if existing:
        return existing  # idempotent replay: same payload -> same run, no duplicate side effects

    ctx = {
        "action": {"type": "automation.run", "consequential": wf.consequential, "dry_run": dry_run,
                   "external_write": wf.consequential and not dry_run, "actor_type": "user", "mode": "execute"},
        "decision": {"status": decision.status if decision else "none", "no_terminations": True},
        "platform": {"external_actions_enabled": s.external_actions_enabled},
    }
    gov = evaluate_policies(load_policies(db, wf.tenant_id), ctx)
    run = AutomationRun(workflow_id=wf.id, idempotency_key=key, dry_run=dry_run, payload=payload,
                        triggered_by=user_id, status="queued")
    db.add(run)
    if gov["outcome"] == "denied" or not wf.enabled:
        run.status = "blocked"
        run.result = {"reason": [d["message_en"] for d in gov["deny_reasons"]] or ["workflow disabled"],
                      "policies": [d["code"] for d in gov["deny_reasons"]]}
    elif dry_run:
        run.status = "dry_run_ok"
        run.result = {"would_post_to": f"{s.n8n_base_url or '<n8n not configured>'}/webhook/{wf.n8n_webhook_path}",
                      "payload_preview": payload, "side_effects": "none (dry-run)"}
    elif not s.n8n_base_url:
        run.status = "failed"
        run.result = {"reason": "FM_N8N_BASE_URL not configured; no delivery attempted"}
    else:
        url = f"{s.n8n_base_url.rstrip('/')}/webhook/{wf.n8n_webhook_path}"
        last_err = ""
        for attempt in range(1, wf.retry_max + 1):
            run.attempts = attempt
            try:
                r = httpx.post(url, json={"idempotency_key": key, **payload}, timeout=10,
                               headers={"X-N8N-API-KEY": s.n8n_api_key} if s.n8n_api_key else {})
                r.raise_for_status()
                run.status = "delivered"
                run.result = {"http_status": r.status_code}
                break
            except httpx.HTTPError as exc:
                last_err = str(exc)
                time.sleep(min(2 ** attempt * 0.2, 2))
        else:
            run.status = "failed"
            run.result = {"reason": last_err, "compensation": "none required - delivery never succeeded"}
    db.commit()
    audit(db, tenant_id=wf.tenant_id, actor_type="user" if user_id else "system", actor_id=user_id or "system",
          action=f"automation.{run.status}", entity_type="automation_run", entity_id=run.id,
          detail={"workflow": wf.key, "dry_run": dry_run, "idempotency_key": key})
    return run
