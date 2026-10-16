"""Dynamics 365 connectors against a mocked Entra ID + OData endpoint (no live tenant here)."""

from urllib.parse import parse_qs

import httpx
import pytest

from app.connectors.base import ConnectorError
from app.connectors.d365 import D365BusinessCentralConnector, D365FinanceOperationsConnector, bucket_by_prefix
from app.simulation.assumptions import Baseline

FO_URL = "https://contoso.operations.dynamics.com"
MAPPING = {"61": "personnel", "62": "contractors", "63": "software", "631": "infrastructure"}


def fo_config(**kw):
    return {"environment_url": FO_URL, "tenant_id": "tid", "client_id": "cid", "legal_entity": "eg01",
            "date_from": "2026-01-01", "date_to": "2026-12-31", "account_mapping": MAPPING, **kw}


def fake_tenant(pages, seen, token_status=200):
    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.host == "login.microsoftonline.com":
            if token_status != 200:
                return httpx.Response(token_status, json={"error": "invalid_client", "error_description": "AADSTS7000215 bad secret"})
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3599})
        assert req.headers["Authorization"] == "Bearer tok"
        idx = int(req.url.params.get("page", "0"))
        body = {"value": pages[idx]}
        if idx + 1 < len(pages):
            body["@odata.nextLink"] = f"{req.url.scheme}://{req.url.host}{req.url.path}?page={idx + 1}"
        return httpx.Response(200, json=body)
    return httpx.MockTransport(handler)


def test_bucket_by_prefix_longest_match_and_ignored():
    totals, ignored = bucket_by_prefix([("6100", 1.0), ("6310", 2.0), ("6320", 3.0), ("1200", 9.0)], MAPPING)
    assert totals == {"personnel": 1.0, "infrastructure": 2.0, "software": 3.0}
    assert ignored == {"1200": 9.0}
    with pytest.raises(ConnectorError):
        bucket_by_prefix([], {})


def test_fo_fetch_pages_maps_and_reconciles():
    pages = [
        [{"LedgerAccount": "610100-001-CC1", "AccountingCurrencyAmount": 40_000_000},
         {"LedgerAccount": "620000-002", "AccountingCurrencyAmount": 15_000_000}],
        [{"LedgerAccount": "631000", "AccountingCurrencyAmount": 7_000_000},
         {"LedgerAccount": "630500", "AccountingCurrencyAmount": 11_000_000},
         {"LedgerAccount": "110000", "AccountingCurrencyAmount": 99_000_000}],  # balance sheet: ignored
    ]
    seen: list[httpx.Request] = []
    res = D365FinanceOperationsConnector(fo_config(), {"client_secret": "s"}, transport=fake_tenant(pages, seen)) \
        .fetch_cost_profile(Baseline())
    token_req = seen[0]
    form = parse_qs(token_req.content.decode())
    assert token_req.url.path == "/tid/oauth2/v2.0/token"
    assert form["grant_type"] == ["client_credentials"] and form["scope"] == [f"{FO_URL}/.default"]
    first = seen[1]
    assert first.url.path == "/data/GeneralJournalAccountEntries"
    assert "dataAreaId eq 'eg01'" in first.url.params["$filter"] and first.url.params["cross-company"] == "true"
    assert len(seen) == 3  # token + two pages via nextLink
    assert res.rows_read == 5 and res.verified_live is True
    p = res.profile
    assert (p["personnel_cost"], p["contractor_cost"], p["software_cost"], p["infrastructure_cost"]) == (40, 15, 11, 7)
    assert res.reconciliation["ignored_accounts"] == 1 and res.reconciliation["ignored_total"] == 99
    assert res.reconciliation["status"] == "ok"


def test_fo_test_connection_reports_auth_failure_and_missing_settings():
    seen: list[httpx.Request] = []
    bad = D365FinanceOperationsConnector(fo_config(), {"client_secret": "s"}, transport=fake_tenant([[]], seen, 401))
    r = bad.test_connection()
    assert r["ok"] is False and "AADSTS7000215" in r["message"]
    r = D365FinanceOperationsConnector(fo_config(tenant_id=""), {"client_secret": "s"}).test_connection()
    assert r["ok"] is False and "tenant_id" in r["message"]
    r = D365FinanceOperationsConnector(fo_config(), {}).test_connection()
    assert r["ok"] is False and "FM_D365_FO_CLIENT_SECRET" in r["message"]
    ok = D365FinanceOperationsConnector(fo_config(), {"client_secret": "s"}, transport=fake_tenant([[{}]], []))
    assert ok.test_connection()["ok"] is True


def test_fo_row_limit_enforced():
    pages = [[{"LedgerAccount": "6100", "AccountingCurrencyAmount": 1}] * 3] * 2
    c = D365FinanceOperationsConnector(fo_config(max_rows=4), {"client_secret": "s"}, transport=fake_tenant(pages, []))
    with pytest.raises(ConnectorError, match="More than 4"):
        c.fetch_cost_profile()


def test_bc_reads_general_ledger_entries_debit_minus_credit():
    seen: list[httpx.Request] = []
    pages = [[{"accountNumber": "6100", "debitAmount": 30_000_000, "creditAmount": 0},
              {"accountNumber": "6100", "debitAmount": 0, "creditAmount": 2_000_000},
              {"accountNumber": "6200", "debitAmount": 5_000_000, "creditAmount": 0}]]
    cfg = {"tenant_id": "tid", "client_id": "cid", "environment": "production", "company_id": "abc-123",
           "date_from": "2026-01-01", "date_to": "2026-12-31", "account_mapping": MAPPING}
    res = D365BusinessCentralConnector(cfg, {"client_secret": "s"}, transport=fake_tenant(pages, seen)).fetch_cost_profile()
    assert parse_qs(seen[0].content.decode())["scope"] == ["https://api.businesscentral.dynamics.com/.default"]
    assert seen[1].url.path == "/v2.0/tid/production/api/v2.0/companies(abc-123)/generalLedgerEntries"
    assert "postingDate ge 2026-01-01" in seen[1].url.params["$filter"]
    assert res.profile["personnel_cost"] == 28 and res.profile["contractor_cost"] == 5
