// Records the Arabic (Modern Standard Arabic) product demo of Future Mirror AI from the REAL running app,
// set at the Executive Authority of the Port Said Free Zone, around the question "how do we get the most out
// of the Authority's 148-room Arakan hotel downtown, through different proposals?" (hotel decision model).
//
//   BASE_URL=http://localhost:8080 OUT_DIR=../docs/video node e2e/video/record-demo-hotel.mjs
//
// Captions are in Modern Standard Arabic with full diacritics (tashkeel), so the voice-over reads them
// correctly: ops\make-voiceover-hotel.bat adds the female voice (ar-EG-SalmaNeural by default).
// All figures in the demo are illustrative (the app's sample data), not the hotel's real numbers.
// Frames come from Chrome's screencast (crisp JPEG), are re-timed to a constant 25 fps and
// piped into ffmpeg (H.264 MP4). On-screen Arabic captions, chapter cards and a visible cursor
// are injected into the page, so Arabic shaping and RTL are rendered by the browser itself.
// Writes: future-mirror-demo-hotel.mp4, .srt (narration, for voice-over), chapters-hotel.txt.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL || "http://localhost:5173";
const OUT = path.resolve(process.env.OUT_DIR || "../docs/video");
const NAME = process.env.VIDEO_NAME || "future-mirror-demo-hotel";
const W = 1600, H = 900, FPS = 25;
const PASSWORD = "FutureMirror!2026";
fs.mkdirSync(OUT, { recursive: true });

// ------------------------------------------------------------------ overlay (runs in the page)
const OVERLAY = () => {
  const css = `
  #fm-cursor{position:fixed;z-index:2147483647;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;
    background:rgba(255,255,255,.18);border:2px solid #fff;box-shadow:0 0 0 2px rgba(0,0,0,.35),0 4px 14px rgba(0,0,0,.4);
    pointer-events:none;transition:transform .12s ease;left:-50px;top:-50px}
  #fm-cursor.down{transform:scale(.7);background:rgba(250,204,21,.55)}
  .fm-ripple{position:fixed;z-index:2147483646;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;
    border:3px solid #facc15;pointer-events:none;animation:fmr .6s ease-out forwards}
  @keyframes fmr{to{transform:scale(4.5);opacity:0}}
  #fm-cap{position:fixed;z-index:2147483645;left:50%;bottom:34px;transform:translate(-50%,20px);opacity:0;
    max-width:1180px;min-width:520px;direction:rtl;text-align:right;font-family:"IBM Plex Sans Arabic",Tahoma,sans-serif;
    background:linear-gradient(135deg,rgba(6,10,22,.94),rgba(17,24,48,.94));color:#f8fafc;border-radius:18px;
    padding:16px 26px 18px;box-shadow:0 18px 50px rgba(0,0,0,.55);border:1px solid rgba(148,163,184,.25);
    border-inline-start:5px solid #facc15;transition:opacity .45s ease,transform .45s ease;pointer-events:none}
  #fm-cap.on{opacity:1;transform:translate(-50%,0)}
  #fm-cap .k{font-size:15px;font-weight:600;color:#facc15;margin-bottom:4px;letter-spacing:.2px}
  #fm-cap .t{font-size:25px;line-height:1.9;font-weight:500}
  #fm-card{position:fixed;inset:0;z-index:2147483644;display:flex;flex-direction:column;align-items:center;justify-content:center;
    gap:18px;direction:rtl;font-family:"IBM Plex Sans Arabic",Tahoma,sans-serif;color:#f8fafc;opacity:0;pointer-events:none;
    background:radial-gradient(1200px 600px at 70% 20%,rgba(56,189,248,.22),transparent),
               radial-gradient(900px 500px at 20% 90%,rgba(167,139,250,.25),transparent),#050914;transition:opacity .7s ease}
  #fm-card.on{opacity:1}
  #fm-card .orb{width:92px;height:92px;border-radius:50%;background:conic-gradient(from 200deg,#38bdf8,#a78bfa,#f472b6,#38bdf8);
    box-shadow:0 0 60px rgba(167,139,250,.6)}
  #fm-card .kick{font-size:22px;color:#facc15;font-weight:600}
  #fm-card .ti{font-size:64px;font-weight:700;text-align:center;line-height:1.3}
  #fm-card .su{font-size:28px;color:#cbd5e1;max-width:1150px;text-align:center;line-height:1.7}
  #fm-prog{position:fixed;z-index:2147483645;top:0;left:0;height:4px;background:linear-gradient(90deg,#38bdf8,#a78bfa,#facc15);
    transition:width .8s ease;pointer-events:none}
  #fm-chap{position:fixed;z-index:2147483645;top:14px;left:18px;direction:rtl;font-family:"IBM Plex Sans Arabic",Tahoma,sans-serif;
    font-size:15px;color:#e2e8f0;background:rgba(6,10,22,.78);border:1px solid rgba(148,163,184,.3);padding:6px 14px;
    border-radius:999px;opacity:0;transition:opacity .4s ease;pointer-events:none}
  #fm-chap.on{opacity:1}`;
  const mount = () => {
    if (document.getElementById("fm-cap")) return;
    const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    for (const [id, html] of [["fm-cursor", ""], ["fm-cap", '<div class="k"></div><div class="t"></div>'],
      ["fm-card", '<div class="orb"></div><div class="kick"></div><div class="ti"></div><div class="su"></div>'],
      ["fm-prog", ""], ["fm-chap", ""]]) {
      const d = document.createElement("div"); d.id = id; d.innerHTML = html; document.body.appendChild(d);
    }
    const cur = document.getElementById("fm-cursor");
    addEventListener("mousemove", (e) => { cur.style.left = e.clientX + "px"; cur.style.top = e.clientY + "px"; }, true);
    addEventListener("mousedown", (e) => {
      cur.classList.add("down");
      const r = document.createElement("div"); r.className = "fm-ripple"; r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px";
      document.body.appendChild(r); setTimeout(() => r.remove(), 700);
    }, true);
    addEventListener("mouseup", () => cur.classList.remove("down"), true);
    const s = JSON.parse(sessionStorage.getItem("fm-ov") || "{}");
    if (s.x !== undefined) { cur.style.left = s.x + "px"; cur.style.top = s.y + "px"; }
    if (s.cap) window.__fm.cap(s.cap, s.kick, true);
    if (s.chap) window.__fm.chap(s.chap, s.prog);
  };
  const save = (o) => sessionStorage.setItem("fm-ov", JSON.stringify({ ...JSON.parse(sessionStorage.getItem("fm-ov") || "{}"), ...o }));
  window.__fm = {
    cap(text, kick, instant) {
      const c = document.getElementById("fm-cap"); if (!c) return;
      const apply = () => { c.querySelector(".k").textContent = kick || ""; c.querySelector(".t").textContent = text; c.classList.add("on"); };
      if (instant || !c.classList.contains("on")) apply(); else { c.classList.remove("on"); setTimeout(apply, 260); }
      save({ cap: text, kick });
    },
    hide() { document.getElementById("fm-cap")?.classList.remove("on"); save({ cap: "" }); },
    card(kick, title, sub) {
      const c = document.getElementById("fm-card");
      c.querySelector(".kick").textContent = kick; c.querySelector(".ti").textContent = title; c.querySelector(".su").textContent = sub || "";
      c.classList.add("on");
    },
    uncard() { document.getElementById("fm-card")?.classList.remove("on"); },
    chap(label, prog) {
      const c = document.getElementById("fm-chap"); c.textContent = label; c.classList.toggle("on", !!label);
      document.getElementById("fm-prog").style.width = (prog * 100).toFixed(1) + "%"; save({ chap: label, prog });
    },
    pos(x, y) { save({ x, y }); },
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
};

// ------------------------------------------------------------------ recorder
const browser = await chromium.launch({ args: ["--force-color-profile=srgb", "--font-render-hinting=none"] });
const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, locale: "ar-EG" });
await context.addInitScript(() => { localStorage.setItem("fm_lang", "ar"); localStorage.removeItem("fm_theme"); });
await context.addInitScript(OVERLAY);
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

const ffmpeg = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
  "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
  "-vf", "scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
  "-profile:v", "high", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "96k", "-shortest",
  path.join(OUT, `${NAME}.mp4`)], { stdio: ["pipe", "inherit", "inherit"] });
const cdp = await context.newCDPSession(page);
let lastFrame = null;
cdp.on("Page.screencastFrame", async ({ data, sessionId }) => {
  lastFrame = Buffer.from(data, "base64");
  try { await cdp.send("Page.screencastFrameAck", { sessionId }); } catch { /* page navigating */ }
});
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
const t0 = Date.now();
let written = 0;
const ticker = setInterval(() => {  // constant frame rate in wall-clock time
  const due = Math.floor(((Date.now() - t0) / 1000) * FPS);
  while (lastFrame && written < due) { ffmpeg.stdin.write(lastFrame); written++; }
}, 1000 / FPS);

// ------------------------------------------------------------------ helpers
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const now = () => Date.now() - t0;
const srt = [], chapters = [];
let open = null, kick = "";
const stamp = (ms) => {
  const h = Math.floor(ms / 3.6e6), m = Math.floor(ms / 6e4) % 60, s = Math.floor(ms / 1000) % 60, x = ms % 1000;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${String(x).padStart(3, "0")}`;
};
const closeCap = () => { if (open) { open.end = now(); srt.push(open); open = null; } };
// Paced for the female voice at +10% (about 1.75 words a second on diacritised text), so the
// voice-over fits each caption without freezing the picture.
const readMs = (t) => Math.max(2600, 450 + t.split(/\s+/).length * 575);
async function say(text, extra = 0) {          // show a caption and hold it for its reading time
  closeCap();
  open = { start: now(), text };
  await page.evaluate(([t, k]) => window.__fm?.cap(t, k), [text, kick]);
  await sleep(readMs(text) + extra);
}
async function cap(text) {                       // show a caption without waiting (actions follow)
  closeCap();
  open = { start: now(), text };
  await page.evaluate(([t, k]) => window.__fm?.cap(t, k), [text, kick]);
}
const TOTAL_CH = 16;
let chapNo = 0;
async function chapter(title, sub) {             // full-screen chapter card
  chapNo++;
  kick = title;
  closeCap();
  chapters.push({ t: now(), title });
  await page.evaluate(() => window.__fm?.hide());
  await page.evaluate(([n, ti, su, total]) => window.__fm?.card(`الْجُزْء ${n.toLocaleString("ar-EG")} مِن ${total.toLocaleString("ar-EG")}`, ti, su),
    [chapNo, title, sub, TOTAL_CH]);
  open = { start: now(), text: title };  // the subtitle is shown on the card but not read aloud
  await sleep(3200);
  closeCap();
  await page.evaluate(([ti, p]) => { window.__fm?.uncard(); window.__fm?.chap(ti, p); }, [title, chapNo / TOTAL_CH]);
  await sleep(900);
}
let mx = W / 2, my = H / 2;
async function moveTo(x, y, steps = 28) {
  await page.mouse.move(x, y, { steps });
  mx = x; my = y;
  await page.evaluate(([a, b]) => window.__fm?.pos(a, b), [x, y]);
}
async function point(loc, pause = 500) {
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox();
  if (!b) return;
  await moveTo(b.x + b.width / 2, b.y + Math.min(b.height / 2, 22));
  await sleep(pause);
}
async function click(loc, pause = 700) {
  await point(loc, 350);
  await loc.click();
  await sleep(pause);
}
async function go(p, settle = 1600) {
  await page.goto(BASE + p);
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.mouse.move(mx, my);
  await sleep(settle);
}
async function scroll(y, ms = 1400) {
  await page.evaluate((top) => window.scrollTo({ top, behavior: "smooth" }), y);
  await sleep(ms);
}
async function scrollToEl(loc, offset = 120, ms = 1300) {
  const b = await loc.boundingBox();
  if (!b) return;
  const cur = await page.evaluate(() => window.scrollY);
  await scroll(Math.max(0, cur + b.y - offset), ms);
}
async function login(email) {
  await go("/login", 1200);
  await click(page.locator('input[name="email"]'), 200);
  await page.locator('input[name="email"]').fill("");
  await page.keyboard.type(email, { delay: 45 });
  await click(page.locator('input[name="password"]'), 200);
  await page.locator('input[name="password"]').fill("");
  await page.keyboard.type(PASSWORD, { delay: 45 });
  await click(page.locator('button[type="submit"]'), 300);
  await page.getByTestId("platform-chips").waitFor();
  await sleep(1200);
}
async function logout() {
  await page.evaluate(() => { localStorage.removeItem("fm_token"); sessionStorage.removeItem("fm_token"); });
}

// ------------------------------------------------------------------ the demo
const QUESTION = "الاستفادة القصوى من فندق أراكان (148 غرفة) بوسط البلد ببورسعيد، المملوك للجهاز التنفيذي للمنطقة الحرة بمحافظة بورسعيد، من خلال مقترحات مختلفة";
const TITLE = "تعظيم الاستفادة من فندق أراكان ببورسعيد";
try {
  // Intro
  await go("/login", 600);
  await page.evaluate(() => window.__fm?.card("عَرْضٌ تَوْضِيحِيٌّ لِلْمُنْتَجِ", "مِرْآةُ الْمُسْتَقْبَلِ",
    "الْجِهَازُ التَّنْفِيذِيُّ لِلْمَنْطِقَةِ الْحُرَّةِ بِبُورْسَعِيدَ: كَيْفَ نُحَقِّقُ الِاسْتِفَادَةَ الْقُصْوَى مِنْ فُنْدُقِ أَرَاكَان؟"));
  chapters.push({ t: 0, title: "الْمُقَدِّمَةُ" });
  const intro = "مَرْحَبًا بِكُمْ فِي مِرْآةِ الْمُسْتَقْبَلِ، الْمَنَصَّةِ الَّتِي تُرِيكَ نَتَائِجَ قَرَارِكَ قَبْلَ أَنْ تَتَّخِذَهُ. وَنَطْرَحُ الْيَوْمَ سُؤَالًا مِنَ الْجِهَازِ التَّنْفِيذِيِّ لِلْمَنْطِقَةِ الْحُرَّةِ بِبُورْسَعِيدَ.";
  open = { start: now(), text: intro };
  await sleep(readMs(intro) + 600);
  closeCap();
  await page.evaluate(() => window.__fm?.uncard());
  await sleep(900);

  // 1. Sign-in
  await chapter("تَسْجِيلُ الدُّخُولِ وَالْوَاجِهَةُ", "حِسَابٌ لِكُلِّ دَوْرٍ، وَوَاجِهَةٌ عَرَبِيَّةٌ كَامِلَةٌ مِنَ الْيَمِينِ إِلَى الْيَسَارِ");
  await say("نَبْدَأُ بِشَاشَةِ الدُّخُولِ. الْمَنَصَّةُ ثُنَائِيَّةُ اللُّغَةِ، وَنَعْرِضُهَا هُنَا بِالْعَرَبِيَّةِ مِنَ الْيَمِينِ إِلَى الْيَسَارِ.");
  await cap("نَدْخُلُ الْآنَ بِحِسَابِ مُحَلِّلِ الْقَرَارَاتِ، الَّذِي يُعِدُّ الْقَرَارَ وَيُرْسِلُهُ لِلتَّحْلِيلِ.");
  await login("analyst@futuremirror.demo");
  await point(page.getByTestId("platform-chips"), 300);
  await say("فِي الشَّرِيطِ الْعُلْوِيِّ ثَلَاثُ شَارَاتٍ صَادِقَةٍ: الْبَيَانَاتُ افْتِرَاضِيَّةٌ، وَالْوُكَلَاءُ يَعْمَلُونَ بِالْقَوَاعِدِ دُونَ نَمُوذَجٍ لُغَوِيٍّ، وَالْإِجْرَاءَاتُ الْخَارِجِيَّةُ مُعَطَّلَةٌ.");
  await say("لِذَلِكَ فَكُلُّ الْأَرْقَامِ فِي هَذَا الْعَرْضِ تَوْضِيحِيَّةٌ، وَلَيْسَتْ أَرْقَامًا فِعْلِيَّةً لِلْفُنْدُقِ أَوْ لِلْمَنْطِقَةِ الْحُرَّةِ.");

  // 2. Command center
  await chapter("مَرْكَزُ الْقِيَادَةِ", "مُؤَشِّرَاتُ الْجِهَةِ وَآخِرُ مَلَفِّ قَرَارٍ فِي نَظْرَةٍ وَاحِدَةٍ");
  await go("/");
  await say("هَذِهِ هِيَ الصَّفْحَةُ الرَّئِيسِيَّةُ: مُؤَشِّرَاتُ الْقَرَارِ الْأَخِيرِ وَمَلَفُّهُ. فَلْنَطْرَحْ سُؤَالًا جَدِيدًا عَنْ أَحَدِ أُصُولِ الْجِهَازِ.");

  // 3. Intake
  await chapter("السُّؤَالُ", "الِاسْتِفَادَةُ الْقُصْوَى مِنْ فُنْدُقِ أَرَاكَان بِوَسَطِ الْبَلَدِ");
  await go("/decisions/new");
  await cap("نَكْتُبُ السُّؤَالَ كَمَا تَطْرَحُهُ الْإِدَارَةُ تَمَامًا.");
  await click(page.getByTestId("question-input"), 300);
  await page.keyboard.type(QUESTION, { delay: 28 });
  await sleep(700);
  await say("السُّؤَالُ: الِاسْتِفَادَةُ الْقُصْوَى مِنْ فُنْدُقِ أَرَاكَان، بِمِئَةٍ وَثَمَانٍ وَأَرْبَعِينَ غُرْفَةً فِي وَسَطِ الْبَلَدِ بِبُورْسَعِيدَ، الْمَمْلُوكِ لِلْجِهَازِ التَّنْفِيذِيِّ لِلْمَنْطِقَةِ الْحُرَّةِ، مِنْ خِلَالِ مُقْتَرَحَاتٍ مُخْتَلِفَةٍ.");
  await cap("تُفَسِّرُ الْمَنَصَّةُ السُّؤَالَ وَتَسْتَخْرِجُ عَنَاصِرَهُ.");
  await click(page.getByTestId("parse-btn"), 1400);
  const titleInput = page.locator("label", { hasText: "عنوان القرار" }).locator("input");
  await titleInput.fill(TITLE);
  await say("لَاحِظُوا أَنَّهَا تَعَرَّفَتْ تِلْقَائِيًّا عَلَى أَنَّهُ قَرَارٌ بِشَأْنِ أَصْلٍ فُنْدُقِيٍّ مَمْلُوكٍ لِلدَّوْلَةِ، وَعَلَى عَدَدِ الْغُرَفِ، وَعَلَى أَنَّ الْمَطْلُوبَ مُقَارَنَةُ مُقْتَرَحَاتٍ مُخْتَلِفَةٍ.");
  await say("وَلِأَنَّ السُّؤَالَ لَا يُحَدِّدُ رَقْمًا، تَقْتَرِحُ الْمَنَصَّةُ هَدَفًا مَرْجِعِيًّا: عَائِدًا سَنَوِيًّا صَافِيًا قَدْرُهُ سِتَّةٌ فِي الْمِائَةِ مِنْ قِيمَةِ الْأَصْلِ، وَيُرَاجِعُهُ الْمُسْتَخْدِمُ وَيُعَدِّلُهُ.");
  await click(page.getByTestId("next-2"), 1200);
  await say("ثُمَّ نَضْبِطُ الضَّوَابِطَ التَّنْفِيذِيَّةَ، وَمِنْهَا أَقْصَى نِسْبَةٍ لِلْغُرَفِ خَارِجَ الْخِدْمَةِ، وَمُوَازَنَةٌ اسْتِثْمَارِيَّةٌ قَدْرُهَا أَرْبَعُونَ مِلْيُونَ جُنَيْهٍ.");
  await scroll(500, 1200);
  await scroll(0, 900);
  await click(page.getByTestId("next-3"), 1200);
  await say("وَأَخِيرًا نَخْتَارُ إِصْدَارَ الْبَيَانَاتِ، وَتُنَبِّهُنَا شَارَةُ الْجَوْدَةِ إِلَى عَدَمِ اتِّسَاقٍ فِي بَعْضِ الْأَرْقَامِ الْمَالِيَّةِ.");
  await cap("نُطْلِقُ التَّحْلِيلَ وَنُوقِظُ الْوُكَلَاءَ.");
  await click(page.getByTestId("launch-btn"), 600);

  // 4. Execution room
  await page.waitForURL(/\/execution\//);
  await chapter("غُرْفَةُ التَّنْفِيذِ الْمُبَاشِرِ", "عَشْرُ مَرَاحِلَ وَسَبْعَةُ وُكَلَاءَ يَعْمَلُونَ بِالتَّوَازِي، وَأَحْدَاثٌ حَقِيقِيَّةٌ مِنَ الْخَادِمِ");
  await say("هَذِهِ غُرْفَةُ التَّنْفِيذِ، وَكُلُّ حَدَثٍ فِيهَا يُبَثُّ فِعْلِيًّا مِنَ الْخَادِمِ أَثْنَاءَ التَّشْغِيلِ، وَلَيْسَ عَرْضًا مُسَجَّلًا.");
  await point(page.getByTestId("flow-graph"), 300);
  await say("يَعْرِضُ الْمُخَطَّطُ الْمَرَاحِلَ الْعَشْرَ، وَسَبْعَةَ وُكَلَاءَ مُتَخَصِّصِينَ يَعْمَلُونَ فِي الْوَقْتِ نَفْسِهِ.");
  await point(page.getByTestId("event-feed"), 300);
  await say("وَيَعْرِضُ سِجِلُّ التَّنْفِيذِ كُلَّ نَتِيجَةٍ فَوْرَ صُدُورِهَا: الْمُدِيرُ الْمَالِيُّ يَحْسُبُ نَتِيجَةَ الْفُنْدُقِ، وَالْقَانُونِيُّ يُنَبِّهُ إِلَى قَانُونِ التَّعَاقُدَاتِ الْعَامَّةِ، وَالْفَرِيقُ الْأَحْمَرُ يَعْتَرِضُ.");
  await page.getByTestId("to-court").waitFor({ timeout: 180_000 });
  await say("اكْتَمَلَ مَلَفُّ الْقَرَارِ، وَيُعْرَضُ وَقْتُ الْحَوْسَبَةِ الْفِعْلِيُّ مُنْفَصِلًا بِكُلِّ شَفَافِيَّةٍ.");
  await cap("نَدْخُلُ مَحْكَمَةَ الْوُكَلَاءِ.");
  await click(page.getByTestId("to-court"), 600);

  // 5. Agent court
  await page.getByTestId("verdict-headline").waitFor();
  await chapter("مَحْكَمَةُ الْوُكَلَاءِ", "مَوَاقِفُ وَأَدِلَّةٌ وَاعْتِرَاضَاتٌ، وَحُكْمٌ يَزِنُ الْأَدِلَّةَ لَا الْأَصْوَاتَ");
  await point(page.getByTestId("court-mode"), 300);
  await say("يُوَضِّحُ هَذَا الشَّرِيطُ أَنَّ كُلَّ عِبَارَةٍ هُنَا مَحْسُوبَةٌ مِنْ بَيَانَاتِ هَذَا التَّشْغِيلِ، وَلَيْسَتْ نَصًّا مُعَدًّا مُسْبَقًا.");
  await point(page.getByTestId("verdict-headline"), 300);
  await say("حُكْمُ الْهَيْئَةِ: يُوصَى بِالْمُسْتَقْبَلِ جِيم، إِعَادَةِ التَّوْظِيفِ مُتَعَدِّدِ الِاسْتِخْدَامَاتِ لِخِدْمَةِ الْمَنْطِقَةِ الْحُرَّةِ، لِأَنَّهُ يَسْتَوْفِي جَمِيعَ الْقُيُودِ الْإِلْزَامِيَّةِ.");
  await say("أَمَّا الْمُسْتَقْبَلُ أَلِف، التَّأْجِيرُ طَوِيلُ الْأَجَلِ لِمُشَغِّلٍ خَاصٍّ، فَمَرْفُوضٌ مِنَ الْحَوْكَمَةِ. وَالْحُكْمُ لَا يَعْتَمِدُ عَلَى الْأَغْلَبِيَّةِ، بَلْ عَلَى جَوْدَةِ الْأَدِلَّةِ وَالسِّيَاسَاتِ.");
  await scrollToEl(page.getByTestId("debate"), 220);
  await say("وَتَعْرِضُ الْمُنَاظَرَةُ النِّقَاشَ عَلَى أَرْبَعِ جَوْلَاتٍ، مِنَ الْمَوَاقِفِ وَالِاعْتِرَاضَاتِ إِلَى الْحَوْكَمَةِ.");
  await say("مِثَالٌ: نَبَّهَ الْفَرِيقُ الْأَحْمَرُ إِلَى أَنَّ تَأْجِيرَ الْفُنْدُقِ خَمْسَةَ عَشَرَ عَامًا يَرْبِطُهُ بِإِيجَارِ الْيَوْمِ، فَإِذَا نَمَتِ الْمَنْطِقَةُ الْحُرَّةُ ذَهَبَ الْمَكْسَبُ إِلَى الْمُشَغِّلِ.");
  await click(page.getByRole("tab", { name: /مواقف الوكلاء/ }), 1200);
  await say("وَفِي مَوَاقِفِ الْوُكَلَاءِ تُصَنَّفُ كُلُّ نَتِيجَةٍ بِنَوْعِهَا، وَدَرَجَةِ ثِقَتِهَا، وَدَلِيلِهَا.");
  await scroll(await page.evaluate(() => window.scrollY + 420), 1300);
  await click(page.getByRole("tab", { name: /كاشف تصادم المستقبل/ }), 1200);
  await scrollToEl(page.getByTestId("collision-card").first(), 160);
  await say("وَيَرْصُدُ كَاشِفُ التَّصَادُمِ تَعَارُضًا حَرِجًا بَيْنَ دَخْلِ التَّأْجِيرِ وَبَيْنَ الْعَامِلِينَ وَاسْتِمْرَارِيَّةِ الْخِدْمَةِ: نَحْوُ ثَمَانِيَةٍ وَأَرْبَعِينَ مُوَظَّفًا بِلَا عَمَلٍ، وَإِغْلَاقُ الْفُنْدُقِ سِتَّةَ أَشْهُرٍ.");
  await say("وَتَصَادُمًا آخَرَ: الْعَائِدُ الْأَعْلَى فِي الْمُسْتَقْبَلِ بَاء يَحْتَاجُ اسْتِثْمَارًا يُعَادِلُ ضِعْفَ الْمُوَازَنَةِ. وَلِكُلِّ تَصَادُمٍ شِدَّتُهُ وَعَوَاقِبُهُ وَحُلُولُهُ الْبَدِيلَةُ.");
  await scroll(0, 900);

  // 6. Three futures
  await chapter("الْمُسْتَقْبَلَاتُ الثَّلَاثَةُ", "مُحَاكَاةُ مُونْت كَارْلُو لِأَلْفَيْ سِينَارْيُو لِكُلِّ مُقْتَرَحٍ");
  await go("/futures", 2200);
  await say("هُنَا نُقَارِنُ ثَلَاثَةَ مُقْتَرَحَاتٍ جَنْبًا إِلَى جَنْبٍ، وَالْأَرْقَامُ مِنْ مُحَرِّكِ مُحَاكَاةٍ كَمِّيٍّ بِأَلْفَيْ سَحْبٍ عَشْوَائِيٍّ.");
  await scrollToEl(page.getByTestId("future-A"), 110);
  await point(page.getByTestId("future-A"), 300);
  await say("الْمُسْتَقْبَلُ أَلِف، التَّأْجِيرُ لِمُشَغِّلٍ خَاصٍّ: دَخْلٌ ثَابِتٌ دُونَ اسْتِثْمَارٍ، بِعَائِدٍ نَحْوَ ثَلَاثَةٍ فِي الْمِائَةِ، لَكِنَّهُ يُغْلِقُ الْفُنْدُقَ، وَيَتْرُكُ عَمَالَةً زَائِدَةً تَفُوقُ طَاقَةَ إِعَادَةِ التَّوْزِيعِ.");
  await point(page.getByTestId("future-B"), 300);
  await say("الْمُسْتَقْبَلُ بَاء، التَّجْدِيدُ الشَّامِلُ مَعَ عَلَامَةٍ فُنْدُقِيَّةٍ: أَعْلَى عَائِدٍ بَعْدَ الِاسْتِقْرَارِ، نَحْوَ ثَمَانِيَةٍ فِي الْمِائَةِ، لَكِنَّهُ يَحْتَاجُ نَحْوَ خَمْسَةٍ وَثَمَانِينَ مِلْيُونَ جُنَيْهٍ، أَيْ ضِعْفَ الْمُوَازَنَةِ.");
  await point(page.getByTestId("future-C"), 300);
  await say("وَالْمُسْتَقْبَلُ جِيم: شُقَقٌ فُنْدُقِيَّةٌ لِلْمُسْتَثْمِرِينَ، وَمَرْكَزُ أَعْمَالٍ، وَفُنْدُقٌ مُجَدَّدٌ، بِاسْتِثْمَارٍ نَحْوَ ثَلَاثِينَ مِلْيُونًا دَاخِلَ الْمُوَازَنَةِ، مَعَ الْإِبْقَاءِ عَلَى جَمِيعِ الْعَامِلِينَ.");
  await say("وَهَذِهِ هِيَ الْحَقِيقَةُ الَّتِي كَشَفَتْهَا الْمُحَاكَاةُ: لَا يَصِلُ أَيُّ مُقْتَرَحٍ إِلَى سِتَّةٍ فِي الْمِائَةِ خِلَالَ اثْنَيْ عَشَرَ شَهْرًا، وَأَقْصَى عَائِدٍ وَاقِعِيٍّ نَحْوُ أَرْبَعَةٍ فِي الْمِائَةِ.");
  await say("وَالسَّبَبُ أَنَّ الْفَنَادِقَ تَحْتَاجُ أَعْمَالًا وَفَتْرَةَ انْطِلَاقٍ، وَلِذَلِكَ تَعْرِضُ الْمَنَصَّةُ أَيْضًا الْعَائِدَ بَعْدَ الِاسْتِقْرَارِ لِكُلِّ مُقْتَرَحٍ.");
  await scroll(0, 900);
  await cap("وَضْعُ مَاذَا لَوْ: نُحَرِّكُ أَيَّ شَرِيطٍ، فَتُعَادُ الْمُحَاكَاةُ فِي جُزْءٍ مِنَ الثَّانِيَةِ.");
  const slider = page.locator('input[type="range"]').first();
  await point(slider, 400);
  await slider.fill("3");
  await sleep(2600);
  await say("خَفَّضْنَا الْهَدَفَ إِلَى ثَلَاثَةٍ فِي الْمِائَةِ، فَظَهَرَتْ شَارَةُ وَضْعِ مَاذَا لَوْ، وَهَذِهِ النَّتَائِجُ لَا تُحْفَظُ إِلَّا إِذَا اخْتَرْنَا ذَلِكَ.");

  // 7. Time machine
  await chapter("آلَةُ زَمَنِ الْقَرَارِ", "الْحَالَةُ الْيَوْمَ، وَبَعْدَ شَهْرٍ وَثَلَاثَةٍ وَسِتَّةٍ وَاثْنَيْ عَشَرَ شَهْرًا");
  await go("/time-machine");
  await say("تَعْرِضُ آلَةُ الزَّمَنِ الْحَالَةَ الْمُتَوَقَّعَةَ فِي أَيِّ شَهْرٍ: إِشْغَالَ الْغُرَفِ، وَالْعَائِدَ الصَّافِيَ لِلْجِهَازِ، وَالْإِيرَادَ، وَالتَّكَالِيفَ، وَالْغُرَفَ خَارِجَ الْخِدْمَةِ.");
  await click(page.getByTestId("tm-stops").locator("button").nth(3), 1400);
  await click(page.getByTestId("tm-stops").locator("button").nth(4), 1400);
  await say("انْتَقَلْنَا إِلَى الشَّهْرِ الثَّانِيَ عَشَرَ: يُبَيِّنُ كُلُّ مُؤَشِّرٍ تَغَيُّرَهُ مُنْذُ الْيَوْمِ، وَيَرْتَفِعُ الْإِشْغَالُ فِي الْمُسْتَقْبَلِ جِيم مِنْ أَرْبَعَةٍ وَثَلَاثِينَ إِلَى نَحْوِ ثَلَاثَةٍ وَخَمْسِينَ فِي الْمِائَةِ.");
  await scroll(520, 1300);
  await scroll(0, 900);

  // 8. Financial, risk, lab
  await chapter("التَّحْلِيلُ الْمَالِيُّ وَالْمَخَاطِرُ وَالْمُخْتَبَرُ", "الْأَثَرُ الْمَالِيُّ، وَعَدَمُ الْيَقِينِ، وَمُحَاكَاةٌ مُخَصَّصَةٌ");
  await go("/financial", 2000);
  await say("لَوْحَةُ الْأَثَرِ الْمَالِيِّ: جِسْرُ الْقِيمَةِ مِنَ التَّحَسُّنِ التَّشْغِيلِيِّ إِلَى الْأَعْمَالِ الرَّأْسِمَالِيَّةِ وَالْمُسَاهَمَةِ الْمَفْقُودَةِ أَثْنَاءَ الْأَعْمَالِ، ثُمَّ صَافِي الْمَنْفَعَةِ.");
  await say("وَفِي السَّنَةِ الْأُولَى يَكُونُ صَافِي الْمَنْفَعَةِ سَالِبًا لِأَنَّهُ يَشْمَلُ الِاسْتِثْمَارَ، الَّذِي يُسْتَرَدُّ فِي الْمُسْتَقْبَلِ جِيم خِلَالَ نَحْوِ سَنَةٍ وَنِصْفٍ.");
  await scroll(620, 1500);
  await sleep(1200);
  await go("/risk", 2000);
  await say("مُسْتَكْشِفُ الْمَخَاطِرِ: احْتِمَالُ اسْتِيفَاءِ كُلِّ قَيْدٍ، وَمَصْفُوفَةُ الِاحْتِمَالِ وَالْأَثَرِ، وَسِجِلُّ الْمَخَاطِرِ، وَمِنْهَا تَأَخُّرُ الْأَعْمَالِ وَضَعْفُ الطَّلَبِ.");
  await scroll(700, 1500);
  await say("وَيُبَيِّنُ مُخَطَّطُ الْإِعْصَارِ أَيَّ الِافْتِرَاضَاتِ يُحَرِّكُ النَّتِيجَةَ أَكْثَرَ، مِثْلَ تَجَاوُزِ تَكْلِفَةِ الْأَعْمَالِ، وَمُدَّتِهَا، وَالطَّلَبِ مِنْ شَرِكَاتِ الْمَنْطِقَةِ الْحُرَّةِ.");
  await go("/lab", 1600);
  await say("وَفِي مُخْتَبَرِ الْمُحَاكَاةِ نَبْنِي مُقْتَرَحَنَا بِأَنْفُسِنَا: التَّأْجِيرَ، أَوْ إِدَارَةَ الْعَلَامَةِ، وَقِيمَةَ التَّجْدِيدِ، وَالشُّقَقَ الْفُنْدُقِيَّةَ، وَمَرْكَزَ الْأَعْمَالِ.");
  await click(page.getByTestId("lab-run"), 2600);
  await say("وَنَحْصُلُ فَوْرًا عَلَى الْمُخْرَجَاتِ نَفْسِهَا، وَمِنْهَا أَشْهُرُ إِغْلَاقِ كُلِّ مِسَاحَةٍ فِي الْفُنْدُقِ.");
  await scroll(0, 900);

  // 9. Approvals
  await chapter("الْحَوْكَمَةُ وَالِاعْتِمَادُ الْبَشَرِيُّ", "سِيَاسَاتٌ تُنَفَّذُ خَارِجَ النَّمَاذِجِ، وَمُوَافَقَةٌ بَشَرِيَّةٌ قَبْلَ أَيِّ تَنْفِيذٍ");
  await go("/approvals", 1800);
  await say("لَا يَمْضِي أَيُّ مُقْتَرَحٍ دُونَ اعْتِمَادٍ بَشَرِيٍّ مِمَّنْ تُحَدِّدُهُمُ السِّيَاسَاتُ، وَالْمَنَصَّةُ نَفْسُهَا لَا تُنَفِّذُ شَيْئًا تِلْقَائِيًّا.");
  await click(page.getByTestId("pick-A"), 1400);
  await say("إِذَا اخْتَرْنَا أَلِف، فَهُوَ مَرْفُوضٌ لِوُجُودِ تَصَادُمٍ حَرِجٍ غَيْرِ مَحْلُولٍ، كَمَا أَنَّ تَأْجِيرَ أَصْلٍ مَمْلُوكٍ لِلدَّوْلَةِ يَتَطَلَّبُ مُنَاقَصَةً عَامَّةً وَفْقَ الْقَانُونِ.");
  await click(page.getByTestId("pick-C"), 1400);
  await say("أَمَّا جِيم فَمَسْمُوحٌ بِشَرْطِ مُوَافَقَةِ الْمُدِيرِ الْمَالِيِّ، وَالرَّئِيسِ التَّنْفِيذِيِّ، وَمُدِيرِ الْعَمَلِيَّاتِ.");
  await click(page.getByTestId("ack"), 600);
  await say("وَلِوُجُودِ تَنْبِيهٍ فِي جَوْدَةِ الْبَيَانَاتِ، تَشْتَرِطُ السِّيَاسَةُ إِقْرَارًا صَرِيحًا قَبْلَ التَّقْدِيمِ.");
  await click(page.getByTestId("submit-approval"), 1600);
  await scrollToEl(page.getByTestId("approval-card").first(), 160);
  await say("قُدِّمَ الطَّلَبُ، وَهُوَ الْآنَ قَيْدُ الِانْتِظَارِ، وَكُلُّ خُطْوَةٍ مُسَجَّلَةٌ فِي سِجِلِّ التَّدْقِيقِ.");
  await cap("نَدْخُلُ الْآنَ بِحِسَابِ الْمُدِيرِ الْمَالِيِّ لِيَعْتَمِدَ الطَّلَبَ.");
  await logout();
  await login("cfo@futuremirror.demo");
  await go("/approvals", 1600);
  await scrollToEl(page.getByTestId("approve-btn").first(), 260);
  await click(page.getByTestId("approve-btn").first(), 1800);
  await say("اعْتَمَدَ الْمُدِيرُ الْمَالِيُّ، فَتَحَوَّلَتْ شَارَةُ دَوْرِهِ إِلَى اللَّوْنِ الْأَخْضَرِ، وَتَبْقَى مُوَافَقَةُ الرَّئِيسِ التَّنْفِيذِيِّ وَمُدِيرِ الْعَمَلِيَّاتِ.");

  // 10. Outcomes
  await chapter("الْفِعْلِيُّ مُقَابِلَ الْمُتَوَقَّعِ", "حَلْقَةُ التَّغْذِيَةِ الرَّاجِعَةِ مِنَ الْوَاقِعِ");
  await go("/outcomes", 1800);
  await say("بَعْدَ التَّنْفِيذِ نُقَارِنُ مَا حَدَثَ فِعْلًا بِمَا تَوَقَّعَتْهُ الْمُحَاكَاةُ، وَلِلْعَرْضِ نُوَلِّدُ قِيَمًا فِعْلِيَّةً افْتِرَاضِيَّةً مَوْسُومَةً بِوُضُوحٍ.");
  await click(page.getByTestId("demo-actuals"), 2600);
  await say("يَعْرِضُ الْمُخَطَّطُ الْخَطَّ الْمُتَوَقَّعَ وَنِطَاقَهُ وَالْقِيَمَ الْفِعْلِيَّةَ، وَتَقِيسُ الْمُؤَشِّرَاتُ دِقَّةَ التَّوَقُّعِ وَانْحِيَازَهُ.");
  await scroll(620, 1500);
  await say("وَلَا تُطَبَّقُ إِعَادَةُ مُعَايَرَةِ النَّمُوذَجِ إِلَّا بِاعْتِمَادِ مُدِيرِ الْمَنَصَّةِ.");
  await scroll(0, 900);

  // 11. History & reports
  await chapter("السِّجِلُّ وَالتَّقَارِيرُ", "كُلُّ تَشْغِيلٍ قَابِلٌ لِلتَّتَبُّعِ، وَتَقَارِيرُ بِالْعَرَبِيَّةِ وَالْإِنْجِلِيزِيَّةِ");
  await go("/history", 1800);
  await say("يَحْفَظُ سِجِلُّ الْقَرَارَاتِ كُلَّ تَشْغِيلٍ وَكُلَّ مُحَاكَاةٍ بِبَصْمَتِهَا، فَيُمْكِنُ تَتَبُّعُ أَيِّ نَتِيجَةٍ وَإِعَادَةُ إِنْتَاجِهَا.");
  await go("/court", 3500);
  await point(page.getByRole("button", { name: /تقرير PDF/ }).first(), 600);
  await say("وَمِنْ شَرِيطِ الْقَرَارِ نُصَدِّرُ تَقْرِيرًا تَنْفِيذِيًّا بِصِيغَةِ PDF أَوْ Excel، يَتَضَمَّنُ الْعَائِدَ وَالِاسْتِثْمَارَ وَفَتْرَةَ الِاسْتِرْدَادِ.");

  // 12. Data connections (admin)
  await chapter("مَصَادِرُ الْبَيَانَاتِ", "مُوَصِّلَاتٌ لِلْقِرَاءَةِ فَقَطْ مَعَ أَنْظِمَةِ الْجِهَةِ");
  await logout();
  await login("admin@futuremirror.demo");
  await go("/data", 1800);
  await say("تَضُمُّ شَاشَةُ مَصَادِرِ الْبَيَانَاتِ مُوَصِّلَاتِ Odoo وَ Dynamics 365 وَ SAP وَ REST وَ SQL، وَاسْتِيرَادَ Excel، وَكُلُّهَا لِلْقِرَاءَةِ فَقَطْ.");
  await click(page.getByTestId("conn-configure-sql"), 1400);
  await scrollToEl(page.getByTestId("conn-settings-sql"), 90);
  await say("وَبِهَا تُسْتَبْدَلُ الْأَرْقَامُ التَّوْضِيحِيَّةُ بِحِسَابَاتِ الْفُنْدُقِ الْفِعْلِيَّةِ، وَتُحْفَظُ كَلِمَاتُ الْمُرُورِ عَلَى الْخَادِمِ فَقَطْ.");
  await click(page.getByTestId("conn-configure-sql"), 800);
  await scroll(0, 900);

  // 13. Automation
  await chapter("مَرْكَزُ الْأَتْمَتَةِ", "سَبْعَةُ مَسَارَاتٍ جَاهِزَةٍ فِي n8n بِتَشْغِيلٍ تَجْرِيبِيٍّ آمِنٍ");
  await go("/automation", 1800);
  await say("تَتَكَامَلُ مَسَارَاتُ الْأَتْمَتَةِ مَعَ n8n: إِعَادَةُ التَّحْلِيلِ، وَمُزَامَنَةُ الْبَيَانَاتِ، وَتَوْجِيهُ الِاعْتِمَادَاتِ، وَمُرَاقَبَةُ الْمُؤَشِّرَاتِ.");
  await scroll(600, 1400);
  await say("وَيُبَيِّنُ التَّشْغِيلُ التَّجْرِيبِيُّ مَا سَيُرْسَلُ بِالضَّبْطِ دُونَ تَغْيِيرِ أَيِّ شَيْءٍ، وَيُسَجَّلُ كُلُّ تَشْغِيلٍ بِمِفْتَاحٍ يَمْنَعُ التَّكْرَارَ.");
  await scroll(0, 900);

  // 14. Governance
  await chapter("حَوْكَمَةُ الذَّكَاءِ الِاصْطِنَاعِيِّ", "ثَمَانِيَ عَشْرَةَ سِيَاسَةً، وَوُكَلَاءُ بِلَا صَلَاحِيَةِ تَنْفِيذٍ");
  await go("/governance", 1800);
  await say("ثَمَانِيَ عَشْرَةَ سِيَاسَةً بِتَأْثِيرَاتِهَا: رَفْضٌ، أَوِ اشْتِرَاطُ اعْتِمَادٍ، أَوِ اشْتِرَاطُ إِقْرَارٍ، وَالسِّيَاسَاتُ الْمُقْفَلَةُ لَا يُمْكِنُ تَعْطِيلُهَا.");
  await point(page.getByTestId("policy-GOV-017"), 600);
  await say("وَمِنْهَا سِيَاسَتَانِ لِلْأُصُولِ الْمَمْلُوكَةِ لِلدَّوْلَةِ: التَّأْجِيرُ طَوِيلُ الْأَجَلِ يَتَطَلَّبُ مُنَاقَصَةً عَامَّةً، وَمُوَافَقَةَ الشُّؤُونِ الْقَانُونِيَّةِ وَالْمَوَارِدِ الْبَشَرِيَّةِ وَالرَّئِيسِ التَّنْفِيذِيِّ.");
  await point(page.getByTestId("policy-GOV-018"), 600);
  await say("وَالِاسْتِثْمَارُ الَّذِي يَتَجَاوَزُ خَمْسِينَ مِلْيُونَ جُنَيْهٍ يَتَطَلَّبُ دِرَاسَةَ جَدْوَى مُسْتَقِلَّةً، وَمُوَافَقَةَ الْمُدِيرِ الْمَالِيِّ وَالرَّئِيسِ التَّنْفِيذِيِّ.");
  const ev = page.getByTestId("evaluate");
  await scrollToEl(ev, 300);
  await click(ev, 1500);
  await say("وَتُقَيِّمُ بِيئَةُ اخْتِبَارِ السِّيَاسَاتِ أَيَّ إِجْرَاءٍ مُقْتَرَحٍ فَوْرًا، وَلَا يَمْلِكُ أَيُّ وَكِيلٍ صَلَاحِيَةَ التَّنْفِيذِ.");
  await scroll(0, 900);

  // 15. Admin
  await chapter("الْإِدَارَةُ وَالْأَمَانُ", "الْإِيقَافُ الطَّارِئُ، وَالْأَدْوَارُ، وَسِجِلُّ تَدْقِيقٍ مُقَاوِمٌ لِلتَّلَاعُبِ");
  await go("/admin", 1800);
  await say("شَاشَةُ الْإِدَارَةِ: الْمُسْتَخْدِمُونَ وَالْأَدْوَارُ الثَّمَانِيَةُ بِصَلَاحِيَّاتِهَا، وَتَفْعِيلُ الْحِسَابَاتِ أَوْ تَعْطِيلُهَا.");
  const stopOn = page.getByRole("button", { name: /تفعيل الإيقاف الطارئ/ });
  await click(stopOn, 1600);
  await say("يُلْغِي الْإِيقَافُ الطَّارِئُ كُلَّ التَّحْلِيلَاتِ الْجَارِيَةِ وَيَمْنَعُ الْجَدِيدَةَ فَوْرًا، ثُمَّ نُلْغِيهِ.");
  await click(page.getByRole("button", { name: /إلغاء الإيقاف الطارئ/ }), 1400);
  await scroll(800, 1500);
  await say("وَسِجِلُّ التَّدْقِيقِ مُرْتَبِطٌ بِسِلْسِلَةِ تَجْزِئَةٍ، فَيُكْتَشَفُ أَيُّ تَعْدِيلٍ عَلَى أَيِّ سِجِلٍّ سَابِقٍ فَوْرًا.");
  await scroll(0, 900);

  // 16. Bilingual + themes
  await chapter("ثُنَائِيَّةُ اللُّغَةِ وَالْمَظْهَرُ", "الْعَرَبِيَّةُ وَالْإِنْجِلِيزِيَّةُ، وَالْمَظْهَرُ الدَّاكِنُ وَالْفَاتِحُ");
  await go("/", 1400);
  await say("وَتَعْرِضُ الصَّفْحَةُ الرَّئِيسِيَّةُ الْآنَ مُؤَشِّرَاتِ الْفُنْدُقِ نَفْسِهِ: الْغُرَفَ، وَالْإِشْغَالَ، وَالْعَامِلِينَ، وَقِيمَةَ الْأَصْلِ.");
  await cap("بِضَغْطَةٍ وَاحِدَةٍ تَتَحَوَّلُ الْمَنَصَّةُ كُلُّهَا إِلَى الْإِنْجِلِيزِيَّةِ، بِمَا فِي ذَلِكَ نَتَائِجُ الْوُكَلَاءِ وَالتَّقَارِيرُ.");
  await click(page.getByTestId("lang-toggle"), 2800);
  await click(page.getByTestId("lang-toggle"), 1800);
  await cap("وَيَتَوَفَّرُ مَظْهَرٌ فَاتِحٌ لِلْعُرُوضِ وَالطِّبَاعَةِ.");
  await click(page.getByTestId("theme-toggle"), 3200);
  await click(page.getByTestId("theme-toggle"), 1600);
  await say("تَعْمَلُ الْمَنَصَّةُ مَحَلِّيًّا أَوْ عَلَى خَوَادِمِ الْجِهَةِ عَبْرَ Docker، مَعَ أَدَوَاتٍ جَاهِزَةٍ لِلتَّشْغِيلِ وَالنَّسْخِ الِاحْتِيَاطِيِّ وَالتَّحْدِيثِ.");

  // Outro
  closeCap();
  await page.evaluate(() => { window.__fm?.hide(); window.__fm?.chap("", 1); });
  chapters.push({ t: now(), title: "الْخَاتِمَةُ" });
  await page.evaluate(() => window.__fm?.card("مِرْآةُ الْمُسْتَقْبَلِ", "جَرِّبِ الْغَدَ قَبْلَ أَنْ تُقَرِّرَهُ",
    "وُكَلَاءُ مُتَخَصِّصُونَ • مُحَاكَاةٌ كَمِّيَّةٌ • مَحْكَمَةُ وُكَلَاءَ • آلَةُ زَمَنٍ • حَوْكَمَةٌ وَاعْتِمَادٌ بَشَرِيٌّ • عَرَبِيٌّ وَإِنْجِلِيزِيٌّ"));
  open = { start: now(), text: "مِرْآةُ الْمُسْتَقْبَلِ: جَرِّبِ الْغَدَ قَبْلَ أَنْ تُقَرِّرَهُ." };
  await sleep(6500);
  closeCap();
} finally {
  clearInterval(ticker);
  await cdp.send("Page.stopScreencast").catch(() => {});
  ffmpeg.stdin.end();
  await new Promise((r) => ffmpeg.on("close", r));
  await browser.close();
  const total = now();
  fs.writeFileSync(path.join(OUT, `${NAME}.srt`),
    srt.map((c, i) => `${i + 1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${c.text}\n`).join("\n"), "utf8");
  const mmss = (ms) => `${String(Math.floor(ms / 60000)).padStart(2, "0")}:${String(Math.floor(ms / 1000) % 60).padStart(2, "0")}`;
  fs.writeFileSync(path.join(OUT, "chapters-hotel.txt"), chapters.map((c) => `${mmss(c.t)} ${c.title}`).join("\n") + "\n", "utf8");
  console.log(`duration ${mmss(total)} · captions ${srt.length} · frames ${written} · page errors ${errors.length}`);
  if (errors.length) console.log(errors.slice(0, 5).join("\n"));
}
