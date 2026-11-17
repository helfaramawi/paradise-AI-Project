"""Role-based access control: permission catalogue and role grants."""

from __future__ import annotations

PERMISSIONS: dict[str, str] = {
    "project.read": "View projects",
    "project.manage": "Create and edit projects and team assignments",
    "document.read": "View and download project documents",
    "document.upload": "Upload project documents",
    "contract.analyze": "Run contract and document analysis",
    "clause.verify": "Verify or correct extracted clauses",
    "event.read": "View project events",
    "event.write": "Record and edit project events",
    "entitlement.read": "View potential entitlements",
    "entitlement.run": "Run the entitlement discovery engine",
    "entitlement.review": "Accept or reject potential entitlements",
    "valuation.write": "Edit claim valuation worksheets",
    "valuation.verify": "Verify claim valuations",
    "claim.read": "View claims",
    "claim.write": "Create claims and advance working stages",
    "claim.legal_review": "Record legal / commercial review",
    "claim.approve": "Give management approval for claim submission",
    "claim.generate": "Generate claim documents",
    "deadline.read": "View contractual deadlines",
    "deadline.manage": "Create, assign and complete deadlines",
    "dashboard.executive": "View the executive dashboard",
    "report.export": "Export reports",
    "admin.users": "Manage users and roles",
    "admin.org": "Manage organisation settings and AI data policy",
    "admin.subscription": "Manage subscription and view usage",
    "audit.read": "View audit trail and access logs",
}

ALL = list(PERMISSIONS)
_READ = ["project.read", "document.read", "event.read", "entitlement.read", "claim.read", "deadline.read"]

ROLES: dict[str, dict] = {
    "admin": {"en": "System Administrator", "ar": "مدير النظام", "perms": ALL, "all_projects": True},
    "ceo": {
        "en": "CEO / Managing Director", "ar": "الرئيس التنفيذي / العضو المنتدب", "all_projects": True,
        "perms": _READ + ["dashboard.executive", "report.export", "claim.approve", "entitlement.review", "audit.read"],
    },
    "cfo": {
        "en": "CFO / Finance Director", "ar": "المدير المالي", "all_projects": True,
        "perms": _READ + ["dashboard.executive", "report.export", "valuation.verify", "claim.approve",
                          "admin.subscription"],
    },
    "commercial_director": {
        "en": "Commercial Director", "ar": "المدير التجاري", "all_projects": True,
        "perms": _READ + ["project.manage", "document.upload", "contract.analyze", "clause.verify", "event.write",
                          "entitlement.run", "entitlement.review", "valuation.write", "valuation.verify",
                          "claim.write", "claim.legal_review", "claim.approve", "claim.generate",
                          "deadline.manage", "dashboard.executive", "report.export"],
    },
    "contracts_manager": {
        "en": "Contracts Manager", "ar": "مدير العقود", "all_projects": True,
        "perms": _READ + ["document.upload", "contract.analyze", "clause.verify", "event.write", "entitlement.run",
                          "entitlement.review", "valuation.write", "claim.write", "claim.generate",
                          "deadline.manage", "dashboard.executive", "report.export"],
    },
    "project_manager": {
        "en": "Project Manager", "ar": "مدير المشروع", "all_projects": False,
        "perms": _READ + ["document.upload", "contract.analyze", "event.write", "entitlement.run",
                          "valuation.write", "claim.write", "deadline.manage", "report.export"],
    },
    "site_engineer": {
        "en": "Site Engineer", "ar": "مهندس الموقع", "all_projects": False,
        "perms": ["project.read", "document.read", "document.upload", "event.read", "event.write", "deadline.read"],
    },
    "legal_reviewer": {
        "en": "Legal Reviewer", "ar": "المراجع القانوني", "all_projects": True,
        "perms": _READ + ["clause.verify", "entitlement.review", "claim.legal_review", "report.export"],
    },
}


def role_permissions(role: str) -> set[str]:
    return set(ROLES.get(role, {}).get("perms", []))


def role_sees_all_projects(role: str) -> bool:
    return bool(ROLES.get(role, {}).get("all_projects"))
