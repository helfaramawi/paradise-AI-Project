"""Contract Intelligence Repository: clauses, verification, deadlines-in-contract and contract Q&A (RAG)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from ..ai.service import AiUnavailable, build_sources_block, run_task
from ..core.audit import audit
from ..core.deps import DB, Principal, get_owned, get_project, require
from ..engines.bm25 import BM25
from ..engines.embeddings import embed
from ..engines.taxonomy import CLAUSE_CATEGORIES
from ..models import Clause, Document, Organization
from ..schemas import AskIn, ClauseOut, ClauseVerifyIn

router = APIRouter(tags=["contract-intelligence"])


@router.get("/projects/{project_id}/clauses")
def list_clauses(project_id: str, db: DB, p: Annotated[Principal, Depends(require("document.read"))],
                 category: str | None = None, document_id: str | None = None, q: str | None = Query(None, max_length=300),
                 has_time_limit: bool | None = None, verification: str | None = None):
    get_project(db, project_id, p)
    query = select(Clause, Document.title).join(Document, Document.id == Clause.document_id).where(
        Clause.project_id == project_id, Document.is_latest.is_(True))
    if category:
        query = query.where(Clause.category == category)
    if document_id:
        query = query.where(Clause.document_id == document_id)
    if verification:
        query = query.where(Clause.verification_status == verification)
    rows = db.execute(query).all()
    items = [{**ClauseOut.model_validate(c).model_dump(mode="json"), "document_title": t} for c, t in rows]
    if has_time_limit:
        items = [i for i in items if i["time_limits"]]
    if q and items:
        scores = BM25([f"{i['clause_number']} {i['title']} {i['text']}" for i in items]).score(q)
        items = [i for s, i in sorted(zip(scores, items, strict=True), key=lambda x: -x[0]) if s > 0]
    else:
        def key(i):
            return [int(x) if x.isdigit() else 0 for x in i["clause_number"].split(".")]
        items.sort(key=key)
    return items


@router.get("/projects/{project_id}/clauses/summary")
def clause_summary(project_id: str, db: DB, p: Annotated[Principal, Depends(require("document.read"))]):
    get_project(db, project_id, p)
    rows = db.execute(select(Clause.category, func.count()).where(Clause.project_id == project_id)
                      .group_by(Clause.category)).all()
    clauses = db.execute(select(Clause).where(Clause.project_id == project_id)).scalars().all()
    time_limits = [{"clause_id": c.id, "clause_number": c.clause_number, "title": c.title, "page": c.page_start, **t}
                   for c in clauses for t in (c.time_limits or [])]
    return {"by_category": [{"category": k, "count": n, "en": CLAUSE_CATEGORIES.get(k, {}).get("en", k),
                             "ar": CLAUSE_CATEGORIES.get(k, {}).get("ar", k)} for k, n in rows],
            "time_limits": sorted(time_limits, key=lambda t: t["days"]),
            "risk_flags": sum(len(c.risk_flags or []) for c in clauses),
            "verified": len([c for c in clauses if c.verification_status == "verified"]), "total": len(clauses)}


@router.get("/clauses/{clause_id}")
def get_clause(clause_id: str, db: DB, p: Annotated[Principal, Depends(require("document.read"))]):
    c = get_owned(db, Clause, clause_id, p)
    d = db.get(Document, c.document_id)
    return {**ClauseOut.model_validate(c).model_dump(mode="json"), "document_title": d.title, "document_id": d.id}


@router.post("/clauses/{clause_id}/verify")
def verify_clause(clause_id: str, body: ClauseVerifyIn, db: DB, p: Annotated[Principal, Depends(require("clause.verify"))]):
    c = get_owned(db, Clause, clause_id, p)
    if body.category:
        if body.category not in CLAUSE_CATEGORIES:
            raise HTTPException(422, "Unknown category")
        c.category = body.category
    if body.time_limits is not None:
        for t in body.time_limits:
            if not isinstance(t.get("days"), int) or t.get("day_type") not in ("calendar", "working", "unspecified"):
                raise HTTPException(422, "Each time limit needs integer 'days' and a valid 'day_type'")
            t.setdefault("kind", "notice")
            t.setdefault("time_bar", False)
            t.setdefault("sentence", "(entered by reviewer)")
            t.setdefault("stated", f"{t['days']} days")
            t["source"] = "reviewer"
        c.time_limits = body.time_limits
    c.verification_status = body.status
    c.reviewer_note = body.note
    c.verified_by, c.verified_at = p.id, datetime.now(UTC)
    audit(db, org_id=p.org_id, user_id=p.id, action="clause.verify", entity_type="clause", entity_id=c.id,
          detail={"status": body.status, "category": body.category}, ip=p.ip)
    db.commit()
    return ClauseOut.model_validate(c)


@router.post("/projects/{project_id}/ask")
def ask_contract(project_id: str, body: AskIn, db: DB, p: Annotated[Principal, Depends(require("document.read"))]):
    """Retrieve the most relevant clauses; if an LLM is configured and allowed, answer with citations.
    Otherwise return the retrieved passages (extractive answer)."""
    get_project(db, project_id, p)
    qv = embed(body.question)
    rows = db.execute(select(Clause, Document.title, Clause.embedding.cosine_distance(qv).label("d"))
                      .join(Document, Document.id == Clause.document_id)
                      .where(Clause.project_id == project_id, Clause.org_id == p.org_id, Document.is_latest.is_(True))
                      .order_by("d").limit(30)).all()
    if not rows:
        return {"mode": "none", "answer": None, "passages": [], "message": "No analysed contract clauses in this project yet."}
    bm = BM25([f"{c.title} {c.text}" for c, _, _ in rows]).score(body.question)
    top = max(bm) or 1
    ranked = sorted(((0.5 * (1 - float(d)) + 0.5 * b / top, c, t) for (c, t, d), b in zip(rows, bm, strict=True)),
                    key=lambda x: -x[0])[:6]
    passages = [{"id": f"C{i}", "clause_id": c.id, "clause_number": c.clause_number, "title": c.title,
                 "document_title": t, "page": c.page_start, "text": c.text[:1800], "score": round(s, 3)}
                for i, (s, c, t) in enumerate(ranked, start=1)]
    org = db.get(Organization, p.org_id)
    sources = [{"id": x["id"], "label": f"Clause {x['clause_number']} {x['title']} ({x['document_title']} p.{x['page']})",
                "text": x["text"]} for x in passages]
    user = (f"Language: {'Arabic' if body.language == 'ar' else 'English'}\nQuestion: {body.question}\n\n"
            f"Retrieved passages:\n{build_sources_block(sources)}")
    try:
        out, run = run_task(db, org=org, project_id=project_id, prompt_id="contract_qa", user_content=user,
                            allowed_citation_ids={s["id"] for s in sources})
        db.commit()
        return {"mode": "llm", "answer": out, "passages": passages, "model": run.model, "ai_run_id": run.id}
    except AiUnavailable as exc:
        db.commit()
        return {"mode": "extractive", "answer": None, "passages": passages, "ai_unavailable": exc.code,
                "message": str(exc)}
