"""Idempotent seed of the demonstration workspace (clearly labelled synthetic)."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .agents.base import AGENT_CATALOG, DEFAULT_AUTHORITY
from .config import get_settings
from .governance.engine import DEFAULT_POLICIES
from .models import (
    AgentDefinition,
    AutomationWorkflow,
    DataConnection,
    DatasetVersion,
    EnterpriseDataset,
    GovernancePolicy,
    Organization,
    Permission,
    Role,
    Tenant,
    User,
)
from .security import PERMISSIONS, ROLE_DEFINITIONS, hash_password
from .services.pipeline import production_model
from .simulation.assumptions import BASELINE_PROVENANCE, Baseline
from .simulation.validation import validate_baseline

DEMO_USERS = [
    ("ceo@futuremirror.demo", "Nadia Hassan", "Chief Executive Officer", ["ceo"]),
    ("cfo@futuremirror.demo", "Karim Mansour", "Chief Financial Officer", ["cfo"]),
    ("coo@futuremirror.demo", "Omar Farouk", "Chief Operating Officer", ["coo"]),
    ("legal@futuremirror.demo", "Laila Adel", "General Counsel", ["legal"]),
    ("hr@futuremirror.demo", "Salma Youssef", "HR Director", ["hr"]),
    ("analyst@futuremirror.demo", "Youssef Samir", "Decision Analyst", ["analyst"]),
    ("admin@futuremirror.demo", "Platform Admin", "Administrator", ["admin"]),
    ("viewer@futuremirror.demo", "Board Observer", "Viewer", ["viewer"]),
]


def checksum(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def seed_permissions(db: Session) -> dict[str, Permission]:
    perms = {p.key: p for p in db.scalars(select(Permission))}
    for key, desc in PERMISSIONS.items():
        if key not in perms:
            perms[key] = Permission(key=key, description=desc)
            db.add(perms[key])
    db.flush()
    return perms


def seed_tenant(db: Session, slug: str = "nile-engineering", name: str = "Nile Engineering Group (Synthetic Demo)",
                with_users: bool = True) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant:
        return tenant
    perms = seed_permissions(db)
    org = Organization(name=name)
    db.add(org)
    db.flush()
    tenant = Tenant(organization_id=org.id, name=name, slug=slug, settings={"currency": "EGP", "emergency_stop": False})
    db.add(tenant)
    db.flush()
    roles = {}
    for key, (en, ar, plist) in ROLE_DEFINITIONS.items():
        r = Role(tenant_id=tenant.id, key=key, name_en=en, name_ar=ar)
        r.permissions = [perms[p] for p in plist]
        db.add(r)
        roles[key] = r
    db.flush()
    if with_users:
        pw = hash_password(get_settings().demo_password)
        for email, full, title, rkeys in DEMO_USERS:
            u = User(tenant_id=tenant.id, email=email, full_name=full, title=title, password_hash=pw)
            u.roles = [roles[k] for k in rkeys]
            db.add(u)
    b = Baseline()
    ds = EnterpriseDataset(tenant_id=tenant.id, name="Synthetic ERP — FY2026 operating profile", source="synthetic",
                           is_synthetic=True)
    db.add(ds)
    db.flush()
    data = b.model_dump()
    db.add(DatasetVersion(dataset_id=ds.id, version=1, data=data, provenance=BASELINE_PROVENANCE,
                          validation=validate_baseline(b).model_dump(), checksum=checksum(data),
                          note="Initial synthetic demonstration dataset"))
    for p in DEFAULT_POLICIES:
        db.add(GovernancePolicy(tenant_id=tenant.id, code=p["code"], name_en=p["name_en"], name_ar=p["name_ar"],
                                description_en=p["description_en"], description_ar=p["description_ar"],
                                effect=p["effect"], rule=p["rule"], locked=p.get("locked", False)))
    connections = [
        ("synthetic_erp", "Synthetic ERP (demo)", "connected", "working", {"dataset": ds.id}),
        ("csv", "CSV / Excel import", "available", "working", {"accepted": [".csv", ".xlsx"]}),
        ("odoo", "Odoo ERP (XML-RPC adapter)", "not_configured", "adapter", {"url": "", "database": "", "username": ""}),
        ("d365_fo", "Microsoft Dynamics 365 Finance & Operations (OData adapter)", "not_configured", "adapter",
         {"environment_url": "", "tenant_id": "", "client_id": "", "legal_entity": ""}),
        ("d365_bc", "Microsoft Dynamics 365 Business Central (API v2.0 adapter)", "not_configured", "adapter",
         {"tenant_id": "", "client_id": "", "environment": "production", "company_id": ""}),
        ("sap", "SAP S/4HANA (OData)", "not_configured", "adapter",
         {"base_url": "", "username": "", "company_code": "", "ledger": "0L"}),
        ("rest", "Generic REST API", "not_configured", "adapter",
         {"url": "", "records_path": "", "account_field": "account", "amount_field": "amount"}),
        ("sql", "SQL database (read-only view)", "not_configured", "adapter",
         {"dialect": "postgresql", "host": "", "database": "", "table": ""}),
    ]
    for kind, nm, status, impl, cfg in connections:
        db.add(DataConnection(tenant_id=tenant.id, kind=kind, name=nm, status=status, implementation=impl, config=cfg))
    workflows = [
        ("scheduled_analysis", "Weekly scheduled re-analysis", "تحليل دوري أسبوعي", "schedule", "0 6 * * 1", False,
         "Re-runs the decision simulation weekly on the latest dataset version.", "إعادة تشغيل المحاكاة أسبوعياً."),
        ("erp_sync", "ERP data synchronisation (read-only)", "مزامنة بيانات تخطيط الموارد (قراءة فقط)", "schedule", "0 2 * * *",
         False, "Pulls the latest cost data from configured connectors.", "سحب أحدث بيانات التكاليف."),
        ("review_notification", "Decision review notification", "إشعار مراجعة القرار", "event", None, False,
         "Notifies approvers when a strategy is submitted for approval.", "إخطار المعتمدين عند تقديم استراتيجية."),
        ("approval_workflow", "Approval routing", "توجيه الاعتمادات", "event", None, False,
         "Routes approval requests to required roles via email/Teams.", "توجيه طلبات الاعتماد للأدوار المطلوبة."),
        ("kpi_monitor", "Financial KPI monitoring", "مراقبة مؤشرات الأداء المالية", "schedule", "0 7 * * *", False,
         "Compares monthly actuals with forecast bands and alerts on breaches.", "مقارنة الفعلي بنطاقات التوقع."),
        ("post_decision_tracking", "Post-decision performance tracking", "متابعة الأداء بعد القرار", "schedule", "0 8 1 * *",
         False, "Collects actual outcomes for the Reality Feedback Loop.", "جمع النتائج الفعلية لحلقة التغذية الراجعة."),
        ("execute_contractor_notice", "Issue contractor reduction notices", "إصدار إخطارات خفض المتعاقدين", "manual", None,
         True, "CONSEQUENTIAL: would send notices via ERP/HR systems. Disabled by default; dry-run only.",
         "ذو أثر: يرسل إخطارات عبر الأنظمة. معطل افتراضياً؛ محاكاة فقط."),
    ]
    for key, en, ar, trig, sched, conseq, d_en, d_ar in workflows:
        db.add(AutomationWorkflow(tenant_id=tenant.id, key=key, name_en=en, name_ar=ar, trigger=trig, schedule=sched,
                                  consequential=conseq, description_en=d_en, description_ar=d_ar,
                                  n8n_webhook_path=f"future-mirror/{key}"))
    db.commit()
    return tenant


def seed_agents(db: Session) -> None:
    existing = {a.key for a in db.scalars(select(AgentDefinition))}
    for key, meta in AGENT_CATALOG.items():
        if key not in existing:
            db.add(AgentDefinition(key=key, authority=DEFAULT_AUTHORITY, **meta))
    db.commit()


def seed_all(db: Session) -> None:
    seed_agents(db)
    production_model(db)
    seed_tenant(db)
