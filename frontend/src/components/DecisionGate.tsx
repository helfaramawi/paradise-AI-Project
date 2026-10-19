import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { FileSpreadsheet, FileText } from "lucide-react";
import { download } from "@/lib/api";
import { useActiveDecision, useAuth, useI18n } from "@/lib/app";
import { useDecisions, useDossier, useResolvedDecisionId, type Dossier } from "@/lib/hooks";
import { Button, Empty, ErrorBox, Select, Spinner, StatusBadge } from "./ui";

export function DecisionPicker({ value }: { value: string | null }) {
  const { data } = useDecisions();
  const { setActive } = useActiveDecision();
  const { date } = useI18n();
  if (!data?.length) return null;
  return (
    <Select value={value || ""} onChange={(e) => setActive(e.target.value)} className="max-w-xs" data-testid="decision-picker">
      {data.map((d) => (
        <option key={d.id} value={d.id}>
          {d.title} · {date(d.created_at, false)}
        </option>
      ))}
    </Select>
  );
}

export function ExportButtons({ decisionId }: { decisionId: string }) {
  const { t, lang } = useI18n();
  const { can } = useAuth();
  if (!can("report.export")) return null;
  return (
    <>
      <Button variant="outline" size="sm" icon={FileText}
        onClick={() => download(`/decisions/${decisionId}/report.pdf?lang=${lang}`, `future-mirror-${decisionId.slice(0, 8)}-${lang}.pdf`)}>
        {t("exportPdf")}
      </Button>
      <Button variant="outline" size="sm" icon={FileSpreadsheet}
        onClick={() => download(`/decisions/${decisionId}/report.xlsx?lang=${lang}`, `future-mirror-${decisionId.slice(0, 8)}-${lang}.xlsx`)}>
        {t("exportXlsx")}
      </Button>
    </>
  );
}

/** Switches the labels to the decision model (cost or collections) of the dossier on screen. */
export function useDecisionDomain(dossier: Dossier | undefined) {
  const { setDomain } = useI18n();
  const domain = dossier?.decision?.controls?.domain === "collections" ? "collections" : "opex";
  useEffect(() => {
    if (dossier) setDomain(domain);
  }, [dossier, domain, setDomain]);
}

/** Loads the active decision's latest completed dossier, or explains what to do. */
export function DecisionGate({ children, requireRun = true }: { children: (d: Dossier, decisionId: string) => ReactNode; requireRun?: boolean }) {
  const { t } = useI18n();
  const id = useResolvedDecisionId();
  const { data, isLoading, error } = useDossier(id);
  useDecisionDomain(data);
  const { isLoading: listLoading } = useDecisions();
  if (listLoading || isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  if (!id || !data || (requireRun && !data.run)) {
    return (
      <Empty action={<Link to="/decisions/new"><Button>{t("startDemo")}</Button></Link>}>
        <div className="text-base text-ink2">{t("noDecision")}</div>
        {id && <DecisionPicker value={id} />}
      </Empty>
    );
  }
  return <>{children(data, id)}</>;
}

export function DecisionContextBar({ dossier, decisionId }: { dossier: Dossier; decisionId: string }) {
  const { t, date } = useI18n();
  return (
    <div className="card mb-5 flex flex-wrap items-center gap-3 px-4 py-3">
      <DecisionPicker value={decisionId} />
      <StatusBadge status={dossier.decision.status} />
      {dossier.run && (
        <span className="text-xs text-muted num">
          {t("hi.run")} {dossier.run.id.slice(0, 8)} · {date(dossier.run.finished_at)} · seed {dossier.simulation?.seed} ·{" "}
          {t("fu.fingerprint")} {dossier.simulation?.input_fingerprint}
        </span>
      )}
      <div className="ms-auto flex gap-2">
        <ExportButtons decisionId={decisionId} />
      </div>
    </div>
  );
}
