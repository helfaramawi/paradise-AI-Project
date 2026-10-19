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

---

## Recording the Arabic demo video

`frontend/e2e/video/record-demo-ar.mjs` records a 12–15 minute Arabic product video from the **real running app**. It covers 16 chapters: sign-in, Command Center, Intake, Live Execution, Agent Court, Three Futures, Time Machine, Financial/Risk/Lab, approvals with separation of duties, Actual vs Predicted, history and reports, Data Connections, Automation, Governance, Administration, and language/theme.

- The browser renders the Arabic captions, chapter cards, a visible cursor and a progress bar, so Arabic shaping and right-to-left layout are exact.
- Frames come from Chrome's screencast and are encoded live to 1080p H.264 by ffmpeg, at a constant 25 fps.
- Outputs: `future-mirror-demo-ar.mp4`; `future-mirror-demo-ar.srt` (timed narration, usable as subtitles or as a voice-over script); `chapters.txt` (YouTube-style chapter list).

```bash
# 1. Start a fresh demo stack (any of: docker compose on :8080, or uvicorn + vite on :5173)
# 2. Record (needs ffmpeg and the Playwright Chromium)
cd frontend
BASE_URL=http://localhost:5173 OUT_DIR=../docs/video node e2e/video/record-demo-ar.mjs
```

Use a fresh database, because the script creates a decision and submits it for approval.

### Adding the Arabic voice-over

`scripts/voiceover/make_voiceover.py` speaks every SRT line at its caption time with a natural neural voice, and muxes the result into a new MP4 without re-encoding the picture. The default voice is Microsoft's Egyptian Arabic male voice, `ar-EG-ShakirNeural`, through the free `edge-tts` service.

- Speech is never sped up. When a line needs more time than its caption is on screen, the picture is held (the caption stays visible) until the line finishes, plus a short pause. Everything after it shifts later, and a matching `-voice.srt` is written.
- The audio is loudness-normalised to -16 LUFS.
- An HTTPS proxy in the environment is used automatically.

**Windows:** put `future-mirror-demo-ar.mp4` and `.srt` in `docs\video`, then double-click `ops\make-voiceover.bat` (`make-voiceover.bat female` for `ar-EG-SalmaNeural`). It needs Python and FFmpeg (`winget install -e --id Python.Python.3.12`, `winget install -e --id Gyan.FFmpeg`). **macOS/Linux:** `ops/make-voiceover.sh [female]`.

**Background music (optional):** save a track as `docs/video/music.mp3` (or `.m4a`/`.wav`), and the launchers pick it up automatically (or pass `--music file`). It is normalised, kept 18 dB below the voice (`--music-volume -24` for quieter, `-14` for louder), looped, faded in and out, and ducked about 12 dB more while the narrator speaks. Use music you have the rights to: commercial tracks will be blocked or muted by Content ID on public platforms, so use royalty-free music, such as the YouTube Audio Library.

Output: `docs/video/future-mirror-demo-ar-voice.mp4`. For fully offline use, choose `--engine piper --piper-model ar_JO-kareem-medium.onnx`. `--engine dummy` tests the timing without any TTS service.

## Port Said Free Zone demo: the collection-agency question

`frontend/e2e/video/record-demo-collections.mjs` records a second demo of the same length. It is set at the Executive Authority of the Port Said Free Zone (الجهاز التنفيذي للمنطقة الحرة ببورسعيد). It types and analyses the question «ماذا لو حققنا متحصلات إيرادات أكبر بنسبة 30 % من خلال التعاقد مع شركة تحصيل؟», which runs on the **revenue collections** decision model. The video covers the same 16 chapters, now with the collections results:

- No future reaches 30%; about 9.5% is achievable, because an agency only works on the overdue book.
- Full outsourcing breaks the complaint, satisfaction and key-account constraints, and is blocked by the fair-collection policy (GOV-016).
- The hybrid future needs Legal approval because customer data is shared with an agency (GOV-015).

The captions are in Modern Standard Arabic with full diacritics (tashkeel), so the voice reads them as written. The narration says that all figures are illustrative sample data, not the Free Zone's real numbers.

```bash
cd frontend
BASE_URL=http://localhost:8080 OUT_DIR=../docs/video node e2e/video/record-demo-collections.mjs
```

The outputs are `future-mirror-demo-collections.mp4`, `future-mirror-demo-collections.srt` and `chapters-collections.txt`. Use a fresh database.

**Voice-over with a female voice (`ar-EG-SalmaNeural` by default):**

- **Windows:** put both files in `docs\video` and double-click `ops\make-voiceover-collections.bat`. The output is `docs\video\future-mirror-demo-collections-voice.mp4`.
- **Another female voice:** `ops\make-voiceover-collections.bat ar-SA-ZariyahNeural` uses the Saudi female voice, which some listeners prefer for Modern Standard Arabic. The video was paced for Salma, so a different voice may freeze the picture a little more often.
- **Speed:** Salma reads diacritised text slowly, so the launcher speaks 10% faster (`FM_VOICE_RATE=10`); the video was paced for that speed. To change it, run `set FM_VOICE_RATE=0` (natural) or `15` before the launcher.
- **Refused lines:** the voice service sometimes refuses a fully diacritised line ("No audio was received"). The tool then reads that line without vowel marks and carries on.
- **macOS/Linux:** run `ops/make-voiceover-collections.sh [voice]`.
- **Background music:** works exactly as above.
- **Other voices or videos:** `make-voiceover.bat <male|female|voice> <video name>` voices any video with any voice.

## Port Said Free Zone demo: the Arakan hotel question

`frontend/e2e/video/record-demo-hotel.mjs` records a third demo of the same length, also set at the Executive Authority of the Port Said Free Zone. It types and analyses the question «الاستفادة القصوى من فندق أراكان (148 غرفة) بوسط البلد ببورسعيد، المملوك للجهاز التنفيذي للمنطقة الحرة بمحافظة بورسعيد، من خلال مقترحات مختلفة», which runs on the **state-owned hotel asset** decision model. The question states no number, so the intake proposes a reference target (a 6% net annual return on the asset value) for the user to confirm or change.

The video covers the same 16 chapters with the hotel results:

- **A. Long-term lease to a private operator:** steady rent with no investment (about 3% return). It closes the hotel during refurbishment and leaves about 48 employees without work, more than the Authority can redeploy. Governance denies it because of the unresolved critical collision, and a lease also needs a public tender (GOV-017).
- **B. Full renovation with a hotel brand:** the highest return once stabilised (about 8%). It needs about EGP 85M, twice the capital budget, so it requires CFO and CEO approval (GOV-018).
- **C. Mixed-use repositioning for the Free Zone:** serviced apartments for investors, an investor business centre and a refreshed 108-room hotel. It costs about EGP 30M (within budget), keeps every employee and pays back in about 1.5 years. This is the recommended proposal.
- No proposal reaches 6% within 12 months: works and ramp-up take time, so the platform also reports the stabilised return.

The captions are in Modern Standard Arabic with full diacritics, and the narration says the figures are illustrative.

```bash
cd frontend
BASE_URL=http://localhost:8080 OUT_DIR=../docs/video node e2e/video/record-demo-hotel.mjs
```

The outputs are `future-mirror-demo-hotel.mp4`, `future-mirror-demo-hotel.srt` and `chapters-hotel.txt`. Use a fresh database.

**Voice-over:**

- **Windows:** put both files in `docs\video` and double-click `ops\make-voiceover-hotel.bat` (female voice `ar-EG-SalmaNeural`, 10% faster). The output is `docs\video\future-mirror-demo-hotel-voice.mp4`.
- **Another female voice:** `ops\make-voiceover-hotel.bat ar-SA-ZariyahNeural`.
- **macOS/Linux:** `ops/make-voiceover-hotel.sh [voice]`.
- Speed, refused lines and background music work exactly as for the collection-agency demo above.

