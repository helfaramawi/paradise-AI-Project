# HAQQ — Known Limitations & Risk Register

## Limitations (honest status)
| # | Area | Limitation |
|---|---|---|
| L1 | Accuracy | The contract engine is rule-based and was evaluated on a **small synthetic** gold set (19 clauses) and the demo contract. Accuracy on real, varied Egyptian contracts is **unmeasured**; expect misses on unusual numbering, tables, and multi-column scans. Human verification of clauses is built in for this reason. |
| L2 | OCR | Tesseract quality depends on scan quality; handwriting is not supported; Arabic OCR of poor scans may be noisy. |
| L3 | DOCX/e-mail pages | No fixed pagination → page numbers are estimated and labelled as such. |
| L4 | Semantics | Local embeddings are lexical-semantic (feature hashing), not neural. |
| L5 | Deadlines | Triggers are counted from the recorded awareness/event date; contract-wide definitions of "day" are not read automatically (flagged as an assumption). No built-in Egyptian holiday calendar. |
| L6 | Delay analysis | HAQQ does not perform critical-path analysis; EOT/prolongation always require an expert programme analysis. |
| L7 | LLM | Anthropic integration implemented and unit-tested with a test double; **not exercised against the live API** in this environment. Other providers need an adapter. |
| L8 | Docker | Images not built/verified in the development sandbox (no package-mirror access). Native stack verified. |
| L9 | Notifications | E-mail requires SMTP configuration; deadline scans are triggered via API/UI (no internal scheduler yet). |
| L10 | Storage | Local filesystem backend only; no at-rest encryption beyond the host disk; no antivirus scanning. |
| L11 | Scale | In-process rate limiter; single-queue worker; no load testing performed. |
| L12 | Retention / PDPL | Retention period stored but not enforced automatically; data-subject request workflow not built. |
| L13 | Billing | No payment gateway; manual invoicing only. |
| L14 | UI | Business units have no UI; no in-browser PDF page viewer with highlights (text view per page instead). |

## Risk register
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Users treat potential entitlements as guaranteed revenue | Medium | High | Status ceiling, disclaimers on every screen/export, human gates |
| Missed time-bar because a clause was not extracted | Medium | High | Clause verification workflow, "no notice clause identified — verify manually" deadlines, accuracy programme |
| Customer data confidentiality objections | High | High | AI off by default, per-tenant policy, Egyptian/regional hosting option, audit logs |
| Prompt injection via documents | Low | Medium | Deterministic core, wrapped excerpts, citation validation, upload flagging |
| Tenant data leakage | Low | Critical | Central scoping helpers, 404 semantics, isolation tests in CI |
| Pricing not validated | High | Medium | Two pilots before scaling spend; metered usage informs plan design |
| Regulatory (PDPL 151/2020) | Medium | High | Legal review before compliance claims; DPA templates; retention enforcement on roadmap |
| Key-person / AI cost overrun | Low | Medium | Deterministic engines, token metering and plan allowances |
