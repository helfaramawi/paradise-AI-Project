// Records the Egyptian-Arabic product demo of Future Mirror AI from the REAL running app, around the
// question "what if we collect 30% more revenue by contracting a collection agency?".
//
//   BASE_URL=http://localhost:8080 OUT_DIR=../docs/video node e2e/video/record-demo-eg.mjs
//
// Captions are in Egyptian dialect with full diacritics (tashkeel), so the voice-over reads them
// correctly: ops\make-voiceover-eg.bat adds the Egyptian female voice (ar-EG-SalmaNeural).
// Frames come from Chrome's screencast (crisp JPEG), are re-timed to a constant 25 fps and
// piped into ffmpeg (H.264 MP4). On-screen Arabic captions, chapter cards and a visible cursor
// are injected into the page, so Arabic shaping and RTL are rendered by the browser itself.
// Writes: future-mirror-demo-eg.mp4, .srt (narration, for voice-over), chapters-eg.txt.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL || "http://localhost:5173";
const OUT = path.resolve(process.env.OUT_DIR || "../docs/video");
const NAME = process.env.VIDEO_NAME || "future-mirror-demo-eg";
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
// Paced for the Egyptian female voice at +10% (about 1.75 words a second on diacritised text), so the
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
const QUESTION = "ماذا لو حققنا متحصلات إيرادات أكبر بنسبة 30 % من خلال التعاقد مع شركة تحصيل؟";
try {
  // Intro
  await go("/login", 600);
  await page.evaluate(() => window.__fm?.card("عَرْض تَوْضِيحِي لِلْمُنْتَج", "مِرْآةُ الْمُسْتَقْبَل",
    "سُؤَال وَاحِد: لَوْ اِتْعَاقِدْنَا مَعَ شِرْكِة تَحْصِيل، هَنْحَصَّل تَلَاتِين فِي الْمِيَّة زِيَادَة؟ وَالْمَنَصَّة هَتِجَاوِب بِالْأَرْقَام"));
  chapters.push({ t: 0, title: "الْمُقَدِّمَة" });
  open = { start: now(), text: "أَهْلًا بِيكُم فِي مِرْآةِ الْمُسْتَقْبَل، الْمَنَصَّة اللِّي بِتْخَلِّيك تِشُوف نَتِيجِة قَرَارَك قَبْل مَا تَاخُدُه." };
  await sleep(7000);
  closeCap();
  await page.evaluate(() => window.__fm?.uncard());
  await sleep(900);

  // 1. Sign-in
  await chapter("الدُّخُول وَالْوَاجْهَة", "حِسَاب لِكُلّ دُور فِي الشِّرْكَة، وَوَاجْهَة عَرَبِي كَامْلَة مِن الْيِمِين لِلشِّمَال");
  await say("هَنِبْدَأ مِن شَاشِة الدُّخُول. الْمَنَصَّة بِتِشْتَغَل عَرَبِي وَإِنْجِلِيزِي، وَإِحْنَا هِنَا شَغَّالِين بِالْعَرَبِي مِن الْيِمِين لِلشِّمَال.");
  await cap("هَنُدْخُل دِلْوَقْتِي بِحِسَاب مُحَلِّل الْقَرَارَات، وَهُوَّ اللِّي بِيِحَضَّر الْقَرَار وَيِبْعَتُه لِلتَّحْلِيل.");
  await login("analyst@futuremirror.demo");
  await point(page.getByTestId("platform-chips"), 300);
  await say("فُوق فِي الشَّرِيط تَلَات عَلَامَات وَاضْحَة: الْبَيَانَات اِفْتِرَاضِيَّة، وَالْوُكَلَاء شَغَّالِين بِقَوَاعِد مِن غِير نَمُوذَج لُغَوِي، وَالْإِجْرَاءَات الْخَارِجِيَّة مَقْفُولَة.");

  // 2. Command center
  await chapter("مَرْكَز الْقِيَادَة", "مُؤَشِّرَات الشِّرْكَة وَآخِر مَلَفّ قَرَار فِي نَظْرَة وَاحْدَة");
  await go("/");
  await say("دِي الصَّفْحَة الرَّئِيسِيَّة. هِنَا مُؤَشِّرَات الشِّرْكَة الْأَسَاسِيَّة: الْإِيرَادَات، وَالتَّكَالِيف، وَعَدَد الْمُوَظَّفِين، وَالِاسْتِغْلَال، وَرِضَا الْعُمَلَاء.");
  await say("وَتَحْت هَيْظْهَر آخِر مَلَفّ قَرَار: تَوْصِيَة الْهَيْئَة، وَكَارْت لِكُلّ مُسْتَقْبَل بَدِيل. خَلِّينَا نِسْأَل سُؤَال جِدِيد.");

  // 3. Intake
  await chapter("السُّؤَال", "مَاذَا لَوْ حَقَّقْنَا مُتَحَصَّلَات إِيرَادَات أَكْبَر بِنِسْبِة تَلَاتِين فِي الْمِيَّة مِن خِلَال شِرْكِة تَحْصِيل؟");
  await go("/decisions/new");
  await cap("بِنِكْتِب السُّؤَال زَيّ مَا الْإِدَارَة بِتِسْأَلُه بِالظَّبْط، بِالْعَرَبِي.");
  await click(page.getByTestId("question-input"), 300);
  await page.keyboard.type(QUESTION, { delay: 35 });
  await sleep(800);
  await say("السُّؤَال: مَاذَا لَوْ حَقَّقْنَا مُتَحَصَّلَات إِيرَادَات أَكْبَر بِنِسْبِة تَلَاتِين فِي الْمِيَّة، مِن خِلَال التَّعَاقُد مَعَ شِرْكِة تَحْصِيل؟");
  await cap("الْمَنَصَّة بِتِفْهَم السُّؤَال وَتِطَلَّع مِنُّه الْعَنَاصِر الْمُهِمَّة.");
  await click(page.getByTestId("parse-btn"), 1600);
  await say("شُوفُوا: عِرْفِت لِوَحْدَهَا إِنّ دَه قَرَار تَحْصِيل إِيرَادَات مِش خَفْض تَكَالِيف، وَإِنّ الْهَدَف تَلَاتِين فِي الْمِيَّة، وَإِنّ فِيه شِرْكِة تَحْصِيل فِي الصُّورَة.");
  await click(page.getByTestId("next-2"), 1200);
  await say("هِنَا الضَّوَابِط التَّنْفِيذِيَّة بِلُغِة التَّحْصِيل: الْهَدَف، وَالْمُدَّة، وَمِيزَانِيِّة التَّحْصِيل الرَّقْمِي، وَالزِّيَادَة الْمَقْبُولَة فِي الشَّكَاوَى.");
  await scroll(500, 1200);
  await scroll(0, 900);
  await click(page.getByTestId("next-3"), 1200);
  await say("آخِر خُطْوَة نِخْتَار نُسْخِة الْبَيَانَات. عَلَامِة الْجَوْدَة بِتْنَبِّهْنَا إِنّ فِيه عَدَم اِتِّسَاق فِي هَامِش الرِّبْح، وَدَه تَنْبِيه حَقِيقِي مَحْسُوب.");
  await cap("يَلَّا نِبْعَت الْقَرَار لِلتَّحْلِيل وَنْصَحِّي الْوُكَلَاء.");
  await click(page.getByTestId("launch-btn"), 600);

  // 4. Execution room
  await page.waitForURL(/\/execution\//);
  await chapter("غُرْفِة التَّنْفِيذ الْمُبَاشِر", "عَشَر مَرَاحِل وَسَبْعَة وُكَلَاء مُتَخَصِّصِين شَغَّالِين مَعَ بَعْض، وَالْأَحْدَاث جَايَّة مِن السِّيرْفَر بِجَدّ");
  await say("دِي غُرْفِة التَّنْفِيذ. كُلّ حَدَث بِتِشُوفُوه هِنَا جَايّ فِعْلًا مِن السِّيرْفَر وَهُوَّ شَغَّال، مِش فِيدْيُو مِتْسَجِّل.");
  await point(page.getByTestId("flow-graph"), 300);
  await say("الرَّسْمَة بِتِوَرِّي الْعَشَر مَرَاحِل، وَسَبْعَة وُكَلَاء بِيِحَلِّلُوا فِي نَفْس الْوَقْت: الِاسْتِرَاتِيجِيَّة، وَالْمَالِيَّة، وَالْعَمَلِيَّات، وَالْمَوَارِد الْبَشَرِيَّة، وَالتَّسْلِيم، وَالْقَانُونِيَّة، وَالْمُخَاطَر.");
  await point(page.getByTestId("event-feed"), 300);
  await say("وَسِجِلّ التَّنْفِيذ بِيِعْرِض كُلّ نَتِيجَة أَوِّل مَا تِطْلَع: الْمُدِير الْمَالِي بِيْحَسِب الْمُتَأَخِّرَات، وَالْقَانُونِي بِيْنَبِّه لِحِمَايِة بَيَانَات الْعُمَلَاء، وَالْفَرِيق الْأَحْمَر بِيِعْتِرِض.");
  await page.getByTestId("to-court").waitFor({ timeout: 180_000 });
  await say("مَلَفّ الْقَرَار جَاهِز. إِحْنَا بِنْهَدِّي بَيْن الْمَرَاحِل عَشَان الْمُتَابْعَة تِبْقَى سَهْلَة، وَوَقْت الْحِسَاب الْحَقِيقِي ظَاهِر لِوَحْدُه بِكُلّ شَفَافِيَّة.");
  await cap("يَلَّا نُدْخُل مَحْكَمِة الْوُكَلَاء.");
  await click(page.getByTestId("to-court"), 600);

  // 5. Agent court
  await page.getByTestId("verdict-headline").waitFor();
  await chapter("مَحْكَمِة الْوُكَلَاء", "مَوَاقِف وَأَدِلَّة وَاعْتِرَاضَات وَرُدُود، وَحُكْم بِوَزْن الْأَدِلَّة مِش بِالتَّصْوِيت");
  await point(page.getByTestId("court-mode"), 300);
  await say("الشَّرِيط دَه بِيِقُول إِنّ كُلّ جُمْلَة هِنَا مَحْسُوبَة مِن بَيَانَات التَّشْغِيل دَه، مِش كَلَام مَكْتُوب قَبْل كِدَه.");
  await point(page.getByTestId("verdict-headline"), 300);
  await say("حُكْم الْهَيْئَة: مَفِيش مُسْتَقْبَل بِيْحَقَّق كُلّ الْأَهْدَاف زَيّ مَا اِتْكَتَبِت. وَالْمُسْتَقْبَل جِيم، تَطْوِير التَّحْصِيل جُوَّا الشِّرْكَة، هُوَّ أَقْوَى أَسَاس.");
  await say("وَالْمُسْتَقْبَل أَلِف، التَّعْهِيد الْكَامِل لِشِرْكِة التَّحْصِيل، مَرْفُوض مِن الْحَوْكَمَة. وَالْحُكْم مِش بِالْأَغْلَبِيَّة: بِيُوزِن جَوْدِة الْأَدِلَّة وَالسِّيَاسَات وَعَدَم الْيَقِين.");
  await scrollToEl(page.getByTestId("debate"), 220);
  await say("تَبْوِيب الْمُنَاظْرَة بِيِعْرِض النِّقَاش عَلَى أَرْبَع جَوْلَات: الْمَوَاقِف، وَبَعْدِين اِعْتِرَاضَات الْفَرِيق الْأَحْمَر وَالرُّدُود، وَبَعْدِين التَّصَادُمَات، وَفِي الْآخِر الْحَوْكَمَة.", 1200);
  await say("مِثَال: الْفَرِيق الْأَحْمَر قَال إِنّ الزِّيَادَة الْكِبِيرَة فِي أَوِّل شَهْرِين مِش مُعَدَّل دَايِم، لِأَنّ الدِّيُون الْقَدِيمَة بِتِخْلَص. وَالِاسْتِرَاتِيجِيَّة وَافْقِت.");
  await click(page.getByRole("tab", { name: /مواقف الوكلاء/ }), 1200);
  await say("فِي مَوَاقِف الْوُكَلَاء، كُلّ نَتِيجَة مِتْصَنَّفَة: حَقِيقَة، أَوْ تَقْدِير، أَوْ اِفْتِرَاض، أَوْ تَوْصِيَة، وَمَعَاهَا دَرَجِة الثِّقَة وَالدَّلِيل.");
  await scroll(await page.evaluate(() => window.scrollY + 420), 1300);
  await click(page.getByRole("tab", { name: /كاشف تصادم المستقبل/ }), 1200);
  await scrollToEl(page.getByTestId("collision-card").first(), 160);
  await say("كَاشِف التَّصَادُم بِيِلْقُط التَّعَارُض بَيْن الْوُكَلَاء: فُلُوس شِرْكِة التَّحْصِيل بِتِتْصَادِم مَعَ عَلَاقِتْنَا بِكِبَار الْعُمَلَاء وَالْجِهَات الْحُكُومِيَّة.");
  await say("وَتَصَادُم تَانِي: هَدَف التَّلَاتِين فِي الْمِيَّة أَكْبَر مِن حَجْم الْمُتَأَخِّرَات نَفْسَهَا. وَكُلّ كَارْت فِيه الشِّدَّة، وَالْأَهْدَاف الْمِتْأَثْرَة، وَالْحُلُول الْبَدِيلَة.");
  await scroll(0, 900);

  // 6. Three futures
  await chapter("الْمُسْتَقْبَلَات التَّلَاتَة", "مُحَاكَاة مُونْت كَارْلُو لِأَلْفَيْن سِينَارْيُو لِكُلّ اِسْتِرَاتِيجِيَّة، وَإِعَادِة حِسَاب فِي ثَانْيَة");
  await go("/futures", 2200);
  await say("هِنَا بِنْقَارِن تَلَات اِسْتِرَاتِيجِيَّات جَنْب بَعْض. الْأَرْقَام جَايَّة مِن مُحَرِّك مُحَاكَاة كَمِّي، بِأَلْفَيْن سَحْبَة عَشْوَائِيَّة.");
  await scrollToEl(page.getByTestId("future-A"), 110);
  await point(page.getByTestId("future-A"), 300);
  await say("الْمُسْتَقْبَل أَلِف، التَّعْهِيد الْكَامِل: بِيْزَوِّد الْمُتَحَصَّلَات حَوَالِي عَشَرَة فِي الْمِيَّة، بَسّ بِيِكْسَر تَلَات قُيُود إِلْزَامِيَّة: الشَّكَاوَى، وَرِضَا الْعُمَلَاء، وَفَقْد كِبَار الْعُمَلَاء.");
  await point(page.getByTestId("future-B"), 300);
  await say("الْمُسْتَقْبَل بِيه، النَّمُوذَج الْهَجِين: شِرْكِة التَّحْصِيل لِلدِّيُون الْأَقْدَم مِن تِسْعِين يُوم بَسّ، وَالْبَاقِي تَحْصِيل رَقْمِي جُوَّا الشِّرْكَة. حَوَالِي تِسْعَة فِي الْمِيَّة.");
  await point(page.getByTestId("future-C"), 300);
  await say("وَالْمُسْتَقْبَل جِيم، التَّطْوِير الدَّاخِلِي: عَشَرَة فِي الْمِيَّة مِن غِير عُمُولَات، وَأَعْلَى صَافِي مَنْفَعَة نَقْدِيَّة، وَمِن غِير مَا يِلْمِس عَلَاقِتْنَا بِالْعُمَلَاء.");
  await say("وَدِي الْحَقِيقَة اللِّي الْمُحَاكَاة كَشَفِتْهَا: مَفِيش وَلَا مُسْتَقْبَل بِيُوصَل لِتَلَاتِين فِي الْمِيَّة. أَقْصَى نِسْبَة وَاقْعِيَّة حَوَالِي تِسْعَة وَنُصّ فِي الْمِيَّة.");
  await say("لِيه؟ لِأَنّ شِرْكِة التَّحْصِيل بِتِشْتَغَل عَلَى الْمُتَأَخِّرَات بَسّ، وَدَه رَصِيد مَحْدُود. الْمُتَحَصَّلَات مِش مُمْكِن تِفْضَل أَكْبَر مِن الْمَبِيعَات لِمُدَّة طَوِيلَة.");
  await scroll(0, 900);
  await cap("وَضْع مَاذَا لَوْ: نِحَرَّك أَيّ شَرِيط فِي الضَّوَابِط، وَالْمُحَاكَاة تِتْعَاد فِي جُزْء مِن الثَّانْيَة.");
  const slider = page.locator('input[type="range"]').first();
  await point(slider, 400);
  await slider.fill("9");
  await sleep(2600);
  await say("نَزِّلْنَا الْهَدَف لِتِسْعَة فِي الْمِيَّة، فَظَهَرِت عَلَامِة وَضْع مَاذَا لَوْ. النَّتَايِج دِي مِش بِتِتْحِفِظ إِلَّا لَوْ إِحْنَا عَايْزِين.");
  await scroll(1500, 1800);
  await say("وَتَحْت فِيه مَسَار الْمُتَحَصَّلَات الْإِضَافِيَّة شَهْر بِشَهْر، وَجَدْوَل الْمُقَارْنَة الْكَامِل، وَأَيّ رَسْمَة تِتْحَوِّل لِجَدْوَل بِضَغْطَة وَاحْدَة.");
  await scroll(0, 900);

  // 7. Time machine
  await chapter("آلِة زَمَن الْقَرَار", "حَالِة الشِّرْكَة النَّهَارْدَه، وَبَعْد شَهْر، وَتَلَات شُهُور، وَسِتَّة، وَسَنَة");
  await go("/time-machine");
  await say("آلِة الزَّمَن بِتْوَرِّيك حَالِة الشِّرْكَة الْمُتَوَقَّعَة فِي أَيّ شَهْر: الْمُتَحَصَّلَات الشَّهْرِيَّة، وَالْمُتَأَخِّرَات، وَمُتَوَسِّط فَتْرِة التَّحْصِيل، وَالتَّدَفُّق النَّقْدِي، وَالشَّكَاوَى.");
  await click(page.getByTestId("tm-stops").locator("button").nth(3), 1400);
  await say("رُحْنَا لِلشَّهْر السَّادِس. كُلّ مُؤَشِّر بِيِقُولَك اِتْغَيَّر قَدّ إِيه مِن النَّهَارْدَه، وَتِقْدَر تِقَارِن الْمُسْتَقْبَلَات التَّلَاتَة فِي نَفْس الشَّهْر.");
  await click(page.getByTestId("tm-stops").locator("button").nth(4), 1400);
  await scroll(520, 1300);
  await scroll(0, 900);

  // 8. Financial, risk, lab
  await chapter("التَّحْلِيل الْمَالِي وَالْمُخَاطَر وَالْمَعْمَل", "الْأَثَر النَّقْدِي، وَالْمُخَاطَر وَعَدَم الْيَقِين، وَمُحَاكَاة اِسْتِرَاتِيجِيَّة عَلَى مَقَاسَك");
  await go("/financial", 2000);
  await say("لُوحِة الْأَثَر الْمَالِي: جِسْر الْقِيمَة مِن النَّقْد الْإِضَافِي، لِلْعُمُولَات وَالْخُصُومَات وَتَكْلِفِة التَّنْفِيذ، لِخَسَايِر الْعَلَاقَات، لِحَدّ صَافِي الْمَنْفَعَة النَّقْدِيَّة.");
  await scroll(620, 1500);
  await say("وَمَسَارَات الرَّصِيد النَّقْدِي وَالتَّكْلِفَة الشَّهْرِيَّة وَالتَّدَفُّق النَّقْدِي، كُلَّهَا بِنِطَاقَات عَدَم يَقِين، مِش رَقَم وَاحِد يِضَلِّلَك.");
  await go("/risk", 2000);
  await say("مُسْتَكْشِف الْمُخَاطَر: اِحْتِمَال تَحْقِيق كُلّ قَيْد، وَمَصْفُوفِة الِاحْتِمَال وَالْأَثَر، وَسِجِلّ الْمُخَاطَر، وَمِنْهَا خَطَر تَسْرِيب بَيَانَات الْعُمَلَاء عَن طَرِيق طَرَف تَالِت.");
  await scroll(700, 1500);
  await say("وَمُخَطَّط الْإِعْصَار بِيِقُولَك أَنْهِي اِفْتِرَاض بِيْحَرَّك النَّتِيجَة أَكْتَر، زَيّ مُعَدَّل اِسْتِرْدَاد شِرْكِة التَّحْصِيل وَعُمُولِتْهَا.");
  await go("/lab", 1600);
  await say("فِي مَعْمَل الْمُحَاكَاة بِتِبْنِي اِسْتِرَاتِيجِيِّتَك بِإِيدَك: نِسْبِة الْمُتَأَخِّرَات اللِّي تِرُوح لِشِرْكِة التَّحْصِيل، وَالتَّحْصِيل الرَّقْمِي، وَخَصْم السَّدَاد الْمُبَكِّر، وَنَقْل مُوَظَّفِين لِلتَّحْصِيل.");
  await click(page.getByTestId("lab-run"), 2600);
  await say("وَعَلَى طُول بِتَاخُد نَفْس الْمُخْرَجَات: نِسْبِة الزِّيَادَة، وَصَافِي الْمَنْفَعَة، وَالشَّكَاوَى، وَاحْتِمَال تَحْقِيق الْهَدَف، وَالْحَسَاسِيَّة، وَتَوْزِيع النَّتَايِج.");
  await scroll(0, 900);

  // 9. Approvals
  await chapter("الْحَوْكَمَة وَالِاعْتِمَاد الْبَشَرِي", "سِيَاسَات بِتِتْنَفِّذ بَرَّه النَّمَاذِج، وَفَصْل لِلْمَهَامّ، وَمُوَافْقَة بَشَرِيَّة قَبْل أَيّ تَنْفِيذ");
  await go("/approvals", 1800);
  await say("مَفِيش اِسْتِرَاتِيجِيَّة بِتِمْشِي مِن غِير مُوَافْقَة بَشَرِيَّة مِن الْأَدْوَار اللِّي السِّيَاسَات بِتْحَدِّدْهَا. وَالْمَنَصَّة نَفْسَهَا مَبْتِنَفِّذْش أَيّ حَاجَة لِوَحْدَهَا.");
  await click(page.getByTestId("pick-A"), 1400);
  await say("لَوْ اِخْتَرْنَا أَلِف: مَرْفُوض بِسِيَاسِة التَّحْصِيل الْعَادِل، لِأَنّ التَّوَاصُل الْمُكَثَّف وَالتَّصْعِيد الْقَانُونِي الْمُبَكِّر مَمْنُوعِين. وَمَفِيش وَكِيل يِقْدَر يِتْخَطَّى السِّيَاسَة دِي.");
  await click(page.getByTestId("pick-B"), 1400);
  await say("بِيه مَسْمُوح، بَسّ مُحْتَاج مُوَافْقِة الْمَالِي وَالرَّئِيس التَّنْفِيذِي وَالْقَانُونِي، لِأَنّ تَسْلِيم الدِّيُون لِشِرْكِة تَحْصِيل مَعْنَاه مُشَارْكِة بَيَانَات الْعُمَلَاء.");
  await click(page.getByTestId("ack"), 600);
  await say("وَعَشَان الْبَيَانَات فِيهَا تَنْبِيه جَوْدَة، السِّيَاسَة بِتِطْلُب إِقْرَار صَرِيح قَبْل التَّقْدِيم.");
  await click(page.getByTestId("submit-approval"), 1600);
  await scrollToEl(page.getByTestId("approval-card").first(), 160);
  await say("الطَّلَب اِتْقَدِّم وَمُسْتَنِّي الْمُوَافْقَات، وَكُلّ خُطْوَة مِتْسَجِّلَة فِي سِجِلّ التَّدْقِيق.");
  await cap("هَنُدْخُل دِلْوَقْتِي بِحِسَاب الْمُدِير الْمَالِي عَشَان يِوَافِق.");
  await logout();
  await login("cfo@futuremirror.demo");
  await go("/approvals", 1600);
  await scrollToEl(page.getByTestId("approve-btn").first(), 260);
  await click(page.getByTestId("approve-btn").first(), 1800);
  await say("الْمُدِير الْمَالِي وَافِق، وَعَلَامِة دُورُه بَقِت خَضْرَا. وَاللِّي قَدِّم الطَّلَب مَيِقْدَرْش يِوَافِق عَلِيه.");

  // 10. Outcomes
  await chapter("الْفِعْلِي قُصَاد الْمُتَوَقَّع", "حَلْقِة التَّغْذِيَة الرَّاجْعَة مِن الْوَاقِع: دِقِّة التَّوَقُّعَات وَأَسْبَاب الِانْحِرَاف");
  await go("/outcomes", 1800);
  await say("بَعْد التَّنْفِيذ بِنْقَارِن اللِّي حَصَل فِعْلًا بِاللِّي الْمُحَاكَاة تَوَقَّعِتُه. لِلْعَرْض بِنْوَلِّد قِيَم فِعْلِيَّة اِفْتِرَاضِيَّة وَعَلِيهَا عَلَامَة وَاضْحَة.");
  await click(page.getByTestId("demo-actuals"), 2600);
  await say("الرَّسْمَة فِيهَا الْخَطّ الْمُتَوَقَّع وَنِطَاقُه وَالْقِيَم الْفِعْلِيَّة، وَالْمُؤَشِّرَات بِتْقِيس التَّغْطِيَة وَمُتَوَسِّط الْخَطَأ وَالِانْحِيَاز.");
  await scroll(620, 1500);
  await say("وَقِسْم لِيه التَّوَقُّع اِخْتَلَف بِيِشْرَح الِانْحِرَافَات. وَتِقْدَر تِقْتِرِح إِعَادِة مُعَايْرِة النَّمُوذَج، بَسّ مَبْتِتْطَبَّقْش إِلَّا بَعْد مُوَافْقِة مُدِير الْمَنَصَّة بِمُبَرِّر مَكْتُوب.");
  await scroll(0, 900);

  // 11. History & reports
  await chapter("السِّجِلّ وَالتَّقَارِير", "كُلّ تَشْغِيل مُمْكِن تِتَابْعُه وَتِعِيدُه، وَتَقَارِير تَنْفِيذِيَّة بِالْعَرَبِي وَالْإِنْجِلِيزِي");
  await go("/history", 1800);
  await say("سِجِلّ الْقَرَارَات بِيِحْفَظ كُلّ تَشْغِيل بِحَالْتُه وَوَقْتُه، وَكُلّ مُحَاكَاة مَحْفُوظَة بِبِذْرِتْهَا وَبَصْمِتْهَا، فَتِقْدَر تِعِيد أَيّ نَتِيجَة فِي أَيّ وَقْت.");
  await go("/court", 3500);
  await point(page.getByRole("button", { name: /تقرير PDF/ }).first(), 600);
  await say("وَمِن شَرِيط الْقَرَار تِطَلَّع تَقْرِير تَنْفِيذِي PDF أَوْ مَلَفّ Excel بِلُغِة الْوَاجْهَة، فِيه الْمُتَحَصَّلَات، وَالْعُمُولَات، وَفَتْرِة التَّحْصِيل، وَفَقْد كِبَار الْعُمَلَاء.");

  // 12. Data connections (admin)
  await chapter("مَصَادِر بَيَانَات الشِّرْكَة", "مُوَصِّلَات لِلْقِرَايَة بَسّ: Odoo وَ Dynamics 365 وَ SAP وَ REST وَقَوَاعِد بَيَانَات SQL");
  await logout();
  await login("admin@futuremirror.demo");
  await go("/data", 1800);
  await say("شَاشِة مَصَادِر الْبَيَانَات فِيهَا مُوَصِّلَات Odoo وَ Dynamics 365 وَ SAP وَ REST وَ SQL، وَاسْتِيرَاد Excel. كُلَّهَا لِلْقِرَايَة بَسّ.");
  await click(page.getByTestId("conn-configure-sql"), 1400);
  await scrollToEl(page.getByTestId("conn-settings-sql"), 90);
  await say("كُلّ مُوَصِّل لِيه نَمُوذَج إِعْدَادَات، وَكِلْمِة السِّرّ عُمْرَهَا مَا بِتِتْكِتِب هِنَا، بِتِتْحِفِظ عَلَى السِّيرْفَر.");
  await click(page.getByTestId("conn-configure-sql"), 800);
  await scroll(await page.evaluate(() => document.body.scrollHeight), 1800);
  await scroll(0, 900);

  // 13. Automation
  await chapter("مَرْكَز الْأَتْمَتَة", "سَبَع مَسَارَات n8n جَاهْزَة، بِتَشْغِيل تَجْرِيبِي آمِن، وَالتَّنْفِيذ اللِّي لِيه أَثَر مَمْنُوع بِالسِّيَاسَات");
  await go("/automation", 1800);
  await say("مَسَارَات الْأَتْمَتَة مُتَكَامْلَة مَعَ n8n: إِعَادِة التَّحْلِيل، وَمُزَامْنِة الـ ERP، وَتَوْجِيه الِاعْتِمَادَات، وَمُرَاقْبِة الْمُؤَشِّرَات.");
  await scroll(600, 1400);
  await say("التَّشْغِيل التَّجْرِيبِي بِيِوَرِّيك اللِّي هَيِتْبِعِت بِالظَّبْط مِن غِير مَا يِغَيَّر حَاجَة، وَكُلّ تَشْغِيل مِتْسَجِّل بِمِفْتَاح يِمْنَع التَّكْرَار.");
  await scroll(0, 900);

  // 14. Governance
  await chapter("حَوْكَمِة الذَّكَاء الِاصْطِنَاعِي", "سِتَّاشَر سِيَاسَة، وَمِنْهُم حِمَايِة بَيَانَات الْعُمَلَاء وَالتَّحْصِيل الْعَادِل، وَوُكَلَاء مِن غِير صَلَاحِيِّة تَنْفِيذ");
  await go("/governance", 1800);
  await say("سِتَّاشَر سِيَاسَة بِتَأْثِيرَاتْهَا: رَفْض، أَوْ اِشْتِرَاط مُوَافْقَة، أَوْ اِشْتِرَاط إِقْرَار. السِّيَاسَات الْمَقْفُولَة مَحَدِّش يِقْدَر يِعَطَّلْهَا.");
  await point(page.getByTestId("policy-GOV-015"), 600);
  await say("سِيَاسَتِين جُدَاد لِلتَّحْصِيل: مُشَارْكِة بَيَانَات الْعُمَلَاء مَعَ طَرَف تَالِت مُحْتَاجَة اِتِّفَاقِيِّة حِمَايِة بَيَانَات وَمُوَافْقِة الْقَانُونِيَّة، حَسَب قَانُون حِمَايِة الْبَيَانَات الشَّخْصِيَّة.");
  await point(page.getByTestId("policy-GOV-016"), 600);
  await say("وَالتَّحْصِيل الْعَادِل: مَمْنُوع الضَّغْط وَالتَّهْدِيد وَالتَّصْعِيد الْقَانُونِي الْمُبَكِّر، وَأَيّ قَضِيَّة بِتِتْقَرَّر حَالَة بِحَالَة.");
  const ev = page.getByTestId("evaluate");
  await scrollToEl(ev, 300);
  await click(ev, 1500);
  await say("وَبِيئِة اِخْتِبَار السِّيَاسَات بِتْقَيِّم أَيّ إِجْرَاء مُقْتَرَح عَلَى السِّيَاسَات الْحَيَّة فِي نَفْس اللَّحْظَة، وَمَفِيش وَلَا وَكِيل عَنْدُه صَلَاحِيِّة تَنْفِيذ.");
  await scroll(0, 900);

  // 15. Admin
  await chapter("الْإِدَارَة وَالْأَمَان", "الْإِيقَاف الطَّارِئ، وَالْمُسْتَخْدِمِين وَالْأَدْوَار، وَسِجِلّ تَدْقِيق مَحَدِّش يِقْدَر يِلْعَب فِيه");
  await go("/admin", 1800);
  await say("شَاشِة الْإِدَارَة: إِعْدَادَات الْمَنَصَّة، وَالْمُسْتَخْدِمِين، وَالتَّمَن أَدْوَار بِصَلَاحِيَّاتْهُم، وَتَفْعِيل الْحِسَابَات أَوْ إِيقَافْهَا.");
  const stopOn = page.getByRole("button", { name: /تفعيل الإيقاف الطارئ/ });
  await click(stopOn, 1600);
  await say("الْإِيقَاف الطَّارِئ بِيِلْغِي كُلّ التَّحْلِيلَات الشَّغَّالَة وَيِمْنَع الْجِدِيدَة فَوْرًا، وَتِظْهَر عَلَامَة حَمْرَا لِلْكُلّ. هَنِلْغِيه دِلْوَقْتِي.");
  await click(page.getByRole("button", { name: /إلغاء الإيقاف الطارئ/ }), 1400);
  await scroll(800, 1500);
  await say("وَسِجِلّ التَّدْقِيق مَرْبُوط بِسِلْسِلِة تَجْزِئَة، فَأَيّ تَعْدِيل فِي أَيّ سِجِلّ قَدِيم بِيِنْكِشِف عَلَى طُول.");
  await scroll(0, 900);

  // 16. Bilingual + themes
  await chapter("لُغْتِين وَمَظْهَرِين", "عَرَبِي وَإِنْجِلِيزِي، وَمَظْهَر غَامِق وَفَاتِح");
  await go("/", 1400);
  await cap("بِضَغْطَة وَاحْدَة الْمَنَصَّة كُلَّهَا تِبْقَى إِنْجِلِيزِي، بِمَا فِيهَا نَتَايِج الْوُكَلَاء وَالتَّقَارِير وَالرُّسُومَات.");
  await click(page.getByTestId("lang-toggle"), 2800);
  await click(page.getByTestId("lang-toggle"), 1800);
  await cap("وَفِيه مَظْهَر فَاتِح لِلْعُرُوض وَالطِّبَاعَة.");
  await click(page.getByTestId("theme-toggle"), 3200);
  await click(page.getByTestId("theme-toggle"), 1600);
  await say("الْمَنَصَّة بِتِشْتَغَل عَلَى جِهَازَك أَوْ عَلَى سِيرْفَرَاتْكُم بِـ Docker، وَمَعَاهَا مَلَفَّات جَاهْزَة لِلتَّشْغِيل وَالنُّسْخَة الِاحْتِيَاطِيَّة وَالتَّحْدِيث.");

  // Outro
  closeCap();
  await page.evaluate(() => { window.__fm?.hide(); window.__fm?.chap("", 1); });
  chapters.push({ t: now(), title: "الْخَاتْمَة" });
  await page.evaluate(() => window.__fm?.card("مِرْآةُ الْمُسْتَقْبَل", "جَرَّب بُكْرَه قَبْل مَا تُقَرَّرُه",
    "وُكَلَاء مُتَخَصِّصِين • مُحَاكَاة كَمِّيَّة • مَحْكَمِة وُكَلَاء • آلِة زَمَن • حَوْكَمَة وَاعْتِمَاد بَشَرِي • عَرَبِي وَإِنْجِلِيزِي"));
  open = { start: now(), text: "مِرْآةُ الْمُسْتَقْبَل. جَرَّب بُكْرَه قَبْل مَا تُقَرَّرُه." };
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
  fs.writeFileSync(path.join(OUT, "chapters-eg.txt"), chapters.map((c) => `${mmss(c.t)} ${c.title}`).join("\n") + "\n", "utf8");
  console.log(`duration ${mmss(total)} · captions ${srt.length} · frames ${written} · page errors ${errors.length}`);
  if (errors.length) console.log(errors.slice(0, 5).join("\n"));
}
