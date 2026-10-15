# API Documentation

- Interactive OpenAPI: **`/api/docs`** (Swagger UI), `/api/redoc`, raw spec at `/api/openapi.json`. An export is committed at `docs/openapi.json`.
- Base path: `/api/v1`. JSON in and out. Authentication: `Authorization: Bearer <JWT>` from `POST /auth/login`. The SSE endpoint also accepts `?access_token=`, because `EventSource` cannot set headers.
- Errors: `{"detail": ...}` with 401 (unauthenticated), 403 (permission, separation of duties, or locked policy), 404 (not found or other tenant), 409 (state conflict), 422 (validation), 423 (emergency stop), 429 (login rate limit).

## Endpoints

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/health`, `/api/ready` | — | liveness; readiness (checks the database) |
| POST | `/auth/login` | — | `{email, password, tenant?}` → `{access_token, user}` |
| GET/PATCH | `/auth/me` | auth | profile; set `preferred_language` |
| GET | `/platform/status` | auth | LLM mode, external actions, emergency stop, n8n |
| GET | `/dashboard` | decision.read | counts, latest dossier summary, recent audit |
| GET | `/agents` | auth | agent definitions and authority |
| POST | `/decisions/parse` | decision.create | intake parser → parsed fields + suggested controls |
| GET | `/decisions/demo-question` | auth | demo question (EN/AR) |
| GET/POST | `/decisions` | read / create | list; create (`auto_run` starts analysis) |
| GET | `/decisions/{id}` | decision.read | decision + runs |
| PATCH | `/decisions/{id}/controls` | decision.create | update controls (frozen once submitted) |
| POST | `/decisions/{id}/runs` | decision.run | start an orchestrated analysis (`pacing_ms` optional) → 202 `{run_id}` |
| GET | `/runs/{id}` | decision.read | run + all events |
| GET | `/runs/{id}/events?after=N` | decision.read | **SSE** stream: `event: workflow` per event, `event: end` at completion |
| POST | `/runs/{id}/cancel` | decision.cancel | cooperative cancellation |
| GET | `/decisions/{id}/dossier?run_id=` | decision.read | full dossier: decision, dataset, run, findings + evidence, executions, objections, collisions, risks, governance, simulation results, approvals |
| GET | `/simulation/model` | simulation.run | production model, versions, parameters, schemas |
| POST | `/simulation/run` | simulation.run | what-if: `{controls, iterations, seed, dataset_version_id?, baseline_overrides?, persist?, decision_id?}` |
| POST | `/simulation/custom` | simulation.run | Simulation Lab: arbitrary `levers` |
| GET | `/simulation/runs` | simulation.run | stored simulation runs |
| GET | `/datasets` | dataset.read | datasets with versions |
| POST | `/datasets/{id}/versions` | dataset.write | new version from edits (provenance → user_input) |
| POST | `/datasets/validate` | dataset.read | validate a baseline document |
| POST | `/datasets/{id}/import` | dataset.write | multipart CSV/XLSX (`field,value` or `category,amount`) → new version + reconciliation |
| GET | `/datasets/synthetic/ledger` | dataset.read | generated synthetic GL and project register |
| GET | `/connectors` | dataset.read | connector registry |
| PATCH | `/connectors/{id}` | connector.manage | non-secret config (secret-like keys rejected) |
| POST | `/connectors/{id}/test` | connector.manage | connection test (`verified_live` flag) |
| POST | `/connectors/{id}/sync` | dataset.write | read-only sync → reconciliation (+ new version if changed) |
| GET | `/governance/policies` | governance.read | policies |
| PATCH | `/governance/policies/{id}` | governance.manage | enable/disable or edit rule (locked → 403) |
| POST | `/governance/evaluate` | governance.read | policy sandbox `{context}` |
| POST | `/decisions/{id}/approval-requests` | approval.request | `{scenario_key, justification, acknowledged[]}` → pending or blocked |
| GET | `/approvals?status=` | decision.read | all requests |
| GET | `/me/approval-inbox` | auth | requests awaiting one of my roles |
| POST | `/approvals/{id}/decide` | approval.decide | `{verdict: approve/reject/request_analysis, role_key, comment}` |
| GET | `/automation/workflows` | automation.read | workflows + n8n status |
| POST | `/automation/workflows/{id}/trigger` | automation.run | `{dry_run, decision_id?, payload}` (idempotent) |
| GET | `/automation/runs` | automation.read | execution log |
| GET/POST | `/decisions/{id}/outcomes` | read / outcome.record | actuals, comparisons, calibration; record `[{month, metric, value}]` |
| POST | `/decisions/{id}/outcomes/synthetic-demo` | outcome.record | labelled synthetic actuals (demo) |
| POST | `/decisions/{id}/calibration-proposal` | outcome.record | create a **candidate** model from diagnostics |
| POST | `/models/{id}/promote` | governance.manage | promote candidate → production `{justification}` |
| GET | `/decisions/{id}/report.pdf?lang=en\|ar` / `report.xlsx` | report.export | executive report |
| GET/POST | `/admin/users`, PATCH `/admin/users/{id}` | admin.users | user management |
| GET | `/admin/roles` | admin.users | RBAC matrix |
| GET | `/admin/audit` | admin.audit | audit events + chain verification |
| POST | `/admin/emergency-stop` | admin.emergency_stop | `{active, reason}` |

## Example: run an analysis from the command line

```bash
API=http://localhost:8080/api/v1
TOK=$(curl -s -X POST $API/auth/login -H 'content-type: application/json' \
  -d '{"email":"analyst@futuremirror.demo","password":"FutureMirror!2026"}' | jq -r .access_token)
DEC=$(curl -s -X POST $API/decisions -H "Authorization: Bearer $TOK" -H 'content-type: application/json' \
  -d '{"title":"Opex -20%","question":"Reduce operating costs by 20% within six months without terminating employees"}' | jq -r .id)
RUN=$(curl -s -X POST $API/decisions/$DEC/runs -H "Authorization: Bearer $TOK" -H 'content-type: application/json' -d '{"pacing_ms":0}' | jq -r .run_id)
curl -N "$API/runs/$RUN/events?access_token=$TOK"           # live event stream
curl -s $API/decisions/$DEC/dossier -H "Authorization: Bearer $TOK" | jq '.run.result.recommendation.headline_en'
```

## SSE event schema

```json
{"id": 57, "ts": "2026-10-15T09:01:52Z", "stage": "agent_court", "event_type": "objection",
 "agent_key": "redteam", "message_en": "...", "message_ar": "...",
 "payload": {"target_agent": "cfo", "severity": "high", "type": "unsupported_assumption", "strategy_key": "A"}}
```

Event types: `stage_started`, `stage_completed`, `agent_started`, `agent_finding`, `agent_completed`, `agent_retry`, `agent_failed`, `warning`, `message`, `objection`, `response`, `collision`, `policy_decision`, `run_completed`, `run_cancelled`, `error`.
