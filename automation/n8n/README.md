# n8n workflows for Future Mirror AI

Seven ready-to-import n8n workflows, one per automation scenario on the platform's **Automation** page.
Each one starts either from a webhook (what the platform's **Trigger** button calls) or on its own
schedule (times are Cairo time). Each one talks to the platform's API and emails a summary.
Arabic version: [README.ar.md](README.ar.md).

All of them were imported into n8n 1.72.1 (the version in `docker-compose.yml`) and run against the
platform with demo data, with a test mail server receiving the emails.

| File | When it runs | What it does | Emails |
|---|---|---|---|
| `scheduled_analysis.json` | Mondays 06:00 + webhook | Re-runs the analysis of every analysed, non-rejected decision on the latest data. If the webhook sends a `decision_id`, only that decision is re-run | Summary to `FM_N8N_ALERT_EMAIL` |
| `erp_sync.json` | Daily 02:00 + webhook | Syncs cost data, read-only, from every connector whose status is *connected* (D365, SAP, REST, SQL, demo ERP). A change creates a new dataset version | Only when data changed or a sync failed |
| `review_notification.json` | Webhook | Sent when a strategy is submitted for approval: tells approvers which decision and roles | To `FM_N8N_ALERT_EMAIL` |
| `approval_workflow.json` | Sun–Thu 09:00 + webhook | Lists pending approvals and emails each role that still has to approve (CFO, CEO, Legal…) its own list | One email per role (`FM_N8N_ROLE_EMAILS`) |
| `kpi_monitor.json` | Daily 07:00 + webhook | Compares the latest actual results with each decision's forecast band (P10–P90) | Alert only when a KPI is outside its band |
| `post_decision_tracking.json` | 1st of each month 08:00 + webhook | Reminds the team which month of actuals to record for each approved decision. If actuals are POSTed to the webhook, it records them in the platform | Reminder to `FM_N8N_ALERT_EMAIL` |
| `execute_contractor_notice.json` | Webhook | **Consequential scenario, kept safe.** The platform blocks live runs (policies GOV-003 / GOV-014). If one is ever allowed, this workflow only emails HR a request to handle it manually. It never contacts contractors or HR/ERP systems | To `FM_N8N_HR_EMAIL` |

## Setup (once)

1. **Tell the platform where n8n is.** Add this to `.env`:
   ```
   FM_N8N_BASE_URL=http://n8n:5678
   ```
   Optional settings in `.env` (shown with their defaults):
   ```
   FM_N8N_FROM_EMAIL=future-mirror@example.com    # sender address
   FM_N8N_ALERT_EMAIL=approvers@example.com       # summaries and alerts
   FM_N8N_HR_EMAIL=hr@example.com                 # contractor-notice requests
   FM_N8N_ROLE_EMAILS={"cfo":"cfo@company.com","ceo":"ceo@company.com","legal":"legal@company.com"}
   FM_N8N_API_EMAIL=cfo@futuremirror.demo         # platform user n8n logs in as
   FM_N8N_API_PASSWORD=FutureMirror!2026
   ```
   For real use, create a dedicated platform user with the CFO role, or another role with `automation.run`, `dataset.write`, `decision.run` and `outcome.record`, and put its login here.

2. **Start the app with n8n:**
   ```
   docker compose --profile automation up -d --build
   ```
   n8n opens on http://localhost:5678. The first time, it asks you to create an owner account.

3. **Add the email account.** In n8n, go to **Credentials → Add credential → SMTP** and enter, for example:
   - Office 365: host `smtp.office365.com`, port `587`, SSL/TLS off, your user and password.
   - Gmail: host `smtp.gmail.com`, port `465`, SSL/TLS on, and an app password, not your normal password.

4. **Import the workflows.** In n8n, go to **Workflows → Add workflow → ⋯ → Import from File**, once per JSON file. Or import all seven at once from the project folder:
   ```
   docker compose cp automation/n8n n8n:/tmp/fm-workflows
   docker compose exec n8n n8n import:workflow --separate --input=/tmp/fm-workflows
   docker compose --profile automation restart n8n
   ```

5. **Finish each workflow.** Open it, click the email node, choose the SMTP credential from step 3, click **Save**, then switch **Active** on (top right). Webhooks and schedules only work while a workflow is active.

## Testing

- **From the platform:** on the **Automation** page, choose a workflow and trigger it with dry-run off. The run shows **delivered**, and n8n's **Executions** list shows the run.
- **From a terminal:**
  ```
  curl -X POST http://localhost:5678/webhook/future-mirror/kpi_monitor -H "Content-Type: application/json" -d "{}"
  ```
- **Recording actuals through the webhook:**
  ```
  curl -X POST http://localhost:5678/webhook/future-mirror/post_decision_tracking -H "Content-Type: application/json" \
    -d "{\"decision_id\":\"<id>\",\"actuals\":[{\"month\":4,\"metric\":\"opex_monthly\",\"value\":8.1}]}"
  ```
  The metrics are `opex_monthly`, `revenue_monthly`, `savings_run_rate`, `delay_pct`, `utilization_pct`, `csat_pct` and `cash_balance`.

Workflows that find nothing to report (no changes, no breaches, no pending approvals) finish without sending an email.

## Safety

- The workflows only read data. The only things they change in the platform are starting analysis runs, creating dataset versions from read-only syncs, and recording actuals.
- No workflow writes to an ERP, HR or other business system.
- Consequential actions stay blocked by the platform's governance policies.
- n8n data (workflows, credentials) is included in every backup made with `ops\backup.bat`.
