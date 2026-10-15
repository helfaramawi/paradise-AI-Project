import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { AlertOctagon, ArrowRight, Bot, CornerDownRight, Gavel, Info, PlayCircle, Scale, Swords, UserCheck, Zap } from "lucide-react";
import { useI18n } from "@/lib/app";
import { DecisionContextBar, DecisionGate } from "@/components/DecisionGate";
import {
  AgentAvatar, Badge, Bar, Button, Card, ClaimBadge, FUTURE_COLOR, FutureChip, PageHeader, StanceBadge, StatusBadge, Tabs,
  cn, futureLabel, useAgentName,
} from "@/components/ui";

type F = any;

function Evidence({ items }: { items: any[] }) {
  const { t } = useI18n();
  if (!items?.length) return null;
  return (
    <div className="mt-2 rounded-lg bg-panel2/60 p-2">
      <div className="label mb-1">{t("evidence")}</div>
      <ul className="space-y-0.5 text-[11px]">
        {items.map((e) => (
          <li key={e.id} className="flex flex-wrap items-baseline gap-1.5">
            <Badge tone={e.source_type === "policy" ? "violet" : e.source_type === "assumption" ? "warn" : e.source_type === "dataset" ? "good" : "accent"}>
              {e.source_type}
            </Badge>
            <span className="text-ink2">{e.label}</span>
            <span className="font-semibold text-ink num">{e.value}</span>
            <code className="text-[10px] text-muted">{e.reference}</code>
          </li>
        ))}
      </ul>
    </div>
  );
}

function FindingCard({ f, agents, compact }: { f: F; agents: any; compact?: boolean }) {
  const { t, pick, prob } = useI18n();
  const name = useAgentName();
  const [open, setOpen] = useState(false);
  return (
    <div className="flex gap-3">
      <AgentAvatar k={f.agent_key} size={34} />
      <div className="min-w-0 flex-1 rounded-2xl rounded-ss-sm border border-line/70 bg-panel p-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-semibold text-ink">{name(agents, f.agent_key)}</span>
          <ClaimBadge type={f.claim_type} />
          <StanceBadge stance={f.stance} />
          {f.strategy_key && <FutureChip k={f.strategy_key} />}
          <span className="ms-auto text-[10px] text-muted num">{t("confidence")} {prob(f.confidence)} · EQ {prob(f.evidence_quality)}</span>
        </div>
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink2">{pick(f.text_en, f.text_ar)}</p>
        {!compact && (
          <button className="mt-1 text-[11px] text-accent hover:underline" onClick={() => setOpen(!open)}>
            {t("evidence")} ({f.evidence.length}) {f.assumptions?.length ? `· ${t("assumptions")} (${f.assumptions.length})` : ""}
          </button>
        )}
        {open && (
          <>
            <Evidence items={f.evidence} />
            {f.assumptions?.length > 0 && (
              <div className="mt-2 text-[11px] text-amber-600 dark:text-warn">{t("assumptions")}: {f.assumptions.join(" · ")}</div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ObjectionCard({ o, agents }: { o: any; agents: any }) {
  const { t, pick } = useI18n();
  const name = useAgentName();
  return (
    <div className="space-y-2">
      <div className="flex gap-3">
        <AgentAvatar k="redteam" size={34} />
        <div className="flex-1 rounded-2xl rounded-ss-sm border border-critical/40 bg-critical/5 p-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-semibold text-critical dark:text-red-300">{name(agents, "redteam")}</span>
            <Badge tone="critical" icon={Swords}>{t("court.objection")} → {name(agents, o.target_agent)}</Badge>
            <StatusBadge status={o.severity} />
            <Badge tone="neutral">{o.objection_type.replace(/_/g, " ")}</Badge>
            {o.strategy_key && <FutureChip k={o.strategy_key} />}
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-ink2">{pick(o.text_en, o.text_ar)}</p>
        </div>
      </div>
      {o.response_en && (
        <div className="flex gap-3 ps-10">
          <CornerDownRight className="mt-2 h-4 w-4 shrink-0 text-muted rtl:-scale-x-100" />
          <AgentAvatar k={o.response_by} size={28} />
          <div className="flex-1 rounded-2xl rounded-ss-sm border border-line bg-panel p-3">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold">{name(agents, o.response_by)}</span>
              <Badge tone="accent">{t("court.response")}</Badge>
              <span className="ms-auto"><StatusBadge status={o.resolution} /></span>
            </div>
            <p className="mt-1 text-[13px] text-ink2">{pick(o.response_en, o.response_ar)}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function CollisionCard({ c, agents }: { c: any; agents: any }) {
  const { t, pick } = useI18n();
  const name = useAgentName();
  const tone = c.severity === "critical" ? "border-critical/60" : c.severity === "high" ? "border-serious/60" : "border-warn/50";
  return (
    <motion.div layout initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className={cn("card border-2 p-5", tone)}
      data-testid="collision-card">
      <div className="flex flex-wrap items-center gap-2">
        <Zap className="h-5 w-5 text-serious" />
        <h4 className="font-display text-[15px] font-semibold">{pick(c.title_en, c.title_ar)}</h4>
        <span className="ms-auto flex items-center gap-2">
          <code className="text-[10px] text-muted">{c.rule_code}</code>
          {c.strategy_key ? <FutureChip k={c.strategy_key} /> : <Badge tone="violet">{t("all")}</Badge>}
          <StatusBadge status={c.severity} />
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2 text-[11px] text-muted">
        {t("severity")} <Bar value={c.severity_score} className="max-w-[160px]" color={c.severity === "critical" ? "#d03b3b" : "#ec835a"} />
        <span className="num">{(c.severity_score * 100).toFixed(0)}/100</span>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {c.positions.map((p: any, i: number) => (
          <div key={i} className="flex gap-2 rounded-xl border border-line/70 bg-panel2/40 p-2.5">
            <AgentAvatar k={p.agent} size={26} />
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold">{name(agents, p.agent)} <StanceBadge stance={p.stance} /></div>
              <p className="mt-0.5 line-clamp-4 text-[12px] text-ink2">{pick(p.text_en, p.text_ar)}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-4 text-xs md:grid-cols-3">
        <div>
          <div className="label mb-1">{t("court.affected")}</div>
          <div className="flex flex-wrap gap-1">{c.affected_objectives.map((o: string) => <Badge key={o}>{o.replace(/_/g, " ")}</Badge>)}</div>
        </div>
        <div>
          <div className="label mb-1">{t("court.consequences")}</div>
          <ul className="list-disc space-y-0.5 ps-4 text-ink2">{c.consequences.map((x: any, i: number) => <li key={i}>{pick(x.en, x.ar)}</li>)}</ul>
        </div>
        <div>
          <div className="label mb-1">{t("court.resolutions")}</div>
          <ul className="list-disc space-y-0.5 ps-4 text-ink2">{c.resolutions.map((x: any, i: number) => <li key={i}>{pick(x.en, x.ar)}</li>)}</ul>
        </div>
      </div>
      {c.requires_human && <div className="mt-3"><Badge tone="warn" icon={UserCheck}>{t("court.human")}</Badge></div>}
    </motion.div>
  );
}

function Verdict({ d }: { d: any }) {
  const { t, pick, num } = useI18n();
  const rec = d.run.result.recommendation;
  const maxW = Math.max(...["A", "B", "C"].map((k) => Math.abs(rec.per_future[k].evidence_weighted_support)), 0.01);
  return (
    <Card className="mb-5 border-accent/40" title={<span className="flex items-center gap-2"><Gavel className="h-4 w-4 text-accent" />{t("court.verdict")}</span>}
      action={rec.recommended_strategy && <FutureChip k={rec.recommended_strategy} className="text-sm" />}>
      <p className="text-[15px] leading-relaxed text-ink" data-testid="verdict-headline">{pick(rec.headline_en, rec.headline_ar)}</p>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {(["A", "B", "C"] as const).map((k) => {
          const p = rec.per_future[k];
          return (
            <div key={k} className="rounded-xl border border-line p-3" style={{ borderInlineStartColor: FUTURE_COLOR[k], borderInlineStartWidth: 3 }}>
              <div className="flex items-center justify-between"><FutureChip k={k} /><StatusBadge status={p.status} /></div>
              <div className="mt-2 text-[11px] text-muted">{t("court.weighted")}</div>
              <div className="flex items-center gap-2">
                <Bar value={Math.abs(p.evidence_weighted_support)} max={maxW} color={p.evidence_weighted_support >= 0 ? "#0ca30c" : "#d03b3b"} />
                <span className="num text-xs font-semibold">{num(p.evidence_weighted_support, 2)}</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                <StatusBadge status={p.governance_outcome} />
                {p.hard_constraints_violated.map((c: string) => <Badge key={c} tone="critical">{c}</Badge>)}
              </div>
              {p.required_roles.length > 0 && (
                <div className="mt-2 text-[11px] text-muted">{t("court.approvals")}: <span className="font-semibold uppercase text-ink2">{p.required_roles.join(" · ")}</span></div>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-4 flex flex-wrap items-start gap-2 rounded-xl bg-panel2/60 p-3 text-xs text-ink2">
        <Scale className="mt-0.5 h-4 w-4 shrink-0 text-accent2" />
        <div>
          <span className="font-semibold">{t("court.method")}:</span> {pick(rec.method_en, rec.method_ar)}
          <div className="mt-1 text-muted">
            {rec.majority_differs
              ? <>{t("court.majority")} <b>{futureLabel(rec.naive_majority_winner, "en")}</b>.</>
              : t("court.majoritySame")}
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link to="/futures"><Button variant="outline" size="sm" icon={ArrowRight}>{t("nav.futures")}</Button></Link>
        <Link to="/approvals"><Button size="sm" icon={UserCheck}>{t("ap.request")}</Button></Link>
      </div>
    </Card>
  );
}

function Court({ d, decisionId }: { d: any; decisionId: string }) {
  const { t, pick } = useI18n();
  const [tab, setTab] = useState<"debate" | "positions" | "collisions">("debate");
  const [focus, setFocus] = useState<"all" | "A" | "B" | "C">("all");
  const [revealed, setRevealed] = useState<number>(Infinity);
  const court = d.findings.filter((f: F) => f.phase === "court" || f.phase === "governance");
  const opening = d.findings.filter((f: F) => f.phase === "independent_analysis");
  const match = (k: string | null) => focus === "all" || !k || k === focus;
  const transcript = useMemo(() => {
    const items: { kind: string; data: any }[] = [];
    items.push({ kind: "round", data: "1" });
    court.filter((f: F) => f.phase === "court" && match(f.strategy_key)).forEach((f: F) => items.push({ kind: "finding", data: f }));
    items.push({ kind: "round", data: "2" });
    d.objections.filter((o: any) => match(o.strategy_key)).forEach((o: any) => items.push({ kind: "objection", data: o }));
    items.push({ kind: "round", data: "3" });
    d.collisions.filter((c: any) => match(c.strategy_key)).forEach((c: any) => items.push({ kind: "collision", data: c }));
    items.push({ kind: "round", data: "4" });
    court.filter((f: F) => f.phase === "governance" && match(f.strategy_key)).forEach((f: F) => items.push({ kind: "finding", data: f }));
    return items;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d, focus]);
  useEffect(() => {
    if (revealed >= transcript.length) return;
    const id = setTimeout(() => setRevealed((r) => r + 1), 700);
    return () => clearTimeout(id);
  }, [revealed, transcript.length]);
  const rounds: Record<string, [string, string]> = {
    "1": ["Round 1 — Positions on the simulated futures", "الجولة 1 — المواقف من المستقبلات المحاكاة"],
    "2": ["Round 2 — Red Team cross-examination", "الجولة 2 — استجواب الفريق الأحمر"],
    "3": ["Round 3 — Decision collisions detected", "الجولة 3 — التعارضات المكتشفة"],
    "4": ["Round 4 — Governance & authority", "الجولة 4 — الحوكمة والصلاحيات"],
  };
  const mode = d.run.mode;
  return (
    <div>
      <DecisionContextBar dossier={d} decisionId={decisionId} />
      <div className={cn("mb-5 flex items-start gap-3 rounded-xl border p-3 text-xs",
        mode === "rule_based" ? "border-accent2/40 bg-accent2/5 text-ink2" : "border-accent/40 bg-accent/5")} data-testid="court-mode">
        <Bot className="h-4 w-4 shrink-0 text-accent2" />
        {mode === "rule_based" ? t("court.modeRule") : t("court.modeLlm")}
        <span className="ms-auto whitespace-nowrap text-muted">{d.executions.length} agent executions · run {d.run.id.slice(0, 8)}</span>
      </div>
      <Verdict d={d} />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={tab} onChange={setTab} items={[
          { value: "debate", label: t("court.debate") },
          { value: "positions", label: t("court.positions") },
          { value: "collisions", label: `${t("court.collisions")} (${d.collisions.length})` },
        ]} />
        <Tabs value={focus} onChange={(v) => { setFocus(v); }} items={[
          { value: "all", label: t("all") }, { value: "A", label: "A" }, { value: "B", label: "B" }, { value: "C", label: "C" }]} />
        {tab === "debate" && <Button variant="ghost" size="sm" icon={PlayCircle} onClick={() => setRevealed(0)}>{t("court.replay")}</Button>}
      </div>

      {tab === "debate" && (
        <div className="space-y-3" data-testid="debate">
          <AnimatePresence initial={false}>
            {transcript.slice(0, revealed === Infinity ? undefined : revealed).map((it, i) => (
              <motion.div key={`${it.kind}-${i}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                {it.kind === "round" && (
                  <div className="flex items-center gap-3 pt-3 text-xs font-semibold text-muted">
                    <span className="h-px flex-1 bg-line" />{pick(...rounds[it.data])}<span className="h-px flex-1 bg-line" />
                  </div>
                )}
                {it.kind === "finding" && <FindingCard f={it.data} agents={d.agents} />}
                {it.kind === "objection" && <ObjectionCard o={it.data} agents={d.agents} />}
                {it.kind === "collision" && (
                  <div className="flex items-center gap-3 rounded-xl border border-serious/50 bg-serious/5 p-3 text-sm">
                    <AlertOctagon className="h-5 w-5 text-serious" />
                    <span className="font-semibold">{pick(it.data.title_en, it.data.title_ar)}</span>
                    <span className="ms-auto"><StatusBadge status={it.data.severity} /></span>
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {tab === "positions" && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card title={pick("Independent analysis (before simulation)", "التحليل المستقل (قبل المحاكاة)")}>
            <div className="space-y-3">{opening.map((f: F) => <FindingCard key={f.id} f={f} agents={d.agents} />)}</div>
          </Card>
          <Card title={pick("Evaluation of simulated futures", "تقييم المستقبلات المحاكاة")}>
            <div className="space-y-3">{court.filter((f: F) => match(f.strategy_key)).map((f: F) => <FindingCard key={f.id} f={f} agents={d.agents} />)}</div>
          </Card>
        </div>
      )}

      {tab === "collisions" && (
        <div>
          <div className="mb-3 flex items-center gap-2 text-xs text-muted"><Info className="h-4 w-4" />{t("court.collisionsSub")}</div>
          <div className="space-y-4">{d.collisions.filter((c: any) => match(c.strategy_key)).map((c: any) => <CollisionCard key={c.id} c={c} agents={d.agents} />)}</div>
        </div>
      )}
    </div>
  );
}

export default function AgentCourt() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader icon={Gavel} title={t("court.title")} subtitle={t("court.subtitle")} />
      <DecisionGate>{(d, id) => <Court d={d} decisionId={id} />}</DecisionGate>
    </div>
  );
}
