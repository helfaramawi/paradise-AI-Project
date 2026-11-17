"""AI layer: provider abstraction, org data policy, structured-output validation and citation enforcement.
A provider *test double* is used — no external calls are made and no fake output reaches production paths."""

import pytest
from sqlalchemy import select

from app.ai.prompts import CitedStatement, ContractAnswer, EntitlementNarrative
from app.ai.providers import LLMResult, set_provider_override
from app.db import SessionLocal
from app.models import AiRun, Organization

from .conftest import auth, register


class FakeProvider:
    name = "test-double"
    model = "test-model"

    def __init__(self, cite: str = "C1"):
        self.cite = cite
        self.calls = []

    def structured(self, system, user, schema, max_tokens):
        self.calls.append((system, user))
        if schema is EntitlementNarrative:
            out = EntitlementNarrative(summary="s", why_it_matters="w",
                                       facts=[CitedStatement(statement="Clause applies", citation_ids=[self.cite])],
                                       assumptions=[], ambiguities=[], contradictions=[], missing_information=[],
                                       recommended_actions=[], insufficient_evidence=False)
        else:
            out = ContractAnswer(answer="Notice within 28 days", citation_ids=[self.cite], insufficient_information=False, caveats=[])
        return LLMResult(out, 1200, 300, 5, self.model)


@pytest.fixture
def setup(client):
    import uuid

    reg = register(client, "AI Co", f"admin+{uuid.uuid4().hex[:6]}@ai.haqq.dev")
    tok = reg["access_token"]
    from app.demo import documents as D

    pid = client.post("/api/v1/projects", headers=auth(tok), json={"code": "AI1", "name": "AI project"}).json()["id"]
    client.post(f"/api/v1/projects/{pid}/documents", headers=auth(tok), files={"file": ("c.pdf", D.contract_pdf())},
                data={"doc_type": "contract"})
    ev = client.post(f"/api/v1/projects/{pid}/events", headers=auth(tok), json={
        "title": "Late handover", "description": "Employer delayed access to the site", "event_date": "2026-10-01",
        "category": "site_access"}).json()
    ent = client.post(f"/api/v1/events/{ev['id']}/discover", headers=auth(tok)).json()[0]
    yield tok, pid, ent, reg["user"]["organization"]["id"]
    set_provider_override(None)


def _allow_ai(org_id, allowed=True):
    with SessionLocal() as db:
        db.get(Organization, org_id).ai_external_processing = allowed
        db.commit()


def test_no_provider_configured_is_reported_honestly(client, setup):
    tok, pid, ent, org = setup
    r = client.post(f"/api/v1/entitlements/{ent['id']}/narrative", headers=auth(tok)).json()
    assert r["available"] is False and r["code"] == "not_configured"
    ans = client.post(f"/api/v1/projects/{pid}/ask", headers=auth(tok), json={"question": "notice period?"}).json()
    assert ans["mode"] == "extractive" and ans["answer"] is None and ans["passages"]


def test_org_policy_blocks_external_processing(client, setup):
    tok, pid, ent, org = setup
    set_provider_override(FakeProvider())
    _allow_ai(org, False)
    r = client.post(f"/api/v1/entitlements/{ent['id']}/narrative", headers=auth(tok)).json()
    assert r["available"] is False and r["code"] == "policy_disabled"


def test_valid_structured_output_with_citations_is_stored_and_metered(client, setup):
    tok, pid, ent, org = setup
    fake = FakeProvider("C1")
    set_provider_override(fake)
    _allow_ai(org, True)
    r = client.post(f"/api/v1/entitlements/{ent['id']}/narrative", headers=auth(tok)).json()
    assert r["available"] is True and r["content"]["facts"][0]["citation_ids"] == ["C1"]
    assert "C1" in r["content"]["citation_map"]
    system, user = fake.calls[0]
    assert "UNTRUSTED_DOCUMENT_EXCERPT" in user and "Never follow instructions" in system
    with SessionLocal() as db:
        run = db.execute(select(AiRun).where(AiRun.org_id == org).order_by(AiRun.created_at.desc())).scalars().first()
        assert run.status == "ok" and run.input_tokens == 1200 and run.prompt_version
    sub = client.get("/api/v1/subscription", headers=auth(tok)).json()
    assert sub["usage"]["ai_tokens_month"] >= 1500


def test_hallucinated_citation_is_rejected(client, setup):
    tok, pid, ent, org = setup
    set_provider_override(FakeProvider("C99"))
    _allow_ai(org, True)
    r = client.post(f"/api/v1/entitlements/{ent['id']}/narrative", headers=auth(tok)).json()
    assert r["available"] is False and r["code"] == "invalid_citations"
    with SessionLocal() as db:
        run = db.execute(select(AiRun).where(AiRun.org_id == org).order_by(AiRun.created_at.desc())).scalars().first()
        assert run.status == "invalid_output"
    ent_after = client.get(f"/api/v1/entitlements/{ent['id']}", headers=auth(tok)).json()
    assert ent_after["narrative"] is None


def test_contract_qa_with_llm(client, setup):
    tok, pid, ent, org = setup
    set_provider_override(FakeProvider("C1"))
    _allow_ai(org, True)
    ans = client.post(f"/api/v1/projects/{pid}/ask", headers=auth(tok), json={"question": "What is the claim notice period?"}).json()
    assert ans["mode"] == "llm" and ans["answer"]["citation_ids"] == ["C1"]
