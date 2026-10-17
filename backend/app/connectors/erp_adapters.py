"""ERP adapters.

* Odoo: implemented XML-RPC adapter (read-only). NOT verified against a live Odoo instance
  in this environment - status remains ``adapter`` until a successful test_connection.
* Dynamics 365 F&O / Business Central: OData adapters in ``d365.py`` (status ``adapter``).
* SAP S/4HANA and generic REST: HTTP adapters in ``sap_rest.py``; SQL: ``sql_source.py``.
"""

from __future__ import annotations

import xmlrpc.client
from typing import Any

from ..simulation.assumptions import Baseline
from .base import ConnectorError, ConnectorResult, ReadOnlyConnector, reconcile
from .d365 import D365BusinessCentralConnector, D365FinanceOperationsConnector
from .sap_rest import RestConnector, SAPConnector
from .sql_source import SQLConnector
from .synthetic import SyntheticERPConnector


class OdooConnector(ReadOnlyConnector):
    kind = "odoo"
    implementation = "adapter"
    secret_env = ("API_KEY",)

    def _client(self):  # noqa: ANN202
        url = (self.config.get("url") or "").rstrip("/")
        if not url.startswith(("http://", "https://")):
            raise ConnectorError("Odoo URL not configured")
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
        uid = common.authenticate(self.config.get("database"), self.config.get("username"),
                                  self.secrets.get("api_key", ""), {})
        if not uid:
            raise ConnectorError("Odoo authentication failed")
        return xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True), uid

    def test_connection(self) -> dict[str, Any]:
        try:
            _, uid = self._client()
            return {"ok": True, "message": f"Authenticated as uid {uid}", "verified_live": True}
        except (ConnectorError, OSError, xmlrpc.client.Error) as exc:
            return {"ok": False, "message": str(exc), "verified_live": False}

    def fetch_cost_profile(self, base: Baseline | None = None) -> ConnectorResult:
        models, uid = self._client()
        db, key = self.config.get("database"), self.secrets.get("api_key", "")
        mapping: dict[str, str] = self.config.get("account_mapping", {})  # account code prefix -> category
        date_from = self.config.get("date_from", "2026-01-01")
        date_to = self.config.get("date_to", "2026-12-31")
        groups = models.execute_kw(db, uid, key, "account.move.line", "read_group",
                                   [[["date", ">=", date_from], ["date", "<=", date_to], ["parent_state", "=", "posted"],
                                     ["account_id.account_type", "in", ["expense", "expense_direct_cost"]]],
                                    ["balance:sum"], ["account_id"]], {"lazy": False})
        totals: dict[str, float] = {}
        for g in groups:
            code = str(g["account_id"][1]).split(" ")[0]
            cat = next((c for p, c in mapping.items() if code.startswith(p)), f"unmapped:{code}")
            totals[cat] = totals.get(cat, 0.0) + float(g["balance"]) / 1e6
        profile, rec = reconcile(totals, base or Baseline())
        return ConnectorResult(profile=profile, reconciliation=rec, rows_read=len(groups), source="odoo",
                               verified_live=True)


REGISTRY: dict[str, type[ReadOnlyConnector]] = {
    "synthetic_erp": SyntheticERPConnector,
    "odoo": OdooConnector,
    "d365_fo": D365FinanceOperationsConnector,
    "d365_bc": D365BusinessCentralConnector,
    "sap": SAPConnector,
    "rest": RestConnector,
    "sql": SQLConnector,
}
