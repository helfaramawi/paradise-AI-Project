// Records the Arabic product demo video of Future Mirror AI from the REAL running app.
//
//   BASE_URL=http://localhost:5173 OUT_DIR=../docs/video node e2e/video/record-demo-ar.mjs
//
// Frames come from Chrome's screencast (crisp JPEG), are re-timed to a constant 25 fps and
// piped into ffmpeg (H.264 MP4). On-screen Arabic captions, chapter cards and a visible cursor
// are injected into the page, so Arabic shaping and RTL are rendered by the browser itself.
// Writes: future-mirror-demo-ar.mp4, .srt (narration, for voice-over), chapters.txt.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL || "http://localhost:5173";
const OUT = path.resolve(process.env.OUT_DIR || "../docs/video");
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
  #fm-cap .t{font-size:25px;line-height:1.65;font-weight:500}
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
  path.join(OUT, "future-mirror-demo-ar.mp4")], { stdio: ["pipe", "inherit", "inherit"] });
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
const readMs = (t) => Math.max(4200, 1400 + t.split(/\s+/).length * 430);
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
  await page.evaluate(([n, ti, su, total]) => window.__fm?.card(`الفصل ${n.toLocaleString("ar-EG")} من ${total.toLocaleString("ar-EG")}`, ti, su),
    [chapNo, title, sub, TOTAL_CH]);
  open = { start: now(), text: `${title} — ${sub}` };
  await sleep(3800);
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
try {
  // Intro
  await go("/login", 600);
  await page.evaluate(() => window.__fm?.card("عرض توضيحي للمنتج", "مرآة المستقبل", "منصة ذكاء القرار المؤسسي: وكلاء ذكاء اصطناعي، ومحاكاة كمية للمستقبلات البديلة، وحوكمة قابلة للتنفيذ قبل أي قرار"));
  chapters.push({ t: 0, title: "المقدمة" });
  open = { start: now(), text: "مرآة المستقبل — منصة ذكاء القرار المؤسسي" };
  await sleep(6500);
  closeCap();
  await page.evaluate(() => window.__fm?.uncard());
  await sleep(900);

  // 1. Sign-in
  await chapter("تسجيل الدخول والواجهة", "حسابات تجريبية لكل دور، وواجهة عربية كاملة من اليمين إلى اليسار");
  await say("نبدأ بشاشة الدخول. المنصة ثنائية اللغة بالكامل، وهنا نعرضها باللغة العربية مع اتجاه من اليمين إلى اليسار.");
  await say("لكل دور في المؤسسة حساب تجريبي: الرئيس التنفيذي، والمدير المالي، ومدير العمليات، والمستشار القانوني، ومدير الموارد البشرية، والمحلل، ومدير المنصة.");
  await cap("ندخل الآن بحساب محلل القرارات الذي يُعدّ الحالات ويطلقها للتحليل.");
  await login("analyst@futuremirror.demo");
  await point(page.getByTestId("platform-chips"), 300);
  await say("في الشريط العلوي ثلاث شارات صادقة: البيانات افتراضية، والوكلاء قائمون على القواعد دون نموذج لغوي، والإجراءات الخارجية معطّلة. لا شيء مخفي عن المستخدم.");

  // 2. Command center
  await chapter("مركز القيادة التنفيذية", "مؤشرات الشركة وآخر ملف قرار في نظرة واحدة");
  await go("/");
  await say("مركز القيادة هو الصفحة الرئيسية: تكلفة التشغيل، والإيرادات، وعدد الموظفين، ونسبة الاستغلال، وتأخر المشروعات، ورضا العملاء.");
  await scroll(380);
  await say("وهنا آخر ملف قرار: توصية الهيئة، وبطاقة لكل مستقبل بديل مع وفوراته وحالته في الحوكمة واحتمال تحقيق الهدف.");
  await scroll(0, 900);

  // 3. Intake
  await chapter("إنشاء قرار جديد", "معالج من أربع خطوات يحوّل السؤال الاستراتيجي إلى حالة منظمة");
  await go("/decisions/new");
  await cap("نكتب السؤال الاستراتيجي بالعربية أو الإنجليزية. سنستخدم سيناريو العرض التوضيحي.");
  await click(page.getByTestId("use-demo"), 900);
  await point(page.getByTestId("question-input"), 300);
  await say("السؤال: كيف نخفض تكاليف التشغيل بنسبة عشرين في المئة خلال اثني عشر شهراً دون تسريح موظفين ودون الإضرار بتسليم المشروعات؟");
  await cap("تفسّر المنصة السؤال وتستخرج النسبة المستهدفة والمدة وقاعدة التكلفة والقيود.");
  await click(page.getByTestId("parse-btn"), 1400);
  await say("لاحظ أنها التقطت قيد «لا تسريح للموظفين» تلقائياً. المستخدم يراجع التفسير ويؤكده قبل أي تحليل.");
  await click(page.getByTestId("next-2"), 1200);
  await say("في الخطوة الثالثة نضبط الضوابط التنفيذية: الهدف، ومدة التنفيذ، وميزانية الأتمتة، والتأخير المقبول، وحد الاستغلال، والحد الأدنى لرضا العملاء، ودرجة تحمل المخاطر.");
  await scroll(500, 1200);
  await sleep(1500);
  await scroll(0, 900);
  await click(page.getByTestId("next-3"), 1200);
  await say("وأخيراً نختار إصدار البيانات. شارة الجودة تنبهنا إلى عدم اتساق في هامش الربح ضمن بيانات العرض، وهو تنبيه حقيقي محسوب.");
  await cap("نطلق التحليل ونوقظ الوكلاء.");
  await click(page.getByTestId("launch-btn"), 600);

  // 4. Execution room
  await page.waitForURL(/\/execution\//);
  await chapter("غرفة التنفيذ المباشر", "عشر مراحل وسبعة وكلاء متخصصين يعملون بالتوازي — أحداث حقيقية تُبث من الخادم");
  await say("هذه غرفة التنفيذ المباشر. كل حدث هنا يُبث فعلياً من الخادم أثناء التشغيل، وليس عرضاً مسجلاً.");
  await point(page.getByTestId("flow-graph"), 300);
  await say("المخطط يعرض المراحل العشر: من استلام القرار، إلى التحقق من البيانات، ثم سبعة وكلاء يعملون بالتوازي: الاستراتيجية والمالية والعمليات والموارد البشرية والتسليم والقانونية والمخاطر.");
  await point(page.getByTestId("event-feed"), 300);
  await say("سجل التنفيذ يعرض كل نتيجة لحظة صدورها: نتائج الوكلاء، وتحذيرات البيانات، واعتراضات الفريق الأحمر، والتصادمات، وقرارات السياسات.");
  await page.getByTestId("to-court").waitFor({ timeout: 120_000 });
  await say("اكتمل ملف القرار. نتوقف قصيراً بين المراحل لتسهيل المتابعة، ويُعرض وقت الحوسبة الفعلي منفصلاً بكل شفافية.");
  await cap("ندخل محكمة الوكلاء.");
  await click(page.getByTestId("to-court"), 600);

  // 5. Agent court
  await page.getByTestId("verdict-headline").waitFor();
  await chapter("محكمة الوكلاء", "مواقف وأدلة واعتراضات وردود، وحكم مرجّح بجودة الأدلة لا بالتصويت");
  await point(page.getByTestId("court-mode"), 300);
  await say("شريط الوضع يوضح أن الاستدلال قائم على القواعد: كل عبارة محسوبة من بيانات هذا التشغيل ومحاكاته، وليست نصاً معداً مسبقاً.");
  await point(page.getByTestId("verdict-headline"), 300);
  await say("حكم الهيئة: بطاقة لكل مستقبل مع حالته، ودعم مرجّح بالأدلة، ونتيجة الحوكمة، والقيود الصارمة غير المستوفاة، والأدوار التي يجب أن تعتمد.");
  await say("المنهجية واضحة: الحكم يزن جودة الأدلة والسياسات وعدم اليقين، ولا يعتمد على تصويت الأغلبية.");
  await scrollToEl(page.getByTestId("debate"), 220);
  await say("تبويب المناظرة يعرض النقاش على أربع جولات: المواقف، ثم اعتراضات الفريق الأحمر والردود عليها، ثم التصادمات، ثم الحوكمة.", 1500);
  await click(page.getByRole("tab", { name: /مواقف الوكلاء/ }), 1200);
  await say("في مواقف الوكلاء، كل نتيجة مصنفة: حقيقة أو تقدير أو افتراض أو فرضية أو توصية، مع درجة الثقة ورابط للدليل الرقمي الذي تستند إليه.");
  await scroll(await page.evaluate(() => window.scrollY + 420), 1300);
  await click(page.getByRole("tab", { name: /كاشف تصادم المستقبل/ }), 1200);
  await scrollToEl(page.getByTestId("collision-card").first(), 160);
  await say("كاشف تصادم المستقبل يرصد التعارض بين توصيات الوكلاء بقواعد منظمة: مثلاً تقليص المتعاقدين يوفر المال لكنه يرفع خطر تأخير المشروعات.");
  await say("كل بطاقة تعرض شدة التصادم، والأهداف المتأثرة، والعواقب المحتملة، والحلول البديلة، وما إذا كان يتطلب تدخلاً بشرياً.");
  await scroll(0, 900);

  // 6. Three futures
  await chapter("المستقبلات الثلاثة", "محاكاة مونت كارلو لألفي سيناريو لكل استراتيجية، وإعادة حساب فورية");
  await go("/futures", 2200);
  await say("هنا نقارن ثلاث استراتيجيات جنباً إلى جنب. الأرقام تأتي من محرك محاكاة كمي منفصل عن أي نموذج لغوي، بألفي سحب عشوائي وبذرة قابلة لإعادة الإنتاج.");
  await scrollToEl(page.getByTestId("future-A"), 110);
  await say("كل بطاقة تعرض الوفورات عند الموعد، واحتمال تحقيق الهدف، وصافي المنفعة، والنقد، وتأخر التسليم، والاستغلال، ورضا العملاء، مع نطاق من العُشير الأول إلى التاسع.");
  await point(page.getByTestId("future-A"), 300);
  await say("المستقبل «أ» الأكثر جرأة يحقق وفورات أعلى، لكنه يصطدم بقيود صارمة وتمنعه الحوكمة. المستقبل «ب» متوازن ويتطلب اعتمادات بشرية.");
  await say("ملاحظة مهمة كشفتها المحاكاة: لا يصل أي مستقبل إلى عشرين في المئة دون تسريح؛ الحد الأقصى الواقعي نحو أربعة عشر ونصف في المئة. المنصة تقول الحقيقة ولا تجمّلها.");
  await scroll(0, 900);
  await cap("وضع «ماذا لو»: نحرّك أي شريط في الضوابط فتُعاد المحاكاة خلال جزء من الثانية.");
  const slider = page.locator('input[type="range"]').first();
  await point(slider, 400);
  await slider.fill("12");
  await sleep(2600);
  await say("تظهر شارة «وضع ماذا لو» وبصمة مدخلات جديدة. نتائج ماذا لو لا تُحفظ إلا إذا اخترنا ذلك، وتذكّرنا المنصة بإعادة التحليل لتقييم الوكلاء والحوكمة من جديد.");
  await scroll(1500, 1800);
  await say("وفي الأسفل مخطط مسار الوفورات وجدول المقارنة الكامل، ويمكن تحويل أي مخطط إلى جدول بضغطة واحدة.");
  await scroll(0, 900);

  // 7. Time machine
  await chapter("آلة زمن القرار", "حالة الشركة المتوقعة اليوم وبعد شهر وثلاثة وستة واثني عشر شهراً");
  await go("/time-machine");
  await say("آلة الزمن تعرض حالة الشركة المتوقعة في أي شهر: التكلفة الشهرية، والإيرادات، والتدفق النقدي، والرصيد، والوفورات، والتأخير، والاستغلال، والمخاطر.");
  await click(page.getByTestId("tm-stops").locator("button").nth(3), 1200);
  await say("انتقلنا إلى الشهر السادس. كل مؤشر يعرض التغير منذ اليوم، ويمكن مقارنة المستقبلات الثلاثة في الشهر نفسه.");
  await click(page.getByTestId("tm-stops").locator("button").nth(4), 1400);
  await scroll(520, 1300);
  await say("والمخطط على الجانب يتتبع أي مؤشر على اثني عشر شهراً مع علامة الشهر المختار.");
  await scroll(0, 900);

  // 8. Financial, risk, lab
  await chapter("التحليل المالي والمخاطر والمختبر", "الأثر المالي، والمخاطر وعدم اليقين، ومحاكاة استراتيجية مخصصة");
  await go("/financial", 2000);
  await say("لوحة الأثر المالي: الربح التشغيلي المتوقع لاثني عشر شهراً لكل مستقبل، وجسر القيمة من الوفورات إلى تكلفة التنفيذ وخسائر التسليم وصافي المنفعة.");
  await scroll(620, 1500);
  await say("ومسارات النقد والتكلفة الشهرية والتدفق النقدي، كلها بنطاقات عدم يقين وليست رقماً واحداً مضللاً.");
  await go("/risk", 2000);
  await say("مستكشف المخاطر: احتمال استيفاء كل قيد مقارنة بدرجة تحمل المخاطر، ومصفوفة الاحتمال والأثر، وسجل المخاطر مع خطط المعالجة.");
  await scroll(700, 1500);
  await say("ومخطط الإعصار يبيّن أي الافتراضات تحرّك النتيجة أكثر، مع توزيع النتائج وأسوأ وأفضل الحالات.");
  await go("/lab", 1600);
  await say("في مختبر المحاكاة نبني استراتيجيتنا الخاصة: دمج التراخيص، والبنية التحتية، والموردين، والمرافق، وتجميد المصروفات، وتقليص المتعاقدين، والأتمتة.");
  await click(page.getByTestId("lab-run"), 2600);
  await say("حصلنا فوراً على نفس المخرجات: الوفورات، وصافي المنفعة، والتأخير، واحتمال الهدف، ومخطط الحساسية، وتوزيع النتائج.");
  await scroll(900, 1600);
  await say("وهذه محاكاة الأحداث المنفصلة لمحفظة المشروعات: أثر كل استراتيجية على كل مشروع على حدة، مع إبراز المشروعات المعرضة للخطر.");
  await scroll(0, 900);

  // 9. Approvals
  await chapter("الحوكمة والاعتماد البشري", "سياسات تُنفَّذ خارج النماذج، وفصل للمهام، وموافقة بشرية قبل أي تنفيذ");
  await go("/approvals", 1800);
  await say("لا تمضي أي استراتيجية دون اعتماد بشري ممن تحددهم السياسات. والمنصة نفسها لا تنفذ أي شيء تلقائياً.");
  await click(page.getByTestId("pick-A"), 1400);
  await say("نختار المستقبل «أ»: الحوكمة تمنعه بالسياسة GOV-009 بسبب تصادم حرج غير محلول. السياسات تُطبَّق في محرك مستقل، ولا يمكن لأي وكيل تجاوزها.");
  await click(page.getByTestId("pick-B"), 1400);
  await say("المستقبل «ب» مسموح بشرط اعتماد المدير المالي والرئيس التنفيذي والمستشار القانوني.");
  await click(page.getByTestId("ack"), 600);
  await say("بما أن البيانات بها تنبيه جودة، تفرض السياسة GOV-011 إقراراً صريحاً قبل التقديم.");
  await click(page.getByTestId("submit-approval"), 1600);
  await scrollToEl(page.getByTestId("approval-card").first(), 160);
  await say("تم تقديم الطلب وهو الآن قيد الانتظار، وكل خطوة مسجلة في سجل التدقيق.");
  await cap("نسجّل الدخول الآن بحساب المدير المالي ليعتمد الطلب.");
  await logout();
  await login("cfo@futuremirror.demo");
  await go("/approvals", 1600);
  await scrollToEl(page.getByTestId("approve-btn").first(), 260);
  await click(page.getByTestId("approve-btn").first(), 1800);
  await say("اعتمد المدير المالي، وتحولت شارة دوره إلى اللون الأخضر. قواعد فصل المهام مفروضة: مقدّم الطلب لا يعتمد طلبه، ولا يعتمد الشخص الواحد إلا عن دور واحد.");

  // 10. Outcomes
  await chapter("الفعلي مقابل المتوقع", "حلقة التغذية الراجعة من الواقع: دقة التوقعات وأسباب الانحراف");
  await go("/outcomes", 1800);
  await say("بعد التنفيذ نقارن ما حدث فعلاً بما توقعته المحاكاة. للعرض نولّد قيماً فعلية افتراضية موسومة بوضوح.");
  await click(page.getByTestId("demo-actuals"), 2600);
  await say("المخطط يعرض الخط المتوقع ونطاقه والقيم الفعلية. والمؤشرات تقيس التغطية ومتوسط الخطأ والانحياز.");
  await scroll(620, 1500);
  await say("وقسم «لماذا اختلف التوقع» يشرح الانحرافات، ويمكن اقتراح إعادة معايرة النموذج، لكنها لا تُطبّق إلا بعد اعتماد مدير المنصة بمبرر مكتوب.");
  await scroll(0, 900);

  // 11. History & reports
  await chapter("السجل والتقارير", "كل تشغيل قابل للتتبع وإعادة الإنتاج، وتقارير تنفيذية بالعربية والإنجليزية");
  await go("/history", 1800);
  await say("سجل القرارات يحفظ كل تشغيل بحالته ووضعه ووقت حوسبته، وكل محاكاة محفوظة ببذرتها وبصمتها، فيمكن تتبع أي نتيجة وإعادة إنتاجها.");
  await go("/court", 3500);
  await point(page.getByRole("button", { name: /تقرير PDF/ }).first(), 600);
  await say("ومن شريط القرار نصدّر تقريراً تنفيذياً بصيغة PDF أو مصنف Excel، بلغة الواجهة، مع تمييز الحقائق والتقديرات والافتراضات والتوصيات.");

  // 12. Data connections (admin)
  await chapter("مصادر بيانات المؤسسة", "موصلات للقراءة فقط: Odoo وDynamics 365 وSAP وواجهات REST وقواعد بيانات SQL");
  await logout();
  await login("admin@futuremirror.demo");
  await go("/data", 1800);
  await say("شاشة مصادر البيانات تعرض الموصلات: ERP افتراضي يعمل، واستيراد CSV وExcel، ومحولات Odoo وDynamics 365 وSAP وواجهات REST وقواعد بيانات SQL. كلها للقراءة فقط.");
  await click(page.getByTestId("conn-configure-sql"), 1400);
  await scrollToEl(page.getByTestId("conn-settings-sql"), 90);
  await say("لكل موصل نموذج إعدادات. مثلاً قاعدة بيانات SQL تدعم PostgreSQL وSQL Server وMySQL. كلمة المرور لا تُكتب هنا أبداً؛ تُحفظ على الخادم، والنموذج يبيّن فقط هل هي مضبوطة.");
  await scroll(await page.evaluate(() => window.scrollY + 520), 1400);
  await say("ربط الحسابات يحوّل بادئات أرقام الحسابات إلى فئات التكلفة. ثم نضغط «اختبار» للتحقق من الاتصال و«مزامنة» لجلب الأرقام كإصدار جديد من البيانات.");
  await click(page.getByTestId("conn-configure-sql"), 800);
  await scroll(await page.evaluate(() => document.body.scrollHeight), 1800);
  await say("وفي الأسفل إصدارات البيانات، ومصدر كل قيمة، وفحوص الجودة، ودفتر أستاذ مولّد للعرض يطابق الأرقام تماماً.");
  await scroll(0, 900);

  // 13. Automation
  await chapter("مركز الأتمتة", "مسارات n8n بتشغيل تجريبي آمن، ومنع التنفيذ ذي الأثر بالسياسات");
  await go("/automation", 1800);
  await say("مسارات الأتمتة تتكامل مع n8n. التشغيل التجريبي يعرض ما سيُرسل بالضبط دون تغيير أي شيء، والمسارات ذات الأثر ممنوعة دائماً من التشغيل الفعلي بالسياسات.");
  await scroll(600, 1400);
  await say("وكل تشغيل مسجل بمفتاح منع التكرار في سجل التنفيذ.");
  await scroll(0, 900);

  // 14. Governance
  await chapter("مركز حوكمة الذكاء الاصطناعي", "أربع عشرة سياسة تصريحية، وبيئة اختبار، ووكلاء بلا صلاحية تنفيذ");
  await go("/governance", 1800);
  await say("أربع عشرة سياسة بتأثيراتها: منع، أو اشتراط اعتماد، أو اشتراط إقرار. السياسات المقفلة لا يمكن تعطيلها، ويمكن للمدير تبديل الباقي.");
  await point(page.getByTestId("policy-GOV-001"), 600);
  await say("مثلاً السياسة GOV-001 تمنع أي استراتيجية تتضمن تسريح موظفين، حتى لو أوصى بها كل الوكلاء.");
  const ev = page.getByTestId("evaluate");
  await scrollToEl(ev, 300);
  await click(ev, 1500);
  await say("بيئة اختبار السياسات تقيّم أي إجراء مقترح مقابل السياسات الحية فوراً، وقائمة الوكلاء تؤكد أن أياً منهم لا يملك صلاحية تنفيذ.");
  await scroll(0, 900);

  // 15. Admin
  await chapter("الإدارة والأمان", "الإيقاف الطارئ، والمستخدمون والأدوار، وسجل تدقيق مقاوم للتلاعب");
  await go("/admin", 1800);
  await say("شاشة الإدارة: إعدادات المنصة، والمستخدمون والأدوار الثمانية بصلاحياتها، وتفعيل الحسابات أو تعطيلها.");
  const stopOn = page.getByRole("button", { name: /تفعيل الإيقاف الطارئ/ });
  await click(stopOn, 1600);
  await say("الإيقاف الطارئ يلغي كل التحليلات الجارية ويمنع الجديدة فوراً، وتظهر شارة حمراء للجميع. سنلغيه الآن.");
  await click(page.getByRole("button", { name: /إلغاء الإيقاف الطارئ/ }), 1400);
  await scroll(800, 1500);
  await say("وسجل التدقيق مرتبط بسلسلة تجزئة، فأي تعديل على أي سجل سابق يُكتشف فوراً.");
  await scroll(0, 900);

  // 16. Bilingual + themes
  await chapter("ثنائية اللغة والمظهر", "العربية والإنجليزية، والمظهر الداكن والفاتح");
  await go("/", 1400);
  await cap("بضغطة واحدة تتحول المنصة بالكامل إلى الإنجليزية، بما في ذلك نتائج الوكلاء والتقارير والمخططات.");
  await click(page.getByTestId("lang-toggle"), 2800);
  await click(page.getByTestId("lang-toggle"), 1800);
  await cap("ويتوفر مظهر فاتح للعروض والطباعة.");
  await click(page.getByTestId("theme-toggle"), 3200);
  await click(page.getByTestId("theme-toggle"), 1600);
  await say("المنصة تعمل محلياً أو على خوادمكم الخاصة عبر Docker، مع سكربتات جاهزة للتشغيل والإيقاف والنسخ الاحتياطي والاستعادة والتحديث.");

  // Outro
  closeCap();
  await page.evaluate(() => { window.__fm?.hide(); window.__fm?.chap("", 1); });
  chapters.push({ t: now(), title: "الخاتمة" });
  await page.evaluate(() => window.__fm?.card("مرآة المستقبل", "جرّب الغد قبل أن تقرّره", "وكلاء متخصصون • محاكاة كمية • محكمة وكلاء • آلة زمن • حوكمة واعتماد بشري • عربي وإنجليزي"));
  open = { start: now(), text: "مرآة المستقبل — جرّب الغد قبل أن تقرّره" };
  await sleep(7000);
  closeCap();
} finally {
  clearInterval(ticker);
  await cdp.send("Page.stopScreencast").catch(() => {});
  ffmpeg.stdin.end();
  await new Promise((r) => ffmpeg.on("close", r));
  await browser.close();
  const total = now();
  fs.writeFileSync(path.join(OUT, "future-mirror-demo-ar.srt"),
    srt.map((c, i) => `${i + 1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${c.text}\n`).join("\n"), "utf8");
  const mmss = (ms) => `${String(Math.floor(ms / 60000)).padStart(2, "0")}:${String(Math.floor(ms / 1000) % 60).padStart(2, "0")}`;
  fs.writeFileSync(path.join(OUT, "chapters.txt"), chapters.map((c) => `${mmss(c.t)} ${c.title}`).join("\n") + "\n", "utf8");
  console.log(`duration ${mmss(total)} · captions ${srt.length} · frames ${written} · page errors ${errors.length}`);
  if (errors.length) console.log(errors.slice(0, 5).join("\n"));
}
