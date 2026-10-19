"""Builds policy-engine input documents from decisions/simulations and loads tenant policies."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import GovernancePolicy
from .engine import DEFAULT_POLICIES, evaluate_policies


def load_policies(db: Session, tenant_id: str) -> list[dict[str, Any]]:
    rows = db.scalars(select(GovernancePolicy).where(GovernancePolicy.tenant_id == tenant_id)
                      .order_by(GovernancePolicy.code)).all()
    if not rows:
        return [dict(p, enabled=True) for p in DEFAULT_POLICIES]
    return [{"code": r.code, "effect": r.effect, "rule": r.rule, "enabled": r.enabled, "name_en": r.name_en,
             "name_ar": r.name_ar} for r in rows]


def strategy_context(
    *, future: dict[str, Any], controls: dict[str, Any], collisions: list[dict[str, Any]],
    dataset_has_errors: bool, decision_status: str = "analyzed", actor_type: str = "user", mode: str = "approve",
) -> dict[str, Any]:
    k = future["strategy_key"]
    s = future["summary"]
    # Decision-level collisions (strategy_key None) concern the objective itself and are surfaced as a
    # required revision in the recommendation; only strategy-specific critical collisions block approval.
    crit = [c for c in collisions if c.get("strategy_key") == k and c.get("severity") == "critical"]
    collections = controls.get("domain") == "collections"  # there the "delay" metric is the complaint rate
    hotel = controls.get("domain") == "hotel"  # capital works are governed by GOV-018, not the GOV-012 spend cap
    return {
        "action": {
            "type": "strategy.approve",
            "strategy_key": k,
            "actor_type": actor_type,
            "mode": mode,
            "external_write": False,
            "levers": future["levers"],
            "financial_impact": abs(s["net_benefit_12m"]["p50"]) + s["one_off_implementation_cost"]["p50"],
        },
        "decision": {"no_terminations": controls.get("no_terminations", True), "status": decision_status},
        "analysis": {
            "max_delay_increase_pct": 0.0 if collections else s["max_delay_increase_pct"]["p50"],
            "complaint_increase_pct": s["max_delay_increase_pct"]["p50"] if collections else 0.0,
            "peak_utilization_pct": s["peak_utilization_pct"]["p50"],
            "hard_constraints_violated": future["hard_constraints_violated"],
            "critical_collisions": len(crit),
            "implementation_cost_p90": 0.0 if hotel else s["one_off_implementation_cost"]["p90"],
            "capital_investment_p90": s["one_off_implementation_cost"]["p90"] if hotel else 0.0,
        },
        "dataset": {"has_errors": dataset_has_errors},
        "platform": {"external_actions_enabled": get_settings().external_actions_enabled},
    }


def evaluate_strategy(policies: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
    ctx = strategy_context(**kw)
    res = evaluate_policies(policies, ctx)
    res["input"] = ctx
    return res
