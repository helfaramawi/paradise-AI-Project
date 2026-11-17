"""Organisation settings, users & roles, audit trail, subscription/usage and platform commercial report."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from ..core.audit import audit, verify_chain
from ..core.deps import DB, Principal, require, require_platform_admin
from ..core.rbac import PERMISSIONS, ROLES
from ..core.security import hash_password, validate_password_strength
from ..models import (
    AiRun,
    AuditLog,
    BillingRecord,
    DocumentAccessLog,
    Organization,
    Plan,
    Project,
    Subscription,
    User,
)
from ..schemas import OrgOut, OrgUpdate, UserCreate, UserOut, UserUpdate
from ..services.subscription import check_limit, get_subscription, usage_this_month

router = APIRouter(tags=["organization"])


@router.get("/org")
def get_org(p: Annotated[Principal, Depends(require("project.read"))]):
    return OrgOut.model_validate(p.user.organization)


@router.patch("/org")
def update_org(body: OrgUpdate, db: DB, p: Annotated[Principal, Depends(require("admin.org"))]):
    org = db.get(Organization, p.org_id)
    data = body.model_dump(exclude_unset=True)
    if "holidays" in data:
        data["holidays"] = [d.isoformat() for d in data["holidays"]]
    for k, v in data.items():
        setattr(org, k, v)
    audit(db, org_id=org.id, user_id=p.id, action="org.update", entity_type="organization", entity_id=org.id,
          detail={k: str(v) for k, v in data.items()}, ip=p.ip)
    db.commit()
    return OrgOut.model_validate(org)


@router.get("/roles")
def roles(p: Annotated[Principal, Depends(require("project.read"))]):
    return {"roles": [{"code": k, "en": v["en"], "ar": v["ar"], "permissions": v["perms"], "all_projects": v["all_projects"]}
                      for k, v in ROLES.items()], "permissions": PERMISSIONS}


@router.get("/users")
def list_users(db: DB, p: Annotated[Principal, Depends(require("project.read"))]):
    users = db.execute(select(User).where(User.org_id == p.org_id).order_by(User.full_name)).scalars().all()
    return [UserOut.model_validate(u) for u in users]


@router.post("/users", status_code=201)
def create_user(body: UserCreate, db: DB, p: Annotated[Principal, Depends(require("admin.users"))]):
    check_limit(db, p.org_id, "users")
    problems = validate_password_strength(body.password)
    if problems:
        raise HTTPException(422, "Password needs " + ", ".join(problems))
    if db.execute(select(User.id).where(User.email == body.email.lower())).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail already in use")
    u = User(org_id=p.org_id, email=body.email.lower(), full_name=body.full_name, role=body.role, title=body.title,
             language=body.language, password_hash=hash_password(body.password))
    db.add(u)
    db.flush()
    audit(db, org_id=p.org_id, user_id=p.id, action="user.create", entity_type="user", entity_id=u.id,
          detail={"role": u.role}, ip=p.ip)
    db.commit()
    return UserOut.model_validate(u)


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserUpdate, db: DB, p: Annotated[Principal, Depends(require("admin.users"))]):
    u = db.get(User, user_id)
    if not u or u.org_id != p.org_id:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if u.id == p.id and (data.get("is_active") is False or (data.get("role") and data["role"] != "admin")):
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot deactivate or demote yourself")
    for k, v in data.items():
        setattr(u, k, v)
    audit(db, org_id=p.org_id, user_id=p.id, action="user.update", entity_type="user", entity_id=u.id,
          detail={k: str(v) for k, v in data.items()}, ip=p.ip)
    db.commit()
    return UserOut.model_validate(u)


@router.get("/audit")
def audit_log(db: DB, p: Annotated[Principal, Depends(require("audit.read"))], limit: int = Query(100, le=500),
              action: str | None = None):
    q = select(AuditLog).where(AuditLog.org_id == p.org_id)
    if action:
        q = q.where(AuditLog.action.startswith(action))
    rows = db.execute(q.order_by(AuditLog.seq.desc()).limit(limit)).scalars().all()
    names = dict(db.execute(select(User.id, User.full_name).where(User.org_id == p.org_id)).all())
    return [{"seq": r.seq, "at": r.created_at, "user": names.get(r.user_id), "action": r.action,
             "entity_type": r.entity_type, "entity_id": r.entity_id, "detail": r.detail, "ip": r.ip, "hash": r.hash[:12]}
            for r in rows]


@router.get("/audit/verify")
def audit_verify(db: DB, p: Annotated[Principal, Depends(require("audit.read"))]):
    return verify_chain(db)


@router.get("/audit/document-access")
def doc_access(db: DB, p: Annotated[Principal, Depends(require("audit.read"))], limit: int = Query(100, le=500)):
    rows = db.execute(select(DocumentAccessLog).where(DocumentAccessLog.org_id == p.org_id)
                      .order_by(DocumentAccessLog.created_at.desc()).limit(limit)).scalars().all()
    return [{"at": r.created_at, "user_id": r.user_id, "document_id": r.document_id, "action": r.action, "ip": r.ip}
            for r in rows]


@router.get("/subscription")
def subscription(db: DB, p: Annotated[Principal, Depends(require("project.read"))]):
    sub = get_subscription(db, p.org_id)
    usage = usage_this_month(db, p.org_id)
    users = db.scalar(select(func.count()).select_from(User).where(User.org_id == p.org_id, User.is_active.is_(True)))
    projects = db.scalar(select(func.count()).select_from(Project).where(Project.org_id == p.org_id))
    ai = db.execute(select(func.count(), func.sum(AiRun.input_tokens + AiRun.output_tokens))
                    .where(AiRun.org_id == p.org_id)).one()
    plan = sub.plan if sub else None
    bills = db.execute(select(BillingRecord).where(BillingRecord.org_id == p.org_id)
                       .order_by(BillingRecord.period_start.desc()).limit(12)).scalars().all()
    return {
        "subscription": None if not sub else {"plan_code": sub.plan_code, "status": sub.status, "billing_cycle": sub.billing_cycle,
                                              "started_at": sub.started_at, "renews_at": sub.renews_at, "trial_ends_at": sub.trial_ends_at},
        "plan": None if not plan else {"code": plan.code, "name": plan.name, "name_ar": plan.name_ar,
                                       "price_monthly": plan.price_monthly, "price_annual": plan.price_annual,
                                       "currency": plan.currency, "features": plan.features},
        "limits": None if not plan else {"users": plan.max_users, "projects": plan.max_projects,
                                         "documents_month": plan.max_documents_month, "pages_month": plan.max_pages_month,
                                         "ai_tokens_month": plan.max_ai_tokens_month},
        "usage": {"users": users, "projects": projects, "documents_month": usage.get("documents", 0),
                  "pages_month": usage.get("pages", 0), "ocr_pages_month": usage.get("ocr_pages", 0),
                  "ai_tokens_month": usage.get("ai_tokens", 0), "claim_documents_month": usage.get("claim_documents", 0),
                  "ai_runs_total": ai[0], "ai_tokens_total": int(ai[1] or 0)},
        "billing": [{"period_start": b.period_start, "period_end": b.period_end, "amount": b.amount, "vat": b.vat_amount,
                     "status": b.status, "reference": b.reference} for b in bills],
        "payment_gateway": "not_integrated — manual invoicing (BillingProvider interface ready)",
    }


@router.get("/plans")
def plans(db: DB):
    return [{"code": x.code, "name": x.name, "name_ar": x.name_ar, "price_monthly": x.price_monthly,
             "price_annual": x.price_annual, "max_users": x.max_users, "max_projects": x.max_projects,
             "max_documents_month": x.max_documents_month, "features": x.features}
            for x in db.execute(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price_monthly)).scalars()]


@router.get("/platform/commercial")
def commercial_report(db: DB, p: Annotated[Principal, Depends(require_platform_admin)]):
    """PAIS internal: MRR and progress to the EGP 1M MRR target. Demo organisations are excluded."""
    rows = db.execute(select(Subscription, Plan, Organization).join(Plan, Plan.code == Subscription.plan_code)
                      .join(Organization, Organization.id == Subscription.org_id)).all()
    paying = [(s, pl, o) for s, pl, o in rows if s.status == "active" and not o.is_demo]
    mrr = sum((pl.price_monthly if s.billing_cycle == "monthly" else pl.price_annual / 12) for s, pl, _ in paying) or Decimal(0)
    by_plan: dict[str, int] = {}
    for _s, pl, _o in paying:
        by_plan[pl.code] = by_plan.get(pl.code, 0) + 1
    target = Decimal(1_000_000)
    return {"as_of": date.today(), "paying_customers": len(paying), "trials": len([1 for s, _, o in rows if s.status == "trial" and not o.is_demo]),
            "mrr": mrr, "arpa": (mrr / len(paying)) if paying else None, "by_plan": by_plan,
            "target_mrr": target, "target_customers": 50, "progress_pct": float(mrr / target * 100),
            "note": "Target is a business goal, not a forecast. Demo organisations are excluded."}
