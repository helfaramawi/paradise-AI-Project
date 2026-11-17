"""Entitlement discovery, explainable findings, human review and valuation worksheets."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from ..core.audit import audit
from ..core.deps import DB, Principal, get_owned, get_project, require
from ..engines import valuation as val_engine
from ..models import Clause, Document, Entitlement, Organization, ProjectEvent, Valuation, ValuationLine
from ..schemas import EntitlementOut, ReviewIn, ValuationIn
from ..services import discovery
from ..services.subscription import check_limit

router = APIRouter(tags=["entitlements"])


def _detail(db, e: Entitlement) -> dict:
    ev = db.get(ProjectEvent, e.event_id)
    clauses = []
    for cid in [e.primary_clause_id, *(e.related_clause_ids or [])]:
        c = db.get(Clause, cid) if cid else None
        if c:
            d = db.get(Document, c.document_id)
            clauses.append({"id": c.id, "clause_number": c.clause_number, "title": c.title, "category": c.category,
                            "text": c.text, "page_start": c.page_start, "page_end": c.page_end,
                            "document_id": c.document_id, "document_title": d.title if d else None,
                            "verification_status": c.verification_status, "primary": c.id == e.primary_clause_id,
                            "time_limits": c.time_limits})
    v = db.execute(select(Valuation).where(Valuation.entitlement_id == e.id)).scalar_one_or_none()
    return {**EntitlementOut.model_validate(e).model_dump(mode="json"),
            "event": {"id": ev.id, "ref": ev.ref, "title": ev.title, "event_date": ev.event_date, "category": ev.category,
                      "description": ev.description},
            "clauses": clauses, "valuation": _val_out(v) if v else None}


@router.post("/projects/{project_id}/discover")
def discover_project(project_id: str, db: DB, p: Annotated[Principal, Depends(require("entitlement.run"))]):
    get_project(db, project_id, p)
    ents = discovery.run_for_project(db, project_id, user_id=p.id)
    db.commit()
    return {"count": len(ents), "items": [EntitlementOut.model_validate(e) for e in ents]}


@router.post("/events/{event_id}/discover")
def discover_event(event_id: str, db: DB, p: Annotated[Principal, Depends(require("entitlement.run"))]):
    ev = get_owned(db, ProjectEvent, event_id, p)
    ents = discovery.run_for_event(db, ev, user_id=p.id)
    db.commit()
    return [_detail(db, e) for e in ents]


@router.get("/projects/{project_id}/entitlements")
def list_entitlements(project_id: str, db: DB, p: Annotated[Principal, Depends(require("entitlement.read"))],
                      status: str | None = None, risk: str | None = None):
    get_project(db, project_id, p)
    q = select(Entitlement).where(Entitlement.project_id == project_id)
    if status:
        q = q.where(Entitlement.status == status)
    if risk:
        q = q.where(Entitlement.risk_level == risk)
    rows = db.execute(q.order_by(Entitlement.ref)).scalars().all()
    events = {e.id: e for e in db.execute(select(ProjectEvent).where(ProjectEvent.project_id == project_id)).scalars()}
    return [{**EntitlementOut.model_validate(e).model_dump(mode="json", include={
        "id", "ref", "entitlement_type", "title", "status", "financial_impact", "financial_basis", "currency",
        "time_impact_days", "risk_level", "confidence", "evidence_completeness", "review_status", "is_demo", "event_id"}),
        "event_ref": events[e.event_id].ref if e.event_id in events else None,
        "notice_due": (e.notice or {}).get("notice", {}).get("due_date"),
        "notice_status": (e.notice or {}).get("notice", {}).get("status")} for e in rows]


@router.get("/entitlements")
def list_all(db: DB, p: Annotated[Principal, Depends(require("entitlement.read"))], ids: str = Query(..., max_length=20000)):
    """Drill-down helper used by the dashboard: fetch entitlements by id list (tenant-checked)."""
    out = []
    for i in ids.split(",")[:200]:
        try:
            e = get_owned(db, Entitlement, i, p)
        except HTTPException:
            continue
        out.append({**EntitlementOut.model_validate(e).model_dump(mode="json", include={
            "id", "ref", "project_id", "entitlement_type", "title", "status", "financial_impact", "risk_level",
            "confidence", "evidence_completeness", "review_status"})})
    return out


@router.get("/entitlements/{ent_id}")
def get_entitlement(ent_id: str, db: DB, p: Annotated[Principal, Depends(require("entitlement.read"))]):
    return _detail(db, get_owned(db, Entitlement, ent_id, p))


@router.post("/entitlements/{ent_id}/review")
def review(ent_id: str, body: ReviewIn, db: DB, p: Annotated[Principal, Depends(require("entitlement.review"))]):
    e = get_owned(db, Entitlement, ent_id, p)
    if body.decision == "substantiated":
        v = db.execute(select(Valuation).where(Valuation.entitlement_id == e.id)).scalar_one_or_none()
        needs_val = e.entitlement_type != "extension_of_time"
        if needs_val and (v is None or v.status != "verified"):
            raise HTTPException(409, "A verified valuation is required before marking an entitlement as substantiated")
        if any(m["critical"] for m in e.evidence_missing):
            raise HTTPException(409, "Critical evidence is still missing")
        e.status = "substantiated"
    elif body.decision == "rejected":
        e.status = "rejected"
    elif body.decision == "accepted" and e.status == "rejected":
        e.status = "potential"
    e.review_status = "accepted" if body.decision == "substantiated" else body.decision
    e.review_comment, e.reviewed_by, e.reviewed_at = body.comment, p.id, datetime.now(UTC)
    audit(db, org_id=p.org_id, user_id=p.id, action="entitlement.review", entity_type="entitlement", entity_id=e.id,
          detail={"decision": body.decision, "comment": body.comment}, ip=p.ip)
    db.commit()
    return _detail(db, e)


@router.post("/entitlements/{ent_id}/narrative")
def narrative(ent_id: str, db: DB, p: Annotated[Principal, Depends(require("entitlement.run"))],
              language: str = Query("en", pattern="^(en|ar)$")):
    e = get_owned(db, Entitlement, ent_id, p)
    check_limit(db, p.org_id, "ai_tokens")
    out = discovery.generate_narrative(db, e, language)
    db.commit()
    return out


# ------------------------------------------------------------------ valuation


def _val_out(v: Valuation) -> dict:
    return {"id": v.id, "entitlement_id": v.entitlement_id, "currency": v.currency, "fx_rate_to_egp": v.fx_rate_to_egp,
            "overhead_pct": v.overhead_pct, "profit_pct": v.profit_pct, "vat_applicable": v.vat_applicable,
            "vat_rate": v.vat_rate, "assumptions": v.assumptions, "contractual_basis_note": v.contractual_basis_note,
            "status": v.status, "totals": v.totals, "calculated_at": v.calculated_at, "verified_by": v.verified_by,
            "verified_at": v.verified_at,
            "lines": [{"id": ln.id, "category": ln.category, "description": ln.description, "quantity": ln.quantity,
                       "unit": ln.unit, "rate": ln.rate, "source_document_id": ln.source_document_id,
                       "source_page": ln.source_page, "source_note": ln.source_note, "rate_basis": ln.rate_basis}
                      for ln in v.lines]}


@router.get("/entitlements/{ent_id}/valuation")
def get_valuation(ent_id: str, db: DB, p: Annotated[Principal, Depends(require("entitlement.read"))]):
    e = get_owned(db, Entitlement, ent_id, p)
    v = db.execute(select(Valuation).where(Valuation.entitlement_id == e.id)).scalar_one_or_none()
    return _val_out(v) if v else None


def save_valuation(db, e: Entitlement, body: ValuationIn, p: Principal) -> Valuation:
    org = db.get(Organization, e.org_id)
    vat_rate = body.vat_rate if body.vat_rate is not None else org.vat_rate
    lines = []
    for ln in body.lines:
        src = None
        if ln.source_document_id:
            d = get_owned(db, Document, ln.source_document_id, p)
            if d.project_id != e.project_id:
                raise HTTPException(422, "Source document belongs to another project")
            src = f"{d.title}" + (f" p.{ln.source_page}" if ln.source_page else "")
        lines.append(val_engine.LineIn(ln.category, ln.description, ln.quantity, ln.rate, ln.unit,
                                       src or ln.source_note))
    try:
        totals = val_engine.calculate(lines, overhead_pct=body.overhead_pct, profit_pct=body.profit_pct,
                                      vat_applicable=body.vat_applicable, vat_rate=Decimal(vat_rate),
                                      currency=body.currency, fx_rate_to_egp=body.fx_rate_to_egp)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    v = db.execute(select(Valuation).where(Valuation.entitlement_id == e.id)).scalar_one_or_none()
    if v is None:
        v = Valuation(org_id=e.org_id, project_id=e.project_id, entitlement_id=e.id, created_by=p.id)
        db.add(v)
    v.currency, v.fx_rate_to_egp, v.overhead_pct, v.profit_pct = body.currency, body.fx_rate_to_egp, body.overhead_pct, body.profit_pct
    v.vat_applicable, v.vat_rate, v.assumptions = body.vat_applicable, vat_rate, body.assumptions
    v.contractual_basis_note = body.contractual_basis_note
    v.status, v.verified_by, v.verified_at = "draft", None, None
    v.created_by = p.id  # last preparer (used for separation of duties)
    v.lines.clear()
    db.flush()
    for i, ln in enumerate(body.lines):
        v.lines.append(ValuationLine(position=i, **ln.model_dump()))
    v.totals = totals
    v.calculated_at = datetime.now(UTC)
    e.financial_impact = Decimal(totals["gross_egp"])
    e.financial_basis = "valuation_draft"
    db.flush()
    return v


@router.put("/entitlements/{ent_id}/valuation")
def put_valuation(ent_id: str, body: ValuationIn, db: DB, p: Annotated[Principal, Depends(require("valuation.write"))]):
    e = get_owned(db, Entitlement, ent_id, p)
    v = save_valuation(db, e, body, p)
    audit(db, org_id=p.org_id, user_id=p.id, action="valuation.save", entity_type="entitlement", entity_id=e.id,
          detail={"gross_egp": v.totals["gross_egp"], "lines": len(body.lines)}, ip=p.ip)
    db.commit()
    return _val_out(v)


@router.post("/entitlements/{ent_id}/valuation/verify")
def verify_valuation(ent_id: str, db: DB, p: Annotated[Principal, Depends(require("valuation.verify"))]):
    e = get_owned(db, Entitlement, ent_id, p)
    v = db.execute(select(Valuation).where(Valuation.entitlement_id == e.id)).scalar_one_or_none()
    if not v or not v.lines:
        raise HTTPException(409, "No valuation to verify")
    if v.created_by == p.id:
        raise HTTPException(409, "Separation of duties: the preparer cannot verify their own valuation")
    v.status, v.verified_by, v.verified_at = "verified", p.id, datetime.now(UTC)
    e.financial_basis = "valuation_verified"
    audit(db, org_id=p.org_id, user_id=p.id, action="valuation.verify", entity_type="entitlement", entity_id=e.id,
          detail={"gross_egp": v.totals.get("gross_egp")}, ip=p.ip)
    db.commit()
    return _val_out(v)
