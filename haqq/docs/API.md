# HAQQ — API Reference

Base path `/api/v1`. Authentication: `Authorization: Bearer <access_token>` from `POST /auth/login`.
Interactive OpenAPI docs: `/api/docs`; machine-readable schema: `/api/openapi.json`.
Errors: JSON `{detail}`; foreign-tenant ids return **404**; missing permission **403**; plan limits **402**; rate limits **429**.


## auth

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/logout` | Logout |
| GET | `/api/v1/auth/me` | Me |
| POST | `/api/v1/auth/mfa/enable` | Mfa Enable |
| POST | `/api/v1/auth/mfa/setup` | Mfa Setup |
| POST | `/api/v1/auth/password` | Change Password |
| POST | `/api/v1/auth/register` | Register |

## claims

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/claim-documents/{doc_id}/download` | Download |
| GET | `/api/v1/claims` | List All Claims |
| GET | `/api/v1/claims/stages` | Stages |
| GET | `/api/v1/claims/{claim_id}` | Get Claim |
| POST | `/api/v1/claims/{claim_id}/documents` | Generate |
| POST | `/api/v1/claims/{claim_id}/transition` | Do Transition |
| GET | `/api/v1/projects/{project_id}/claims` | List Claims |
| POST | `/api/v1/projects/{project_id}/claims` | Create Claim |

## contract-intelligence

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/clauses/{clause_id}` | Get Clause |
| POST | `/api/v1/clauses/{clause_id}/verify` | Verify Clause |
| POST | `/api/v1/projects/{project_id}/ask` | Ask Contract |
| GET | `/api/v1/projects/{project_id}/clauses` | List Clauses |
| GET | `/api/v1/projects/{project_id}/clauses/summary` | Clause Summary |

## dashboard

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/dashboard/executive` | Executive |
| GET | `/api/v1/meta/taxonomy` | Taxonomy |
| GET | `/api/v1/reports/portfolio.xlsx` | Portfolio Export |

## deadlines

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/deadlines` | All Deadlines |
| POST | `/api/v1/deadlines/scan` | Scan |
| PATCH | `/api/v1/deadlines/{deadline_id}` | Update Deadline |
| GET | `/api/v1/notifications` | Notifications |
| POST | `/api/v1/notifications/read-all` | Read All |
| GET | `/api/v1/projects/{project_id}/deadlines` | Project Deadlines |
| POST | `/api/v1/projects/{project_id}/deadlines` | Create Deadline |

## documents

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/documents/{doc_id}` | Get Document |
| PATCH | `/api/v1/documents/{doc_id}` | Update Document |
| GET | `/api/v1/documents/{doc_id}/download` | Download |
| GET | `/api/v1/documents/{doc_id}/pages` | Pages |
| POST | `/api/v1/documents/{doc_id}/reprocess` | Reprocess Document |
| GET | `/api/v1/projects/{project_id}/boq` | Boq |
| GET | `/api/v1/projects/{project_id}/documents` | List Documents |
| POST | `/api/v1/projects/{project_id}/documents` | Upload |
| GET | `/api/v1/projects/{project_id}/search` | Search |

## entitlements

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/entitlements` | List All |
| GET | `/api/v1/entitlements/{ent_id}` | Get Entitlement |
| POST | `/api/v1/entitlements/{ent_id}/narrative` | Narrative |
| POST | `/api/v1/entitlements/{ent_id}/review` | Review |
| GET | `/api/v1/entitlements/{ent_id}/valuation` | Get Valuation |
| PUT | `/api/v1/entitlements/{ent_id}/valuation` | Put Valuation |
| POST | `/api/v1/entitlements/{ent_id}/valuation/verify` | Verify Valuation |
| POST | `/api/v1/events/{event_id}/discover` | Discover Event |
| POST | `/api/v1/projects/{project_id}/discover` | Discover Project |
| GET | `/api/v1/projects/{project_id}/entitlements` | List Entitlements |

## events

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/events/classify` | Classify |
| GET | `/api/v1/events/{event_id}` | Get Event |
| PATCH | `/api/v1/events/{event_id}` | Update Event |
| POST | `/api/v1/events/{event_id}/clauses/{clause_id}/confirm` | Confirm Clause |
| POST | `/api/v1/events/{event_id}/documents` | Link Document |
| DELETE | `/api/v1/events/{event_id}/documents/{doc_id}` | Unlink Document |
| GET | `/api/v1/events/{event_id}/suggested-documents` | Suggested |
| GET | `/api/v1/projects/{project_id}/events` | List Events |
| POST | `/api/v1/projects/{project_id}/events` | Create Event |

## organization

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/audit` | Audit Log |
| GET | `/api/v1/audit/document-access` | Doc Access |
| GET | `/api/v1/audit/verify` | Audit Verify |
| GET | `/api/v1/org` | Get Org |
| PATCH | `/api/v1/org` | Update Org |
| GET | `/api/v1/plans` | Plans |
| GET | `/api/v1/platform/commercial` | Commercial Report |
| GET | `/api/v1/roles` | Roles |
| GET | `/api/v1/subscription` | Subscription |
| GET | `/api/v1/users` | List Users |
| POST | `/api/v1/users` | Create User |
| PATCH | `/api/v1/users/{user_id}` | Update User |

## projects

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/projects` | List Projects |
| POST | `/api/v1/projects` | Create Project |
| GET | `/api/v1/projects/{project_id}` | Get Project Detail |
| PATCH | `/api/v1/projects/{project_id}` | Update Project |
| POST | `/api/v1/projects/{project_id}/members` | Add Member |
| DELETE | `/api/v1/projects/{project_id}/members/{user_id}` | Remove Member |

## system

| Method | Path | Summary |
|---|---|---|
| GET | `/api/health` | Health |
| GET | `/api/health/ready` | Ready |
