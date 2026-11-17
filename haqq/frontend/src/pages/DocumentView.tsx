import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Alert, Badge, Button, Card, DemoBadge, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, useI18n } from "../lib/i18n";
import { useTaxonomy } from "../lib/taxonomy";
import { ClauseCard } from "./ProjectDetail";

export default function DocumentView() {
  const { id = "" } = useParams();
  const { t, lang } = useI18n();
  const { label } = useTaxonomy();
  const { can } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["doc", id], queryFn: () => api.get<any>(`/documents/${id}`),
    refetchInterval: (query) => (["uploaded", "processing"].includes((query.state.data as any)?.status) ? 2000 : false) });
  const pages = useQuery({ queryKey: ["doc-pages", id], queryFn: () => api.get<any[]>(`/documents/${id}/pages`), enabled: q.data?.status === "processed" });
  const clauses = useQuery({ queryKey: ["doc-clauses", id, q.data?.project_id], enabled: !!q.data?.project_id && q.data?.doc_type === "contract",
    queryFn: () => api.get<any[]>(`/projects/${q.data.project_id}/clauses`, { document_id: id }) });
  const re = useMutation({ mutationFn: () => api.post(`/documents/${id}/reprocess`), onSuccess: () => qc.invalidateQueries({ queryKey: ["doc", id] }) });
  const [page, setPage] = useState(1);
  if (q.isLoading) return <Spinner />;
  const d = q.data;
  if (!d) return <Alert tone="error">{t("error")}</Alert>;
  const cur = pages.data?.find((p) => p.page === page);
  return (
    <div>
      <PageHeader crumbs={<Link to={`/projects/${d.project_id}/documents`} className="hover:underline">{t("documents")}</Link>}
        title={<span className="flex items-center gap-2">{d.title} {d.is_demo && <DemoBadge />}</span>}
        subtitle={`${d.filename} · v${d.version} · sha256 ${d.sha256.slice(0, 16)}…`}
        actions={<>
          <Button variant="secondary" icon={<Download className="h-4 w-4" />} onClick={() => api.download(`/documents/${id}/download`, d.filename)}>{t("download")}</Button>
          {can("contract.analyze") && <Button variant="secondary" icon={<RefreshCw className="h-4 w-4" />} loading={re.isPending} onClick={() => re.mutate()}>{t("reprocess")}</Button>}
        </>} />
      {d.security_flags?.length > 0 && <div className="mb-4"><Alert tone="warn" title={t("security_flag")}>{d.security_flags.map((f: any) => <div key={f.pattern} className="text-xs">“…{f.match}…”</div>)}</Alert></div>}
      {d.meta?.warning && <div className="mb-4"><Alert tone="warn">{d.meta.warning}</Alert></div>}
      {d.status === "failed" && <div className="mb-4"><Alert tone="error">{d.error || d.job?.error}</Alert></div>}
      <div className="grid gap-5 xl:grid-cols-3">
        <Card title={t("classification")}>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-slate-500">{t("status")}</dt><dd><StatusBadge status={d.status} label={t(d.status)} /></dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">{t("doc_type")}</dt><dd>{label("doc_types", d.doc_type)} <span className="text-xs text-slate-400">{d.doc_type_confidence !== null && `${Math.round(d.doc_type_confidence * 100)}%`}</span></dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">{t("author")}</dt><dd>{d.author_party || "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">{t("doc_date")}</dt><dd>{fmtDate(d.doc_date, lang)}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">{t("pages")}</dt><dd className="num">{d.page_count}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Method</dt><dd>{d.extraction_method} {d.ocr_pages > 0 && <Badge tone="violet">{t("ocr")} {d.ocr_pages}</Badge>}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Language</dt><dd>{d.language}</dd></div>
          </dl>
          {d.meta?.classifier?.scores && <div className="mt-3 text-xs text-slate-500">{Object.entries(d.meta.classifier.scores).map(([k, v]) => `${k}: ${v}`).join(" · ")}</div>}
          {d.versions?.length > 1 && <div className="mt-4"><div className="label">{t("version")}</div>{d.versions.map((v: any) => <Link key={v.id} to={`/documents/${v.id}`} className="me-2 text-xs text-brand-600">v{v.version}</Link>)}</div>}
        </Card>
        <Card title={t("extracted_text")} className="xl:col-span-2" actions={pages.data && pages.data.length > 1 && (
          <select className="input w-28" value={page} onChange={(e) => setPage(+e.target.value)}>{pages.data.map((p) => <option key={p.page} value={p.page}>{t("page")} {p.page}</option>)}</select>)}>
          {!pages.data ? <Spinner /> : cur ? (<>
            <div className="mb-2 flex gap-2 text-xs text-slate-500"><Badge>{cur.method}</Badge>{cur.estimated && <Badge tone="amber">{t("page_estimated")}</Badge>}</div>
            <pre dir="auto" className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-4 font-sans text-sm leading-relaxed text-slate-800">{cur.text || "—"}</pre></>) : null}
        </Card>
      </div>
      {clauses.data && clauses.data.length > 0 && (
        <div className="mt-6"><h2 className="mb-3 text-lg font-semibold text-navy-900">{t("extracted_clauses")} ({clauses.data.length})</h2>
          <div className="grid gap-3 lg:grid-cols-2">{clauses.data.map((c) => <ClauseCard key={c.id} c={c} />)}</div></div>)}
    </div>
  );
}
