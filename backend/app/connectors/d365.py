"""Microsoft Dynamics 365 read-only connectors (OData v4, Microsoft Entra ID client credentials).

* Finance & Operations: reads general-ledger lines from the ``GeneralJournalAccountEntries``
  data entity on the environment URL (``https://<env>.operations.dynamics.com/data``).
* Business Central: reads ``generalLedgerEntries`` from the standard API v2.0.

Both authenticate as an Entra ID app registration (client id + client secret, token scope
``<resource>/.default``), follow ``@odata.nextLink`` paging, map ledger account codes to cost
categories by longest prefix, and reconcile onto the canonical cost profile.

The client secret is read from the environment (``FM_D365_FO_CLIENT_SECRET`` /
``FM_D365_BC_CLIENT_SECRET``), never from the stored config. Entity and field names follow
Microsoft's documented defaults and are overridable in config, because F&O deployments
frequently expose customised entities. Not verified against a live tenant in this environment.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from ..simulation.assumptions import Baseline
from .base import ConnectorError, ConnectorResult, ReadOnlyConnector, reconcile

DEFAULT_AUTHORITY = "https://login.microsoftonline.com"
DEFAULT_MAX_ROWS = 500_000


def bucket_by_prefix(lines: Iterable[tuple[str, float]], mapping: dict[str, str]) -> tuple[dict[str, float], dict[str, float]]:
    """Sum amounts per category using the longest matching account prefix; return (totals, ignored)."""
    if not mapping:
        raise ConnectorError("account_mapping is required (account code prefix -> cost category)")
    prefixes = sorted(mapping, key=len, reverse=True)
    totals: dict[str, float] = {}
    ignored: dict[str, float] = {}
    for code, amount in lines:
        code = (code or "").strip()
        p = next((p for p in prefixes if code.startswith(p)), None)
        if p is None:
            ignored[code] = ignored.get(code, 0.0) + amount
        else:
            totals[mapping[p]] = totals.get(mapping[p], 0.0) + amount
    return totals, ignored


class _EntraODataConnector(ReadOnlyConnector):
    implementation = "adapter"
    secret_env = ("CLIENT_SECRET",)
    required: tuple[str, ...] = ()

    def __init__(self, config: dict[str, Any] | None = None, secrets: dict[str, str] | None = None,
                 transport: httpx.BaseTransport | None = None):
        super().__init__(config, secrets)
        self._transport = transport

    # -- subclass hooks
    def _scope(self) -> str: ...
    def _collection_url(self) -> str: ...
    def _query(self) -> dict[str, str]: ...
    def _line(self, rec: dict[str, Any]) -> tuple[str, float]: ...

    # -- shared plumbing
    def _check_config(self) -> None:
        missing = [k for k in self.required if not str(self.config.get(k) or "").strip()]
        if missing:
            raise ConnectorError(f"Missing settings: {', '.join(missing)}")
        if not self.secrets.get("client_secret"):
            raise ConnectorError(f"Client secret not set (environment variable FM_{self.kind.upper()}_CLIENT_SECRET)")

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=float(self.config.get("timeout_s", 30)), transport=self._transport)

    def _token(self, client: httpx.Client) -> str:
        authority = str(self.config.get("authority") or DEFAULT_AUTHORITY).rstrip("/")
        r = client.post(f"{authority}/{self.config['tenant_id']}/oauth2/v2.0/token", data={
            "grant_type": "client_credentials", "client_id": self.config["client_id"],
            "client_secret": self.secrets["client_secret"], "scope": self._scope()})
        if r.status_code != 200:
            try:
                detail = r.json().get("error_description") or r.json().get("error") or r.text
            except ValueError:
                detail = r.text
            raise ConnectorError(f"Entra ID token request failed ({r.status_code}): {str(detail)[:300]}")
        return r.json()["access_token"]

    def _get(self, client: httpx.Client, token: str, url: str, params: dict[str, str] | None) -> dict[str, Any]:
        r = client.get(url, params=params, headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                                                     "OData-MaxVersion": "4.0", "OData-Version": "4.0"})
        if r.status_code != 200:
            try:
                detail = r.json().get("error", {}).get("message") or r.text
            except (ValueError, AttributeError):
                detail = r.text
            raise ConnectorError(f"{self.kind} OData request failed ({r.status_code}): {str(detail)[:300]}")
        return r.json()

    def _read_all(self, client: httpx.Client, token: str) -> list[dict[str, Any]]:
        max_rows = int(self.config.get("max_rows", DEFAULT_MAX_ROWS))
        rows: list[dict[str, Any]] = []
        url: str | None = self._collection_url()
        params: dict[str, str] | None = self._query()
        while url:
            page = self._get(client, token, url, params)
            rows.extend(page.get("value", []))
            if len(rows) > max_rows:
                raise ConnectorError(f"More than {max_rows} ledger lines; narrow the date range or legal entity")
            url, params = page.get("@odata.nextLink"), None  # nextLink already carries the query
        return rows

    def test_connection(self) -> dict[str, Any]:
        try:
            self._check_config()
            with self._client() as client:
                token = self._token(client)
                page = self._get(client, token, self._collection_url(), {**self._query(), "$top": "1"})
            return {"ok": True, "verified_live": True,
                    "message": f"Authenticated; {self.config.get('entity_set') or 'ledger'} readable "
                               f"({len(page.get('value', []))} sample row)"}
        except (ConnectorError, httpx.HTTPError, KeyError, ValueError) as exc:
            return {"ok": False, "verified_live": False, "message": str(exc)}

    def fetch_cost_profile(self, base: Baseline | None = None) -> ConnectorResult:
        self._check_config()
        try:
            with self._client() as client:
                rows = self._read_all(client, self._token(client))
        except httpx.HTTPError as exc:
            raise ConnectorError(f"{self.kind} request failed: {exc}") from exc
        divisor = float(self.config.get("amount_divisor", 1e6))  # source currency units -> EGP millions
        lines = [(code, amt / divisor) for code, amt in (self._line(r) for r in rows)]
        totals, ignored = bucket_by_prefix(lines, self.config.get("account_mapping") or {})
        profile, rec = reconcile(totals, base or Baseline())
        rec.update({"ignored_accounts": len(ignored), "ignored_total": round(sum(ignored.values()), 4),
                    "period": [self.config.get("date_from"), self.config.get("date_to")]})
        return ConnectorResult(profile=profile, reconciliation=rec, rows_read=len(rows), source=self.kind,
                               verified_live=True)


class D365FinanceOperationsConnector(_EntraODataConnector):
    kind = "d365_fo"
    required = ("environment_url", "tenant_id", "client_id", "date_from", "date_to")

    def _base(self) -> str:
        url = str(self.config.get("environment_url") or "").rstrip("/")
        if not url.startswith("https://"):
            raise ConnectorError("environment_url must be an https:// Dynamics 365 F&O URL")
        return url

    def _scope(self) -> str:
        return f"{self._base()}/.default"

    def _collection_url(self) -> str:
        return f"{self._base()}/data/{self.config.get('entity_set') or 'GeneralJournalAccountEntries'}"

    def _fields(self) -> tuple[str, str, str]:
        c = self.config
        return (c.get("date_field") or "AccountingDate", c.get("account_field") or "LedgerAccount",
                c.get("amount_field") or "AccountingCurrencyAmount")

    def _query(self) -> dict[str, str]:
        date_f, acct_f, amt_f = self._fields()
        flt = (f"{date_f} ge {self.config['date_from']}T00:00:00Z and "
               f"{date_f} le {self.config['date_to']}T23:59:59Z")
        q = {"$select": f"{acct_f},{amt_f}", "$filter": flt}
        if le := str(self.config.get("legal_entity") or "").strip():
            q["$filter"] += f" and dataAreaId eq '{le.replace(chr(39), '')}'"
            q["cross-company"] = "true"
        return q

    def _line(self, rec: dict[str, Any]) -> tuple[str, float]:
        _, acct_f, amt_f = self._fields()
        # LedgerAccount is the display value "610100-001-..."; the main account is the first segment.
        code = str(rec.get(acct_f) or "").split(str(self.config.get("segment_delimiter") or "-"))[0]
        return code, float(rec.get(amt_f) or 0.0)


class D365BusinessCentralConnector(_EntraODataConnector):
    kind = "d365_bc"
    required = ("tenant_id", "client_id", "environment", "company_id", "date_from", "date_to")

    def _scope(self) -> str:
        return "https://api.businesscentral.dynamics.com/.default"

    def _collection_url(self) -> str:
        base = str(self.config.get("api_base") or "https://api.businesscentral.dynamics.com").rstrip("/")
        c = self.config
        return (f"{base}/v2.0/{c['tenant_id']}/{c['environment']}/api/v2.0/"
                f"companies({c['company_id']})/generalLedgerEntries")

    def _query(self) -> dict[str, str]:
        c = self.config
        return {"$select": "accountNumber,debitAmount,creditAmount",
                "$filter": f"postingDate ge {c['date_from']} and postingDate le {c['date_to']}"}

    def _line(self, rec: dict[str, Any]) -> tuple[str, float]:
        return str(rec.get("accountNumber") or ""), float(rec.get("debitAmount") or 0) - float(rec.get("creditAmount") or 0)
