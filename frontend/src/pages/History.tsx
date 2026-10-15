import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { History as HistoryIcon } from "lucide-react";
import { api } from "@/lib/api";
import { useActiveDecision, useI18n } from "@/lib/app";
import { useDecisions } from "@/lib/hooks";
import { Badge, Card, FutureChip, PageHeader, Spinner, StatusBadge } from "@/components/ui";

function DecisionRuns({ d }: { d: any }) {
  const { t, date, num } = useI18n();
  const { setActive } = useActiveDecision();
  const detail = useQuery({ queryKey: ["decision", d.id], queryFn: () => api(`/decisions/${d.id}`) });
  return (
    <Card title={d.title} subtitle={d.question} action={<StatusBadge status={d.status} />}>
      {!detail.data ? <Spinner /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-xs">
            <thead><tr className="border-b border-line text-muted">
              <th className="p-2 text-start">{t("hi.run")}</th><th className="p-2 text-start">{t("status")}</th><th className="p-2 text-start">{t("hi.mode")}</th>
              <th className="p-2 text-end">{t("hi.duration")}</th><th className="p-2 text-start">{t("created")}</th><th className="p-2" />
            </tr></thead>
            <tbody>
              {detail.data.runs.map((r: any) => (
                <tr key={r.id} className="border-b border-line/40">
                  <td className="p-2 font-mono">{r.id.slice(0, 8)}</td>
                  <td className="p-2"><StatusBadge status={r.status} />{r.error && <span className="ms-2 text-critical">{r.error}</span>}</td>
                  <td className="p-2"><Badge tone="violet">{r.mode}</Badge></td>
                  <td className="p-2 text-end num">{num(r.compute_ms, 0)} ms</td>
                  <td className="p-2 text-muted">{date(r.created_at)}</td>
                  <td className="p-2 text-end"><Link to={`/execution/${r.id}`} onClick={() => setActive(d.id)} className="text-accent hover:underline">{t("open")}</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
          {d.recommended_strategy && <div className="mt-2 flex items-center gap-2 text-xs text-muted">{t("hi.rec")}: <FutureChip k={d.recommended_strategy} /></div>}
          <div className="mt-2 text-[11px] text-muted">{detail.data.objectives.map((o: any) => o.description_en).join(" · ")}</div>
        </div>
      )}
    </Card>
  );
}

export default function History() {
  const { t } = useI18n();
  const { data, isLoading } = useDecisions();
  const sims = useQuery({ queryKey: ["simruns"], queryFn: () => api<any[]>("/simulation/runs") });
  const { date, num } = useI18n();
  return (
    <div>
      <PageHeader icon={HistoryIcon} title={t("hi.title")} subtitle={t("hi.subtitle")} />
      {isLoading ? <Spinner /> : <div className="space-y-5">{data?.map((d) => <DecisionRuns key={d.id} d={d} />)}</div>}
      <Card className="mt-5" title={t("nav.lab")} subtitle="simulation_runs">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-xs">
            <thead><tr className="border-b border-line text-muted">
              <th className="p-2 text-start">ID</th><th className="p-2 text-start">Kind</th><th className="p-2 text-start">{t("fu.fingerprint")}</th>
              <th className="p-2 text-end">Seed</th><th className="p-2 text-end">n</th><th className="p-2 text-end">ms</th><th className="p-2 text-start">{t("created")}</th>
            </tr></thead>
            <tbody>
              {sims.data?.map((s) => (
                <tr key={s.id} className="border-b border-line/40">
                  <td className="p-2 font-mono">{s.id.slice(0, 8)}</td><td className="p-2"><Badge>{s.kind}</Badge></td>
                  <td className="p-2 font-mono">{s.input_fingerprint}</td><td className="p-2 text-end num">{s.seed}</td>
                  <td className="p-2 text-end num">{num(s.iterations, 0)}</td><td className="p-2 text-end num">{num(s.elapsed_ms, 0)}</td>
                  <td className="p-2 text-muted">{date(s.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
