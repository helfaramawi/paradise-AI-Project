"""Base seed: subscription plans and (optionally) the PAIS platform-operator account."""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.security import hash_password
from .models import Organization, User
from .services.subscription import seed_plans


def seed_base(db: Session) -> None:
    seed_plans(db)
    email = os.environ.get("HAQQ_PLATFORM_ADMIN_EMAIL")
    pwd = os.environ.get("HAQQ_PLATFORM_ADMIN_PASSWORD")
    if email and pwd and not db.execute(select(User.id).where(User.email == email.lower())).first():
        org = db.execute(select(Organization).where(Organization.slug == "pais")).scalar_one_or_none()
        if org is None:
            org = Organization(name="Paradise AI Solutions", name_ar="بارادايس للحلول الذكية", slug="pais",
                               default_language="en", onboarding_completed=True)
            db.add(org)
            db.flush()
        db.add(User(org_id=org.id, email=email.lower(), full_name="PAIS Platform Admin", role="admin",
                    password_hash=hash_password(pwd), is_platform_admin=True, language="en"))
