"""Create the DEMO organisation, users, projects and documents, and run them through the real pipeline.

    python -m app.demo.seed            # create (idempotent: skipped if the demo org exists)
    python -m app.demo.seed --reset    # delete and recreate the demo organisation

Everything created here is flagged is_demo=True and labelled DEMO DATA in the UI and in exports.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from ..core.deps import Principal
from ..core.rbac import role_permissions
from ..core.security import hash_password
from ..db import SessionLocal
from ..models import Entitlement, Job, Organization, Project, ProjectEvent, ProjectMember, User
from ..schemas import ValuationIn, ValuationLineIn
from ..seed import seed_base
from ..services import claimdocs, discovery, jobs
from ..services.claims import transition
from ..services.pipeline import upload_document
from ..services.subscription import start_trial
from . import documents as D

log = logging.getLogger("haqq.demo")
DEMO_SLUG = "demo-example-construction"
DEMO_PASSWORD = "HaqqDemo!2026"
USERS = [
    ("admin@haqq.demo", "Mona Adel (DEMO)", "admin", "System Administrator"),
    ("ceo@haqq.demo", "Eng. Hany Mostafa (DEMO)", "ceo", "Managing Director"),
    ("cfo@haqq.demo", "Sara Fathy (DEMO)", "cfo", "Finance Director"),
    ("commercial@haqq.demo", "Karim Nabil (DEMO)", "commercial_director", "Commercial Director"),
    ("contracts@haqq.demo", "Yasmin Samir (DEMO)", "contracts_manager", "Contracts Manager"),
    ("pm@haqq.demo", "Eng. Omar Khaled (DEMO)", "project_manager", "Project Manager"),
    ("site@haqq.demo", "Eng. Ahmed Ali (DEMO)", "site_engineer", "Site Engineer"),
    ("legal@haqq.demo", "Dina Hassan (DEMO)", "legal_reviewer", "Legal Counsel"),
]


def _principal(u: User) -> Principal:
    return Principal(user=u, session_id="demo-seed", ip=None, permissions=role_permissions(u.role))


def _upload(db, org, project, user, filename, data, **kw):
    doc = upload_document(db, org_id=org.id, project_id=project.id, user_id=user.id, filename=filename, data=data,
                          is_demo=True, **kw)
    db.commit()
    for job_id in db.execute(select(Job.id).where(Job.status == "queued", Job.payload["document_id"].as_string() == doc.id)).scalars():
        jobs.run_job(job_id)
    db.refresh(doc)
    return doc


def _event(db, org, project, user, *, title, description, category, event_date, docs, est_cost=None, est_days=None,
           party="employer"):
    ev = ProjectEvent(org_id=org.id, project_id=project.id, ref=discovery.next_ref(db, ProjectEvent, project.id, "EV"),
                      title=title, description=description, event_date=event_date, awareness_date=event_date,
                      category=category, category_source="user", responsible_party=party, est_cost_impact=est_cost,
                      est_time_impact_days=est_days, currency="EGP", created_by=user.id, is_demo=True)
    db.add(ev)
    db.flush()
    from ..models import EventDocument

    for d in docs:
        db.add(EventDocument(event_id=ev.id, document_id=d.id, org_id=org.id, link_source="user", confirmed=True))
    db.flush()
    return ev


def _boq_valuation(boq_doc, lines) -> ValuationIn:
    return ValuationIn(
        currency="EGP", overhead_pct=Decimal(0), profit_pct=Decimal(0), vat_applicable=False,
        assumptions=["Quantities from the Contractor's measurement of the instructed work (to be agreed with the Engineer).",
                     "Rates from the contract Bill of Quantities; pump set is a new rate from a supplier quotation."],
        contractual_basis_note="Clause 13.3 — valuation at BOQ rates; new rates where no rate applies.",
        lines=[ValuationLineIn(category=c, description=desc, quantity=Decimal(q), unit=u, rate=Decimal(r),
                               source_document_id=boq_doc.id if basis == "boq_rate" else None,
                               source_note=note, rate_basis=basis)
               for c, desc, q, u, r, basis, note in lines])


def reset(db) -> None:
    org = db.execute(select(Organization).where(Organization.slug == DEMO_SLUG)).scalar_one_or_none()
    if org:
        db.delete(org)
        db.commit()


def seed(today: date | None = None) -> dict:
    today = today or date.today()
    db = SessionLocal()
    try:
        seed_base(db)
        db.commit()
        if db.execute(select(Organization).where(Organization.slug == DEMO_SLUG)).scalar_one_or_none():
            return {"skipped": "demo organisation already exists"}
        org = Organization(name="Example Construction Company (DEMO)", name_ar="شركة مثال للمقاولات (عرض توضيحي)",
                           slug=DEMO_SLUG, default_language="ar", is_demo=True, onboarding_completed=True,
                           ai_external_processing=False)
        db.add(org)
        db.flush()
        start_trial(db, org.id, "enterprise", days=365)
        users = {}
        for email, name, role, title in USERS:
            u = User(org_id=org.id, email=email, full_name=name, role=role, title=title, language="ar" if role != "cfo" else "en",
                     password_hash=hash_password(DEMO_PASSWORD))
            db.add(u)
            users[role] = u
        db.flush()
        cm, pm, cfo, site = users["contracts_manager"], users["project_manager"], users["cfo"], users["site_engineer"]

        # ------------------------------------------------------------ Project 1 (the live demo journey)
        p1 = Project(org_id=org.id, code="NAC-01", name="New Administrative and Commercial Complex (DEMO)",
                     name_ar="المجمع الإداري والتجاري الجديد (عرض توضيحي)", classification="commercial_building",
                     location="New Administrative Capital, Egypt", employer_name="Example Development Company (DEMO)",
                     contractor_name="Example Construction Company (DEMO)",
                     engineer_name="Example Consulting Engineers (DEMO)", contract_form="Bespoke (FIDIC-style structure)",
                     contract_value=Decimal("100000000"), currency="EGP", start_date=today - timedelta(days=300),
                     original_completion_date=today + timedelta(days=430),
                     current_completion_date=today + timedelta(days=430), manager_id=pm.id, is_demo=True)
        db.add(p1)
        db.flush()
        db.add(ProjectMember(project_id=p1.id, user_id=pm.id, project_role="project_manager"))
        db.add(ProjectMember(project_id=p1.id, user_id=site.id, project_role="site_engineer"))
        db.commit()

        _upload(db, org, p1, cm, "DEMO_Conditions_of_Contract_NAC.pdf", D.contract_pdf(),
                             title="Conditions of Contract (DEMO)", declared_type="contract")
        _upload(db, org, p1, cm, "DEMO_Particular_Conditions_AR.docx", D.particular_conditions_docx_ar(),
                       title="الشروط الخاصة (عرض توضيحي)", declared_type="contract")
        d_boq = _upload(db, org, p1, cm, "DEMO_BOQ_NAC.xlsx", D.boq_xlsx(), title="Bill of Quantities (DEMO)")
        si_date = today - timedelta(days=21)
        d_si = _upload(db, org, p1, site, "DEMO_SI-014_scan.png", D.site_instruction_png(si_date),
                       title="Engineer's Site Instruction SI-014 (scanned, DEMO)", author_party="engineer", doc_date=si_date)
        d_mom22 = _upload(db, org, p1, pm, "DEMO_MoM-22.docx", D.minutes_docx(si_date + timedelta(days=2), title="Minutes of Meeting No. 22 (DEMO)", items=[
            "The Engineer confirmed Site Instruction SI-014 for the additional underground water tank and pump room at Block C.",
            "The Contractor stated that the tank is not included in the contract drawings or the Bill of Quantities.",
            "Excavation for the tank started on site. The Contractor will submit quantities for the additional work."]),
            title="Minutes of Meeting No. 22 (DEMO)", author_party="engineer", doc_date=si_date + timedelta(days=2))
        d_dr = _upload(db, org, p1, site, "DEMO_Daily_Report_tank.txt", D.daily_report_txt(si_date + timedelta(days=5),
                       "Work done today: excavation for additional water tank at Block C per SI-014 - 180 m3 excavated. "
                       "Blinding concrete scheduled tomorrow."), title="Daily Report — tank excavation (DEMO)",
                       author_party="contractor", doc_date=si_date + timedelta(days=5))

        hand_date = today - timedelta(days=75)
        d_mom18 = _upload(db, org, p1, pm, "DEMO_MoM-18.docx", D.minutes_docx(hand_date + timedelta(days=3), title="Minutes of Meeting No. 18 (DEMO)", items=[
            "Site handover of Zone B has been delayed by the Employer because the existing utility relocation is not complete.",
            "The Contractor's resources for Zone B are on standby pending access.",
            "The Employer expects to hand over Zone B within six weeks."]),
            title="Minutes of Meeting No. 18 (DEMO)", author_party="engineer", doc_date=hand_date + timedelta(days=3))
        d_emp = _upload(db, org, p1, pm, "DEMO_Employer_letter_ZoneB.pdf", D.letter_pdf([
            f"Date: {hand_date + timedelta(days=1):%d %B %Y}", "From: Example Development Company (DEMO) - the Employer",
            "To: Example Construction Company (DEMO)", "Subject: Site handover of Zone B",
            "Dear Sirs, we regret that the handover of Zone B is postponed due to the relocation",
            "of existing utilities. A revised handover date will be advised. Yours faithfully."]),
            title="Employer letter — Zone B handover postponed (DEMO)", declared_type="letter", author_party="employer",
            doc_date=hand_date + timedelta(days=1))
        d_notice_delay = _upload(db, org, p1, cm, "DEMO_Contractor_Notice_Delay_ZoneB.pdf", D.letter_pdf([
            f"Date: {hand_date + timedelta(days=12):%d %B %Y}", "From: Example Construction Company (DEMO) - the Contractor",
            "To: The Engineer", "Subject: Notice of delay and claim - late handover of Zone B",
            "Pursuant to Sub-Clauses 2.1 and 20.1 we hereby give notice of claim in respect of the",
            "delayed site handover of Zone B. Particulars will follow. Yours faithfully."]),
            title="Contractor's notice of delay — Zone B (DEMO)", declared_type="notice", author_party="contractor",
            doc_date=hand_date + timedelta(days=12))

        ipc_due = today - timedelta(days=40)
        d_ipc = _upload(db, org, p1, cfo, "DEMO_IPC-07.pdf", D.letter_pdf([
            "INTERIM PAYMENT CERTIFICATE No. 07 (DEMO)", f"Certified on: {ipc_due - timedelta(days=30):%d %B %Y}",
            f"Payment due date: {ipc_due:%d %B %Y}", "Amount certified for payment: EGP 6,240,000",
            "Amount due under Sub-Clause 14.7. Payment certificate issued by the Engineer."]),
            title="Interim Payment Certificate No. 07 (DEMO)", declared_type="payment_certificate", author_party="engineer",
            doc_date=ipc_due - timedelta(days=30))
        d_mail = _upload(db, org, p1, cfo, "DEMO_payment_followup.eml", D.email_eml(
            ipc_due + timedelta(days=7), "finance@contractor.demo", "accounts@employer.demo",
            "IPC-07 overdue payment", "Dear colleagues, IPC No. 07 (EGP 6,240,000) remains unpaid after its due date. "
            "Kindly arrange payment. Regards, Finance Department (DEMO)"),
            title="E-mail: IPC-07 overdue (DEMO)", author_party="contractor", doc_date=ipc_due + timedelta(days=7))
        d_notice_pay = _upload(db, org, p1, cm, "DEMO_Contractor_Notice_IPC07.pdf", D.letter_pdf([
            f"Date: {ipc_due + timedelta(days=10):%d %B %Y}", "From: Example Construction Company (DEMO) - the Contractor",
            "To: The Engineer / the Employer", "Subject: Notice of claim - delayed payment of IPC No. 07",
            "We hereby give notice under Sub-Clauses 14.8 and 20.1 of our claim for financing charges",
            "on the overdue amount of IPC No. 07. Yours faithfully."]),
            title="Contractor's notice — delayed payment IPC-07 (DEMO)", declared_type="notice", author_party="contractor",
            doc_date=ipc_due + timedelta(days=10))
        d_quote = _upload(db, org, p1, cm, "DEMO_Steel_quotation.pdf", D.letter_pdf([
            "SUPPLIER QUOTATION (DEMO)", f"Date: {today - timedelta(days=48):%d %B %Y}",
            "Reinforcing steel B500 - price per ton: EGP 46,800 (tender basis EGP 41,500)",
            "Purchase order reference PO-DEMO-311. Cost report attached."]),
            title="Steel supplier quotation (DEMO)", declared_type="cost_record", author_party="other",
            doc_date=today - timedelta(days=48))

        ev1 = _event(db, org, p1, site, title="Additional underground water tank and pump room instructed (SI-014)",
                     description="The Engineer instructed by Site Instruction SI-014 the construction of an additional "
                                 "underground fire-fighting water tank and pump room at Block C. The work is not in the "
                                 "contract drawings or the Bill of Quantities. Excavation has started.",
                     category="additional_work", event_date=si_date, docs=[d_si, d_boq, d_mom22, d_dr], party="engineer")
        ev2 = _event(db, org, p1, pm, title="Late site handover of Zone B by the Employer",
                     description="The Employer postponed the handover of Zone B because of utility relocation; Contractor's "
                                 "resources are on standby. Delay to Zone B activities is estimated at 45 days.",
                     category="site_access", event_date=hand_date, docs=[d_mom18, d_emp, d_notice_delay],
                     est_cost=Decimal("1350000"), est_days=45)
        ev3 = _event(db, org, p1, cfo, title="Late payment of Interim Payment Certificate No. 07",
                     description="IPC No. 07 for EGP 6,240,000 was not paid by its due date. Financing charges accrue under "
                                 "the payment provisions.", category="payment_delay", event_date=ipc_due,
                     docs=[d_ipc, d_mail, d_notice_pay], est_cost=Decimal("186000"))
        ev4 = _event(db, org, p1, cm, title="Reinforcing steel price increase",
                     description="Market price of reinforcing steel increased from EGP 41,500 to EGP 46,800 per ton. "
                                 "Estimated impact on remaining steel quantities.", category="material_escalation",
                     event_date=today - timedelta(days=50), docs=[d_quote], est_cost=Decimal("3400000"), party="third_party")
        db.commit()
        for ev in (ev1, ev2, ev3, ev4):
            discovery.run_for_event(db, ev, user_id=cm.id, today=today)
        db.commit()

        # valuation for EV-001 (draft — to be verified live in the demo by the CFO)
        ent1 = db.execute(select(Entitlement).where(Entitlement.event_id == ev1.id)).scalars().first()
        from ..api.entitlements import save_valuation

        save_valuation(db, ent1, _boq_valuation(d_boq, [
            ("direct_work", "Excavation for additional tank (BOQ A.01)", "420", "m3", "185", "boq_rate", "BOQ item A.01"),
            ("direct_work", "Blinding concrete C15 (BOQ A.02)", "35", "m3", "2400", "boq_rate", "BOQ item A.02"),
            ("direct_work", "Reinforced concrete C35 incl. formwork (BOQ B.01)", "180", "m3", "4850", "boq_rate", "BOQ item B.01"),
            ("direct_work", "Reinforcement steel (BOQ B.02)", "18", "ton", "41500", "boq_rate", "BOQ item B.02"),
            ("direct_work", "Waterproofing membrane (BOQ C.01)", "640", "m2", "260", "boq_rate", "BOQ item C.01"),
            ("subcontractor", "Fire pump set supply & installation (new rate — supplier quotation)", "1", "LS", "51900",
             "new_rate", "New rate — supplier quotation to be attached"),
        ]), _principal(cm))
        db.commit()
        discovery.run_for_event(db, ev1, user_id=cm.id, today=today)
        db.commit()

        # ------------------------------------------------------------ Project 2 (history for the dashboard)
        p2 = Project(org_id=org.id, code="WH-02", name="Industrial Warehouse Expansion (DEMO)",
                     name_ar="توسعة المستودعات الصناعية (عرض توضيحي)", classification="industrial",
                     location="10th of Ramadan City, Egypt", employer_name="Example Logistics Company (DEMO)",
                     contractor_name="Example Construction Company (DEMO)", engineer_name="Example Consulting Engineers (DEMO)",
                     contract_value=Decimal("38000000"), currency="EGP", start_date=today - timedelta(days=420),
                     original_completion_date=today + timedelta(days=60), current_completion_date=today + timedelta(days=95),
                     is_demo=True)
        db.add(p2)
        db.commit()
        c2 = _upload(db, org, p2, cm, "DEMO_Conditions_of_Contract_WH.pdf", D.contract_pdf(),
                     title="Conditions of Contract — WH-02 (DEMO)", declared_type="contract")
        b2 = _upload(db, org, p2, cm, "DEMO_BOQ_WH.xlsx", D.boq_xlsx(), title="Bill of Quantities — WH-02 (DEMO)")
        hist = []
        for days_ago, title, cat, cost, ed in [
            (190, "Additional mezzanine floor instructed (VO-03)", "variation", Decimal("1250000"), None),
            (150, "Late approval of steel shop drawings", "approval_delay", Decimal("780000"), 21),
            (120, "Unforeseen rock encountered in foundation excavation", "unforeseen_condition", Decimal("520000"), 10),
        ]:
            d0 = today - timedelta(days=days_ago)
            instr = _upload(db, org, p2, pm, f"DEMO_WH_record_{days_ago}.pdf", D.letter_pdf([
                f"Date: {d0:%d %B %Y}", "From: The Engineer (DEMO)", f"Subject: {title}",
                "You are hereby instructed / we record the following event for the Works.", title]),
                title=f"Engineer's record — {title} (DEMO)", declared_type="site_instruction" if cat == "variation" else "letter",
                author_party="engineer", doc_date=d0)
            notice = _upload(db, org, p2, cm, f"DEMO_WH_notice_{days_ago}.pdf", D.letter_pdf([
                f"Date: {d0 + timedelta(days=9):%d %B %Y}", "From: The Contractor (DEMO)",
                f"Subject: Notice of claim - {title}", "We hereby give notice of claim under Sub-Clause 20.1."]),
                title=f"Contractor's notice — {title} (DEMO)", declared_type="notice", author_party="contractor",
                doc_date=d0 + timedelta(days=9))
            extra = []
            if cat == "approval_delay":
                extra.append(_upload(db, org, p2, pm, f"DEMO_WH_programme_{days_ago}.pdf", D.letter_pdf([
                    "DELAY ANALYSIS - programme update (DEMO)", "Critical path impacted by late shop drawing approval: 21 days.",
                    "Baseline schedule vs updated programme attached."]), title="Programme delay analysis (DEMO)",
                    declared_type="programme", doc_date=d0 + timedelta(days=30)))
                extra.append(_upload(db, org, p2, pm, f"DEMO_WH_overheads_{days_ago}.pdf", D.letter_pdf([
                    "SITE OVERHEAD COST REPORT (DEMO)", "Time-related site overheads: EGP 37,150 per day."]),
                    title="Site overhead cost records (DEMO)", declared_type="cost_record", doc_date=d0 + timedelta(days=35)))
            else:
                extra.append(_upload(db, org, p2, pm, f"DEMO_WH_cost_{days_ago}.pdf", D.letter_pdf([
                    "COST REPORT (DEMO)", f"Cost records for: {title}", "Timesheets, delivery notes and invoices attached."]),
                    title=f"Cost records — {title} (DEMO)", declared_type="cost_record", doc_date=d0 + timedelta(days=20)))
                extra.append(_upload(db, org, p2, site, f"DEMO_WH_daily_{days_ago}.txt", D.daily_report_txt(
                    d0 + timedelta(days=4), f"Work done today related to: {title}."), title=f"Daily report — {title} (DEMO)",
                    author_party="contractor", doc_date=d0 + timedelta(days=4)))
            ev = _event(db, org, p2, pm, title=title, description=f"{title}. Recorded by the project team (DEMO).",
                        category=cat, event_date=d0, docs=[instr, notice, b2, *extra], est_cost=cost, est_days=ed)
            db.commit()
            ents = discovery.run_for_event(db, ev, user_id=cm.id, today=d0 + timedelta(days=40))
            db.commit()
            fin = next(e for e in ents if e.financial_impact is not None)
            hist.append((fin, d0, cost))

        admin = _principal(users["admin"])
        outcomes = [("collected", Decimal("1100000"), Decimal("900000")), ("negotiation", None, None), ("rejected", None, None)]
        for (ent, d0, cost), (final, approved, collected) in zip(hist, outcomes, strict=True):
            save_valuation(db, ent, ValuationIn(lines=[ValuationLineIn(category="direct_work", description=ent.title[:200],
                                                                       quantity=Decimal(1), unit="LS", rate=cost,
                                                                       source_document_id=c2.id, source_note="Claim valuation (DEMO)",
                                                                       rate_basis="estimate")]), _principal(cm))
            db.flush()
            from ..models import Claim

            claim = Claim(org_id=org.id, project_id=p2.id, entitlement_id=ent.id,
                          ref=discovery.next_ref(db, Claim, p2.id, "CLM"), title=ent.title, claim_type=ent.entitlement_type,
                          stage="detected", claimed_amount=ent.financial_impact or 0, owner_id=cm.id, is_demo=True)
            db.add(claim)
            db.flush()
            for st in ["initial_review", "evidence_collection", "contractual_verification", "financial_valuation",
                       "technical_review", "legal_review", "management_approval"]:
                transition(db, claim, st, admin, "DEMO progression", on=d0 + timedelta(days=45))
            data, _, ext = claimdocs.render(db, claim, "package", "docx", "en")
            from ..models import ClaimDocument
            from ..services.storage import get_store

            key = f"{org.id}/{p2.id}/claims/{claim.id}/{claim.ref}_package_en_v1.{ext}"
            db.add(ClaimDocument(org_id=org.id, claim_id=claim.id, kind="package", fmt=ext, language="en",
                                 filename=f"{claim.ref}_package_en_v1.{ext}", storage_key=key, sha256=get_store().put(key, data),
                                 generated_by=cm.id))
            db.flush()
            transition(db, claim, "submitted", admin, "Submitted by hand to the Engineer (DEMO)", on=d0 + timedelta(days=50))
            transition(db, claim, "employer_response", admin, "Engineer's response received (DEMO)", on=d0 + timedelta(days=80))
            if final == "collected":
                transition(db, claim, "approved", admin, "Partially approved (DEMO)", approved_amount=approved, on=d0 + timedelta(days=85))
                transition(db, claim, "collected", admin, "Paid with IPC (DEMO)", collected_amount=collected, on=d0 + timedelta(days=110))
            elif final == "negotiation":
                transition(db, claim, "negotiation", admin, "Negotiation meeting scheduled (DEMO)")
            else:
                transition(db, claim, "rejected", admin, "Engineer rejected: rock considered foreseeable (DEMO)")
        db.commit()
        return {"organization": org.id, "projects": [p1.id, p2.id], "password": DEMO_PASSWORD,
                "users": [u[0] for u in USERS]}
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    if args.reset:
        with SessionLocal() as s:
            reset(s)
    print(seed())
