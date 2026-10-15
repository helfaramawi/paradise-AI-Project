# Demo Script — "Experience Tomorrow Before You Decide Today"

**Duration:** about 12 minutes. **Stack:** `docker compose up -d` → http://localhost:8080. **Data:** synthetic and labelled as such.
Have two browser profiles ready: **Analyst** (`analyst@futuremirror.demo`) and **CFO** (`cfo@futuremirror.demo`). The password for both is `FutureMirror!2026`.

The whole sequence is automated in `frontend/e2e/demo.spec.ts`, which produced the screenshots in `docs/screenshots/`.

---

### Scene 1 — The Executive Question (Decision Intake Wizard)
1. Sign in as the Analyst. Point out the header chips: **Synthetic data · Rule-based agents · no LLM · External actions disabled**. The platform is telling you exactly what is real.
2. Go to **New Decision** → *Use the demonstration scenario*. The 20% / six months / no-terminations question appears.
3. **Interpret question.** The parser detects the target, timeline, cost base and the constraint flags (*no terminations, protect delivery, contracts, CSAT*). Stress that every field is confirmed by the human.
4. Step 3 shows the executive controls; step 4 shows the dataset. Note the **data quality error** badge: the brief itself is inconsistent (gross margin vs cost base). Then click **Create decision & awaken the agents**.

### Scene 2 — The Agents Awaken (Live Execution Room)
- Real Server-Sent Events from the backend: stages light up, and seven agents run **in parallel** (LangGraph fan-out).
- Point at **Compute time** (about 1 second) versus **Presentation pacing**. The visible pauses are disclosed and excluded from compute time, so nothing is faked.
- The feed shows warnings (DQ-002, DQ-005), the Monte Carlo line with its seed and fingerprint, objections, collisions and policy decisions.

### Scene 3 — The Agent Court
- **Enter the Agent Court.** The banner states that every statement was computed in this run, not scripted.
- Use *Replay debate* to walk the rounds: positions on each future → Red Team cross-examination → collisions → governance.
- Highlight the CFO supporting Future A on savings and the Delivery agent opposing it ("could delay 4 of 18 projects", from the SimPy simulation). Then the Red Team: *"assumes internal employees possess the required skills… unsupported"*, with the quantified downside.
- Open *Agent positions* to show evidence chips referencing exact dataset and simulation paths, plus claim types (Fact / Estimate / Assumption / Hypothesis).

### Scene 4 — The Future Collision
- Open the **Future Collision Detector** tab. COL-01: contractor savings collide with delivery commitments, with CFO, Delivery, HR and Legal positions, consequences, severity score and alternative resolutions. COL-02: the 20% target collides with the no-termination constraint.

### Scene 5 — The Three Futures
- **Three Futures:** A 14.5% (delivery breach), B 9.4% (delivery protected), C 12.1% (transition risk), each with P10–P90 bands and constraint chips.
- Move **Implementation timeline** to 12 months or **Cost reduction target** to 10%. The model recalculates in about 150 ms ("What-if mode"). Show the input fingerprint changing.

### Scene 6 — The Time Machine
- **Decision Time Machine:** press *Play*, or click Today → Month 1 → 3 → 6 → 12. The tiles show modelled cost, revenue, cash, delay, utilisation, CSAT and risk exposure for the selected future, with deltas against today. The comparison table shows all futures at the same month.

### Scene 7 — The Governance Gate
- **Approval Center:** select Future A. It is **denied** by GOV-009 (a critical collision), even though the CFO agent supports it. Show the *AI Governance* screen: 14 policies, locked non-negotiables, and the sandbox (paste an agent `execute` request → denied by GOV-002).
- Select Future B. It requires **CFO · CEO · Legal**. Tick the data-quality acknowledgement (GOV-011) and submit.

### Scene 8 — The Executive Decision
- Switch to the CFO profile → Approval Center → **Approve** (separation of duties: the Analyst who requested cannot approve; one person, one role). The remaining roles stay pending until Legal and the CEO sign.
- Download the **PDF report** (also in Arabic) and the **Excel workbook** from any decision page.
- Optionally show **Actual vs Predicted**: generate labelled synthetic actuals. Delay lands above the P90 band, so the diagnostic says *"skill match / delay elasticity assumptions appear optimistic"*. **Propose model recalibration** creates a *candidate* model that needs admin approval before it can affect any decision.

### Closing (switch to Arabic)
Click **العربية**. The whole cockpit mirrors to RTL with Arabic numerals, and the bilingual agent findings switch language.

> "Future Mirror AI didn't tell us to cut 20%. It showed us that 20% isn't realistic without breaking a protected constraint, quantified what *is* achievable, exposed the assumption everyone was making, and refused to let any agent act without the right humans signing off."
