"""Acceptance scenarios 1–6 and 8 (PRD §13), executed end-to-end through the HTTP API with real document
processing (PDF text, DOCX, XLSX, OCR) and the PostgreSQL database."""

import io
from datetime import date, timedelta
from decimal import Decimal

import docx
import pytest

from app.demo import documents as D

from .conftest import add_user, auth, register

TODAY = date.today()


def upload(client, token, pid, name, data, **form):
    r = client.post(f"/api/v1/projects/{pid}/documents", headers=auth(token), files={"file": (name, data)},
                    data={k: str(v) for k, v in form.items()})
    assert r.status_code == 201, r.text
    doc = r.json()
    r = client.get(f"/api/v1/documents/{doc['id']}", headers=auth(token))
    assert r.json()["status"] == "processed", r.json()
    return r.json()


@pytest.fixture(scope="module")
def world(client):
    reg = register(client, "Scenario Contractors", "admin@scenario.haqq.dev")
    admin = reg["access_token"]
    tokens = {"admin": admin}
    for role in ("contracts_manager", "cfo", "commercial_director", "legal_reviewer", "site_engineer", "ceo"):
        tokens[role] = add_user(client, admin, f"{role}@scenario.haqq.dev", role)
    r = client.post("/api/v1/projects", headers=auth(admin), json={
        "code": "SC-01", "name": "Scenario Tower", "contract_value": "100000000", "employer_name": "Employer Co",
        "engineer_name": "Engineer Co"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    site_id = client.get("/api/v1/auth/me", headers=auth(tokens["site_engineer"])).json()["id"]
    assert client.post(f"/api/v1/projects/{pid}/members", headers=auth(admin), json={"user_id": site_id}).status_code == 201
    cm = tokens["contracts_manager"]
    docs = {
        "contract": upload(client, cm, pid, "conditions.pdf", D.contract_pdf(), doc_type="contract"),
        "pc_ar": upload(client, cm, pid, "particular_ar.docx", D.particular_conditions_docx_ar()),
        "boq": upload(client, cm, pid, "boq.xlsx", D.boq_xlsx()),
        "si": upload(client, tokens["site_engineer"], pid, "SI-014.png", D.site_instruction_png(TODAY - timedelta(days=21)),
                     author_party="engineer", doc_date=(TODAY - timedelta(days=21)).isoformat()),
    }
    return {"pid": pid, "t": tokens, "docs": docs}


# ---------------------------------------------------------------- Scenario 1 — contract analysis


def test_s1_contract_analysis_with_source_references(client, world):
    t, pid = world["t"]["contracts_manager"], world["pid"]
    assert world["docs"]["contract"]["doc_type"] == "contract"
    assert world["docs"]["boq"]["doc_type"] == "boq"
    assert world["docs"]["si"]["doc_type"] == "site_instruction" and world["docs"]["si"]["ocr_pages"] == 1
    clauses = client.get(f"/api/v1/projects/{pid}/clauses", headers=auth(t)).json()
    by_num = {(c["document_id"], c["clause_number"]): c for c in clauses}
    c201 = by_num[(world["docs"]["contract"]["id"], "20.1")]
    assert c201["page_start"] == 3 and c201["document_title"]
    # the quoted text exists verbatim on the cited page of the source document
    page = client.get(f"/api/v1/documents/{c201['document_id']}/pages?page={c201['page_start']}", headers=auth(t)).json()[0]
    assert "Contractor's Claims" in page["text"]
    assert c201["time_limits"][0]["days"] == 28
    ar = [c for c in clauses if c["document_id"] == world["docs"]["pc_ar"]["id"]]
    assert any(c["language"] == "ar" and c["category"] == "delay_eot" for c in ar)
    summ = client.get(f"/api/v1/projects/{pid}/clauses/summary", headers=auth(t)).json()
    assert summ["total"] >= 20 and summ["time_limits"]
    # retrieval: semantic search & extractive Q&A (no LLM configured)
    hits = client.get(f"/api/v1/projects/{pid}/search", params={"q": "retention money release"}, headers=auth(t)).json()
    assert hits and "Retention" in hits[0]["text"]
    ans = client.post(f"/api/v1/projects/{pid}/ask", json={"question": "What is the notice period for claims?"}, headers=auth(t)).json()
    assert ans["mode"] == "extractive" and ans["passages"][0]["clause_number"] in ("20.1", "8")
    boq = client.get(f"/api/v1/projects/{pid}/boq", params={"q": "reinforcement steel"}, headers=auth(t)).json()
    assert boq[0]["item_ref"] == "B.02"


# ---------------------------------------------------------------- Scenario 2 — additional works


@pytest.fixture(scope="module")
def additional_work(client, world):
    t, pid, d = world["t"]["site_engineer"], world["pid"], world["docs"]
    r = client.post(f"/api/v1/projects/{pid}/events", headers=auth(t), json={
        "title": "Additional water tank instructed by SI-014",
        "description": "The Engineer instructed an additional underground water tank and pump room not in the BOQ.",
        "event_date": (TODAY - timedelta(days=21)).isoformat(), "responsible_party": "engineer",
        "document_ids": [d["si"]["id"], d["boq"]["id"]]})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["category"] in ("additional_work", "employer_instruction") and ev["category_source"] == "ai"
    r = client.post(f"/api/v1/events/{ev['id']}/discover", headers=auth(world["t"]["contracts_manager"]))
    assert r.status_code == 200, r.text
    return ev, r.json()


def test_s2_additional_work_explainable_finding(client, world, additional_work):
    ev, findings = additional_work
    f = findings[0]
    assert f["entitlement_type"] == "variation_payment"
    assert f["clauses"][0]["primary"] and f["clauses"][0]["clause_number"] in ("13.1", "13.3")
    # it requests missing evidence instead of declaring a valid claim
    assert f["status"] == "insufficient_evidence"
    assert "contractor_notice" in {m["code"] for m in f["evidence_missing"]}
    assert "written_instruction" in {a["code"] for a in f["evidence_available"]}
    # every explanation item about a clause/evidence carries a citation with document + page
    for item in f["explanation"]:
        if item["kind"] in ("clause", "evidence"):
            assert item["citation"]["document_id"] and item["citation"]["page"] >= 1
    assert f["financial_basis"] == "not_quantified" and f["financial_impact"] is None
    assert f["recommended_actions"]


# ---------------------------------------------------------------- Scenario 3 — delay event


def test_s3_delay_event_does_not_conclude_eot(client, world):
    t, pid = world["t"]["contracts_manager"], world["pid"]
    mom = upload(client, t, pid, "mom18.docx", D.minutes_docx(TODAY - timedelta(days=60), title="Minutes of Meeting No. 18",
                 items=["Site handover of Zone B delayed by the Employer pending utility relocation."]),
                 doc_date=(TODAY - timedelta(days=60)).isoformat(), author_party="engineer")
    letter = upload(client, t, pid, "employer_letter.pdf", D.letter_pdf(["From: the Employer", "Handover of Zone B is postponed."]),
                    doc_type="letter", author_party="employer", doc_date=(TODAY - timedelta(days=62)).isoformat())
    ev = client.post(f"/api/v1/projects/{pid}/events", headers=auth(t), json={
        "title": "Late handover of Zone B", "description": "Employer delayed site handover of Zone B.",
        "event_date": (TODAY - timedelta(days=63)).isoformat(), "category": "site_access", "est_time_impact_days": 45,
        "document_ids": [mom["id"], letter["id"]]}).json()
    findings = client.post(f"/api/v1/events/{ev['id']}/discover", headers=auth(t)).json()
    types = {f["entitlement_type"]: f for f in findings}
    eot = types["extension_of_time"]
    assert eot["status"] in ("insufficient_evidence", "requires_expert_verification")
    assert eot["status"] != "substantiated"
    assert any(a.get("code") == "no_eot_conclusion" for a in eot["assumptions"])
    assert eot["clauses"][0]["clause_number"] in ("2.1", "8.4")
    # notice provisions found in both the English GC (28 d) and the Arabic PC (21 d) → flagged ambiguous
    n = eot["notice"]["notice"]
    assert n["certainty"] == "ambiguous" and 21 in n["alternatives"] and 28 in n["alternatives"]
    # no contractor notice and the shortest period has passed → overdue + time-bar → expert verification
    assert n["status"] == "overdue"


# ---------------------------------------------------------------- Scenario 4 — missing notice / deadline


def test_s4_notice_deadline_and_uncertainty(client, world, additional_work):
    t, pid = world["t"]["contracts_manager"], world["pid"]
    ev, findings = additional_work
    n = findings[0]["notice"]["notice"]
    assert n["status"] == "due" and n["period_days"] == 28
    assert n["due_date"] == (TODAY - timedelta(days=21) + timedelta(days=28)).isoformat()
    assert n["certainty"] in ("estimated", "ambiguous")
    assert any(x["code"] == "day_type_assumed" for x in n["notes"])
    dls = client.get(f"/api/v1/projects/{pid}/deadlines", headers=auth(t)).json()
    mine = [d for d in dls if d["entitlement_id"] == findings[0]["id"] and d["deadline_type"] == "notice"]
    assert mine and mine[0]["due_date"] == n["due_date"] and mine[0]["uncertainty_notes"]
    assert mine[0]["days_left"] == 7
    res = client.post("/api/v1/deadlines/scan", headers=auth(t)).json()
    assert res["notifications"] >= 1
    notes = client.get("/api/v1/notifications", headers=auth(t)).json()
    assert any("Notice" in x["title"] for x in notes)
    assert all(x["email_status"] == "not_configured" for x in notes)


# ---------------------------------------------------------------- Scenario 5 — claim generation


def test_s5_full_journey_to_claim_package(client, world, additional_work):
    T, pid, d = world["t"], world["pid"], world["docs"]
    ev, findings = additional_work
    ent_id = findings[0]["id"]
    # contractor issues its notice → evidence complete for critical items
    notice = upload(client, T["contracts_manager"], pid, "notice_si014.pdf",
                    D.letter_pdf(["From: the Contractor", "Notice of claim - additional water tank SI-014"]),
                    doc_type="notice", author_party="contractor", doc_date=TODAY.isoformat())
    r = client.post(f"/api/v1/events/{ev['id']}/documents", headers=auth(T["contracts_manager"]), json={"document_id": notice["id"]})
    assert r.status_code == 200
    f = [x for x in client.post(f"/api/v1/events/{ev['id']}/discover", headers=auth(T["contracts_manager"])).json()
         if x["id"] == ent_id][0]
    assert f["status"] == "potential" and f["notice"]["notice"]["status"] == "given_on_time"

    # valuation: prepared by contracts manager, verified by CFO (separation of duties)
    lines = [{"category": "direct_work", "description": "RC C35 (BOQ B.01)", "quantity": "180", "unit": "m3", "rate": "4850",
              "source_document_id": d["boq"]["id"], "rate_basis": "boq_rate"},
             {"category": "direct_work", "description": "Steel (BOQ B.02)", "quantity": "18", "unit": "ton", "rate": "41500",
              "source_document_id": d["boq"]["id"], "rate_basis": "boq_rate"}]
    v = client.put(f"/api/v1/entitlements/{ent_id}/valuation", headers=auth(T["contracts_manager"]),
                   json={"lines": lines, "assumptions": ["Quantities to be agreed"]})
    assert v.status_code == 200, v.text
    assert v.json()["totals"]["gross"] == "1620000.00"
    assert client.post(f"/api/v1/entitlements/{ent_id}/valuation/verify", headers=auth(T["commercial_director"])).status_code == 200

    # cannot substantiate while a critical item is missing? (all critical items present now) → substantiated by human
    r = client.post(f"/api/v1/entitlements/{ent_id}/review", headers=auth(T["commercial_director"]),
                    json={"decision": "substantiated", "comment": "Reviewed clause 13.1 and SI-014"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "substantiated"

    claim = client.post(f"/api/v1/projects/{pid}/claims", headers=auth(T["contracts_manager"]), json={"entitlement_id": ent_id})
    assert claim.status_code == 201, claim.text
    cid = claim.json()["id"]
    assert Decimal(claim.json()["claimed_amount"]) == Decimal("1620000.00")

    # documents in EN and AR, DOCX/PDF/XLSX
    for kind, fmt, lang in [("notice", "docx", "en"), ("package", "docx", "ar"), ("package", "pdf", "en"),
                            ("package", "pdf", "ar"), ("worksheet", "xlsx", "ar")]:
        r = client.post(f"/api/v1/claims/{cid}/documents", headers=auth(T["contracts_manager"]),
                        json={"kind": kind, "fmt": fmt, "language": lang})
        assert r.status_code == 201, r.text
    detail = client.get(f"/api/v1/claims/{cid}", headers=auth(T["contracts_manager"])).json()
    pkg = next(x for x in detail["documents"] if x["kind"] == "package" and x["fmt"] == "docx" and x["language"] == "ar")
    blob = client.get(f"/api/v1/claim-documents/{pkg['id']}/download", headers=auth(T["contracts_manager"])).content
    text = "\n".join(p.text for p in docx.Document(io.BytesIO(blob)).paragraphs)
    assert "مسودة للمراجعة الداخلية" in text            # draft / not-sent banner
    assert "13.1" in text or "13.3" in text               # contractual basis cited
    assert "فهرس الأدلة" in text and "الإجمالي" in text     # evidence index + financial breakdown
    assert 'w:bidi' in docx.Document(io.BytesIO(blob)).paragraphs[0]._p.xml  # genuine RTL paragraphs
    pdf = next(x for x in detail["documents"] if x["fmt"] == "pdf")
    assert client.get(f"/api/v1/claim-documents/{pdf['id']}/download", headers=auth(T["admin"])).content[:4] == b"%PDF"

    # lifecycle with role gates; the system only records submission
    def move(token, to, **kw):
        return client.post(f"/api/v1/claims/{cid}/transition", headers=auth(token), json={"to_stage": to, **kw})
    for st in ["initial_review", "evidence_collection", "contractual_verification", "financial_valuation",
               "technical_review", "legal_review"]:
        assert move(T["contracts_manager"], st).status_code == 200, st
    assert move(T["contracts_manager"], "management_approval").status_code == 403  # needs legal review permission
    assert move(T["legal_reviewer"], "management_approval").status_code == 200
    assert move(T["contracts_manager"], "submitted").status_code == 403            # needs management approval
    assert move(T["ceo"], "submitted").status_code == 200
    assert move(T["contracts_manager"], "employer_response").status_code == 200
    assert move(T["contracts_manager"], "approved", approved_amount="2000000").status_code == 422  # > claimed
    assert move(T["contracts_manager"], "approved", approved_amount="1500000").status_code == 200
    assert move(T["contracts_manager"], "collected", collected_amount="1000000").status_code == 200
    assert move(T["contracts_manager"], "submitted").status_code == 409            # illegal transition


# ---------------------------------------------------------------- Scenario 6 — dashboard from DB


def test_s6_dashboard_matches_database(client, world):
    t = world["t"]["ceo"]
    dash = client.get("/api/v1/dashboard/executive", headers=auth(t)).json()
    k = dash["kpis"]
    assert Decimal(k["total_contract_value"]["value"]) == Decimal("100000000")
    assert Decimal(k["claims_approved"]["value"]) == Decimal("1500000")
    assert Decimal(k["cash_collected"]["value"]) == Decimal("1000000")
    assert Decimal(k["outstanding_approved"]["value"]) == Decimal("500000")
    assert k["claim_conversion_rate"]["value"] == 1.0
    # drill-down ids resolve to the same records and sums
    claims = client.get("/api/v1/claims", params={"ids": ",".join(k["claims_approved"]["ids"])}, headers=auth(t)).json()
    assert sum(Decimal(c["approved_amount"]) for c in claims) == Decimal(k["claims_approved"]["value"])
    ents = client.get("/api/v1/entitlements", params={"ids": ",".join(k["potential_entitlements"]["ids"])}, headers=auth(t)).json()
    assert sum(Decimal(e["financial_impact"] or 0) for e in ents) == Decimal(k["potential_entitlements"]["value"])
    assert dash["demo_data_present"] is False
    xl = client.get("/api/v1/reports/portfolio.xlsx", params={"lang": "ar"}, headers=auth(t))
    assert xl.status_code == 200 and xl.content[:2] == b"PK"


# ---------------------------------------------------------------- Scenario 8 — Arabic workflow


def test_s8_arabic_event_and_taxonomy(client, world):
    t, pid = world["t"]["site_engineer"], world["pid"]
    r = client.post(f"/api/v1/projects/{pid}/events", headers=auth(t), json={
        "title": "تأخر صرف المستخلص رقم ٧", "description": "لم يتم صرف المستخلص رقم ٧ في موعده وتأخر صرف المستحقات.",
        "event_date": (TODAY - timedelta(days=10)).isoformat()})
    assert r.status_code == 201 and r.json()["category"] == "payment_delay"
    tax = client.get("/api/v1/meta/taxonomy").json()
    assert tax["event_categories"]["payment_delay"]["ar"] == "تأخر الدفعات"
