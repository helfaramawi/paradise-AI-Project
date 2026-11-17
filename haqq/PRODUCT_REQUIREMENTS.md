# HAQQ — Product Requirements

## Positioning
Not a contract-management or document system: **an AI revenue-protection and contractual-entitlement discovery
platform for construction contractors**, Egypt first, Arabic + English. Five customer benefits: discover hidden
entitlements; reduce revenue leakage; protect contractual deadlines; build stronger claims; give management financial
visibility. HAQQ distinguishes **potential entitlement → substantiated claim → submitted → approved → collected cash**
and never promises recovery.

## Personas & roles (implemented as RBAC roles)
| Persona | Role code | Primary screens |
|---|---|---|
| CEO / MD | `ceo` | dashboard, approvals for submission |
| CFO | `cfo` | dashboard, valuation verification, approved vs collected, subscription |
| Commercial Director | `commercial_director` | entitlement review, claims pipeline, everything commercial |
| Contracts Manager | `contracts_manager` | clauses, discovery, valuation, claim preparation, deadlines |
| Project Manager | `project_manager` | assigned projects: events, evidence, actions |
| Site Engineer | `site_engineer` | assigned projects: upload reports/photos, record events |
| Legal Reviewer | `legal_reviewer` | clause verification, legal review stage, entitlement review |
| System Administrator | `admin` | users, settings, AI policy, audit, subscription |
| PAIS operator | `is_platform_admin` flag | commercial (MRR) report |

## Modules (A–H) — scope delivered in the MVP
* **A Enterprise & projects** — orgs (isolated), onboarding wizard, projects with employer/engineer/contract data,
  team assignment, portfolio. *Business units* exist in the model; no UI yet.
* **B Contract intelligence** — upload any contract format incl. scans; OCR; classification; clause repository with
  number, title, verbatim text, page, document, category, obligations, rights, conditions, notice/time limits, time
  bars, payment terms, retention/LD percentages, risk flags, confidence, verification status; contract Q&A.
* **C Event intelligence** — register with all fields (ID, project, dates, category, party, activities, documents,
  cost/time estimates, related clauses, status, reviewer); AI category suggestion; document suggestions; correlation.
* **D Entitlement discovery** — the 15 outputs required (ID, references, trigger, clause, conditions, evidence available
  / missing, financial and time impact, notice requirement, deadlines, risk, confidence, next action, review status)
  plus "Why did HAQQ identify this?" with citations; five statuses.
* **E Valuation** — cost categories (direct, labour, equipment, material, subcontractor, site overheads,
  prolongation, other), EGP primary + FX, configurable VAT, assumptions, formulas, sources, verification.
* **F Claims** — 13 required workflow steps (modelled as 15 stages incl. rejected/closed), role gates, generation of
  notice letters (delay / variation / generic) and full claim packages (narrative, chronology, evidence index,
  financial breakdown, missing information, assumptions, review status) in AR/EN DOCX/PDF + XLSX worksheet. Never sent.
* **G Deadlines** — notice, detailed claim, payment and manual deadlines; working/calendar days; triggers;
  ambiguity; assignment; escalation levels; in-app + e-mail (SMTP) notifications.
* **H Executive dashboard** — all 12 required KPIs (+1) and the 10 required visualisations, each drillable.

## Acceptance scenarios (PRD §13) → see TESTING_STRATEGY.md traceability. All 8 automated and passing.

## Non-goals for the MVP
ERP / Microsoft 365 / P6 integrations, mobile app, voice capture, payment gateway, benchmarking, predictive risk —
see `docs/ROADMAP.md`.
