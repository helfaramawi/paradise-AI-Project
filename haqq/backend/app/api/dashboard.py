"""Executive dashboard and exports."""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select

from ..core.audit import audit
from ..core.deps import DB, Principal, accessible_project_ids, require
from ..engines.taxonomy import CLAUSE_CATEGORIES, DOC_TYPES, ENTITLEMENT_TYPES, EVENT_CATEGORIES, LABELS_STATUS
from ..engines.valuation import CATEGORIES as COST_CATEGORIES
from ..models import Claim, Entitlement, Project
from ..services import dashboard
from ..services.claims import STAGE_LABELS

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/executive")
def executive(db: DB, p: Annotated[Principal, Depends(require("project.read"))], project_id: str | None = None):
    ids = accessible_project_ids(db, p)
    if project_id:
        ids = [i for i in ids if i == project_id]
    return dashboard.compute(db, ids)


@router.get("/reports/portfolio.xlsx")
def portfolio_export(db: DB, p: Annotated[Principal, Depends(require("report.export"))],
                     lang: str = Query("en", pattern="^(en|ar)$")):
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    ids = accessible_project_ids(db, p)
    data = dashboard.compute(db, ids)
    wb = openpyxl.Workbook()
    ar = lang == "ar"
    ws = wb.active
    ws.title = "KPIs"
    ws.sheet_view.rightToLeft = ar
    hdr = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="13315C")
    ws.append(["HAQQ — " + ("ملخص المحفظة" if ar else "Portfolio summary"), f"as of {data['as_of']}"])
    if data["demo_data_present"]:
        ws.append(["DEMO DATA PRESENT — figures include fictional demonstration projects" if not ar
                   else "تتضمن الأرقام بيانات عرض توضيحي افتراضية"])
    ws.append([])
    for k, v in data["kpis"].items():
        ws.append([k, v.get("value"), v.get("count")])
    ws2 = wb.create_sheet("Entitlements")
    ws2.sheet_view.rightToLeft = ar
    cols = ["Project", "Ref", "Type", "Status", "Financial impact (EGP)", "Basis", "Time (days)", "Risk", "Confidence",
            "Evidence %", "Review", "Notice due", "Demo"]
    ws2.append(cols)
    for c in ws2[1]:
        c.font, c.fill = hdr, fill
    projects = {x.id: x for x in db.execute(select(Project).where(Project.id.in_(ids))).scalars()} if ids else {}
    for e in db.execute(select(Entitlement).where(Entitlement.project_id.in_(ids)).order_by(Entitlement.project_id, Entitlement.ref)).scalars() if ids else []:
        ws2.append([projects[e.project_id].code, e.ref, ENTITLEMENT_TYPES[e.entitlement_type][lang],
                    LABELS_STATUS[e.status][lang], float(e.financial_impact) if e.financial_impact is not None else None,
                    e.financial_basis, e.time_impact_days, e.risk_level, e.confidence, e.evidence_completeness,
                    e.review_status, (e.notice or {}).get("notice", {}).get("due_date"), "DEMO" if e.is_demo else ""])
    ws3 = wb.create_sheet("Claims")
    ws3.sheet_view.rightToLeft = ar
    ws3.append(["Project", "Ref", "Title", "Stage", "Claimed", "Approved", "Collected", "Submitted", "Demo"])
    for c in ws3[1]:
        c.font, c.fill = hdr, fill
    for c in db.execute(select(Claim).where(Claim.project_id.in_(ids))).scalars() if ids else []:
        ws3.append([projects[c.project_id].code, c.ref, c.title, STAGE_LABELS[c.stage][1 if ar else 0],
                    float(c.claimed_amount), float(c.approved_amount), float(c.collected_amount),
                    c.submitted_at.isoformat() if c.submitted_at else None, "DEMO" if c.is_demo else ""])
    for sheet in (ws, ws2, ws3):
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = 22
    buf = io.BytesIO()
    wb.save(buf)
    audit(db, org_id=p.org_id, user_id=p.id, action="report.export", detail={"report": "portfolio", "lang": lang}, ip=p.ip)
    db.commit()
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=HAQQ_portfolio_{date.today()}.xlsx"})


@router.get("/meta/taxonomy")
def taxonomy():
    def strip(d):
        return {k: {"en": v["en"], "ar": v["ar"]} for k, v in d.items()}
    return {"doc_types": strip(DOC_TYPES), "clause_categories": strip(CLAUSE_CATEGORIES),
            "event_categories": strip(EVENT_CATEGORIES), "entitlement_types": strip(ENTITLEMENT_TYPES),
            "entitlement_status": LABELS_STATUS, "cost_categories": COST_CATEGORIES,
            "claim_stages": {k: {"en": v[0], "ar": v[1]} for k, v in STAGE_LABELS.items()}}


__all__ = ["router", "Decimal"]
