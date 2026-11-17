"""Document upload, processing status, secure download, pages, BOQ items and semantic search."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from ..core.audit import audit, log_document_access
from ..core.deps import DB, Principal, get_owned, get_project, require
from ..engines.bm25 import BM25
from ..engines.embeddings import embed
from ..models import BoqItem, Document, DocumentChunk, DocumentPage, Job
from ..schemas import DocumentOut, DocumentUpdate
from ..services.pipeline import reprocess, upload_document
from ..services.storage import get_store

router = APIRouter(tags=["documents"])


@router.post("/projects/{project_id}/documents", status_code=201)
async def upload(project_id: str, db: DB, p: Annotated[Principal, Depends(require("document.upload"))],
                 file: UploadFile = File(...), title: str | None = Form(None), doc_type: str | None = Form(None),
                 doc_date: date | None = Form(None), author_party: str | None = Form(None)):
    get_project(db, project_id, p)
    data = await file.read()
    doc = upload_document(db, org_id=p.org_id, project_id=project_id, user_id=p.id, filename=file.filename or "upload",
                          data=data, title=title, declared_type=doc_type or None, doc_date=doc_date,
                          author_party=author_party or None)
    log_document_access(db, org_id=p.org_id, user_id=p.id, document_id=doc.id, action="upload", ip=p.ip)
    db.commit()
    db.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.get("/projects/{project_id}/documents")
def list_documents(project_id: str, db: DB, p: Annotated[Principal, Depends(require("document.read"))],
                   doc_type: str | None = None, include_old_versions: bool = False):
    get_project(db, project_id, p)
    q = select(Document).where(Document.project_id == project_id)
    if not include_old_versions:
        q = q.where(Document.is_latest.is_(True))
    if doc_type:
        q = q.where(Document.doc_type == doc_type)
    return [DocumentOut.model_validate(d) for d in db.execute(q.order_by(Document.created_at.desc())).scalars()]


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, db: DB, p: Annotated[Principal, Depends(require("document.read"))]):
    d = get_owned(db, Document, doc_id, p)
    versions = db.execute(select(Document.id, Document.version, Document.created_at)
                          .where(Document.project_id == d.project_id, Document.filename == d.filename)
                          .order_by(Document.version)).all()
    job = db.execute(select(Job).where(Job.kind == "process_document", Job.payload["document_id"].as_string() == d.id)
                     .order_by(Job.created_at.desc()).limit(1)).scalar_one_or_none()
    log_document_access(db, org_id=p.org_id, user_id=p.id, document_id=d.id, action="view", ip=p.ip)
    db.commit()
    return {**DocumentOut.model_validate(d).model_dump(mode="json"),
            "versions": [{"id": i, "version": v, "created_at": c} for i, v, c in versions],
            "job": None if not job else {"status": job.status, "attempts": job.attempts, "error": (job.error or "")[:500],
                                         "result": job.result}}


@router.patch("/documents/{doc_id}")
def update_document(doc_id: str, body: DocumentUpdate, db: DB, p: Annotated[Principal, Depends(require("document.upload"))]):
    d = get_owned(db, Document, doc_id, p)
    data = body.model_dump(exclude_unset=True)
    retype = "doc_type" in data and data["doc_type"] != d.doc_type
    for k, v in data.items():
        setattr(d, k, v)
    if retype:
        d.declared_type = d.doc_type
    audit(db, org_id=p.org_id, user_id=p.id, action="document.update", entity_type="document", entity_id=d.id,
          detail={k: str(v) for k, v in data.items()}, ip=p.ip)
    if retype:
        reprocess(db, d)
    db.commit()
    return DocumentOut.model_validate(d)


@router.post("/documents/{doc_id}/reprocess")
def reprocess_document(doc_id: str, db: DB, p: Annotated[Principal, Depends(require("contract.analyze"))]):
    d = get_owned(db, Document, doc_id, p)
    reprocess(db, d)
    audit(db, org_id=p.org_id, user_id=p.id, action="document.reprocess", entity_type="document", entity_id=d.id, ip=p.ip)
    db.commit()
    return {"status": d.status}


@router.get("/documents/{doc_id}/download")
def download(doc_id: str, db: DB, p: Annotated[Principal, Depends(require("document.read"))]):
    d = get_owned(db, Document, doc_id, p)
    data = get_store().get(d.storage_key, d.sha256)
    log_document_access(db, org_id=p.org_id, user_id=p.id, document_id=d.id, action="download", ip=p.ip)
    db.commit()
    inline = d.mime_type in ("application/pdf", "image/png", "image/jpeg")
    disp = "inline" if inline else "attachment"
    return Response(data, media_type=d.mime_type, headers={
        "Content-Disposition": f"{disp}; filename*=UTF-8''{quote(d.filename)}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@router.get("/documents/{doc_id}/pages")
def pages(doc_id: str, db: DB, p: Annotated[Principal, Depends(require("document.read"))],
          page: int | None = Query(None, ge=1)):
    d = get_owned(db, Document, doc_id, p)
    q = select(DocumentPage).where(DocumentPage.document_id == d.id)
    if page:
        q = q.where(DocumentPage.page_number == page)
    return [{"page": x.page_number, "text": x.text, "method": x.method, "estimated": x.page_is_estimated}
            for x in db.execute(q.order_by(DocumentPage.page_number)).scalars()]


@router.get("/projects/{project_id}/boq")
def boq(project_id: str, db: DB, p: Annotated[Principal, Depends(require("document.read"))], q: str | None = None):
    get_project(db, project_id, p)
    rows = db.execute(select(BoqItem).where(BoqItem.project_id == project_id).order_by(BoqItem.sheet, BoqItem.row_number)).scalars().all()
    items = [{"id": r.id, "document_id": r.document_id, "sheet": r.sheet, "row": r.row_number, "item_ref": r.item_ref,
              "description": r.description, "unit": r.unit, "quantity": r.quantity, "rate": r.rate, "amount": r.amount}
             for r in rows]
    if q and items:
        scores = BM25([i["description"] for i in items]).score(q)
        items = [i for s, i in sorted(zip(scores, items, strict=True), key=lambda x: -x[0]) if s > 0][:30]
    return items


@router.get("/projects/{project_id}/search")
def search(project_id: str, db: DB, p: Annotated[Principal, Depends(require("document.read"))],
           q: str = Query(min_length=2, max_length=500), limit: int = Query(10, le=30)):
    """Hybrid retrieval: pgvector cosine over local embeddings, re-ranked with BM25."""
    get_project(db, project_id, p)
    qv = embed(q)
    rows = db.execute(select(DocumentChunk, Document.title, DocumentChunk.embedding.cosine_distance(qv).label("dist"))
                      .join(Document, Document.id == DocumentChunk.document_id)
                      .where(DocumentChunk.project_id == project_id, DocumentChunk.org_id == p.org_id,
                             Document.is_latest.is_(True))
                      .order_by("dist").limit(60)).all()
    if not rows:
        return []
    bm = BM25([r[0].text for r in rows]).score(q)
    top = max(bm) or 1
    out = [{"document_id": c.document_id, "document_title": t, "page": c.page_number, "text": c.text,
            "score": round(0.6 * (1 - float(dist)) + 0.4 * (b / top), 3)} for (c, t, dist), b in zip(rows, bm, strict=True)]
    out.sort(key=lambda x: -x["score"])
    return out[:limit]
