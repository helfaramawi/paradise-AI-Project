import { useI18n } from "@/lib/app";
import { Select, SliderField, Toggle } from "./ui";

export type Controls = {
  domain: "opex" | "collections";
  cost_reduction_target_pct: number;
  implementation_months: number;
  no_terminations: boolean;
  max_utilization_pct: number;
  automation_investment: number;
  acceptable_delay_increase_pct: number;
  min_csat_pct: number;
  risk_tolerance: "low" | "medium" | "high";
  implementation_budget: number;
};

export const DEFAULT_CONTROLS: Controls = {
  domain: "opex",
  cost_reduction_target_pct: 20,
  implementation_months: 6,
  no_terminations: true,
  max_utilization_pct: 85,
  automation_investment: 6,
  acceptable_delay_increase_pct: 2,
  min_csat_pct: 85,
  risk_tolerance: "medium",
  implementation_budget: 12,
};

export function pickControls(c: Record<string, unknown>): Controls {
  const out = { ...DEFAULT_CONTROLS };
  for (const k of Object.keys(DEFAULT_CONTROLS) as (keyof Controls)[]) if (k in c) (out as any)[k] = c[k];
  return out;
}

export function ControlsForm({ value, onChange, compact, wide }: { value: Controls; onChange: (c: Controls) => void; compact?: boolean; wide?: boolean }) {
  const { t, num, pct, egp } = useI18n();
  const set = <K extends keyof Controls>(k: K, v: Controls[K]) => onChange({ ...value, [k]: v });
  return (
    <div className={compact ? "space-y-4" : wide ? "grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5" : "grid gap-5 md:grid-cols-2"}>
      <SliderField label={t("in.target")} value={value.cost_reduction_target_pct} min={2} max={value.domain === "collections" ? 60 : 40} step={1}
        onChange={(v) => set("cost_reduction_target_pct", v)} format={(v) => pct(v, 0)} />
      <SliderField label={t("in.duration")} value={value.implementation_months} min={3} max={12} step={1}
        onChange={(v) => set("implementation_months", v)} format={(v) => `${num(v, 0)} ${t("months")}`} />
      <SliderField label={t("in.automation")} value={value.automation_investment} min={0} max={value.domain === "collections" ? 10 : 20} step={0.5}
        onChange={(v) => set("automation_investment", v)} format={(v) => egp(v, 1)} />
      <SliderField label={t("in.delay")} value={value.acceptable_delay_increase_pct} min={0} max={10} step={0.5}
        onChange={(v) => set("acceptable_delay_increase_pct", v)} format={(v) => `${num(v, 1)} ${t("pts")}`} />
      <SliderField label={t("in.maxUtil")} value={value.max_utilization_pct} min={75} max={95} step={1}
        onChange={(v) => set("max_utilization_pct", v)} format={(v) => pct(v, 0)} />
      <SliderField label={t("in.csat")} value={value.min_csat_pct} min={75} max={90} step={0.5}
        onChange={(v) => set("min_csat_pct", v)} format={(v) => pct(v, 1)} />
      <SliderField label={t("in.budget")} value={value.implementation_budget} min={2} max={30} step={1}
        onChange={(v) => set("implementation_budget", v)} format={(v) => egp(v, 0)} />
      <label className="block">
        <div className="mb-1 text-xs font-medium text-ink2">{t("in.risk")}</div>
        <Select className="w-full" value={value.risk_tolerance} onChange={(e) => set("risk_tolerance", e.target.value as Controls["risk_tolerance"])}>
          <option value="low">{t("risk.low")}</option>
          <option value="medium">{t("risk.medium")}</option>
          <option value="high">{t("risk.high")}</option>
        </Select>
      </label>
      <Toggle label={t("in.noTerm")} checked={value.no_terminations} onChange={(v) => set("no_terminations", v)} />
    </div>
  );
}
