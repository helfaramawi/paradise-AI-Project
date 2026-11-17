"""FastAPI dependencies: authentication, permission checks and tenant/project scoping."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, TypeVar

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Base, get_db
from ..models import Project, ProjectMember, User, UserSession
from .rbac import role_permissions, role_sees_all_projects
from .security import decode_token

bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]
T = TypeVar("T", bound=Base)


@dataclass
class Principal:
    user: User
    session_id: str
    ip: str | None
    permissions: set[str] = field(default_factory=set)

    @property
    def org_id(self) -> str:
        return self.user.org_id

    @property
    def id(self) -> str:
        return self.user.id

    def can(self, perm: str) -> bool:
        return perm in self.permissions


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)


def get_principal(request: Request, db: DB,
                  creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Principal:
    token = creds.credentials if creds else request.query_params.get("access_token")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        claims = decode_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    sess = db.get(UserSession, claims.get("sid"))
    if not sess or sess.revoked_at or sess.expires_at < datetime.now(UTC) or sess.user_id != claims.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or revoked")
    user = db.get(User, claims["sub"])
    if not user or not user.is_active or user.org_id != claims.get("org"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    if not user.organization.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organisation suspended")
    return Principal(user=user, session_id=sess.id, ip=client_ip(request), permissions=role_permissions(user.role))


CurrentUser = Annotated[Principal, Depends(get_principal)]


def require(*perms: str):
    def checker(p: CurrentUser) -> Principal:
        missing = [x for x in perms if not p.can(x)]
        if missing:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {', '.join(missing)}")
        return p
    return checker


def require_platform_admin(p: CurrentUser) -> Principal:
    if not p.user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform administrator only")
    return p


# ---- tenancy


def get_owned(db: Session, model: type[T], obj_id: str, p: Principal) -> T:
    """Fetch a tenant-owned row; rows from other organisations are reported as not found."""
    obj = db.get(model, obj_id)
    if obj is None or getattr(obj, "org_id", None) != p.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    project_id = getattr(obj, "project_id", None)
    if project_id and not can_access_project(db, p, project_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return obj


def accessible_project_ids(db: Session, p: Principal) -> list[str]:
    q = select(Project.id).where(Project.org_id == p.org_id)
    if not role_sees_all_projects(p.user.role):
        q = q.join(ProjectMember, ProjectMember.project_id == Project.id).where(ProjectMember.user_id == p.id)
    return list(db.execute(q).scalars())


def can_access_project(db: Session, p: Principal, project_id: str) -> bool:
    if role_sees_all_projects(p.user.role):
        proj = db.get(Project, project_id)
        return bool(proj and proj.org_id == p.org_id)
    return db.get(ProjectMember, (project_id, p.id)) is not None and db.get(Project, project_id).org_id == p.org_id


def get_project(db: Session, project_id: str, p: Principal) -> Project:
    proj = db.get(Project, project_id)
    if proj is None or proj.org_id != p.org_id or not can_access_project(db, p, project_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return proj
