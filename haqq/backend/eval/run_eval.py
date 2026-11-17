"""Repeatable evaluation of the deterministic contract engine against a labelled gold set.

    python -m eval.run_eval            # prints per-item results and summary metrics (JSON)

The gold set (eval/clause_gold.json) is synthetic and labelled by hand; extend it with reviewed clauses from
pilot customers (with consent) — never with unverified model output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engines.contract import RawClause, analyze_clause  # noqa: E402

GOLD = Path(__file__).with_name("clause_gold.json")


def evaluate() -> dict:
    items = json.loads(GOLD.read_text())
    rows, ok = [], {"category": 0, "notice": 0, "time_bar": 0, "exclusion": 0, "payment": 0}
    n_pay = 0
    for g in items:
        a = analyze_clause(RawClause("X", g["title"], None, 1, 1, [g["text"]]))
        notices = [t for t in a.time_limits if t["kind"] == "notice"]
        got_notice = notices[0]["days"] if notices else None
        r = {"id": g["id"], "category": (a.category, g["category"]), "notice": (got_notice, g["notice_days"]),
             "time_bar": (bool(notices and notices[0]["time_bar"]), g["time_bar"]),
             "exclusion": (bool(a.exclusions), g["has_exclusion"])}
        if g.get("notice_day_type") and notices:
            r["day_type"] = (notices[0]["day_type"], g["notice_day_type"])
        if "payment_days" in g:
            n_pay += 1
            pays = [t["days"] for t in a.time_limits if t["kind"] == "payment"]
            r["payment"] = (pays[0] if pays else None, g["payment_days"])
            ok["payment"] += r["payment"][0] == r["payment"][1]
        for k in ("category", "notice", "time_bar", "exclusion"):
            ok[k] += r[k][0] == r[k][1]
        rows.append(r)
    n = len(items)
    summary = {"n": n, "category_accuracy": ok["category"] / n, "notice_period_accuracy": ok["notice"] / n,
               "time_bar_accuracy": ok["time_bar"] / n, "exclusion_accuracy": ok["exclusion"] / n,
               "payment_period_accuracy": ok["payment"] / n_pay if n_pay else None}
    return {"summary": summary, "errors": [r for r in rows if any(v[0] != v[1] for k, v in r.items() if k != "id")]}


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=1, default=str))
