import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { useI18n } from "@/lib/app";
import { DecisionContextBar, DecisionGate } from "@/components/DecisionGate";
import { Histogram, Tornado } from "@/components/charts";
import { Bar, Card, FUTURE_COLOR, FutureChip, PageHeader, StatusBadge, Tabs } from "@/components/ui";

function Risk({ d, decisionId }: { d: any; decisionId: string }) {
  const { t, pick, prob, egp, dir, domain } = useI18n();
  const col = domain === "collections";
  const res = d.simulation.results;
  const [k, setK] = useState<"A" | "B" | "C">((d.run.result.recommendation.recommended_strategy as any) || "B");
  const f = res[k];
  const risks = d.risks.filter((r: any) => r.scenario_key === k);
  const probs: [string, number][] = [
    [col ? pick("Meet collections target", "تحقيق هدف المتحصلات") : pick("Meet savings target", "تحقيق هدف الوفورات"), f.probabilities.meet_target],
    [col ? pick("Complaints within acceptable limit", "الشكاوى ضمن الحد المقبول") : pick("Delay within acceptable limit", "تأخير ضمن الحد المقبول"),
      f.probabilities.delay_within_acceptable],
    [pick("CSAT maintained", "الحفاظ على رضا العملاء"), f.probabilities.csat_maintained],
    [pick("Positive 12m net benefit", "صافي منفعة موجب"), f.probabilities.positive_net_benefit_12m],
    [col ? pick("Key-account attrition within limit", "فقد كبار العملاء ضمن الحد") : pick("No contractual breach", "عدم الإخلال التعاقدي"),
      1 - f.probabilities.contractual_breach],
  ];
  return (
    <div>
      <DecisionContextBar dossier={d} decisionId={decisionId} />
      <div className="mb-4"><Tabs value={k} onChange={setK} items={(["A", "B", "C"] as const).map((x) => ({ value: x, label: <FutureChip k={x} /> }))} /></div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Card title={t("rk.probs")} subtitle={`n=${d.simulation.iterations} · ${pick("required", "المطلوب")} ≥ ${prob(d.simulation.meta.required_probability)}`}>
          <div className="space-y-3">
            {probs.map(([l, p]) => (
              <div key={l}>
                <div className="mb-1 flex justify-between text-xs"><span className="text-ink2">{l}</span><span className="font-semibold num">{prob(p)}</span></div>
                <Bar value={p} color={p >= d.simulation.meta.required_probability ? "#0ca30c" : "#d03b3b"} />
              </div>
            ))}
          </div>
        </Card>
        <Card title={t("rk.matrix")}>
          <ResponsiveContainer width="100%" height={240}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
              <CartesianGrid />
              <XAxis type="number" dataKey="probability" domain={[0, 1]} reversed={dir === "rtl"} tickFormatter={(v) => `${Math.round(v * 100)}%`} name={t("probability")} />
              <YAxis type="number" dataKey="impact_egp_m" name={t("rk.impact")} orientation={dir === "rtl" ? "right" : "left"} width={40} />
              <ZAxis range={[90, 90]} />
              <Tooltip contentStyle={{ background: "rgb(var(--panel))", border: "1px solid rgb(var(--line))", borderRadius: 12, fontSize: 12 }}
                formatter={(v: number, n: string) => [n === t("probability") ? prob(v) : egp(v, 2), n]}
                labelFormatter={() => ""} />
              <Scatter data={risks} fill={FUTURE_COLOR[k]} />
            </ScatterChart>
          </ResponsiveContainer>
        </Card>
        <Card title={t("rk.register")} className="xl:col-span-2">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-xs">
              <thead><tr className="border-b border-line text-muted">
                <th className="p-2 text-start">Risk</th><th className="p-2 text-end">{t("probability")}</th><th className="p-2 text-end">{t("rk.impact")}</th>
                <th className="p-2">{t("severity")}</th><th className="p-2 text-start">{t("rk.mitigation")}</th><th className="p-2 text-start">{t("rk.basis")}</th>
              </tr></thead>
              <tbody>
                {risks.map((r: any) => (
                  <tr key={r.id} className="border-b border-line/40 align-top">
                    <td className="p-2 font-medium">{pick(r.title_en, r.title_ar)}</td>
                    <td className="p-2 text-end num">{prob(r.probability)}</td>
                    <td className="p-2 text-end num">{egp(r.impact_egp_m, 2)}</td>
                    <td className="p-2 text-center"><StatusBadge status={r.severity} /></td>
                    <td className="p-2 text-ink2">{pick(r.mitigation_en, r.mitigation_ar)}</td>
                    <td className="p-2 text-muted">{r.basis}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title={t("rk.drivers")}><Tornado rows={f.sensitivity} base={f.sensitivity[0]?.base_net_benefit ?? 0} /></Card>
        <Card title={`${t("rk.dist")} — ${t("fu.net")}`}>
          <Histogram counts={f.net_benefit_histogram.counts} edges={f.net_benefit_histogram.edges} color={FUTURE_COLOR[k]} height={240} />
          <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
            {(["worst", "base", "best"] as const).map((c) => (
              <div key={c} className="rounded-lg border border-line p-2">
                <div className="label">{c === "worst" ? "P10" : c === "base" ? "P50" : "P90"}</div>
                <div className="font-semibold num">{egp(f.cases[c].net_benefit_12m)}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function RiskExplorer() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader icon={ShieldCheck} title={t("rk.title")} subtitle={t("rk.subtitle")} />
      <DecisionGate>{(d, id) => <Risk d={d} decisionId={id} />}</DecisionGate>
    </div>
  );
}
