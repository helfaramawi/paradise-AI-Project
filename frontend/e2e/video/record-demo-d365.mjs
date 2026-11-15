// Records the Arabic (Modern Standard Arabic) demo "Future Mirror AI + Dynamics 365 Finance & Operations"
// from the REAL running app and the local F&O simulator (tools/d365fo-simulator, compose profile d365sim):
// why connect the ERP, the simulator and its Arabic data, the OData interface (explorer page), connecting
// and syncing in Future Mirror, a second company, a full decision on the synced ERP data, safety, and the
// move to a real F&O environment.
//
//   ops/d365-sim.sh            # stack + simulator, connection configured (do NOT sync before recording)
//   BASE_URL=http://localhost:8080 SIM_URL=https://localhost:8443 OUT_DIR=../docs/video node e2e/video/record-demo-d365.mjs
//
// Captions are fully diacritised Modern Standard Arabic so the voice-over reads them correctly:
// ops\make-voiceover-d365.bat adds the female voice (ar-EG-SalmaNeural) and calm background music.
// All data is synthetic (two fictitious Egyptian companies); the simulator is not a Microsoft product.
// Writes: future-mirror-demo-d365.mp4, .srt (narration, for voice-over), chapters-d365.txt.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL || "http://localhost:5173";
const OUT = path.resolve(process.env.OUT_DIR || "../docs/video");
const NAME = process.env.VIDEO_NAME || "future-mirror-demo-d365";
const SIM = process.env.SIM_URL || "https://localhost:8443";
const SIM_SECRET = process.env.SIM_SECRET || "fm-sim-secret-2026";
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
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ["--force-color-profile=srgb", "--font-render-hinting=none"] });
const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, locale: "ar-EG", ignoreHTTPSErrors: true });
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
// Paced for the female voice at +5% (about 1.65 words a second on diacritised text), so the
// voice-over fits each caption without freezing the picture.
const readMs = (t) => Math.max(2800, 500 + t.split(/\s+/).length * 605);
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
const TOTAL_CH = 14;
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

// ------------------------------------------------------------------ simulator + slides helpers
async function simGo(p, settle = 1500) {
  await page.goto(SIM + p);
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.mouse.move(mx, my);
  await sleep(settle);
}
async function slide(title, sub, lines, kickText) {   // a full-screen card with narration over it
  closeCap();
  await page.evaluate(() => window.__fm?.hide());
  await page.evaluate(([k, ti, su]) => window.__fm?.card(k, ti, su), [kickText || kick, title, sub]);
  await sleep(900);
  for (const l of lines) await say(l);
  closeCap();
  await page.evaluate(() => { window.__fm?.hide(); window.__fm?.uncard(); });
  await sleep(700);
}
const conn = () => page.getByTestId("conn-d365_fo");
const lastMsg = () => conn().locator("div.rounded-lg").last();
async function syncNow() {
  const before = await conn().innerText();
  await click(conn().getByRole("button", { name: /^(مزامنة|Sync)$/ }), 400);
  await page.waitForFunction((b) => {
    const el = document.querySelector('[data-testid="conn-d365_fo"]');
    return el && el.innerText !== b && /rows \d+/.test(el.innerText);
  }, before, { timeout: 60_000 }).catch(() => {});
  await sleep(900);
}
async function setLegalEntity(le) {
  await click(page.getByTestId("conn-configure-d365_fo"), 900);
  const f = page.getByTestId("cfg-legal_entity");
  await scrollToEl(f, 260);
  await click(f, 200);
  await f.fill("");
  await page.keyboard.type(le, { delay: 90 });
  await sleep(400);
  await click(page.getByTestId("cfg-save"), 1200);
  await click(page.getByTestId("conn-configure-d365_fo"), 700);
  await scroll(0, 900);
}

// ------------------------------------------------------------------ the demo
const QUESTION = "خفض التكاليف التشغيلية لشركة المستقبل للصناعات الغذائية بنسبة 8% خلال 12 شهراً دون التأثير على جودة الخدمة";
const TITLE = "خفض تكاليف التشغيل 8% - شركة المستقبل للصناعات الغذائية";
try {
  // Intro
  await simGo("/health", 300);
  await page.evaluate(() => window.__fm?.card("عَرْضٌ تَوْضِيحِيٌّ", "مِرْآةُ الْمُسْتَقْبَلِ وَ Dynamics 365",
    "رَبْطُ النِّظَامِ الْمُحَاسَبِيِّ لِلشَّرِكَةِ بِمِرْآةِ الْمُسْتَقْبَلِ: مِنْ قُيُودِ الدَّفَاتِرِ إِلَى قَرَارٍ مَدْرُوسٍ"));
  chapters.push({ t: 0, title: "الْمُقَدِّمَةُ" });
  for (const l of [
    "مَرْحَبًا بِكُمْ فِي مِرْآةِ الْمُسْتَقْبَلِ. فِي هَذَا الْعَرْضِ نَرْبِطُ الْمَنَصَّةَ بِنِظَامِ Dynamics 365 لِلْمَالِيَّةِ وَالْعَمَلِيَّاتِ.",
    "وَنَرَى خُطْوَةً بِخُطْوَةٍ كَيْفَ تَتَحَوَّلُ قُيُودُ الدَّفَاتِرِ الْمُحَاسَبِيَّةِ لِلشَّرِكَةِ إِلَى قَرَارٍ مَدْرُوسٍ، مَبْنِيٍّ عَلَى أَرْقَامِهَا الْفِعْلِيَّةِ.",
  ]) { open = { start: now(), text: l }; await sleep(readMs(l)); closeCap(); }
  await page.evaluate(() => window.__fm?.uncard());
  await sleep(700);

  // 1. Why connect the ERP
  await chapter("لِمَاذَا نَرْبِطُ النِّظَامَ الْمُحَاسَبِيَّ؟", "الْفَائِدَةُ لِلشَّرِكَةِ وَلِلْمُسْتَخْدِمِ");
  await slide("أَرْقَامٌ حَقِيقِيَّةٌ بَدَلَ التَّقْدِيرَاتِ", "تُبْنَى الْمُحَاكَاةُ عَلَى دَفَاتِرِ الشَّرِكَةِ نَفْسِهَا", [
    "بِدُونِ رَبْطٍ، يُدْخِلُ الْمُحَلِّلُ تَكَالِيفَ الشَّرِكَةِ يَدَوِيًّا، أَوْ يَنْقُلُهَا مِنْ مَلَفَّاتِ إِكْسِل، فَتَكُونُ تَقْدِيرِيَّةً، وَقَدْ تَكُونُ قَدِيمَةً.",
    "وَمَعَ الرَّبْطِ، تَقْرَأُ مِرْآةُ الْمُسْتَقْبَلِ قُيُودَ دَفْتَرِ الْأُسْتَاذِ الْعَامِّ مُبَاشَرَةً، فَتُبْنَى كُلُّ مُحَاكَاةٍ عَلَى أَرْقَامِ الشَّرِكَةِ الْفِعْلِيَّةِ.",
  ]);
  await slide("بَيَانَاتٌ مُحَدَّثَةٌ بِضَغْطَةِ زِرٍّ", "مُزَامَنَةٌ لِأَيِّ فَتْرَةٍ، وَلِأَيِّ شَرِكَةٍ فِي الْمَجْمُوعَةِ", [
    "تَتِمُّ الْمُزَامَنَةُ بِضَغْطَةِ زِرٍّ وَاحِدَةٍ، لِأَيِّ فَتْرَةٍ زَمَنِيَّةٍ، وَلِأَيِّ كِيَانٍ قَانُونِيٍّ دَاخِلَ النِّظَامِ.",
    "فَيُوَفِّرُ الْمُسْتَخْدِمُ سَاعَاتٍ مِنْ تَجْمِيعِ الْبَيَانَاتِ وَمُرَاجَعَتِهَا، وَيَبْدَأُ التَّحْلِيلَ فَوْرًا.",
  ]);
  await slide("قِرَاءَةٌ فَقَطْ، وَأَمَانٌ كَامِلٌ", "لَا تَكْتُبُ الْمَنَصَّةُ أَيَّ شَيْءٍ فِي النِّظَامِ الْمُحَاسَبِيِّ", [
    "الِاتِّصَالُ لِلْقِرَاءَةِ فَقَطْ، فَلَا تُعَدِّلُ الْمَنَصَّةُ أَيَّ قَيْدٍ فِي النِّظَامِ الْمُحَاسَبِيِّ.",
    "وَسِرُّ الِاتِّصَالِ يُحْفَظُ عَلَى الْخَادِمِ، وَلَا يُخَزَّنُ فِي قَاعِدَةِ الْبَيَانَاتِ، وَلَا يَظْهَرُ عَلَى الشَّاشَةِ.",
  ]);
  await slide("مُطَابَقَةٌ وَتَتَبُّعٌ", "كُلُّ رَقْمٍ مَعْرُوفُ الْمَصْدَرِ، وَكُلُّ مُزَامَنَةٍ نُسْخَةٌ جَدِيدَةٌ", [
    "وَكُلُّ مُزَامَنَةٍ تُنْتِجُ تَقْرِيرَ مُطَابَقَةٍ وَنُسْخَةً جَدِيدَةً مِنَ الْبَيَانَاتِ، فَيُعْرَفُ مَصْدَرُ كُلِّ رَقْمٍ فِي الْقَرَارِ، وَيُسَجَّلُ ذَلِكَ فِي سِجِلِّ التَّدْقِيقِ.",
    "وَالنَّتِيجَةُ: قَرَارَاتٌ أَسْرَعُ، مَبْنِيَّةٌ عَلَى بَيَانَاتٍ أَدَقَّ، وَيُمْكِنُ مُرَاجَعَتُهَا فِي أَيِّ وَقْتٍ.",
  ]);

  // 2. The simulator
  await chapter("مُحَاكِي Dynamics 365", "بِيئَةُ اخْتِبَارٍ مَحَلِّيَّةٌ بِبَيَانَاتٍ عَرَبِيَّةٍ");
  await slide("كَيْفَ يَعْمَلُ الِاتِّصَالُ؟", "مِرْآةُ الْمُسْتَقْبَلِ ← رَمْزُ دُخُولٍ مِنْ Entra ID ← وَاجِهَةُ OData ← دَفْتَرُ الْأُسْتَاذِ الْعَامِّ", [
    "يَتِمُّ الِاتِّصَالُ فِي خُطْوَتَيْنِ: أَوَّلًا تَحْصُلُ الْمَنَصَّةُ عَلَى رَمْزِ دُخُولٍ مِنْ خِدْمَةِ Entra ID، بِاسْتِخْدَامِ مُعَرِّفِ التَّطْبِيقِ وَسِرِّهِ.",
    "ثُمَّ تَقْرَأُ قُيُودَ دَفْتَرِ الْأُسْتَاذِ مِنْ وَاجِهَةِ OData الْقِيَاسِيَّةِ فِي Dynamics 365، صَفْحَةً بَعْدَ صَفْحَةٍ.",
    "وَلِأَنَّ بِيئَةَ Dynamics الْحَقِيقِيَّةَ تَحْتَاجُ تَرَاخِيصَ مِنْ مَايْكْرُوسُوفْت، أَضَفْنَا مُحَاكِيًا مَحَلِّيًّا يَعْمَلُ عَلَى الْجِهَازِ نَفْسِهِ، وَيَسْتَجِيبُ بِالطَّرِيقَةِ نَفْسِهَا.",
    "يُشَغَّلُ الْمُحَاكِي بِمَلَفٍّ وَاحِدٍ فِي مُجَلَّدِ ops، فَيُشَغِّلُ الْمَنَصَّةَ وَالْمُحَاكِيَ مَعًا، وَيَضْبِطُ إِعْدَادَاتِ الِاتِّصَالِ تِلْقَائِيًّا.",
    "وَالْمُحَاكِي لَيْسَ مُنْتَجًا مِنْ مَايْكْرُوسُوفْت، بَلْ أَدَاةُ اخْتِبَارٍ، وَبَيَانَاتُهُ وَهْمِيَّةٌ بِالْكَامِلِ.",
  ]);
  await simGo("/", 1400);
  await say("هَذِهِ صَفْحَةُ الْمُحَاكِي. فِيهَا شَرِكَتَانِ مِصْرِيَّتَانِ وَهْمِيَّتَانِ: شَرِكَةُ الْمُسْتَقْبَلِ لِلصِّنَاعَاتِ الْغِذَائِيَّةِ فِي بُورْسَعِيدَ، وَشَرِكَةُ الْقَنَاةِ لِلْخَدَمَاتِ الْفُنْدُقِيَّةِ فِي الْإِسْمَاعِيلِيَّةِ.");
  await point(page.locator("table").first(), 400);
  await say("وَلِكُلِّ شَرِكَةٍ ثَلَاثُونَ عَمِيلًا، وَأَحَدَ عَشَرَ مُوَرِّدًا، وَأَكْثَرُ مِنْ أَلْفَيْ سَطْرِ قَيْدٍ، مِنْ يَنَايِرَ أَلْفَيْنِ وَخَمْسَةٍ وَعِشْرِينَ، إِلَى أُكْتُوبَرَ أَلْفَيْنِ وَسِتَّةٍ وَعِشْرِينَ.");
  await point(page.locator("table").last(), 400);
  await say("وَفِي الْأَسْفَلِ بَيَانَاتُ الِاتِّصَالِ: الرَّابِطُ، وَمُعَرِّفُ الْمُسْتَأْجِرِ، وَمُعَرِّفُ التَّطْبِيقِ، وَرَبْطُ الْحِسَابَاتِ الْمُقْتَرَحُ لِفِئَاتِ التَّكْلِفَةِ.");

  // 3. Arabic data
  await chapter("الْبَيَانَاتُ الْعَرَبِيَّةُ", "دَلِيلُ حِسَابَاتٍ، وَعُمَلَاءُ، وَمُوَرِّدُونَ، وَقُيُودٌ مُحَاسَبِيَّةٌ");
  await simGo("/browse/MainAccounts");
  await say("دَلِيلُ الْحِسَابَاتِ مُشْتَرَكٌ بَيْنَ الشَّرِكَتَيْنِ، وَفِيهِ اثْنَانِ وَثَلَاثُونَ حِسَابًا رَئِيسِيًّا بِأَسْمَاءٍ عَرَبِيَّةٍ: أُصُولٌ، وَخُصُومٌ، وَحُقُوقُ مِلْكِيَّةٍ، وَإِيرَادَاتٌ، وَمَصْرُوفَاتٌ.");
  await scroll(520, 1400);
  await say("وَحِسَابَاتُ الْمَصْرُوفَاتِ تَبْدَأُ بِالرَّقْمِ سِتَّةٍ: الرَّوَاتِبُ وَالْأُجُورُ، وَالْمُقَاوِلُونَ، وَتَرَاخِيصُ الْبَرْمَجِيَّاتِ، وَالِاسْتِضَافَةُ، وَالْإِيجَارُ، وَالْخَدَمَاتُ، وَالسَّفَرُ وَالتَّدْرِيبُ.");
  await simGo("/browse/CustomersV3?company=egmf");
  await say("وَهَؤُلَاءِ عُمَلَاءُ شَرِكَةِ الْمُسْتَقْبَلِ: أَسْمَاءٌ عَرَبِيَّةٌ، وَمُدُنٌ مِصْرِيَّةٌ، وَأَرْقَامُ هَوَاتِفَ، وَحُدُودٌ ائْتِمَانِيَّةٌ، وَشُرُوطُ سَدَادٍ.");
  await simGo("/browse/VendorsV2?company=egmf");
  await say("وَالْمُوَرِّدُونَ مُصَنَّفُونَ فِي مَجْمُوعَاتٍ: مُقَاوِلُونَ، وَتِكْنُولُوجْيَا مَعْلُومَاتٍ، وَمَرَافِقُ، وَخَدَمَاتٌ، وَتَوْرِيدَاتٌ.");
  await simGo("/browse/GeneralJournalAccountEntries?company=egmf");
  await say("وَهَذِهِ قُيُودُ دَفْتَرِ الْأُسْتَاذِ الْعَامِّ. لِكُلِّ سَطْرٍ تَارِيخٌ، وَحِسَابٌ بِأَبْعَادِهِ الْمَالِيَّةِ، وَوَصْفٌ عَرَبِيٌّ، وَمَبْلَغٌ بِالْجُنَيْهِ الْمِصْرِيِّ.");
  await scroll(600, 1500);
  await say("فِيهَا الرَّوَاتِبُ لِكُلِّ إِدَارَةٍ، وَالتَّأْمِينَاتُ، وَفَوَاتِيرُ الْمُوَرِّدِينَ، وَالْمَبِيعَاتُ مَعَ ضَرِيبَةِ الْقِيمَةِ الْمُضَافَةِ، وَتَحْصِيلَاتُ الْعُمَلَاءِ.");
  await say("وَكُلُّ قَيْدٍ مُتَوَازِنٌ: الْمَدِينُ يُسَاوِي الدَّائِنَ، تَمَامًا كَمَا فِي نِظَامٍ مُحَاسَبِيٍّ حَقِيقِيٍّ.");

  // 4. OData
  await chapter("وَاجِهَةُ OData", "كَيْفَ يَقْرَأُ الْمُوَصِّلُ الْبَيَانَاتِ");
  await simGo("/explorer", 1400);
  await say("هَذَا مُسْتَكْشِفُ OData فِي الْمُحَاكِي. يُتِيحُ لَنَا أَنْ نَرَى بِأَعْيُنِنَا الطَّلَبَاتِ نَفْسَهَا الَّتِي تُرْسِلُهَا مِرْآةُ الْمُسْتَقْبَلِ.");
  await cap("أَوَّلًا نُدْخِلُ سِرَّ التَّطْبِيقِ، ثُمَّ نَطْلُبُ رَمْزَ الدُّخُولِ.");
  await click(page.locator("#secret"), 300);
  await page.keyboard.type(SIM_SECRET, { delay: 70 });
  await sleep(500);
  await click(page.locator("#btn-token"), 1200);
  await point(page.locator("#tok"), 400);
  await say("حَصَلْنَا عَلَى رَمْزِ دُخُولٍ صَالِحٍ لِمُدَّةِ سَاعَةٍ. وَهَذَا مَا تَفْعَلُهُ الْمَنَصَّةُ فِي بِدَايَةِ كُلِّ مُزَامَنَةٍ، دُونَ أَنْ يَظْهَرَ السِّرُّ.");
  const preset = (i) => page.locator(".preset").nth(i);
  await click(preset(0), 1000);
  await say("مُسْتَنَدُ الْخِدْمَةِ يُعَدِّدُ كِيَانَاتِ الْبَيَانَاتِ الْمُتَاحَةِ: الشَّرِكَاتُ، وَالْحِسَابَاتُ الرَّئِيسِيَّةُ، وَالْعُمَلَاءُ، وَالْمُوَرِّدُونَ، وَقُيُودُ دَفْتَرِ الْأُسْتَاذِ.");
  await click(preset(1), 1000);
  await say("وَالْبَيَانَاتُ الْوَصْفِيَّةُ تَشْرَحُ حُقُولَ كُلِّ كِيَانٍ وَأَنْوَاعَهَا، كَمَا فِي النِّظَامِ الْحَقِيقِيِّ.");
  await click(preset(2), 1000);
  await say("وَبِاسْتِعْلَامٍ بَسِيطٍ نَخْتَارُ الْحُقُولَ الَّتِي نُرِيدُهَا فَقَطْ، فَتَعُودُ الْحِسَابَاتُ بِأَسْمَائِهَا الْعَرَبِيَّةِ.");
  await click(preset(3), 1000);
  await say("وَيُمْكِنُ التَّصْفِيَةُ بِأَيِّ حَقْلٍ، حَتَّى بِالْعَرَبِيَّةِ: هُنَا عُمَلَاءُ بُورْسَعِيدَ فِي الشَّرِكَتَيْنِ، مَعَ الْعَدَدِ الْكُلِّيِّ.");
  await click(preset(4), 1000);
  await say("وَهَذِهِ قُيُودُ الرَّوَاتِبِ لِشَهْرِ أُكْتُوبَرَ، بِحِسَابِ الرَّوَاتِبِ وَالْأُجُورِ، وَبِأَبْعَادِ الْإِدَارَاتِ الْمُخْتَلِفَةِ.");
  await click(preset(5), 1200);
  await say("أَمَّا هَذَا فَهُوَ الِاسْتِعْلَامُ الَّذِي يُرْسِلُهُ الْمُوَصِّلُ فِعْلًا: آخِرُ اثْنَيْ عَشَرَ شَهْرًا، لِشَرِكَةٍ وَاحِدَةٍ، وَحَقْلَانِ فَقَطْ، هُمَا الْحِسَابُ وَالْمَبْلَغُ.");
  await point(page.locator("#status"), 400);
  await say("تَعُودُ النَّتَائِجُ عَلَى صَفَحَاتٍ مِنْ أَلْفِ سَطْرٍ، وَمَعَ كُلِّ صَفْحَةٍ رَابِطٌ لِلصَّفْحَةِ التَّالِيَةِ، فَيَتْبَعُهُ الْمُوَصِّلُ حَتَّى يَقْرَأَ كُلَّ الْبَيَانَاتِ.");
  await click(preset(6), 1000);
  await say("وَإِذَا أَخْطَأْنَا فِي اسْمِ حَقْلٍ، يَرُدُّ النِّظَامُ بِرِسَالَةِ خَطَأٍ وَاضِحَةٍ، وَتَعْرِضُهَا مِرْآةُ الْمُسْتَقْبَلِ كَمَا هِيَ، لِيَسْهُلَ الْإِصْلَاحُ.");

  // 5. Connect in Future Mirror
  await chapter("الرَّبْطُ فِي مِرْآةِ الْمُسْتَقْبَلِ", "إِعْدَادُ الِاتِّصَالِ وَاخْتِبَارُهُ");
  await cap("نَدْخُلُ بِحِسَابِ مُدِيرِ الْمَنَصَّةِ.");
  await login("admin@futuremirror.demo");
  await go("/data", 1800);
  await say("وَنَفْتَحُ صَفْحَةَ مَصَادِرِ الْبَيَانَاتِ. هُنَا كُلُّ الْمُوَصِّلَاتِ الْمُتَاحَةِ: أُودُو، وَ Dynamics 365، وَسَاب، وَوَاجِهَاتُ REST، وَقَوَاعِدُ الْبَيَانَاتِ.");
  await point(conn(), 500);
  await say("هَذِهِ بِطَاقَةُ Dynamics 365 لِلْمَالِيَّةِ وَالْعَمَلِيَّاتِ. وَلَا تَظْهَرُ أَزْرَارُ الْإِعْدَادِ وَالِاخْتِبَارِ وَالْمُزَامَنَةِ إِلَّا لِمَنْ يَمْلِكُ صَلَاحِيَّةَ إِدَارَةِ الْمُوَصِّلَاتِ.");
  await click(page.getByTestId("conn-configure-d365_fo"), 1000);
  await scrollToEl(page.getByTestId("conn-settings-d365_fo"), 90);
  await say("فِي الْإِعْدَادَاتِ: رَابِطُ الْبِيئَةِ، وَمُعَرِّفُ الْمُسْتَأْجِرِ، وَمُعَرِّفُ التَّطْبِيقِ، وَالْكِيَانُ الْقَانُونِيُّ، وَالْفَتْرَةُ الْمَطْلُوبَةُ. وَقَدْ مَلَأَهَا سِكْرِبْتُ التَّشْغِيلِ تِلْقَائِيًّا.");
  await say("وَلَا يُوجَدُ حَقْلٌ لِلسِّرِّ: فَالسِّرُّ يُوضَعُ فِي مَلَفِّ الْإِعْدَادَاتِ عَلَى الْخَادِمِ، وَتُظْهِرُ الْبِطَاقَةُ فَقَطْ أَنَّهُ مَوْجُودٌ.");
  await click(page.getByRole("button", { name: /إظهار الحقول المتقدمة/ }), 1000);
  await say("وَفِي الْحُقُولِ الْمُتَقَدِّمَةِ يُمْكِنُ تَغْيِيرُ كِيَانِ الْبَيَانَاتِ وَأَسْمَاءِ الْحُقُولِ، لِأَنَّ بَعْضَ الشَّرِكَاتِ تُخَصِّصُ كِيَانَاتِهَا، وَكَذَلِكَ جِهَةُ تَسْجِيلِ الدُّخُولِ.");
  await scrollToEl(page.getByTestId("map-prefix-0"), 260);
  await say("ثُمَّ رَبْطُ الْحِسَابَاتِ: كُلُّ بَادِئَةٍ لِرَقْمِ الْحِسَابِ تُوَجَّهُ إِلَى فِئَةِ تَكْلِفَةٍ. فَالْحِسَابَاتُ الَّتِي تَبْدَأُ بِوَاحِدٍ وَسِتِّينَ تَذْهَبُ إِلَى تَكَالِيفِ الْأَفْرَادِ.");
  await say("وَتُطَبَّقُ أَطْوَلُ بَادِئَةٍ مُطَابِقَةٍ، فَنُفَرِّقُ بَيْنَ تَرَاخِيصِ الْبَرْمَجِيَّاتِ وَالْبِنْيَةِ التَّحْتِيَّةِ دَاخِلَ الْمَجْمُوعَةِ نَفْسِهَا.");
  await click(page.getByTestId("conn-configure-d365_fo"), 700);
  await scroll(0, 900);
  await cap("نَضْغَطُ اخْتِبَارَ الِاتِّصَالِ.");
  await click(conn().getByRole("button", { name: /^(اختبار|Test)$/ }), 2200);
  await point(lastMsg(), 400);
  await say("تَمَّتِ الْمُصَادَقَةُ، وَدَفْتَرُ الْأُسْتَاذِ قَابِلٌ لِلْقِرَاءَةِ. الِاتِّصَالُ جَاهِزٌ.");

  // 6. Sync
  await chapter("الْمُزَامَنَةُ", "مِنْ قُيُودِ الدَّفْتَرِ إِلَى مَلَفِّ تَكَالِيفِ الشَّرِكَةِ");
  await scroll(620, 1300);
  await say("قَبْلَ الْمُزَامَنَةِ، هَذِهِ هِيَ الْبَيَانَاتُ الْحَالِيَّةُ: بَيَانَاتٌ تَوْضِيحِيَّةٌ لِلْعَرْضِ، تُقَدِّرُ التَّكَالِيفَ السَّنَوِيَّةَ بِنَحْوِ مِئَةٍ وَعِشْرِينَ مِلْيُونَ جُنَيْهٍ.");
  await scroll(0, 900);
  await cap("نَضْغَطُ الْآنَ زِرَّ الْمُزَامَنَةِ.");
  await syncNow();
  await point(lastMsg(), 400);
  await say("قَرَأَتِ الْمَنَصَّةُ أَلْفًا وَمِئَتَيْنِ وَوَاحِدًا وَثَلَاثِينَ سَطْرًا مِنْ قُيُودِ آخِرِ اثْنَيْ عَشَرَ شَهْرًا، فِي ثَوَانٍ مَعْدُودَةٍ، وَتَغَيَّرَتْ ثَمَانِيَةُ حُقُولٍ.");
  await scroll(620, 1400);
  await say("وَأَصْبَحَتِ التَّكَالِيفُ الْآنَ مِنْ دَفَاتِرِ الشَّرِكَةِ: نَحْوُ مِئَةٍ وَسَبْعَةٍ وَعِشْرِينَ مِلْيُونَ جُنَيْهٍ، مِنْهَا ثَلَاثَةٌ وَسَبْعُونَ مِلْيُونًا لِلْأَفْرَادِ، وَسَبْعَةَ عَشَرَ مِلْيُونًا وَنِصْفٌ لِلْمُقَاوِلِينَ.");
  await say("وَكُلُّ حَقْلٍ مُسْتَوْرَدٍ عَلَيْهِ شَارَةٌ خَضْرَاءُ، فَيَعْرِفُ الْمُسْتَخْدِمُ أَيَّ الْأَرْقَامِ جَاءَ مِنَ النِّظَامِ الْمُحَاسَبِيِّ، وَأَيُّهَا مَا زَالَ افْتِرَاضًا.");
  await scroll(1100, 1300);
  await say("وَحُفِظَتِ الْبَيَانَاتُ كَنُسْخَةٍ جَدِيدَةٍ، مَعَ بَقَاءِ النُّسْخَةِ السَّابِقَةِ لِلْمُقَارَنَةِ أَوِ الرُّجُوعِ إِلَيْهَا.");
  await say("وَتَفْحَصُ لَوْحَةُ جَوْدَةِ الْبَيَانَاتِ الِاتِّسَاقَ تِلْقَائِيًّا. وَهُنَا تُنَبِّهُ إِلَى أَنَّ هَامِشَ الرِّبْحِ الْمَأْخُوذَ مِنْ بَيَانَاتِ الْعَرْضِ لَا يَتَّسِقُ مَعَ التَّكَالِيفِ الْجَدِيدَةِ، وَهَذَا مُتَوَقَّعٌ مَعَ بَيَانَاتِ الِاخْتِبَارِ.");
  await say("أَمَّا الْحِسَابَاتُ الَّتِي لَا تُطَابِقُ أَيَّ بَادِئَةٍ، كَالْإِيرَادَاتِ وَالْأُصُولِ، فَتُسْتَبْعَدُ، وَيُبْلَغُ عَنْهَا فِي تَقْرِيرِ الْمُطَابَقَةِ.");
  await scroll(0, 900);

  // 7. Second company
  await chapter("شَرِكَةٌ ثَانِيَةٌ", "الْمُزَامَنَةُ لِأَيِّ كِيَانٍ قَانُونِيٍّ فِي الْمَجْمُوعَةِ");
  await cap("لِلشَّرِكَةِ الثَّانِيَةِ نُغَيِّرُ الْكِيَانَ الْقَانُونِيَّ فَقَطْ، ثُمَّ نُزَامِنُ مِنْ جَدِيدٍ.");
  await setLegalEntity("EGHS");
  await syncNow();
  await scroll(620, 1400);
  await say("شَرِكَةُ الْقَنَاةِ لِلْخَدَمَاتِ الْفُنْدُقِيَّةِ أَصْغَرُ، فَتَكَالِيفُهَا السَّنَوِيَّةُ نَحْوُ خَمْسِينَ مِلْيُونَ جُنَيْهٍ فَقَطْ.");
  await say("وَهَكَذَا تَخْدُمُ الْمَنَصَّةُ مَجْمُوعَةَ شَرِكَاتٍ كَامِلَةً مِنْ نِظَامٍ مُحَاسَبِيٍّ وَاحِدٍ، وَيُحَلَّلُ كُلُّ قَرَارٍ عَلَى أَرْقَامِ الشَّرِكَةِ الْمَعْنِيَّةِ بِهِ.");
  await scroll(0, 900);
  await cap("نَعُودُ إِلَى شَرِكَةِ الْمُسْتَقْبَلِ لِنَبْنِيَ عَلَيْهَا قَرَارًا.");
  await setLegalEntity("EGMF");
  await syncNow();
  await sleep(600);

  // 8. Decision on ERP data
  await chapter("قَرَارٌ مَبْنِيٌّ عَلَى بَيَانَاتٍ حَقِيقِيَّةٍ", "خَفْضُ تَكَالِيفِ التَّشْغِيلِ فِي شَرِكَةِ الْمُسْتَقْبَلِ");
  await go("/decisions/new");
  await say("الْآنَ نَطْرَحُ سُؤَالًا إِدَارِيًّا حَقِيقِيًّا عَلَى هَذِهِ الْأَرْقَامِ.");
  await click(page.getByTestId("question-input"), 300);
  await page.keyboard.type(QUESTION, { delay: 26 });
  await sleep(700);
  await say("كَيْفَ نَخْفِضُ تَكَالِيفَ التَّشْغِيلِ فِي شَرِكَةِ الْمُسْتَقْبَلِ بِنِسْبَةِ ثَمَانِيَةٍ فِي الْمِائَةِ خِلَالَ اثْنَيْ عَشَرَ شَهْرًا، دُونَ التَّأْثِيرِ عَلَى جَوْدَةِ الْخِدْمَةِ؟");
  await cap("تُفَسِّرُ الْمَنَصَّةُ السُّؤَالَ وَتَسْتَخْرِجُ عَنَاصِرَهُ.");
  await click(page.getByTestId("parse-btn"), 1400);
  await page.locator("label", { hasText: "عنوان القرار" }).locator("input").fill(TITLE).catch(() => {});
  await say("تَعَرَّفَتِ الْمَنَصَّةُ عَلَى نَوْعِ الْقَرَارِ، وَعَلَى النِّسْبَةِ الْمُسْتَهْدَفَةِ، وَعَلَى الْمُدَّةِ، وَيُرَاجِعُهَا الْمُسْتَخْدِمُ قَبْلَ الْمُتَابَعَةِ.");
  await click(page.getByTestId("next-2"), 1200);
  await say("ثُمَّ نُرَاجِعُ الضَّوَابِطَ: مُوَازَنَةُ التَّنْفِيذِ، وَأَقْصَى زِيَادَةٍ مَقْبُولَةٍ فِي تَأْخِيرِ الْمَشْرُوعَاتِ، وَالْحَدُّ الْأَدْنَى لِرِضَا الْعُمَلَاءِ.");
  await click(page.getByTestId("next-3"), 1200);
  await say("وَفِي خُطْوَةِ الْبَيَانَاتِ نَرَى أَنَّ الْإِصْدَارَ الْمُخْتَارَ هُوَ الَّذِي زَامَنَّاهُ لِلتَّوِّ مِنْ Dynamics 365، فَكُلُّ مَا سَيَأْتِي مَبْنِيٌّ عَلَى أَرْقَامِ الشَّرِكَةِ.");
  await cap("نُطْلِقُ التَّحْلِيلَ.");
  await click(page.getByTestId("launch-btn"), 600);

  // 9. Execution and court
  await page.waitForURL(/\/execution\//);
  await chapter("غُرْفَةُ التَّنْفِيذِ وَمَحْكَمَةُ الْوُكَلَاءِ", "وُكَلَاءُ مُتَخَصِّصُونَ يُحَلِّلُونَ أَرْقَامَ الشَّرِكَةِ وَيَتَنَاظَرُونَ");
  await say("يَعْمَلُ الْوُكَلَاءُ الْمُتَخَصِّصُونَ الْآنَ بِالتَّوَازِي، وَكُلُّ وَكِيلٍ يَقْرَأُ مَلَفَّ التَّكَالِيفِ الَّذِي جَاءَ مِنَ النِّظَامِ الْمُحَاسَبِيِّ.");
  await point(page.getByTestId("event-feed"), 300);
  await say("الْمُدِيرُ الْمَالِيُّ يَحْسُبُ الْوَفْرَ الْمُمْكِنَ، وَمُدِيرُ الْمَوَارِدِ الْبَشَرِيَّةِ يَزِنُ أَثَرَهُ عَلَى الْعَامِلِينَ، وَالْفَرِيقُ الْأَحْمَرُ يَبْحَثُ عَنْ نِقَاطِ الضَّعْفِ.");
  await page.getByTestId("to-court").waitFor({ timeout: 180_000 });
  await say("اكْتَمَلَ التَّحْلِيلُ. نَدْخُلُ مَحْكَمَةَ الْوُكَلَاءِ.");
  await click(page.getByTestId("to-court"), 600);
  await page.getByTestId("verdict-headline").waitFor();
  await sleep(1200);
  await point(page.getByTestId("verdict-headline"), 300);
  await say("وَهَذَا حُكْمُ مَحْكَمَةِ الْوُكَلَاءِ: تَوْصِيَةٌ مَبْنِيَّةٌ عَلَى الْأَدِلَّةِ وَالسِّيَاسَاتِ، لَا عَلَى عَدَدِ الْأَصْوَاتِ.");
  await say("وَالْفَرْقُ هُنَا جَوْهَرِيٌّ: الْأَدِلَّةُ مَحْسُوبَةٌ مِنْ تَكَالِيفِ الشَّرِكَةِ الْفِعْلِيَّةِ. فَحِينَ تَقُولُ الْمَحْكَمَةُ إِنَّ الرَّوَاتِبَ تُمَثِّلُ أَكْثَرَ مِنْ نِصْفِ التَّكَالِيفِ، فَهَذَا رَقْمٌ مِنْ دَفَاتِرِهَا.");
  await scrollToEl(page.getByTestId("debate"), 220);
  await say("وَتَعْرِضُ الْمُنَاظَرَةُ الْمَوَاقِفَ وَالِاعْتِرَاضَاتِ وَالرُّدُودَ، جَوْلَةً بَعْدَ جَوْلَةٍ، حَتَّى الْحَوْكَمَةِ.");
  await click(page.getByRole("tab", { name: /كاشف تصادم المستقبل/ }), 1200);
  await say("وَيَرْصُدُ كَاشِفُ التَّصَادُمِ التَّعَارُضَ بَيْنَ الْوَفْرِ الْمَالِيِّ وَبَيْنَ جَوْدَةِ الْخِدْمَةِ أَوِ الْعَامِلِينَ، وَيَقْتَرِحُ حُلُولًا بَدِيلَةً.");
  await scroll(0, 900);

  // 10. Futures and time machine
  await chapter("الْمُسْتَقْبَلَاتُ الثَّلَاثَةُ وَآلَةُ الزَّمَنِ", "مُحَاكَاةٌ كَمِّيَّةٌ تَنْطَلِقُ مِنْ تَكَالِيفِ الشَّرِكَةِ الْمُزَامَنَةِ");
  await go("/futures", 2200);
  await say("هُنَا ثَلَاثَةُ مُسْتَقْبَلَاتٍ مُحْتَمَلَةٍ لِلْقَرَارِ، بِأَرْقَامٍ مِنْ مُحَاكَاةِ مُونْت كَارْلُو لِأَلْفَيْ سِينَارْيُو، انْطِلَاقًا مِنْ تَكَالِيفِ الشَّرِكَةِ الَّتِي زَامَنَّاهَا.");
  await scrollToEl(page.getByTestId("future-A"), 110);
  for (const k of ["A", "B", "C"]) await point(page.getByTestId(`future-${k}`), 900);
  await say("لِكُلِّ مُسْتَقْبَلٍ: الْوَفْرُ الْمُتَوَقَّعُ وَنِطَاقُهُ، وَتَكْلِفَةُ التَّنْفِيذِ، وَالْأَثَرُ عَلَى التَّسْلِيمِ وَرِضَا الْعُمَلَاءِ، وَالْقُيُودُ الَّتِي يَسْتَوْفِيهَا أَوْ يُخَالِفُهَا.");
  await scroll(0, 900);
  await cap("وَفِي وَضْعِ مَاذَا لَوْ نُغَيِّرُ الْهَدَفَ، فَتُعَادُ الْمُحَاكَاةُ فَوْرًا.");
  const slider = page.locator('input[type="range"]').first();
  await point(slider, 400);
  await slider.fill("5");
  await sleep(2600);
  await say("خَفَّضْنَا الْهَدَفَ إِلَى خَمْسَةٍ فِي الْمِائَةِ، فَتَغَيَّرَتِ النَّتَائِجُ فِي جُزْءٍ مِنَ الثَّانِيَةِ، دُونَ حِفْظِ أَيِّ شَيْءٍ.");
  await go("/time-machine");
  await click(page.getByTestId("tm-stops").locator("button").nth(3), 1400);
  await click(page.getByTestId("tm-stops").locator("button").nth(4), 1400);
  await say("وَآلَةُ الزَّمَنِ تُرِينَا حَالَ الشَّرِكَةِ بَعْدَ سِتَّةِ أَشْهُرٍ، ثُمَّ بَعْدَ عَامٍ، إِذَا نُفِّذَ الْقَرَارُ: التَّكَالِيفُ، وَالْعَامِلُونَ، وَالْمَخَاطِرُ.");
  await go("/financial", 2000);
  await say("وَالْأَثَرُ الْمَالِيُّ يُقَارِنُ صَافِيَ الْعَائِدِ لِكُلِّ مُسْتَقْبَلٍ شَهْرًا بِشَهْرٍ، عَلَى مَدَى اثْنَيْ عَشَرَ شَهْرًا.");
  await scroll(620, 1500);
  await scroll(0, 900);

  // 11. Human approval
  await chapter("الِاعْتِمَادُ الْبَشَرِيُّ", "لَا يُنَفَّذُ شَيْءٌ دُونَ مُوَافَقَةِ الْمَسْؤُولِ");
  await go("/approvals", 1800);
  await say("لَا يُنَفَّذُ أَيُّ مُسْتَقْبَلٍ قَبْلَ الْمُوَافَقَاتِ الَّتِي تَشْتَرِطُهَا السِّيَاسَاتُ. نَخْتَارُ مُسْتَقْبَلًا، وَنُرْسِلُهُ لِلِاعْتِمَادِ.");
  let submitted = false;
  try {
    for (const k of ["C", "B", "A"]) {
      const pick = page.getByTestId(`pick-${k}`);
      if (await pick.isEnabled().catch(() => false)) { await click(pick, 1200); break; }
    }
    await click(page.getByTestId("ack"), 600);
    await click(page.getByTestId("submit-approval"), 1600);
    submitted = true;
  } catch (e) { errors.push(`approval submit: ${e}`); }
  if (submitted) {
    await cap("نَدْخُلُ الْآنَ بِحِسَابِ الْمُدِيرِ الْمَالِيِّ لِيَعْتَمِدَ الطَّلَبَ.");
    await logout();
    await login("cfo@futuremirror.demo");
    await go("/approvals", 1600);
    try {
      await scrollToEl(page.getByTestId("approve-btn").first(), 260);
      await click(page.getByTestId("approve-btn").first(), 1800);
    } catch (e) { errors.push(`approve: ${e}`); }
    await say("وَيَعْتَمِدُ الْمُدِيرُ الْمَالِيُّ الطَّلَبَ بِحِسَابِهِ، فَلَا يَعْتَمِدُ أَحَدٌ قَرَارًا أَرْسَلَهُ بِنَفْسِهِ، وَيُسَجَّلُ كُلُّ ذَلِكَ.");
  }

  // 12. Safety and audit
  await chapter("الْأَمَانُ وَالتَّدْقِيقُ", "اتِّصَالٌ لِلْقِرَاءَةِ فَقَطْ، وَسِجِلٌّ لَا يُمْكِنُ التَّلَاعُبُ بِهِ");
  await logout();
  await login("admin@futuremirror.demo");
  await go("/admin", 1800);
  await scroll(5000, 1800);
  await say("فِي سِجِلِّ التَّدْقِيقِ نَجِدُ كُلَّ خُطْوَةٍ قُمْنَا بِهَا: ضَبْطُ الْمُوَصِّلِ، وَالْمُزَامَنَاتُ، وَإِطْلَاقُ التَّحْلِيلِ، وَالِاعْتِمَادُ، مَعَ اسْمِ الْمُسْتَخْدِمِ وَالْوَقْتِ.");
  await say("وَالسِّجِلُّ مُتَسَلْسِلٌ بِالتَّجْزِئَةِ، فَأَيُّ تَعْدِيلٍ فِي أَيِّ سَطْرٍ يُكْشَفُ فَوْرًا.");
  await slide("ضَمَانَاتُ الِاتِّصَالِ", "قِرَاءَةٌ فَقَطْ • سِرٌّ عَلَى الْخَادِمِ • تَشْفِيرٌ مَعَ تَحَقُّقٍ كَامِلٍ مِنَ الشَّهَادَاتِ • صَلَاحِيَّاتٌ مُحَدَّدَةٌ", [
    "وَلِلتَّلْخِيصِ: الِاتِّصَالُ لِلْقِرَاءَةِ فَقَطْ، وَالسِّرُّ عَلَى الْخَادِمِ، وَالِاتِّصَالُ مُشَفَّرٌ مَعَ تَحَقُّقٍ كَامِلٍ مِنَ الشَّهَادَاتِ، وَلَا يُدِيرُ الْمُوَصِّلَاتِ إِلَّا الْمُخَوَّلُونَ.",
    "وَفِي Dynamics نَفْسِهِ يَرْتَبِطُ التَّطْبِيقُ بِمُسْتَخْدِمٍ لَهُ صَلَاحِيَّةُ قِرَاءَةٍ فَقَطْ، فَيَبْقَى نِطَاقُ الْبَيَانَاتِ تَحْتَ سَيْطَرَةِ الشَّرِكَةِ.",
  ]);

  // 13. Real environment
  await chapter("الِانْتِقَالُ إِلَى بِيئَةٍ حَقِيقِيَّةٍ", "مِنَ الْمُحَاكِي إِلَى Dynamics 365 لَدَى الشَّرِكَةِ");
  await slide("١. تَسْجِيلُ تَطْبِيقٍ فِي Entra ID", "مُعَرِّفُ التَّطْبِيقِ، وَمُعَرِّفُ الْمُسْتَأْجِرِ، وَسِرٌّ جَدِيدٌ", [
    "لِلِانْتِقَالِ إِلَى بِيئَةِ الشَّرِكَةِ الْحَقِيقِيَّةِ، يُسَجِّلُ مَسْؤُولُ الْأَنْظِمَةِ تَطْبِيقًا فِي Entra ID، وَيُنْشِئُ لَهُ سِرًّا.",
  ]);
  await slide("٢. إِضَافَةُ التَّطْبِيقِ فِي Dynamics 365", "System administration ← Microsoft Entra applications", [
    "ثُمَّ يُضِيفُ التَّطْبِيقَ فِي إِعْدَادَاتِ Dynamics 365، وَيَرْبِطُهُ بِمُسْتَخْدِمٍ لَهُ صَلَاحِيَّةُ قِرَاءَةِ دَفْتَرِ الْأُسْتَاذِ الْعَامِّ.",
  ]);
  await slide("٣. ضَبْطُ مِرْآةِ الْمُسْتَقْبَلِ", "السِّرُّ فِي مَلَفِّ ‎.env‎ • رَابِطُ الْبِيئَةِ الْحَقِيقِيَّةِ • اخْتِبَارٌ ثُمَّ مُزَامَنَةٌ", [
    "وَأَخِيرًا نَضَعُ السِّرَّ فِي مَلَفِّ الْإِعْدَادَاتِ عَلَى الْخَادِمِ، وَنُدْخِلُ رَابِطَ الْبِيئَةِ الْحَقِيقِيَّةِ، ثُمَّ نَخْتَبِرُ وَنُزَامِنُ، تَمَامًا كَمَا رَأَيْنَا مَعَ الْمُحَاكِي.",
  ]);
  await slide("حُزْمَةُ بَيَانَاتٍ عَرَبِيَّةٍ لِلِاسْتِيرَادِ", "نَفْسُ بَيَانَاتِ الْمُحَاكِي فِي مَلَفَّاتِ إِكْسِل، لِأَدَاةِ Data management", [
    "وَإِذَا أَرَدْتُمْ تَجْرِبَةَ الْبَيَانَاتِ الْعَرَبِيَّةِ نَفْسِهَا فِي بِيئَةٍ حَقِيقِيَّةٍ، فَهِيَ مُتَاحَةٌ كَحُزْمَةِ مَلَفَّاتِ إِكْسِل جَاهِزَةٍ لِلِاسْتِيرَادِ، مَعَ دَلِيلٍ بِالْعَرَبِيَّةِ وَالْإِنْجِلِيزِيَّةِ.",
  ]);

  // 14. Summary
  await chapter("الْخُلَاصَةُ", "مَاذَا تَكْسِبُ الشَّرِكَةُ وَالْمُسْتَخْدِمُ؟");
  await slide("لِلشَّرِكَةِ", "قَرَارَاتٌ عَلَى دَفَاتِرِهَا الْفِعْلِيَّةِ • لِكُلِّ شَرِكَاتِ الْمَجْمُوعَةِ • تَتَبُّعٌ كَامِلٌ • أَمَانٌ لَا يَمَسُّ النِّظَامَ", [
    "لِلشَّرِكَةِ: قَرَارَاتٌ مَبْنِيَّةٌ عَلَى دَفَاتِرِهَا الْفِعْلِيَّةِ، لِكُلِّ شَرِكَاتِ الْمَجْمُوعَةِ، مَعَ تَتَبُّعٍ كَامِلٍ، وَأَمَانٍ لَا يَمَسُّ النِّظَامَ الْمُحَاسَبِيَّ.",
  ]);
  await slide("لِلْمُسْتَخْدِمِ", "مُزَامَنَةٌ بِضَغْطَةٍ • سُؤَالٌ بِلُغَتِهِ • ثَلَاثَةُ مُسْتَقْبَلَاتٍ مَدْرُوسَةٍ فِي دَقَائِقَ", [
    "وَلِلْمُسْتَخْدِمِ: لَا مَزِيدَ مِنْ تَجْمِيعِ الْأَرْقَامِ يَدَوِيًّا. ضَغْطَةُ مُزَامَنَةٍ، ثُمَّ سُؤَالٌ بِلُغَتِهِ، ثُمَّ ثَلَاثَةُ مُسْتَقْبَلَاتٍ مَدْرُوسَةٍ فِي دَقَائِقَ.",
  ]);

  // Outro
  closeCap();
  await page.evaluate(() => { window.__fm?.hide(); window.__fm?.chap("", 1); });
  chapters.push({ t: now(), title: "الْخَاتِمَةُ" });
  await page.evaluate(() => window.__fm?.card("مِرْآةُ الْمُسْتَقْبَلِ", "جَرِّبِ الْغَدَ قَبْلَ أَنْ تُقَرِّرَهُ",
    "بَيَانَاتُ شَرِكَتِكَ مِنْ Dynamics 365 • وُكَلَاءُ مُتَخَصِّصُونَ • مُحَاكَاةٌ كَمِّيَّةٌ • حَوْكَمَةٌ وَاعْتِمَادٌ بَشَرِيٌّ"));
  open = { start: now(), text: "مِرْآةُ الْمُسْتَقْبَلِ: جَرِّبِ الْغَدَ قَبْلَ أَنْ تُقَرِّرَهُ، عَلَى بَيَانَاتِ شَرِكَتِكَ الْحَقِيقِيَّةِ." };
  await sleep(7500);
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
  fs.writeFileSync(path.join(OUT, "chapters-d365.txt"), chapters.map((c) => `${mmss(c.t)} ${c.title}`).join("\n") + "\n", "utf8");
  console.log(`duration ${mmss(total)} · captions ${srt.length} · frames ${written} · page errors ${errors.length}`);
  if (errors.length) console.log(errors.slice(0, 8).join("\n"));
}
