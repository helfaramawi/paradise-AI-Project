import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Beaker, Sparkles } from "lucide-react";
import { CartesianGrid, ComposedChart, Area, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { api } from "@/lib/api";
import { useAuth, useI18n } from "@/lib/app";
import { DecisionContextBar, DecisionGate } from "@/components/DecisionGate";
import { Badge, Button, Card, ErrorBox, FutureChip, Input, PageHeader, Select, Stat } from "@/components/ui";

function Loop({ d, decisionId }: { d: any; decisionId: string }) {
  const { t, pick, num, prob, dir } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["outcomes", decisionId], queryFn: () => api(`/decisions/${decisionId}/outcomes`) });
  const [metric, setMetric] = useState("delay_pct");
  const [month, setMonth] = useState(1);
  const [value, setValue] = useState("");
  const inv = () => qc.invalidateQueries({ queryKey: ["outcomes", decisionId] });
  const demo = useMutation({ mutationFn: () => api(`/decisions/${decisionId}/outcomes/synthetic-demo`, { method: "POST" }), onSuccess: inv });
  const rec = useMutation({ mutationFn: () => api(`/decisions/${decisionId}/outcomes`, { method: "POST", json: [{ month, metric, value: Number(value) }] }), onSuccess: inv });
  const propose = useMutation({ mutationFn: () => api(`/decisions/${decisionId}/calibration-proposal`, { method: "POST" }) });
  const o: any = q.data;
  const scenario = o?.scenario_key || d.decision.recommended_strategy || "B";
  const traj = d.simulation.results[scenario].trajectory[metric];
  const comps = o?.comparisons.filter((c: any) => c.metric === metric) || [];
  const data = traj.expected.map((_: number, m: number) => ({
    m, band: [traj.p10[m], traj.p90[m]], pred: traj.expected[m], actual: comps.find((c: any) => c.month === m)?.actual,
  }));
  const cal = o?.calibration;
  const mc = cal?.metrics?.[metric];
  return (
    <div>
      <DecisionContextBar dossier={d} decisionId={decisionId} />
      <div className="mb-5 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted">{t("oc.tracked")}:</span><FutureChip k={scenario} />
        {o?.actuals?.some((a: any) => a.is_synthetic) && <Badge tone="warn">{t("oc.syntheticNote")}</Badge>}
      </div>
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={t("oc.coverage")} value={cal?.overall_interval_coverage != null ? prob(cal.overall_interval_coverage) : "—"} sub={`nominal ${prob(0.8)}`}
          tone={cal?.overall_interval_coverage != null ? (cal.overall_interval_coverage >= 0.6 ? "good" : "critical") : undefined} />
        <Stat label={`${t("oc.mape")} (${metric})`} value={mc ? `${num(mc.mape_pct, 1)}%` : "—"} />
        <Stat label={`${t("oc.bias")} (${metric})`} value={mc ? `${num(mc.bias_pct, 1)}%` : "—"} />
        <Stat label="n" value={num(o?.comparisons?.length ?? 0, 0)} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
        <Card title={pick(o?.metrics?.[metric]?.en, o?.metrics?.[metric]?.ar) || metric}
          action={<Select value={metric} onChange={(e) => setMetric(e.target.value)} className="h-8 text-xs">
            {o && Object.entries(o.metrics).map(([k, v]: any) => <option key={k} value={k}>{pick(v.en, v.ar)}</option>)}
          </Select>}>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={data}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="m" reversed={dir === "rtl"} tickFormatter={(v) => (v === 0 ? t("today") : `${t("month")} ${v}`)} />
              <YAxis domain={["auto", "auto"]} orientation={dir === "rtl" ? "right" : "left"} width={48} tickFormatter={(v) => num(v, 1)} />
              <Tooltip contentStyle={{ background: "rgb(var(--panel))", border: "1px solid rgb(var(--line))", borderRadius: 12, fontSize: 12 }}
                formatter={(v: any, n: string) => [Array.isArray(v) ? `${num(v[0], 2)} – ${num(v[1], 2)}` : num(v, 2), n]} />
              <Legend />
              <Area dataKey="band" name="P10–P90" stroke="none" fill="var(--fa)" fillOpacity={0.15} />
              <Line dataKey="pred" name={t("expected")} stroke="var(--fa)" strokeWidth={2} dot={false} />
              <Scatter dataKey="actual" name={pick("Actual", "الفعلي")} fill="var(--fb)" shape="diamond" />
            </ComposedChart>
          </ResponsiveContainer>
          {!o?.comparisons?.length && <p className="text-sm text-muted">{t("oc.none")}</p>}
        </Card>
        <div className="space-y-5">
          {can("outcome.record") && (
            <Card title={t("oc.record")}>
              <div className="grid grid-cols-2 gap-2">
                <Input type="number" min={1} max={12} value={month} onChange={(e) => setMonth(Number(e.target.value))} aria-label={t("month")} />
                <Input type="number" step="0.01" placeholder={t("oc.value")} value={value} onChange={(e) => setValue(e.target.value)} />
              </div>
              <Button className="mt-2 w-full" size="sm" onClick={() => rec.mutate()} disabled={!value} loading={rec.isPending}>{t("save")}</Button>
              <Button className="mt-2 w-full" size="sm" variant="outline" icon={Beaker} onClick={() => demo.mutate()} loading={demo.isPending} data-testid="demo-actuals">
                {t("oc.demo")}
              </Button>
              <ErrorBox error={rec.error || demo.error} />
            </Card>
          )}
          <Card title={t("oc.diagnostics")}>
            {cal?.diagnostics?.length ? (
              <ul className="space-y-2 text-xs">
                {cal.diagnostics.map((x: any, i: number) => (
                  <li key={i} className="rounded-lg border border-warn/40 bg-warn/5 p-2">
                    <code className="text-[10px] text-muted">{x.metric} → {x.parameter} ({x.direction})</code>
                    <div className="text-ink2">{pick(x.en, x.ar)}</div>
                  </li>
                ))}
              </ul>
            ) : <div className="text-sm text-muted">—</div>}
            {cal?.diagnostics?.length > 0 && can("outcome.record") && (
              <Button className="mt-3 w-full" size="sm" icon={Sparkles} onClick={() => propose.mutate()} loading={propose.isPending}>{t("oc.propose")}</Button>
            )}
            {propose.data?.created && <div className="mt-2 rounded-lg border border-accent2/40 bg-accent2/5 p-2 text-xs">{t("oc.candidate")} <code>{propose.data.candidate.version}</code></div>}
            <p className="mt-2 text-[11px] text-muted">{pick(cal?.note_en, cal?.note_ar)}</p>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function Outcomes() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader icon={Sparkles} title={t("oc.title")} subtitle={t("oc.subtitle")} />
      <DecisionGate>{(d, id) => <Loop d={d} decisionId={id} />}</DecisionGate>
    </div>
  );
}
