"""Executive intelligence: every KPI is computed from stored records and returns the ids needed for
drill-down. No figure is hard-coded."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Claim, Deadline, Entitlement, Project, ProjectEvent
from .claims import PIPELINE_GROUPS, STAGES

OPEN_ENT = ("potential", "insufficient_evidence", "requires_expert_verification", "substantiated")
PREP = set(PIPELINE_GROUPS["preparation"])
SUBMITTED = {"submitted", "employer_response", "negotiation", "approved", "rejected", "collected", "closed"}


def D(x) -> Decimal:
    return Decimal(x or 0)


def compute(db: Session, project_ids: list[str], today: date | None = None) -> dict:
    today = today or date.today()
    projects = db.execute(select(Project).where(Project.id.in_(project_ids))).scalars().all() if project_ids else []
    ents = db.execute(select(Entitlement).where(Entitlement.project_id.in_(project_ids))).scalars().all() if project_ids else []
    claims = db.execute(select(Claim).where(Claim.project_id.in_(project_ids))).scalars().all() if project_ids else []
    dls = db.execute(select(Deadline).where(Deadline.project_id.in_(project_ids), Deadline.status == "open")).scalars().all() if project_ids else []
    pname = {p.id: p.name for p in projects}
    pname_ar = {p.id: p.name_ar or p.name for p in projects}

    open_ents = [e for e in ents if e.status in OPEN_ENT]
    claimed_ent_ids = {c.entitlement_id for c in claims}
    potential = [e for e in open_ents if e.financial_impact is not None]
    soon = today + timedelta(days=14)
    at_risk_ids = {e.id for e in open_ents if e.risk_level == "high"}
    for d in dls:
        if d.entitlement_id and d.due_date and d.due_date <= soon:
            at_risk_ids.add(d.entitlement_id)
    at_risk = [e for e in open_ents if e.id in at_risk_ids and e.financial_impact is not None]
    prep = [c for c in claims if c.stage in PREP]
    submitted = [c for c in claims if c.stage in SUBMITTED and c.submitted_at]
    approved = [c for c in claims if c.stage in ("approved", "collected") or (c.stage == "closed" and D(c.approved_amount) > 0)]
    rejected = [c for c in claims if c.stage == "rejected"]
    decided = len(approved) + len(rejected)
    upcoming = [d for d in dls if d.due_date and today <= d.due_date <= today + timedelta(days=30)]
    overdue = [d for d in dls if d.due_date and d.due_date < today]
    completeness = [e.evidence_completeness for e in open_ents]

    def ids(xs):
        return [x.id for x in xs]

    kpis = {
        "total_contract_value": {"value": str(sum((D(p.contract_value) for p in projects), Decimal(0))), "ids": ids(projects), "entity": "project"},
        "potential_entitlements": {"value": str(sum((D(e.financial_impact) for e in potential), Decimal(0))), "count": len(open_ents),
                                   "unquantified": len([e for e in open_ents if e.financial_impact is None]), "ids": ids(open_ents), "entity": "entitlement"},
        "claims_in_preparation": {"value": str(sum((D(c.claimed_amount) for c in prep), Decimal(0))), "count": len(prep), "ids": ids(prep), "entity": "claim"},
        "claims_submitted": {"value": str(sum((D(c.claimed_amount) for c in submitted), Decimal(0))), "count": len(submitted), "ids": ids(submitted), "entity": "claim"},
        "claims_approved": {"value": str(sum((D(c.approved_amount) for c in approved), Decimal(0))), "count": len(approved), "ids": ids(approved), "entity": "claim"},
        "claims_rejected": {"value": str(sum((D(c.claimed_amount) for c in rejected), Decimal(0))), "count": len(rejected), "ids": ids(rejected), "entity": "claim"},
        "outstanding_approved": {"value": str(sum((D(c.approved_amount) - D(c.collected_amount) for c in approved), Decimal(0))), "ids": ids(approved), "entity": "claim"},
        "cash_collected": {"value": str(sum((D(c.collected_amount) for c in claims), Decimal(0))), "ids": ids([c for c in claims if D(c.collected_amount) > 0]), "entity": "claim"},
        "revenue_at_risk": {"value": str(sum((D(e.financial_impact) for e in at_risk), Decimal(0))), "count": len(at_risk_ids), "ids": sorted(at_risk_ids), "entity": "entitlement"},
        "critical_deadlines": {"value": len(upcoming), "overdue": len(overdue), "ids": ids(upcoming + overdue), "entity": "deadline"},
        "evidence_completeness": {"value": round(sum(completeness) / len(completeness), 2) if completeness else None, "ids": ids(open_ents), "entity": "entitlement"},
        "claim_conversion_rate": {"value": round(len(approved) / decided, 2) if decided else None, "approved": len(approved), "decided": decided,
                                  "amount_rate": round(float(sum((D(c.approved_amount) for c in approved), Decimal(0)) /
                                                             sum((D(c.claimed_amount) for c in approved + rejected), Decimal(1))), 2) if decided else None,
                                  "ids": ids(approved + rejected), "entity": "claim"},
        "entitlements_not_yet_claimed": {"count": len([e for e in open_ents if e.id not in claimed_ent_ids]), "entity": "entitlement",
                                         "ids": [e.id for e in open_ents if e.id not in claimed_ent_ids]},
    }

    by_project = []
    for p in projects:
        pe = [e for e in open_ents if e.project_id == p.id]
        pc = [c for c in claims if c.project_id == p.id]
        by_project.append({"project_id": p.id, "name": p.name, "name_ar": pname_ar[p.id], "code": p.code,
                           "contract_value": str(p.contract_value),
                           "potential": str(sum((D(e.financial_impact) for e in pe), Decimal(0))),
                           "at_risk": str(sum((D(e.financial_impact) for e in pe if e.id in at_risk_ids), Decimal(0))),
                           "submitted": str(sum((D(c.claimed_amount) for c in pc if c in submitted), Decimal(0))),
                           "approved": str(sum((D(c.approved_amount) for c in pc if c in approved), Decimal(0))),
                           "collected": str(sum((D(c.collected_amount) for c in pc), Decimal(0))),
                           "is_demo": p.is_demo,
                           "risk": {lvl: len([e for e in pe if e.risk_level == lvl]) for lvl in ("high", "medium", "low")}})
    by_project.sort(key=lambda r: -float(r["potential"]))

    by_type: dict[str, dict] = defaultdict(lambda: {"value": Decimal(0), "count": 0})
    for e in open_ents:
        by_type[e.entitlement_type]["value"] += D(e.financial_impact)
        by_type[e.entitlement_type]["count"] += 1
    by_status: dict[str, int] = defaultdict(int)
    for e in ents:
        by_status[e.status] += 1
    pipeline = [{"stage": s, "count": len([c for c in claims if c.stage == s]),
                 "value": str(sum((D(c.claimed_amount) for c in claims if c.stage == s), Decimal(0)))} for s in STAGES]
    months: dict[str, dict] = defaultdict(lambda: {"submitted": Decimal(0), "approved": Decimal(0), "collected": Decimal(0), "detected": Decimal(0)})
    for c in claims:
        if c.submitted_at:
            months[c.submitted_at.strftime("%Y-%m")]["submitted"] += D(c.claimed_amount)
        if c.responded_at and D(c.approved_amount) > 0:
            months[c.responded_at.strftime("%Y-%m")]["approved"] += D(c.approved_amount)
    ev_dates = dict(db.execute(select(ProjectEvent.id, ProjectEvent.event_date)
                               .where(ProjectEvent.project_id.in_(project_ids))).all()) if project_ids else {}
    for e in ents:  # potential value by the month the triggering event occurred
        when = ev_dates.get(e.event_id) or e.created_at.date()
        months[when.strftime("%Y-%m")]["detected"] += D(e.financial_impact)
    trend = [{"month": m, **{k: str(v) for k, v in vals.items()}} for m, vals in sorted(months.items())][-12:]
    aging = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    aging_ids: dict[str, list] = {k: [] for k in aging}
    for c in claims:
        if c.stage in ("submitted", "employer_response", "negotiation") and c.submitted_at:
            age = (today - c.submitted_at).days
            k = "0-30" if age <= 30 else "31-60" if age <= 60 else "61-90" if age <= 90 else "90+"
            aging[k] += 1
            aging_ids[k].append(c.id)
    deadlines = sorted(
        [{"id": d.id, "title": d.title, "due_date": d.due_date.isoformat() if d.due_date else None,
          "certainty": d.certainty, "project_id": d.project_id, "project": pname.get(d.project_id),
          "entitlement_id": d.entitlement_id, "overdue": bool(d.due_date and d.due_date < today),
          "days_left": (d.due_date - today).days if d.due_date else None} for d in dls],
        key=lambda x: x["due_date"] or "9999")
    return {"as_of": today.isoformat(), "currency": "EGP", "kpis": kpis, "by_project": by_project,
            "by_type": [{"type": k, "value": str(v["value"]), "count": v["count"]} for k, v in by_type.items()],
            "by_status": dict(by_status), "pipeline": pipeline, "trend": trend,
            "aging": [{"bucket": k, "count": v, "ids": aging_ids[k]} for k, v in aging.items()],
            "deadlines": deadlines[:40],
            "demo_data_present": any(p.is_demo for p in projects)}
