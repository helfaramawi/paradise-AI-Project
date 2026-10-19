import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Clock3, Pause, Play } from "lucide-react";
import { useI18n } from "@/lib/app";
import { DecisionContextBar, DecisionGate } from "@/components/DecisionGate";
import { FanChart } from "@/components/charts";
import { Button, Card, FUTURE_COLOR, FutureChip, PageHeader, Tabs, cn } from "@/components/ui";
import type { DictKey } from "@/i18n/dict";

const STOPS = [0, 1, 3, 6, 12];
type Metric = { key: string; label: DictKey; unit: "egp" | "pct" | "pts" | "days"; better: "up" | "down" };
const COLLECTIONS_METRICS: Metric[] = [
  { key: "collections_monthly", label: "tm.collections", unit: "egp", better: "up" },
  { key: "overdue_balance", label: "tm.overdue", unit: "egp", better: "down" },
  { key: "dso_days", label: "tm.dso", unit: "days", better: "down" },
];
const HOTEL_METRICS: Metric[] = [
  { key: "occupancy_pct", label: "tm.occupancy", unit: "pct", better: "up" },
  { key: "owner_net_return", label: "tm.ownerNet", unit: "egp", better: "up" },
];
const BASE_METRICS: Metric[] = [
  { key: "opex_monthly", label: "tm.opex", unit: "egp", better: "down" },
  { key: "revenue_monthly", label: "tm.revenue", unit: "egp", better: "up" },
  { key: "cash_flow_monthly", label: "tm.cashflow", unit: "egp", better: "up" },
  { key: "cash_balance", label: "tm.cash", unit: "egp", better: "up" },
  { key: "savings_run_rate", label: "tm.savings", unit: "egp", better: "up" },
  { key: "delay_pct", label: "tm.delay", unit: "pct", better: "down" },
  { key: "utilization_pct", label: "tm.util", unit: "pct", better: "down" },
  { key: "csat_pct", label: "tm.csat", unit: "pct", better: "up" },
  { key: "risk_exposure", label: "tm.exposure", unit: "egp", better: "down" },
];

function Machine({ d, decisionId }: { d: any; decisionId: string }) {
  const { t, num, egp, pct, lang } = useI18n();
  const res = d.simulation.results;
  // Collections decisions also track collections, the overdue book and DSO, hotel decisions occupancy and the
  // owner's net return; show what the model produced.
  const METRICS = [...COLLECTIONS_METRICS, ...HOTEL_METRICS, ...BASE_METRICS].filter((m) => res.A?.trajectory?.[m.key]);
  const [month, setMonth] = useState(0);
  const [focus, setFocus] = useState<"A" | "B" | "C">((d.run.result.recommendation.recommended_strategy as "A" | "B" | "C") || "B");
  const [chartMetric, setChartMetric] = useState("cash_balance");
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setMonth((m) => { if (m >= 12) { setPlaying(false); return 12; } return m + 1; }), 650);
    return () => clearInterval(id);
  }, [playing]);
  const fmt = (u: string, v: number) => (u === "egp" ? egp(v, 2) : u === "pct" ? pct(v, 1) : u === "days" ? `${num(v, 0)} ${t("days")}` : num(v, 1));
  const f = res[focus];
  return (
    <div>
      <DecisionContextBar dossier={d} decisionId={decisionId} />
      <Card className="mb-5">
        <div className="flex flex-wrap items-center gap-4">
          <Button variant="subtle" size="sm" icon={playing ? Pause : Play} onClick={() => { if (month >= 12) setMonth(0); setPlaying(!playing); }}>
            {playing ? "Pause" : "Play"}
          </Button>
          <div className="flex gap-1.5" data-testid="tm-stops">
            {STOPS.map((s) => (
              <button key={s} onClick={() => setMonth(s)}
                className={cn("rounded-xl border px-3 py-1.5 text-xs font-semibold transition",
                  month === s ? "border-accent bg-accent/15 text-ink" : "border-line text-muted hover:text-ink")}>
                {s === 0 ? t("today") : `${t("month")} ${num(s, 0)}`}
              </button>
            ))}
          </div>
          <Tabs value={focus} onChange={setFocus} items={(["A", "B", "C"] as const).map((k) => ({ value: k, label: <FutureChip k={k} /> }))} />
        </div>
        <div className="mt-5" dir="ltr">
          <input type="range" min={0} max={12} value={month} onChange={(e) => setMonth(Number(e.target.value))}
            className="w-full" aria-label="timeline" style={lang === "ar" ? { direction: "rtl" } : undefined} />
          <div className="mt-1 flex justify-between text-[10px] text-muted num" style={lang === "ar" ? { flexDirection: "row-reverse" } : undefined}>
            {Array.from({ length: 13 }, (_, i) => <span key={i}>{num(i, 0)}</span>)}
          </div>
        </div>
      </Card>

      <div className="mb-2 flex items-center gap-2">
        <h3 className="font-display text-lg font-semibold">{t("tm.state")}</h3>
        <span className="text-sm text-muted">— <FutureChip k={focus} /> · {month === 0 ? t("today") : `${t("month")} ${num(month, 0)}`}</span>
      </div>
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5" data-testid="tm-tiles">
        {METRICS.map((m, i) => {
          const tr = f.trajectory[m.key];
          const v = tr.expected[month];
          const v0 = tr.expected[0];
          const delta = v - v0;
          const good = m.better === "up" ? delta > 0 : delta < 0;
          return (
            <motion.div key={m.key} layout className="card p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.02 }}>
              <div className="label">{t(m.label)}</div>
              <motion.div key={`${focus}-${month}`} initial={{ opacity: 0.3, y: 4 }} animate={{ opacity: 1, y: 0 }}
                className="mt-2 font-display text-xl font-semibold num">{fmt(m.unit, v)}</motion.div>
              <div className="mt-0.5 text-[10px] text-muted num">{t("range")}: {fmt(m.unit, tr.p10[month])} – {fmt(m.unit, tr.p90[month])}</div>
              {month > 0 && Math.abs(delta) > 1e-6 && (
                <div className={cn("mt-1 flex items-center gap-1 text-[11px] font-medium", good ? "text-good" : "text-critical dark:text-red-400")}>
                  {delta > 0 ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                  {fmt(m.unit, Math.abs(delta))} {t("tm.vsToday")}
                </div>
              )}
            </motion.div>
          );
        })}
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title={`${t("tm.compare")} ${month === 0 ? t("today") : `${t("month")} ${num(month, 0)}`}`}>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-line">
                <th className="p-2 text-start" />
                {["BASELINE", "A", "B", "C"].map((k) => <th key={k} className="p-2 text-end"><FutureChip k={k} /></th>)}
              </tr></thead>
              <tbody>
                {METRICS.map((m) => (
                  <tr key={m.key} className="border-b border-line/40">
                    <td className="p-2 text-muted">{t(m.label)}</td>
                    {["BASELINE", "A", "B", "C"].map((k) => (
                      <td key={k} className={cn("p-2 text-end num", k === focus && "font-semibold text-ink")}>{fmt(m.unit, res[k].trajectory[m.key].expected[month])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title={t(METRICS.find((m) => m.key === chartMetric)!.label)}
          action={
            <select value={chartMetric} onChange={(e) => setChartMetric(e.target.value)} className="rounded-lg border border-line bg-panel px-2 py-1 text-xs">
              {METRICS.map((m) => <option key={m.key} value={m.key}>{t(m.label)}</option>)}
            </select>
          }>
          <FanChart height={250} highlightMonth={month}
            series={(["A", "B", "C"] as const).map((k) => ({ key: k, band: res[k].trajectory[chartMetric] }))} />
          <div className="mt-2 flex gap-3 text-[11px] text-muted">
            {(["A", "B", "C"] as const).map((k) => <span key={k} className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: FUTURE_COLOR[k] }} />{num(res[k].trajectory[chartMetric].expected[month], 2)}</span>)}
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function TimeMachine() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader icon={Clock3} title={t("tm.title")} subtitle={t("tm.subtitle")} />
      <DecisionGate>{(d, id) => <Machine d={d} decisionId={id} />}</DecisionGate>
    </div>
  );
}
