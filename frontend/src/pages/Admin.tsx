import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Octagon, ShieldCheck, ShieldX, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth, useI18n } from "@/lib/app";
import { usePlatform } from "@/lib/hooks";
import { Badge, Button, Card, ErrorBox, Input, PageHeader, Toggle } from "@/components/ui";

export default function Admin() {
  const { t, date } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const platform = usePlatform();
  const users = useQuery({ queryKey: ["users"], queryFn: () => api<any[]>("/admin/users"), enabled: can("admin.users") });
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api<any[]>("/admin/roles"), enabled: can("admin.users") });
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => api("/admin/audit?limit=100"), enabled: can("admin.audit") });
  const [reason, setReason] = useState("");
  const stop = useMutation({
    mutationFn: (active: boolean) => api("/admin/emergency-stop", { method: "POST", json: { active, reason } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const setActive = useMutation({
    mutationFn: ({ id, v }: { id: string; v: boolean }) => api(`/admin/users/${id}`, { method: "PATCH", json: { is_active: v } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
  const p: any = platform.data;
  return (
    <div>
      <PageHeader icon={Users} title={t("ad.title")} />
      <div className="grid gap-5 xl:grid-cols-3">
        <Card title={t("ad.estop")} className={p?.emergency_stop ? "border-critical" : ""}>
          <p className="text-xs text-muted">Cancels running analyses and blocks new runs for this tenant. Audited.</p>
          {can("admin.emergency_stop") ? (
            <div className="mt-3 space-y-2">
              <Input placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
              {p?.emergency_stop
                ? <Button className="w-full" variant="outline" onClick={() => stop.mutate(false)}>{t("ad.estopOff")}</Button>
                : <Button className="w-full" variant="danger" icon={Octagon} onClick={() => stop.mutate(true)}>{t("ad.estopOn")}</Button>}
              <ErrorBox error={stop.error} />
            </div>
          ) : <Badge>read-only</Badge>}
        </Card>
        <Card title={t("ad.platform")} className="xl:col-span-2">
          {p && (
            <dl className="grid gap-2 text-xs sm:grid-cols-2">
              {[["Tenant", p.tenant.name], ["LLM provider", `${p.llm.provider} (${p.llm.mode})`], ["External actions", String(p.external_actions_enabled)],
                ["n8n configured", String(p.n8n_configured)], ["Presentation pacing", `${p.presentation_pacing_ms} ms`], ["Environment", p.environment], ["Database", p.database]].map(([k, v]) => (
                <div key={k} className="flex justify-between rounded-lg border border-line p-2"><dt className="text-muted">{k}</dt><dd className="font-medium">{v}</dd></div>
              ))}
            </dl>
          )}
        </Card>
        {can("admin.users") && (
          <Card title={t("ad.users")} className="xl:col-span-3">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-xs">
                <thead><tr className="border-b border-line text-muted"><th className="p-2 text-start">Name</th><th className="p-2 text-start">Email</th><th className="p-2 text-start">Roles</th><th className="p-2">Active</th></tr></thead>
                <tbody>{users.data?.map((u) => (
                  <tr key={u.id} className="border-b border-line/40">
                    <td className="p-2 font-medium">{u.full_name}<div className="text-muted">{u.title}</div></td><td className="p-2">{u.email}</td>
                    <td className="p-2">{u.roles.map((r: string) => <Badge key={r} className="me-1">{r}</Badge>)}</td>
                    <td className="p-2"><Toggle label="" checked={u.is_active} onChange={(v) => setActive.mutate({ id: u.id, v })} /></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <ErrorBox error={setActive.error} />
            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-accent">RBAC matrix</summary>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                {roles.data?.map((r) => <div key={r.id} className="rounded-lg border border-line p-2"><b>{r.key}</b>: <span className="text-muted">{r.permissions.join(", ")}</span></div>)}
              </div>
            </details>
          </Card>
        )}
        {can("admin.audit") && (
          <Card title={t("ad.audit")} className="xl:col-span-3"
            action={audit.data && (audit.data.chain.valid
              ? <Badge tone="good" icon={ShieldCheck}>{t("ad.chainOk")} · {audit.data.chain.checked}</Badge>
              : <Badge tone="critical" icon={ShieldX}>{t("ad.chainBad")}</Badge>)}>
            <div className="max-h-96 overflow-auto scroll-thin">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-panel"><tr className="border-b border-line text-muted"><th className="p-2 text-start">#</th><th className="p-2 text-start">Time</th><th className="p-2 text-start">Actor</th><th className="p-2 text-start">Action</th><th className="p-2 text-start">Entity</th><th className="p-2 text-start">Hash</th></tr></thead>
                <tbody>{audit.data?.events.map((e: any) => (
                  <tr key={e.id} className="border-b border-line/40">
                    <td className="p-2 num">{e.id}</td><td className="p-2 text-muted">{date(e.ts)}</td><td className="p-2">{e.actor_type}</td>
                    <td className="p-2 font-medium">{e.action}</td><td className="p-2 text-muted">{e.entity_type}:{e.entity_id.slice(0, 8)}</td><td className="p-2 font-mono text-[10px] text-muted">{e.hash.slice(0, 12)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
