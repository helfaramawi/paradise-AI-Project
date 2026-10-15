# Database Design

PostgreSQL 16 (SQLite for dev/tests). The schema lives in `backend/app/models.py`, and the migration in `backend/alembic/versions/0001_initial_schema.py` (35 tables). It applies automatically at startup, or manually with `alembic upgrade head`. Primary keys are UUID strings, except the append-only `workflow_events` and `audit_events` tables, which use auto-incrementing integers. Foreign keys enforce referential integrity; on SQLite, `PRAGMA foreign_keys=ON` is set.

## Entity groups

### Tenancy and identity
| Table | Purpose | Key relations |
|---|---|---|
| organizations | legal entity | — |
| tenants | isolated workspace; `settings` (currency, emergency_stop) | → organizations |
| users | unique (tenant_id, email); PBKDF2 hash; preferred language | → tenants |
| roles | unique (tenant_id, key) | → tenants |
| permissions | global catalogue (19) | — |
| role_permissions, user_roles | many-to-many | → roles, permissions, users |

### Enterprise data
| Table | Purpose |
|---|---|
| enterprise_datasets | dataset per tenant; `source`, `is_synthetic` |
| dataset_versions | immutable versions: `data` (Baseline), per-field `provenance`, `validation` report, SHA-256 `checksum`, `created_by`; unique (dataset_id, version) |
| data_connections | connector registry: kind, status, `implementation` (working / adapter / interface_only), non-secret config, last sync result |

### Decisions and orchestration
| Table | Purpose |
|---|---|
| decisions | question, controls (+ seed / iterations), parsed intake, status, recommended strategy → dataset_versions |
| decision_objectives, decision_constraints | structured objectives and hard/soft constraints |
| decision_runs | one orchestrated analysis: status, mode, LLM provider/model, compute_ms, pacing_ms, cancel flag, `result` (recommendation, governance probe, validation) |
| workflow_events | append-only event stream (SSE source) |
| agent_definitions | 10 agents with an `authority` JSON |
| agent_executions | per agent, per phase: status, attempts, duration, error, LLM narrative |
| agent_findings | claim type, stance, future, bilingual text, confidence, evidence quality, assumptions → executions |
| evidence_records | source type, reference path, value, verified → findings |
| agent_objections | Red Team objection + response + resolution → target finding |
| decision_collisions | rule, severity score, positions, objectives, consequences, resolutions |
| risk_assessments | probability × impact per future with basis and mitigation |

### Simulation
| Table | Purpose |
|---|---|
| scenarios | strategy definitions used in a run |
| simulation_models | key + version (unique), parameters, economics, status production / candidate / retired |
| simulation_runs | kind (pipeline / what_if), seed, iterations, **input_fingerprint**, controls, elapsed time → model, dataset version, decision, run |
| simulation_results | full output per scenario (BASELINE, A, B, C) |

### Governance and automation
| Table | Purpose |
|---|---|
| governance_policies | per tenant, code unique, effect, JSON rule, enabled, locked, version |
| governance_evaluations | outcome, roles and per-policy results per future |
| approval_requests | future, status, required roles, governance snapshot, requester |
| approval_decisions | approver, role, verdict, comment |
| automation_workflows | trigger, schedule, consequential flag, mode, n8n path, retry limit |
| automation_runs | idempotency_key (unique), dry_run, attempts, status, result |

### Audit and feedback loop
| Table | Purpose |
|---|---|
| audit_events | hash-chained (`prev_hash`, `hash`) audit log |
| actual_outcomes | unique (decision, month, metric); `is_synthetic` flag |
| forecast_comparisons | predicted, P10/P90, actual, error, error %, within-interval → simulation run |

## Traceability chain

```
approval_requests ─► decision_runs ─► simulation_runs ─► simulation_models (version, params)
        │                  │                 └────────► dataset_versions (checksum, provenance, validation)
        │                  ├─► agent_executions ─► agent_findings ─► evidence_records (reference → simulation path)
        │                  ├─► agent_objections / decision_collisions / risk_assessments / governance_evaluations
        └─ governance_snapshot (frozen policy results at submission)
forecast_comparisons ─► simulation_runs (the forecast the actuals were compared against)
audit_events (hash chain over every consequential action)
```

## Migrations

```bash
cd backend
alembic upgrade head                                   # apply
alembic revision --autogenerate -m "describe change"   # new migration after model edits
```

`FM_DATABASE_URL` selects the target database. The test suite runs the same migration on SQLite and PostgreSQL.
