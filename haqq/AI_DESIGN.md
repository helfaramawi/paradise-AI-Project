# HAQQ — AI Design

## 1. Principle: deterministic intelligence first, language models second

HAQQ's findings are produced by **deterministic, testable engines** (`backend/app/engines/`). A large language model
is an *optional* layer that explains and answers questions **with citations**, under the tenant's data policy.
Consequences:

* Clause numbers, page references, periods, due dates and amounts can never be hallucinated — they are extracted
  from text or computed by code.
* The product works fully with `HAQQ_LLM_PROVIDER=none` (the default), and for tenants who forbid external AI.
* Every engine is versioned (`contract-rules-1.2`, `entitlement-1.3`, `deadline-1.1`, `valuation-1.0`) and its version
  is stored with each finding.

## 2. Capabilities and where they live

| # | Capability | Implementation |
|---|---|---|
| 1 | Document ingestion | `services/pipeline.py`, DB job queue |
| 2 | OCR & extraction | `engines/extraction.py` — pdfplumber text layer; Tesseract `ara+eng` at 300 dpi for pages < 40 chars and images; python-docx; openpyxl; e-mail |
| 3 | Document classification | `engines/contract.classify_document` — bilingual weighted keyword scoring (16 types), declared type wins |
| 4 | Clause extraction | `engines/contract.segment_clauses` — EN headings (`Clause/Sub-Clause/Article 13.1`, numbered titles), AR headings (`المادة (8)`, ordinal words), numbered paragraphs; guards against wrapped cross-references and tables of contents |
| 5 | Clause analysis | categories (18), obligations, rights, conditions, exclusions, time limits (digits, English & Arabic number words, Arabic-Indic digits, weeks), day type, trigger wording, time-bar detection, percentages, risk flags |
| 6 | Semantic search / RAG | local hashed embeddings in pgvector (HNSW) + BM25 re-ranking; `POST /projects/{id}/ask` |
| 7 | Event classification | `engines/entitlement.classify_event` — suggestion only; user choice prevails |
| 8 | Contract–event correlation | `rank_clauses`: 0.55·category fit (event→clause weight table) + 0.30·BM25 + 0.15·vector similarity |
| 9 | Entitlement detection | `engines/entitlement.discover` (below) |
| 10 | Financial calculation | `engines/valuation.py` — Decimal, formulas per step |
| 11 | Claim drafting | `services/claimdocs.py` — templated DOCX/PDF/XLSX from structured, cited data |
| 12 | Explainability | explanation items each with a citation (document, page, verbatim quote) or flagged as gap/assumption |

## 3. The entitlement discovery algorithm

For each entitlement type implied by the event category:
1. **Candidate clauses** = clauses in the type's core categories, or in the event's primary categories that
   contain entitlement wording relevant to the type.
2. **Primary clause** = the best candidate that *confers* a right ("shall be entitled", "يحق للمقاول"…);
   procedural or limiting clauses become *related* clauses. Below a 0.45 match → no contractual basis identified →
   `requires_expert_verification`.
3. **Evidence rules** (`taxonomy.EVIDENCE_RULES`) per type, each requirement critical or supporting, satisfied only by
   **user-confirmed** linked documents of matching type (and author, e.g. a *contractor* notice).
4. **Exclusions** from the primary clause and same-category related clauses. Conditional limitations are resolved
   when the condition is evidenced (e.g. "no payment without written instruction" + written instruction on file);
   time-bar sentences are handled by the notice logic rather than as blanket exclusions.
5. **Notice & detailed-claim deadlines**: from the primary clause first, then claims clauses; differing periods across
   documents (e.g. 28 days EN general conditions vs 21 days AR particular conditions) → shortest used, certainty
   `ambiguous`; unspecified day type → calendar days assumed (conservative), certainty `estimated`; trigger counted
   from the recorded awareness/event date with an explicit assumption note. Contractor notice on file → given on
   time / late.
6. **Quantification**: verified valuation › draft valuation › user estimate (flagged unverified) › not quantified.
7. **Status** (never above *potential*): no clause → expert verification; blocking exclusion, or overdue notice with
   time-bar → expert verification; missing critical evidence → insufficient evidence; else potential.
   *Substantiated* requires a human, a verified valuation and no missing critical evidence. EOT is never concluded.
8. **Confidence** = 0.35·clause match + 0.30·evidence completeness + 0.15·classification + 0.10·notice clarity +
   0.10·quantification − penalties (exclusion 0.15, contradiction 0.10); shown with its breakdown.
9. **Contradictions**: non-contractor documents containing rejection language; oral-instruction wording.

## 4. LLM layer (`backend/app/ai/`)

* **Provider abstraction** (`providers.py`): `LLMProvider.structured(system, user, schema, max_tokens)`. Implemented:
  `none` (default) and `anthropic` (official Anthropic Python SDK, `client.messages.parse` with a Pydantic
  `output_format`, model `claude-opus-5-5` by default via `HAQQ_LLM_MODEL`, `effort` configurable, server-side refusal
  fallback enabled, typed error handling, SDK retries). Other providers plug in behind the same protocol.
* **Prompt registry** (`prompts.py`): id + version + system prompt + output schema (`entitlement_narrative`,
  `contract_qa`).
* **Task runner** (`service.py`): enforces the tenant policy (`ai_external_processing`), logs every call in `ai_runs`
  (provider, model, prompt version, tokens, latency, input hash, status), meters tokens, and **rejects any output
  that cites a source id that was not supplied** (`invalid_output`).
* **Prompt-injection defence** (`guard.py`): documents are scanned on upload (EN/AR patterns) and flagged in the UI;
  excerpts sent to a model are wrapped in labelled delimiters (look-alike delimiters are neutralised) and the system
  prompt instructs the model to treat them as inert evidence.
* The LLM never computes money or dates and its narrative is labelled "requires human verification".

## 5. Learning from outcomes (designed, not automated)
Human decisions are stored (clause verification, entitlement review with comment, claim outcomes with approved /
collected amounts). They are the future training/evaluation signal. Rejected or unverified items are **not** treated
as ground truth; the gold set is curated by hand.

## 6. Evaluation
`backend/eval/clause_gold.json` (19 labelled EN/AR clauses) + `python -m eval.run_eval` report category, notice period,
time-bar, exclusion and payment-period accuracy; `tests/test_eval.py` gates regressions. Current: 100 % on all
metrics after fixing two Arabic misses the evaluation found. **Caveat:** the set is small and synthetic; real contract
accuracy must be measured on pilot-customer documents before any accuracy claim is made.
