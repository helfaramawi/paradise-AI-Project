import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Activity, ArrowRight, BadgeCheck, Building2, Clock, Gauge, Landmark, ShieldCheck, Smile, Users, Wallet } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/app";
import { useDossier, useResolvedDecisionId } from "@/lib/hooks";
import { Badge, Button, Card, FUTURE_COLOR, FutureChip, PageHeader, Spinner, Stat, StatusBadge } from "@/components/ui";

export default function CommandCenter() {
  const { t, pick, egp, pct, num, date, prob } = useI18n();
  const { data: dash, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: () => api("/dashboard"), refetchInterval: 10000 });
  const { data: datasets } = useQuery({ queryKey: ["datasets"], queryFn: () => api<any[]>("/datasets") });
  const did = useResolvedDecisionId();
  const { data: dossier } = useDossier(did);
  if (isLoading) return <Spinner />;
  const ds = datasets?.[0]?.versions?.[0]?.data;
  const rec = dossier?.run?.result?.recommendation;
  const res = dossier?.simulation?.results;
  const counts = dash?.decision_counts || {};
  const total = Object.values(counts).reduce((a: number, b) => a + (b as number), 0);
  return (
    <div>
      <PageHeader icon={Landmark} title={t("cc.title")} subtitle={t("cc.subtitle")}
        actions={<Link to="/decisions/new"><Button icon={ArrowRight}>{t("cc.cta")}</Button></Link>} />

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="card relative mb-6 overflow-hidden p-5">
        <div className="absolute inset-0 grid-bg opacity-40" />
        <div className="relative flex flex-wrap items-center gap-4">
          <ShieldCheck className="h-6 w-6 text-good" />
          <p className="flex-1 text-sm text-ink2">{t("cc.principle")}</p>
          <Badge tone="warn">{t("chip.synthetic")}</Badge>
        </div>
      </motion.div>

      {ds && (
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Stat label={t("cc.kpi.opex")} value={egp(ds.annual_opex, 0)} icon={Wallet} />
          <Stat label={t("cc.kpi.revenue")} value={egp(ds.annual_revenue, 0)} icon={Building2} />
          <Stat label={t("cc.kpi.employees")} value={num(ds.employees, 0)} icon={Users} />
          <Stat label={t("cc.kpi.util")} value={pct(ds.utilization_pct, 0)} icon={Gauge} />
          <Stat label={t("cc.kpi.delay")} value={pct(ds.avg_project_delay_pct, 0)} icon={Clock} />
          <Stat label={t("cc.kpi.csat")} value={pct(ds.csat_pct, 0)} icon={Smile} />
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2" title={t("cc.latest")}
          action={dossier && <StatusBadge status={dossier.decision.status} />}>
          {rec ? (
            <div>
              <div className="text-sm font-semibold text-ink">{dossier.decision.title}</div>
              <p className="mt-2 text-[15px] leading-relaxed text-ink2">{pick(rec.headline_en, rec.headline_ar)}</p>
              <div className="mt-5 grid gap-3 md:grid-cols-3">
                {(["A", "B", "C"] as const).map((k) => {
                  const f = res?.[k];
                  const pf = rec.per_future[k];
                  return (
                    <Link to="/futures" key={k} className="card card-hover block p-4"
                      style={{ borderTopColor: FUTURE_COLOR[k], borderTopWidth: 3 }}>
                      <div className="flex items-center justify-between">
                        <FutureChip k={k} />
                        {rec.recommended_strategy === k && <Badge tone="accent">★</Badge>}
                      </div>
                      <div className="mt-1 text-[11px] text-muted">{pick(f?.definition?.name_en, f?.definition?.name_ar)}</div>
                      <div className="mt-3 font-display text-2xl font-semibold num">{pct(f?.summary.savings_pct_at_deadline.p50)}</div>
                      <div className="text-[11px] text-muted">{t("fu.savings")}</div>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        <StatusBadge status={pf.governance_outcome} />
                        <Badge tone="neutral">{t("fu.pTarget")} {prob(f?.probabilities.meet_target)}</Badge>
                      </div>
                    </Link>
                  );
                })}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to="/court"><Button variant="outline" size="sm">{t("nav.court")}</Button></Link>
                <Link to="/time-machine"><Button variant="outline" size="sm">{t("nav.timemachine")}</Button></Link>
                <Link to="/approvals"><Button variant="outline" size="sm">{t("nav.approvals")}</Button></Link>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-start gap-3 text-sm text-muted">
              {t("noDecision")}
              <Link to="/decisions/new"><Button>{t("startDemo")}</Button></Link>
            </div>
          )}
        </Card>

        <div className="grid gap-5">
          <div className="grid grid-cols-3 gap-3">
            <Stat label={t("cc.decisions")} value={num(total, 0)} icon={Landmark} />
            <Stat label={t("cc.pending")} value={num(dash?.pending_approvals, 0)} icon={BadgeCheck} tone={dash?.pending_approvals ? "warn" : undefined} />
            <Stat label={t("cc.runs")} value={num(dash?.total_runs, 0)} icon={Activity} />
          </div>
          <Card title={t("cc.activity")}>
            <ul className="space-y-2.5">
              {dash?.recent_activity?.map((a: any) => (
                <li key={a.id} className="flex items-start gap-2 text-xs">
                  <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${a.actor_type === "user" ? "bg-accent" : "bg-accent2"}`} />
                  <div className="min-w-0">
                    <div className="truncate font-medium text-ink2">{a.action}</div>
                    <div className="text-muted">{a.actor_type} · {date(a.ts)}</div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
