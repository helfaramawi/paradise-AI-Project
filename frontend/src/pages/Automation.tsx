import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Play, ShieldAlert, Workflow } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth, useI18n } from "@/lib/app";
import { useResolvedDecisionId } from "@/lib/hooks";
import { Badge, Button, Card, ErrorBox, PageHeader, Spinner, StatusBadge } from "@/components/ui";

export default function Automation() {
  const { t, pick, date } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const did = useResolvedDecisionId();
  const wfs = useQuery({ queryKey: ["workflows"], queryFn: () => api("/automation/workflows") });
  const runs = useQuery({ queryKey: ["autoruns"], queryFn: () => api<any[]>("/automation/runs") });
  const trig = useMutation({
    mutationFn: ({ id, dry }: { id: string; dry: boolean }) =>
      api(`/automation/workflows/${id}/trigger`, { method: "POST", json: { dry_run: dry, decision_id: did, payload: { requested_at: new Date().toISOString().slice(0, 16) } } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["autoruns"] }),
  });
  if (!wfs.data) return <Spinner />;
  return (
    <div>
      <PageHeader icon={Workflow} title={t("au.title")} subtitle={t("au.subtitle")} />
      {!wfs.data.n8n_configured && (
        <div className="mb-5 flex items-center gap-2 rounded-xl border border-warn/40 bg-warn/5 p-3 text-xs text-ink2"><AlertTriangle className="h-4 w-4 text-warn" />{t("au.n8nOff")}</div>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {wfs.data.workflows.map((w: any) => (
          <Card key={w.id} className={w.consequential ? "border-critical/40" : ""}>
            <div className="flex items-start justify-between gap-2">
              <div className="font-semibold">{pick(w.name_en, w.name_ar)}</div>
              <div className="flex gap-1">
                {w.consequential && <Badge tone="critical" icon={ShieldAlert}>{t("au.consequential")}</Badge>}
                <Badge>{w.trigger}</Badge>
              </div>
            </div>
            <p className="mt-1 text-xs text-muted">{pick(w.description_en, w.description_ar)}</p>
            <div className="mt-2 text-[11px] text-muted"><code>{w.n8n_webhook_path}</code>{w.schedule && <> · <code>{w.schedule}</code></>} · retry ×{w.retry_max} · {w.mode}</div>
            {can("automation.run") && (
              <div className="mt-3 flex gap-2">
                <Button size="sm" variant="outline" icon={Play} onClick={() => trig.mutate({ id: w.id, dry: true })}>{t("au.dryRun")}</Button>
                <Button size="sm" variant={w.consequential ? "danger" : "subtle"} onClick={() => trig.mutate({ id: w.id, dry: false })}>{t("au.live")}</Button>
              </div>
            )}
          </Card>
        ))}
      </div>
      <ErrorBox error={trig.error} />
      <Card className="mt-5" title={t("au.runs")}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-xs">
            <thead><tr className="border-b border-line text-muted">
              <th className="p-2 text-start">Workflow</th><th className="p-2 text-start">{t("status")}</th><th className="p-2 text-start">Idempotency key</th><th className="p-2 text-start">Result</th><th className="p-2 text-start">{t("created")}</th>
            </tr></thead>
            <tbody>
              {runs.data?.map((r) => (
                <tr key={r.id} className="border-b border-line/40 align-top">
                  <td className="p-2">{r.workflow_key}</td>
                  <td className="p-2"><StatusBadge status={r.status === "dry_run_ok" ? "completed" : r.status} /> {r.dry_run && <Badge>{t("au.dryRun")}</Badge>}</td>
                  <td className="p-2 font-mono text-[10px]">{r.idempotency_key}</td>
                  <td className="max-w-md p-2 text-[11px] text-ink2">{r.result?.reason ? [].concat(r.result.reason).join("; ") : r.result?.would_post_to || JSON.stringify(r.result)}</td>
                  <td className="p-2 text-muted">{date(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
