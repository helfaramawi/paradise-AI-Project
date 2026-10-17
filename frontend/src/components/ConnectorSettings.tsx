import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, Save, Trash2, X } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/app";
import { Badge, Button, Card, ErrorBox, Input, Select } from "./ui";
import type { DictKey } from "@/i18n/dict";

/** Cost categories the backend maps onto the canonical cost profile (connectors/base.py). */
const CATEGORIES = ["personnel", "contractors", "software", "infrastructure", "facilities", "vendor services", "other g&a"];

type Field = {
  key: string; type?: "text" | "url" | "date" | "number" | "select"; options?: string[]; label?: string;
  placeholder?: string; required?: boolean; advanced?: boolean;
};

const PERIOD: Field[] = [
  { key: "date_from", type: "date", required: true },
  { key: "date_to", type: "date", required: true },
];

/** Settings per connector kind. Secrets are deliberately absent: they come from the server environment. */
export const CONNECTOR_FIELDS: Record<string, Field[]> = {
  odoo: [
    { key: "url", type: "url", placeholder: "https://erp.example.com", required: true },
    { key: "database", placeholder: "production", required: true },
    { key: "username", placeholder: "integration@company.com", required: true },
    ...PERIOD,
  ],
  d365_fo: [
    { key: "environment_url", type: "url", placeholder: "https://contoso.operations.dynamics.com", required: true },
    { key: "tenant_id", placeholder: "00000000-0000-0000-0000-000000000000", required: true },
    { key: "client_id", placeholder: "00000000-0000-0000-0000-000000000000", required: true },
    { key: "legal_entity", placeholder: "usmf" },
    ...PERIOD,
    { key: "entity_set", placeholder: "GeneralJournalAccountEntries", advanced: true },
    { key: "account_field", placeholder: "LedgerAccount", advanced: true },
    { key: "amount_field", placeholder: "AccountingCurrencyAmount", advanced: true },
    { key: "date_field", placeholder: "AccountingDate", advanced: true },
  ],
  d365_bc: [
    { key: "tenant_id", placeholder: "00000000-0000-0000-0000-000000000000", required: true },
    { key: "client_id", placeholder: "00000000-0000-0000-0000-000000000000", required: true },
    { key: "environment", placeholder: "production", required: true },
    { key: "company_id", placeholder: "00000000-0000-0000-0000-000000000000", required: true },
    ...PERIOD,
  ],
  sap: [
    { key: "base_url", type: "url", placeholder: "https://my123456.s4hana.ondemand.com", required: true },
    { key: "username", placeholder: "COMM_USER_FM", required: true },
    { key: "company_code", placeholder: "1010", required: true },
    { key: "ledger", placeholder: "0L" },
    ...PERIOD,
    { key: "sap_client", placeholder: "100", advanced: true },
  ],
  rest: [
    { key: "url", label: "rest_url", type: "url", placeholder: "https://erp.example.com/api/gl?year=2026", required: true },
    { key: "records_path", placeholder: "data.items" },
    { key: "account_field", placeholder: "account", required: true },
    { key: "amount_field", placeholder: "amount", required: true },
    { key: "next_field", placeholder: "links.next" },
    ...PERIOD.map((f) => ({ ...f, required: false })),
    { key: "auth_header", placeholder: "Authorization", advanced: true },
    { key: "auth_scheme", placeholder: "Bearer", advanced: true },
  ],
  sql: [
    { key: "dialect", type: "select", options: ["postgresql", "mssql", "mysql"], required: true },
    { key: "host", placeholder: "erp-db.company.local", required: true },
    { key: "port", type: "number", placeholder: "5432 / 1433 / 3306" },
    { key: "database", placeholder: "erp", required: true },
    { key: "username", placeholder: "fm_readonly", required: true },
    { key: "schema", placeholder: "public" },
    { key: "table", placeholder: "v_gl_expenses", required: true },
    { key: "account_column", placeholder: "account", required: true },
    { key: "amount_column", placeholder: "amount", required: true },
    { key: "date_column", placeholder: "posting_date", required: true },
    ...PERIOD,
  ],
};

const NUMBER_KEYS = new Set(Object.values(CONNECTOR_FIELDS).flat().filter((f) => f.type === "number").map((f) => f.key));

type Row = { prefix: string; category: string };

export default function ConnectorSettings({ conn, onClose }: { conn: any; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const fields = CONNECTOR_FIELDS[conn.kind] ?? [];
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((f) => [f.key, String(conn.config?.[f.key] ?? (f.type === "select" ? f.options?.[0] : "") ?? "")])));
  const [rows, setRows] = useState<Row[]>(() => {
    const m = Object.entries((conn.config?.account_mapping ?? {}) as Record<string, string>);
    return m.length ? m.map(([prefix, category]) => ({ prefix, category })) : [{ prefix: "", category: "personnel" }];
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [saved, setSaved] = useState(false);

  const missing = fields.filter((f) => f.required && !values[f.key]?.trim()).map((f) => f.key);
  const mappingRows = rows.filter((r) => r.prefix.trim());
  const save = useMutation({
    mutationFn: () => api(`/connectors/${conn.id}`, {
      method: "PATCH",
      json: { config: { ...Object.fromEntries(Object.entries(values).map(([k, v]) =>
          [k, NUMBER_KEYS.has(k) && v.trim() ? Number(v) : v.trim()])),
        account_mapping: Object.fromEntries(mappingRows.map((r) => [r.prefix.trim(), r.category])) } },
    }),
    onSuccess: () => { setSaved(true); qc.invalidateQueries({ queryKey: ["connectors"] }); },
  });

  const label = (k: string) => t(`dc.f.${fields.find((f) => f.key === k)?.label ?? k}` as DictKey);
  const set = (k: string, v: string) => { setSaved(false); setValues({ ...values, [k]: v }); };
  const setRow = (i: number, r: Partial<Row>) => { setSaved(false); setRows(rows.map((x, j) => (j === i ? { ...x, ...r } : x))); };

  return (
    <Card className="mb-5" data-testid={`conn-settings-${conn.kind}`} title={`${t("dc.settings")} · ${conn.name}`}
      subtitle={t("dc.settingsHint")}
      action={<Button size="sm" variant="ghost" icon={X} onClick={onClose} aria-label={t("dc.close")} />}>
      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-panel2/50 p-3 text-xs">
        <KeyRound className="h-4 w-4 text-muted" />
        <span className="text-ink2">{t("dc.secret")}:</span>
        {conn.secret_env?.map((v: string) => <code key={v} className="rounded bg-panel px-1.5 py-0.5">{v}</code>)}
        <Badge tone={conn.secret_configured ? "good" : conn.secret_optional ? "neutral" : "warn"}>
          {t(conn.secret_configured ? "dc.secretSet" : conn.secret_optional ? "dc.secretOptional" : "dc.secretMissing")}
        </Badge>
        {!conn.secret_configured && <span className="text-muted">{t(conn.secret_optional ? "dc.secretOptionalHow" : "dc.secretHow")}</span>}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {fields.filter((f) => !f.advanced || showAdvanced).map((f) => (
          <label key={f.key} className="text-xs">
            <span className="mb-1 block text-ink2">{label(f.key)}{f.required && <span className="text-critical"> *</span>}</span>
            {f.type === "select" ? (
              <Select className="w-full" dir="ltr" value={values[f.key] || f.options?.[0]} onChange={(e) => set(f.key, e.target.value)}
                data-testid={`cfg-${f.key}`}>
                {f.options?.map((o) => <option key={o} value={o}>{o}</option>)}
              </Select>
            ) : (
              <Input type={f.type === "date" || f.type === "url" || f.type === "number" ? f.type : "text"} dir="ltr"
                value={values[f.key]} placeholder={f.placeholder} onChange={(e) => set(f.key, e.target.value)} data-testid={`cfg-${f.key}`} />
            )}
          </label>
        ))}
      </div>
      {fields.some((f) => f.advanced) && (
        <button type="button" className="mt-2 text-xs text-accent hover:underline" onClick={() => setShowAdvanced(!showAdvanced)}>
          {t(showAdvanced ? "dc.hideAdvanced" : "dc.showAdvanced")}
        </button>
      )}

      <div className="mt-5">
        <div className="mb-1 text-sm font-semibold">{t("dc.mapping")}</div>
        <div className="mb-2 text-xs text-muted">{t("dc.mappingHint")}</div>
        <div className="space-y-2">
          {rows.map((r, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input className="h-9 w-40 num" dir="ltr" placeholder="61" value={r.prefix} aria-label={t("dc.prefix")}
                onChange={(e) => setRow(i, { prefix: e.target.value })} data-testid={`map-prefix-${i}`} />
              <span className="inline-block text-muted rtl:-scale-x-100">→</span>
              <Select className="h-9 flex-1" value={r.category} aria-label={t("dc.category")} onChange={(e) => setRow(i, { category: e.target.value })}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{t(`dc.cat.${c}` as DictKey)}</option>)}
              </Select>
              <Button size="sm" variant="ghost" icon={Trash2} aria-label={t("dc.remove")} disabled={rows.length === 1}
                onClick={() => setRows(rows.filter((_, j) => j !== i))} />
            </div>
          ))}
        </div>
        <Button size="sm" variant="outline" icon={Plus} className="mt-2" onClick={() => setRows([...rows, { prefix: "", category: "personnel" }])}>
          {t("dc.addRow")}
        </Button>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button icon={Save} loading={save.isPending} disabled={missing.length > 0 || mappingRows.length === 0}
          onClick={() => save.mutate()} data-testid="cfg-save">{t("dc.save")}</Button>
        {missing.length > 0 && <span className="text-xs text-muted">{t("dc.required")}: {missing.map(label).join(", ")}</span>}
        {missing.length === 0 && mappingRows.length === 0 && <span className="text-xs text-muted">{t("dc.mappingRequired")}</span>}
        {saved && <Badge tone="good">{t("dc.saved")}</Badge>}
      </div>
      <ErrorBox error={save.error} />
    </Card>
  );
}
