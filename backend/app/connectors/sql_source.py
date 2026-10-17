"""Read-only SQL connector: sums ledger amounts per account from a table or view.

The query is built with SQLAlchemy Core from validated identifiers (no free-text SQL):

    SELECT <account>, SUM(<amount>) FROM <schema.table> WHERE <date> BETWEEN :from AND :to GROUP BY <account>

On PostgreSQL the transaction is opened READ ONLY. The password comes from
``FM_SQL_PASSWORD``. PostgreSQL (psycopg2) and SQL Server (pymssql, FreeTDS bundled in the
wheel) work out of the box; MySQL needs ``pymysql`` added to the backend image. Use a database
user with SELECT rights on that one view only. Verified against PostgreSQL 16 and SQL Server 2022.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import column, create_engine, func, select, table
from sqlalchemy.engine import URL
from sqlalchemy.exc import NoSuchModuleError, SQLAlchemyError

from ..simulation.assumptions import Baseline
from .base import ConnectorError, ConnectorResult, ReadOnlyConnector, summarise_ledger

DRIVERS = {"postgresql": "postgresql+psycopg2", "mssql": "mssql+pymssql", "mysql": "mysql+pymysql", "sqlite": "sqlite"}
DEFAULT_PORTS = {"postgresql": 5432, "mssql": 1433, "mysql": 3306}
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def _ident(value: Any, what: str) -> str:
    v = str(value or "").strip()
    if not IDENT.match(v):
        raise ConnectorError(f"{what} must be a plain identifier (letters, digits, underscore)")
    return v


def _db_message(exc: SQLAlchemyError) -> str:
    """Readable driver message: pymssql returns (code, b"text DB-Lib error ...") tuples."""
    orig = getattr(exc, "orig", None) or exc
    flat: list = []
    for a in getattr(orig, "args", ()) or (orig,):
        flat.extend(a if isinstance(a, tuple) else (a,))  # login errors nest: ((18456, b"..."),)
    parts = [a.decode("utf-8", "replace") if isinstance(a, bytes) else str(a) for a in flat]
    text = next((p for p in parts if not p.isdigit()), str(orig))
    head = text.split("DB-Lib error")[0].strip()
    if not head:  # e.g. "DB-Lib error message 20009, severity 9:\nUnable to connect: Adaptive Server is unavailable..."
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("DB-Lib error")]
        head = lines[0] if lines else text
    return head[:300]


class SQLConnector(ReadOnlyConnector):
    kind = "sql"
    implementation = "adapter"
    secret_env = ("PASSWORD",)
    required = ("dialect", "database", "table", "account_column", "amount_column", "date_column", "date_from", "date_to")

    def _check_config(self) -> None:
        missing = [k for k in self.required if not str(self.config.get(k) or "").strip()]
        if missing:
            raise ConnectorError(f"Missing settings: {', '.join(missing)}")
        dialect = self.config["dialect"]
        if dialect not in DRIVERS:
            raise ConnectorError(f"dialect must be one of: {', '.join(DRIVERS)}")
        if dialect != "sqlite":
            if not str(self.config.get("host") or "").strip() or not str(self.config.get("username") or "").strip():
                raise ConnectorError("Missing settings: host, username")
            if not self.secrets.get("password"):
                raise ConnectorError("Password not set (environment variable FM_SQL_PASSWORD)")

    def _url(self) -> URL:
        c = self.config
        if c["dialect"] == "sqlite":
            return URL.create("sqlite", database=str(c["database"]))
        return URL.create(DRIVERS[c["dialect"]], username=str(c["username"]), password=self.secrets["password"],
                          host=str(c["host"]), port=int(c.get("port") or DEFAULT_PORTS[c["dialect"]]),
                          database=str(c["database"]))

    def _query(self):  # noqa: ANN202
        c = self.config
        schema = _ident(c["schema"], "schema") if str(c.get("schema") or "").strip() else None
        tbl = table(_ident(c["table"], "table"), schema=schema)
        acct = column(_ident(c["account_column"], "account_column"))
        amt = column(_ident(c["amount_column"], "amount_column"))
        dt = column(_ident(c["date_column"], "date_column"))
        start, end = date.fromisoformat(str(c["date_from"])), date.fromisoformat(str(c["date_to"]))
        return (select(acct, func.sum(amt)).select_from(tbl).where(dt >= start, dt <= end).group_by(acct))

    def _run(self, limit: int | None = None) -> list[tuple[Any, Any]]:
        self._check_config()
        try:
            engine = create_engine(self._url(), pool_pre_ping=True)
        except NoSuchModuleError as exc:
            raise ConnectorError(f"Database driver for '{self.config['dialect']}' is not installed in the backend image") from exc
        except ModuleNotFoundError as exc:
            raise ConnectorError(f"Database driver not installed: {exc.name}") from exc
        query = self._query()
        if limit:
            query = query.limit(limit)
        try:
            with engine.connect() as conn:
                if self.config["dialect"] == "postgresql":
                    conn = conn.execution_options(postgresql_readonly=True)
                rows = conn.execute(query).all()
        except SQLAlchemyError as exc:
            raise ConnectorError(f"SQL query failed: {_db_message(exc)}") from exc
        finally:
            engine.dispose()
        max_rows = int(self.config.get("max_rows", 500_000))
        if len(rows) > max_rows:
            raise ConnectorError(f"More than {max_rows} accounts returned; check the account column")
        return rows

    def test_connection(self) -> dict[str, Any]:
        try:
            sample = self._run(limit=1)
            return {"ok": True, "verified_live": True, "message": f"Connected; query runs ({len(sample)} sample row)"}
        except (ConnectorError, ValueError) as exc:
            return {"ok": False, "verified_live": False, "message": str(exc)}

    def fetch_cost_profile(self, base: Baseline | None = None) -> ConnectorResult:
        rows = self._run()
        lines = [(str(a or "").strip(), float(s or 0)) for a, s in rows]
        return summarise_ledger(self.kind, lines, self.config, base, len(rows))
