import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Landmark, Play, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useActiveDecision, useAuth, useI18n } from "@/lib/app";
import { useDecisions } from "@/lib/hooks";
import { Button, Empty, ErrorBox, FutureChip, PageHeader, Spinner, StatusBadge } from "@/components/ui";

export default function Workspace() {
  const { t, date, num } = useI18n();
  const { can } = useAuth();
  const { data, isLoading, error } = useDecisions();
  const { setActive, activeId } = useActiveDecision();
  const nav = useNavigate();
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: (id: string) => api(`/decisions/${id}/runs`, { method: "POST", json: {} }),
    onSuccess: (r: any, id) => {
      setActive(id);
      qc.invalidateQueries({ queryKey: ["decisions"] });
      nav(`/execution/${r.run_id}`);
    },
  });
  return (
    <div>
      <PageHeader icon={Landmark} title={t("ws.title")} subtitle={t("ws.subtitle")}
        actions={can("decision.create") && <Link to="/decisions/new"><Button icon={Plus}>{t("ws.new")}</Button></Link>} />
      <ErrorBox error={error || run.error} />
      {isLoading ? <Spinner /> : !data?.length ? (
        <Empty action={<Link to="/decisions/new"><Button>{t("startDemo")}</Button></Link>}>{t("noDecision")}</Empty>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b border-line text-start text-xs text-muted">
              <tr>
                <th className="p-3 text-start">{t("in.titleField")}</th>
                <th className="p-3 text-start">{t("status")}</th>
                <th className="p-3 text-start">{t("hi.rec")}</th>
                <th className="p-3 text-start">{t("hi.run")}</th>
                <th className="p-3 text-start">{t("created")}</th>
                <th className="p-3 text-end">{t("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.id} className={`border-b border-line/50 transition hover:bg-panel2/50 ${activeId === d.id ? "bg-accent/5" : ""}`}>
                  <td className="p-3">
                    <button className="text-start font-medium text-ink hover:text-accent" onClick={() => { setActive(d.id); nav("/court"); }}>
                      {d.title}
                    </button>
                    <div className="line-clamp-1 max-w-md text-xs text-muted">{d.question}</div>
                  </td>
                  <td className="p-3"><StatusBadge status={d.status} /></td>
                  <td className="p-3">{d.recommended_strategy ? <FutureChip k={d.recommended_strategy} /> : <span className="text-muted">—</span>}</td>
                  <td className="p-3 text-xs text-muted">
                    {d.latest_run ? <span className="flex items-center gap-2"><StatusBadge status={d.latest_run.status} /> {num(d.run_count, 0)} {t("ws.runs")}</span> : "—"}
                  </td>
                  <td className="p-3 text-xs text-muted">{date(d.created_at)}</td>
                  <td className="p-3 text-end">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" onClick={() => { setActive(d.id); nav("/futures"); }}>{t("open")}</Button>
                      {can("decision.run") && (
                        <Button size="sm" variant="outline" icon={Play} loading={run.isPending && run.variables === d.id}
                          disabled={["analyzing", "pending_approval", "approved"].includes(d.status)} onClick={() => run.mutate(d.id)}>
                          {d.latest_run ? t("rerun") : t("run")}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
