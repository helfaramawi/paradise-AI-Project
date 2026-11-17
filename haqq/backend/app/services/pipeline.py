"""Document ingestion pipeline and job handlers.

upload → (validate, hash, version, store) → job "process_document":
    extract pages (text layer, OCR fallback) → classify → injection scan → detect date/author →
    chunk + embed → BOQ rows → (contract documents) clause extraction + analysis
"""

from __future__ import annotations

import logging
import re
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..ai.guard import scan
from ..config import get_settings
from ..core.audit import audit
from ..core.text import detect_language, norm
from ..engines import contract as contract_engine
from ..engines.embeddings import chunk_text, embed
from ..engines.extraction import Page, UnsupportedFile, extract, find_dates, sniff
from ..models import BoqItem, Clause, Document, DocumentChunk, DocumentPage, UsageRecord
from .jobs import enqueue, handler
from .storage import get_store, sha256
from .subscription import check_limit

log = logging.getLogger("haqq.pipeline")
CONTRACT_TYPES = {"contract"}
DECLARABLE = {"contract", "boq", "site_instruction", "variation_order", "notice", "letter", "email", "meeting_minutes",
              "daily_report", "progress_report", "programme", "drawing", "payment_certificate", "cost_record", "photo",
              "other"}


def upload_document(db: Session, *, org_id: str, project_id: str, user_id: str | None, filename: str, data: bytes,
                    title: str | None = None, declared_type: str | None = None, doc_date: date | None = None,
                    author_party: str | None = None, is_demo: bool = False) -> Document:
    s = get_settings()
    if len(data) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds {s.max_upload_mb} MB")
    if declared_type and declared_type not in DECLARABLE:
        raise HTTPException(422, "Unknown document type")
    if author_party and author_party not in ("contractor", "employer", "engineer", "subcontractor", "other"):
        raise HTTPException(422, "Unknown author party")
    try:
        ext, mime = sniff(filename, data)
    except UnsupportedFile as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    check_limit(db, org_id, "documents")
    safe_name = re.sub(r"[^\w.\- ؀-ۿ]", "_", filename)[-200:]
    digest = sha256(data)
    dup = db.execute(select(Document).where(Document.project_id == project_id, Document.sha256 == digest,
                                            Document.is_latest.is_(True))).scalar_one_or_none()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This exact file is already uploaded as '{dup.title}'")
    prev = db.execute(select(Document).where(Document.project_id == project_id, Document.filename == safe_name,
                                             Document.is_latest.is_(True))).scalar_one_or_none()
    version = 1
    if prev:
        prev.is_latest = False
        version = prev.version + 1
    doc = Document(org_id=org_id, project_id=project_id, title=(title or safe_name.rsplit(".", 1)[0])[:300],
                   filename=safe_name, mime_type=mime, size_bytes=len(data), sha256=digest, storage_key="",
                   version=version, previous_version_id=prev.id if prev else None, declared_type=declared_type,
                   doc_date=doc_date, author_party=author_party, uploaded_by=user_id, is_demo=is_demo,
                   meta={"ext": ext})
    db.add(doc)
    db.flush()
    doc.storage_key = f"{org_id}/{project_id}/{doc.id}/v{version}{ext}"
    get_store().put(doc.storage_key, data)
    db.add(UsageRecord(org_id=org_id, metric="documents", quantity=1, reference=doc.id))
    audit(db, org_id=org_id, user_id=user_id, action="document.upload", entity_type="document", entity_id=doc.id,
          detail={"filename": safe_name, "sha256": digest, "version": version})
    enqueue(db, org_id, "process_document", {"document_id": doc.id})
    return doc


@handler("process_document")
def process_document(db: Session, payload: dict) -> dict:
    doc = db.get(Document, payload["document_id"])
    if doc is None:
        return {"skipped": "missing"}
    doc.status = "processing"
    db.commit()
    data = get_store().get(doc.storage_key, doc.sha256)
    ext = doc.meta.get("ext", "")
    ex = extract(ext, data)

    # reset derived data (re-processing is idempotent)
    for model in (DocumentPage, DocumentChunk, BoqItem, Clause):
        db.execute(delete(model).where(model.document_id == doc.id))

    for p in ex.pages:
        db.add(DocumentPage(org_id=doc.org_id, document_id=doc.id, page_number=p.number, text=p.text, method=p.method,
                            page_is_estimated=p.estimated))
    full = ex.full_text
    dtype, conf, scores = contract_engine.classify_document(full, doc.filename, ext, ex.meta)
    doc.doc_type = doc.declared_type or dtype
    doc.doc_type_confidence = 1.0 if doc.declared_type else conf
    doc.language = detect_language(full)
    doc.page_count = len(ex.pages)
    doc.ocr_pages = ex.ocr_pages
    doc.extraction_method = ex.method
    doc.security_flags = scan(full)
    meta = dict(doc.meta)
    meta.update({"classifier": {"type": dtype, "confidence": conf, "scores": scores}, **{k: v for k, v in ex.meta.items()
                                                                                         if k != "warning"}})
    if ex.meta.get("warning"):
        meta["warning"] = ex.meta["warning"]
    doc.meta = meta
    if doc.doc_date is None:
        dates = find_dates(full[:2500])
        if dates:
            doc.doc_date = dates[0]
    if doc.author_party is None:
        doc.author_party = _guess_author(full[:1500])

    # chunks + embeddings for semantic retrieval
    for p in ex.pages:
        for i, ch in enumerate(chunk_text(p.text)):
            db.add(DocumentChunk(org_id=doc.org_id, project_id=doc.project_id, document_id=doc.id,
                                 page_number=p.number, chunk_index=i, text=ch, embedding=embed(ch)))
    for r in ex.boq_rows:
        db.add(BoqItem(org_id=doc.org_id, project_id=doc.project_id, document_id=doc.id, sheet=r.sheet,
                       row_number=r.row_number, item_ref=r.item_ref, description=r.description[:2000], unit=r.unit,
                       quantity=r.quantity, rate=r.rate, amount=r.amount))
    clauses = 0
    if doc.doc_type in CONTRACT_TYPES:
        clauses = extract_clauses(db, doc, ex.pages)
    db.add(UsageRecord(org_id=doc.org_id, metric="pages", quantity=len(ex.pages), reference=doc.id))
    if ex.ocr_pages:
        db.add(UsageRecord(org_id=doc.org_id, metric="ocr_pages", quantity=ex.ocr_pages, reference=doc.id))
    doc.status = "processed"
    doc.error = None
    db.commit()
    return {"pages": len(ex.pages), "clauses": clauses, "boq_rows": len(ex.boq_rows), "type": doc.doc_type}


@handler("process_document:failed")
def process_document_failed(db: Session, payload: dict) -> None:
    doc = db.get(Document, payload["document_id"])
    if doc:
        doc.status = "failed"
        doc.error = "Processing failed after retries; see the job log."


def extract_clauses(db: Session, doc: Document, pages: list[Page]) -> int:
    analyzed = contract_engine.analyze_contract(pages)
    for a in analyzed:
        db.add(Clause(org_id=doc.org_id, project_id=doc.project_id, document_id=doc.id, clause_number=a.number,
                      title=a.title, parent_title=a.parent_title, text=a.text, language=a.language,
                      page_start=a.page_start, page_end=a.page_end, page_is_estimated=a.page_is_estimated,
                      category=a.category, secondary_categories=a.secondary_categories, obligations=a.obligations,
                      entitlements=a.entitlements, conditions=a.conditions, time_limits=a.time_limits,
                      exclusions=a.exclusions, percentages=a.percentages, risk_flags=a.risk_flags,
                      confidence=a.confidence, extraction_method="rules",
                      embedding=embed(f"{a.parent_title or ''} {a.title} {a.text}")))
    return len(analyzed)


def reprocess(db: Session, doc: Document) -> None:
    doc.status = "uploaded"
    enqueue(db, doc.org_id, "process_document", {"document_id": doc.id})


def _guess_author(head: str) -> str | None:
    t = norm(head)
    if re.search(r"from:\s*.{0,40}(contractor|construction)|^from the contractor|من:\s*.{0,30}(المقاول|شركه .{0,20}للمقاولات)", t):
        return "contractor"
    if re.search(r"from:\s*.{0,40}(employer|developer|owner)|من:\s*.{0,30}(صاحب العمل|المالك|للتطوير)", t):
        return "employer"
    if re.search(r"from:\s*.{0,40}(engineer|consultant)|من:\s*.{0,30}(المهندس|الاستشاري)", t):
        return "engineer"
    return None


def project_document_stats(db: Session, project_id: str) -> dict:
    rows = db.execute(select(Document.status, func.count()).where(Document.project_id == project_id,
                                                                  Document.is_latest.is_(True))
                      .group_by(Document.status)).all()
    return dict(rows)
