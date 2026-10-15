import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { useActiveDecision } from "./app";

export type Dossier = any;

export function usePlatform() {
  return useQuery({ queryKey: ["platform"], queryFn: () => api("/platform/status"), refetchInterval: 15000 });
}

export function useDecisions() {
  return useQuery({ queryKey: ["decisions"], queryFn: () => api<any[]>("/decisions") });
}

/** Resolves the decision to show: explicit id, else the active one, else the most recent analysed one. */
export function useResolvedDecisionId(explicit?: string): string | null {
  const { activeId } = useActiveDecision();
  const { data } = useDecisions();
  if (explicit) return explicit;
  if (activeId && (!data || data.some((d) => d.id === activeId))) return activeId;
  const analysed = data?.find((d) => d.latest_run?.status === "completed");
  return analysed?.id ?? data?.[0]?.id ?? null;
}

export function useDossier(decisionId: string | null, runId?: string) {
  return useQuery({
    queryKey: ["dossier", decisionId, runId],
    queryFn: () => api<Dossier>(`/decisions/${decisionId}/dossier${runId ? `?run_id=${runId}` : ""}`),
    enabled: !!decisionId,
  });
}
