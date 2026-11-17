// Records the Arabic product demo video of HAQQ (حقّك) from the REAL running app and DEMO data.
// Reset the demo data first (ops\seed-demo.bat reset), then, from haqq/frontend:
//   BASE_URL=http://localhost:8090 OUT_DIR=../docs/video node e2e/video/record-demo-ar.mjs
// (dev server: BASE_URL=http://localhost:5173). Recording engine shared with the Future Mirror videos.
//
// Frames come from Chrome's screencast (crisp JPEG), are re-timed to a constant 25 fps and
// piped into ffmpeg (H.264 MP4). On-screen Arabic captions, chapter cards and a visible cursor
// are injected into the page, so Arabic shaping and RTL are rendered by the browser itself.
// Writes: haqq-demo-ar.mp4, haqq-demo-ar.srt (narration, for the voice-over), haqq-chapters.txt.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const BASE = process.env.BASE_URL || "http://localhost:5173";
const OUT = path.resolve(process.env.OUT_DIR || "../docs/video");
const W = 1600, H = 900, FPS = 25;
const PASSWORD = "HaqqDemo!2026";
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
const browser = await chromium.launch({ executablePath: process.env.PW_CHROMIUM || undefined, args: ["--force-color-profile=srgb", "--font-render-hinting=none"] });
const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, locale: "ar-EG" });
await context.addInitScript(() => { localStorage.setItem("haqq.lang", "ar"); });
await context.addInitScript(OVERLAY);
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

const ffmpeg = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
  "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
  "-vf", "scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
  "-profile:v", "high", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "96k", "-shortest",
  path.join(OUT, "haqq-demo-ar.mp4")], { stdio: ["pipe", "inherit", "inherit"] });
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
const TOTAL_CH = 10;
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
  await go("/", 1200);
  await click(page.getByTestId("email"), 200);
  await page.getByTestId("email").fill("");
  await page.keyboard.type(email, { delay: 45 });
  await click(page.getByTestId("password"), 200);
  await page.getByTestId("password").fill("");
  await page.keyboard.type(PASSWORD, { delay: 45 });
  await click(page.getByTestId("login"), 300);
  await page.getByTestId("lang-toggle").waitFor();
  await sleep(1400);
}
async function api(path) {                       // read ids from the API with the signed-in session
  return page.evaluate(async (p) => {
    const r = await fetch("/api/v1" + p, { headers: { Authorization: "Bearer " + sessionStorage.getItem("haqq.token") } });
    return r.json();
  }, path);
}
// ------------------------------------------------------------------ the demo
try {
  await go("/", 600);
  await page.evaluate(() => window.__fm?.card("عرض توضيحي للمنتج", "حقّك — HAQQ", "منصة ذكاء اصطناعي لاكتشاف المستحقات التعاقدية وحماية إيرادات شركات المقاولات"));
  chapters.push({ t: 0, title: "المقدمة" });
  open = { start: now(), text: "حقّك: اكتشف مستحقاتك التعاقدية قبل أن تضيع." };
  await sleep(6500);
  closeCap();
  await page.evaluate(() => window.__fm?.uncard());
  await sleep(900);

  // 1. Sign-in
  await chapter("تسجيل الدخول", "حسابات تجريبية لكل دور في شركة المقاولات");
  await say("كثير من شركات المقاولات لها حقوق تعاقدية لا تطالب بها، لأن الدليل متفرق والمواعيد تفوت. حقّك يربط بين بنود العقد وما حدث في الموقع والمستندات المتاحة.");
  await say("كل البيانات في هذا العرض افتراضية لمشروع تجريبي، والمبالغ توضيحية وليست مطالبات مثبتة أو مضمونة التحصيل.");
  await cap("ندخل بحساب المدير التجاري، وهو الشخص الذي يراجع النتائج ويقرر متابعة المطالبة.");
  await login("commercial@haqq.demo");

  // 2. Executive dashboard
  await chapter("لوحة القيادة التنفيذية", "المحفظة كلها في نظرة واحدة، محسوبة من السجلات الفعلية");
  await say("لوحة القيادة تعرض قيمة العقود، والمستحقات المحتملة، والإيرادات المعرضة للخطر، والمواعيد الحرجة، ومسار المطالبات حتى التحصيل.");
  await point(page.locator('[data-kpi="potential_entitlements"]'), 600);
  await say("لاحظ أن المنصة تفرّق دائماً بين مستحق محتمل، ومطالبة مقدّمة، ومبلغ معتمد، ومبلغ تم تحصيله فعلاً.");
  await cap("كل مؤشر قابل للتفصيل. نضغط على الإيرادات المعرضة للخطر.");
  await click(page.locator('[data-kpi="revenue_at_risk"]'), 2200);
  await say("تظهر البنود التي تكوّن هذا الرقم، وكل بند يفتح ملفه الكامل. لا توجد أرقام مكتوبة يدوياً في اللوحة.");
  await click(page.getByRole("button", { name: "close" }), 900);
  await scroll(900, 1800);
  await say("الرسوم تعرض التعرض المالي لكل مشروع، والمستحقات حسب الفئة، ومسار المطالبات، والمواعيد التعاقدية القادمة.");
  await scroll(0, 1000);

  // 3. Project & journey
  const projects = await api("/projects");
  const nac = projects.find((p) => p.code === "NAC-01");
  await chapter("المشروع ورحلة حماية الإيرادات", "مجمع إداري وتجاري بقيمة مائة مليون جنيه");
  await go(`/projects/${nac.id}`);
  await say("المشروع الأول قيمته مائة مليون جنيه. الرحلة ست خطوات واضحة: رفع العقد، ثم مستندات المشروع، ثم التحليل، واكتشاف المستحقات، ومراجعة الأدلة، وإعداد المطالبة.");

  // 4. Documents & OCR
  await chapter("مستودع المستندات", "عقود ومستندات ممسوحة ضوئياً وجداول كميات وبريد إلكتروني");
  await click(page.getByRole("button", { name: /^المستندات/ }), 1600);
  await say("هنا كل مستندات المشروع: العقد بصيغة PDF، والشروط الخاصة بالعربية في ملف Word، وجدول الكميات في Excel، ومحاضر الاجتماعات والخطابات والبريد الإلكتروني.");
  await scroll(500, 1400);
  await say("المنصة صنّفت كل مستند تلقائياً، وحدّدت تاريخه والطرف الذي أصدره.");
  await cap("هذه تعليمات موقع ممسوحة ضوئياً كصورة فقط. لنرَ كيف قرأتها المنصة.");
  await click(page.getByRole("link", { name: /SI-014/ }), 2200);
  await say("بالتعرف الضوئي على الحروف استُخرج نص التعليمات: المهندس يطلب إنشاء خزان مياه إضافي وغرفة طلمبات خارج نطاق العقد.");

  // 5. Contract intelligence
  await chapter("ذكاء العقد", "البنود والمهل وسقوط الحق، مع رقم الصفحة لكل بند");
  await go(`/projects/${nac.id}/clauses`);
  await say("حلّلت المنصة العقد إلى بنود، ولكل بند رقمه وعنوانه ونصه الحرفي ورقم الصفحة، وتصنيفه، والالتزامات والحقوق والشروط والاستثناءات.");
  await click(page.getByText("البنود ذات المهل فقط"), 1800);
  await say("بالأحمر المهل التي يترتب على فواتها سقوط الحق. البند عشرين واحد يشترط الإخطار خلال ثمانية وعشرين يوماً، بينما الشروط الخاصة العربية تنص على واحد وعشرين يوماً لمطالبات التأخير.");
  await cap("ويمكن سؤال العقد مباشرة.");
  const ask = page.getByPlaceholder(/مثال/);
  await click(ask, 200);
  await page.keyboard.type("ما مهلة الإخطار بالمطالبات؟", { delay: 55 });
  await click(page.getByRole("button", { name: "بحث" }).last(), 2200);
  await say("تظهر البنود الأكثر صلة بالسؤال مع مصدرها. وإذا فعّلت الشركة نموذج ذكاء اصطناعي، تأتي الإجابة مكتوبة مع الإشارة للمصادر.");

  // 6. Events
  const ents = await api(`/projects/${nac.id}/entitlements`);
  const e1 = ents.find((e) => e.ref === "ENT-001");
  await chapter("سجل الأحداث", "ما حدث في الموقع، مربوطاً بأدلته");
  await go(`/events/${e1.event_id}`);
  await say("الحدث الأول: تعليمات المهندس بإنشاء خزان إضافي. سجّله مهندس الموقع، وربط به التعليمات الممسوحة ومحضر الاجتماع وجدول الكميات والتقرير اليومي.");
  await scroll(450, 1500);
  await say("المنصة تقترح مستندات أخرى ذات صلة، لكنها لا تُحتسب دليلاً إلا بعد أن يربطها المستخدم بنفسه.");
  await scroll(0, 900);

  // 7. Entitlement
  await chapter("اكتشاف المستحق", "لماذا رصد حقّك هذا الاستحقاق المحتمل؟");
  await go(`/entitlements/${e1.id}`);
  await point(page.getByTestId("fin-impact"), 600);
  await say("النتيجة: مستحق محتمل عن أعمال إضافية بقيمة تقديرية مليوني جنيه، محسوبة من فئات جدول الكميات.");
  await say("المهم هو السبب. كل سطر في التفسير يشير إلى بند العقد أو المستند ورقم الصفحة، مع اقتباس حرفي.");
  await scroll(380, 1500);
  await say("البند ثلاثة عشر واحد يمنح الحق في تقييم الأعمال الإضافية. والبند ثلاثة عشر اثنين يشترط تعليمات مكتوبة، وهي موجودة بالفعل.");
  await point(page.getByTestId("notice-due"), 700);
  await say("لكن هناك خطر: إخطار المقاول غير موجود في الملف، ومهلة الإخطار حسب البند عشرين واحد تنتهي بعد سبعة أيام.");
  await say("ودرجة اليقين في الموعد تقديرية، لأن البند لا يحدد هل الأيام تقويمية أم أيام عمل. المنصة توضح افتراضها بدلاً من أن تخفيه.");
  await scroll(1500, 1800);
  await say("الأدلة المتوفرة والناقصة واضحة، ومعها الإجراءات الموصى بها، وطريقة حساب درجة الثقة.");
  await scroll(0, 900);

  // 8. Valuation
  await chapter("التقييم المالي", "حسابات دقيقة بمعادلات واضحة، وفصل للمهام");
  await go(`/entitlements/${e1.id}/valuation`);
  await say("ورقة التقييم أعدّها مدير العقود من فئات جدول الكميات. كل الحسابات تتم بمحرك حسابي دقيق، وليس بالنموذج اللغوي.");
  await scroll(700, 1600);
  await say("كل خطوة معروضة بمعادلتها: التكاليف المباشرة، والمصروفات العمومية، والربح، والضريبة، والإجمالي.");
  await scroll(0, 900);
  const verifyBtn = page.getByRole("button", { name: "اعتماد التقييم" });
  if (await verifyBtn.count()) {
    await cap("والاعتماد يتم من شخص آخر غير من أعدّ التقييم.");
    await click(verifyBtn, 2000);
  }

  // 9. Claim
  await chapter("إعداد المطالبة", "خطاب إخطار وملف مطالبة بالعربية والإنجليزية");
  await go(`/entitlements/${e1.id}`);
  await cap("بضغطة واحدة نبدأ إعداد المطالبة.");
  await click(page.getByTestId("create-claim"), 2400);
  await say("المطالبة تمر بمراحل معتمدة: مراجعة مبدئية، وتجميع الأدلة، والتحقق التعاقدي، والتقييم، والمراجعة الفنية والقانونية، ثم اعتماد الإدارة.");
  await page.locator("select").first().selectOption("notice");
  await cap("ننشئ الآن خطاب إخطار باللغة العربية.");
  await click(page.getByTestId("generate"), 2600);
  await say("الخطاب جاهز كمسودة تحتوي على البند التعاقدي ورقم الصفحة، وتنبيه واضح بأنه لم يُرسل. حقّك لا يرسل أي مطالبة لصاحب العمل؛ القرار دائماً للشركة.");
  const e5 = ents.find((e) => e.ref === "ENT-005");
  await go(`/entitlements/${e5.id}`);
  await say("وهذه نقطة مهمة للمصداقية: ارتفاع سعر الحديد لا تعتبره المنصة مستحقاً تلقائياً، لأن البند ثلاثة عشر سبعة يستبعد ذلك. الحالة: يتطلب تحقق خبير.");
  const e2 = ents.find((e) => e.ref === "ENT-002");
  await go(`/entitlements/${e2.id}`);
  await say("وفي تأخر تسليم الموقع، تنبّه المنصة إلى تعارض مهلتي الإخطار بين الشروط العامة والخاصة، ولا تقرر أن المقاول يستحق مد المدة قبل تحليل المسار الحرج.");

  // 10. Deadlines & close
  await chapter("المواعيد والتنبيهات", "تقويم تعاقدي بأيام العمل المصرية وتنبيهات تصاعدية");
  await go("/deadlines");
  await say("تقويم المواعيد يعرض كل مهلة تعاقدية، مع أيام العطلة المصرية، ودرجة اليقين، وطريقة الحساب.");
  await click(page.getByRole("button", { name: /فحص المواعيد/ }), 2200);
  await say("وفحص المواعيد يرسل تنبيهات تتصاعد من مدير العقود إلى المدير التجاري ثم الإدارة العليا كلما اقترب الموعد.");
  await go("/", 1400);
  await cap("والمنصة كلها متاحة بالإنجليزية بضغطة واحدة.");
  await click(page.getByTestId("lang-toggle"), 3000);
  await click(page.getByTestId("lang-toggle"), 1800);
  await say("حقّك يعمل على خوادمكم الخاصة، مع نسخ احتياطي يتم التحقق منه، وصلاحيات لكل دور، وعزل كامل لبيانات كل شركة.");

  closeCap();
  await page.evaluate(() => { window.__fm?.hide(); window.__fm?.chap("", 1); });
  chapters.push({ t: now(), title: "الخاتمة" });
  await page.evaluate(() => window.__fm?.card("حقّك — HAQQ", "لا تخسر ما يمنحك إياه عقدك", "اكتشاف المستحقات • حماية المواعيد • ملفات مطالبات موثقة • رؤية مالية للإدارة — Paradise AI Solutions"));
  open = { start: now(), text: "حقّك: لا تخسر ما يمنحك إياه عقدك." };
  await sleep(7000);
  closeCap();
} finally {
  clearInterval(ticker);
  await cdp.send("Page.stopScreencast").catch(() => {});
  ffmpeg.stdin.end();
  await new Promise((r) => ffmpeg.on("close", r));
  await browser.close();
  const total = now();
  fs.writeFileSync(path.join(OUT, "haqq-demo-ar.srt"),
    srt.map((c, i) => `${i + 1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${c.text}\n`).join("\n"), "utf8");
  const mmss = (ms) => `${String(Math.floor(ms / 60000)).padStart(2, "0")}:${String(Math.floor(ms / 1000) % 60).padStart(2, "0")}`;
  fs.writeFileSync(path.join(OUT, "haqq-chapters.txt"), chapters.map((c) => `${mmss(c.t)} ${c.title}`).join("\n") + "\n", "utf8");
  console.log(`duration ${mmss(total)} · captions ${srt.length} · frames ${written} · page errors ${errors.length}`);
  if (errors.length) console.log(errors.slice(0, 5).join("\n"));
}
