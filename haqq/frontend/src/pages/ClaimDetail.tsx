import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, Download, FileOutput } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Alert, Badge, Button, Card, DemoBadge, Field, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, fmtMoney, useI18n } from "../lib/i18n";
import { useTaxonomy } from "../lib/taxonomy";

const FLOW = ["detected", "initial_review", "evidence_collection", "contractual_verification", "financial_valuation", "technical_review", "legal_review",
  "management_approval", "submitted", "employer_response", "negotiation", "approved", "collected", "closed"];

export default function ClaimDetail() {
  const { id = "" } = useParams();
  const { t, lang, pick } = useI18n();
  const { label } = useTaxonomy();
  const { can } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["claim", id], queryFn: () => api.get<any>(`/claims/${id}`) });
  const [tr, setTr] = useState({ to_stage: "", comment: "", approved_amount: "", collected_amount: "" });
  const [gen, setGen] = useState({ kind: "package", fmt: "docx", language: lang });
  const move = useMutation({ mutationFn: () => api.post(`/claims/${id}/transition`, Object.fromEntries(Object.entries(tr).filter(([, v]) => v !== ""))),
    onSuccess: () => { setTr({ to_stage: "", comment: "", approved_amount: "", collected_amount: "" }); qc.invalidateQueries({ queryKey: ["claim", id] }); } });
  const generate = useMutation({ mutationFn: () => api.post(`/claims/${id}/documents`, { ...gen, fmt: gen.kind === "worksheet" ? "xlsx" : gen.fmt }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["claim", id] }) });
  if (q.isLoading) return <Spinner />;
  const c = q.data;
  if (!c) return <Alert tone="error">{t("error")}</Alert>;
  const idx = FLOW.indexOf(c.stage);
  const ent = c.entitlement;
  return (
    <div>
      <PageHeader crumbs={<Link to={`/projects/${c.project_id}/claims`} className="hover:underline">{t("claim_mgmt")}</Link>}
        title={<span className="flex items-center gap-2">{c.ref} · {c.title} {c.is_demo && <DemoBadge />}</span>}
        subtitle={ent && <Link to={`/entitlements/${ent.id}`} className="text-brand-600">{ent.ref} · {pick(ent.type_label)}</Link>} />
      <Card>
        <ol className="flex gap-1 overflow-x-auto pb-1">{FLOW.map((s, i) => (
          <li key={s} className={clsx("flex min-w-[96px] flex-1 flex-col items-center gap-1 rounded-md px-1 py-2 text-center text-[11px]",
            c.stage === "rejected" && s === "approved" ? "bg-red-50 text-red-700" : i < idx ? "bg-emerald-50 text-emerald-800" : i === idx ? "bg-navy-800 text-white" : "bg-slate-50 text-slate-500")}>
            <span className="grid h-5 w-5 place-items-center rounded-full bg-white/80 text-[10px] font-bold text-navy-900">{i < idx ? <Check className="h-3 w-3" /> : i + 1}</span>
            {label("claim_stages", s)}</li>))}</ol>
        {c.stage === "rejected" && <div className="mt-2"><Alert tone="error">{label("claim_stages", "rejected")}</Alert></div>}
      </Card>
      <div className="mt-5 grid gap-5 xl:grid-cols-3">
        <div className="space-y-5 xl:col-span-2">
          <div className="grid grid-cols-3 gap-3">
            {[["claimed", c.claimed_amount], ["approved", c.approved_amount], ["collected", c.collected_amount]].map(([k, v]) => (
              <div key={k} className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-xs text-slate-500">{t(k)}</div><div className="num mt-1 text-xl font-semibold text-navy-900">{fmtMoney(v, lang)}</div></div>))}
          </div>
          {ent && ent.evidence_missing?.length > 0 && <Alert tone="warn" title={t("evidence_missing")}>{ent.evidence_missing.map((m: any) => <div key={m.code}>• {pick(m)}{m.critical ? ` (${t("critical")})` : ""}</div>)}</Alert>}
          <Card title={<span className="flex items-center gap-2"><FileOutput className="h-4 w-4" />{t("generated_docs")}</span>}>
            {can("claim.generate") && (
              <div className="mb-4 flex flex-wrap items-end gap-2">
                <Field label={t("type")}><select className="input" value={gen.kind} onChange={(e) => setGen({ ...gen, kind: e.target.value })}>
                  <option value="notice">{t("kind_notice")}</option><option value="package">{t("kind_package")}</option><option value="worksheet">{t("kind_worksheet")}</option></select></Field>
                {gen.kind !== "worksheet" && <Field label="Format"><select className="input" value={gen.fmt} onChange={(e) => setGen({ ...gen, fmt: e.target.value })}><option value="docx">Word (DOCX)</option><option value="pdf">PDF</option></select></Field>}
                <Field label={t("language")}><select className="input" value={gen.language} onChange={(e) => setGen({ ...gen, language: e.target.value as "en" | "ar" })}><option value="ar">العربية</option><option value="en">English</option></select></Field>
                <Button loading={generate.isPending} onClick={() => generate.mutate()} data-testid="generate">{t("generate")}</Button>
              </div>)}
            {generate.error && <Alert tone="error">{(generate.error as Error).message}</Alert>}
            {c.documents.length === 0 ? <p className="text-sm text-slate-500">{t("none")}</p> : (
              <ul className="divide-y divide-slate-100">{c.documents.map((d: any) => (
                <li key={d.id} className="flex items-center justify-between gap-2 py-2.5 text-sm">
                  <div><div className="font-medium">{d.filename}</div><div className="text-xs text-slate-500">{d.kind} · {d.language} · v{d.version} · {fmtDate(d.created_at, lang)} · {d.by}</div></div>
                  <Button size="sm" variant="secondary" icon={<Download className="h-3.5 w-3.5" />} onClick={() => api.download(`/claim-documents/${d.id}/download`, d.filename)}>{t("download")}</Button>
                </li>))}</ul>)}
            <p className="mt-3 text-xs text-slate-500">{lang === "ar" ? "لا يقوم حقّك بإرسال أي مطالبة إلى صاحب العمل. يتم تسجيل التقديم فقط بعد إرسال الشركة لها عبر قنواتها." : "HAQQ never sends a claim to the employer. 'Submitted' only records that your company submitted it through its own channels."}</p>
          </Card>
        </div>
        <div className="space-y-5">
          <Card title={t("move_to")}>
            {c.next_stages.length === 0 ? <p className="text-sm text-slate-500">{t("none")}</p> : (<div className="space-y-3">
              <div className="flex flex-wrap gap-2">{c.next_stages.map((s: any) => (
                <button key={s.stage} disabled={!s.allowed} title={s.allowed ? "" : t("not_allowed")} onClick={() => setTr({ ...tr, to_stage: s.stage })}
                  className={clsx("rounded-lg border px-2.5 py-1.5 text-xs", tr.to_stage === s.stage ? "border-navy-800 bg-navy-800 text-white" : "border-slate-300", !s.allowed && "cursor-not-allowed opacity-40")}>{pick(s)}</button>))}</div>
              {tr.to_stage === "approved" && <Field label={t("approved_amount")}><input className="input" type="number" min="0" value={tr.approved_amount} onChange={(e) => setTr({ ...tr, approved_amount: e.target.value })} /></Field>}
              {tr.to_stage === "collected" && <Field label={t("collected_amount")}><input className="input" type="number" min="0" value={tr.collected_amount} onChange={(e) => setTr({ ...tr, collected_amount: e.target.value })} /></Field>}
              <Field label={t("comment")}><textarea className="input" value={tr.comment} onChange={(e) => setTr({ ...tr, comment: e.target.value })} /></Field>
              <Button disabled={!tr.to_stage} loading={move.isPending} onClick={() => move.mutate()} data-testid="transition">{t("move_to")}</Button>
              {move.error && <Alert tone="error">{(move.error as Error).message}</Alert>}
            </div>)}
          </Card>
          <Card title={t("history")}>
            <ol className="space-y-2.5 text-sm">{c.history.slice().reverse().map((h: any, i: number) => (
              <li key={i} className="border-s-2 border-navy-700 ps-3"><div className="font-medium">{label("claim_stages", h.to)}</div>
                <div className="text-xs text-slate-500">{h.by} · {fmtDate(h.at, lang)}</div>{h.comment && <div className="text-xs text-slate-600">{h.comment}</div>}</li>))}</ol>
          </Card>
          {ent?.notice?.due_date && <Card title={t("notice_req")}><Badge tone={ent.notice.status === "overdue" ? "red" : "amber"}>{fmtDate(ent.notice.due_date, lang)} · {ent.notice.status}</Badge></Card>}
        </div>
      </div>
    </div>
  );
}
