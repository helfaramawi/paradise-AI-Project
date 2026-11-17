"""Claim lifecycle state machine with role-gated transitions. Claims are never sent to the employer by
the system: 'submitted' records that the company submitted it through its own channels."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.audit import audit
from ..core.deps import Principal
from ..models import Claim, ClaimDocument, ClaimStageHistory, Entitlement, Valuation

STAGES = ["detected", "initial_review", "evidence_collection", "contractual_verification", "financial_valuation",
          "technical_review", "legal_review", "management_approval", "submitted", "employer_response", "negotiation",
          "approved", "rejected", "collected", "closed"]
STAGE_LABELS = {
    "detected": ("Potential claim detected", "تم رصد مطالبة محتملة"),
    "initial_review": ("Initial review", "مراجعة مبدئية"),
    "evidence_collection": ("Evidence collection", "تجميع الأدلة"),
    "contractual_verification": ("Contractual verification", "التحقق التعاقدي"),
    "financial_valuation": ("Financial valuation", "التقييم المالي"),
    "technical_review": ("Technical review", "مراجعة فنية"),
    "legal_review": ("Legal / commercial review", "مراجعة قانونية / تجارية"),
    "management_approval": ("Management approval", "اعتماد الإدارة"),
    "submitted": ("Submitted to employer", "تم التقديم لصاحب العمل"),
    "employer_response": ("Employer response", "رد صاحب العمل"),
    "negotiation": ("Negotiation", "التفاوض"),
    "approved": ("Approved", "معتمدة"),
    "rejected": ("Rejected", "مرفوضة"),
    "collected": ("Collected", "تم التحصيل"),
    "closed": ("Closed", "مغلقة"),
}
# allowed forward transitions
FLOW = {
    "detected": ["initial_review", "closed"],
    "initial_review": ["evidence_collection", "closed"],
    "evidence_collection": ["contractual_verification"],
    "contractual_verification": ["financial_valuation", "evidence_collection"],
    "financial_valuation": ["technical_review"],
    "technical_review": ["legal_review", "financial_valuation"],
    "legal_review": ["management_approval", "evidence_collection"],
    "management_approval": ["submitted", "legal_review"],
    "submitted": ["employer_response"],
    "employer_response": ["negotiation", "approved", "rejected"],
    "negotiation": ["approved", "rejected"],
    "approved": ["collected"],
    "rejected": ["negotiation", "closed"],
    "collected": ["closed"],
    "closed": [],
}
# permission needed to ENTER a stage
GATES = {"management_approval": "claim.legal_review", "submitted": "claim.approve", "approved": "claim.write",
         "collected": "claim.write"}
PIPELINE_GROUPS = {
    "preparation": STAGES[:8], "submitted": ["submitted", "employer_response", "negotiation"],
    "approved": ["approved", "collected"], "rejected": ["rejected"], "closed": ["closed"],
}


def transition(db: Session, claim: Claim, to: str, p: Principal, comment: str | None = None, *,
               approved_amount: Decimal | None = None, collected_amount: Decimal | None = None,
               eot_approved_days: int | None = None, on: date | None = None) -> Claim:
    if to not in FLOW.get(claim.stage, []):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot move a claim from '{claim.stage}' to '{to}'")
    perm = GATES.get(to, "claim.write")
    if not p.can(perm):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Moving to '{to}' requires permission '{perm}'")
    on = on or date.today()
    if to == "technical_review" and claim.entitlement_id:
        ent = db.get(Entitlement, claim.entitlement_id)
        if ent and ent.entitlement_type != "extension_of_time":
            v = db.execute(select(Valuation).where(Valuation.entitlement_id == ent.id)).scalar_one_or_none()
            if v is None or not v.lines:
                raise HTTPException(status.HTTP_409_CONFLICT, "A valuation worksheet is required before technical review")
            claim.claimed_amount = Decimal(v.totals.get("gross_egp", "0"))
    if to == "submitted":
        has_doc = db.execute(select(ClaimDocument.id).where(ClaimDocument.claim_id == claim.id)).first()
        if not has_doc:
            raise HTTPException(status.HTTP_409_CONFLICT, "Generate and review the claim document before recording submission")
        claim.submitted_at = on
    if to == "employer_response":
        claim.responded_at = on
    if to == "approved":
        if approved_amount is None:
            raise HTTPException(422, "approved_amount is required")
        if approved_amount < 0 or approved_amount > claim.claimed_amount:
            raise HTTPException(422, "approved_amount must be between 0 and the claimed amount")
        claim.approved_amount = approved_amount
        if eot_approved_days is not None:
            claim.eot_approved_days = eot_approved_days
    if to == "collected":
        if collected_amount is None or collected_amount <= 0 or collected_amount > claim.approved_amount:
            raise HTTPException(422, "collected_amount must be >0 and ≤ approved amount")
        claim.collected_amount = collected_amount
    if to == "closed":
        claim.closed_at = on
    db.add(ClaimStageHistory(claim_id=claim.id, from_stage=claim.stage, to_stage=to, user_id=p.id, comment=comment))
    audit(db, org_id=claim.org_id, user_id=p.id, action="claim.transition", entity_type="claim", entity_id=claim.id,
          detail={"from": claim.stage, "to": to, "comment": comment}, ip=p.ip)
    claim.stage = to
    return claim
