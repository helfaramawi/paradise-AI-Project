"""Authentication (JWT), password hashing (PBKDF2-SHA256) and RBAC dependencies."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User

PBKDF2_ITERATIONS = 240_000
ALGORITHM = "HS256"

# Permission catalogue. Roles are granted subsets of these in seed data.
PERMISSIONS = {
    "decision.read": "View decisions and dossiers",
    "decision.create": "Create decisions",
    "decision.run": "Run multi-agent analysis",
    "decision.cancel": "Cancel / emergency-stop a running analysis",
    "simulation.run": "Run what-if simulations",
    "dataset.read": "View enterprise datasets",
    "dataset.write": "Create dataset versions / import data",
    "approval.request": "Submit a strategy for approval",
    "approval.decide": "Record an approval verdict (role-gated by policy)",
    "governance.read": "View governance policies",
    "governance.manage": "Change governance policies",
    "automation.read": "View automation workflows",
    "automation.run": "Trigger automation workflows (dry-run unless authorised)",
    "connector.manage": "Configure enterprise data connections",
    "outcome.record": "Record actual outcomes",
    "report.export": "Export reports",
    "admin.users": "Administer users and roles",
    "admin.audit": "View audit trail",
    "admin.emergency_stop": "Trigger platform-wide emergency stop",
}

ROLE_DEFINITIONS: dict[str, tuple[str, str, list[str]]] = {
    "admin": ("Platform Administrator", "مدير المنصة", list(PERMISSIONS)),
    "ceo": ("Chief Executive Officer", "الرئيس التنفيذي", [
        "decision.read", "decision.create", "decision.run", "decision.cancel", "simulation.run",
        "dataset.read", "approval.request", "approval.decide", "governance.read", "automation.read",
        "report.export", "outcome.record", "admin.audit", "admin.emergency_stop"]),
    "cfo": ("Chief Financial Officer", "المدير المالي", [
        "decision.read", "decision.create", "decision.run", "simulation.run", "dataset.read",
        "dataset.write", "approval.request", "approval.decide", "governance.read", "automation.read",
        "automation.run", "report.export", "outcome.record"]),
    "coo": ("Chief Operating Officer", "مدير العمليات", [
        "decision.read", "decision.create", "decision.run", "simulation.run", "dataset.read",
        "approval.request", "approval.decide", "governance.read", "automation.read", "report.export",
        "outcome.record"]),
    "legal": ("General Counsel", "المستشار القانوني", [
        "decision.read", "dataset.read", "approval.decide", "governance.read", "report.export"]),
    "hr": ("HR Director", "مدير الموارد البشرية", [
        "decision.read", "dataset.read", "approval.decide", "governance.read", "report.export"]),
    "analyst": ("Decision Analyst", "محلل القرارات", [
        "decision.read", "decision.create", "decision.run", "simulation.run", "dataset.read",
        "dataset.write", "approval.request", "automation.read", "report.export", "outcome.record"]),
    "viewer": ("Viewer", "مشاهد", ["decision.read", "dataset.read", "governance.read", "automation.read"]),
}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, iters, salt_b64, dk_b64 = encoded.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except Exception:  # noqa: BLE001
        return False


def create_access_token(user: User) -> str:
    s = get_settings()
    payload = {
        "sub": user.id,
        "tid": user.tenant_id,
        "roles": [r.key for r in user.roles],
        "exp": datetime.now(UTC) + timedelta(minutes=s.access_token_minutes),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, s.secret_key, algorithm=ALGORITHM)


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    token = creds.credentials if creds else request.query_params.get("access_token")  # SSE (EventSource) fallback
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    user = db.scalar(select(User).where(User.id == payload["sub"], User.tenant_id == payload["tid"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def user_permissions(user: User) -> set[str]:
    return {p.key for r in user.roles for p in r.permissions}


def user_role_keys(user: User) -> set[str]:
    return {r.key for r in user.roles}


def require(permission: str):
    def dep(user: CurrentUser) -> User:
        if permission not in user_permissions(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {permission}")
        return user
    return Depends(dep)
