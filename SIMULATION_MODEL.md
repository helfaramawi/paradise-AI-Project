# Simulation Model — `opex-optimization` v1.3.0

Source: `backend/app/simulation/` (`assumptions.py`, `engine.py`, `delivery_des.py`, `validation.py`, `futures.py`).
The engine is pure Python/NumPy/SimPy and has **no dependency on any language model**.

## 1. Nature of outputs

| Output | Nature | Shown as |
|---|---|---|
| Dataset values (revenue, opex, headcount …) | synthetic "given" facts | FACT (synthetic) |
| Cost decomposition, contractor cost per FTE, tolerances | synthetic assumptions | ASSUMPTION |
| Triangular priors (14 parameters) | expert-judgement priors, **uncalibrated** | ASSUMPTION |
| Trajectories, percentiles, probabilities | model estimates | ESTIMATE |
| Collisions, recommendation | derived from estimates + policy | RECOMMENDATION |

## 2. Data validation and the interpretation used

The synthetic brief is **internally inconsistent**, and the validator says so (check `DQ-002`):

- Gross margin 28% on EGP 180M of revenue → gross profit EGP 50.4M.
- If the EGP 120M of operating expenses sit *below* gross profit → operating profit −EGP 69.6M.
- If the EGP 120M is the *total* cost base → operating margin 33.3%, which cannot exceed a 28% gross margin.

**Interpretation used:** operating expenses = total annual cost base (EGP 120M). The stated gross margin is flagged as unverified and is not used in any calculation. Approvers must acknowledge this (policy GOV-011). Editing the dataset (for example, gross margin 70%) clears the error; this is tested.

Other checks: categories reconcile to the total (DQ-001), personnel cost is an assumption (DQ-003), utilisation headroom (DQ-004), no historical or skills data (DQ-005), contractor dependency (DQ-006).

Synthetic decomposition of the EGP 120M: personnel 66, contractors 18, software 12, infrastructure 9, facilities 6, vendor services 5, other G&A 4.

## 3. Decision controls (sliders)

Target % (C1), implementation months *D*, no-terminations flag, maximum sustainable utilisation, automation investment, acceptable delay increase, minimum CSAT, risk tolerance (low/medium/high → required probability 0.9/0.7/0.5), implementation budget.

## 4. Levers and strategies

| Lever | Affects | Impl. cost at intensity 1 (EGP M) | Ramp at D = 6 (months) |
|---|---|---|---|
| software_consolidation | software × `sw_savings_rate` | 0.5 | 3 |
| infra_optimization | infrastructure × `infra_savings_rate` | 0.7 | 4 |
| vendor_renegotiation | vendor services × `vendor_savings_rate` | 0.2 | 2 |
| facilities_consolidation | facilities × `facilities_savings_rate` | 0.9 | 6 |
| expense_freeze | other G&A × `discretionary_savings_rate`; reduces skill match by ≤ 0.10 (training cut) | 0 | 1 |
| contractor_reduction | contractor spend × share; removes contractor FTE | 0.6 | 2 |
| automation_investment (EGP M) | frees FTE = inv × `automation_productivity` × S-curve; running cost 15%/yr | = investment | adoption prior |
| operating_model_redesign | + reallocation FTE, + 0.15 skill match, transition disruption | 2.5 | 5 |
| workforce_termination | personnel savings and capacity loss — **exists so governance can block it** | 0 | 2 |

Futures A/B/C are fixed lever mixes (`futures.py`). Future B's automation investment follows the slider.

## 5. Monthly model (vectorised over N draws), t = 1..12

Timeline compression: k = 6 / D. Ramps scale by D/6. One-off costs scale by 1 + 0.25·max(0, k−1). Disruption scales by max(1, k). One-off costs are multiplied by `impl_cost_overrun`.

```
ramp_l(t)           = clip(t / max(1, ramp_l·D/6), 0, 1)
savings(t)          = Σ_l cost_l · rate_l · intensity_l · ramp_l(t)           (annual run-rate)
adoption(t)         = 1 / (1 + exp(−(t − m/2)/(m/8))),  m = automation_adoption_months
automation_fte(t)   = inv · automation_productivity · adoption(t)
removed_fte(t)      = contractor_FTE · contractor_reduction · ramp_c(t)         (contractor_FTE = 18 / 0.6 = 30)
headroom_fte        = employees · max(0, max_util − util₀)/100                  (150 · 13% = 19.5)
skill(t)            = clip(skill_match + 0.15·redesign·ramp_r(t) − 0.10·freeze, 0, 1)
realloc_fte(t)      = employees · reallocation_gain/100 · redesign · ramp_r(t)
disruption_fte(t)   = employees · change_disruption/100 · redesign · max(1,k) · sin(πt/(R+1))  for t ≤ R
absorbed_auto       = min(removed, automation_fte)
absorbed_people     = min(removed − absorbed_auto, headroom·skill + realloc)
shortfall(t)        = max(0, removed − absorbed_auto − absorbed_people + disruption)
delay(t)            = delay₀ + delay_elasticity · shortfall / workload_FTE · 100     (workload_FTE = 108 + 30)
utilisation(t)      = util₀ + (absorbed_people − excess_automation + 0.5·shortfall)/employees·100
CSAT(t)             = csat₀ − csat_delay_sensitivity·(delay − delay₀) − 0.3·disruption%
penalties(t)        = revenue · penalty_rate% · max(0, delay − contractual_tolerance)
revenue_loss(t)     = revenue · 0.5 · (delay − delay₀)/100                         (deferral proxy)
revenue_m(t)        = (revenue − revenue_loss − penalties)/12
opex_m(t)           = (opex − savings)/12 + one_off(t) + running(t)
cash(t)             = opening_cash + Σ (revenue_m − opex_m)
risk_exposure(t)    = penalties + revenue_loss                                     (annualised EGP M)
```

Summaries per draw: savings % at deadline, 12-month realised savings, implementation cost, delivery loss, **12-month net benefit = realised savings − implementation & running cost − delivery loss**, maximum delay increase, minimum CSAT, peak utilisation, minimum cash, 12-month operating profit.

## 6. Uncertainty

Fourteen triangular priors (low/mode/high) in `default_uncertain_parameters()`, each with a rationale. **None is calibrated** — no historical outcome data exists. The UI and reports say so. The widest-impact priors are skill match (0.35/0.55/0.75), delay elasticity, automation productivity and implementation overrun (0.95/1.10/1.50, right-skewed).

- **Monte Carlo:** `numpy.random.default_rng(seed)`, parameters sampled in sorted-key order, N = 2 000 by default (100–20 000).
- **Common random numbers:** every future uses the same draws, so differences reflect the strategy.
- **Expected case:** all parameters at their mode (independent of the seed).
- **Bands:** P10/P50/P90 per month and per summary metric. Best/base/worst cases are the draws at the P90/P50/P10 net-benefit ranks.
- **Sensitivity:** one-at-a-time low/high per parameter at the mode, ranked by net-benefit swing (tornado).

## 7. Constraints (evaluated on the Monte Carlo distribution)

A constraint passes when P(satisfied) ≥ the required probability for the chosen risk tolerance.

| Code | Constraint | Hard |
|---|---|---|
| C1 | savings % at month D ≥ target | soft (objective) |
| C2 | no terminations | hard (deterministic) |
| C3 | max delay increase ≤ acceptable | hard |
| C4 | min CSAT ≥ floor | hard |
| C5 | delay ≤ contractual tolerance | hard |
| C6 | one-off implementation cost ≤ budget | soft |

**Achievable reduction at tolerance** = the (1 − required probability) quantile of savings % at deadline. The **feasibility search** re-runs the model at D ∈ {6, 9, 12} (600 draws, same seed) to list options that satisfy every hard constraint.

## 8. Project-portfolio discrete-event simulation (SimPy)

There are 18 synthetic projects × 5 work packages (crews 4–9 FTE, durations triangular(1.5, 2.5, 4) months, staggered starts). Work packages draw crews from a shared `simpy.Container` sized so baseline demand is about 91% of capacity. The scenario run shrinks capacity by the strategy's mean expected shortfall. Common random numbers make the additional delay per project attributable to the strategy. A project counts as **at risk** when its additional delay exceeds max(acceptable delay, 2)% of its planned duration.

## 9. Reproducibility and versioning

- `input_fingerprint` = SHA-256 (first 16 hex characters) over model id/version, baseline, controls, config, parameters and economics. It is stored on every `simulation_runs` row and shown in the UI.
- Same seed and inputs → identical results (tested in `test_reproducible_with_same_seed`).
- Model versions live in `simulation_models` (`production` / `candidate` / `retired`). Calibration proposals create a **candidate**, and only a `governance.manage` holder can promote it, with an audited justification.

## 10. Demo results (seed 20260101, default controls)

| | Future A | Future B | Future C |
|---|---|---|---|
| Savings at month 6 (median) | 14.5% | 9.4% | 12.1% |
| Delay increase (median) | +8.2 pts | +0.0 pts | +4.8 pts |
| Projects at risk (DES) | 4/18 | 0/18 | 0/18 |
| Hard constraints violated | C3, C4, C5 | none | C3, C4, C5 |
| Governance | denied (GOV-009) | requires CFO/CEO/Legal | requires 5 roles |

**Insight:** no future reaches 20% without terminations, because personnel (55% of costs) is protected and the remaining EGP 54M would need a 44% cut. The platform reports the realistic range and the trade-offs. It does not pretend the target is achievable.

## 11. Known model limitations

Linear ramps; a single portfolio-level delay elasticity; revenue effects use proxies; the DES uses mean shortfall rather than a time-varying capacity; parameters are treated as independent (no correlation structure); there is no seasonality in the monthly model.
