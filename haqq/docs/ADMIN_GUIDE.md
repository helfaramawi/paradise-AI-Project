# HAQQ — Administrator Guide

## Organisation onboarding
Self-service at `/register` creates the organisation, its administrator and a 30-day trial; the wizard then asks for
weekend days, VAT and the **AI data policy**, and the first project.

## Users & roles (Administration → Users & roles)
Add users with one of 8 roles; the permission matrix is shown on the page. Leadership, contracts, finance and legal
roles see all projects; **project managers and site engineers see only projects they are assigned to**
(Project → team, or `POST /projects/{id}/members`). Deactivate leavers (their sessions stop working immediately).
Administrators cannot deactivate or demote themselves.

## Organisation settings
* **Weekend days & public holidays** — drive every working-day deadline. Enter Egyptian public holidays each year
  (one ISO date per line); HAQQ does not ship an official holiday calendar.
* **VAT rate** — default for valuations (VAT is applied only when ticked on a valuation).
* **AI data policy** — off by default. When on *and* the platform has an LLM provider configured, short cited
  excerpts may be sent to the external model for narratives/Q&A. Every call is logged in `ai_runs`.
* **Data retention (days)** — recorded policy; automated purge is on the roadmap.
* **Security** — each user can enable TOTP two-factor authentication.
* **Audit trail** — hash-chained log of all significant actions; **Verify integrity** recomputes the chain.
  Document views/downloads are logged separately (`/audit/document-access`).

## Subscription & usage
Shows plan, status, renewal, usage vs limits (users, projects, documents, pages, AI tokens) and billing records.
Exceeding a limit returns a clear "limit reached" message (HTTP 402).

## Platform operator (PAIS)
Set `HAQQ_PLATFORM_ADMIN_EMAIL/PASSWORD` to create the operator account; it sees **PAIS commercial** (paying
customers, MRR, progress to the EGP 1M MRR target, trials; demo organisations excluded).

## Demo data
`python -m app.demo.seed` creates the DEMO organisation (`*@haqq.demo`, password `HaqqDemo!2026`); `--reset` recreates
it. Everything is flagged and labelled DEMO. Do not load demo data into a customer's production tenant.

## Troubleshooting
* Document stuck in *Queued*: check `/api/health/ready` (`queued_jobs`) and that a worker is running.
* Scanned PDF has no text: check `ocr: available` in readiness; install `tesseract-ocr-ara`.
* No e-mails: readiness shows `email: not_configured` until SMTP is set.
