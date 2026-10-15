import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, FlaskConical, Play } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/app";
import { DEFAULT_CONTROLS, ControlsForm, type Controls } from "@/components/Controls";
import { FanChart, Histogram, Tornado } from "@/components/charts";
import { Badge, Button, Card, ErrorBox, PageHeader, SliderField, Stat } from "@/components/ui";
import type { DictKey } from "@/i18n/dict";

const LEVERS = [
  "software_consolidation", "infra_optimization", "vendor_renegotiation", "facilities_consolidation", "expense_freeze",
  "contractor_reduction", "automation_investment", "operating_model_redesign", "workforce_termination",
] as const;

export default function SimulationLab() {
  const { t, pick, egp, pct, num, prob } = useI18n();
  const [levers, setLevers] = useState<Record<string, number>>({
    software_consolidation: 0.8, infra_optimization: 0.8, vendor_renegotiation: 0.6, facilities_consolidation: 0,
    expense_freeze: 0.5, contractor_reduction: 0.25, automation_investment: 4, operating_model_redesign: 0, workforce_termination: 0,
  });
  const [controls, setControls] = useState<Controls>(DEFAULT_CONTROLS);
  const [iterations, setIterations] = useState(2000);
  const model = useQuery({ queryKey: ["model"], queryFn: () => api("/simulation/model") });
  const run = useMutation({ mutationFn: () => api("/simulation/custom", { method: "POST", json: { levers, controls, iterations } }) });
  const r: any = run.data;
  return (
    <div>
      <PageHeader icon={FlaskConical} title={t("lab.title")} subtitle={t("lab.subtitle")} />
      <div className="grid gap-5 xl:grid-cols-[340px_1fr]">
        <div className="space-y-5">
          <Card title={t("lab.levers")}>
            <div className="space-y-4">
              {LEVERS.map((k) => (
                <SliderField key={k} label={t(`lever.${k}` as DictKey)} value={levers[k]}
                  min={0} max={k === "automation_investment" ? 20 : 1} step={k === "automation_investment" ? 0.5 : 0.05}
                  onChange={(v) => setLevers({ ...levers, [k]: v })}
                  format={(v) => (k === "automation_investment" ? egp(v) : pct(v * 100, 0))}
                  hint={k === "workforce_termination" ? t("lab.termWarn") : undefined} />
              ))}
              <SliderField label="Monte Carlo iterations" value={iterations} min={200} max={10000} step={200} onChange={setIterations} format={(v) => num(v, 0)} />
              <Button className="w-full" icon={Play} loading={run.isPending} onClick={() => run.mutate()} data-testid="lab-run">{t("lab.run")}</Button>
              <ErrorBox error={run.error} />
            </div>
          </Card>
          <Card title={t("fu.controls")}><ControlsForm value={controls} onChange={setControls} compact /></Card>
        </div>
        <div className="min-w-0 space-y-5">
          {r ? (
            <>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label={t("fu.savings")} value={pct(r.summary.savings_pct_at_deadline.p50)} sub={egp(r.summary.run_rate_savings_at_deadline.p50)} />
                <Stat label={t("fu.net")} value={egp(r.summary.net_benefit_12m.p50)} sub={`${t("range")} ${num(r.summary.net_benefit_12m.p10)}–${num(r.summary.net_benefit_12m.p90)}`} />
                <Stat label={t("fu.delay")} value={`+${num(r.summary.max_delay_increase_pct.p50)} ${t("pts")}`} sub={`P90 +${num(r.summary.max_delay_increase_pct.p90)}`} />
                <Stat label={t("fu.pTarget")} value={prob(r.probabilities.meet_target)} sub={`${t("fu.violated")}: ${r.constraints_violated.join(", ") || "—"}`}
                  tone={r.hard_constraints_violated.length ? "critical" : "good"} />
              </div>
              {levers.workforce_termination > 0 && (
                <div className="flex items-center gap-2 rounded-xl border border-critical/40 bg-critical/5 p-3 text-xs">
                  <AlertTriangle className="h-4 w-4 text-critical" /> C2 · GOV-001 — {t("lab.termWarn")}
                </div>
              )}
              <div className="grid gap-5 lg:grid-cols-2">
                <Card title={t("fu.savingsPath")}><FanChart series={[{ key: "A", band: r.trajectory.savings_run_rate, label: pick("Custom strategy", "استراتيجية مخصصة") }]} height={220} /></Card>
                <Card title={t("tm.delay")}><FanChart series={[{ key: "B", band: r.trajectory.delay_pct, label: pick("Custom strategy", "استراتيجية مخصصة") }]} height={220} /></Card>
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                <Card title={t("lab.tornado")}><Tornado rows={r.sensitivity} base={r.sensitivity[0]?.base_net_benefit ?? 0} /></Card>
                <Card title={t("lab.hist")}><Histogram counts={r.net_benefit_histogram.counts} edges={r.net_benefit_histogram.edges} /></Card>
              </div>
              <Card title={t("lab.des")} subtitle={`${r.project_portfolio.method} · capacity ${num(r.project_portfolio.baseline_capacity_fte)} → ${num(r.project_portfolio.scenario_capacity_fte)} FTE`}>
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-6 lg:grid-cols-9">
                  {r.project_portfolio.projects.map((p: any) => (
                    <div key={p.project_id} title={`${p.baseline_months} → ${p.scenario_months} months`}
                      className={`rounded-lg border p-2 text-center text-[10px] ${p.at_risk ? "border-critical/60 bg-critical/10" : "border-line"}`}>
                      <div className="font-semibold">{p.project_id}</div>
                      <div className="num">+{num(p.additional_delay_pct, 1)}%</div>
                    </div>
                  ))}
                </div>
              </Card>
              <p className="text-[11px] text-muted num">fingerprint {r.meta.fingerprint} · seed {r.meta.seed} · n={num(r.meta.iterations, 0)}</p>
            </>
          ) : (
            <Card><div className="p-10 text-center text-sm text-muted">{t("lab.run")} →</div></Card>
          )}
          <Card title={t("lab.params")} subtitle={model.data && `${model.data.production.key} v${model.data.production.version}`}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-xs">
                <thead><tr className="border-b border-line text-muted">
                  <th className="p-2 text-start">Parameter</th><th className="p-2 text-end">Low</th><th className="p-2 text-end">Mode</th><th className="p-2 text-end">High</th><th className="p-2 text-start">Rationale / calibration</th>
                </tr></thead>
                <tbody>
                  {model.data?.parameters.map((p: any) => (
                    <tr key={p.key} className="border-b border-line/40 align-top">
                      <td className="p-2"><div className="font-medium">{pick(p.label_en, p.label_ar)}</div><div className="text-muted">{p.unit}</div></td>
                      <td className="p-2 text-end num">{p.dist.low}</td><td className="p-2 text-end num font-semibold">{p.dist.mode}</td><td className="p-2 text-end num">{p.dist.high}</td>
                      <td className="p-2 text-muted">{p.rationale}<div><Badge tone="warn">{p.calibration}</Badge></div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
