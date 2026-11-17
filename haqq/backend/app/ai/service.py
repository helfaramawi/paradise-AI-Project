"""AI task runner: policy enforcement, prompt versioning, structured-output validation, citation checks,
execution logging (ai_runs) and token-usage metering."""

from __future__ import annotations

import hashlib
import json
import logging

from sqlalchemy.orm import Session

from ..models import AiRun, Organization, UsageRecord
from .guard import wrap
from .prompts import PROMPTS
from .providers import ProviderError, ProviderNotConfigured, ProviderRefusal, get_provider

log = logging.getLogger("haqq.ai")


class AiUnavailable(Exception):
    def __init__(self, reason: str, code: str):
        super().__init__(reason)
        self.code = code


def _collect_citations(obj) -> set[str]:
    found: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "citation_ids" and isinstance(v, list):
                found.update(str(x) for x in v)
            else:
                found |= _collect_citations(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= _collect_citations(v)
    return found


def build_sources_block(sources: list[dict]) -> str:
    """sources: [{id, label, text}] — rendered as wrapped untrusted excerpts."""
    return "\n\n".join(wrap(s["id"], s["label"], s["text"]) for s in sources)


def run_task(db: Session, *, org: Organization, project_id: str | None, prompt_id: str, user_content: str,
             allowed_citation_ids: set[str], task: str | None = None) -> tuple[dict, AiRun]:
    spec = PROMPTS[prompt_id]
    provider = get_provider()
    run = AiRun(org_id=org.id, project_id=project_id, task=task or prompt_id, prompt_id=spec.id,
                prompt_version=spec.version, provider=provider.name, model=getattr(provider, "model", "-"),
                status="skipped", input_hash=hashlib.sha256(user_content.encode()).hexdigest())
    db.add(run)
    if provider.name == "none":
        run.error = "No LLM provider is configured (HAQQ_LLM_PROVIDER=none)."
        db.flush()
        raise AiUnavailable(run.error, "not_configured")
    if not org.ai_external_processing:
        run.error = "Organisation policy does not allow external AI processing."
        db.flush()
        raise AiUnavailable(run.error, "policy_disabled")
    try:
        res = provider.structured(spec.system, user_content, spec.schema, spec.max_tokens)
    except ProviderNotConfigured as exc:
        run.error = str(exc)
        db.flush()
        raise AiUnavailable(str(exc), "not_configured") from exc
    except ProviderRefusal as exc:
        run.status, run.error = "refused", str(exc)
        db.flush()
        raise AiUnavailable(str(exc), "refused") from exc
    except ProviderError as exc:
        run.status, run.error = "error", str(exc)
        db.flush()
        raise AiUnavailable(str(exc), "provider_error") from exc
    out = res.parsed.model_dump()
    run.input_tokens, run.output_tokens, run.latency_ms = res.input_tokens, res.output_tokens, res.latency_ms
    run.model, run.attempts = res.model, res.attempts
    db.add(UsageRecord(org_id=org.id, metric="ai_tokens", quantity=res.input_tokens + res.output_tokens,
                       reference=run.id))
    unknown = _collect_citations(out) - allowed_citation_ids
    if unknown:
        run.status = "invalid_output"
        run.error = f"Output cited unknown sources: {sorted(unknown)}"
        run.output = out
        db.flush()
        log.warning("AI output rejected (unknown citations %s)", unknown)
        raise AiUnavailable("The AI output referenced sources that were not provided and was rejected.",
                            "invalid_citations")
    run.status, run.output = "ok", out
    db.flush()
    return out, run


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str, indent=1)
