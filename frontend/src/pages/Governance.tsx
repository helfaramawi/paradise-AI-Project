import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, Play, Scale } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth, useI18n } from "@/lib/app";
import { AgentAvatar, Badge, Button, Card, ErrorBox, PageHeader, StatusBadge, Textarea, Toggle } from "@/components/ui";

const SAMPLE = {
  action: { type: "strategy.approve", actor_type: "agent", mode: "execute", external_write: true,
    levers: { workforce_termination: 0.1, contractor_reduction: 0.5 }, financial_impact: 8 },
  decision: { no_terminations: true, status: "analyzed" },
  analysis: { max_delay_increase_pct: 3, peak_utilization_pct: 90, hard_constraints_violated: ["C3"], critical_collisions: 1, implementation_cost_p90: 9 },
  dataset: { has_errors: true },
  platform: { external_actions_enabled: false },
};

export default function Governance() {
  const { t, pick, lang } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const pols = useQuery({ queryKey: ["policies"], queryFn: () => api<any[]>("/governance/policies") });
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => api<any[]>("/agents") });
  const [ctx, setCtx] = useState(JSON.stringify(SAMPLE, null, 2));
  const evaluate = useMutation({ mutationFn: () => api("/governance/evaluate", { method: "POST", json: { context: JSON.parse(ctx) } }) });
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => api(`/governance/policies/${id}`, { method: "PATCH", json: { enabled } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
  const r: any = evaluate.data;
  return (
    <div>
      <PageHeader icon={Scale} title={t("gv.title")} subtitle={t("gv.subtitle")} />
      <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
        <div className="space-y-3">
          {pols.data?.map((p) => (
            <div key={p.id} className="card p-4" data-testid={`policy-${p.code}`}>
              <div className="flex flex-wrap items-center gap-2">
                <code className="text-xs text-muted">{p.code}</code>
                <span className="font-semibold">{pick(p.name_en, p.name_ar)}</span>
                <Badge tone={p.effect === "deny" ? "critical" : p.effect === "require_approval" ? "warn" : "violet"}>{p.effect.replace(/_/g, " ")}</Badge>
                {p.locked && <Badge tone="neutral" icon={Lock}>{t("gv.locked")}</Badge>}
                <span className="ms-auto text-[11px] text-muted">v{p.version}</span>
                {can("governance.manage") && !p.locked && (
                  <Toggle label={t("gv.enabled")} checked={p.enabled} onChange={(v) => toggle.mutate({ id: p.id, enabled: v })} />
                )}
              </div>
              <p className="mt-1 text-xs text-ink2">{pick(p.description_en, p.description_ar)}</p>
              <details className="mt-1 text-[11px]">
                <summary className="cursor-pointer text-accent">rule</summary>
                <pre dir="ltr" className="mt-1 overflow-x-auto rounded-lg bg-panel2 p-2 text-[10px]">{JSON.stringify(p.rule, null, 2)}</pre>
              </details>
            </div>
          ))}
          <ErrorBox error={toggle.error} />
        </div>
        <div className="space-y-5">
          <Card title={t("gv.sandbox")} subtitle={t("gv.sandboxSub")}>
            <Textarea dir="ltr" rows={14} className="font-mono text-[11px]" value={ctx} onChange={(e) => setCtx(e.target.value)} />
            <Button className="mt-2 w-full" icon={Play} onClick={() => evaluate.mutate()} loading={evaluate.isPending} data-testid="evaluate">{t("gv.evaluate")}</Button>
            <ErrorBox error={evaluate.error} />
            {r && (
              <div className="mt-3 space-y-2 text-xs" data-testid="sandbox-result">
                <div className="flex items-center gap-2"><StatusBadge status={r.outcome} />
                  {r.required_roles.length > 0 && <span className="uppercase">{r.required_roles.join(" · ")}</span>}</div>
                {r.policy_results.filter((x: any) => x.matched).map((x: any) => (
                  <div key={x.code} className="rounded-lg border border-line p-2"><code>{x.code}</code> <Badge tone={x.effect === "deny" ? "critical" : "warn"}>{x.effect}</Badge>
                    <div className="mt-0.5 text-ink2">{lang === "ar" ? x.message_ar : x.message_en}</div></div>
                ))}
              </div>
            )}
          </Card>
          <Card title={t("gv.authority")}>
            <ul className="space-y-2">
              {agents.data?.map((a) => (
                <li key={a.key} className="flex items-center gap-2 text-xs">
                  <AgentAvatar k={a.key} size={26} />
                  <span className="flex-1 font-medium">{pick(a.name_en, a.name_ar)}</span>
                  <Badge tone={a.authority.can_execute ? "critical" : "good"}>{t("gv.canExecute")}: {a.authority.can_execute ? "yes" : "no"}</Badge>
                </li>
              ))}
            </ul>
            <div className="mt-2 text-[11px] text-muted">{t("gv.tools")}: {agents.data?.[0]?.authority.tools.join(", ")} · max {agents.data?.[0]?.authority.max_runtime_seconds}s</div>
          </Card>
        </div>
      </div>
    </div>
  );
}
