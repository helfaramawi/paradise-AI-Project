import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, PlugZap, RefreshCw, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth, useI18n } from "@/lib/app";
import { Badge, Button, Card, ErrorBox, Input, PageHeader, Spinner, StatusBadge } from "@/components/ui";
import type { DictKey } from "@/i18n/dict";

const EDITABLE = ["annual_opex", "annual_revenue", "gross_margin_pct", "utilization_pct", "avg_project_delay_pct", "csat_pct",
  "software_cost", "infrastructure_cost", "contractor_cost", "personnel_cost", "facilities_cost", "vendor_services_cost", "other_ga_cost",
  "contractor_fte_cost", "contractual_delay_tolerance_pct", "opening_cash"];

export default function DataConnections() {
  const { t, pick, date, num } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const conns = useQuery({ queryKey: ["connectors"], queryFn: () => api<any[]>("/connectors") });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: () => api<any[]>("/datasets") });
  const ledger = useQuery({ queryKey: ["ledger"], queryFn: () => api("/datasets/synthetic/ledger") });
  const [msg, setMsg] = useState<Record<string, any>>({});
  const [edits, setEdits] = useState<Record<string, string>>({});
  const fileRef = useRef<HTMLInputElement>(null);
  const ds = datasets.data?.[0];
  const cur = ds?.versions?.[0];
  const inv = () => { qc.invalidateQueries({ queryKey: ["datasets"] }); qc.invalidateQueries({ queryKey: ["connectors"] }); };
  const test = useMutation({ mutationFn: (id: string) => api(`/connectors/${id}/test`, { method: "POST" }), onSuccess: (r, id) => { setMsg({ ...msg, [id]: r }); inv(); } });
  const sync = useMutation({ mutationFn: (id: string) => api(`/connectors/${id}/sync`, { method: "POST" }), onSuccess: (r, id) => { setMsg({ ...msg, [id]: r }); inv(); } });
  const upload = useMutation({
    mutationFn: (f: File) => { const fd = new FormData(); fd.append("file", f); return api(`/datasets/${ds.id}/import`, { method: "POST", body: fd }); },
    onSuccess: inv,
  });
  const save = useMutation({
    mutationFn: () => api(`/datasets/${ds.id}/versions`, { method: "POST", json: { data: Object.fromEntries(Object.entries(edits).map(([k, v]) => [k, Number(v)])), note: "Edited in UI" } }),
    onSuccess: () => { setEdits({}); inv(); },
  });
  if (!ds) return <Spinner />;
  return (
    <div>
      <PageHeader icon={Database} title={t("dc.title")} subtitle={t("dc.subtitle")} />
      <Card title={t("dc.connectors")} className="mb-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {conns.data?.map((c) => (
            <div key={c.id} className="rounded-xl border border-line p-3" data-testid={`conn-${c.kind}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="text-sm font-semibold">{c.name}</div>
                <Badge tone={c.implementation === "working" ? "good" : c.implementation === "adapter" ? "warn" : "neutral"}>
                  {t(`dc.impl.${c.implementation}` as DictKey)}
                </Badge>
              </div>
              <div className="mt-1 flex items-center gap-2 text-[11px] text-muted"><code>{c.kind}</code> · {c.status.replace(/_/g, " ")}</div>
              {c.last_sync_at && <div className="text-[11px] text-muted">{date(c.last_sync_at)}</div>}
              {can("connector.manage") && c.kind !== "csv" && (
                <div className="mt-2 flex gap-2">
                  <Button size="sm" variant="outline" icon={PlugZap} onClick={() => test.mutate(c.id)}>{t("dc.test")}</Button>
                  {c.implementation !== "interface_only" && <Button size="sm" variant="ghost" icon={RefreshCw} onClick={() => sync.mutate(c.id)}>{t("dc.sync")}</Button>}
                </div>
              )}
              {msg[c.id] && (
                <div className="mt-2 rounded-lg bg-panel2/70 p-2 text-[11px] text-ink2">
                  {msg[c.id].message || (msg[c.id].reconciliation ? `rows ${msg[c.id].rows_read} · diff ${msg[c.id].reconciliation.difference ?? "—"} · changed ${msg[c.id].changed_fields?.length ?? 0}` : JSON.stringify(msg[c.id]))}
                  {"verified_live" in msg[c.id] && <div>verified_live: {String(msg[c.id].verified_live)}</div>}
                </div>
              )}
            </div>
          ))}
        </div>
        <ErrorBox error={test.error || sync.error} />
      </Card>
      <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <Card title={`${t("dc.dataset")}: ${ds.name}`} subtitle={`v${cur.version} · ${cur.note} · ${cur.checksum.slice(0, 12)}`}
          action={<Badge tone="warn">{t("chip.synthetic")}</Badge>}>
          <div className="mb-2 text-xs text-muted">{t("dc.edit")}</div>
          <div className="grid gap-2 sm:grid-cols-2">
            {EDITABLE.map((k) => (
              <label key={k} className="flex items-center gap-2 text-xs">
                <span className="w-44 shrink-0 text-ink2">{k.replace(/_/g, " ")}</span>
                <Input className="h-8 num" disabled={!can("dataset.write")} value={edits[k] ?? String(cur.data[k])} onChange={(e) => setEdits({ ...edits, [k]: e.target.value })} />
                <Badge tone={cur.provenance[k] === "synthetic_given" ? "neutral" : cur.provenance[k] === "user_input" ? "accent" : cur.provenance[k] === "imported" ? "good" : "warn"}>
                  {cur.provenance[k]?.replace("synthetic_", "") || "—"}
                </Badge>
              </label>
            ))}
          </div>
          {can("dataset.write") && (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" disabled={!Object.keys(edits).length} loading={save.isPending} onClick={() => save.mutate()}>{t("save")}</Button>
              <input ref={fileRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
              <Button size="sm" variant="outline" icon={Upload} onClick={() => fileRef.current?.click()} loading={upload.isPending}>{t("dc.import")}</Button>
            </div>
          )}
          <ErrorBox error={save.error || upload.error} />
          {upload.data && <pre className="mt-2 overflow-x-auto rounded-lg bg-panel2 p-2 text-[10px]">{JSON.stringify((upload.data as any).reconciliation, null, 2)}</pre>}
        </Card>
        <div className="space-y-5">
          <Card title={t("dc.quality")} subtitle={`${Math.round(cur.validation.quality_score * 100)}%`}>
            <ul className="space-y-2">
              {cur.validation.checks.map((c: any) => (
                <li key={c.code} className="text-xs">
                  <div className="flex items-center gap-2"><code className="text-muted">{c.code}</code><StatusBadge status={c.severity === "error" ? "critical" : c.severity === "warning" ? "medium" : "low"} /><span className="font-medium">{pick(c.title_en, c.title_ar)}</span></div>
                  <p className="mt-0.5 text-ink2">{pick(c.detail_en, c.detail_ar)}</p>
                </li>
              ))}
            </ul>
          </Card>
          <Card title={t("dc.versions")}>
            <ul className="space-y-1 text-xs">
              {ds.versions.map((v: any) => <li key={v.id} className="flex justify-between"><span>v{v.version} · {v.note}</span><span className="text-muted">{date(v.created_at)}</span></li>)}
            </ul>
          </Card>
        </div>
      </div>
      <Card className="mt-5" title={t("dc.ledger")} subtitle={`${num(ledger.data?.rows?.length ?? 0, 0)} rows · synthetic=true`}>
        <div className="max-h-64 overflow-auto scroll-thin">
          <table className="w-full text-xs num">
            <thead className="sticky top-0 bg-panel text-muted"><tr><th className="p-1.5 text-start">Period</th><th className="p-1.5 text-start">Account</th><th className="p-1.5 text-start">Category</th><th className="p-1.5 text-end">EGP M</th></tr></thead>
            <tbody>{ledger.data?.rows?.slice(0, 84).map((r: any, i: number) => (
              <tr key={i} className="border-t border-line/40"><td className="p-1.5">{r.period}</td><td className="p-1.5">{r.account} {r.account_name}</td><td className="p-1.5">{r.category}</td><td className="p-1.5 text-end">{num(r.amount_egp_m, 3)}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
