"""Contractual deadline intelligence and notifications."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..core.audit import audit
from ..core.deps import DB, Principal, accessible_project_ids, get_owned, get_project, require
from ..engines.deadlines import Calendar, compute
from ..models import Clause, Deadline, Notification, Organization, Project, User
from ..schemas import DeadlineIn, DeadlineOut, DeadlineUpdate
from ..services.notify import scan_deadlines

router = APIRouter(tags=["deadlines"])


def _out(db, d: Deadline, today: date) -> dict:
    proj = db.get(Project, d.project_id)
    return {**DeadlineOut.model_validate(d).model_dump(mode="json"), "project_name": proj.name,
            "project_name_ar": proj.name_ar, "overdue": bool(d.status == "open" and d.due_date and d.due_date < today),
            "days_left": (d.due_date - today).days if d.due_date else None}


@router.get("/deadlines")
def all_deadlines(db: DB, p: Annotated[Principal, Depends(require("deadline.read"))], status: str = "open",
                  ids: str | None = None):
    pids = accessible_project_ids(db, p)
    if not pids:
        return []
    q = select(Deadline).where(Deadline.project_id.in_(pids))
    if ids:
        q = q.where(Deadline.id.in_(ids.split(",")[:200]))
    elif status != "all":
        q = q.where(Deadline.status == status)
    today = date.today()
    rows = db.execute(q.order_by(Deadline.due_date.asc().nulls_first())).scalars().all()
    return [_out(db, d, today) for d in rows]


@router.get("/projects/{project_id}/deadlines")
def project_deadlines(project_id: str, db: DB, p: Annotated[Principal, Depends(require("deadline.read"))]):
    get_project(db, project_id, p)
    today = date.today()
    rows = db.execute(select(Deadline).where(Deadline.project_id == project_id)
                      .order_by(Deadline.due_date.asc().nulls_first())).scalars().all()
    return [_out(db, d, today) for d in rows]


@router.post("/projects/{project_id}/deadlines", status_code=201)
def create_deadline(project_id: str, body: DeadlineIn, db: DB, p: Annotated[Principal, Depends(require("deadline.manage"))]):
    proj = get_project(db, project_id, p)
    org = db.get(Organization, p.org_id)
    d = Deadline(org_id=p.org_id, project_id=project_id, title=body.title, deadline_type=body.deadline_type,
                 assigned_to=body.assigned_to, is_demo=proj.is_demo)
    if body.clause_id:
        get_owned(db, Clause, body.clause_id, p)
        d.clause_id = body.clause_id
    if body.due_date:
        d.due_date, d.certainty = body.due_date, "manual"
    elif body.trigger_date and body.period_days is not None:
        r = compute(body.trigger_date, True, body.period_days, body.day_type, Calendar.from_org(org.weekend_days, org.holidays))
        d.due_date, d.certainty, d.uncertainty_notes, d.calculation = r.due_date, r.certainty, r.notes, r.calculation
        d.trigger_date, d.period_days, d.day_type = body.trigger_date, body.period_days, body.day_type
    else:
        raise HTTPException(422, "Provide a due_date, or a trigger_date with period_days")
    if body.assigned_to:
        u = db.get(User, body.assigned_to)
        if not u or u.org_id != p.org_id:
            raise HTTPException(422, "Assignee not found")
    db.add(d)
    db.flush()
    audit(db, org_id=p.org_id, user_id=p.id, action="deadline.create", entity_type="deadline", entity_id=d.id, ip=p.ip)
    db.commit()
    return _out(db, d, date.today())


@router.patch("/deadlines/{deadline_id}")
def update_deadline(deadline_id: str, body: DeadlineUpdate, db: DB, p: Annotated[Principal, Depends(require("deadline.manage"))]):
    d = get_owned(db, Deadline, deadline_id, p)
    data = body.model_dump(exclude_unset=True)
    if "assigned_to" in data and data["assigned_to"]:
        u = db.get(User, data["assigned_to"])
        if not u or u.org_id != p.org_id:
            raise HTTPException(422, "Assignee not found")
    if "due_date" in data and data["due_date"]:
        d.certainty = "manual"
    for k, v in data.items():
        setattr(d, k, v)
    if data.get("status") == "completed":
        d.completed_at = datetime.now(UTC)
    audit(db, org_id=p.org_id, user_id=p.id, action="deadline.update", entity_type="deadline", entity_id=d.id,
          detail={k: str(v) for k, v in data.items()}, ip=p.ip)
    db.commit()
    return _out(db, d, date.today())


@router.post("/deadlines/scan")
def scan(db: DB, p: Annotated[Principal, Depends(require("deadline.manage"))]):
    res = scan_deadlines(db, p.org_id)
    db.commit()
    return res


@router.get("/notifications")
def notifications(db: DB, p: Annotated[Principal, Depends(require("project.read"))], unread_only: bool = False):
    q = select(Notification).where(Notification.user_id == p.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    rows = db.execute(q.order_by(Notification.created_at.desc()).limit(50)).scalars().all()
    return [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read": n.read_at is not None,
             "email_status": n.email_status, "created_at": n.created_at} for n in rows]


@router.post("/notifications/read-all")
def read_all(db: DB, p: Annotated[Principal, Depends(require("project.read"))]):
    for n in db.execute(select(Notification).where(Notification.user_id == p.id, Notification.read_at.is_(None))).scalars():
        n.read_at = datetime.now(UTC)
    db.commit()
    return {"ok": True}
