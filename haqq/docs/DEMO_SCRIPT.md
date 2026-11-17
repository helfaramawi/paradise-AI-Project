# HAQQ — Live Business Demonstration (15 minutes)

**Message:** *"You may have entitlements you have not claimed. HAQQ helps you find them before it is too late."*
All data is fictional DEMO data; amounts are illustrative, not proven claims or guaranteed recoveries.

| # | Time | Screen (login `commercial@haqq.demo` / `HaqqDemo!2026`) | Say / show |
|---|---|---|---|
| 1 | 0:00 | Dashboard (Arabic) | Portfolio EGP 138M; **potential entitlements EGP 9.5M**; revenue at risk; deadlines; drill into *Revenue at risk*. Toggle English. |
| 2 | 2:00 | Projects → NAC-01 (EGP 100M) → Documents | Contract PDF, Arabic particular conditions (Word), BOQ (Excel), **scanned site instruction read by OCR**, minutes, letters, e-mail. Open SI-014 to show the OCR text. Optionally upload a new file live. |
| 3 | 4:00 | Clauses | 24 clauses with pages; time limits — 28-day time-barred notice (20.1, English GC) vs **21 days in the Arabic PC**; *Ask the contract*: "ما مهلة الإخطار بالمطالبات؟". |
| 4 | 6:00 | Events → EV-001 → Discover | Additional water tank instructed by the engineer. |
| 5 | 7:00 | ENT-001 | **EGP 2,000,000** variation (valuation from BOQ rates) · Clause 13.1 quoted · evidence found (SI-014, MoM-22, BOQ, daily report) · **contractor notice missing** · **notice due in 7 days** (estimated — day type unstated) · recommended action #1. Clause 13.2's limitation shown and resolved by the written instruction. |
| 6 | 9:00 | Valuation worksheet | Lines with BOQ references, formulas; verify as CFO to show separation of duties. |
| 7 | 10:30 | Prepare claim → Generate | Arabic notice letter (Word) and English claim package (PDF): clauses, chronology, evidence index, financial breakdown, missing information, draft banner. *HAQQ never sends it.* |
| 8 | 12:00 | ENT-005 (steel escalation) | HAQQ **does not** assume escalation is recoverable: Clause 13.7 exclusion → *requires expert verification*. Credibility moment. |
| 9 | 13:00 | ENT-002 (Zone B delay) | Conflicting notice periods flagged *ambiguous*; EOT not concluded — programme analysis missing. |
| 10 | 14:00 | Deadline calendar / WH-02 claims | Claim pipeline through to collection; approved vs collected. Close with the pilot offer. |

Reset before each demo: `python -m app.demo.seed --reset`.

## Recorded video with Arabic voice-over

`ops\record-demo.bat` records a ~10-minute Arabic walkthrough of the real app (10 chapters following the table
above, captions and chapter cards rendered in the browser) into `docs/video/haqq-demo-ar.mp4` plus the narration
`haqq-demo-ar.srt`. `ops\make-voiceover.bat` (or `make-voiceover.bat female`) then speaks each caption with Microsoft's
Egyptian neural voices (`ar-EG-ShakirNeural` / `ar-EG-SalmaNeural`, needs internet), adds the calm background music
low under the voice and writes `docs/video/haqq-demo-ar-voice.mp4`. Details: `docs/OPERATIONS_GUIDE.md` §5.
Videos are not committed to Git (size); keep the final MP4 in your shared drive.
