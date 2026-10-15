import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Lock } from "lucide-react";
import { useAuth, useI18n } from "@/lib/app";
import { Button, ErrorBox, Input } from "@/components/ui";

const DEMO = [
  ["ceo@futuremirror.demo", "CEO"],
  ["cfo@futuremirror.demo", "CFO"],
  ["coo@futuremirror.demo", "COO"],
  ["legal@futuremirror.demo", "Legal"],
  ["hr@futuremirror.demo", "HR"],
  ["analyst@futuremirror.demo", "Analyst"],
  ["admin@futuremirror.demo", "Admin"],
];

export default function Login() {
  const { t, lang, setLang } = useI18n();
  const { login, user } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string } };
  const [email, setEmail] = useState("ceo@futuremirror.demo");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to={loc.state?.from || "/"} replace />;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await login(email, password);
      nav(loc.state?.from || "/");
    } catch {
      setErr(new Error(t("login.error")));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="grid min-h-full lg:grid-cols-2">
      <div className="relative hidden overflow-hidden lg:block">
        <div className="absolute inset-0 grid-bg opacity-60" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <img src="/favicon.svg" className="h-10 w-10" alt="" />
            <span className="font-display text-xl font-semibold">{t("appName")}</span>
          </div>
          <div>
            <motion.h1 initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
              className="font-display text-5xl font-semibold leading-tight tracking-tight">
              {t("tagline")}
            </motion.h1>
            <p className="mt-6 max-w-lg text-ink2">{t("cc.principle")}</p>
            <div className="mt-10 flex gap-3">
              {(["A", "B", "C"] as const).map((k, i) => (
                <motion.div key={k} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + i * 0.15 }}
                  className="card w-40 p-4">
                  <div className="h-1 w-10 rounded-full" style={{ background: `var(--f${k.toLowerCase()})` }} />
                  <div className="mt-3 text-xs text-muted">{lang === "ar" ? `المستقبل ${["أ", "ب", "ج"][i]}` : `Future ${k}`}</div>
                  <svg viewBox="0 0 100 30" className="mt-2 h-8 w-full">
                    <path d={["M0 28 L30 10 L60 6 L100 4", "M0 28 L30 24 L60 12 L100 6", "M0 28 L30 20 L60 10 L100 8"][i]}
                      fill="none" stroke={`var(--f${k.toLowerCase()})`} strokeWidth="2" />
                  </svg>
                </motion.div>
              ))}
            </div>
          </div>
          <div className="text-xs text-muted">© Future Mirror AI · Decision intelligence with enforceable human authority</div>
        </div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="card w-full max-w-md p-8">
          <div className="flex items-center justify-between">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent/15 text-accent"><Lock className="h-5 w-5" /></div>
            <button type="button" className="text-xs text-muted hover:text-ink" onClick={() => setLang(lang === "en" ? "ar" : "en")}>
              {lang === "en" ? "العربية" : "English"}
            </button>
          </div>
          <h2 className="mt-5 font-display text-xl font-semibold">{t("login.title")}</h2>
          <div className="mt-6 space-y-4">
            <label className="block text-xs text-ink2">{t("login.email")}
              <Input className="mt-1" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" name="email" />
            </label>
            <label className="block text-xs text-ink2">{t("login.password")}
              <Input className="mt-1" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" name="password" />
            </label>
            <ErrorBox error={err} />
            <Button type="submit" className="w-full" loading={busy}>{t("login.submit")}</Button>
          </div>
          <div className="mt-6 border-t border-line pt-4">
            <div className="label mb-2">{t("login.demo")}</div>
            <div className="flex flex-wrap gap-1.5">
              {DEMO.map(([e, r]) => (
                <button type="button" key={e} onClick={() => { setEmail(e); setPassword("FutureMirror!2026"); }}
                  className="rounded-lg border border-line px-2 py-1 text-[11px] text-ink2 hover:border-accent">{r}</button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-muted">Password: FutureMirror!2026</p>
          </div>
        </form>
      </div>
    </div>
  );
}
