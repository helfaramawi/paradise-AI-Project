# n8n workflow examples

Import these into n8n (Workflows → Import from file). The backend posts to
`{FM_N8N_BASE_URL}/webhook/{automation_workflows.n8n_webhook_path}` with an `idempotency_key`
in the body. Only notification-style workflows are provided; workflows that would change
business systems are deliberately **not** included, and the platform blocks consequential
live runs by policy (GOV-003 / GOV-014).

| File | Webhook path | Effect |
|---|---|---|
| decision_review_notification.json | future-mirror/review_notification | emails approvers (configure SMTP credentials in n8n) |

Status: the workflow JSON is provided as a template. It has not been executed against a live n8n
instance in the build environment.
