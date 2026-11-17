"""Authentication, sessions, self-service organisation onboarding and MFA (TOTP)."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..config import get_settings
from ..core.audit import audit
from ..core.deps import DB, CurrentUser, client_ip
from ..core.ratelimit import limiter
from ..core.rbac import ROLES, role_permissions
from ..core.security import (
    create_access_token,
    hash_password,
    new_totp_secret,
    validate_password_strength,
    verify_password,
    verify_totp,
)
from ..models import Organization, User, UserSession
from ..schemas import LoginIn, OrgOut, RegisterIn, UserOut
from ..services.subscription import start_trial

router = APIRouter(prefix="/auth", tags=["auth"])
LOCK_AFTER = 5
LOCK_MINUTES = 15


def _session_payload(db, user: User, request: Request) -> dict:
    s = get_settings()
    sess = UserSession(user_id=user.id, expires_at=datetime.now(UTC) + timedelta(minutes=s.access_token_minutes),
                       ip=client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:300])
    db.add(sess)
    db.flush()
    token, exp = create_access_token(user.id, user.org_id, sess.id)
    return {"access_token": token, "token_type": "bearer", "expires_at": exp.isoformat(), "user": me_payload(user)}


def me_payload(user: User) -> dict:
    return {**UserOut.model_validate(user).model_dump(mode="json"),
            "permissions": sorted(role_permissions(user.role)),
            "role_label": {"en": ROLES[user.role]["en"], "ar": ROLES[user.role]["ar"]},
            "organization": OrgOut.model_validate(user.organization).model_dump(mode="json")}


@router.post("/login")
def login(body: LoginIn, request: Request, db: DB):
    ip = client_ip(request) or "?"
    if not limiter.allow(f"login:{ip}", get_settings().rate_limit_login_per_minute):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts; try again in a minute")
    user = db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none()
    now = datetime.now(UTC)
    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(status.HTTP_423_LOCKED, "Account temporarily locked after failed attempts")
    if not user or not verify_password(body.password, user.password_hash) or not user.is_active:
        if user:
            user.failed_logins += 1
            if user.failed_logins >= LOCK_AFTER:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                user.failed_logins = 0
            audit(db, org_id=user.org_id, user_id=user.id, action="auth.login_failed", ip=ip)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if user.mfa_enabled:
        if not body.mfa_code:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="mfa_required")
        if not verify_totp(user.mfa_secret or "", body.mfa_code):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid MFA code")
    user.failed_logins, user.locked_until, user.last_login_at = 0, None, now
    payload = _session_payload(db, user, request)
    audit(db, org_id=user.org_id, user_id=user.id, action="auth.login", ip=ip)
    db.commit()
    return payload


@router.post("/logout")
def logout(p: CurrentUser, db: DB):
    sess = db.get(UserSession, p.session_id)
    sess.revoked_at = datetime.now(UTC)
    audit(db, org_id=p.org_id, user_id=p.id, action="auth.logout", ip=p.ip)
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(p: CurrentUser):
    return me_payload(p.user)


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, db: DB):
    """Self-service onboarding: creates an organisation, its administrator and a 30-day trial."""
    ip = client_ip(request) or "?"
    if not limiter.allow(f"register:{ip}", 5):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many registrations from this address")
    problems = validate_password_strength(body.password)
    if problems:
        raise HTTPException(422, "Password needs " + ", ".join(problems))
    if db.execute(select(User.id).where(User.email == body.email.lower())).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this e-mail already exists")
    slug = re.sub(r"[^a-z0-9]+", "-", body.company_name.lower()).strip("-")[:60] or "org"
    slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    org = Organization(name=body.company_name, name_ar=body.company_name_ar, slug=slug, default_language=body.language)
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(body.password),
                role="admin", language=body.language, title="Administrator")
    db.add(user)
    db.flush()
    start_trial(db, org.id, body.plan_code)
    audit(db, org_id=org.id, user_id=user.id, action="org.register", entity_type="organization", entity_id=org.id, ip=ip)
    db.refresh(user)
    payload = _session_payload(db, user, request)
    db.commit()
    return payload


class MfaVerifyIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


@router.post("/mfa/setup")
def mfa_setup(p: CurrentUser, db: DB):
    secret = new_totp_secret()
    p.user.mfa_secret = secret
    p.user.mfa_enabled = False
    db.commit()
    uri = f"otpauth://totp/HAQQ:{p.user.email}?secret={secret}&issuer=HAQQ"
    return {"secret": secret, "otpauth_uri": uri}


@router.post("/mfa/enable")
def mfa_enable(body: MfaVerifyIn, p: CurrentUser, db: DB):
    if not p.user.mfa_secret or not verify_totp(p.user.mfa_secret, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code")
    p.user.mfa_enabled = True
    audit(db, org_id=p.org_id, user_id=p.id, action="auth.mfa_enabled", ip=p.ip)
    db.commit()
    return {"mfa_enabled": True}


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


@router.post("/password")
def change_password(body: PasswordChangeIn, p: CurrentUser, db: DB):
    if not verify_password(body.current_password, p.user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    problems = validate_password_strength(body.new_password)
    if problems:
        raise HTTPException(422, "Password needs " + ", ".join(problems))
    p.user.password_hash = hash_password(body.new_password)
    for s in db.execute(select(UserSession).where(UserSession.user_id == p.id, UserSession.id != p.session_id,
                                                  UserSession.revoked_at.is_(None))).scalars():
        s.revoked_at = datetime.now(UTC)
    audit(db, org_id=p.org_id, user_id=p.id, action="auth.password_changed", ip=p.ip)
    db.commit()
    return {"ok": True}
