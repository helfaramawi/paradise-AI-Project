import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Languages, ShieldCheck, Sparkles, Scale, Clock } from "lucide-react";
import { Logo } from "../components/Layout";
import { Alert, Button, Field } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

function Shell({ children }: { children: React.ReactNode }) {
  const { t, lang, setLang } = useI18n();
  const points = lang === "ar"
    ? [[Sparkles, "اكتشاف المستحقات التعاقدية الخفية"], [Clock, "حماية مواعيد الإخطار التعاقدية"], [Scale, "ملفات مطالبات موثّقة بالمصادر"], [ShieldCheck, "عزل تام لبيانات كل شركة"]]
    : [[Sparkles, "Discover hidden contractual entitlements"], [Clock, "Protect contractual notice deadlines"], [Scale, "Source-referenced claim packages"], [ShieldCheck, "Full tenant data isolation"]];
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-navy-950 p-12 text-white lg:flex">
        <Logo light />
        <div>
          <h1 className="text-4xl font-semibold leading-tight">{t("tagline")}</h1>
          <p className="mt-4 max-w-md text-slate-300">{lang === "ar"
            ? "منصة ذكاء اصطناعي تربط بنود العقد بأحداث المشروع والأدلة لتكشف المستحقات المحتملة قبل فوات مواعيدها."
            : "AI that connects contract clauses, project events and evidence to surface potential entitlements before they are time-barred."}</p>
          <ul className="mt-8 space-y-3">
            {points.map(([Icon, txt], i) => { const I = Icon as typeof Sparkles; return <li key={i} className="flex items-center gap-3 text-sm text-slate-200"><I className="h-4 w-4 text-gold-400" />{txt as string}</li>; })}
          </ul>
        </div>
        <p className="text-xs text-slate-400">© Paradise AI Solutions (PAIS)</p>
      </div>
      <div className="flex flex-col">
        <div className="flex justify-end p-4">
          <button onClick={() => setLang(lang === "ar" ? "en" : "ar")} className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"><Languages className="h-4 w-4" />{t("language")}</button>
        </div>
        <div className="flex flex-1 items-center justify-center p-6">{children}</div>
      </div>
    </div>
  );
}

export function Login() {
  const { login } = useAuth();
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfa, setMfa] = useState("");
  const [needMfa, setNeedMfa] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await login(email, password, mfa); } catch (x) {
      const m = (x as Error).message;
      if (m === "mfa_required") setNeedMfa(true); else setErr(m);
    } finally { setBusy(false); }
  };
  const demo = ["ceo", "commercial", "contracts", "cfo", "legal", "site", "admin"];
  return (
    <Shell>
      <form onSubmit={submit} className="w-full max-w-sm space-y-4">
        <div className="lg:hidden"><Logo /></div>
        <h2 className="text-2xl font-semibold text-navy-900">{t("sign_in")}</h2>
        <Field label={t("email")}><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" data-testid="email" /></Field>
        <Field label={t("password")}><input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" data-testid="password" /></Field>
        {needMfa && <Field label={t("mfa_code")}><input className="input" inputMode="numeric" value={mfa} onChange={(e) => setMfa(e.target.value)} autoFocus /></Field>}
        {err && <Alert tone="error">{err}</Alert>}
        <Button className="w-full" loading={busy} type="submit" data-testid="login">{t("sign_in")}</Button>
        <Link to="/register" className="block text-center text-sm text-brand-600 hover:underline">{t("no_account")}</Link>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <div className="mb-1.5 font-semibold">{t("demo_accounts")}</div>
          <div className="flex flex-wrap gap-1.5">
            {demo.map((d) => <button type="button" key={d} className="rounded bg-white px-2 py-1 ring-1 ring-amber-200 hover:bg-amber-100"
              onClick={() => { setEmail(`${d}@haqq.demo`); setPassword("HaqqDemo!2026"); }}>{d}@haqq.demo</button>)}
          </div>
        </div>
      </form>
    </Shell>
  );
}

const WEEKDAYS: [number, string, string][] = [[0, "Mon", "الإثنين"], [1, "Tue", "الثلاثاء"], [2, "Wed", "الأربعاء"], [3, "Thu", "الخميس"], [4, "Fri", "الجمعة"], [5, "Sat", "السبت"], [6, "Sun", "الأحد"]];
export { WEEKDAYS };

export function Onboarding() {
  const { me, acceptSession, refresh } = useAuth();
  const { t, lang } = useI18n();
  const nav = useNavigate();
  const [step, setStep] = useState(me ? 1 : 0);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reg, setReg] = useState({ company_name: "", company_name_ar: "", full_name: "", email: "", password: "", plan_code: "business" });
  const [pol, setPol] = useState({ weekend_days: [4, 5], ai_external_processing: false, vat_rate: "14" });
  const [proj, setProj] = useState({ code: "", name: "", name_ar: "", employer_name: "", engineer_name: "", contract_value: "", start_date: "" });

  const run = async (fn: () => Promise<void>) => { setBusy(true); setErr(null); try { await fn(); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); } };
  const steps = [t("create_account"), t("onb_step_policy"), t("onb_step_project")];

  return (
    <Shell>
      <div className="w-full max-w-lg">
        <h2 className="text-2xl font-semibold text-navy-900">{t("onboarding")}</h2>
        <ol className="my-5 flex gap-2 text-xs">
          {steps.map((s, i) => <li key={s} className={`flex-1 rounded-md px-2 py-1.5 text-center ${i === step ? "bg-navy-800 text-white" : i < step ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500"}`}>{i + 1}. {s}</li>)}
        </ol>
        {step === 0 && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); run(async () => {
            const r = await api.post("/auth/register", { ...reg, company_name_ar: reg.company_name_ar || undefined, language: lang });
            acceptSession(r); setStep(1); }); }}>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("company_name")}><input className="input" required value={reg.company_name} onChange={(e) => setReg({ ...reg, company_name: e.target.value })} /></Field>
              <Field label={t("company_name_ar")}><input className="input" dir="rtl" value={reg.company_name_ar} onChange={(e) => setReg({ ...reg, company_name_ar: e.target.value })} /></Field>
            </div>
            <Field label={t("full_name")}><input className="input" required value={reg.full_name} onChange={(e) => setReg({ ...reg, full_name: e.target.value })} /></Field>
            <Field label={t("email")}><input className="input" type="email" required value={reg.email} onChange={(e) => setReg({ ...reg, email: e.target.value })} /></Field>
            <Field label={t("password")} hint={lang === "ar" ? "10 أحرف على الأقل وتتضمن حرفًا ورقمًا" : "At least 10 characters with a letter and a digit"}>
              <input className="input" type="password" required minLength={10} value={reg.password} onChange={(e) => setReg({ ...reg, password: e.target.value })} /></Field>
            <Field label={t("plan")}>
              <select className="input" value={reg.plan_code} onChange={(e) => setReg({ ...reg, plan_code: e.target.value })}>
                <option value="project">Project — EGP 10,000 / {lang === "ar" ? "شهر" : "month"}</option>
                <option value="business">Business — EGP 20,000 / {lang === "ar" ? "شهر" : "month"}</option>
                <option value="enterprise">Enterprise — EGP 40,000 / {lang === "ar" ? "شهر" : "month"}</option>
              </select></Field>
            <p className="text-xs text-slate-500">{lang === "ar" ? "تجربة مجانية لمدة 30 يومًا. الأسعار افتراضات أولية قابلة للتحقق مع العملاء." : "30-day free trial. Prices are initial hypotheses being validated with customers."}</p>
            {err && <Alert tone="error">{err}</Alert>}
            <Button className="w-full" loading={busy} type="submit">{t("create_account")}</Button>
            <Link to="/" className="block text-center text-sm text-brand-600">{t("have_account")}</Link>
          </form>
        )}
        {step === 1 && (
          <div className="space-y-4">
            <Field label={t("weekend")}>
              <div className="flex flex-wrap gap-2">{WEEKDAYS.map(([d, en, ar]) => (
                <label key={d} className="flex items-center gap-1.5 rounded border px-2 py-1 text-sm">
                  <input type="checkbox" checked={pol.weekend_days.includes(d)} onChange={(e) => setPol({ ...pol, weekend_days: e.target.checked ? [...pol.weekend_days, d] : pol.weekend_days.filter((x) => x !== d) })} />
                  {lang === "ar" ? ar : en}</label>))}</div>
            </Field>
            <Field label={t("vat_rate")}><input className="input" type="number" value={pol.vat_rate} onChange={(e) => setPol({ ...pol, vat_rate: e.target.value })} /></Field>
            <label className="flex items-start gap-2 rounded-lg border p-3 text-sm">
              <input type="checkbox" className="mt-1" checked={pol.ai_external_processing} onChange={(e) => setPol({ ...pol, ai_external_processing: e.target.checked })} />
              <span><span className="font-medium">{t("ai_policy")}</span><span className="block text-xs text-slate-500">{t("ai_policy_help")}</span></span>
            </label>
            {err && <Alert tone="error">{err}</Alert>}
            <Button loading={busy} onClick={() => run(async () => { await api.patch("/org", pol); setStep(2); })}>{t("next")}</Button>
          </div>
        )}
        {step === 2 && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); run(async () => {
            const p = await api.post("/projects", { ...proj, contract_value: proj.contract_value || "0", start_date: proj.start_date || undefined, name_ar: proj.name_ar || undefined });
            await api.patch("/org", { onboarding_completed: true }); await refresh(); nav(`/projects/${p.id}`); }); }}>
            <div className="grid grid-cols-3 gap-3">
              <Field label={t("code")}><input className="input" required pattern="[A-Za-z0-9\-_/]+" value={proj.code} onChange={(e) => setProj({ ...proj, code: e.target.value })} /></Field>
              <div className="col-span-2"><Field label={t("name")}><input className="input" required value={proj.name} onChange={(e) => setProj({ ...proj, name: e.target.value })} /></Field></div>
            </div>
            <Field label={t("name_ar")}><input className="input" dir="rtl" value={proj.name_ar} onChange={(e) => setProj({ ...proj, name_ar: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("employer")}><input className="input" value={proj.employer_name} onChange={(e) => setProj({ ...proj, employer_name: e.target.value })} /></Field>
              <Field label={t("engineer")}><input className="input" value={proj.engineer_name} onChange={(e) => setProj({ ...proj, engineer_name: e.target.value })} /></Field>
              <Field label={t("contract_value") + " (EGP)"}><input className="input" type="number" min="0" value={proj.contract_value} onChange={(e) => setProj({ ...proj, contract_value: e.target.value })} /></Field>
              <Field label={t("start_date")}><input className="input" type="date" value={proj.start_date} onChange={(e) => setProj({ ...proj, start_date: e.target.value })} /></Field>
            </div>
            {err && <Alert tone="error">{err}</Alert>}
            <div className="flex gap-2"><Button loading={busy} type="submit">{t("finish")}</Button>
              <Button variant="ghost" type="button" onClick={() => run(async () => { await api.patch("/org", { onboarding_completed: true }); await refresh(); nav("/projects"); })}>{lang === "ar" ? "تخطي" : "Skip"}</Button></div>
          </form>
        )}
      </div>
    </Shell>
  );
}
