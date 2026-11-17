"""Project Event Intelligence: event register, AI classification, evidence association, clause links."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..core.audit import audit
from ..core.deps import DB, Principal, get_owned, get_project, require
from ..engines.entitlement import classify_event
from ..models import Clause, Document, EventClauseLink, EventDocument, ProjectEvent, User
from ..schemas import ClassifyIn, EventIn, EventOut, EventUpdate, LinkDocIn
from ..services.discovery import next_ref, suggest_documents

router = APIRouter(tags=["events"])


def _event_detail(db, ev: ProjectEvent) -> dict:
    docs = db.execute(select(Document, EventDocument).join(EventDocument, EventDocument.document_id == Document.id)
                      .where(EventDocument.event_id == ev.id)).all()
    links = db.execute(select(Clause, EventClauseLink).join(EventClauseLink, EventClauseLink.clause_id == Clause.id)
                       .where(EventClauseLink.event_id == ev.id).order_by(EventClauseLink.score.desc())).all()
    return {**EventOut.model_validate(ev).model_dump(mode="json"),
            "documents": [{"id": d.id, "title": d.title, "doc_type": d.doc_type, "doc_date": d.doc_date,
                           "author_party": d.author_party, "link_source": lk.link_source, "confirmed": lk.confirmed,
                           "relevance": lk.relevance} for d, lk in docs],
            "clause_links": [{"clause_id": c.id, "clause_number": c.clause_number, "title": c.title, "category": c.category,
                              "page": c.page_start, "score": lk.score, "breakdown": lk.score_breakdown,
                              "source": lk.link_source, "confirmed": lk.confirmed} for c, lk in links]}


@router.post("/events/classify")
def classify(body: ClassifyIn, p: Annotated[Principal, Depends(require("event.read"))]):
    cat, conf, scores = classify_event(body.text)
    return {"category": cat, "confidence": conf, "scores": scores, "method": "keyword-rules"}


@router.get("/projects/{project_id}/events")
def list_events(project_id: str, db: DB, p: Annotated[Principal, Depends(require("event.read"))]):
    get_project(db, project_id, p)
    rows = db.execute(select(ProjectEvent).where(ProjectEvent.project_id == project_id)
                      .order_by(ProjectEvent.event_date.desc())).scalars().all()
    out = []
    for ev in rows:
        n = len(db.execute(select(EventDocument.document_id).where(EventDocument.event_id == ev.id,
                                                                   EventDocument.confirmed.is_(True))).all())
        out.append({**EventOut.model_validate(ev).model_dump(mode="json"), "document_count": n})
    return out


@router.post("/projects/{project_id}/events", status_code=201)
def create_event(project_id: str, body: EventIn, db: DB, p: Annotated[Principal, Depends(require("event.write"))]):
    proj = get_project(db, project_id, p)
    suggested, conf, _ = classify_event(f"{body.title}. {body.description}")
    category = body.category or suggested
    if body.reviewer_id:
        r = db.get(User, body.reviewer_id)
        if not r or r.org_id != p.org_id:
            raise HTTPException(422, "Reviewer not found")
    ev = ProjectEvent(org_id=p.org_id, project_id=project_id, ref=next_ref(db, ProjectEvent, project_id, "EV"),
                      title=body.title, description=body.description, event_date=body.event_date,
                      awareness_date=body.awareness_date, category=category,
                      category_source="user" if body.category else "ai", suggested_category=suggested,
                      suggested_category_confidence=conf, responsible_party=body.responsible_party,
                      impacted_activities=body.impacted_activities, est_cost_impact=body.est_cost_impact,
                      est_time_impact_days=body.est_time_impact_days, currency=body.currency or proj.currency,
                      reviewer_id=body.reviewer_id, created_by=p.id, is_demo=proj.is_demo)
    db.add(ev)
    db.flush()
    for did in body.document_ids:
        d = get_owned(db, Document, did, p)
        if d.project_id != project_id:
            raise HTTPException(422, "Document belongs to another project")
        db.add(EventDocument(event_id=ev.id, document_id=d.id, org_id=p.org_id, link_source="user", confirmed=True))
    audit(db, org_id=p.org_id, user_id=p.id, action="event.create", entity_type="event", entity_id=ev.id,
          detail={"category": category, "category_source": ev.category_source}, ip=p.ip)
    db.commit()
    return _event_detail(db, ev)


@router.get("/events/{event_id}")
def get_event(event_id: str, db: DB, p: Annotated[Principal, Depends(require("event.read"))]):
    return _event_detail(db, get_owned(db, ProjectEvent, event_id, p))


@router.patch("/events/{event_id}")
def update_event(event_id: str, body: EventUpdate, db: DB, p: Annotated[Principal, Depends(require("event.write"))]):
    ev = get_owned(db, ProjectEvent, event_id, p)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(ev, k, v)
    if "category" in data:
        ev.category_source = "user"
    audit(db, org_id=p.org_id, user_id=p.id, action="event.update", entity_type="event", entity_id=ev.id,
          detail={k: str(v) for k, v in data.items()}, ip=p.ip)
    db.commit()
    return _event_detail(db, ev)


@router.post("/events/{event_id}/documents")
def link_document(event_id: str, body: LinkDocIn, db: DB, p: Annotated[Principal, Depends(require("event.write"))]):
    ev = get_owned(db, ProjectEvent, event_id, p)
    d = get_owned(db, Document, body.document_id, p)
    if d.project_id != ev.project_id:
        raise HTTPException(422, "Document belongs to another project")
    link = db.get(EventDocument, (ev.id, d.id))
    if link:
        link.confirmed = body.confirmed
    else:
        db.add(EventDocument(event_id=ev.id, document_id=d.id, org_id=p.org_id, link_source="user", confirmed=body.confirmed))
    audit(db, org_id=p.org_id, user_id=p.id, action="event.link_document", entity_type="event", entity_id=ev.id,
          detail={"document": d.id}, ip=p.ip)
    db.commit()
    return _event_detail(db, ev)


@router.delete("/events/{event_id}/documents/{doc_id}")
def unlink_document(event_id: str, doc_id: str, db: DB, p: Annotated[Principal, Depends(require("event.write"))]):
    ev = get_owned(db, ProjectEvent, event_id, p)
    link = db.get(EventDocument, (ev.id, doc_id))
    if link:
        db.delete(link)
        audit(db, org_id=p.org_id, user_id=p.id, action="event.unlink_document", entity_type="event", entity_id=ev.id,
              detail={"document": doc_id}, ip=p.ip)
        db.commit()
    return _event_detail(db, ev)


@router.get("/events/{event_id}/suggested-documents")
def suggested(event_id: str, db: DB, p: Annotated[Principal, Depends(require("event.read"))]):
    ev = get_owned(db, ProjectEvent, event_id, p)
    return suggest_documents(db, ev)


@router.post("/events/{event_id}/clauses/{clause_id}/confirm")
def confirm_clause(event_id: str, clause_id: str, db: DB, p: Annotated[Principal, Depends(require("event.write"))]):
    ev = get_owned(db, ProjectEvent, event_id, p)
    c = get_owned(db, Clause, clause_id, p)
    link = db.get(EventClauseLink, (ev.id, c.id))
    if link is None:
        link = EventClauseLink(event_id=ev.id, clause_id=c.id, org_id=p.org_id, score=1.0, link_source="user")
        db.add(link)
    link.confirmed = True
    db.commit()
    return _event_detail(db, ev)
