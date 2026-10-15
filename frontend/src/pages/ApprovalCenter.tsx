import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, CheckCircle2, Info, Lock, ShieldAlert, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth, useI18n } from "@/lib/app";
import { useDossier, useResolvedDecisionId } from "@/lib/hooks";
import { DecisionPicker } from "@/components/DecisionGate";
import { Badge, Button, Card, Empty, ErrorBox, FUTURE_COLOR, FutureChip, PageHeader, Select, StatusBadge, Textarea, cn } from "@/components/ui";

function RequestCard({ a, actionable }: { a: any; actionable: boolean }) {
  const { t, pick, date } = useI18n();
  const { user } = useAuth();
  const qc = useQueryClient();
  const myRoles = user?.roles.map((r) => r.key).filter((r) => a.pending_roles.includes(r)) || [];
  const [role, setRole] = useState(myRoles[0] || "");
  const [comment, setComment] = useState("");
  const decide = useMutation({
    mutationFn: (verdict: string) => api(`/approvals/${a.id}/decide`, { method: "POST", json: { verdict, role_key: role, comment } }),
    onSuccess: () => { qc.invalidateQueries(); },
  });
  const snap = a.governance_snapshot;
  return (
    <div className={cn("card p-5", a.status === "blocked" && "border-critical/50")} data-testid="approval-card">
      <div className="flex flex-wrap items-center gap-2">
        <span className="h-3 w-3 rounded-full" style={{ background: FUTURE_COLOR[a.scenario_key] }} />
        <span className="font-semibold">{a.decision_title}</span>
        <FutureChip k={a.scenario_key} />
        <span className="ms-auto"><StatusBadge status={a.status} /></span>
      </div>
      <div className="mt-1 text-xs text-muted">{a.requested_by_name} · {date(a.created_at)}</div>
      {a.justification && <p className="mt-2 text-sm text-ink2">“{a.justification}”</p>}
      {a.status === "blocked" && (
        <div className="mt-3 rounded-xl border border-critical/40 bg-critical/5 p-3 text-xs">
          <div className="mb-1 flex items-center gap-1.5 font-semibold text-critical dark:text-red-300"><ShieldAlert className="h-4 w-4" />{t("ap.blocked")}</div>
          {snap.deny_reasons.map((r: any) => <div key={r.code}><code>{r.code}</code> — {pick(r.message_en, r.message_ar)}</div>)}
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {a.required_roles.map((r: string) => {
          const dd = a.decisions.find((x: any) => x.role_key === r);
          return (
            <Badge key={r} tone={dd?.verdict === "approve" ? "good" : dd ? "critical" : "warn"} icon={dd?.verdict === "approve" ? CheckCircle2 : dd ? XCircle : Lock}>
              {r.toUpperCase()}{dd ? ` · ${dd.approver_name}` : ""}
            </Badge>
          );
        })}
      </div>
      {a.decisions.filter((x: any) => x.comment).map((x: any) => (
        <div key={x.id} className="mt-2 text-xs text-muted">{x.approver_name} ({x.role_key}): {x.comment}</div>
      ))}
      {actionable && a.status === "pending" && myRoles.length > 0 && (
        <div className="mt-4 space-y-2 border-t border-line pt-3">
          <div className="flex items-center gap-2 text-xs">
            {t("ap.as")}
            <Select value={role} onChange={(e) => setRole(e.target.value)} className="h-8">
              {myRoles.map((r) => <option key={r} value={r}>{r.toUpperCase()}</option>)}
            </Select>
          </div>
          <Textarea rows={2} placeholder={t("ap.comment")} value={comment} onChange={(e) => setComment(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" icon={CheckCircle2} onClick={() => decide.mutate("approve")} loading={decide.isPending} data-testid="approve-btn">{t("ap.approve")}</Button>
            <Button size="sm" variant="outline" onClick={() => decide.mutate("request_analysis")}>{t("ap.analysis")}</Button>
            <Button size="sm" variant="danger" onClick={() => decide.mutate("reject")}>{t("ap.reject")}</Button>
          </div>
          <ErrorBox error={decide.error} />
        </div>
      )}
    </div>
  );
}

export default function ApprovalCenter() {
  const { t, pick } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const did = useResolvedDecisionId();
  const dossier = useDossier(did);
  const all = useQuery({ queryKey: ["approvals"], queryFn: () => api<any[]>("/approvals") });
  const inbox = useQuery({ queryKey: ["inbox"], queryFn: () => api<any[]>("/me/approval-inbox") });
  const rec = dossier.data?.run?.result?.recommendation;
  const [scenario, setScenario] = useState<string>("");
  const [just, setJust] = useState("");
  const [ack, setAck] = useState(false);
  const sel = scenario || rec?.recommended_strategy || "B";
  const submit = useMutation({
    mutationFn: () => api(`/decisions/${did}/approval-requests`, {
      method: "POST", json: { scenario_key: sel, justification: just, acknowledged: ack ? ["GOV-011"] : [] },
    }),
    onSuccess: () => { qc.invalidateQueries(); setJust(""); },
  });
  const gov = dossier.data?.governance?.find((g: any) => g.scenario_key === sel);
  return (
    <div>
      <PageHeader icon={BadgeCheck} title={t("ap.title")} subtitle={t("ap.subtitle")} />
      <div className="mb-5 grid gap-2 md:grid-cols-2">
        <div className="flex items-center gap-2 rounded-xl border border-accent2/40 bg-accent2/5 p-3 text-xs text-ink2"><Lock className="h-4 w-4 text-accent2" />{t("ap.sod")}</div>
        <div className="flex items-center gap-2 rounded-xl border border-good/40 bg-good/5 p-3 text-xs text-ink2"><Info className="h-4 w-4 text-good" />{t("ap.noExec")}</div>
      </div>
      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        <div className="space-y-5">
          {can("approval.request") && dossier.data?.run && (
            <Card title={t("ap.request")}>
              <div className="mb-3"><DecisionPicker value={did} /></div>
              <div className="grid grid-cols-3 gap-2">
                {["A", "B", "C"].map((k) => {
                  const g = dossier.data.governance.find((x: any) => x.scenario_key === k);
                  return (
                    <button key={k} onClick={() => setScenario(k)} data-testid={`pick-${k}`}
                      className={cn("rounded-xl border p-2 text-start transition", sel === k ? "border-accent bg-accent/10" : "border-line")}>
                      <FutureChip k={k} />
                      <div className="mt-1"><StatusBadge status={g?.outcome} /></div>
                    </button>
                  );
                })}
              </div>
              {gov && (
                <div className="mt-3 rounded-xl bg-panel2/60 p-3 text-xs">
                  {gov.outcome === "denied" ? (
                    gov.policy_results.filter((p: any) => p.matched && p.effect === "deny").map((p: any) => (
                      <div key={p.code} className="text-critical dark:text-red-300"><code>{p.code}</code> {pick(p.message_en, p.message_ar)}</div>
                    ))
                  ) : (
                    <div>{t("court.approvals")}: <b className="uppercase">{gov.required_roles.join(" · ")}</b></div>
                  )}
                </div>
              )}
              <Textarea className="mt-3" rows={3} placeholder={t("ap.justification")} value={just} onChange={(e) => setJust(e.target.value)} />
              {dossier.data.dataset.validation.has_errors && (
                <label className="mt-3 flex items-start gap-2 text-xs text-ink2">
                  <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-0.5" data-testid="ack" />
                  {t("ap.ack")}
                </label>
              )}
              <Button className="mt-3 w-full" onClick={() => submit.mutate()} loading={submit.isPending} data-testid="submit-approval">{t("ap.request")}</Button>
              <ErrorBox error={submit.error} />
            </Card>
          )}
          <Card title={t("ap.inbox")}>
            {inbox.data?.length ? <div className="space-y-3">{inbox.data.map((a) => <RequestCard key={a.id} a={a} actionable />)}</div>
              : <div className="text-sm text-muted">{t("ap.empty")}</div>}
          </Card>
        </div>
        <div>
          <h3 className="mb-3 font-display text-lg font-semibold">{t("ap.all")}</h3>
          {all.data?.length ? <div className="grid gap-4 lg:grid-cols-2">{all.data.map((a) => <RequestCard key={a.id} a={a} actionable />)}</div>
            : <Empty>{t("ap.empty")}</Empty>}
        </div>
      </div>
    </div>
  );
}
