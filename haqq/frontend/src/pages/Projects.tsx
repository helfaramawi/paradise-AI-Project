import { useMutation, useQuery } from "@tanstack/react-query";
import { Building2, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Alert, Badge, Button, Card, DemoBadge, Empty, Field, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, fmtMoney, useI18n } from "../lib/i18n";

export function Projects() {
  const { t, lang } = useI18n();
  const { can } = useAuth();
  const q = useQuery({ queryKey: ["projects"], queryFn: () => api.get<any[]>("/projects") });
  return (
    <div>
      <PageHeader title={t("portfolio")} actions={can("project.manage") && <Link to="/projects/new"><Button icon={<Plus className="h-4 w-4" />}>{t("new_project")}</Button></Link>} />
      {q.isLoading && <Spinner />}
      {q.data?.length === 0 && <Empty icon={<Building2 className="h-6 w-6" />}>{t("none")}</Empty>}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {q.data?.map((p) => (
          <Link key={p.id} to={`/projects/${p.id}`} className="rounded-xl border border-slate-200 bg-white p-5 shadow-card transition hover:border-brand-500">
            <div className="flex items-start justify-between gap-2">
              <div><div className="text-xs font-medium text-slate-500">{p.code}</div>
                <div className="mt-0.5 font-semibold text-navy-900">{lang === "ar" ? p.name_ar || p.name : p.name}</div></div>
              {p.is_demo && <DemoBadge />}
            </div>
            <div className="mt-1 text-xs text-slate-500">{p.employer_name} · {p.location}</div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-xs text-slate-500">{t("contract_value")}</dt><dd className="num font-semibold">{fmtMoney(p.contract_value, lang, { compact: true })}</dd></div>
              <div><dt className="text-xs text-slate-500">{t("k_potential_entitlements")}</dt><dd className="num font-semibold text-gold-500">{fmtMoney(p.stats.potential_value, lang, { compact: true })}</dd></div>
            </dl>
            <div className="mt-4 flex flex-wrap gap-1.5">
              <Badge>{p.stats.documents} {t("documents")}</Badge><Badge>{p.stats.events} {t("events")}</Badge>
              <Badge tone="blue">{p.stats.entitlements} {t("entitlements")}</Badge><Badge>{p.stats.claims} {t("claims")}</Badge>
              {p.stats.open_deadlines > 0 && <Badge tone="amber">{p.stats.open_deadlines} {t("deadlines")}</Badge>}
            </div>
            <div className="mt-3 text-xs text-slate-500">{t("completion")}: {fmtDate(p.current_completion_date, lang)}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function ProjectNew() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [f, setF] = useState<Record<string, string>>({ code: "", name: "", name_ar: "", employer_name: "", contractor_name: "", engineer_name: "",
    contract_form: "", location: "", contract_value: "", start_date: "", original_completion_date: "" });
  const m = useMutation({ mutationFn: (body: any) => api.post("/projects", body), onSuccess: (p: any) => nav(`/projects/${p.id}`) });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const body: any = Object.fromEntries(Object.entries(f).filter(([, v]) => v !== ""));
    body.contract_value = f.contract_value || "0";
    body.current_completion_date = f.original_completion_date || undefined;
    m.mutate(body);
  };
  const inp = (k: string, type = "text", extra: any = {}) => <input className="input" type={type} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} {...extra} />;
  return (
    <div className="max-w-3xl">
      <PageHeader title={t("new_project")} />
      <Card>
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
          <Field label={t("code")}>{inp("code", "text", { required: true, pattern: "[A-Za-z0-9\\-_/]+" })}</Field>
          <Field label={t("name")}>{inp("name", "text", { required: true })}</Field>
          <Field label={t("name_ar")}>{inp("name_ar", "text", { dir: "rtl" })}</Field>
          <Field label={t("location")}>{inp("location")}</Field>
          <Field label={t("employer")}>{inp("employer_name")}</Field>
          <Field label={t("contractor")}>{inp("contractor_name")}</Field>
          <Field label={t("engineer")}>{inp("engineer_name")}</Field>
          <Field label={t("contract_form")}>{inp("contract_form")}</Field>
          <Field label={t("contract_value") + " (EGP)"}>{inp("contract_value", "number", { min: 0 })}</Field>
          <Field label={t("start_date")}>{inp("start_date", "date")}</Field>
          <Field label={t("completion")}>{inp("original_completion_date", "date")}</Field>
          <div className="md:col-span-2">{m.error && <Alert tone="error">{(m.error as Error).message}</Alert>}</div>
          <div className="md:col-span-2"><Button type="submit" loading={m.isPending}>{t("create")}</Button></div>
        </form>
      </Card>
    </div>
  );
}
