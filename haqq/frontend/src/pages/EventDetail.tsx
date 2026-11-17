import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, Sparkles, Unlink } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Alert, Badge, Button, Card, DemoBadge, Empty, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, fmtMoney, useI18n } from "../lib/i18n";
import { useTaxonomy } from "../lib/taxonomy";

export default function EventDetail() {
  const { id = "" } = useParams();
  const { t, lang } = useI18n();
  const { label } = useTaxonomy();
  const { can } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["event", id], queryFn: () => api.get<any>(`/events/${id}`) });
  const sugg = useQuery({ queryKey: ["event-sugg", id], queryFn: () => api.get<any[]>(`/events/${id}/suggested-documents`) });
  const ents = useQuery({ queryKey: ["event-ents", id, q.data?.project_id], enabled: !!q.data, queryFn: () => api.get<any[]>(`/projects/${q.data.project_id}/entitlements`) });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["event", id] }); qc.invalidateQueries({ queryKey: ["event-sugg", id] }); };
  const link = useMutation({ mutationFn: (doc: string) => api.post(`/events/${id}/documents`, { document_id: doc }), onSuccess: refresh });
  const unlink = useMutation({ mutationFn: (doc: string) => api.del(`/events/${id}/documents/${doc}`), onSuccess: refresh });
  const discover = useMutation({ mutationFn: () => api.post<any[]>(`/events/${id}/discover`), onSuccess: (r) => { qc.invalidateQueries(); if (r[0]) nav(`/entitlements/${r[0].id}`); } });
  if (q.isLoading) return <Spinner />;
  const e = q.data;
  if (!e) return <Alert tone="error">{t("error")}</Alert>;
  const mine = ents.data?.filter((x) => x.event_id === id) || [];
  return (
    <div>
      <PageHeader crumbs={<Link to={`/projects/${e.project_id}/events`} className="hover:underline">{t("event_register")}</Link>}
        title={<span className="flex items-center gap-2">{e.ref} · {e.title} {e.is_demo && <DemoBadge />}</span>}
        actions={can("entitlement.run") && <Button variant="gold" icon={<Sparkles className="h-4 w-4" />} loading={discover.isPending} onClick={() => discover.mutate()} data-testid="discover">{t("run_discovery")}</Button>} />
      <div className="grid gap-5 xl:grid-cols-3">
        <Card title={t("overview")} className="xl:col-span-2">
          <p className="whitespace-pre-line text-sm text-slate-700">{e.description}</p>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <div><dt className="text-xs text-slate-500">{t("category")}</dt><dd><Badge tone="blue">{label("event_categories", e.category)}</Badge>
              {e.category_source === "ai" && <div className="text-[11px] text-slate-400">{t("ai_suggest")} {Math.round((e.suggested_category_confidence || 0) * 100)}%</div>}</dd></div>
            <div><dt className="text-xs text-slate-500">{t("event_date")}</dt><dd className="num">{fmtDate(e.event_date, lang)}</dd></div>
            <div><dt className="text-xs text-slate-500">{t("awareness_date")}</dt><dd className="num">{fmtDate(e.awareness_date, lang)}</dd></div>
            <div><dt className="text-xs text-slate-500">{t("responsible")}</dt><dd>{e.responsible_party || "—"}</dd></div>
            <div><dt className="text-xs text-slate-500">{t("est_cost")}</dt><dd className="num">{e.est_cost_impact ? fmtMoney(e.est_cost_impact, lang) : "—"}</dd></div>
            <div><dt className="text-xs text-slate-500">{t("est_time")}</dt><dd className="num">{e.est_time_impact_days ?? "—"}</dd></div>
          </dl>
        </Card>
        <Card title={t("entitlements")}>
          {mine.length === 0 ? <Empty>{lang === "ar" ? "لم يتم التحليل بعد" : "Not analysed yet"}</Empty> :
            <ul className="space-y-2">{mine.map((x) => <li key={x.id}><Link to={`/entitlements/${x.id}`} className="flex items-center justify-between rounded-lg border p-2.5 text-sm hover:border-brand-500">
              <span>{x.ref} · {label("entitlement_types", x.entitlement_type)}</span><Badge>{label("entitlement_status", x.status)}</Badge></Link></li>)}</ul>}
        </Card>
        <Card title={t("linked_docs")} className="xl:col-span-2">
          {e.documents.length === 0 ? <Empty>{t("none")}</Empty> : (
            <ul className="divide-y divide-slate-100">{e.documents.map((d: any) => (
              <li key={d.id} className="flex items-center justify-between gap-2 py-2.5 text-sm">
                <div><Link to={`/documents/${d.id}`} className="font-medium text-brand-600">{d.title}</Link>
                  <div className="text-xs text-slate-500">{label("doc_types", d.doc_type)} · {d.author_party || "—"} · {fmtDate(d.doc_date, lang)}</div></div>
                {can("event.write") && <Button size="sm" variant="ghost" icon={<Unlink className="h-3.5 w-3.5" />} onClick={() => unlink.mutate(d.id)}>{t("unlink")}</Button>}
              </li>))}</ul>)}
        </Card>
        <Card title={t("suggested_docs")} subtitle={lang === "ar" ? "اقتراحات فقط — لا تُحتسب كأدلة إلا بعد ربطها" : "Suggestions only — not counted as evidence until you link them"}>
          {sugg.data?.length === 0 ? <Empty>{t("none")}</Empty> : <ul className="space-y-2">{sugg.data?.map((s) => (
            <li key={s.document_id} className="rounded-lg border p-2.5 text-sm">
              <div className="flex items-start justify-between gap-2"><span className="font-medium">{s.title}</span><span className="num text-xs text-slate-500">{Math.round(s.score * 100)}%</span></div>
              <p className="mt-1 line-clamp-2 text-xs text-slate-500">{s.excerpt}</p>
              {can("event.write") && <Button size="sm" variant="secondary" className="mt-2" icon={<Link2 className="h-3.5 w-3.5" />} onClick={() => link.mutate(s.document_id)}>{t("link")}</Button>}
            </li>))}</ul>}
        </Card>
        <Card title={t("related_clauses")} className="xl:col-span-3">
          {e.clause_links.length === 0 ? <Empty>{lang === "ar" ? "شغّل الاكتشاف لربط البنود" : "Run discovery to correlate clauses"}</Empty> : (
            <table className="w-full"><thead><tr><th className="th">{t("clauses")}</th><th className="th">{t("category")}</th><th className="th">{t("page")}</th><th className="th">{t("score")}</th><th className="th">{t("basis")}</th></tr></thead>
              <tbody>{e.clause_links.map((c: any) => (
                <tr key={c.clause_id} className="border-t border-slate-100"><td className="td">{c.clause_number} · {c.title}</td><td className="td"><Badge tone="blue">{label("clause_categories", c.category)}</Badge></td>
                  <td className="td num">{c.page}</td><td className="td num">{Math.round(c.score * 100)}%</td>
                  <td className="td text-xs text-slate-500">{c.breakdown && Object.entries(c.breakdown).map(([k, v]) => `${k} ${Math.round((v as number) * 100)}%`).join(" · ")}</td></tr>))}</tbody></table>)}
        </Card>
      </div>
    </div>
  );
}
