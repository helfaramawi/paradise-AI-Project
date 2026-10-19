"""Quantitative simulation engine (no LLM involvement).

The same vectorised monthly model is used for:
  * the deterministic "expected" trajectory (all uncertain parameters at their mode),
  * Monte Carlo analysis (N draws from documented triangular priors),
  * one-at-a-time sensitivity analysis (tornado).

Common random numbers: every strategy is simulated with the same parameter draws for a
given seed so differences between futures are due to the strategy, not sampling noise.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from .assumptions import (
    MODEL_ID,
    MODEL_VERSION,
    Baseline,
    DecisionControls,
    LeverEconomics,
    Levers,
    SimulationConfig,
    UncertainParameter,
    default_uncertain_parameters,
)
from .delivery_des import simulate_project_portfolio
from .futures import StrategyDefinition, build_futures

TRAJECTORY_METRICS = [
    "opex_monthly",
    "savings_run_rate",
    "revenue_monthly",
    "cash_flow_monthly",
    "cash_balance",
    "delay_pct",
    "utilization_pct",
    "csat_pct",
    "risk_exposure",
    "capacity_shortfall_fte",
]

SUMMARY_METRICS = [
    "savings_pct_at_deadline",
    "run_rate_savings_at_deadline",
    "realized_savings_12m",
    "implementation_cost_12m",
    "one_off_implementation_cost",
    "delivery_loss_12m",
    "net_benefit_12m",
    "steady_state_net_run_rate",
    "max_delay_increase_pct",
    "min_csat_pct",
    "peak_utilization_pct",
    "min_cash_balance",
    "projected_operating_profit_12m",
]

# Lever -> (cost category attribute, uncertain savings-rate parameter or None for direct share)
_SAVINGS_LEVERS: dict[str, tuple[str, str | None]] = {
    "software_consolidation": ("software_cost", "sw_savings_rate"),
    "infra_optimization": ("infrastructure_cost", "infra_savings_rate"),
    "vendor_renegotiation": ("vendor_services_cost", "vendor_savings_rate"),
    "facilities_consolidation": ("facilities_cost", "facilities_savings_rate"),
    "expense_freeze": ("other_ga_cost", "discretionary_savings_rate"),
    "contractor_reduction": ("contractor_cost", None),
}


def _canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


@dataclass
class ModelInputs:
    baseline: Baseline
    controls: DecisionControls
    config: SimulationConfig
    params: list[UncertainParameter]
    economics: LeverEconomics

    def fingerprint(self) -> str:
        return _canonical_hash({
            "model": MODEL_ID,
            "version": MODEL_VERSION,
            "baseline": self.baseline.model_dump(),
            "controls": self.controls.model_dump(),
            "config": self.config.model_dump(),
            "params": [p.model_dump() for p in self.params],
            "economics": self.economics.model_dump(),
        })


def sample_parameters(params: list[UncertainParameter], n: int, seed: int) -> dict[str, np.ndarray]:
    """Draw N samples per parameter in a fixed (sorted) order for reproducibility."""
    rng = np.random.default_rng(seed)
    out: dict[str, np.ndarray] = {}
    for p in sorted(params, key=lambda x: x.key):
        d = p.dist
        if d.high - d.low < 1e-12:
            out[p.key] = np.full(n, d.mode)
        else:
            out[p.key] = rng.triangular(d.low, d.mode, d.high, size=n)
    return out


def mode_parameters(params: list[UncertainParameter]) -> dict[str, np.ndarray]:
    return {p.key: np.array([p.dist.mode]) for p in params}


def run_model(
    b: Baseline,
    c: DecisionControls,
    levers: Levers,
    econ: LeverEconomics,
    theta: dict[str, np.ndarray],
    horizon: int = 12,
) -> dict[str, np.ndarray]:
    """Vectorised monthly model. Returns trajectories (N, H+1) and summaries (N,)."""
    n = len(next(iter(theta.values())))
    months = np.arange(1, horizon + 1, dtype=float)
    D = float(c.implementation_months)
    k = 6.0 / D  # >1 means compressed timeline
    compression_cost = 1.0 + 0.25 * max(0.0, k - 1.0)
    disruption_mult = max(1.0, k)
    overrun = theta["impl_cost_overrun"][:, None]

    def ramp(lever_key: str) -> np.ndarray:
        r = max(1.0, econ.ramp_months[lever_key] * D / 6.0)
        return np.clip(months / r, 0.0, 1.0)[None, :]  # (1, H)

    def spread_cost(lever_key: str, amount: float) -> np.ndarray:
        r = max(1, math.ceil(econ.ramp_months[lever_key] * D / 6.0))
        cost = np.zeros(horizon)
        cost[: min(r, horizon)] = amount / r
        return cost[None, :]

    savings = np.zeros((n, horizon))
    one_off = np.zeros((n, horizon))
    lv = levers.model_dump()

    for key, (attr, rate_key) in _SAVINGS_LEVERS.items():
        intensity = lv[key]
        if intensity <= 0:
            continue
        base_cost = getattr(b, attr)
        rate = theta[rate_key][:, None] if rate_key else np.ones((n, 1))
        savings += base_cost * rate * intensity * ramp(key)
        one_off += spread_cost(key, econ.impl_cost[key] * intensity * compression_cost) * overrun

    # Operating model redesign
    redesign = lv["operating_model_redesign"]
    r_red = ramp("operating_model_redesign")
    if redesign > 0:
        one_off += spread_cost("operating_model_redesign",
                               econ.impl_cost["operating_model_redesign"] * redesign * compression_cost) * overrun

    # Workforce termination (modelled only so governance has something concrete to block)
    term = lv["workforce_termination"]
    term_ramp = np.clip(months / 2.0, 0, 1)[None, :]
    if term > 0:
        savings += b.personnel_cost * term * term_ramp
    employees_eff = b.employees * (1 - term * term_ramp)

    # Automation investment (capex-like spend + running cost), S-curve adoption
    inv = lv["automation_investment"]
    adopt_m = theta["automation_adoption_months"][:, None]
    adoption = 1.0 / (1.0 + np.exp(-(months[None, :] - adopt_m / 2.0) / (adopt_m / 8.0)))
    if inv > 0:
        spend_months = max(1, math.ceil(D / 2))
        inv_cost = np.zeros(horizon)
        inv_cost[: min(spend_months, horizon)] = inv * compression_cost / spend_months
        one_off += inv_cost[None, :] * overrun
    running = np.full((n, horizon), inv * econ.automation_running_cost_rate / 12.0) * np.clip(months / 2, 0, 1)[None, :]
    automation_fte = inv * theta["automation_productivity"][:, None] * adoption

    # Capacity balance
    removed_fte = b.contractor_fte * lv["contractor_reduction"] * ramp("contractor_reduction")
    removed_fte = removed_fte + b.employees * term * term_ramp * b.utilization_pct / 100.0
    headroom_fte = b.employees * max(0.0, c.max_utilization_pct - b.utilization_pct) / 100.0
    skill_eff = theta["skill_match"][:, None] + 0.15 * redesign * r_red - 0.10 * lv["expense_freeze"]
    skill_eff = np.clip(skill_eff, 0.0, 1.0)
    realloc_fte = b.employees * theta["reallocation_gain_pct"][:, None] / 100.0 * redesign * r_red
    red_ramp_m = max(1.0, econ.ramp_months["operating_model_redesign"] * D / 6.0)
    bump = np.where(months <= red_ramp_m, np.sin(np.pi * months / (red_ramp_m + 1.0)), 0.0)[None, :]
    disruption_fte = (b.employees * theta["change_disruption_pct"][:, None] / 100.0
                      * redesign * disruption_mult * bump)

    absorbed_auto = np.minimum(removed_fte, automation_fte)
    remaining = removed_fte - absorbed_auto
    people_capacity = headroom_fte * skill_eff + realloc_fte
    absorbed_people = np.minimum(remaining, people_capacity)
    shortfall = np.maximum(0.0, remaining - absorbed_people + disruption_fte)
    shortfall_pct = shortfall / b.delivery_workload_fte * 100.0

    delay = b.avg_project_delay_pct + theta["delay_elasticity"][:, None] * shortfall_pct
    excess_auto = np.maximum(0.0, automation_fte - absorbed_auto)
    util = (b.utilization_pct
            + (absorbed_people - excess_auto + 0.5 * shortfall) / employees_eff * 100.0)
    util = np.clip(util, 0.0, 100.0)
    disruption_pct_now = disruption_fte / b.employees * 100.0
    csat = (b.csat_pct - theta["csat_delay_sensitivity"][:, None] * (delay - b.avg_project_delay_pct)
            - 0.3 * disruption_pct_now)
    csat = np.clip(csat, 0.0, 100.0)

    penalties = b.annual_revenue * theta["penalty_rate_pct"][:, None] / 100.0 * np.maximum(
        0.0, delay - b.contractual_delay_tolerance_pct)
    revenue_loss = b.annual_revenue * 0.5 * (delay - b.avg_project_delay_pct) / 100.0
    risk_exposure = penalties + revenue_loss  # annualised EGP M at risk from delivery effects

    revenue_m = (b.annual_revenue - revenue_loss - penalties) / 12.0
    opex_m = (b.annual_opex - savings) / 12.0 + one_off + running
    cash_flow = revenue_m - opex_m
    cash = b.opening_cash + np.cumsum(cash_flow, axis=1)

    # Month 0 (today) baseline prepended to trajectories
    def with_t0(arr: np.ndarray, v0: float) -> np.ndarray:
        return np.concatenate([np.full((n, 1), v0), arr], axis=1)

    base_cf = (b.annual_revenue - b.annual_opex) / 12.0
    traj = {
        "opex_monthly": with_t0(opex_m, b.annual_opex / 12.0),
        "savings_run_rate": with_t0(savings, 0.0),
        "revenue_monthly": with_t0(revenue_m, b.annual_revenue / 12.0),
        "cash_flow_monthly": with_t0(cash_flow, base_cf),
        "cash_balance": with_t0(cash, b.opening_cash),
        "delay_pct": with_t0(delay, b.avg_project_delay_pct),
        "utilization_pct": with_t0(util, b.utilization_pct),
        "csat_pct": with_t0(csat, b.csat_pct),
        "risk_exposure": with_t0(risk_exposure, 0.0),
        "capacity_shortfall_fte": with_t0(shortfall, 0.0),
    }

    d_idx = min(int(D), horizon) - 1
    run_rate_d = savings[:, d_idx]
    impl_total = (one_off + running)[:, :12].sum(axis=1)
    delivery_loss = ((penalties + revenue_loss) / 12.0)[:, :12].sum(axis=1)
    realized = (savings / 12.0)[:, :12].sum(axis=1)
    summary = {
        "savings_pct_at_deadline": run_rate_d / b.annual_opex * 100.0,
        "run_rate_savings_at_deadline": run_rate_d,
        "realized_savings_12m": realized,
        "implementation_cost_12m": impl_total,
        "one_off_implementation_cost": one_off.sum(axis=1),
        "delivery_loss_12m": delivery_loss,
        "net_benefit_12m": realized - impl_total - delivery_loss,
        "steady_state_net_run_rate": savings[:, -1] - running[:, -1] * 12 - risk_exposure[:, -1],
        "max_delay_increase_pct": (delay - b.avg_project_delay_pct).max(axis=1),
        "min_csat_pct": csat.min(axis=1),
        "peak_utilization_pct": util.max(axis=1),
        "min_cash_balance": np.minimum(cash.min(axis=1), b.opening_cash),
        "projected_operating_profit_12m": (revenue_m - opex_m)[:, :12].sum(axis=1),
    }
    return {"trajectory": traj, "summary": summary, "employees_effective": employees_eff}


def _pct(a: np.ndarray, q: float) -> float:
    return float(np.percentile(a, q))


def _r(x: float, nd: int = 3) -> float:
    return round(float(x), nd)


def evaluate_constraints(
    b: Baseline, c: DecisionControls, levers: Levers, mc: dict[str, np.ndarray]
) -> list[dict[str, Any]]:
    req = c.required_probability
    s = mc
    def chk(code: str, name_en: str, name_ar: str, ok_mask: np.ndarray | None, metric: str,
            threshold: float, direction: str, hard: bool, deterministic_ok: bool | None = None) -> dict:
        if deterministic_ok is not None:
            prob = 1.0 if deterministic_ok else 0.0
        else:
            prob = float(np.mean(ok_mask))
        q_val = None
        if metric in s:
            # unfavourable percentile at the chosen risk tolerance
            q = (1 - req) * 100 if direction == ">=" else req * 100
            q_val = _r(_pct(s[metric], q))
        return {
            "code": code, "name_en": name_en, "name_ar": name_ar, "metric": metric,
            "threshold": threshold, "direction": direction, "probability_satisfied": _r(prob),
            "required_probability": req, "value_at_tolerance": q_val,
            "status": "pass" if prob >= req else "fail", "hard": hard,
        }

    return [
        chk("C1", f"Achieve {c.cost_reduction_target_pct:.0f}% run-rate cost reduction by month {c.implementation_months}",
            f"تحقيق خفض {c.cost_reduction_target_pct:.0f}% في التكاليف بحلول الشهر {c.implementation_months}",
            s["savings_pct_at_deadline"] >= c.cost_reduction_target_pct, "savings_pct_at_deadline",
            c.cost_reduction_target_pct, ">=", False),
        chk("C2", "No employee terminations", "عدم إنهاء خدمة أي موظف", None, "workforce_termination",
            0.0, "<=", True, deterministic_ok=(levers.workforce_termination == 0 or not c.no_terminations)),
        chk("C3", f"Project delay increase ≤ {c.acceptable_delay_increase_pct:.1f} pts",
            f"زيادة تأخير المشروعات ≤ {c.acceptable_delay_increase_pct:.1f} نقطة",
            s["max_delay_increase_pct"] <= c.acceptable_delay_increase_pct + 1e-9, "max_delay_increase_pct",
            c.acceptable_delay_increase_pct, "<=", True),
        chk("C4", f"Customer satisfaction ≥ {c.min_csat_pct:.0f}%", f"رضا العملاء ≥ {c.min_csat_pct:.0f}%",
            s["min_csat_pct"] >= c.min_csat_pct - 1e-9, "min_csat_pct", c.min_csat_pct, ">=", True),
        chk("C5", f"Contractual delay tolerance ({b.contractual_delay_tolerance_pct:.0f}%) not breached",
            f"عدم تجاوز حد التأخير التعاقدي ({b.contractual_delay_tolerance_pct:.0f}%)",
            (s["max_delay_increase_pct"] + b.avg_project_delay_pct) <= b.contractual_delay_tolerance_pct + 1e-9,
            "max_delay_increase_pct", b.contractual_delay_tolerance_pct - b.avg_project_delay_pct, "<=", True),
        chk("C6", f"One-off implementation cost ≤ EGP {c.implementation_budget:.1f}M",
            f"تكلفة التنفيذ ≤ {c.implementation_budget:.1f} مليون جنيه",
            s["one_off_implementation_cost"] <= c.implementation_budget + 1e-9, "one_off_implementation_cost",
            c.implementation_budget, "<=", False),
    ]


def sensitivity_analysis(inputs: ModelInputs, levers: Levers) -> list[dict[str, Any]]:
    base_theta = mode_parameters(inputs.params)
    base = run_model(inputs.baseline, inputs.controls, levers, inputs.economics, base_theta,
                     inputs.config.horizon_months)["summary"]
    rows = []
    for p in inputs.params:
        vals = {}
        for side, v in (("low", p.dist.low), ("high", p.dist.high)):
            th = dict(base_theta)
            th[p.key] = np.array([v])
            vals[side] = run_model(inputs.baseline, inputs.controls, levers, inputs.economics, th,
                                   inputs.config.horizon_months)["summary"]
        lo_nb = float(vals["low"]["net_benefit_12m"][0])
        hi_nb = float(vals["high"]["net_benefit_12m"][0])
        rows.append({
            "parameter": p.key, "label_en": p.label_en, "label_ar": p.label_ar,
            "low_value": p.dist.low, "high_value": p.dist.high,
            "net_benefit_at_low": _r(lo_nb), "net_benefit_at_high": _r(hi_nb),
            "savings_pct_at_low": _r(vals["low"]["savings_pct_at_deadline"][0]),
            "savings_pct_at_high": _r(vals["high"]["savings_pct_at_deadline"][0]),
            "delay_at_low": _r(vals["low"]["max_delay_increase_pct"][0]),
            "delay_at_high": _r(vals["high"]["max_delay_increase_pct"][0]),
            "swing": _r(abs(hi_nb - lo_nb)),
        })
    rows.sort(key=lambda r: r["swing"], reverse=True)
    return [{**r, "base_net_benefit": _r(base["net_benefit_12m"][0])} for r in rows]


def _summarize_traj(traj: dict[str, np.ndarray], expected: dict[str, np.ndarray]) -> dict[str, Any]:
    out = {}
    for m in TRAJECTORY_METRICS:
        a = traj[m]
        out[m] = {
            "expected": [_r(v) for v in expected[m][0]],
            "p10": [_r(v) for v in np.percentile(a, 10, axis=0)],
            "p50": [_r(v) for v in np.percentile(a, 50, axis=0)],
            "p90": [_r(v) for v in np.percentile(a, 90, axis=0)],
        }
    return out


def simulate_strategy(inputs: ModelInputs, strategy: StrategyDefinition | None,
                      theta: dict[str, np.ndarray], include_sensitivity: bool = True,
                      include_des: bool = True) -> dict[str, Any]:
    levers = strategy.levers if strategy else Levers()
    b, c, cfg = inputs.baseline, inputs.controls, inputs.config
    mc = run_model(b, c, levers, inputs.economics, theta, cfg.horizon_months)
    exp = run_model(b, c, levers, inputs.economics, mode_parameters(inputs.params), cfg.horizon_months)
    s = mc["summary"]

    summary = {}
    for m in SUMMARY_METRICS:
        summary[m] = {
            "expected": _r(exp["summary"][m][0]),
            "mean": _r(np.mean(s[m])),
            "p10": _r(_pct(s[m], 10)),
            "p50": _r(_pct(s[m], 50)),
            "p90": _r(_pct(s[m], 90)),
        }
    target = c.cost_reduction_target_pct
    req = c.required_probability
    achievable = _r(_pct(s["savings_pct_at_deadline"], (1 - req) * 100), 2)
    constraints = evaluate_constraints(b, c, levers, s)

    nb = s["net_benefit_12m"]
    hist_counts, hist_edges = np.histogram(nb, bins=24)
    order = np.argsort(nb)
    def scen(idx: int) -> dict[str, float]:
        return {m: _r(s[m][idx]) for m in SUMMARY_METRICS}
    n = len(nb)
    cases = {
        "worst": scen(order[int(0.10 * (n - 1))]),
        "base": scen(order[int(0.50 * (n - 1))]),
        "best": scen(order[int(0.90 * (n - 1))]),
    }

    result: dict[str, Any] = {
        "strategy_key": strategy.key if strategy else "BASELINE",
        "levers": levers.model_dump(),
        "summary": summary,
        "probabilities": {
            "meet_target": _r(np.mean(s["savings_pct_at_deadline"] >= target)),
            "delay_within_acceptable": _r(np.mean(s["max_delay_increase_pct"] <= c.acceptable_delay_increase_pct + 1e-9)),
            "csat_maintained": _r(np.mean(s["min_csat_pct"] >= c.min_csat_pct - 1e-9)),
            "positive_net_benefit_12m": _r(np.mean(nb > 0)),
            "contractual_breach": _r(np.mean(s["max_delay_increase_pct"] + b.avg_project_delay_pct
                                             > b.contractual_delay_tolerance_pct + 1e-9)),
        },
        "achievable_reduction_pct_at_tolerance": achievable,
        "constraints": constraints,
        "constraints_violated": [x["code"] for x in constraints if x["status"] == "fail"],
        "hard_constraints_violated": [x["code"] for x in constraints if x["status"] == "fail" and x["hard"]],
        "cases": cases,
        "net_benefit_histogram": {"counts": hist_counts.tolist(), "edges": [_r(e) for e in hist_edges]},
        "trajectory": _summarize_traj(mc["trajectory"], exp["trajectory"]),
    }
    if include_sensitivity:
        result["sensitivity"] = sensitivity_analysis(inputs, levers)
    if include_des:
        mean_short = float(np.mean(exp["trajectory"]["capacity_shortfall_fte"][0, 1:]))
        result["project_portfolio"] = simulate_project_portfolio(
            b, capacity_reduction_fte=mean_short, seed=cfg.seed,
            at_risk_threshold_pct=max(c.acceptable_delay_increase_pct, 2.0))
    return result


def run_full_simulation(
    baseline: Baseline | None = None,
    controls: DecisionControls | None = None,
    config: SimulationConfig | None = None,
    params: list[UncertainParameter] | None = None,
    economics: LeverEconomics | None = None,
    include_sensitivity: bool = True,
    include_des: bool = True,
) -> dict[str, Any]:
    if controls is not None and controls.domain == "hotel":
        from . import hotel

        hparams = params if params and any(p.key == "brand_occupancy_gain" for p in params) else None
        return hotel.run_full_simulation(baseline or Baseline(), controls, config or SimulationConfig(), hparams,
                                         None, include_sensitivity, include_des)
    if controls is not None and controls.domain == "collections":
        from . import collections

        cparams = params if params and any(p.key == "agency_recovery_rate" for p in params) else None
        return collections.run_full_simulation(baseline or Baseline(), controls, config or SimulationConfig(), cparams,
                                               None, include_sensitivity, include_des)
    t0 = time.perf_counter()
    inputs = ModelInputs(
        baseline=baseline or Baseline(),
        controls=controls or DecisionControls(),
        config=config or SimulationConfig(),
        params=params or default_uncertain_parameters(),
        economics=economics or LeverEconomics(),
    )
    theta = sample_parameters(inputs.params, inputs.config.iterations, inputs.config.seed)
    futures = build_futures(inputs.controls)
    results = {
        "baseline": simulate_strategy(inputs, None, theta, include_sensitivity=False, include_des=include_des),
        "futures": {},
    }
    for f in futures:
        r = simulate_strategy(inputs, f, theta, include_sensitivity, include_des)
        r["definition"] = f.model_dump()
        results["futures"][f.key] = r
    results["meta"] = {
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "input_fingerprint": inputs.fingerprint(),
        "seed": inputs.config.seed,
        "iterations": inputs.config.iterations,
        "horizon_months": inputs.config.horizon_months,
        "controls": inputs.controls.model_dump(),
        "confidence_percentile": inputs.controls.confidence_percentile,
        "required_probability": inputs.controls.required_probability,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "method": "Vectorised monthly cost/capacity model; Monte Carlo over triangular priors with "
                  "common random numbers; one-at-a-time sensitivity; SimPy discrete-event project "
                  "portfolio simulation.",
        "nature": "quantitative_simulation",
    }
    return results
