import { useState, type ReactNode } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useI18n } from "@/lib/app";
import { FUTURE_COLOR, futureLabel, Tabs } from "./ui";

export type Band = { expected: number[]; p10: number[]; p50: number[]; p90: number[] };

const tooltipStyle = {
  contentStyle: {
    background: "rgb(var(--panel))",
    border: "1px solid rgb(var(--line))",
    borderRadius: 12,
    fontSize: 12,
    color: "rgb(var(--ink))",
  },
  labelStyle: { color: "rgb(var(--muted))" },
};

function WithTable({ table, children }: { table: ReactNode; children: ReactNode }) {
  const { t } = useI18n();
  const [mode, setMode] = useState<"chart" | "table">("chart");
  return (
    <div>
      <div className="mb-2 flex justify-end">
        <Tabs value={mode} onChange={setMode} items={[{ value: "chart", label: t("chartView") }, { value: "table", label: t("tableView") }]} />
      </div>
      {mode === "chart" ? children : <div className="max-h-72 overflow-auto scroll-thin">{table}</div>}
    </div>
  );
}

/** Median line + P10–P90 band per series over months. One y-axis. */
export function FanChart({ series, height = 260, unit = "", highlightMonth, yDomain }: {
  series: { key: string; band: Band }[];
  height?: number;
  unit?: string;
  highlightMonth?: number;
  yDomain?: [number | "auto", number | "auto"];
}) {
  const { lang, num, t, dir } = useI18n();
  const months = series[0]?.band.p50.length ?? 0;
  const data = Array.from({ length: months }, (_, m) => {
    const row: Record<string, number | number[] | string> = { m, label: m === 0 ? t("today") : `${t("month")} ${num(m, 0)}` };
    for (const s of series) {
      row[`${s.key}_band`] = [s.band.p10[m], s.band.p90[m]];
      row[`${s.key}_mid`] = s.band.p50[m];
    }
    return row;
  });
  const rtl = dir === "rtl";
  const table = (
    <table className="w-full text-xs num">
      <thead className="sticky top-0 bg-panel text-muted">
        <tr>
          <th className="p-1.5 text-start">{t("month")}</th>
          {series.map((s) => (
            <th key={s.key} className="p-1.5 text-end">{futureLabel(s.key, lang)} ({t("median")} [{t("range")}])</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((r, i) => (
          <tr key={i} className="border-t border-line/50">
            <td className="p-1.5">{r.label as string}</td>
            {series.map((s) => (
              <td key={s.key} className="p-1.5 text-end">
                {num(s.band.p50[i], 2)} [{num(s.band.p10[i], 2)}–{num(s.band.p90[i], 2)}]
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
  return (
    <WithTable table={table}>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="label" reversed={rtl} tickLine={false} axisLine={{ stroke: "var(--axis)" }} interval="preserveStartEnd" />
          <YAxis orientation={rtl ? "right" : "left"} tickLine={false} axisLine={false} width={48} domain={yDomain || ["auto", "auto"]}
            tickFormatter={(v) => num(v, Math.abs(v) < 10 ? 1 : 0)} />
          <Tooltip {...tooltipStyle}
            formatter={(v: unknown, name: string) => {
              const k = name.split("_")[0];
              const lbl = futureLabel(k, lang) + (name.endsWith("_band") ? ` ${t("range")}` : ` ${t("median")}`);
              const val = Array.isArray(v) ? `${num(v[0], 2)} – ${num(v[1], 2)}` : num(v as number, 2);
              return [`${val}${unit ? " " + unit : ""}`, lbl];
            }} />
          <Legend formatter={(v: string) => futureLabel(v.split("_")[0], lang)} payload={series.map((s) => ({
            value: `${s.key}_mid`, type: "line", color: FUTURE_COLOR[s.key], id: s.key }))} />
          {highlightMonth !== undefined && (
            <ReferenceLine x={data[highlightMonth]?.label as string} stroke="rgb(var(--accent2))" strokeDasharray="4 4" />
          )}
          {series.map((s) => (
            <Area key={`${s.key}_band`} dataKey={`${s.key}_band`} stroke="none" fill={FUTURE_COLOR[s.key]} fillOpacity={0.14}
              isAnimationActive={false} legendType="none" />
          ))}
          {series.map((s) => (
            <Line key={`${s.key}_mid`} dataKey={`${s.key}_mid`} stroke={FUTURE_COLOR[s.key]} strokeWidth={2} dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "rgb(var(--panel))" }} isAnimationActive />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </WithTable>
  );
}

/** Tornado: change in net benefit when each parameter moves to its low/high bound. */
export function Tornado({ rows, base, height }: {
  rows: { label_en: string; label_ar: string; net_benefit_at_low: number; net_benefit_at_high: number; swing: number }[];
  base: number;
  height?: number;
}) {
  const { lang, num, dir } = useI18n();
  const top = rows.slice(0, 8);
  const data = top.map((r) => ({
    name: lang === "ar" ? r.label_ar : r.label_en,
    low: r.net_benefit_at_low - base,
    high: r.net_benefit_at_high - base,
  }));
  const rtl = dir === "rtl";
  const table = (
    <table className="w-full text-xs num">
      <thead className="text-muted"><tr><th className="p-1.5 text-start">Parameter</th><th className="p-1.5 text-end">Low</th><th className="p-1.5 text-end">High</th></tr></thead>
      <tbody>{data.map((d) => <tr key={d.name} className="border-t border-line/50"><td className="p-1.5">{d.name}</td><td className="p-1.5 text-end">{num(d.low, 2)}</td><td className="p-1.5 text-end">{num(d.high, 2)}</td></tr>)}</tbody>
    </table>
  );
  return (
    <WithTable table={table}>
      <ResponsiveContainer width="100%" height={height || 34 * top.length + 40}>
        <BarChart data={data} layout="vertical" stackOffset="sign" margin={{ left: 8, right: 16 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} />
          <XAxis type="number" reversed={rtl} tickFormatter={(v) => num(v, 1)} tickLine={false} axisLine={false} />
          <YAxis type="category" dataKey="name" width={190} orientation={rtl ? "right" : "left"} tickLine={false} axisLine={false} />
          <Tooltip {...tooltipStyle} formatter={(v: number, n: string) => [num(v, 2) + " EGP M", n === "low" ? "Low bound Δ" : "High bound Δ"]} />
          <ReferenceLine x={0} stroke="var(--axis)" />
          <Bar dataKey="low" stackId="s" fill="var(--fb)" radius={4} />
          <Bar dataKey="high" stackId="s" fill="var(--fa)" radius={4} />
        </BarChart>
      </ResponsiveContainer>
    </WithTable>
  );
}

export function Histogram({ counts, edges, color = "var(--fa)", height = 200, unit = "EGP M" }: {
  counts: number[]; edges: number[]; color?: string; height?: number; unit?: string;
}) {
  const { num, dir } = useI18n();
  const total = counts.reduce((a, b) => a + b, 0) || 1;
  const data = counts.map((c, i) => ({ x: (edges[i] + edges[i + 1]) / 2, share: c / total, lo: edges[i], hi: edges[i + 1], neg: edges[i + 1] <= 0 }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} barCategoryGap={1}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="x" reversed={dir === "rtl"} tickFormatter={(v) => num(v, 1)} tickLine={false} />
        <YAxis tickFormatter={(v) => `${Math.round(v * 100)}%`} width={40} tickLine={false} axisLine={false} orientation={dir === "rtl" ? "right" : "left"} />
        <Tooltip {...tooltipStyle} labelFormatter={(_, p) => (p?.[0] ? `${num(p[0].payload.lo, 2)} – ${num(p[0].payload.hi, 2)} ${unit}` : "")}
          formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "share of iterations"]} />
        <Bar dataKey="share" radius={[4, 4, 0, 0]}>
          {data.map((d, i) => <Cell key={i} fill={d.neg ? "var(--fb)" : color} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GroupedBars({ data, keys, height = 220, unit = "" }: {
  data: Record<string, string | number>[]; keys: string[]; height?: number; unit?: string;
}) {
  const { lang, num, dir } = useI18n();
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} barGap={2}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="name" reversed={dir === "rtl"} tickLine={false} />
        <YAxis tickFormatter={(v) => num(v, 0)} width={44} tickLine={false} axisLine={false} orientation={dir === "rtl" ? "right" : "left"} />
        <Tooltip {...tooltipStyle} formatter={(v: number, n: string) => [`${num(v, 2)} ${unit}`, futureLabel(n, lang)]} />
        <Legend formatter={(v: string) => futureLabel(v, lang)} />
        <ReferenceLine y={0} stroke="var(--axis)" />
        {keys.map((k) => <Bar key={k} dataKey={k} fill={FUTURE_COLOR[k]} radius={4} maxBarSize={28} />)}
      </BarChart>
    </ResponsiveContainer>
  );
}
