import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, FileText, FileUp, MessageSquareText, Plus, Search, ShieldAlert, Sparkles } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Alert, Badge, Button, Card, ConfidenceBar, DemoBadge, Empty, Field, Modal, PageHeader, RiskBadge, Spinner, StatusBadge, Tabs } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, fmtMoney, fmtNum, useI18n } from "../lib/i18n";
import { useTaxonomy } from "../lib/taxonomy";

export default function ProjectDetail() {
  const { id = "", tab = "overview" } = useParams();
  const nav = useNavigate();
  const { t, lang } = useI18n();
  const q = useQuery({ queryKey: ["project", id], queryFn: () => api.get<any>(`/projects/${id}`) });
  if (q.isLoading) return <Spinner />;
  if (!q.data) return <Alert tone="error">{t("error")}</Alert>;
  const p = q.data;
  const s = p.stats;
  const tabs = [
    { key: "overview", label: t("overview") }, { key: "documents", label: t("documents"), count: s.documents },
    { key: "clauses", label: t("clauses"), count: s.clauses }, { key: "events", label: t("events"), count: s.events },
    { key: "entitlements", label: t("entitlements"), count: s.entitlements }, { key: "claims", label: t("claims"), count: s.claims },
    { key: "deadlines", label: t("deadlines"), count: s.open_deadlines },
  ];
  return (
    <div>
      <PageHeader crumbs={<Link to="/projects" className="hover:underline">{t("nav_projects")}</Link>}
        title={<span className="flex items-center gap-2">{p.code} · {lang === "ar" ? p.name_ar || p.name : p.name} {p.is_demo && <DemoBadge />}</span>}
        subtitle={`${p.employer_name || "—"} · ${t("contract_value")}: ${fmtMoney(p.contract_value, lang)}`} />
      <Tabs tabs={tabs} active={tab} onChange={(k) => nav(`/projects/${id}/${k}`)} />
      <div className="mt-5">
        {tab === "overview" && <Overview p={p} />}
        {tab === "documents" && <Documents pid={id} />}
        {tab === "clauses" && <Clauses pid={id} />}
        {tab === "events" && <Events pid={id} />}
        {tab === "entitlements" && <Entitlements pid={id} />}
        {tab === "claims" && <ClaimsTab pid={id} />}
        {tab === "deadlines" && <DeadlinesTab pid={id} />}
      </div>
    </div>
  );
}

function Overview({ p }: { p: any }) {
  const { t, lang } = useI18n();
  const s = p.stats;
  const steps = [
    { k: "j1", done: s.clauses > 0, to: "documents" }, { k: "j2", done: s.documents > 1, to: "documents" },
    { k: "j3", done: s.clauses > 0 && s.processing === 0, to: "clauses" }, { k: "j4", done: s.entitlements > 0, to: "events" },
    { k: "j5", done: s.entitlements > 0, to: "entitlements" }, { k: "j6", done: s.claims > 0, to: "claims" },
  ];
  const next = steps.find((x) => !x.done);
  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <Card title={t("journey")} className="xl:col-span-3">
        <ol className="grid gap-3 md:grid-cols-6">
          {steps.map((st, i) => (
            <li key={st.k}><Link to={`/projects/${p.id}/${st.to}`} className={clsx("flex h-full flex-col gap-2 rounded-lg border p-3 transition hover:border-brand-500",
              st.done ? "border-emerald-200 bg-emerald-50" : next === st ? "border-gold-400 bg-amber-50" : "border-slate-200")}>
              <span className={clsx("grid h-7 w-7 place-items-center rounded-full text-xs font-bold", st.done ? "bg-emerald-600 text-white" : "bg-navy-800 text-white")}>
                {st.done ? <Check className="h-4 w-4" /> : i + 1}</span>
              <span className="text-sm font-medium text-navy-900">{t(st.k)}</span>
            </Link></li>))}
        </ol>
      </Card>
      <Card title={t("overview")} className="xl:col-span-2">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm md:grid-cols-3">
          {[["employer", p.employer_name], ["contractor", p.contractor_name], ["engineer", p.engineer_name], ["location", p.location],
            ["contract_form", p.contract_form], ["contract_value", fmtMoney(p.contract_value, lang)], ["start_date", fmtDate(p.start_date, lang)],
            ["completion", fmtDate(p.current_completion_date, lang)]].map(([k, v]) => (
            <div key={k}><dt className="text-xs text-slate-500">{t(k)}</dt><dd className="font-medium text-navy-900">{v || "—"}</dd></div>))}
        </dl>
      </Card>
      <Card title={t("team")}>
        <ul className="space-y-2 text-sm">{p.members.map((m: any) => <li key={m.user_id} className="flex justify-between"><span>{m.full_name}</span><Badge>{m.project_role}</Badge></li>)}
          {p.members.length === 0 && <li className="text-slate-500">{t("none")}</li>}</ul>
        <p className="mt-3 text-xs text-slate-500">{lang === "ar" ? "الأدوار العليا (الإدارة، العقود، المالية، القانونية) ترى كل المشروعات." : "Leadership, contracts, finance and legal roles see all projects."}</p>
      </Card>
      <Card title={t("k_potential_entitlements")}><div className="num text-3xl font-semibold text-navy-900">{fmtMoney(s.potential_value, lang)}</div>
        <p className="mt-1 text-xs text-slate-500">{t("disclaimer")}</p></Card>
    </div>
  );
}

// ------------------------------------------------------------------ documents

const DOC_TYPES = ["contract", "boq", "site_instruction", "variation_order", "notice", "letter", "email", "meeting_minutes", "daily_report",
  "progress_report", "programme", "drawing", "payment_certificate", "cost_record", "photo", "other"];

function Documents({ pid }: { pid: string }) {
  const { t, lang } = useI18n();
  const { label } = useTaxonomy();
  const { can } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["docs", pid], queryFn: () => api.get<any[]>(`/projects/${pid}/documents`),
    refetchInterval: (query) => ((query.state.data as any[] | undefined)?.some((d) => ["uploaded", "processing"].includes(d.status)) ? 2000 : false) });
  const [meta, setMeta] = useState({ doc_type: "", author_party: "", doc_date: "" });
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const uploadFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true); setErrors([]);
    for (const f of Array.from(files)) {
      const fd = new FormData();
      fd.append("file", f);
      Object.entries(meta).forEach(([k, v]) => v && fd.append(k, v));
      try { await api.upload(`/projects/${pid}/documents`, fd); } catch (e) { setErrors((x) => [...x, `${f.name}: ${(e as Error).message}`]); }
    }
    setBusy(false);
    qc.invalidateQueries({ queryKey: ["docs", pid] }); qc.invalidateQueries({ queryKey: ["project", pid] });
  };
  return (
    <div className="space-y-5">
      {can("document.upload") && (
        <Card title={t("upload")}>
          <div className="grid gap-3 md:grid-cols-3">
            <Field label={t("doc_type")}><select className="input" value={meta.doc_type} onChange={(e) => setMeta({ ...meta, doc_type: e.target.value })}>
              <option value="">{t("auto_detect")}</option>{DOC_TYPES.map((d) => <option key={d} value={d}>{label("doc_types", d)}</option>)}</select></Field>
            <Field label={t("author")}><select className="input" value={meta.author_party} onChange={(e) => setMeta({ ...meta, author_party: e.target.value })}>
              <option value="">{t("auto_detect")}</option>{["contractor", "employer", "engineer", "subcontractor", "other"].map((a) => <option key={a} value={a}>{a}</option>)}</select></Field>
            <Field label={t("doc_date")}><input type="date" className="input" value={meta.doc_date} onChange={(e) => setMeta({ ...meta, doc_date: e.target.value })} /></Field>
          </div>
          <div onClick={() => input.current?.click()} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); uploadFiles(e.dataTransfer.files); }}
            className="mt-4 flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-600 hover:border-brand-500">
            <FileUp className="h-7 w-7 text-navy-700" />{busy ? t("loading") : t("drop_here")}
            <input ref={input} type="file" multiple className="hidden" data-testid="file-input" accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.tif,.tiff,.eml,.txt" onChange={(e) => uploadFiles(e.target.files)} />
          </div>
          {errors.map((e) => <Alert key={e} tone="error">{e}</Alert>)}
        </Card>
      )}
      <Card title={t("documents")}>
        {q.isLoading ? <Spinner /> : q.data?.length === 0 ? <Empty>{t("none")}</Empty> : (
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr><th className="th">{t("title")}</th><th className="th">{t("type")}</th><th className="th">{t("author")}</th><th className="th">{t("date")}</th><th className="th">{t("pages")}</th><th className="th">{t("status")}</th></tr></thead>
            <tbody>{q.data?.map((d) => (
              <tr key={d.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="td"><Link to={`/documents/${d.id}`} className="flex items-center gap-2 font-medium text-brand-600"><FileText className="h-4 w-4 shrink-0" />{d.title}</Link>
                  <div className="text-xs text-slate-400">{d.filename} · v{d.version}</div></td>
                <td className="td"><span>{label("doc_types", d.doc_type)}</span>{d.doc_type_confidence !== null && d.doc_type_confidence < 1 && <div className="text-xs text-slate-400">{Math.round(d.doc_type_confidence * 100)}% · {t("ai_suggest")}</div>}</td>
                <td className="td text-xs">{d.author_party || "—"}</td><td className="td num text-xs">{fmtDate(d.doc_date, lang)}</td>
                <td className="td num text-xs">{d.page_count}{d.ocr_pages > 0 && <Badge tone="violet" className="ms-1">{t("ocr")} {d.ocr_pages}</Badge>}</td>
                <td className="td"><div className="flex items-center gap-1"><StatusBadge status={d.status} label={t(d.status)} />
                  {d.security_flags?.length > 0 && <span title={t("security_flag")}><ShieldAlert className="h-4 w-4 text-red-600" /></span>}</div></td>
              </tr>))}</tbody>
          </table></div>)}
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ clauses

export function ClauseCard({ c, onVerify }: { c: any; onVerify?: (status: string) => void }) {
  const { t, lang } = useI18n();
  const { label } = useTaxonomy();
  const { can } = useAuth();
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4" dir={c.language === "ar" ? "rtl" : undefined}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-navy-900">{c.clause_number} — {c.title}</div>
          <div className="mt-0.5 text-xs text-slate-500">
            <Link to={`/documents/${c.document_id}`} className="hover:underline">{c.document_title}</Link> · {t("page")} {c.page_start}{c.page_end !== c.page_start && `–${c.page_end}`}
            {c.page_is_estimated && ` (${t("page_estimated")})`}</div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone="blue">{label("clause_categories", c.category)}</Badge>
          <StatusBadge status={c.verification_status} label={t(c.verification_status)} />
          <span className="num text-xs text-slate-500">{Math.round(c.confidence * 100)}%</span>
        </div>
      </div>
      {c.time_limits?.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{c.time_limits.map((tl: any, i: number) => (
        <Badge key={i} tone={tl.time_bar ? "red" : "amber"}>{tl.stated} · {tl.kind}{tl.day_type !== "unspecified" ? ` · ${tl.day_type}` : ""}{tl.time_bar ? ` · ${t("time_bar")}` : ""}</Badge>))}</div>}
      {c.risk_flags?.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{c.risk_flags.map((r: any) => <Badge key={r.code} tone="slate">⚑ {lang === "ar" ? r.ar : r.en}</Badge>)}</div>}
      <p className={clsx("quote mt-3 whitespace-pre-line rounded-md px-3 py-2 text-sm text-slate-700", !open && "line-clamp-3")}>{c.text}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button className="text-xs text-brand-600" onClick={() => setOpen(!open)}>{open ? "−" : "+"} {t("view")}</button>
        {onVerify && can("clause.verify") && c.verification_status !== "verified" && <Button size="sm" variant="secondary" onClick={() => onVerify("verified")}>{t("mark_verified")}</Button>}
        {onVerify && can("clause.verify") && c.verification_status !== "rejected" && <Button size="sm" variant="ghost" onClick={() => onVerify("rejected")}>{t("mark_rejected")}</Button>}
      </div>
      {open && (
        <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
          {[["rights", c.entitlements], ["obligations", c.obligations], ["conditions", c.conditions], ["exclusions", c.exclusions]].map(([k, items]) => (items as string[])?.length > 0 && (
            <div key={k as string}><div className="mb-1 text-xs font-semibold text-slate-500">{t(k as string)}</div>
              <ul className="list-disc space-y-1 ps-5 text-slate-700">{(items as string[]).map((x, i) => <li key={i}>{x}</li>)}</ul></div>))}
        </div>)}
    </div>
  );
}

function Clauses({ pid }: { pid: string }) {
  const { t } = useI18n();
  const { tax, label } = useTaxonomy();
  const qc = useQueryClient();
  const [f, setF] = useState({ category: "", q: "", has_time_limit: false });
  const q = useQuery({ queryKey: ["clauses", pid, f], queryFn: () => api.get<any[]>(`/projects/${pid}/clauses`, { category: f.category, q: f.q, has_time_limit: f.has_time_limit || undefined }) });
  const summary = useQuery({ queryKey: ["clause-summary", pid], queryFn: () => api.get<any>(`/projects/${pid}/clauses/summary`) });
  const verify = useMutation({ mutationFn: ({ id, status }: { id: string; status: string }) => api.post(`/clauses/${id}/verify`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clauses", pid] }) });
  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <Card>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="relative"><Search className="absolute start-3 top-2.5 h-4 w-4 text-slate-400" /><input className="input ps-9" placeholder={t("search")} value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} /></div>
            <select className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}><option value="">{t("all")} — {t("category")}</option>
              {tax && Object.keys(tax.clause_categories).map((c) => <option key={c} value={c}>{label("clause_categories", c)}</option>)}</select>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.has_time_limit} onChange={(e) => setF({ ...f, has_time_limit: e.target.checked })} />{t("with_time_limits")}</label>
          </div>
        </Card>
        {q.isLoading && <Spinner />}
        {q.data?.length === 0 && <Empty>{t("none")}</Empty>}
        {q.data?.map((c) => <ClauseCard key={c.id} c={c} onVerify={(status) => verify.mutate({ id: c.id, status })} />)}
      </div>
      <div className="space-y-4">
        <AskContract pid={pid} />
        {summary.data && (
          <Card title={t("time_limits")} subtitle={`${summary.data.verified}/${summary.data.total} ${t("verified")}`}>
            <ul className="space-y-2 text-sm">{summary.data.time_limits.map((tl: any, i: number) => (
              <li key={i} className="flex items-center justify-between gap-2"><span className="truncate">{tl.clause_number} · {tl.title}</span>
                <Badge tone={tl.time_bar ? "red" : "amber"}>{tl.stated}</Badge></li>))}</ul>
          </Card>)}
        {summary.data && <Card title={t("category")}><ul className="space-y-1.5 text-sm">{summary.data.by_category.map((c: any) => (
          <li key={c.category} className="flex justify-between"><button className="text-brand-600" onClick={() => setF({ ...f, category: c.category })}>{label("clause_categories", c.category)}</button><span className="num">{c.count}</span></li>))}</ul></Card>}
      </div>
    </div>
  );
}

function AskContract({ pid }: { pid: string }) {
  const { t, lang } = useI18n();
  const [question, setQuestion] = useState("");
  const m = useMutation({ mutationFn: () => api.post<any>(`/projects/${pid}/ask`, { question, language: lang }) });
  return (
    <Card title={<span className="flex items-center gap-2"><MessageSquareText className="h-4 w-4" />{t("ask_contract")}</span>}>
      <form onSubmit={(e) => { e.preventDefault(); if (question.trim().length > 2) m.mutate(); }} className="flex gap-2">
        <input className="input" placeholder={t("ask_placeholder")} value={question} onChange={(e) => setQuestion(e.target.value)} />
        <Button type="submit" loading={m.isPending}>{t("search")}</Button>
      </form>
      {m.data && (
        <div className="mt-3 space-y-2 text-sm">
          {m.data.mode === "llm" ? <Alert tone="ok">{m.data.answer.answer}<div className="mt-1 text-xs">[{m.data.answer.citation_ids.join(", ")}]</div></Alert>
            : <p className="text-xs text-slate-500">{t("ask_extractive")}</p>}
          {m.data.passages?.slice(0, 4).map((p: any) => (
            <div key={p.id} className="rounded border border-slate-200 p-2"><div className="text-xs font-semibold text-navy-900">[{p.id}] {p.clause_number} {p.title} · {t("page")} {p.page}</div>
              <p className="mt-1 line-clamp-4 text-xs text-slate-600">{p.text}</p></div>))}
        </div>)}
    </Card>
  );
}

// ------------------------------------------------------------------ events

function Events({ pid }: { pid: string }) {
  const { t, lang } = useI18n();
  const { tax, label } = useTaxonomy();
  const { can } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["events", pid], queryFn: () => api.get<any[]>(`/projects/${pid}/events`) });
  const docs = useQuery({ queryKey: ["docs", pid], queryFn: () => api.get<any[]>(`/projects/${pid}/documents`), enabled: open });
  const [f, setF] = useState<any>({ title: "", description: "", event_date: "", awareness_date: "", category: "", responsible_party: "", est_cost_impact: "", est_time_impact_days: "", document_ids: [] });
  const [suggest, setSuggest] = useState<any>(null);
  const create = useMutation({ mutationFn: () => api.post<any>(`/projects/${pid}/events`, Object.fromEntries(Object.entries(f).filter(([, v]) => v !== "" && !(Array.isArray(v) && !v.length)))),
    onSuccess: (ev) => { qc.invalidateQueries({ queryKey: ["events", pid] }); setOpen(false); nav(`/events/${ev.id}`); } });
  const runAll = useMutation({ mutationFn: () => api.post(`/projects/${pid}/discover`), onSuccess: () => { qc.invalidateQueries(); nav(`/projects/${pid}/entitlements`); } });
  const classify = async () => { if ((f.title + f.description).length > 5) setSuggest(await api.post("/events/classify", { text: `${f.title}. ${f.description}` })); };
  return (
    <div>
      <div className="mb-4 flex flex-wrap justify-end gap-2">
        {can("entitlement.run") && <Button variant="gold" icon={<Sparkles className="h-4 w-4" />} loading={runAll.isPending} onClick={() => runAll.mutate()}>{t("run_all")}</Button>}
        {can("event.write") && <Button icon={<Plus className="h-4 w-4" />} onClick={() => setOpen(true)}>{t("new_event")}</Button>}
      </div>
      <Card title={t("event_register")}>
        {q.data?.length === 0 ? <Empty>{t("none")}</Empty> : (
          <table className="w-full"><thead><tr><th className="th">Ref</th><th className="th">{t("title")}</th><th className="th">{t("category")}</th><th className="th">{t("event_date")}</th><th className="th">{t("est_cost")}</th><th className="th">{t("linked_docs")}</th><th className="th">{t("status")}</th></tr></thead>
            <tbody>{q.data?.map((e) => (
              <tr key={e.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="td font-medium"><Link className="text-brand-600" to={`/events/${e.id}`}>{e.ref}</Link></td>
                <td className="td">{e.title}</td>
                <td className="td"><Badge tone="blue">{label("event_categories", e.category)}</Badge>{e.category_source === "ai" && <span className="ms-1 text-xs text-slate-400">{t("ai_suggest")}</span>}</td>
                <td className="td num text-xs">{fmtDate(e.event_date, lang)}</td><td className="td num text-xs">{e.est_cost_impact ? fmtMoney(e.est_cost_impact, lang) : "—"}</td>
                <td className="td num">{e.document_count}</td><td className="td"><StatusBadge status={e.status} /></td>
              </tr>))}</tbody></table>)}
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title={t("new_event")} wide>
        <form className="grid gap-3 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div className="md:col-span-2"><Field label={t("title")}><input className="input" required minLength={3} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} onBlur={classify} /></Field></div>
          <div className="md:col-span-2"><Field label={t("description")}><textarea className="input min-h-24" required minLength={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} onBlur={classify} /></Field></div>
          <Field label={t("event_date")}><input type="date" className="input" required value={f.event_date} onChange={(e) => setF({ ...f, event_date: e.target.value })} /></Field>
          <Field label={t("awareness_date")}><input type="date" className="input" value={f.awareness_date} onChange={(e) => setF({ ...f, awareness_date: e.target.value })} /></Field>
          <Field label={t("category")} hint={suggest && <>{t("ai_suggest")}: <b>{label("event_categories", suggest.category)}</b> ({Math.round(suggest.confidence * 100)}%) <button type="button" className="text-brand-600" onClick={() => setF({ ...f, category: suggest.category })}>✓</button></>}>
            <select className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}><option value="">{t("auto_detect")}</option>
              {tax && Object.keys(tax.event_categories).map((c) => <option key={c} value={c}>{label("event_categories", c)}</option>)}</select></Field>
          <Field label={t("responsible")}><select className="input" value={f.responsible_party} onChange={(e) => setF({ ...f, responsible_party: e.target.value })}><option value="">—</option>
            {["employer", "engineer", "contractor", "subcontractor", "third_party", "neutral"].map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label={t("est_cost")}><input type="number" min="0" className="input" value={f.est_cost_impact} onChange={(e) => setF({ ...f, est_cost_impact: e.target.value })} /></Field>
          <Field label={t("est_time")}><input type="number" min="0" className="input" value={f.est_time_impact_days} onChange={(e) => setF({ ...f, est_time_impact_days: e.target.value })} /></Field>
          <div className="md:col-span-2"><Field label={t("linked_docs")}>
            <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border p-2">{docs.data?.filter((d) => d.doc_type !== "contract").map((d) => (
              <label key={d.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.document_ids.includes(d.id)}
                onChange={(e) => setF({ ...f, document_ids: e.target.checked ? [...f.document_ids, d.id] : f.document_ids.filter((x: string) => x !== d.id) })} />{d.title}</label>))}</div></Field></div>
          <div className="md:col-span-2">{create.error && <Alert tone="error">{(create.error as Error).message}</Alert>}</div>
          <div className="md:col-span-2"><Button type="submit" loading={create.isPending}>{t("create")}</Button></div>
        </form>
      </Modal>
    </div>
  );
}

// ------------------------------------------------------------------ entitlements

function Entitlements({ pid }: { pid: string }) {
  const { t, lang } = useI18n();
  const { label } = useTaxonomy();
  const [status, setStatus] = useState("");
  const q = useQuery({ queryKey: ["ents", pid, status], queryFn: () => api.get<any[]>(`/projects/${pid}/entitlements`, { status }) });
  return (
    <Card title={t("discovery")} actions={<select className="input w-56" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">{t("all")}</option>
      {["potential", "insufficient_evidence", "requires_expert_verification", "substantiated", "rejected"].map((s) => <option key={s} value={s}>{label("entitlement_status", s)}</option>)}</select>}>
      {q.data?.length === 0 ? <Empty>{t("none")}</Empty> : (
        <div className="overflow-x-auto"><table className="w-full">
          <thead><tr><th className="th">Ref</th><th className="th">{t("type")}</th><th className="th">{t("status")}</th><th className="th">{t("financial_impact")}</th><th className="th">{t("notice_req")}</th><th className="th">{t("risk")}</th><th className="th">{t("confidence")}</th><th className="th">{t("review")}</th></tr></thead>
          <tbody>{q.data?.map((e) => (
            <tr key={e.id} className="border-t border-slate-100 hover:bg-slate-50">
              <td className="td"><Link className="font-semibold text-brand-600" to={`/entitlements/${e.id}`}>{e.ref}</Link><div className="text-xs text-slate-400">{e.event_ref}</div></td>
              <td className="td text-sm">{label("entitlement_types", e.entitlement_type)}</td>
              <td className="td"><StatusBadge status={e.status} label={label("entitlement_status", e.status)} /></td>
              <td className="td num">{e.financial_impact ? fmtMoney(e.financial_impact, lang) : <span className="text-xs text-slate-400">{e.financial_basis === "not_applicable" ? "—" : t("not_quantified")}</span>}
                {e.financial_basis === "event_estimate" && <div className="text-[11px] text-amber-700">{lang === "ar" ? "تقدير غير مُتحقق" : "unverified estimate"}</div>}</td>
              <td className="td text-xs">{e.notice_due ? <span className={clsx("num", e.notice_status === "overdue" && "font-semibold text-red-700")}>{fmtDate(e.notice_due, lang)} · {e.notice_status}</span> : "—"}</td>
              <td className="td"><RiskBadge level={e.risk_level} /></td><td className="td"><ConfidenceBar value={e.confidence} /></td>
              <td className="td"><StatusBadge status={e.review_status} /></td>
            </tr>))}</tbody></table></div>)}
    </Card>
  );
}

function ClaimsTab({ pid }: { pid: string }) {
  const { t, lang } = useI18n();
  const { label } = useTaxonomy();
  const q = useQuery({ queryKey: ["claims", pid], queryFn: () => api.get<any[]>(`/projects/${pid}/claims`) });
  return (
    <Card title={t("claim_mgmt")}>
      {q.data?.length === 0 ? <Empty>{lang === "ar" ? "لا توجد مطالبات بعد — ابدأ من صفحة الاستحقاق." : "No claims yet — prepare one from an entitlement."}</Empty> : (
        <table className="w-full"><thead><tr><th className="th">Ref</th><th className="th">{t("title")}</th><th className="th">{t("stage")}</th><th className="th">{t("claimed")}</th><th className="th">{t("approved")}</th><th className="th">{t("collected")}</th></tr></thead>
          <tbody>{q.data?.map((c) => (
            <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50"><td className="td"><Link className="font-semibold text-brand-600" to={`/claims/${c.id}`}>{c.ref}</Link></td>
              <td className="td">{c.title}</td><td className="td"><Badge tone="navy">{label("claim_stages", c.stage)}</Badge></td>
              <td className="td num">{fmtMoney(c.claimed_amount, lang)}</td><td className="td num">{fmtMoney(c.approved_amount, lang)}</td><td className="td num">{fmtMoney(c.collected_amount, lang)}</td></tr>))}</tbody></table>)}
    </Card>
  );
}

export function DeadlinesTab({ pid }: { pid: string }) {
  const { t, lang } = useI18n();
  const q = useQuery({ queryKey: ["deadlines", pid], queryFn: () => api.get<any[]>(`/projects/${pid}/deadlines`) });
  return (
    <Card title={t("deadlines")}>
      {q.data?.length === 0 ? <Empty>{t("none")}</Empty> : <DeadlineTable rows={q.data || []} lang={lang} />}
    </Card>
  );
}

export function DeadlineTable({ rows, lang }: { rows: any[]; lang: "en" | "ar" }) {
  const { t } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const m = useMutation({ mutationFn: (id: string) => api.patch(`/deadlines/${id}`, { status: "completed" }), onSuccess: () => qc.invalidateQueries() });
  return (
    <div className="overflow-x-auto"><table className="w-full">
      <thead><tr><th className="th">{t("title")}</th><th className="th">{t("type")}</th><th className="th">{t("due")}</th><th className="th">{t("certainty")}</th><th className="th">{t("calc")}</th><th className="th">{t("status")}</th><th className="th" /></tr></thead>
      <tbody>{rows.map((d) => (
        <tr key={d.id} className={clsx("border-t border-slate-100 align-top", d.overdue && "bg-red-50/50")}>
          <td className="td"><Link className="text-brand-600" to={d.entitlement_id ? `/entitlements/${d.entitlement_id}` : `/projects/${d.project_id}`}>{d.title}</Link>
            <div className="text-xs text-slate-400">{lang === "ar" ? d.project_name_ar || d.project_name : d.project_name}</div></td>
          <td className="td text-xs">{d.deadline_type}</td>
          <td className="td num text-sm">{d.due_date ? <><span className={clsx(d.overdue && "font-semibold text-red-700")}>{fmtDate(d.due_date, lang)}</span>
            {d.days_left !== null && d.status === "open" && <div className="text-xs text-slate-500">{d.overdue ? t("overdue") : `${fmtNum(d.days_left, lang)} ${t("days_left")}`}</div>}</> : <span className="text-amber-700">{t("undetermined")}</span>}</td>
          <td className="td"><Badge tone={d.certainty === "determined" || d.certainty === "manual" ? "green" : d.certainty === "ambiguous" ? "violet" : "amber"}>{d.certainty}</Badge>
            {d.uncertainty_notes?.map((n: any) => <div key={n.code} className="mt-1 max-w-xs text-[11px] text-slate-500">• {lang === "ar" ? n.ar : n.en}</div>)}</td>
          <td className="td num max-w-[220px] text-[11px] text-slate-500">{d.calculation?.formula || "—"}</td>
          <td className="td"><StatusBadge status={d.status} /></td>
          <td className="td">{d.status === "open" && can("deadline.manage") && <Button size="sm" variant="secondary" onClick={() => m.mutate(d.id)}>{t("complete")}</Button>}</td>
        </tr>))}</tbody></table></div>
  );
}
