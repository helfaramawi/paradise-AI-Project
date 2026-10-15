import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Background, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Activity, AlertTriangle, CheckCircle2, Clock, Cpu, Gavel, Loader2, Octagon, RefreshCw, XCircle } from "lucide-react";
import { api, sseUrl } from "@/lib/api";
import { useAuth, useI18n } from "@/lib/app";
import { useResolvedDecisionId } from "@/lib/hooks";
import { AgentAvatar, Badge, Button, Card, Empty, PageHeader, Stat, StatusBadge, cn } from "@/components/ui";

type Ev = { id: number; ts: string; stage: string; event_type: string; agent_key: string | null; message_en: string; message_ar: string; payload: any };

const STAGES: [string, string, string][] = [
  ["intake", "Decision received", "استلام القرار"],
  ["data_validation", "Data validation", "التحقق من البيانات"],
  ["agent_assignment", "Agent assignment", "تكليف الوكلاء"],
  ["independent_analysis", "Independent analysis", "التحليل المستقل"],
  ["scenario_generation", "Scenario generation", "توليد السيناريوهات"],
  ["quantitative_simulation", "Quantitative simulation", "المحاكاة الكمية"],
  ["agent_court", "Agent Court", "محكمة الوكلاء"],
  ["risk_assessment", "Risk assessment", "تقييم المخاطر"],
  ["governance_review", "Governance review", "مراجعة الحوكمة"],
  ["executive_recommendation", "Executive recommendation", "التوصية التنفيذية"],
];
const PHASE1 = ["strategy", "cfo", "coo", "hr", "delivery", "legal", "risk"];
const AGENT_NAMES: Record<string, [string, string]> = {
  strategy: ["Strategy", "الاستراتيجية"], cfo: ["CFO", "المالية"], coo: ["COO", "العمليات"], hr: ["HR", "الموارد البشرية"],
  delivery: ["Delivery", "التسليم"], legal: ["Legal", "القانونية"], risk: ["Risk", "المخاطر"], redteam: ["Red Team", "الفريق الأحمر"],
  governance: ["Governance", "الحوكمة"], orchestrator: ["Orchestrator", "المنسق"],
};

type NodeState = "pending" | "active" | "done" | "failed";

function StageNode({ data }: NodeProps) {
  const d = data as { label: string; state: NodeState; ms?: number; reverse?: boolean };
  return (
    <div className={cn("w-[150px] rounded-xl border px-3 py-2 text-[11px] shadow-sm transition",
      d.state === "done" && "border-good/50 bg-good/10",
      d.state === "active" && "border-accent bg-accent/15 animate-pulseRing",
      d.state === "failed" && "border-critical bg-critical/10",
      d.state === "pending" && "border-line bg-panel")}>
      <Handle type="target" position={d.reverse ? Position.Right : Position.Left} className="!bg-line" />
      <div className="flex items-center gap-1.5 font-semibold text-ink">
        {d.state === "done" ? <CheckCircle2 className="h-3.5 w-3.5 text-good" /> : d.state === "active" ? <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" /> : d.state === "failed" ? <XCircle className="h-3.5 w-3.5 text-critical" /> : <Clock className="h-3.5 w-3.5 text-muted" />}
        {d.label}
      </div>
      {d.ms !== undefined && <div className="mt-0.5 text-muted num">{d.ms.toFixed(0)} ms</div>}
      <Handle type="source" position={d.reverse ? Position.Left : Position.Right} className="!bg-line" />
    </div>
  );
}

function AgentNode({ data }: NodeProps) {
  const d = data as { k: string; label: string; state: NodeState; findings?: number };
  return (
    <div className={cn("flex w-[150px] items-center gap-2 rounded-xl border bg-panel px-2 py-1.5 text-[11px] transition",
      d.state === "active" && "border-accent", d.state === "done" && "border-good/50", d.state === "failed" && "border-critical",
      d.state === "pending" && "border-line opacity-70")}>
      <Handle type="target" position={Position.Left} className="!bg-line" />
      <AgentAvatar k={d.k} size={24} active={d.state === "active"} />
      <div className="min-w-0">
        <div className="truncate font-semibold text-ink">{d.label}</div>
        <div className="text-muted">{d.state === "done" ? `${d.findings ?? 0} findings` : d.state}</div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-line" />
    </div>
  );
}
const nodeTypes = { stage: StageNode, agent: AgentNode };

export default function ExecutionRoom() {
  const { runId: paramRun } = useParams();
  const { t, lang, pick, num } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const did = useResolvedDecisionId();
  const decision = useQuery({ queryKey: ["decision", did], queryFn: () => api(`/decisions/${did}`), enabled: !paramRun && !!did });
  const runId = paramRun || decision.data?.runs?.[0]?.id;
  const [events, setEvents] = useState<Ev[]>([]);
  const [ended, setEnded] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runId) return;
    setEvents([]);
    setEnded(null);
    const es = new EventSource(sseUrl(runId));
    es.addEventListener("workflow", (e) => {
      const ev = JSON.parse((e as MessageEvent).data) as Ev;
      setEvents((prev) => (prev.some((p) => p.id === ev.id) ? prev : [...prev, ev]));
    });
    es.addEventListener("end", (e) => {
      setEnded(JSON.parse((e as MessageEvent).data).status);
      es.close();
      qc.invalidateQueries({ queryKey: ["decisions"] });
      qc.invalidateQueries({ queryKey: ["dossier"] });
    });
    es.onerror = () => { /* browser auto-reconnects; server replays from Last-Event-ID */ };
    return () => es.close();
  }, [runId, qc]);

  useEffect(() => {
    if (ended) return;
    const i = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(i);
  }, [ended]);
  useEffect(() => { feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: "smooth" }); }, [events.length]);

  const state = useMemo(() => {
    const stage: Record<string, NodeState> = {};
    const stageMs: Record<string, number> = {};
    const agent: Record<string, NodeState> = {};
    const findings: Record<string, number> = {};
    let current = "";
    for (const e of events) {
      if (e.event_type === "stage_started") { stage[e.stage] = "active"; current = e.stage; }
      if (e.event_type === "stage_completed") { stage[e.stage] = "done"; if (e.payload?.duration_ms) stageMs[e.stage] = e.payload.duration_ms; }
      if (e.agent_key && e.event_type === "agent_started") agent[e.agent_key] = "active";
      if (e.agent_key && e.event_type === "agent_completed") { agent[e.agent_key] = "done"; findings[e.agent_key] = (findings[e.agent_key] || 0) + (e.payload?.findings || 0); }
      if (e.agent_key && e.event_type === "agent_failed") agent[e.agent_key] = "failed";
      if (e.event_type === "error" || e.event_type === "run_cancelled") stage[current] = "failed";
    }
    const first = events[0] ? new Date(events[0].ts).getTime() : null;
    const last = events.length ? new Date(events[events.length - 1].ts).getTime() : null;
    const done = events.find((e) => e.event_type === "run_completed");
    return {
      stage, stageMs, agent, findings, current,
      elapsed: first ? ((ended && last ? last : now) - first) / 1000 : 0,
      compute: done?.payload?.compute_ms as number | undefined,
      paced: done?.payload?.paced_ms as number | undefined,
      warnings: events.filter((e) => e.event_type === "warning").length,
      retries: events.filter((e) => e.event_type === "agent_retry").length,
      failed: events.filter((e) => e.event_type === "agent_failed").length,
      completed: !!done,
    };
  }, [events, now, ended]);

  const { nodes, edges } = useMemo(() => {
    const n: Node[] = [];
    const e: Edge[] = [];
    const lbl = (s: [string, string, string]) => (lang === "ar" ? s[2] : s[1]);
    const order = STAGES.filter((s) => s[0] !== "independent_analysis");
    // Two-row "snake" layout: row 1 left→right, agents fan out, row 2 right→left.
    const pos: Record<string, { x: number; y: number; reverse?: boolean }> = {
      intake: { x: 0, y: 70 }, data_validation: { x: 175, y: 70 }, agent_assignment: { x: 350, y: 70 },
      scenario_generation: { x: 740, y: 70 }, quantitative_simulation: { x: 915, y: 70 },
      agent_court: { x: 915, y: 360, reverse: true }, risk_assessment: { x: 740, y: 360, reverse: true },
      governance_review: { x: 565, y: 360, reverse: true }, executive_recommendation: { x: 390, y: 360, reverse: true },
    };
    order.forEach((s) => {
      const p = pos[s[0]];
      n.push({ id: s[0], type: "stage", position: { x: p.x, y: p.y }, width: 150, height: 52,
        data: { label: lbl(s), state: state.stage[s[0]] || "pending", ms: state.stageMs[s[0]], reverse: p.reverse } });
    });
    PHASE1.forEach((k, i) => {
      n.push({ id: `a_${k}`, type: "agent", position: { x: 545, y: -40 + i * 46 }, width: 150, height: 40, data: { k, label: pick(...AGENT_NAMES[k]), state: state.agent[k] || "pending", findings: state.findings[k] } });
      e.push({ id: `e1${k}`, source: "agent_assignment", target: `a_${k}`, animated: state.agent[k] === "active" });
      e.push({ id: `e2${k}`, source: `a_${k}`, target: "scenario_generation", animated: state.stage.scenario_generation === "active" });
    });
    for (let i = 0; i < order.length - 1; i++) {
      if (order[i][0] === "agent_assignment") continue;
      e.push({ id: `s${i}`, source: order[i][0], target: order[i + 1][0], animated: state.stage[order[i + 1][0]] === "active" });
    }
    return { nodes: n, edges: e.map((x) => ({ ...x, type: "smoothstep", style: { stroke: "rgb(var(--muted) / 0.6)", strokeWidth: 1.5 } })) };
  }, [state, lang, pick]);

  if (!runId) return <Empty>{t("ex.noRun")}</Empty>;
  const cancel = () => api(`/runs/${runId}/cancel`, { method: "POST" });
  const visible = events.filter((e) => !["stage_completed"].includes(e.event_type));
  return (
    <div>
      <PageHeader icon={Activity} title={t("ex.title")} subtitle={t("ex.subtitle")}
        actions={
          <>
            {ended && <StatusBadge status={ended} />}
            {!ended && can("decision.cancel") && <Button variant="danger" size="sm" icon={Octagon} onClick={cancel}>{t("ex.stop")}</Button>}
            {state.completed && <Link to="/court"><Button icon={Gavel} data-testid="to-court">{t("ex.toCourt")}</Button></Link>}
          </>
        } />
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-6">
        <Stat label={t("ex.stage")} value={<span className="text-base">{pick(...((STAGES.find((s) => s[0] === state.current) || ["", "—", "—"]).slice(1) as [string, string]))}</span>} />
        <Stat label={t("ex.elapsed")} value={`${num(state.elapsed, 1)}s`} icon={Clock} />
        <Stat label={t("ex.compute")} value={state.compute !== undefined ? `${num(state.compute, 0)} ms` : "…"} icon={Cpu} />
        <Stat label={t("ex.warnings")} value={num(state.warnings, 0)} icon={AlertTriangle} tone={state.warnings ? "warn" : undefined} />
        <Stat label={t("ex.retries")} value={num(state.retries, 0)} icon={RefreshCw} />
        <Stat label={t("ex.failed")} value={num(state.failed, 0)} icon={XCircle} tone={state.failed ? "critical" : undefined} />
      </div>
      <div className="grid gap-5 xl:grid-cols-5">
        <Card className="xl:col-span-3 !p-0 overflow-hidden" >
          <div className="h-[430px]" dir="ltr" data-testid="flow-graph">
            <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.12 }} proOptions={{ hideAttribution: true }}
              onInit={(inst) => { [60, 300, 900].forEach((ms) => setTimeout(() => inst.fitView({ padding: 0.12 }), ms)); }}
              nodesDraggable={false} nodesConnectable={false} panOnScroll zoomOnScroll={false}>
              <Background color="rgb(var(--line))" gap={22} />
            </ReactFlow>
          </div>
          <div className="border-t border-line px-4 py-2 text-[11px] text-muted">
            {t("ex.pacingNote")} {state.paced !== undefined && `${t("ex.paced")}: ${num(state.paced, 0)} ms.`}
          </div>
        </Card>
        <Card className="xl:col-span-2" title={t("ex.feed")} action={<Badge tone="accent">{num(events.length, 0)} events</Badge>}>
          <div ref={feedRef} className="h-[400px] space-y-2 overflow-y-auto pe-1 scroll-thin" data-testid="event-feed">
            {!events.length && <div className="text-sm text-muted">{t("ex.waiting")}</div>}
            <AnimatePresence initial={false}>
              {visible.map((e) => (
                <motion.div key={e.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                  className={cn("flex gap-2 rounded-xl border p-2 text-xs",
                    e.event_type === "warning" && "border-warn/40 bg-warn/5",
                    (e.event_type === "error" || e.event_type === "agent_failed") && "border-critical/40 bg-critical/5",
                    e.event_type === "objection" && "border-critical/30",
                    e.event_type === "collision" && "border-serious/50 bg-serious/5",
                    e.event_type === "run_completed" && "border-good/50 bg-good/10",
                    !["warning", "error", "agent_failed", "objection", "collision", "run_completed"].includes(e.event_type) && "border-line/60")}>
                  {e.agent_key ? <AgentAvatar k={e.agent_key} size={22} /> : <div className="grid h-[22px] w-[22px] shrink-0 place-items-center rounded-lg bg-panel2"><Activity className="h-3 w-3 text-muted" /></div>}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 text-[10px] text-muted">
                      <span className="font-semibold uppercase">{e.event_type.replace(/_/g, " ")}</span>
                      <span className="num">{new Date(e.ts).toLocaleTimeString(lang === "ar" ? "ar-EG" : "en-GB")}</span>
                    </div>
                    <div className="text-ink2">{pick(e.message_en, e.message_ar)}</div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </Card>
      </div>
      {state.completed && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card mt-5 flex items-center gap-3 border-good/50 p-4">
          <CheckCircle2 className="h-5 w-5 text-good" />
          <span className="font-semibold">{t("ex.done")}</span>
          <Link to="/court" className="ms-auto"><Button>{t("ex.toCourt")}</Button></Link>
        </motion.div>
      )}
    </div>
  );
}
