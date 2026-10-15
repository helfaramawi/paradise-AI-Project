from __future__ import annotations

import time
from collections import defaultdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Tenant, User
from ..security import CurrentUser, create_access_token, user_permissions, verify_password
from ..services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])
_attempts: dict[str, list[float]] = defaultdict(list)
MAX_ATTEMPTS, WINDOW_S = 8, 300


class LoginIn(BaseModel):
    email: str
    password: str
    tenant: str = "nile-engineering"


def user_out(u: User) -> dict[str, Any]:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "title": u.title, "tenant_id": u.tenant_id,
            "preferred_language": u.preferred_language, "roles": [{"key": r.key, "name_en": r.name_en,
                                                                   "name_ar": r.name_ar} for r in u.roles],
            "permissions": sorted(user_permissions(u))}


@router.post("/login")
def login(body: LoginIn, request: Request, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    key = f"{request.client.host if request.client else 'x'}:{body.email.lower()}"
    now = time.time()
    _attempts[key] = [t for t in _attempts[key] if now - t < WINDOW_S]
    if len(_attempts[key]) >= MAX_ATTEMPTS:
        raise HTTPException(429, "Too many login attempts; try again later")
    tenant = db.scalar(select(Tenant).where(Tenant.slug == body.tenant, Tenant.is_active.is_(True)))
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.tenant_id == tenant.id)) if tenant else None
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        _attempts[key].append(now)
        raise HTTPException(401, "Invalid credentials")
    _attempts.pop(key, None)
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="auth.login",
          entity_type="user", entity_id=user.id)
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": user_out(user)}


@router.get("/me")
def me(user: CurrentUser) -> dict[str, Any]:
    return user_out(user)


class PrefIn(BaseModel):
    preferred_language: str


@router.patch("/me")
def update_me(body: PrefIn, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    if body.preferred_language not in ("en", "ar"):
        raise HTTPException(422, "Language must be en or ar")
    u = db.get(User, user.id)
    u.preferred_language = body.preferred_language
    db.commit()
    return user_out(u)
