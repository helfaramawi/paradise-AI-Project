"""Read-only enterprise connector contract.

All connectors map source data onto the canonical cost profile (``Baseline`` fields) and
return a reconciliation report. Write operations are intentionally absent from the
interface: the MVP is read-only with respect to external systems (policy GOV-003).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from ..simulation.assumptions import Baseline

CATEGORY_TO_FIELD = {
    "personnel": "personnel_cost",
    "salaries": "personnel_cost",
    "payroll": "personnel_cost",
    "contractors": "contractor_cost",
    "external contractors": "contractor_cost",
    "software": "software_cost",
    "software licensing": "software_cost",
    "licenses": "software_cost",
    "infrastructure": "infrastructure_cost",
    "cloud": "infrastructure_cost",
    "facilities": "facilities_cost",
    "rent": "facilities_cost",
    "vendor services": "vendor_services_cost",
    "vendors": "vendor_services_cost",
    "other g&a": "other_ga_cost",
    "other": "other_ga_cost",
    "travel": "other_ga_cost",
    "training": "other_ga_cost",
}


class ConnectorResult(BaseModel):
    profile: dict[str, Any]
    reconciliation: dict[str, Any]
    rows_read: int
    source: str
    verified_live: bool


class ConnectorError(RuntimeError):
    pass


class ReadOnlyConnector(ABC):
    kind: str = "abstract"
    implementation: str = "interface_only"  # working | adapter | interface_only
    secret_env: tuple[str, ...] = ()  # FM_<KIND>_<NAME> environment variables holding secrets
    secret_optional: bool = False  # True when the connector also works without its secret

    def __init__(self, config: dict[str, Any] | None = None, secrets: dict[str, str] | None = None):
        self.config = config or {}
        self.secrets = secrets or {}

    @abstractmethod
    def test_connection(self) -> dict[str, Any]: ...

    @abstractmethod
    def fetch_cost_profile(self) -> ConnectorResult: ...


def reconcile(category_totals: dict[str, float], base: Baseline, extra: dict[str, float] | None = None) -> tuple[dict, dict]:
    """Map category totals onto the baseline and report unmapped categories and totals check."""
    mapped: dict[str, float] = {}
    unmapped: dict[str, float] = {}
    for cat, amt in category_totals.items():
        f = CATEGORY_TO_FIELD.get(cat.strip().lower())
        if f:
            mapped[f] = mapped.get(f, 0.0) + amt
        else:
            unmapped[cat] = amt
    profile = base.model_dump()
    profile.update({k: round(v, 4) for k, v in mapped.items()})
    if extra:
        profile.update(extra)
    total = sum(mapped.values())
    cost_fields = set(CATEGORY_TO_FIELD.values())
    retained = sum(profile[f] for f in cost_fields if f not in mapped)
    profile["annual_opex"] = round(total + retained, 4)
    rec = {
        "mapped_fields": sorted(mapped),
        "unmapped_categories": unmapped,
        "mapped_total": round(total, 4),
        "unmapped_total": round(sum(unmapped.values()), 4),
        "defaults_retained": sorted(set(f for f in CATEGORY_TO_FIELD.values()) - set(mapped)),
        "status": "ok" if not unmapped else "needs_mapping",
    }
    return profile, rec

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


def summarise_ledger(source: str, lines: Iterable[tuple[str, float]], config: dict[str, Any], base: Baseline | None,
                     rows_read: int) -> ConnectorResult:
    """Ledger lines (account code, amount in source currency) -> mapped, reconciled cost profile."""
    divisor = float(config.get("amount_divisor", 1e6))  # source currency units -> EGP millions
    scaled = [(code, amt / divisor) for code, amt in lines]
    totals, ignored = bucket_by_prefix(scaled, config.get("account_mapping") or {})
    profile, rec = reconcile(totals, base or Baseline())
    rec.update({"ignored_accounts": len(ignored), "ignored_total": round(sum(ignored.values()), 4),
                "period": [config.get("date_from"), config.get("date_to")]})
    return ConnectorResult(profile=profile, reconciliation=rec, rows_read=rows_read, source=source, verified_live=True)
