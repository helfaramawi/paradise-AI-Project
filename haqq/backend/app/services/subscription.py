"""Plans, plan limits and usage metering."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Plan, Project, Subscription, UsageRecord, User

PLANS = [
    {"code": "project", "name": "Project", "name_ar": "المشروع", "price_monthly": Decimal("10000"),
     "price_annual": Decimal("108000"), "max_users": 5, "max_projects": 1, "max_documents_month": 300,
     "max_pages_month": 6000, "max_ai_tokens_month": 2_000_000,
     "features": ["contract_intelligence", "entitlement_discovery", "claims", "deadlines"]},
    {"code": "business", "name": "Business", "name_ar": "الأعمال", "price_monthly": Decimal("20000"),
     "price_annual": Decimal("216000"), "max_users": 20, "max_projects": 5, "max_documents_month": 1500,
     "max_pages_month": 30000, "max_ai_tokens_month": 8_000_000,
     "features": ["contract_intelligence", "entitlement_discovery", "claims", "deadlines", "executive_dashboard"]},
    {"code": "enterprise", "name": "Enterprise", "name_ar": "المؤسسات", "price_monthly": Decimal("40000"),
     "price_annual": Decimal("432000"), "max_users": 100, "max_projects": 50, "max_documents_month": 10000,
     "max_pages_month": 200000, "max_ai_tokens_month": 40_000_000,
     "features": ["contract_intelligence", "entitlement_discovery", "claims", "deadlines", "executive_dashboard",
                  "sso_ready", "dedicated_support"]},
]


def seed_plans(db: Session) -> None:
    for p in PLANS:
        existing = db.get(Plan, p["code"])
        if existing:
            for k, v in p.items():
                setattr(existing, k, v)
        else:
            db.add(Plan(**p))
    db.flush()


def start_trial(db: Session, org_id: str, plan_code: str = "business", days: int = 30) -> Subscription:
    today = date.today()
    sub = Subscription(org_id=org_id, plan_code=plan_code, status="trial", billing_cycle="monthly",
                       started_at=today, renews_at=today + timedelta(days=days), trial_ends_at=today + timedelta(days=days))
    db.add(sub)
    db.flush()
    return sub


def month_start() -> datetime:
    n = datetime.now(UTC)
    return datetime(n.year, n.month, 1, tzinfo=UTC)


def usage_this_month(db: Session, org_id: str) -> dict[str, int]:
    rows = db.execute(select(UsageRecord.metric, func.sum(UsageRecord.quantity))
                      .where(UsageRecord.org_id == org_id, UsageRecord.created_at >= month_start())
                      .group_by(UsageRecord.metric)).all()
    return {m: int(q or 0) for m, q in rows}


def get_subscription(db: Session, org_id: str) -> Subscription | None:
    return db.execute(select(Subscription).where(Subscription.org_id == org_id)).scalar_one_or_none()


def _limit_error(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_402_PAYMENT_REQUIRED, msg)


def check_limit(db: Session, org_id: str, what: str) -> None:
    sub = get_subscription(db, org_id)
    if sub is None:
        return
    if sub.status == "cancelled":
        raise _limit_error("Subscription is cancelled.")
    plan = sub.plan
    if what == "users":
        n = db.scalar(select(func.count()).select_from(User).where(User.org_id == org_id, User.is_active.is_(True)))
        if n >= plan.max_users:
            raise _limit_error(f"User limit reached for plan '{plan.name}' ({plan.max_users}).")
    elif what == "projects":
        n = db.scalar(select(func.count()).select_from(Project).where(Project.org_id == org_id))
        if n >= plan.max_projects:
            raise _limit_error(f"Project limit reached for plan '{plan.name}' ({plan.max_projects}).")
    elif what == "documents":
        if usage_this_month(db, org_id).get("documents", 0) >= plan.max_documents_month:
            raise _limit_error(f"Monthly document limit reached for plan '{plan.name}'.")
    elif what == "ai_tokens":
        if usage_this_month(db, org_id).get("ai_tokens", 0) >= plan.max_ai_tokens_month:
            raise _limit_error("Monthly AI processing allowance reached.")


class BillingProvider:
    """Interface for a payment gateway integration (e.g. Paymob, Fawry). Only 'manual' invoicing is implemented."""

    name = "manual"

    def create_invoice(self, org_id: str, amount: Decimal, currency: str) -> str:
        return f"MANUAL-{org_id[:8]}-{datetime.now(UTC):%Y%m%d%H%M%S}"
