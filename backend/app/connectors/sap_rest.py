"""Read-only HTTP connectors: SAP S/4HANA (OData v2) and a generic JSON REST API.

* SAP S/4HANA: reads ``A_JournalEntryItemBasic`` from the released API
  ``API_JOURNALENTRYITEMBASIC_SRV`` with a communication user (HTTP basic auth). The
  password comes from ``FM_SAP_PASSWORD``. Paging follows ``d.__next``.
* Generic REST: GETs a JSON endpoint, takes the records from a configurable path, reads an
  account and an amount field per record and follows an optional next-page link. An optional
  token comes from ``FM_REST_TOKEN``.

Both map account codes to cost categories by prefix and reconcile onto the cost profile.
Not verified against live systems in this environment.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..simulation.assumptions import Baseline
from .base import ConnectorError, ConnectorResult, ReadOnlyConnector, summarise_ledger

DEFAULT_MAX_ROWS = 500_000


def dig(obj: Any, path: str) -> Any:
    """Follow a dotted path ("data.items") through nested dicts; "" returns obj itself."""
    for part in [p for p in (path or "").split(".") if p]:
        if not isinstance(obj, dict) or part not in obj:
            return None
        obj = obj[part]
    return obj


class _HttpLedgerConnector(ReadOnlyConnector):
    implementation = "adapter"
    required: tuple[str, ...] = ()

    def __init__(self, config: dict[str, Any] | None = None, secrets: dict[str, str] | None = None,
                 transport: httpx.BaseTransport | None = None):
        super().__init__(config, secrets)
        self._transport = transport

    # -- subclass hooks
    def _check_secret(self) -> None: ...
    def _client(self) -> httpx.Client: ...
    def _first_request(self) -> tuple[str, dict[str, str] | None]: ...
    def _page(self, body: Any) -> tuple[list[dict[str, Any]], str | None]: ...
    def _line(self, rec: dict[str, Any]) -> tuple[str, float]: ...

    def _check_config(self) -> None:
        missing = [k for k in self.required if not str(self.config.get(k) or "").strip()]
        if missing:
            raise ConnectorError(f"Missing settings: {', '.join(missing)}")
        self._check_secret()

    def _get(self, client: httpx.Client, url: str, params: dict[str, str] | None) -> Any:
        r = client.get(url, params=params)
        if r.status_code != 200:
            raise ConnectorError(f"{self.kind} request failed ({r.status_code}): {r.text[:300]}")
        try:
            return r.json()
        except ValueError as exc:
            raise ConnectorError(f"{self.kind} did not return JSON") from exc

    def _read_all(self, limit: int | None = None) -> list[dict[str, Any]]:
        max_rows = int(self.config.get("max_rows", DEFAULT_MAX_ROWS))
        rows: list[dict[str, Any]] = []
        url, params = self._first_request()
        with self._client() as client:
            next_url: str | None = url
            while next_url:
                records, following = self._page(self._get(client, next_url, params))
                rows.extend(records)
                if limit and len(rows) >= limit:
                    return rows[:limit]
                if len(rows) > max_rows:
                    raise ConnectorError(f"More than {max_rows} ledger lines; narrow the period or the filter")
                # next links already carry the query; relative links resolve against the current page
                next_url, params = (str(httpx.URL(next_url).join(following)) if following else None), None
        return rows

    def test_connection(self) -> dict[str, Any]:
        try:
            self._check_config()
            sample = self._read_all(limit=1)
            return {"ok": True, "verified_live": True, "message": f"Connected; ledger readable ({len(sample)} sample row)"}
        except (ConnectorError, httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            return {"ok": False, "verified_live": False, "message": str(exc)}

    def fetch_cost_profile(self, base: Baseline | None = None) -> ConnectorResult:
        self._check_config()
        try:
            rows = self._read_all()
        except httpx.HTTPError as exc:
            raise ConnectorError(f"{self.kind} request failed: {exc}") from exc
        return summarise_ledger(self.kind, [self._line(r) for r in rows], self.config, base, len(rows))


class SAPConnector(_HttpLedgerConnector):
    kind = "sap"
    secret_env = ("PASSWORD",)
    required = ("base_url", "username", "company_code", "date_from", "date_to")
    SERVICE = "/sap/opu/odata/sap/API_JOURNALENTRYITEMBASIC_SRV/A_JournalEntryItemBasic"

    def _check_secret(self) -> None:
        if not self.secrets.get("password"):
            raise ConnectorError("Password not set (environment variable FM_SAP_PASSWORD)")

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=float(self.config.get("timeout_s", 60)), transport=self._transport,
                            auth=(self.config["username"], self.secrets["password"]),
                            headers={"Accept": "application/json"})

    def _first_request(self) -> tuple[str, dict[str, str] | None]:
        base = str(self.config["base_url"]).rstrip("/")
        if not base.startswith("https://"):
            raise ConnectorError("base_url must be an https:// SAP S/4HANA URL")
        c = self.config
        flt = (f"CompanyCode eq '{c['company_code']}' and Ledger eq '{c.get('ledger') or '0L'}' and "
               f"PostingDate ge datetime'{c['date_from']}T00:00:00' and PostingDate le datetime'{c['date_to']}T23:59:59'")
        params = {"$format": "json", "$select": "GLAccount,AmountInCompanyCodeCurrency", "$filter": flt}
        if client_no := str(c.get("sap_client") or "").strip():
            params["sap-client"] = client_no
        return base + self.SERVICE, params

    def _page(self, body: Any) -> tuple[list[dict[str, Any]], str | None]:
        d = body.get("d", {}) if isinstance(body, dict) else {}
        return list(d.get("results", [])), d.get("__next")

    def _line(self, rec: dict[str, Any]) -> tuple[str, float]:
        code = str(rec.get("GLAccount") or "")
        if self.config.get("strip_leading_zeros", True):
            code = code.lstrip("0")  # SAP pads G/L accounts to 10 digits: 0061000000 -> 61000000
        return code, float(rec.get("AmountInCompanyCodeCurrency") or 0)


class RestConnector(_HttpLedgerConnector):
    kind = "rest"
    secret_env = ("TOKEN",)
    secret_optional = True
    required = ("url", "account_field", "amount_field")

    def _client(self) -> httpx.Client:
        headers = {"Accept": "application/json"}
        if token := self.secrets.get("token"):
            scheme = str(self.config.get("auth_scheme", "Bearer")).strip()
            headers[str(self.config.get("auth_header") or "Authorization")] = f"{scheme} {token}".strip()
        return httpx.Client(timeout=float(self.config.get("timeout_s", 60)), transport=self._transport, headers=headers)

    def _first_request(self) -> tuple[str, dict[str, str] | None]:
        url = str(self.config["url"])
        if not url.startswith(("https://", "http://")):
            raise ConnectorError("url must be an http(s) URL")
        return url, None

    def _page(self, body: Any) -> tuple[list[dict[str, Any]], str | None]:
        records = dig(body, str(self.config.get("records_path") or ""))
        if not isinstance(records, list):
            raise ConnectorError(f"No list of records at path '{self.config.get('records_path') or '(root)'}'")
        nxt = dig(body, str(self.config["next_field"])) if self.config.get("next_field") else None
        return [r for r in records if isinstance(r, dict)], (str(nxt) if nxt else None)

    def _line(self, rec: dict[str, Any]) -> tuple[str, float]:
        return str(dig(rec, self.config["account_field"]) or ""), float(dig(rec, self.config["amount_field"]) or 0)
