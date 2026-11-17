"""Projects, portfolio and team assignments."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from ..core.audit import audit
from ..core.deps import DB, Principal, accessible_project_ids, get_project, require
from ..models import (
    Claim,
    Clause,
    Deadline,
    Document,
    Entitlement,
    Project,
    ProjectEvent,
    ProjectMember,
    User,
)
from ..schemas import MemberIn, ProjectIn, ProjectOut, ProjectUpdate
from ..services.subscription import check_limit

router = APIRouter(prefix="/projects", tags=["projects"])


def _counts(db, pid: str) -> dict:
    def c(model, *cond):
        return db.scalar(select(func.count()).select_from(model).where(model.project_id == pid, *cond)) or 0
    return {"documents": c(Document, Document.is_latest.is_(True)), "clauses": c(Clause), "events": c(ProjectEvent),
            "entitlements": c(Entitlement), "claims": c(Claim),
            "open_deadlines": c(Deadline, Deadline.status == "open"),
            "potential_value": str(db.scalar(select(func.coalesce(func.sum(Entitlement.financial_impact), 0))
                                             .where(Entitlement.project_id == pid,
                                                    Entitlement.status.in_(("potential", "insufficient_evidence",
                                                                            "requires_expert_verification", "substantiated"))))),
            "processing": c(Document, Document.status.in_(("uploaded", "processing")))}


@router.get("")
def list_projects(db: DB, p: Annotated[Principal, Depends(require("project.read"))]):
    ids = accessible_project_ids(db, p)
    rows = db.execute(select(Project).where(Project.id.in_(ids)).order_by(Project.created_at)).scalars().all() if ids else []
    return [{**ProjectOut.model_validate(r).model_dump(mode="json"), "stats": _counts(db, r.id)} for r in rows]


@router.post("", status_code=201)
def create_project(body: ProjectIn, db: DB, p: Annotated[Principal, Depends(require("project.manage"))]):
    check_limit(db, p.org_id, "projects")
    if db.execute(select(Project.id).where(Project.org_id == p.org_id, Project.code == body.code)).first():
        raise HTTPException(409, "Project code already exists")
    proj = Project(org_id=p.org_id, **body.model_dump())
    db.add(proj)
    db.flush()
    if body.manager_id:
        mgr = db.get(User, body.manager_id)
        if not mgr or mgr.org_id != p.org_id:
            raise HTTPException(422, "Manager not found")
        db.add(ProjectMember(project_id=proj.id, user_id=mgr.id, project_role="project_manager"))
    audit(db, org_id=p.org_id, user_id=p.id, action="project.create", entity_type="project", entity_id=proj.id, ip=p.ip)
    db.commit()
    return ProjectOut.model_validate(proj)


@router.get("/{project_id}")
def get_project_detail(project_id: str, db: DB, p: Annotated[Principal, Depends(require("project.read"))]):
    proj = get_project(db, project_id, p)
    members = db.execute(select(User, ProjectMember.project_role).join(ProjectMember, ProjectMember.user_id == User.id)
                         .where(ProjectMember.project_id == project_id)).all()
    return {**ProjectOut.model_validate(proj).model_dump(mode="json"), "stats": _counts(db, project_id),
            "members": [{"user_id": u.id, "full_name": u.full_name, "role": u.role, "project_role": r} for u, r in members]}


@router.patch("/{project_id}")
def update_project(project_id: str, body: ProjectUpdate, db: DB, p: Annotated[Principal, Depends(require("project.manage"))]):
    proj = get_project(db, project_id, p)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(proj, k, v)
    audit(db, org_id=p.org_id, user_id=p.id, action="project.update", entity_type="project", entity_id=proj.id,
          detail={k: str(v) for k, v in data.items()}, ip=p.ip)
    db.commit()
    return ProjectOut.model_validate(proj)


@router.post("/{project_id}/members", status_code=201)
def add_member(project_id: str, body: MemberIn, db: DB, p: Annotated[Principal, Depends(require("project.manage"))]):
    get_project(db, project_id, p)
    u = db.get(User, body.user_id)
    if not u or u.org_id != p.org_id:
        raise HTTPException(404, "User not found")
    if not db.get(ProjectMember, (project_id, u.id)):
        db.add(ProjectMember(project_id=project_id, user_id=u.id, project_role=body.project_role))
    audit(db, org_id=p.org_id, user_id=p.id, action="project.member_add", entity_type="project", entity_id=project_id,
          detail={"user": u.id}, ip=p.ip)
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/members/{user_id}")
def remove_member(project_id: str, user_id: str, db: DB, p: Annotated[Principal, Depends(require("project.manage"))]):
    get_project(db, project_id, p)
    m = db.get(ProjectMember, (project_id, user_id))
    if m:
        db.delete(m)
        audit(db, org_id=p.org_id, user_id=p.id, action="project.member_remove", entity_type="project",
              entity_id=project_id, detail={"user": user_id}, ip=p.ip)
        db.commit()
    return {"ok": True}
