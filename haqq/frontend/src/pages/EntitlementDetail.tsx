import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, BookOpenText, CalendarClock, CheckCircle2, CircleSlash, FileSearch, Gavel, Lightbulb, Scale, Sparkles, XCircle } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Alert, Badge, Button, Card, DemoBadge, Field, PageHeader, RiskBadge, Spinner, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, fmtMoney, fmtNum, fmtPct, useI18n } from "../lib/i18n";
import { useTaxonomy } from "../lib/taxonomy";

function Cite({ c }: { c: any }) {
  const { t } = useI18n();
  if (!c) return null;
  return (
    <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-2.5 text-xs">
      <div className="mb-1 flex flex-wrap items-center gap-1.5 font-medium text-navy-900">
        <BookOpenText className="h-3.5 w-3.5" />
        {c.type === "clause" ? `${t("clause")} ${c.clause_number}` : c.doc_type}
        <Link to={`/documents/${c.document_id}`} className="text-brand-600 hover:underline">{c.document_title}</Link>
        <span className="text-slate-500">· {t("page")} {c.page}</span>
        {c.verification_status && c.verification_status !== "verified" && <Badge tone="slate">{t("unverified")}</Badge>}
      </div>
      {c.quote && <p dir="auto" className="quote rounded px-2 py-1.5 text-slate-700">“{c.quote}”</p>}
    </div>
  );
}

const KIND_ICON: Record<string, typeof Lightbulb> = { event: CalendarClock, clause: Scale, evidence: FileSearch, gap: AlertTriangle, deadline: CalendarClock, exclusion: CircleSlash };

export default function EntitlementDetail() {
  const { id = "" } = useParams();
  const { t, lang, pick } = useI18n();
  const { label } = useTaxonomy();
  const { can } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["ent", id], queryFn: () => api.get<any>(`/entitlements/${id}`) });
  const claims = useQuery({ queryKey: ["claims", q.data?.project_id], enabled: !!q.data, queryFn: () => api.get<any[]>(`/projects/${q.data.project_id}/claims`) });
  const [comment, setComment] = useState("");
  const review = useMutation({ mutationFn: (decision: string) => api.post(`/entitlements/${id}/review`, { decision, comment }),
    onSuccess: () => { setComment(""); qc.invalidateQueries({ queryKey: ["ent", id] }); } });
  const rerun = useMutation({ mutationFn: () => api.post(`/events/${q.data.event_id}/discover`), onSuccess: () => qc.invalidateQueries({ queryKey: ["ent", id] }) });
  const narrative = useMutation({ mutationFn: () => api.post<any>(`/entitlements/${id}/narrative?language=${lang}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["ent", id] }) });
  const mkClaim = useMutation({ mutationFn: () => api.post<any>(`/projects/${q.data.project_id}/claims`, { entitlement_id: id }), onSuccess: (c) => nav(`/claims/${c.id}`) });
  if (q.isLoading) return <Spinner />;
  const e = q.data;
  if (!e) return <Alert tone="error">{t("error")}</Alert>;
  const n = e.notice?.notice || {};
  const dc = e.notice?.detailed_claim;
  const primary = e.clauses.find((c: any) => c.primary);
  const existingClaim = claims.data?.find((c) => c.entitlement_id === id);
  const narr = e.narrative?.content;

  return (
    <div>
      <PageHeader crumbs={<><Link to={`/projects/${e.project_id}/entitlements`} className="hover:underline">{t("discovery")}</Link> · <Link to={`/events/${e.event.id}`} className="hover:underline">{e.event.ref}</Link></>}
        title={<span className="flex flex-wrap items-center gap-2">{e.ref} · {label("entitlement_types", e.entitlement_type)} {e.is_demo && <DemoBadge />}</span>}
        subtitle={e.event.title}
        actions={<>
          {can("entitlement.run") && <Button variant="secondary" loading={rerun.isPending} onClick={() => rerun.mutate()}>{t("reprocess")}</Button>}
          {(can("valuation.write") || can("valuation.verify")) && label("entitlement_types", e.entitlement_type) && e.entitlement_type !== "extension_of_time" &&
            <Link to={`/entitlements/${id}/valuation`}><Button variant="secondary">{t("open_valuation")}</Button></Link>}
          {existingClaim ? <Link to={`/claims/${existingClaim.id}`}><Button>{existingClaim.ref}</Button></Link>
            : can("claim.write") && e.status !== "rejected" && <Button variant="gold" loading={mkClaim.isPending} onClick={() => mkClaim.mutate()} data-testid="create-claim">{t("create_claim")}</Button>}
        </>} />
      {mkClaim.error && <div className="mb-4"><Alert tone="error">{(mkClaim.error as Error).message}</Alert></div>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-xs text-slate-500">{t("status")}</div><div className="mt-2"><StatusBadge status={e.status} label={label("entitlement_status", e.status)} /></div></div>
        <div className="rounded-xl border border-gold-400 bg-white p-4"><div className="text-xs text-slate-500">{t("financial_impact")}</div>
          <div className="num mt-1 text-xl font-semibold text-navy-900" data-testid="fin-impact">{e.financial_impact ? fmtMoney(e.financial_impact, lang) : e.financial_basis === "not_applicable" ? "—" : t("not_quantified")}</div>
          <div className="text-[11px] text-slate-500">{e.financial_basis.replace(/_/g, " ")}</div></div>
        <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-xs text-slate-500">{t("time_impact")}</div><div className="num mt-1 text-xl font-semibold">{e.time_impact_days ? `${fmtNum(e.time_impact_days, lang)} ${t("days")}` : "—"}</div></div>
        <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-xs text-slate-500">{t("risk")}</div><div className="mt-2"><RiskBadge level={e.risk_level} /></div></div>
        <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-xs text-slate-500">{t("confidence")}</div><div className="num mt-1 text-xl font-semibold">{fmtPct(e.confidence, lang)}</div></div>
      </div>
      <p className="mt-2 text-xs text-slate-500">{t("disclaimer")}</p>

      <div className="mt-5 grid gap-5 xl:grid-cols-3">
        <div className="space-y-5 xl:col-span-2">
          <Card title={<span className="flex items-center gap-2"><Lightbulb className="h-4 w-4 text-gold-500" />{t("why")}</span>}>
            <ol className="space-y-3">{e.explanation.map((x: any, i: number) => { const I = KIND_ICON[x.kind] || Lightbulb; return (
              <li key={i} className={clsx("rounded-lg border p-3", x.kind === "gap" ? "border-amber-200 bg-amber-50/50" : x.kind === "exclusion" ? "border-violet-200 bg-violet-50/40" : "border-slate-200")}>
                <div className="flex gap-2 text-sm text-slate-800"><I className={clsx("mt-0.5 h-4 w-4 shrink-0", x.kind === "gap" ? "text-amber-600" : "text-navy-700")} /><span>{pick(x)}</span></div>
                <Cite c={x.citation} />
              </li>); })}</ol>
          </Card>

          {primary && (
            <Card title={t("applicable_clause")} subtitle={`${primary.document_title} · ${t("page")} ${primary.page_start}`}>
              <div className="font-semibold text-navy-900">{primary.clause_number} — {primary.title}</div>
              <p dir="auto" className="quote mt-2 whitespace-pre-line rounded-md px-3 py-2 text-sm text-slate-700">{primary.text}</p>
              {e.conditions.length > 0 && <><div className="label mt-3">{t("conditions")}</div><ul className="list-disc space-y-1 ps-5 text-sm">{e.conditions.map((c: any, i: number) => <li key={i}>{c.text}</li>)}</ul></>}
              {e.clauses.length > 1 && <div className="mt-3 flex flex-wrap gap-1.5 text-xs"><span className="text-slate-500">{t("related_clauses")}:</span>
                {e.clauses.filter((c: any) => !c.primary).map((c: any) => <Badge key={c.id}>{c.clause_number} {c.title.slice(0, 30)}</Badge>)}</div>}
            </Card>)}

          <div className="grid gap-5 md:grid-cols-2">
            <Card title={<span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-600" />{t("evidence_available")}</span>}>
              {e.evidence_available.length === 0 ? <p className="text-sm text-slate-500">{t("none")}</p> :
                <ul className="space-y-3">{e.evidence_available.map((a: any) => <li key={a.code} className="text-sm"><div className="font-medium">{pick(a)}</div>
                  {a.sources.map((s: any) => <Link key={s.document_id} to={`/documents/${s.document_id}`} className="block text-xs text-brand-600">↳ {s.document_title} · {t("page")} {s.page}</Link>)}</li>)}</ul>}
            </Card>
            <Card title={<span className="flex items-center gap-2"><XCircle className="h-4 w-4 text-amber-600" />{t("evidence_missing")}</span>}
              subtitle={`${t("k_evidence_completeness")}: ${fmtPct(e.evidence_completeness, lang)}`}>
              {e.evidence_missing.length === 0 ? <p className="text-sm text-emerald-700">✓</p> :
                <ul className="space-y-2">{e.evidence_missing.map((m: any) => <li key={m.code} className="flex items-start gap-2 text-sm">
                  {m.critical ? <Badge tone="red">{t("critical")}</Badge> : <Badge>—</Badge>}<span>{pick(m)}</span></li>)}</ul>}
            </Card>
          </div>

          {(e.notice?.contradictions?.length > 0 || e.exclusions.length > 0) && (
            <Card title={t("contradictions")}>
              {e.notice.contradictions?.map((c: any, i: number) => <div key={i} className="mb-2"><Alert tone="warn">{pick(c)}</Alert><Cite c={c.citation} /></div>)}
              {e.exclusions.map((x: any, i: number) => <div key={i} className="mb-2"><Alert tone={x.blocking ? "error" : "info"} title={`${t("exclusions")} — ${x.clause_number}`}>
                {x.note ? pick(x.note) : x.text}</Alert></div>)}
            </Card>)}

          <Card title={<span className="flex items-center gap-2"><Sparkles className="h-4 w-4" />{t("narrative")}</span>}
            actions={can("entitlement.run") && <Button size="sm" variant="secondary" loading={narrative.isPending} onClick={() => narrative.mutate()}>{t("generate_narrative")}</Button>}>
            {narrative.data && narrative.data.available === false && <Alert tone="info">{lang === "ar" ? "النموذج اللغوي غير متاح: " : "AI narrative unavailable: "}{narrative.data.reason}</Alert>}
            {narr ? (<div className="space-y-2 text-sm">
              <p className="font-medium">{narr.summary}</p><p className="text-slate-600">{narr.why_it_matters}</p>
              <ul className="list-disc ps-5">{narr.facts.map((f: any, i: number) => <li key={i}>{f.statement} <span className="text-xs text-brand-600">[{f.citation_ids.join(", ")}]</span></li>)}</ul>
              {narr.ambiguities.length > 0 && <div><b>{lang === "ar" ? "غموض:" : "Ambiguities:"}</b> {narr.ambiguities.join(" · ")}</div>}
              <div className="text-[11px] text-slate-400">{e.narrative.model} · prompt {e.narrative.prompt_version} · {lang === "ar" ? "يتطلب تحققًا بشريًا" : "requires human verification"}</div>
            </div>) : !narrative.data && <p className="text-xs text-slate-500">{lang === "ar" ? "النتيجة أعلاه من المحرك الحتمي. السرد الآلي اختياري ويخضع لسياسة البيانات." : "The finding above comes from the deterministic engine. The AI narrative is optional and subject to your data policy."}</p>}
          </Card>
        </div>

        <div className="space-y-5">
          <Card title={<span className="flex items-center gap-2"><CalendarClock className="h-4 w-4" />{t("notice_req")}</span>}>
            {n.required ? (<div className="space-y-2 text-sm">
              <div className="flex items-baseline justify-between"><span className="text-slate-500">{t("due")}</span>
                <span className={clsx("num text-lg font-semibold", n.status === "overdue" ? "text-red-700" : n.days_remaining !== null && n.days_remaining <= 7 && n.status === "due" ? "text-amber-700" : "text-navy-900")} data-testid="notice-due">{fmtDate(n.due_date, lang)}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">{t("status")}</span><Badge tone={n.status === "overdue" || n.status === "given_late" ? "red" : n.status === "due" ? "amber" : "green"}>{n.status}{n.status === "due" && n.days_remaining !== null ? ` · ${n.days_remaining} ${t("days")}` : ""}</Badge></div>
              <div className="flex justify-between"><span className="text-slate-500">{t("certainty")}</span><Badge tone={n.certainty === "determined" ? "green" : n.certainty === "ambiguous" ? "violet" : "amber"}>{n.certainty}</Badge></div>
              <div className="text-xs text-slate-600">{n.stated} ({n.day_type}){n.time_bar && <Badge tone="red" className="ms-1">{t("time_bar")}</Badge>}</div>
              <div className="num rounded bg-slate-50 p-2 text-[11px] text-slate-600">{n.calculation?.formula}</div>
              {n.notes?.map((x: any) => <div key={x.code} className="text-xs text-amber-800">⚠ {pick(x)}</div>)}
              <Cite c={n.clause} />
              {n.notice_document && <div className="text-xs text-emerald-700">✓ {n.notice_document.document_title} ({fmtDate(n.notice_document.doc_date, lang)})</div>}
            </div>) : <Alert tone="warn">{n.notes?.map((x: any) => pick(x))}</Alert>}
            {dc?.required && <div className="mt-3 border-t pt-3 text-sm"><div className="text-slate-500">{lang === "ar" ? "المطالبة التفصيلية" : "Detailed claim"}</div>
              <div className="num font-semibold">{fmtDate(dc.due_date, lang)} <span className="text-xs font-normal text-slate-500">({dc.stated}, {dc.certainty})</span></div></div>}
          </Card>

          <Card title={t("recommended")}>
            <ol className="space-y-2 text-sm">{e.recommended_actions.map((a: any, i: number) =>
              <li key={i} className="flex gap-2"><span className={clsx("grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] font-bold", a.priority === 1 ? "bg-red-600 text-white" : "bg-slate-200 text-slate-700")}>{i + 1}</span><span>{pick(a)}</span></li>)}</ol>
          </Card>

          <Card title={t("risk")}>
            {e.risk_factors.length === 0 ? <p className="text-sm text-slate-500">{t("none")}</p> :
              <ul className="space-y-1.5 text-sm">{e.risk_factors.map((r: any) => <li key={r.code} className="flex gap-2"><AlertTriangle className={clsx("mt-0.5 h-4 w-4 shrink-0", r.severity === "high" ? "text-red-600" : "text-amber-600")} />{pick(r)}</li>)}</ul>}
          </Card>

          <Card title={t("confidence_breakdown")}>
            <ul className="space-y-1.5 text-sm">{Object.entries(e.confidence_breakdown).map(([k, v]) => (
              <li key={k} className="flex justify-between"><span className="text-slate-600">{t("conf_" + k)}</span><span className="num">{Math.round((v as number) * 100)}%</span></li>))}</ul>
            <p className="mt-2 text-[11px] text-slate-500">0.35·clause + 0.30·evidence + 0.15·classification + 0.10·notice + 0.10·quantification − penalties</p>
          </Card>

          <Card title={t("assumptions")}>
            <ul className="space-y-1.5 text-xs text-slate-600">{e.assumptions.map((a: any, i: number) => <li key={i}>• {pick(a)}</li>)}</ul>
          </Card>

          <Card title={<span className="flex items-center gap-2"><Gavel className="h-4 w-4" />{t("review")}</span>} subtitle={<StatusBadge status={e.review_status} />}>
            {e.review_comment && <p className="mb-3 rounded bg-slate-50 p-2 text-xs">“{e.review_comment}” · {fmtDate(e.reviewed_at, lang)}</p>}
            {can("entitlement.review") ? (<>
              <Field label={t("review_comment")}><textarea className="input min-h-16" value={comment} onChange={(x) => setComment(x.target.value)} data-testid="review-comment" /></Field>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" disabled={comment.length < 3} onClick={() => review.mutate("accepted")}>{t("accept")}</Button>
                <Button size="sm" variant="secondary" disabled={comment.length < 3} onClick={() => review.mutate("needs_info")}>{t("needs_info")}</Button>
                <Button size="sm" variant="gold" disabled={comment.length < 3} onClick={() => review.mutate("substantiated")}>{t("substantiate")}</Button>
                <Button size="sm" variant="danger" disabled={comment.length < 3} onClick={() => review.mutate("rejected")}>{t("reject")}</Button>
              </div>
              {review.error && <Alert tone="error">{(review.error as Error).message}</Alert>}
            </>) : <p className="text-xs text-slate-500">{t("not_allowed")}</p>}
          </Card>
        </div>
      </div>
    </div>
  );
}
