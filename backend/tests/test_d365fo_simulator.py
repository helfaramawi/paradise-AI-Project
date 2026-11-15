"""The D365 F&O connector end to end against the local F&O simulator (tools/d365fo-simulator).

The simulator is served in-process for the protocol tests, and once over real HTTPS to prove that
FM_D365_CA_BUNDLE makes the connector trust a private CA without turning certificate checks off.
"""

import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.connectors.base import ConnectorError
from app.connectors.d365 import D365FinanceOperationsConnector
from app.simulation.assumptions import Baseline

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "d365fo-simulator"))
from d365fo_sim.arabic_data import FM_ACCOUNT_MAPPING, generate  # noqa: E402
from d365fo_sim.server import Settings, create_app  # noqa: E402

SIM = "https://d365fo-sim:8443"
DATA = generate()
S = Settings(page_size=500, public_urls=[SIM])


def config(**kw):
    return {"environment_url": SIM, "authority": SIM, "tenant_id": S.tenant_id, "client_id": S.client_id,
            "legal_entity": "EGMF", "date_from": "2025-11-01", "date_to": "2026-10-31",
            "account_mapping": FM_ACCOUNT_MAPPING, **kw}


class _InProcess(httpx.BaseTransport):
    """Sends the connector's requests to the simulator app in-process (no network, no TLS)."""

    def __init__(self, app):
        self.client = TestClient(app, base_url=SIM)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        r = self.client.request(request.method, str(request.url), headers=request.headers, content=request.read())
        headers = {k: v for k, v in r.headers.items() if k.lower() not in ("content-length", "content-encoding")}
        return httpx.Response(r.status_code, headers=headers, content=r.content)


def transport(settings: Settings = S):
    return _InProcess(create_app(settings, DATA))


def expected(company: str, date_from: str = "2025-11-01", date_to: str = "2026-10-31") -> tuple[int, dict[str, float]]:
    rows = [e for e in DATA.gl_entries if e["dataAreaId"] == company and date_from <= e["AccountingDate"][:10] <= date_to]
    tot: dict[str, float] = {}
    for e in rows:
        p = max((p for p in FM_ACCOUNT_MAPPING if e["MainAccount"].startswith(p)), key=len, default=None)
        if p:
            tot[FM_ACCOUNT_MAPPING[p]] = tot.get(FM_ACCOUNT_MAPPING[p], 0.0) + e["AccountingCurrencyAmount"] / 1e6
    return len(rows), tot


def test_sync_reads_every_page_and_maps_arabic_ledger():
    res = D365FinanceOperationsConnector(config(), {"client_secret": S.client_secret}, transport=transport()) \
        .fetch_cost_profile(Baseline())
    n, tot = expected("egmf")
    assert n > S.page_size  # the connector had to follow @odata.nextLink
    assert res.rows_read == n and res.verified_live is True
    p = res.profile
    assert p["personnel_cost"] == pytest.approx(tot["personnel"], abs=1e-3)
    assert p["software_cost"] == pytest.approx(tot["software"], abs=1e-3)
    assert p["infrastructure_cost"] == pytest.approx(tot["infrastructure"], abs=1e-3)
    assert 100 < p["annual_opex"] < 160  # EGP millions, about the Baseline's size
    rec = res.reconciliation
    assert rec["status"] == "ok" and len(rec["mapped_fields"]) == 7
    assert rec["ignored_accounts"] > 0  # balance-sheet, revenue and cost-of-sales accounts are left out


def test_legal_entity_and_default_company():
    t = transport()
    other = D365FinanceOperationsConnector(config(legal_entity="EGHS"), {"client_secret": S.client_secret}, transport=t) \
        .fetch_cost_profile(Baseline())
    assert other.rows_read == expected("eghs")[0]
    # Without legal_entity F&O answers for the user's default company only (no cross-company query).
    default = D365FinanceOperationsConnector(config(legal_entity=""), {"client_secret": S.client_secret}, transport=t) \
        .fetch_cost_profile(Baseline())
    assert default.rows_read == expected("egmf")[0]


def test_sign_in_and_query_errors_are_reported():
    def check(cfg, secret=S.client_secret):
        return D365FinanceOperationsConnector(cfg, {"client_secret": secret}, transport=transport()).test_connection()

    assert check(config())["ok"] is True
    assert "AADSTS7000215" in check(config(), secret="wrong")["message"]
    assert "AADSTS700016" in check(config(client_id="00000000-0000-0000-0000-000000000000"))["message"]
    assert "AADSTS500011" in check(config(environment_url="https://other.operations.dynamics.com"))["message"]
    r = check(config(amount_field="Amount"))
    assert r["ok"] is False and "Could not find a property named 'Amount'" in r["message"]


def test_ca_bundle_setting(monkeypatch, tmp_path):
    monkeypatch.setenv("FM_D365_CA_BUNDLE", str(tmp_path / "missing.pem"))
    r = D365FinanceOperationsConnector(config(), {"client_secret": S.client_secret}).test_connection()
    assert r["ok"] is False and "does not exist" in r["message"]
    (tmp_path / "bad.pem").write_text("not a certificate")
    monkeypatch.setenv("FM_D365_CA_BUNDLE", str(tmp_path / "bad.pem"))
    with pytest.raises(ConnectorError, match="not a valid PEM"):
        D365FinanceOperationsConnector(config(), {"client_secret": S.client_secret}).fetch_cost_profile(Baseline())


def test_real_https_with_private_ca(monkeypatch, tmp_path):
    pytest.importorskip("cryptography")
    import uvicorn
    from d365fo_sim.run import ensure_certificates

    crt, key = ensure_certificates(tmp_path)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    url = f"https://localhost:{port}"
    server = uvicorn.Server(uvicorn.Config(create_app(Settings(public_urls=[url]), DATA), host="127.0.0.1", port=port,
                                           ssl_certfile=str(crt), ssl_keyfile=str(key), log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        cfg = config(environment_url=url, authority=url)
        monkeypatch.delenv("FM_D365_CA_BUNDLE", raising=False)
        untrusted = D365FinanceOperationsConnector(cfg, {"client_secret": S.client_secret}).test_connection()
        assert untrusted["ok"] is False and "CERTIFICATE_VERIFY_FAILED" in untrusted["message"]
        monkeypatch.setenv("FM_D365_CA_BUNDLE", str(tmp_path / "ca.pem"))
        trusted = D365FinanceOperationsConnector(cfg, {"client_secret": S.client_secret}).test_connection()
        assert trusted["ok"] is True, trusted["message"]
    finally:
        server.should_exit = True
        th.join(timeout=5)


def test_odata_queries_and_browser_page():
    c = TestClient(create_app(S, DATA), base_url=SIM)
    tok = c.post(f"/{S.tenant_id}/oauth2/v2.0/token", data={
        "grant_type": "client_credentials", "client_id": S.client_id, "client_secret": S.client_secret,
        "scope": f"{SIM}/.default"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert c.get("/data/CustomersV3").status_code == 401
    r = c.get("/data/CustomersV3", headers=h, params={
        "$filter": "AddressCity eq 'بورسعيد' and CreditLimit ge 500000", "$select": "CustomerAccount,OrganizationName",
        "$orderby": "CustomerAccount desc", "$count": "true", "cross-company": "true"}).json()
    want = [x for x in DATA.customers if x["AddressCity"] == "بورسعيد" and x["CreditLimit"] >= 500000]
    assert r["@odata.count"] == len(want) and set(r["value"][0]) == {"CustomerAccount", "OrganizationName"}
    assert [v["CustomerAccount"] for v in r["value"]] == sorted((v["CustomerAccount"] for v in r["value"]), reverse=True)
    assert c.get("/data/CustomersV3", headers=h, params={"$filter": "CreditLimit gt 1 or CreditLimit lt 0"}).status_code == 400
    assert c.get("/data/Nope", headers=h).status_code == 404
    assert "MainAccount" in c.get("/data/$metadata", headers=h).text
    page = c.get("/").text
    assert "شركة المستقبل للصناعات الغذائية" in page and S.client_id in page
    assert "الرواتب" in c.get("/browse/MainAccounts").text


def test_odata_explorer_page():
    c = TestClient(create_app(S, DATA), base_url=SIM)
    page = c.get("/explorer").text
    assert S.tenant_id in page and S.client_id in page and S.client_secret not in page
    assert page.count('class="preset"') == 7 and "$metadata" in page
    assert "/explorer" in c.get("/").text
