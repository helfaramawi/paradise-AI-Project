import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, GitCompareArrows, Loader2, RotateCcw, Save, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth, useI18n } from "@/lib/app";
import { DecisionContextBar, DecisionGate } from "@/components/DecisionGate";
import { ControlsForm, pickControls, type Controls } from "@/components/Controls";
import { FanChart } from "@/components/charts";
import { Badge, Button, Card, ErrorBox, FUTURE_COLOR, FutureChip, PageHeader, StatusBadge, cn } from "@/components/ui";

const KEYS = ["A", "B", "C"] as const;

function Range({ s, fmt }: { s: { p10: number; p50: number; p90: number }; fmt: (v: number) => string }) {
  return (
    <span>
      <span className="font-semibold text-ink num">{fmt(s.p50)}</span>
      <span className="ms-1 text-[10px] text-muted num">[{fmt(s.p10)} – {fmt(s.p90)}]</span>
    </span>
  );
}

function FutureCard({ k, f, gov, recommended, i }: { k: string; f: any; gov?: any; recommended: boolean; i: number }) {
  const { t, pick, egp, pct, num, prob } = useI18n();
  const s = f.summary;
  const rows: [string, React.ReactNode][] = [
    [t("fu.savings"), <Range s={s.run_rate_savings_at_deadline} fmt={(v) => egp(v)} />],
    [t("fu.implCost"), <Range s={s.one_off_implementation_cost} fmt={(v) => egp(v)} />],
    [t("fu.net"), <Range s={s.net_benefit_12m} fmt={(v) => egp(v)} />],
    [t("fu.cash"), <Range s={s.min_cash_balance} fmt={(v) => egp(v)} />],
    [t("fu.delay"), <Range s={s.max_delay_increase_pct} fmt={(v) => `+${num(v, 1)}`} />],
    [t("fu.workforce"), <Range s={s.peak_utilization_pct} fmt={(v) => pct(v, 0)} />],
    [t("fu.csat"), <Range s={s.min_csat_pct} fmt={(v) => pct(v, 1)} />],
    [t("fu.risk"), <span className="font-semibold num">{egp(s.delivery_loss_12m.p90)}</span>],
    [t("fu.projects"), <span className="font-semibold num">{num(f.project_portfolio?.projects_at_risk, 0)} / {num(f.project_portfolio?.projects?.length, 0)}</span>],
  ];
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
      className={cn("card relative overflow-hidden p-5", recommended && "ring-2 ring-accent/60")} data-testid={`future-${k}`}>
      <div className="absolute inset-x-0 top-0 h-1" style={{ background: FUTURE_COLOR[k] }} />
      <div className="flex items-start justify-between gap-2">
        <div>
          <FutureChip k={k} />
          <h3 className="mt-1 font-display text-lg font-semibold">{pick(f.definition.name_en, f.definition.name_ar)}</h3>
          <p className="text-xs text-muted">{pick(f.definition.tagline_en, f.definition.tagline_ar)}</p>
        </div>
        {recommended && <Badge tone="accent">★</Badge>}
      </div>
      <div className="mt-4 flex items-end gap-3">
        <div className="font-display text-4xl font-semibold num" style={{ color: FUTURE_COLOR[k] }}>{pct(s.savings_pct_at_deadline.p50)}</div>
        <div className="pb-1 text-[11px] leading-tight text-muted">
          {t("fu.pTarget")} <b className="text-ink">{prob(f.probabilities.meet_target)}</b><br />
          {t("fu.achievable")} <b className="text-ink">{pct(f.achievable_reduction_pct_at_tolerance)}</b>
        </div>
      </div>
      <dl className="mt-4 divide-y divide-line/60 text-xs">
        {rows.map(([l, v]) => (
          <div key={l} className="flex items-center justify-between gap-2 py-1.5"><dt className="text-muted">{l}</dt><dd>{v}</dd></div>
        ))}
      </dl>
      <div className="mt-3">
        <div className="label mb-1">{t("fu.violated")}</div>
        <div className="flex flex-wrap gap-1">
          {f.constraints.map((c: any) => (
            <Badge key={c.code} tone={c.status === "pass" ? "good" : c.hard ? "critical" : "warn"} icon={c.status === "pass" ? CheckCircle2 : AlertTriangle}>
              {c.code} {prob(c.probability_satisfied)}
            </Badge>
          ))}
        </div>
      </div>
      {gov && (
        <div className="mt-3 flex items-center gap-2 text-xs">
          <span className="label">{t("fu.governance")}</span><StatusBadge status={gov.outcome} />
          {gov.required_roles?.length > 0 && <span className="uppercase text-muted">{gov.required_roles.join(" · ")}</span>}
        </div>
      )}
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer text-accent">{t("fu.measures")} · {t("fu.validate")}</summary>
        <ul className="mt-2 list-disc space-y-0.5 ps-4 text-ink2">
          {(pick(f.definition.measures_en.join("|"), f.definition.measures_ar.join("|"))).split("|").map((m: string) => <li key={m}>{m}</li>)}
        </ul>
        <div className="mt-2 text-amber-600 dark:text-warn">
          {f.sensitivity?.slice(0, 3).map((x: any) => pick(x.label_en, x.label_ar)).join(" · ")}
        </div>
      </details>
    </motion.div>
  );
}

function Futures({ d, decisionId }: { d: any; decisionId: string }) {
  const { t, pick, egp, pct, num, prob } = useI18n();
  const { can } = useAuth();
  const initial = pickControls(d.decision.controls);
  const [controls, setControls] = useState<Controls>(initial);
  const [whatIf, setWhatIf] = useState<any>(null);
  const timer = useRef<number>();
  const dirty = JSON.stringify(controls) !== JSON.stringify(initial);
  const sim = useMutation({
    mutationFn: (persist: boolean) => api("/simulation/run", {
      method: "POST",
      json: { controls, iterations: 1000, seed: d.simulation.seed, dataset_version_id: d.dataset.version_id, persist, decision_id: decisionId },
    }),
    onSuccess: (r) => setWhatIf(r),
  });
  useEffect(() => {
    if (!dirty) { setWhatIf(null); return; }
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => sim.mutate(false), 350);
    return () => window.clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(controls)]);
  const results = whatIf ? { ...whatIf.futures, BASELINE: whatIf.baseline } : d.simulation.results;
  const govByKey = Object.fromEntries(d.governance.map((g: any) => [g.scenario_key, g]));
  const rec = d.run.result.recommendation;
  const metrics: [string, (f: any) => string][] = [
    [t("fu.savings"), (f) => egp(f.summary.run_rate_savings_at_deadline.p50)],
    ["%", (f) => pct(f.summary.savings_pct_at_deadline.p50)],
    [t("fu.implCost"), (f) => egp(f.summary.one_off_implementation_cost.p50)],
    [t("fu.net"), (f) => egp(f.summary.net_benefit_12m.p50)],
    [t("fu.cash"), (f) => egp(f.summary.min_cash_balance.p50)],
    [t("fu.delay"), (f) => `+${num(f.summary.max_delay_increase_pct.p50, 1)} ${t("pts")}`],
    [t("fu.workforce"), (f) => pct(f.summary.peak_utilization_pct.p50, 0)],
    [t("fu.csat"), (f) => pct(f.summary.min_csat_pct.p50)],
    [t("fu.pTarget"), (f) => prob(f.probabilities.meet_target)],
    [t("fu.projects"), (f) => num(f.project_portfolio?.projects_at_risk, 0)],
    [t("fu.violated"), (f) => f.constraints_violated.join(", ") || "—"],
  ];
  return (
    <div>
      <DecisionContextBar dossier={d} decisionId={decisionId} />
      <div className="space-y-5">
        <Card title={t("fu.controls")}
          action={dirty && <Button variant="ghost" size="sm" icon={RotateCcw} onClick={() => setControls(initial)} aria-label="reset" />}>
          <ControlsForm value={controls} onChange={setControls} wide />
          <div className="mt-4 flex flex-wrap items-center gap-3 text-[11px] text-muted">
            {sim.isPending && <div className="flex items-center gap-2 text-accent"><Loader2 className="h-3 w-3 animate-spin" />{t("fu.recalc")}</div>}
            {whatIf && <Badge tone="violet">{t("fu.whatIf")}</Badge>}
            <div className="num">{t("fu.fingerprint")}: {whatIf ? whatIf.meta.input_fingerprint : d.simulation.input_fingerprint} · {num(whatIf ? whatIf.meta.elapsed_ms : d.simulation.elapsed_ms, 0)} ms</div>
            {whatIf && can("simulation.run") && (
              <Button size="sm" variant="outline" icon={Save} onClick={() => sim.mutate(true)} disabled={!!whatIf.meta.simulation_run_id}>
                {whatIf.meta.simulation_run_id ? t("fu.saved") : t("fu.save")}
              </Button>
            )}
            <ErrorBox error={sim.error} />
          </div>
        </Card>
        <div className="min-w-0 space-y-5">
          {whatIf && (
            <div className="flex items-center gap-2 rounded-xl border border-warn/40 bg-warn/5 p-3 text-xs text-ink2">
              <ShieldAlert className="h-4 w-4 text-warn" />
              {pick("Governance verdicts and agent findings shown below refer to the analysed run. Re-run the analysis to re-evaluate them with these controls.",
                "أحكام الحوكمة ونتائج الوكلاء تخص التشغيل المحلَّل. أعد التحليل لإعادة تقييمها بهذه الضوابط.")}
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-3">
            {KEYS.map((k, i) => (
              <FutureCard key={k} k={k} f={results[k]} gov={govByKey[k]} recommended={rec.recommended_strategy === k} i={i} />
            ))}
          </div>
          <Card title={t("fu.savingsPath")}>
            <FanChart unit="EGP M/yr" series={KEYS.map((k) => ({ key: k, band: results[k].trajectory.savings_run_rate }))}
              highlightMonth={controls.implementation_months} />
          </Card>
          <Card title={t("fu.compare")}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[600px] text-xs">
                <thead><tr className="border-b border-line text-muted">
                  <th className="p-2 text-start" />
                  <th className="p-2 text-end"><FutureChip k="BASELINE" /></th>
                  {KEYS.map((k) => <th key={k} className="p-2 text-end"><FutureChip k={k} /></th>)}
                </tr></thead>
                <tbody>
                  {metrics.map(([l, fn]) => (
                    <tr key={l} className="border-b border-line/40">
                      <td className="p-2 text-muted">{l}</td>
                      <td className="p-2 text-end num text-muted">{fn(results.BASELINE)}</td>
                      {KEYS.map((k) => <td key={k} className="p-2 text-end font-medium num">{fn(results[k])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px] text-muted">{pick("Medians over Monte Carlo iterations. Estimates — not facts.", "قيم وسيطة عبر تكرارات مونت كارلو. تقديرات — وليست حقائق.")}</p>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function ThreeFutures() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader icon={GitCompareArrows} title={t("fu.title")} subtitle={t("fu.subtitle")} />
      <DecisionGate>{(d, id) => <Futures d={d} decisionId={id} />}</DecisionGate>
    </div>
  );
}
