import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Field, Modal, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, fmtMoney, fmtNum, useI18n } from "../lib/i18n";
import { WEEKDAYS } from "./Auth";

export function UsersAdmin() {
  const { t, lang, pick } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const users = useQuery({ queryKey: ["users"], queryFn: () => api.get<any[]>("/users") });
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api.get<any>("/roles") });
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ email: "", full_name: "", role: "contracts_manager", title: "", password: "", language: lang });
  const create = useMutation({ mutationFn: () => api.post("/users", f), onSuccess: () => { setOpen(false); qc.invalidateQueries({ queryKey: ["users"] }); } });
  const upd = useMutation({ mutationFn: ({ id, body }: { id: string; body: any }) => api.patch(`/users/${id}`, body), onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }) });
  const roleLabel = (code: string) => pick(roles.data?.roles.find((r: any) => r.code === code)) || code;
  return (
    <div>
      <PageHeader title={t("nav_users")} actions={can("admin.users") && <Button onClick={() => setOpen(true)}>{t("add_user")}</Button>} />
      <Card>
        {users.isLoading ? <Spinner /> : <table className="w-full"><thead><tr><th className="th">{t("name")}</th><th className="th">{t("email")}</th><th className="th">{t("role")}</th><th className="th">MFA</th><th className="th">{t("active")}</th><th className="th">Last login</th></tr></thead>
          <tbody>{users.data?.map((u) => (
            <tr key={u.id} className="border-t border-slate-100"><td className="td font-medium">{u.full_name}<div className="text-xs text-slate-400">{u.title}</div></td><td className="td text-sm">{u.email}</td>
              <td className="td">{can("admin.users") ? <select className="input" value={u.role} onChange={(e) => upd.mutate({ id: u.id, body: { role: e.target.value } })}>
                {roles.data?.roles.map((r: any) => <option key={r.code} value={r.code}>{pick(r)}</option>)}</select> : roleLabel(u.role)}</td>
              <td className="td">{u.mfa_enabled ? <Badge tone="green">on</Badge> : <Badge>off</Badge>}</td>
              <td className="td"><input type="checkbox" disabled={!can("admin.users")} checked={u.is_active} onChange={(e) => upd.mutate({ id: u.id, body: { is_active: e.target.checked } })} /></td>
              <td className="td text-xs">{fmtDate(u.last_login_at, lang)}</td></tr>))}</tbody></table>}
        {upd.error && <Alert tone="error">{(upd.error as Error).message}</Alert>}
      </Card>
      {roles.data && <Card className="mt-5" title={lang === "ar" ? "مصفوفة الصلاحيات" : "Role permissions"}>
        <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr><th className="th">Permission</th>{roles.data.roles.map((r: any) => <th key={r.code} className="th">{pick(r)}</th>)}</tr></thead>
          <tbody>{Object.keys(roles.data.permissions).map((p) => <tr key={p} className="border-t border-slate-100"><td className="px-3 py-1.5">{p}</td>
            {roles.data.roles.map((r: any) => <td key={r.code} className="text-center">{r.permissions.includes(p) ? "●" : ""}</td>)}</tr>)}</tbody></table></div>
      </Card>}
      <Modal open={open} onClose={() => setOpen(false)} title={t("add_user")}>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <Field label={t("name")}><input className="input" required value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field label={t("email")}><input className="input" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <Field label={t("role")}><select className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{roles.data?.roles.map((r: any) => <option key={r.code} value={r.code}>{pick(r)}</option>)}</select></Field>
          <Field label={t("title")}><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label={t("password")}><input className="input" type="password" minLength={10} required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
          {create.error && <Alert tone="error">{(create.error as Error).message}</Alert>}
          <Button type="submit" loading={create.isPending}>{t("create")}</Button>
        </form>
      </Modal>
    </div>
  );
}

export function OrgSettings() {
  const { t, lang } = useI18n();
  const { can, refresh, me } = useAuth();
  const org = useQuery({ queryKey: ["org"], queryFn: () => api.get<any>("/org") });
  const audit = useQuery({ queryKey: ["audit"], enabled: can("audit.read"), queryFn: () => api.get<any[]>("/audit", { limit: 60 }) });
  const [f, setF] = useState<any>(null);
  useEffect(() => { if (org.data) setF({ ...org.data, holidays: org.data.holidays.join("\n") }); }, [org.data]);
  const save = useMutation({ mutationFn: () => api.patch("/org", { name: f.name, name_ar: f.name_ar, weekend_days: f.weekend_days, vat_rate: f.vat_rate,
    holidays: f.holidays.split(/\s+/).filter(Boolean), ai_external_processing: f.ai_external_processing, data_retention_days: Number(f.data_retention_days) }), onSuccess: () => refresh() });
  const verify = useMutation({ mutationFn: () => api.get<any>("/audit/verify") });
  const mfa = useMutation({ mutationFn: () => api.post<any>("/auth/mfa/setup") });
  const [code, setCode] = useState("");
  const enable = useMutation({ mutationFn: () => api.post("/auth/mfa/enable", { code }), onSuccess: () => refresh() });
  if (!f) return <Spinner />;
  const ed = can("admin.org");
  return (
    <div>
      <PageHeader title={t("nav_settings")} />
      <div className="grid gap-5 xl:grid-cols-2">
        <Card title={t("nav_settings")}>
          <div className="space-y-3">
            <Field label={t("company_name")}><input disabled={!ed} className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
            <Field label={t("company_name_ar")}><input disabled={!ed} className="input" dir="rtl" value={f.name_ar || ""} onChange={(e) => setF({ ...f, name_ar: e.target.value })} /></Field>
            <Field label={t("weekend")}><div className="flex flex-wrap gap-2">{WEEKDAYS.map(([d, en, ar]) => (
              <label key={d} className="flex items-center gap-1.5 rounded border px-2 py-1 text-sm"><input disabled={!ed} type="checkbox" checked={f.weekend_days.includes(d)}
                onChange={(e) => setF({ ...f, weekend_days: e.target.checked ? [...f.weekend_days, d] : f.weekend_days.filter((x: number) => x !== d) })} />{lang === "ar" ? ar : en}</label>))}</div></Field>
            <Field label={t("holidays")}><textarea disabled={!ed} className="input min-h-24 font-mono text-xs" value={f.holidays} onChange={(e) => setF({ ...f, holidays: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("vat_rate")}><input disabled={!ed} className="input" type="number" value={f.vat_rate} onChange={(e) => setF({ ...f, vat_rate: e.target.value })} /></Field>
              <Field label={t("retention")}><input disabled={!ed} className="input" type="number" value={f.data_retention_days} onChange={(e) => setF({ ...f, data_retention_days: e.target.value })} /></Field>
            </div>
            <label className="flex items-start gap-2 rounded-lg border p-3 text-sm"><input disabled={!ed} type="checkbox" className="mt-1" checked={f.ai_external_processing} onChange={(e) => setF({ ...f, ai_external_processing: e.target.checked })} />
              <span><span className="font-medium">{t("ai_policy")}</span><span className="block text-xs text-slate-500">{t("ai_policy_help")}</span></span></label>
            {ed && <Button loading={save.isPending} onClick={() => save.mutate()}>{t("save")}</Button>}
            {save.isSuccess && <Alert tone="ok">✓</Alert>}{save.error && <Alert tone="error">{(save.error as Error).message}</Alert>}
          </div>
        </Card>
        <div className="space-y-5">
          <Card title={<span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" />{t("security")}</span>}>
            {me?.mfa_enabled ? <Alert tone="ok">MFA ✓</Alert> : (<>
              <Button variant="secondary" onClick={() => mfa.mutate()}>{t("enable_mfa")}</Button>
              {mfa.data && <div className="mt-3 space-y-2 text-sm"><div className="break-all rounded bg-slate-50 p-2 font-mono text-xs">{mfa.data.secret}</div>
                <div className="break-all text-xs text-slate-500">{mfa.data.otpauth_uri}</div>
                <div className="flex gap-2"><input className="input" placeholder="123456" value={code} onChange={(e) => setCode(e.target.value)} /><Button onClick={() => enable.mutate()}>OK</Button></div>
                {enable.error && <Alert tone="error">{(enable.error as Error).message}</Alert>}</div>}</>)}
          </Card>
          {can("audit.read") && <Card title={t("audit")} actions={<Button size="sm" variant="secondary" onClick={() => verify.mutate()}>{t("verify_chain")}</Button>}>
            {verify.data && <div className="mb-3"><Alert tone={verify.data.valid ? "ok" : "error"}>{verify.data.valid ? `✓ ${verify.data.checked}` : `✗ seq ${verify.data.broken_at_seq}`}</Alert></div>}
            <div className="max-h-96 overflow-y-auto"><table className="w-full text-xs"><tbody>{audit.data?.map((a) => (
              <tr key={a.seq} className="border-t border-slate-100"><td className="px-2 py-1.5 text-slate-400">#{a.seq}</td><td className="px-2 py-1.5">{fmtDate(a.at, lang)}</td><td className="px-2 py-1.5">{a.user || "system"}</td>
                <td className="px-2 py-1.5 font-mono">{a.action}</td><td className="px-2 py-1.5 font-mono text-slate-400">{a.hash}</td></tr>))}</tbody></table></div>
          </Card>}
        </div>
      </div>
    </div>
  );
}

export function Subscription() {
  const { t, lang, pick } = useI18n();
  const q = useQuery({ queryKey: ["subscription"], queryFn: () => api.get<any>("/subscription") });
  const plans = useQuery({ queryKey: ["plans"], queryFn: () => api.get<any[]>("/plans") });
  if (q.isLoading) return <Spinner />;
  const s = q.data;
  const bar = (used: number, max: number) => <div className="h-2 w-full rounded-full bg-slate-100"><div className="h-full rounded-full bg-navy-700" style={{ width: `${Math.min(100, (used / Math.max(1, max)) * 100)}%` }} /></div>;
  const rows: [string, number, number][] = s.limits ? [["Users", s.usage.users, s.limits.users], ["Projects", s.usage.projects, s.limits.projects],
    ["Documents / month", s.usage.documents_month, s.limits.documents_month], ["Pages / month", s.usage.pages_month, s.limits.pages_month],
    ["AI tokens / month", s.usage.ai_tokens_month, s.limits.ai_tokens_month]] : [];
  return (
    <div>
      <PageHeader title={t("nav_subscription")} />
      <div className="grid gap-5 xl:grid-cols-3">
        <Card title={t("plan")}>
          {s.plan && <><div className="text-2xl font-semibold text-navy-900">{pick({ en: s.plan.name, ar: s.plan.name_ar })}</div>
            <div className="num mt-1 text-sm">{fmtMoney(s.plan.price_monthly, lang)} / {lang === "ar" ? "شهر" : "month"}</div>
            <div className="mt-3 flex flex-wrap gap-1.5"><Badge tone={s.subscription.status === "active" ? "green" : "amber"}>{s.subscription.status}</Badge><Badge>{s.subscription.billing_cycle}</Badge></div>
            <div className="mt-3 text-xs text-slate-500">{lang === "ar" ? "التجديد" : "Renews"}: {fmtDate(s.subscription.renews_at, lang)}</div></>}
          <p className="mt-4 text-xs text-slate-500">{s.payment_gateway}</p>
        </Card>
        <Card title={t("usage")} className="xl:col-span-2">
          <div className="space-y-3">{rows.map(([k, u, m]) => <div key={k}><div className="mb-1 flex justify-between text-sm"><span>{k}</span><span className="num text-slate-600">{fmtNum(u, lang)} / {fmtNum(m, lang)}</span></div>{bar(u, m)}</div>)}</div>
          <div className="mt-4 text-xs text-slate-500">OCR pages: {s.usage.ocr_pages_month} · AI runs (total): {s.usage.ai_runs_total} · claim documents: {s.usage.claim_documents_month}</div>
        </Card>
        <Card title={t("plan")} className="xl:col-span-3">
          <div className="grid gap-3 md:grid-cols-3">{plans.data?.map((p) => (
            <div key={p.code} className={`rounded-xl border p-4 ${p.code === s.plan?.code ? "border-navy-800 ring-2 ring-navy-800/10" : "border-slate-200"}`}>
              <div className="font-semibold">{pick({ en: p.name, ar: p.name_ar })}</div><div className="num text-xl font-semibold text-navy-900">{fmtMoney(p.price_monthly, lang)}</div>
              <div className="mt-2 text-xs text-slate-500">{p.max_users} users · {p.max_projects} projects · {fmtNum(p.max_documents_month, lang)} docs/month</div></div>))}</div>
          <p className="mt-3 text-xs text-slate-500">{lang === "ar" ? "الأسعار افتراضات تجارية أولية يجري التحقق منها مع العملاء." : "Prices are initial commercial hypotheses being validated with customers."}</p>
        </Card>
      </div>
    </div>
  );
}

export function Platform() {
  const { lang } = useI18n();
  const q = useQuery({ queryKey: ["platform"], queryFn: () => api.get<any>("/platform/commercial") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <Alert tone="error">{(q.error as Error).message}</Alert>;
  const d = q.data;
  return (
    <div>
      <PageHeader title="PAIS — Commercial progress" subtitle={d.note} />
      <div className="grid gap-3 md:grid-cols-4">
        {[["Paying customers", `${d.paying_customers} / ${d.target_customers}`], ["MRR", fmtMoney(d.mrr, lang)], ["Target MRR", fmtMoney(d.target_mrr, lang)], ["Progress", `${d.progress_pct.toFixed(1)}%`]].map(([k, v]) => (
          <div key={k} className="rounded-xl border bg-white p-4"><div className="text-xs text-slate-500">{k}</div><div className="num mt-1 text-xl font-semibold">{v}</div></div>))}
      </div>
      <Card className="mt-5" title="By plan"><pre className="text-sm">{JSON.stringify(d.by_plan, null, 2)}</pre><p className="text-xs text-slate-500">Trials: {d.trials}</p></Card>
    </div>
  );
}
