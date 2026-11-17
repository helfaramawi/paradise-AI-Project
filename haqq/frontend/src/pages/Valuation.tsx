import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Alert, Badge, Button, Card, Field, Modal, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtMoney, useI18n } from "../lib/i18n";
import { useTaxonomy } from "../lib/taxonomy";

type Line = { category: string; description: string; quantity: string; unit: string; rate: string; source_document_id?: string | null; source_note?: string; rate_basis: string };
const blank: Line = { category: "direct_work", description: "", quantity: "1", unit: "", rate: "0", source_note: "", rate_basis: "user_input" };

export default function Valuation() {
  const { id = "" } = useParams();
  const { t, lang, pick } = useI18n();
  const { tax, label } = useTaxonomy();
  const { can } = useAuth();
  const qc = useQueryClient();
  const ent = useQuery({ queryKey: ["ent", id], queryFn: () => api.get<any>(`/entitlements/${id}`) });
  const val = useQuery({ queryKey: ["val", id], queryFn: () => api.get<any>(`/entitlements/${id}/valuation`) });
  const [lines, setLines] = useState<Line[]>([]);
  const [opts, setOpts] = useState({ overhead_pct: "0", profit_pct: "0", vat_applicable: false, assumptions: "", contractual_basis_note: "" });
  const [boqOpen, setBoqOpen] = useState(false);
  const [boqQ, setBoqQ] = useState("");
  const boq = useQuery({ queryKey: ["boq", ent.data?.project_id, boqQ], enabled: boqOpen && !!ent.data, queryFn: () => api.get<any[]>(`/projects/${ent.data.project_id}/boq`, { q: boqQ }) });
  useEffect(() => {
    if (val.data) {
      setLines(val.data.lines.map((l: any) => ({ ...l, quantity: String(l.quantity), rate: String(l.rate), unit: l.unit || "", source_note: l.source_note || "" })));
      setOpts({ overhead_pct: String(val.data.overhead_pct), profit_pct: String(val.data.profit_pct), vat_applicable: val.data.vat_applicable,
        assumptions: (val.data.assumptions || []).join("\n"), contractual_basis_note: val.data.contractual_basis_note || "" });
    } else if (val.isFetched) setLines([{ ...blank }]);
  }, [val.data, val.isFetched]);
  const save = useMutation({ mutationFn: () => api.put(`/entitlements/${id}/valuation`, { ...opts, assumptions: opts.assumptions.split("\n").filter(Boolean),
    lines: lines.map((l) => ({ ...l, unit: l.unit || null, source_document_id: l.source_document_id || null })) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["val", id] }); qc.invalidateQueries({ queryKey: ["ent", id] }); } });
  const verify = useMutation({ mutationFn: () => api.post(`/entitlements/${id}/valuation/verify`), onSuccess: () => qc.invalidateQueries({ queryKey: ["val", id] }) });
  if (ent.isLoading || val.isLoading) return <Spinner />;
  const set = (i: number, k: keyof Line, v: string) => setLines(lines.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  const preview = lines.reduce((s, l) => s + (Number(l.quantity) || 0) * (Number(l.rate) || 0), 0);
  const tot = val.data?.totals;
  const editable = can("valuation.write");
  return (
    <div>
      <PageHeader crumbs={<Link to={`/entitlements/${id}`} className="hover:underline">{ent.data?.ref}</Link>} title={t("valuation")}
        subtitle={label("entitlement_types", ent.data?.entitlement_type)}
        actions={val.data && <StatusBadge status={val.data.status === "verified" ? "verified" : "pending"} label={val.data.status === "verified" ? t("verified") : t("draft")} />} />
      <Alert tone="info">{lang === "ar" ? "جميع الحسابات تتم بمحرك حتمي (أرقام عشرية دقيقة) وليس بالنموذج اللغوي. لا تُفترض قابلية استرداد أي تكلفة دون أساس تعاقدي." :
        "All arithmetic is done by a deterministic engine (exact decimals), never by the language model. No cost is assumed recoverable without a contractual basis."}</Alert>
      <Card className="mt-5" title={t("valuation")} actions={editable && <>
        <Button size="sm" variant="secondary" onClick={() => setBoqOpen(true)}>{t("from_boq")}</Button>
        <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setLines([...lines, { ...blank }])}>{t("add_line")}</Button></>}>
        <div className="overflow-x-auto"><table className="w-full min-w-[900px]">
          <thead><tr><th className="th">{t("category")}</th><th className="th">{t("description")}</th><th className="th">{t("qty")}</th><th className="th">{t("unit")}</th><th className="th">{t("rate")}</th><th className="th">{t("amount")}</th><th className="th">{t("source")}</th><th className="th" /></tr></thead>
          <tbody>{lines.map((l, i) => (
            <tr key={i} className="border-t border-slate-100">
              <td className="p-1"><select disabled={!editable} className="input" value={l.category} onChange={(e) => set(i, "category", e.target.value)}>
                {tax && Object.keys(tax.cost_categories).map((c) => <option key={c} value={c}>{label("cost_categories", c)}</option>)}</select></td>
              <td className="p-1"><input disabled={!editable} className="input" value={l.description} onChange={(e) => set(i, "description", e.target.value)} /></td>
              <td className="p-1 w-24"><input disabled={!editable} className="input num" type="number" min="0" step="any" value={l.quantity} onChange={(e) => set(i, "quantity", e.target.value)} /></td>
              <td className="p-1 w-20"><input disabled={!editable} className="input" value={l.unit} onChange={(e) => set(i, "unit", e.target.value)} /></td>
              <td className="p-1 w-32"><input disabled={!editable} className="input num" type="number" min="0" step="any" value={l.rate} onChange={(e) => set(i, "rate", e.target.value)} /></td>
              <td className="td num whitespace-nowrap">{fmtMoney((Number(l.quantity) || 0) * (Number(l.rate) || 0), lang)}</td>
              <td className="p-1"><input disabled={!editable} className="input text-xs" value={l.source_note} onChange={(e) => set(i, "source_note", e.target.value)} />
                <Badge className="mt-1">{l.rate_basis}</Badge></td>
              <td className="p-1">{editable && <button className="p-2 text-slate-400 hover:text-red-600" onClick={() => setLines(lines.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4" /></button>}</td>
            </tr>))}</tbody>
        </table></div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <Field label={t("overhead")}><input disabled={!editable} className="input" type="number" min="0" value={opts.overhead_pct} onChange={(e) => setOpts({ ...opts, overhead_pct: e.target.value })} /></Field>
          <Field label={t("profit")}><input disabled={!editable} className="input" type="number" min="0" value={opts.profit_pct} onChange={(e) => setOpts({ ...opts, profit_pct: e.target.value })} /></Field>
          <label className="flex items-center gap-2 pt-6 text-sm"><input disabled={!editable} type="checkbox" checked={opts.vat_applicable} onChange={(e) => setOpts({ ...opts, vat_applicable: e.target.checked })} />{t("vat")}</label>
          <div className="pt-5 text-sm text-slate-500">Σ {fmtMoney(preview, lang)}</div>
          <div className="md:col-span-2"><Field label={t("assumptions")}><textarea disabled={!editable} className="input min-h-20" value={opts.assumptions} onChange={(e) => setOpts({ ...opts, assumptions: e.target.value })} /></Field></div>
          <div className="md:col-span-2"><Field label={t("basis")}><textarea disabled={!editable} className="input min-h-20" value={opts.contractual_basis_note} onChange={(e) => setOpts({ ...opts, contractual_basis_note: e.target.value })} /></Field></div>
        </div>
        {save.error && <Alert tone="error">{(save.error as Error).message}</Alert>}
        {verify.error && <Alert tone="error">{(verify.error as Error).message}</Alert>}
        <div className="mt-4 flex gap-2">
          {editable && <Button loading={save.isPending} onClick={() => save.mutate()} data-testid="save-valuation">{t("save_calc")}</Button>}
          {can("valuation.verify") && val.data && val.data.status !== "verified" && <Button variant="gold" loading={verify.isPending} onClick={() => verify.mutate()}>{t("verify_val")}</Button>}
        </div>
      </Card>
      {tot && (
        <Card className="mt-5" title={t("calc")} subtitle={`${lang === "ar" ? "تاريخ الحساب" : "Calculated"}: ${val.data.calculated_at?.slice(0, 19).replace("T", " ")} · ${tot.engine}`}>
          <table className="w-full"><tbody>{tot.steps.map((s: any) => (
            <tr key={s.key} className="border-t border-slate-100"><td className="td font-medium">{pick(s)}</td><td className="td num text-xs text-slate-500">{s.formula}</td>
              <td className="td num text-end font-semibold">{fmtMoney(s.value, lang, { currency: tot.currency })}</td></tr>))}</tbody></table>
          {tot.flags.map((f: any) => <div key={f.code} className="mt-2"><Alert tone="warn">{pick(f)}</Alert></div>)}
        </Card>)}
      <Modal open={boqOpen} onClose={() => setBoqOpen(false)} title={t("from_boq")} wide>
        <input className="input mb-3" placeholder={t("search")} value={boqQ} onChange={(e) => setBoqQ(e.target.value)} />
        {boq.isLoading ? <Spinner /> : <table className="w-full"><tbody>{boq.data?.map((b) => (
          <tr key={b.id} className="border-t border-slate-100"><td className="td text-xs">{b.item_ref}</td><td className="td text-sm">{b.description}</td><td className="td text-xs">{b.unit}</td>
            <td className="td num text-sm">{fmtMoney(b.rate, lang)}</td>
            <td className="td"><Button size="sm" onClick={() => { setLines([...lines.filter((l) => l.description), { category: "direct_work", description: `${b.description} (BOQ ${b.item_ref})`, quantity: "1",
              unit: b.unit || "", rate: String(b.rate ?? 0), source_document_id: b.document_id, source_note: `BOQ item ${b.item_ref}`, rate_basis: "boq_rate" }]); setBoqOpen(false); }}>+</Button></td></tr>))}</tbody></table>}
      </Modal>
    </div>
  );
}
