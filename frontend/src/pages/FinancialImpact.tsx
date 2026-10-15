import { Gauge } from "lucide-react";
import { useI18n } from "@/lib/app";
import { DecisionContextBar, DecisionGate } from "@/components/DecisionGate";
import { FanChart, GroupedBars } from "@/components/charts";
import { Card, FutureChip, PageHeader } from "@/components/ui";

function Financial({ d, decisionId }: { d: any; decisionId: string }) {
  const { t, egp, pick } = useI18n();
  const res = d.simulation.results;
  const keys = ["A", "B", "C"];
  const bridge = [
    { name: t("fin.realized"), ...Object.fromEntries(keys.map((k) => [k, res[k].summary.realized_savings_12m.p50])) },
    { name: t("fin.impl"), ...Object.fromEntries(keys.map((k) => [k, -res[k].summary.implementation_cost_12m.p50])) },
    { name: t("fin.delivery"), ...Object.fromEntries(keys.map((k) => [k, -res[k].summary.delivery_loss_12m.p50])) },
    { name: t("fin.net"), ...Object.fromEntries(keys.map((k) => [k, res[k].summary.net_benefit_12m.p50])) },
  ];
  return (
    <div>
      <DecisionContextBar dossier={d} decisionId={decisionId} />
      <div className="mb-5 grid gap-3 md:grid-cols-4">
        {["BASELINE", ...keys].map((k) => (
          <div key={k} className="card p-4">
            <FutureChip k={k} />
            <div className="mt-2 label">{t("fin.profit")}</div>
            <div className="font-display text-2xl font-semibold num">{egp(res[k].summary.projected_operating_profit_12m.p50)}</div>
            <div className="text-[11px] text-muted num">{t("range")} {egp(res[k].summary.projected_operating_profit_12m.p10)} – {egp(res[k].summary.projected_operating_profit_12m.p90)}</div>
          </div>
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Card title={t("fin.waterfall")} subtitle={pick("Estimate · EGP M · median of Monte Carlo", "تقدير · مليون جنيه · وسيط مونت كارلو")}>
          <GroupedBars data={bridge} keys={keys} unit="EGP M" height={280} />
        </Card>
        <Card title={t("fin.cashBalance")}>
          <FanChart unit="EGP M" series={["BASELINE", ...keys].map((k) => ({ key: k, band: res[k].trajectory.cash_balance }))} />
        </Card>
        <Card title={t("fin.opex")}>
          <FanChart unit="EGP M" series={["BASELINE", ...keys].map((k) => ({ key: k, band: res[k].trajectory.opex_monthly }))} />
        </Card>
        <Card title={t("tm.cashflow")}>
          <FanChart unit="EGP M" series={keys.map((k) => ({ key: k, band: res[k].trajectory.cash_flow_monthly }))} />
        </Card>
      </div>
      <p className="mt-4 text-[11px] text-muted">{pick(d.dataset.validation.interpretation_en, d.dataset.validation.interpretation_ar)}</p>
    </div>
  );
}

export default function FinancialImpact() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader icon={Gauge} title={t("fin.title")} subtitle={t("fin.subtitle")} />
      <DecisionGate>{(d, id) => <Financial d={d} decisionId={id} />}</DecisionGate>
    </div>
  );
}
