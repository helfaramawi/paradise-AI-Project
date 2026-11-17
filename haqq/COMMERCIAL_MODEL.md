# HAQQ — Commercial Model

## Positioning
Sold as **revenue protection for contractors**, not contract management. The buyer is the CEO/CFO/Commercial
Director; the value story is "potential entitlements you have not claimed, and deadlines about to time-bar them".

## Pricing hypotheses (to validate — not established market prices)
| Plan | EGP / month | EGP / year (≈10 % discount) | Users | Projects | Documents / month |
|---|---:|---:|---:|---:|---:|
| Project | 10,000 | 108,000 | 5 | 1 | 300 |
| Business | 20,000 | 216,000 | 20 | 5 | 1,500 |
| Enterprise | 40,000 | 432,000 | 100 | 50 | 10,000 |

Limits are enforced in the product (`plans` table, `check_limit`), usage is metered (documents, pages, OCR pages,
AI tokens, claim documents) and a 30-day trial starts at sign-up. Billing is manual invoicing; a payment-gateway
adapter (e.g. Paymob/Fawry) plugs into `BillingProvider`.

## Target
50 paying customers × EGP 20,000 average = **EGP 1,000,000 MRR** — a business goal, not a forecast. Progress is
tracked live in the PAIS commercial report (`/platform`, demo organisations excluded).

## Unit-economics guardrails
* Default deterministic engines → near-zero variable AI cost; LLM features are opt-in and metered against plan
  token allowances.
* OCR is CPU-bound; price large scanned archives as onboarding services.

## Go-to-market (recommended)
1. **Two pilot customers first** (mid-size contractors with ≥ 3 active projects). Success criterion: each pilot sees
   at least one finding it agrees is a credible, previously unnoticed potential entitlement or at-risk notice deadline.
2. Live demo script: `docs/DEMO_SCRIPT.md` (EGP 100M contract → EGP 2M potential entitlement, 7 days to notice).
3. Convert pilots to annual Business plans; collect permission-based anonymised outcomes to improve the engine.
4. Do not spend the full budget before pilots prove a clear financial value story.

## Messaging rules
Always say *potential* entitlement; separate potential / substantiated / submitted / approved / collected; never
guarantee recovery; state that HAQQ supports, and does not replace, contracts and legal professionals.
