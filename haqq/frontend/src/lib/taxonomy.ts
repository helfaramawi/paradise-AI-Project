import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { useI18n } from "./i18n";

type L = { en: string; ar: string };
export type Taxonomy = { doc_types: Record<string, L>; clause_categories: Record<string, L>; event_categories: Record<string, L>;
  entitlement_types: Record<string, L>; entitlement_status: Record<string, L>; cost_categories: Record<string, L>; claim_stages: Record<string, L> };

export function useTaxonomy() {
  const { pick } = useI18n();
  const q = useQuery({ queryKey: ["taxonomy"], queryFn: () => api.get<Taxonomy>("/meta/taxonomy"), staleTime: Infinity });
  const label = (group: keyof Taxonomy, key: string | null | undefined) => (key ? pick(q.data?.[group]?.[key]) || key.replace(/_/g, " ") : "—");
  return { tax: q.data, label };
}
