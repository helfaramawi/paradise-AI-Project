"""Entitlement discovery service: loads project data, runs the deterministic engine, persists findings,
clause links and contractual deadlines, and (optionally) asks the LLM for a cited narrative."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai.service import AiUnavailable, build_sources_block, dumps, run_task
from ..core.audit import audit
from ..engines import entitlement as engine
from ..engines.deadlines import Calendar
from ..engines.embeddings import cosine, embed
from ..models import (
    Clause,
    Deadline,
    Document,
    DocumentChunk,
    DocumentPage,
    Entitlement,
    EventClauseLink,
    EventDocument,
    Organization,
    Project,
    ProjectEvent,
    Valuation,
)

log = logging.getLogger("haqq.discovery")


def next_ref(db: Session, model, project_id: str, prefix: str) -> str:
    n = db.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)) or 0
    while True:
        n += 1
        ref = f"{prefix}-{n:03d}"
        if not db.scalar(select(func.count()).select_from(model).where(model.project_id == project_id, model.ref == ref)):
            return ref


def _clauses(db: Session, project_id: str) -> list[engine.ClauseIn]:
    rows = db.execute(select(Clause, Document.title).join(Document, Document.id == Clause.document_id)
                      .where(Clause.project_id == project_id, Document.is_latest.is_(True),
                             Clause.verification_status != "rejected")).all()
    return [engine.ClauseIn(id=c.id, number=c.clause_number, title=c.title, text=c.text, category=c.category,
                            secondary_categories=c.secondary_categories or [], time_limits=c.time_limits or [],
                            exclusions=c.exclusions or [], conditions=c.conditions or [],
                            entitlements=c.entitlements or [], document_id=c.document_id, document_title=t,
                            page_start=c.page_start, page_end=c.page_end, verification_status=c.verification_status,
                            embedding=list(c.embedding) if c.embedding is not None else None)
            for c, t in rows]


def _linked_docs(db: Session, event_id: str) -> list[engine.DocIn]:
    docs = db.execute(select(Document).join(EventDocument, EventDocument.document_id == Document.id)
                      .where(EventDocument.event_id == event_id, EventDocument.confirmed.is_(True))).scalars().all()
    out = []
    for d in docs:
        pages = db.execute(select(DocumentPage.page_number, DocumentPage.text)
                           .where(DocumentPage.document_id == d.id).order_by(DocumentPage.page_number)).all()
        out.append(engine.DocIn(id=d.id, title=d.title, doc_type=d.doc_type or "other", doc_date=d.doc_date,
                                author_party=d.author_party, pages=[(p, t) for p, t in pages]))
    return out


def _event_in(ev: ProjectEvent) -> engine.EventIn:
    return engine.EventIn(id=ev.id, ref=ev.ref, title=ev.title, description=ev.description, category=ev.category,
                          event_date=ev.event_date, awareness_date=ev.awareness_date,
                          est_cost_impact=ev.est_cost_impact, est_time_impact_days=ev.est_time_impact_days,
                          responsible_party=ev.responsible_party, category_source=ev.category_source,
                          suggested_category_confidence=ev.suggested_category_confidence, currency=ev.currency)


def suggest_documents(db: Session, ev: ProjectEvent, limit: int = 6) -> list[dict]:
    """Suggest (not link) project documents related to an event: semantic similarity + date proximity."""
    qv = embed(f"{ev.title} {ev.description}")
    linked = set(db.execute(select(EventDocument.document_id).where(EventDocument.event_id == ev.id)).scalars())
    best: dict[str, dict] = {}
    rows = db.execute(select(DocumentChunk.document_id, DocumentChunk.page_number, DocumentChunk.text,
                             DocumentChunk.embedding.cosine_distance(qv).label("dist"))
                      .where(DocumentChunk.project_id == ev.project_id)
                      .order_by("dist").limit(60)).all()
    for doc_id, page, text, dist in rows:
        if doc_id in linked:
            continue
        sim = 1 - float(dist)
        if doc_id not in best or sim > best[doc_id]["similarity"]:
            best[doc_id] = {"document_id": doc_id, "page": page, "similarity": round(sim, 3), "excerpt": text[:300]}
    out = []
    for item in best.values():
        d = db.get(Document, item["document_id"])
        if not d or not d.is_latest or d.doc_type == "contract":
            continue
        prox = 0.0
        if d.doc_date:
            gap = abs((d.doc_date - ev.event_date).days)
            prox = max(0.0, 1 - gap / 60)
        item.update({"title": d.title, "doc_type": d.doc_type, "doc_date": d.doc_date.isoformat() if d.doc_date else None,
                     "score": round(0.75 * item["similarity"] + 0.25 * prox, 3)})
        out.append(item)
    out.sort(key=lambda x: -x["score"])
    return [o for o in out if o["score"] >= 0.15][:limit]


def run_for_event(db: Session, ev: ProjectEvent, *, user_id: str | None = None, today: date | None = None) -> list[Entitlement]:
    org = db.get(Organization, ev.org_id)
    project = db.get(Project, ev.project_id)
    cal = Calendar.from_org(org.weekend_days, org.holidays)
    clauses = _clauses(db, ev.project_id)
    docs = _linked_docs(db, ev.id)
    existing = {e.entitlement_type: e for e in db.execute(select(Entitlement).where(Entitlement.event_id == ev.id)).scalars()}
    valuations: dict[str, engine.ValuationIn] = {}
    for etype, ent in existing.items():
        v = db.execute(select(Valuation).where(Valuation.entitlement_id == ent.id)).scalar_one_or_none()
        if v and v.totals.get("gross_egp"):
            valuations[etype] = engine.ValuationIn(Decimal(v.totals["gross_egp"]), v.status, "EGP")
    findings = engine.discover(_event_in(ev), clauses, docs, valuations=valuations, cal=cal, today=today or date.today())

    # clause links (AI suggestions; user-confirmed links are kept)
    for link in db.execute(select(EventClauseLink).where(EventClauseLink.event_id == ev.id,
                                                         EventClauseLink.confirmed.is_(False))).scalars():
        db.delete(link)
    db.flush()
    if findings:
        for cs in findings[0].clause_scores[:6]:
            if cs["score"] < engine.CLAUSE_MIN_SCORE * 0.8:
                continue
            if db.get(EventClauseLink, (ev.id, cs["clause_id"])) is None:
                db.add(EventClauseLink(event_id=ev.id, clause_id=cs["clause_id"], org_id=ev.org_id, score=cs["score"],
                                       score_breakdown=cs["breakdown"], link_source="ai", confirmed=False))

    out = []
    for f in findings:
        ent = existing.get(f.entitlement_type)
        if ent is None:
            ent = Entitlement(org_id=ev.org_id, project_id=ev.project_id, event_id=ev.id,
                              ref=next_ref(db, Entitlement, ev.project_id, "ENT"), entitlement_type=f.entitlement_type,
                              currency=project.currency, is_demo=ev.is_demo)
            db.add(ent)
        human_locked = ent.status in ("substantiated", "rejected")
        ent.title = f.title[:300]
        if not human_locked:
            ent.status = f.status
        ent.primary_clause_id = f.primary_clause_id
        ent.related_clause_ids = f.related_clause_ids
        ent.conditions = f.conditions
        ent.evidence_available = f.evidence_available
        ent.evidence_missing = f.evidence_missing
        ent.evidence_completeness = f.evidence_completeness
        ent.financial_impact = f.financial_impact
        ent.financial_basis = f.financial_basis
        ent.time_impact_days = f.time_impact_days
        ent.notice = {"notice": f.notice, "detailed_claim": f.detailed_claim, "clause_scores": f.clause_scores,
                      "contradictions": f.contradictions}
        ent.exclusions = f.exclusions
        ent.risk_level = f.risk_level
        ent.risk_factors = f.risk_factors
        ent.confidence = f.confidence
        ent.confidence_breakdown = f.confidence_breakdown
        ent.explanation = f.explanation
        ent.facts = f.facts
        ent.assumptions = f.assumptions
        ent.recommended_actions = f.recommended_actions
        ent.engine_version = engine.ENGINE_VERSION
        db.flush()
        _sync_deadlines(db, ent, ev, f)
        out.append(ent)
    audit(db, org_id=ev.org_id, user_id=user_id, action="entitlement.discover", entity_type="event", entity_id=ev.id,
          detail={"findings": [(f.entitlement_type, f.status, f.confidence) for f in findings],
                  "engine": engine.ENGINE_VERSION})
    return out


def _sync_deadlines(db: Session, ent: Entitlement, ev: ProjectEvent, f: engine.Finding) -> None:
    for kind, info in (("notice", f.notice), ("detailed_claim", f.detailed_claim)):
        dl = db.execute(select(Deadline).where(Deadline.entitlement_id == ent.id, Deadline.deadline_type == kind)).scalar_one_or_none()
        if info is None or info.get("required") is None:
            if kind == "notice" and info is not None:
                # record that the deadline could not be determined (never silently dropped)
                if dl is None:
                    dl = Deadline(org_id=ent.org_id, project_id=ent.project_id, entitlement_id=ent.id, event_id=ev.id,
                                  deadline_type=kind, is_demo=ent.is_demo, title="")
                    db.add(dl)
                dl.title = f"{ent.ref}: notice requirement not identified — verify manually"
                dl.certainty, dl.due_date, dl.uncertainty_notes = "undetermined", None, info.get("notes", [])
            continue
        if dl is None:
            dl = Deadline(org_id=ent.org_id, project_id=ent.project_id, entitlement_id=ent.id, event_id=ev.id,
                          deadline_type=kind, is_demo=ent.is_demo, title="")
            db.add(dl)
        if dl.status == "completed":
            continue
        label = "Notice" if kind == "notice" else "Detailed claim"
        dl.title = f"{ent.ref}: {label} under Clause {info['clause']['clause_number']}"
        dl.clause_id = info["clause"]["clause_id"]
        dl.trigger_date = date.fromisoformat(info["trigger_date"])
        dl.trigger_description = info.get("trigger_wording")
        dl.period_days = info["period_days"]
        dl.day_type = info["day_type"]
        dl.due_date = date.fromisoformat(info["due_date"]) if info.get("due_date") else None
        dl.certainty = info["certainty"]
        dl.uncertainty_notes = info["notes"]
        dl.calculation = info["calculation"]
        if kind == "notice" and info["status"] in ("given_on_time", "given_late", "given"):
            dl.status = "completed"
            dl.completed_at = dl.completed_at or ent.updated_at


def run_for_project(db: Session, project_id: str, *, user_id: str | None = None) -> list[Entitlement]:
    out = []
    for ev in db.execute(select(ProjectEvent).where(ProjectEvent.project_id == project_id,
                                                    ProjectEvent.status != "closed")).scalars():
        out.extend(run_for_event(db, ev, user_id=user_id))
    return out


# ------------------------------------------------------------------ optional LLM narrative


def generate_narrative(db: Session, ent: Entitlement, language: str = "en") -> dict:
    org = db.get(Organization, ent.org_id)
    ev = db.get(ProjectEvent, ent.event_id)
    sources, allowed = [], set()
    sources.append({"id": "E1", "label": f"Event {ev.ref}", "text": f"{ev.title}\n{ev.event_date}\n{ev.description}"})
    allowed.add("E1")
    clause_ids = [ent.primary_clause_id, *ent.related_clause_ids][:5]
    for i, cid in enumerate([c for c in clause_ids if c], start=1):
        c = db.get(Clause, cid)
        if c:
            sources.append({"id": f"C{i}", "label": f"Clause {c.clause_number} {c.title} (p.{c.page_start})", "text": c.text[:3000]})
            allowed.add(f"C{i}")
    j = 1
    for ev_item in ent.evidence_available:
        for src in ev_item.get("sources", [])[:1]:
            sources.append({"id": f"D{j}", "label": f"{src.get('document_title')} p.{src.get('page')}",
                            "text": src.get("quote", "")[:1500]})
            allowed.add(f"D{j}")
            j += 1
    finding = {k: getattr(ent, k) for k in ("ref", "entitlement_type", "status", "evidence_missing", "financial_impact",
                                           "financial_basis", "time_impact_days", "risk_factors", "confidence",
                                           "assumptions")}
    finding["notice"] = ent.notice.get("notice")
    user = (f"Language: {'Arabic' if language == 'ar' else 'English'}\n\nStructured finding from the deterministic "
            f"engine:\n{dumps(finding)}\n\nSource excerpts (cite by id):\n{build_sources_block(sources)}")
    try:
        out, run = run_task(db, org=org, project_id=ent.project_id, prompt_id="entitlement_narrative", user_content=user,
                            allowed_citation_ids=allowed)
    except AiUnavailable as exc:
        return {"available": False, "reason": str(exc), "code": exc.code}
    out["citation_map"] = {s["id"]: s["label"] for s in sources}
    ent.narrative = {"language": language, "content": out, "ai_run_id": run.id, "model": run.model,
                     "prompt_version": run.prompt_version}
    return {"available": True, **ent.narrative}


def similarity(a: str, b: str) -> float:
    return cosine(embed(a), embed(b))
