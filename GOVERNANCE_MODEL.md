# Governance Model

**Principle:** an AI agent may analyse and recommend, but it never has unrestricted authority to execute consequential decisions. Enforcement lives in code (`backend/app/governance/`, `backend/app/api/governance.py`, `backend/app/security.py`), never in prompts.

## 1. Policy engine

- Policies are JSON documents in `governance_policies`, per tenant and versioned. Conditions support `all` / `any` / `not` and the operators `eq, ne, gt, gte, lt, lte, in, contains, truthy, falsy, exists, missing, len_gt`.
- Input document: `{action, decision, analysis, dataset, platform}`, built from persisted simulation results by `governance/service.py`.
- **Precedence:** any matching `deny` → **denied** (no roles can override it). Otherwise any `require_approval` → **requires_approval** with the union of roles. Otherwise **allowed**. `require_acknowledgement` adds mandatory acknowledgements.
- Agent recommendations are **not an input**. The engine can deny a strategy that every agent supports. This is tested: unanimous high-confidence support for a strategy containing terminations is still denied, and the recommendation returns no strategy.
- The design mirrors Open Policy Agent (input document → decision), so the rules could move to Rego with the same call sites. A sandbox (`POST /governance/evaluate`, *AI Governance* screen) evaluates any document against the live policy set.

## 2. Default policies

| Code | Effect | Locked | Rule |
|---|---|---|---|
| GOV-001 | deny | ✔ | terminations while the decision has a no-termination constraint, or any `workforce.terminate` action |
| GOV-002 | deny | ✔ | execution requested by an AI agent (`actor_type=agent ∧ mode=execute`) |
| GOV-003 | deny | ✔ | external system writes while `FM_EXTERNAL_ACTIONS_ENABLED=false` (the default) |
| GOV-004 | require CFO | | financial impact ≥ EGP 1M |
| GOV-005 | require CEO | | financial impact ≥ EGP 5M |
| GOV-006 | require Legal | | contractor reduction or vendor renegotiation (contract changes) |
| GOV-007 | require HR | | operating-model redesign, or peak utilisation > 85% |
| GOV-008 | require COO | | modelled delay increase > 0.5 pts |
| GOV-009 | deny | | unresolved strategy-specific **critical** decision collision |
| GOV-010 | require CEO + COO | | a hard constraint fails at the selected risk tolerance (explicit risk acceptance) |
| GOV-011 | acknowledgement | | the dataset has consistency errors |
| GOV-012 | deny | | P90 implementation cost > EGP 20M hard cap |
| GOV-013 | deny | ✔ | separation of duties (procedural: requester ≠ approver; one approver, one role) |
| GOV-014 | deny | ✔ | live consequential automation unless external actions are enabled **and** the decision is approved |
| GOV-015 | require Legal | | collections: receivables placed with an agency (customer data shared with a third party) |
| GOV-016 | deny | | collections: aggressive collection tactics (fair collection) |
| GOV-017 | require Legal + HR + CEO | | hotel: long-term lease or usufruct of a state-owned asset (public tender under Law 182 of 2018, staff transfer plan) |
| GOV-018 | require CFO + CEO | | hotel: capital investment above EGP 50M (P90) in a state-owned asset (independent feasibility study) |

In the hotel model, capital works are governed by GOV-018 rather than by the GOV-012 implementation-spend cap.

Locked policies cannot be disabled or edited through the API (HTTP 403, tested). Unlocked ones can be toggled by `governance.manage`. Every change bumps the version and is audited.

## 3. Human approval workflow

1. A user with `approval.request` submits a future. Governance is evaluated on the latest persisted run.
2. If the outcome is denied → the request is stored as **blocked**, with the deny reasons (auditable evidence that the gate worked).
3. If acknowledgements are pending (GOV-011) → HTTP 422 until they are acknowledged.
4. Otherwise → **pending**, with `required_roles` taken from the policies. A dry-run "review notification" automation is logged.
5. Approvers record `approve` / `reject` / `request_analysis` for a role they hold. Separation of duties is enforced:
   - the requester cannot approve their own request;
   - one person cannot satisfy two roles;
   - a role cannot approve twice.
6. When every required role has approved, governance is **re-evaluated** before the status becomes `approved`.
7. Approval authorises implementation by accountable people. **The platform executes nothing automatically.**

## 4. RBAC

8 roles × 19 permissions (`security.py`): admin, ceo, cfo, coo, legal, hr, analyst, viewer. For example, the viewer role cannot create, run or approve, and only admins manage users or promote models.

## 5. Agent authority limits

Each `agent_definitions.authority` holds read-only tools, `can_execute=false`, `can_write_external=false`, `max_runtime_seconds=20`. Additional limits:

- per-agent timeout and a whole-pipeline timeout;
- simulation iterations capped at 20 000;
- upload size capped at 5 MB / 50 000 rows;
- login rate limit: 8 attempts per 5 minutes.

## 6. Emergency stop

`POST /admin/emergency-stop` (admin or CEO) sets a tenant flag. The flag cancels queued and running analyses at their next checkpoint, makes new runs return HTTP 423, and shows a red banner in the UI. Every toggle is audited. Individual runs can be cancelled with `POST /runs/{id}/cancel`.

## 7. Automation controls

Dry-run is the default. Each run gets an idempotency key (SHA-256 of workflow, mode and payload, unique in the database), so a replay returns the same run. Policy is checked first (GOV-003 / GOV-014). Live delivery retries with backoff, and a failed delivery records "no compensation required". Every run is audited. The MVP is **read-only** towards ERP systems: the connector interface has no write methods.

## 8. Data protection and AI safety

- **Secrets:** environment only. Connector config rejects keys containing password/secret/token/api_key.
- **Prompt injection:** input is sanitised and length-capped. The question is wrapped as untrusted data in prompts. The LLM has no tools, and its output is display text only.
- **Tenant isolation:** every query is scoped by the authenticated user's tenant (tested with a second tenant).
- **Audit trail:** each `audit_events` row stores `hash = SHA-256(prev_hash + canonical body)`. `GET /admin/audit` verifies the chain.
- **Model governance:** calibration produces *candidate* models. Promotion requires `governance.manage` and a written justification.
- **Legal:** the Legal agent states that it does not provide legal advice and frames contractual exposure as a hypothesis that needs qualified review.
