"""SAP S/4HANA, generic REST and SQL connectors (mocked HTTP; a real SQLite database for SQL)."""

import base64
import os
import sqlite3

import httpx
import pytest

from app.connectors.base import ConnectorError
from app.connectors.sap_rest import RestConnector, SAPConnector, dig
from app.connectors.sql_source import SQLConnector

MAPPING = {"61": "personnel", "62": "contractors", "63": "software"}
PERIOD = {"date_from": "2026-01-01", "date_to": "2026-12-31"}


def test_dig_follows_dotted_paths():
    assert dig({"a": {"b": [1]}}, "a.b") == [1]
    assert dig({"a": 1}, "") == {"a": 1}
    assert dig({"a": 1}, "x.y") is None


# ---------------------------------------------------------------- SAP
def sap_config(**kw):
    return {"base_url": "https://my123.s4hana.ondemand.com", "username": "COMM_USER", "company_code": "1010",
            "sap_client": "100", "account_mapping": MAPPING, **PERIOD, **kw}


def test_sap_reads_journal_items_with_paging_and_basic_auth():
    seen: list[httpx.Request] = []
    page2 = "https://my123.s4hana.ondemand.com/sap/opu/odata/sap/API_JOURNALENTRYITEMBASIC_SRV/A_JournalEntryItemBasic?$skiptoken=2"

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if "$skiptoken" in str(req.url):
            return httpx.Response(200, json={"d": {"results": [
                {"GLAccount": "0063100000", "AmountInCompanyCodeCurrency": "12000000.00"},
                {"GLAccount": "0011000000", "AmountInCompanyCodeCurrency": "5000000.00"}]}})
        return httpx.Response(200, json={"d": {"results": [
            {"GLAccount": "0061000000", "AmountInCompanyCodeCurrency": "40000000.00"},
            {"GLAccount": "0062000000", "AmountInCompanyCodeCurrency": "15000000.00"}], "__next": page2}})

    res = SAPConnector(sap_config(), {"password": "pw"}, transport=httpx.MockTransport(handler)).fetch_cost_profile()
    first = seen[0]
    assert first.url.path.endswith("/API_JOURNALENTRYITEMBASIC_SRV/A_JournalEntryItemBasic")
    flt = first.url.params["$filter"]
    assert "CompanyCode eq '1010'" in flt and "Ledger eq '0L'" in flt and "datetime'2026-01-01T00:00:00'" in flt
    assert first.url.params["sap-client"] == "100" and first.url.params["$format"] == "json"
    assert first.headers["Authorization"] == "Basic " + base64.b64encode(b"COMM_USER:pw").decode()
    assert len(seen) == 2 and res.rows_read == 4
    p = res.profile
    assert (p["personnel_cost"], p["contractor_cost"], p["software_cost"]) == (40, 15, 12)
    assert res.reconciliation["ignored_accounts"] == 1  # 11000000 (balance sheet) not mapped


def test_sap_reports_missing_password_and_http_errors():
    r = SAPConnector(sap_config(), {}).test_connection()
    assert r["ok"] is False and "FM_SAP_PASSWORD" in r["message"]
    bad = httpx.MockTransport(lambda req: httpx.Response(401, text="Unauthorized"))
    r = SAPConnector(sap_config(), {"password": "x"}, transport=bad).test_connection()
    assert r["ok"] is False and "401" in r["message"]
    ok = httpx.MockTransport(lambda req: httpx.Response(200, json={"d": {"results": [{"GLAccount": "1"}]}}))
    assert SAPConnector(sap_config(), {"password": "x"}, transport=ok).test_connection()["ok"] is True


# ---------------------------------------------------------------- REST
def test_rest_reads_nested_records_follows_relative_next_and_sends_token():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.params.get("page") == "2":
            return httpx.Response(200, json={"data": {"items": [{"gl": {"code": "6300"}, "value": 7_000_000}]}})
        return httpx.Response(200, json={"data": {"items": [{"gl": {"code": "6100"}, "value": 30_000_000}]},
                                         "links": {"next": "/ledger?page=2"}})

    cfg = {"url": "https://erp.example.com/ledger?year=2026", "records_path": "data.items", "account_field": "gl.code",
           "amount_field": "value", "next_field": "links.next", "account_mapping": MAPPING}
    res = RestConnector(cfg, {"token": "t0k"}, transport=httpx.MockTransport(handler)).fetch_cost_profile()
    assert seen[0].headers["Authorization"] == "Bearer t0k"
    assert str(seen[1].url) == "https://erp.example.com/ledger?page=2"
    assert res.profile["personnel_cost"] == 30 and res.profile["software_cost"] == 7


def test_rest_works_without_token_and_reports_bad_path():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"rows": []})

    c = RestConnector({"url": "https://x.example.com/l", "records_path": "data", "account_field": "a",
                       "amount_field": "b"}, {}, transport=httpx.MockTransport(handler))
    r = c.test_connection()
    assert r["ok"] is False and "No list of records" in r["message"]
    c.config["records_path"] = "rows"
    assert c.test_connection()["ok"] is True
    assert "Authorization" not in seen[-1].headers


# ---------------------------------------------------------------- SQL
@pytest.fixture()
def ledger_db(tmp_path):
    path = tmp_path / "erp.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE gl_lines (account TEXT, amount REAL, posted DATE)")
    con.executemany("INSERT INTO gl_lines VALUES (?, ?, ?)", [
        ("6100", 25e6, "2026-02-01"), ("6100", 15e6, "2026-08-01"), ("6200", 9e6, "2026-03-15"),
        ("6300", 4e6, "2025-12-31"),  # outside the period
        ("1100", 50e6, "2026-05-05")])  # balance sheet -> ignored
    con.commit()
    con.close()
    return str(path)


def sql_config(db, **kw):
    return {"dialect": "sqlite", "database": db, "table": "gl_lines", "account_column": "account",
            "amount_column": "amount", "date_column": "posted", "account_mapping": MAPPING, **PERIOD, **kw}


def test_sql_aggregates_by_account_within_period(ledger_db):
    res = SQLConnector(sql_config(ledger_db)).fetch_cost_profile()
    assert res.rows_read == 3  # grouped: 6100, 6200, 1100 (6300 is outside the period)
    assert res.profile["personnel_cost"] == 40 and res.profile["contractor_cost"] == 9
    assert res.reconciliation["ignored_accounts"] == 1 and res.reconciliation["ignored_total"] == 50
    assert SQLConnector(sql_config(ledger_db)).test_connection()["ok"] is True


def test_sql_rejects_injection_and_reports_missing_settings(ledger_db):
    with pytest.raises(ConnectorError, match="plain identifier"):
        SQLConnector(sql_config(ledger_db, table="gl_lines; DROP TABLE gl_lines")).fetch_cost_profile()
    with pytest.raises(ConnectorError, match="plain identifier"):
        SQLConnector(sql_config(ledger_db, amount_column="amount) FROM x --")).fetch_cost_profile()
    r = SQLConnector(sql_config(ledger_db, dialect="postgresql")).test_connection()
    assert r["ok"] is False and "host" in r["message"]
    r = SQLConnector(sql_config(ledger_db, dialect="postgresql", host="db", username="u")).test_connection()
    assert r["ok"] is False and "FM_SQL_PASSWORD" in r["message"]
    r = SQLConnector(sql_config(ledger_db, table="missing_view")).test_connection()
    assert r["ok"] is False and "SQL query failed" in r["message"]
    con = sqlite3.connect(ledger_db)
    assert con.execute("SELECT COUNT(*) FROM gl_lines").fetchone()[0] == 5  # untouched


# ---------------------------------------------------------------- SQL Server
def test_sql_server_driver_is_installed():
    from sqlalchemy import create_engine

    c = SQLConnector({"dialect": "mssql", "host": "db", "database": "erp", "username": "u"}, {"password": "p"})
    url = c._url()
    assert url.drivername == "mssql+pymssql" and url.port == 1433  # default port
    create_engine(url)  # raises NoSuchModuleError / ModuleNotFoundError if pymssql is missing


def test_db_driver_messages_are_readable():
    from sqlalchemy.exc import OperationalError

    from app.connectors.sql_source import _db_message

    perm = OperationalError("q", {}, Exception(229, b"The SELECT permission was denied.DB-Lib error message 20018"))
    assert _db_message(perm) == "The SELECT permission was denied."
    login = OperationalError("q", {}, Exception((18456, b"Login failed for user 'u'.DB-Lib error message 20018")))
    assert _db_message(login) == "Login failed for user 'u'."
    down = OperationalError("q", {}, Exception((20009, b"DB-Lib error message 20009, severity 9:\nUnable to connect: x\n")))
    assert _db_message(down) == "Unable to connect: x"


@pytest.mark.skipif(not os.environ.get("FM_TEST_MSSQL_HOST"), reason="set FM_TEST_MSSQL_HOST/PORT/USER/PASSWORD to run")
def test_sql_server_live():
    """Live check against a SQL Server whose dbo.v_gl_expenses holds the same rows as the SQLite fixture."""
    cfg = {"dialect": "mssql", "host": os.environ["FM_TEST_MSSQL_HOST"], "port": int(os.environ.get("FM_TEST_MSSQL_PORT", 1433)),
           "database": os.environ.get("FM_TEST_MSSQL_DB", "erp"), "username": os.environ["FM_TEST_MSSQL_USER"],
           "schema": "dbo", "table": "v_gl_expenses", "account_column": "account", "amount_column": "amount",
           "date_column": "posting_date", "account_mapping": {**MAPPING, "64": "infrastructure"}, **PERIOD}
    c = SQLConnector(cfg, {"password": os.environ["FM_TEST_MSSQL_PASSWORD"]})
    assert c.test_connection()["ok"] is True
    res = c.fetch_cost_profile()
    assert res.profile["personnel_cost"] == 41 and res.reconciliation["ignored_accounts"] == 1


# ---------------------------------------------------------------- MySQL
def test_mysql_driver_is_installed():
    from sqlalchemy import create_engine

    c = SQLConnector({"dialect": "mysql", "host": "db", "database": "erp", "username": "u"}, {"password": "p"})
    url = c._url()
    assert url.drivername == "mysql+pymysql" and url.port == 3306  # default port
    create_engine(url)  # raises if PyMySQL is missing
    import cryptography  # noqa: F401  needed for MySQL 8 caching_sha2_password logins


@pytest.mark.skipif(not os.environ.get("FM_TEST_MYSQL_HOST"), reason="set FM_TEST_MYSQL_HOST/PORT/USER/PASSWORD to run")
def test_mysql_live():
    """Live check against a MySQL whose erp.v_gl_expenses holds the same rows as the SQLite fixture."""
    cfg = {"dialect": "mysql", "host": os.environ["FM_TEST_MYSQL_HOST"], "port": int(os.environ.get("FM_TEST_MYSQL_PORT", 3306)),
           "database": os.environ.get("FM_TEST_MYSQL_DB", "erp"), "username": os.environ["FM_TEST_MYSQL_USER"],
           "table": "v_gl_expenses", "account_column": "account", "amount_column": "amount",
           "date_column": "posting_date", "account_mapping": {**MAPPING, "64": "infrastructure"}, **PERIOD}
    c = SQLConnector(cfg, {"password": os.environ["FM_TEST_MYSQL_PASSWORD"]})
    assert c.test_connection()["ok"] is True
    res = c.fetch_cost_profile()
    assert res.profile["personnel_cost"] == 41 and res.reconciliation["ignored_accounts"] == 1
