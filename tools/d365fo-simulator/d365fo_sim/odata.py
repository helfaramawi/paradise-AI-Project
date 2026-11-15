"""A small subset of OData v4 query options, enough to exercise real F&O clients.

Supported: ``$filter`` with comparisons (eq ne gt ge lt le) joined by ``and``, ``$select``,
``$orderby`` (one or more fields, asc/desc), ``$top``, ``$skip``, ``$count`` and server-driven
paging (``@odata.nextLink`` with ``$skiptoken``). String comparisons ignore case, as SQL Server
does in F&O. Anything else is rejected with a 400 error that names what is unsupported, so a
client never silently gets unfiltered data.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

_CMP = {"eq": lambda a, b: a == b, "ne": lambda a, b: a != b, "gt": lambda a, b: a > b,
        "ge": lambda a, b: a >= b, "lt": lambda a, b: a < b, "le": lambda a, b: a <= b}
_TERM = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s+(eq|ne|gt|ge|lt|le)\s+"
                   r"('(?:[^']|'')*'|\d{4}-\d{2}-\d{2}(?:T[0-9:.]+(?:Z|[+-]\d{2}:\d{2})?)?|-?\d+(?:\.\d+)?|true|false|null)\s*$",
                   re.IGNORECASE)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(T[0-9:.]+(Z|[+-]\d{2}:\d{2})?)?$")


class ODataError(ValueError):
    """A query the simulator cannot answer; becomes an HTTP 400 in OData error format."""


def _split_and(expr: str) -> list[str]:
    parts, buf, in_str = [], [], False
    tokens = re.split(r"(\s+and\s+|')", expr, flags=re.IGNORECASE)
    for t in tokens:
        if t == "'":
            in_str = not in_str
            buf.append(t)
        elif not in_str and re.fullmatch(r"\s+and\s+", t, re.IGNORECASE):
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(t)
    parts.append("".join(buf))
    return [p for p in parts if p.strip()]


def _literal(tok: str) -> Any:
    low = tok.lower()
    if tok.startswith("'"):
        return tok[1:-1].replace("''", "'")
    if low in ("true", "false"):
        return low == "true"
    if low == "null":
        return None
    if _DATE.match(tok):
        return _as_datetime(tok)
    return float(tok)


def _as_datetime(v: str) -> datetime:
    if len(v) == 10:
        return datetime.combine(date.fromisoformat(v), datetime.min.time(), UTC)
    dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _comparable(rec_value: Any, lit: Any) -> tuple[Any, Any]:
    if isinstance(lit, datetime) and isinstance(rec_value, str) and _DATE.match(rec_value):
        return _as_datetime(rec_value), lit
    if isinstance(lit, str) and isinstance(rec_value, str):
        return rec_value.casefold(), lit.casefold()
    if isinstance(lit, float) and isinstance(rec_value, int | float) and not isinstance(rec_value, bool):
        return float(rec_value), lit
    return rec_value, lit


def parse_filter(expr: str, fields: set[str], type_name: str) -> list[tuple[str, str, Any]]:
    if re.search(r"\b(or|not)\b|\(", expr, re.IGNORECASE):
        raise ODataError("The simulator supports $filter comparisons joined by 'and' only "
                         "(no 'or', 'not', parentheses or functions).")
    terms = []
    for part in _split_and(expr):
        m = _TERM.match(part)
        if not m:
            raise ODataError(f"Syntax error in $filter near: {part.strip()[:80]}")
        name, op, lit = m.group(1), m.group(2).lower(), m.group(3)
        if name not in fields:
            raise ODataError(f"Could not find a property named '{name}' on type '{type_name}'.")
        terms.append((name, op, _literal(lit)))
    return terms


def _matches(rec: dict[str, Any], terms: list[tuple[str, str, Any]]) -> bool:
    for name, op, lit in terms:
        a, b = _comparable(rec.get(name), lit)
        if a is None or b is None:  # null only compares with eq / ne
            if op not in ("eq", "ne") or not _CMP[op](a, b):
                return False
            continue
        try:
            if not _CMP[op](a, b):
                return False
        except TypeError as exc:
            raise ODataError(f"Cannot compare property '{name}' with the given literal.") from exc
    return True


def apply_query(records: list[dict[str, Any]], params: dict[str, str], type_name: str) -> tuple[list[dict], int]:
    """Filter, order and project; returns (rows after $skip/$top, total matching count)."""
    fields: set[str] = set().union(*(r.keys() for r in records)) if records else set()
    known = {"$filter", "$select", "$orderby", "$top", "$skip", "$count", "$skiptoken", "$format", "cross-company"}
    unknown = sorted(k for k in params if k.startswith("$") and k not in known)
    if unknown:
        raise ODataError(f"The simulator does not support the query option(s): {', '.join(unknown)}")
    rows = records
    if flt := params.get("$filter", "").strip():
        terms = parse_filter(flt, fields, type_name)
        rows = [r for r in rows if _matches(r, terms)]
    if ob := params.get("$orderby", "").strip():
        for part in reversed([p.strip() for p in ob.split(",") if p.strip()]):
            name, _, direction = part.partition(" ")
            if name not in fields:
                raise ODataError(f"Could not find a property named '{name}' on type '{type_name}'.")
            rows = sorted(rows, key=lambda r, n=name: (r.get(n) is None, r.get(n)),
                          reverse=direction.strip().lower() == "desc")
    total = len(rows)
    try:
        skip = int(params.get("$skip", 0))
        top = int(params["$top"]) if "$top" in params else None
    except ValueError as exc:
        raise ODataError("$top and $skip must be whole numbers.") from exc
    rows = rows[skip:] if top is None else rows[skip: skip + top]
    if sel := params.get("$select", "").strip():
        cols = [c.strip() for c in sel.split(",") if c.strip()]
        missing = [c for c in cols if c not in fields]
        if missing:
            raise ODataError(f"Could not find a property named '{missing[0]}' on type '{type_name}'.")
        rows = [{c: r.get(c) for c in cols} for r in rows]
    return rows, total
