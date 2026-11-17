"""Claims management: lifecycle, history, document generation and secure download."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select

from ..core.audit import audit
from ..core.deps import DB, Principal, accessible_project_ids, get_owned, get_project, require
from ..engines.taxonomy import ENTITLEMENT_TYPES
from ..models import Claim, ClaimDocument, ClaimStageHistory, Entitlement, UsageRecord, User
from ..schemas import ClaimIn, ClaimOut, GenerateIn, TransitionIn
from ..services import claimdocs
from ..services.claims import FLOW, GATES, STAGE_LABELS, STAGES, transition
from ..services.discovery import next_ref
from ..services.storage import get_store

router = APIRouter(tags=["claims"])


def _detail(db, c: Claim, p: Principal) -> dict:
    hist = db.execute(select(ClaimStageHistory).where(ClaimStageHistory.claim_id == c.id)
                      .order_by(ClaimStageHistory.created_at)).scalars().all()
    names = dict(db.execute(select(User.id, User.full_name).where(User.org_id == c.org_id)).all())
    docs = db.execute(select(ClaimDocument).where(ClaimDocument.claim_id == c.id).order_by(ClaimDocument.created_at.desc())).scalars().all()
    return {**ClaimOut.model_validate(c).model_dump(mode="json"),
            "stage_label": {"en": STAGE_LABELS[c.stage][0], "ar": STAGE_LABELS[c.stage][1]},
            "next_stages": [{"stage": s, "en": STAGE_LABELS[s][0], "ar": STAGE_LABELS[s][1],
                             "allowed": p.can(GATES.get(s, "claim.write"))} for s in FLOW[c.stage]],
            "history": [{"from": h.from_stage, "to": h.to_stage, "by": names.get(h.user_id), "comment": h.comment,
                         "at": h.created_at} for h in hist],
            "documents": [{"id": d.id, "kind": d.kind, "fmt": d.fmt, "language": d.language, "filename": d.filename,
                           "version": d.version, "created_at": d.created_at, "by": names.get(d.generated_by)} for d in docs]}


@router.get("/claims/stages")
def stages():
    return [{"stage": s, "en": STAGE_LABELS[s][0], "ar": STAGE_LABELS[s][1], "next": FLOW[s]} for s in STAGES]


@router.get("/projects/{project_id}/claims")
def list_claims(project_id: str, db: DB, p: Annotated[Principal, Depends(require("claim.read"))]):
    get_project(db, project_id, p)
    rows = db.execute(select(Claim).where(Claim.project_id == project_id).order_by(Claim.ref)).scalars().all()
    return [ClaimOut.model_validate(c) for c in rows]


@router.get("/claims")
def list_all_claims(db: DB, p: Annotated[Principal, Depends(require("claim.read"))], ids: str | None = Query(None, max_length=20000)):
    pids = accessible_project_ids(db, p)
    q = select(Claim).where(Claim.project_id.in_(pids)) if pids else None
    if q is None:
        return []
    if ids:
        q = q.where(Claim.id.in_(ids.split(",")[:200]))
    return [ClaimOut.model_validate(c) for c in db.execute(q.order_by(Claim.created_at.desc())).scalars()]


@router.post("/projects/{project_id}/claims", status_code=201)
def create_claim(project_id: str, body: ClaimIn, db: DB, p: Annotated[Principal, Depends(require("claim.write"))]):
    proj = get_project(db, project_id, p)
    e = get_owned(db, Entitlement, body.entitlement_id, p)
    if e.project_id != project_id:
        raise HTTPException(422, "Entitlement belongs to another project")
    if e.status == "rejected":
        raise HTTPException(409, "Rejected entitlements cannot be turned into claims")
    if db.execute(select(Claim.id).where(Claim.entitlement_id == e.id)).first():
        raise HTTPException(409, "A claim already exists for this entitlement")
    c = Claim(org_id=p.org_id, project_id=project_id, entitlement_id=e.id, ref=next_ref(db, Claim, project_id, "CLM"),
              title=body.title or e.title, claim_type=e.entitlement_type, stage="detected",
              claimed_amount=e.financial_impact or 0, currency=e.currency, eot_claimed_days=e.time_impact_days,
              owner_id=body.owner_id or p.id, notes=body.notes, is_demo=proj.is_demo)
    db.add(c)
    db.flush()
    db.add(ClaimStageHistory(claim_id=c.id, from_stage=None, to_stage="detected", user_id=p.id, comment="Claim opened"))
    audit(db, org_id=p.org_id, user_id=p.id, action="claim.create", entity_type="claim", entity_id=c.id,
          detail={"entitlement": e.id}, ip=p.ip)
    db.commit()
    return _detail(db, c, p)


@router.get("/claims/{claim_id}")
def get_claim(claim_id: str, db: DB, p: Annotated[Principal, Depends(require("claim.read"))]):
    c = get_owned(db, Claim, claim_id, p)
    out = _detail(db, c, p)
    if c.entitlement_id:
        e = db.get(Entitlement, c.entitlement_id)
        out["entitlement"] = {"id": e.id, "ref": e.ref, "status": e.status, "type": e.entitlement_type,
                              "type_label": ENTITLEMENT_TYPES[e.entitlement_type], "financial_impact": e.financial_impact,
                              "financial_basis": e.financial_basis, "evidence_missing": e.evidence_missing,
                              "evidence_completeness": e.evidence_completeness, "review_status": e.review_status,
                              "notice": (e.notice or {}).get("notice")}
    return out


@router.post("/claims/{claim_id}/transition")
def do_transition(claim_id: str, body: TransitionIn, db: DB, p: Annotated[Principal, Depends(require("claim.read"))]):
    c = get_owned(db, Claim, claim_id, p)
    transition(db, c, body.to_stage, p, body.comment, approved_amount=body.approved_amount,
               collected_amount=body.collected_amount, eot_approved_days=body.eot_approved_days, on=body.on_date)
    db.commit()
    return _detail(db, c, p)


@router.post("/claims/{claim_id}/documents", status_code=201)
def generate(claim_id: str, body: GenerateIn, db: DB, p: Annotated[Principal, Depends(require("claim.generate"))]):
    c = get_owned(db, Claim, claim_id, p)
    if body.kind == "worksheet":
        body.fmt = "xlsx"
    elif body.fmt == "xlsx":
        raise HTTPException(422, "Excel output is available for the valuation worksheet only")
    data, mime, ext = claimdocs.render(db, c, body.kind, body.fmt, body.language)
    version = (db.scalar(select(func.count()).select_from(ClaimDocument).where(
        ClaimDocument.claim_id == c.id, ClaimDocument.kind == body.kind, ClaimDocument.fmt == ext,
        ClaimDocument.language == body.language)) or 0) + 1
    filename = f"{c.ref}_{body.kind}_{body.language}_v{version}.{ext}"
    key = f"{c.org_id}/{c.project_id}/claims/{c.id}/{filename}"
    digest = get_store().put(key, data)
    cd = ClaimDocument(org_id=c.org_id, claim_id=c.id, kind=body.kind, fmt=ext, language=body.language, filename=filename,
                       storage_key=key, sha256=digest, version=version, generated_by=p.id)
    db.add(cd)
    db.add(UsageRecord(org_id=c.org_id, metric="claim_documents", quantity=1, reference=c.id))
    audit(db, org_id=p.org_id, user_id=p.id, action="claim.generate_document", entity_type="claim", entity_id=c.id,
          detail={"kind": body.kind, "fmt": ext, "lang": body.language, "sha256": digest}, ip=p.ip)
    db.commit()
    return {"id": cd.id, "filename": filename, "sha256": digest, "size": len(data)}


@router.get("/claim-documents/{doc_id}/download")
def download(doc_id: str, db: DB, p: Annotated[Principal, Depends(require("claim.read"))]):
    cd = db.get(ClaimDocument, doc_id)
    if not cd or cd.org_id != p.org_id:
        raise HTTPException(404, "Document not found")
    get_owned(db, Claim, cd.claim_id, p)
    data = get_store().get(cd.storage_key, cd.sha256)
    mime = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}[cd.fmt]
    audit(db, org_id=p.org_id, user_id=p.id, action="claim.download_document", entity_type="claim", entity_id=cd.claim_id,
          detail={"file": cd.filename}, ip=p.ip)
    db.commit()
    return Response(data, media_type=mime, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(cd.filename)}",
                                                    "Cache-Control": "private, no-store"})
