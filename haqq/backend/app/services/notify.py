"""Deadline monitoring, escalation and notifications (in-app always; e-mail when SMTP is configured)."""

from __future__ import annotations

import logging
import smtplib
from datetime import date
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Deadline, Notification, Project, User

log = logging.getLogger("haqq.notify")
ESCALATION_ROLES = {1: ["contracts_manager", "project_manager"], 2: ["commercial_director"], 3: ["ceo", "admin"]}


def send_email(to: str, subject: str, body: str) -> str:
    s = get_settings()
    if not s.smtp_host:
        return "not_configured"
    try:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
        msg.set_content(body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return "sent"
    except Exception as exc:  # noqa: BLE001
        log.warning("E-mail to %s failed: %s", to, exc)
        return "failed"


def notify(db: Session, user: User, *, kind: str, title: str, body: str, link: str | None, dedupe_key: str) -> bool:
    if db.execute(select(Notification.id).where(Notification.user_id == user.id, Notification.dedupe_key == dedupe_key)).first():
        return False
    n = Notification(org_id=user.org_id, user_id=user.id, kind=kind, title=title, body=body, link=link,
                     dedupe_key=dedupe_key)
    n.email_status = send_email(user.email, f"[HAQQ] {title}", f"{body}\n\n{link or ''}")
    db.add(n)
    return True


def escalation_level(dl: Deadline, today: date) -> int:
    if dl.due_date is None:
        return 1 if dl.certainty == "undetermined" else 0
    left = (dl.due_date - today).days
    if left < 0:
        return 3
    if left <= 3:
        return 2
    if left <= 14:
        return 1
    return 0


def scan_deadlines(db: Session, org_id: str | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    q = select(Deadline).where(Deadline.status == "open")
    if org_id:
        q = q.where(Deadline.org_id == org_id)
    sent = 0
    for dl in db.execute(q).scalars():
        level = escalation_level(dl, today)
        dl.escalation_level = level
        if level == 0:
            continue
        project = db.get(Project, dl.project_id)
        roles = [r for lvl in range(1, level + 1) for r in ESCALATION_ROLES[lvl]]
        users = db.execute(select(User).where(User.org_id == dl.org_id, User.is_active.is_(True),
                                              User.role.in_(roles))).scalars().all()
        if dl.assigned_to:
            assignee = db.get(User, dl.assigned_to)
            if assignee and assignee not in users:
                users.append(assignee)
        when = dl.due_date.isoformat() if dl.due_date else "undetermined"
        state = "OVERDUE" if dl.due_date and dl.due_date < today else "due"
        for u in users:
            if u.role == "project_manager" and project.manager_id not in (None, u.id):
                continue
            title = (f"{dl.title} — {state} {when}" if u.language == "en"
                     else f"{dl.title} — {'متأخر' if state == 'OVERDUE' else 'مستحق'} {when}")
            body = f"{project.name}: {dl.title}. Due: {when} (certainty: {dl.certainty})."
            if notify(db, u, kind="deadline", title=title, body=body, link=f"/projects/{dl.project_id}/deadlines",
                      dedupe_key=f"dl:{dl.id}:L{level}:{when}"):
                sent += 1
    return {"notifications": sent}
