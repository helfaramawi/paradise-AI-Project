import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, ArrowUpRight, CalendarClock, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, Badge, Card, Empty, Modal, PageHeader, RiskBadge, Spinner, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate, fmtMoney, fmtNum, fmtPct, useI18n } from "../lib/i18n";
import { useTaxonomy } from "../lib/taxonomy";

const S = { s1: "#2a78d6", s2: "#eb6834", s3: "#1baf7a", seq: ["#86b6ef", "#3987e5", "#1c5cab", "#0f3d7a"] };
type Kpi = { value: any; count?: number; ids: string[]; entity: string; overdue?: number; unquantified?: number; approved?: number; decided?: number; amount_rate?: number };

function KpiTile({ k, label, value, sub, onClick, tone }: { k: string; label: string; value: string; sub?: string; onClick: () => void; tone?: "risk" | "gold" }) {
  return (
    <button onClick={onClick} data-kpi={k} className={clsx("group rounded-xl border bg-white p-4 text-start shadow-card transition hover:border-brand-500 hover:shadow-md",
      tone === "risk" ? "border-red-200" : tone === "gold" ? "border-gold-400" : "border-slate-200")}>
      <div className="flex items-start justify-between gap-2 text-xs font-medium text-slate-500">{label}<ArrowUpRight className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" /></div>
      <div className="num mt-2 text-2xl font-semibold tracking-tight text-navy-900">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </button>
  );
}

function Drill({ kpi, title, onClose }: { kpi: Kpi | null; title: string; onClose: () => void }) {
  const { t, lang } = useI18n();
  const { label } = useTaxonomy();
  const ids = kpi?.ids?.join(",") || "";
  const path = kpi?.entity === "entitlement" ? "/entitlements" : kpi?.entity === "claim" ? "/claims" : kpi?.entity === "deadline" ? "/deadlines" : null;
  const q = useQuery({ queryKey: ["drill", kpi?.entity, ids], enabled: !!kpi && !!ids && !!path, queryFn: () => api.get<any[]>(path!, { ids }) });
  const projects = useQuery({ queryKey: ["projects"], enabled: kpi?.entity === "project", queryFn: () => api.get<any[]>("/projects") });
  return (
    <Modal open={!!kpi} onClose={onClose} title={`${t("drilldown")}: ${title}`} wide>
      {!ids && <Empty>{t("none")}</Empty>}
      {(q.isLoading || projects.isLoading) && <Spinner />}
      {kpi?.entity === "entitlement" && q.data && (
        <table className="w-full"><thead><tr><th className="th">Ref</th><th className="th">{t("type")}</th><th className="th">{t("status")}</th><th className="th">{t("amount")}</th><th className="th">{t("risk")}</th><th className="th">{t("confidence")}</th></tr></thead>
          <tbody>{q.data.map((e) => <tr key={e.id} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="td"><Link className="font-medium text-brand-600" to={`/entitlements/${e.id}`}>{e.ref}</Link></td><td className="td">{label("entitlement_types", e.entitlement_type)}</td>
            <td className="td"><StatusBadge status={e.status} label={label("entitlement_status", e.status)} /></td><td className="td num">{e.financial_impact ? fmtMoney(e.financial_impact, lang) : t("not_quantified")}</td>
            <td className="td"><RiskBadge level={e.risk_level} /></td><td className="td num">{fmtPct(e.confidence, lang)}</td></tr>)}</tbody></table>)}
      {kpi?.entity === "claim" && q.data && (
        <table className="w-full"><thead><tr><th className="th">Ref</th><th className="th">{t("title")}</th><th className="th">{t("stage")}</th><th className="th">{t("claimed")}</th><th className="th">{t("approved")}</th><th className="th">{t("collected")}</th></tr></thead>
          <tbody>{q.data.map((c) => <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="td"><Link className="font-medium text-brand-600" to={`/claims/${c.id}`}>{c.ref}</Link></td><td className="td">{c.title}</td>
            <td className="td">{label("claim_stages", c.stage)}</td><td className="td num">{fmtMoney(c.claimed_amount, lang)}</td><td className="td num">{fmtMoney(c.approved_amount, lang)}</td><td className="td num">{fmtMoney(c.collected_amount, lang)}</td></tr>)}</tbody></table>)}
      {kpi?.entity === "deadline" && q.data && (
        <table className="w-full"><thead><tr><th className="th">{t("title")}</th><th className="th">{t("due")}</th><th className="th">{t("certainty")}</th></tr></thead>
          <tbody>{q.data.map((d) => <tr key={d.id} className="border-t border-slate-100"><td className="td"><Link className="text-brand-600" to={d.entitlement_id ? `/entitlements/${d.entitlement_id}` : `/projects/${d.project_id}/deadlines`}>{d.title}</Link></td>
            <td className={clsx("td num", d.overdue && "font-semibold text-red-700")}>{fmtDate(d.due_date, lang)}</td><td className="td">{d.certainty}</td></tr>)}</tbody></table>)}
      {kpi?.entity === "project" && projects.data && (
        <table className="w-full"><tbody>{projects.data.filter((p) => kpi.ids.includes(p.id)).map((p) => <tr key={p.id} className="border-t border-slate-100">
          <td className="td"><Link className="text-brand-600" to={`/projects/${p.id}`}>{p.code} — {lang === "ar" ? p.name_ar || p.name : p.name}</Link></td><td className="td num">{fmtMoney(p.contract_value, lang)}</td></tr>)}</tbody></table>)}
    </Modal>
  );
}

const tipStyle = { borderRadius: 8, border: "1px solid #e4e7ec", fontSize: 12 };

export default function Dashboard() {
  const { t, lang, dir } = useI18n();
  const { label } = useTaxonomy();
  const rtl = dir === "rtl";
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<any>("/dashboard/executive") });
  const [drill, setDrill] = useState<{ kpi: Kpi; title: string } | null>(null);
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <Alert tone="error">{t("error")}</Alert>;
  const d = q.data;
  const k: Record<string, Kpi> = d.kpis;
  const money = (v: any) => fmtMoney(v, lang, { compact: true });
  const tile = (key: string, value: string, sub?: string, tone?: "risk" | "gold") =>
    <KpiTile k={key} label={t("k_" + key)} value={value} sub={sub} tone={tone} onClick={() => setDrill({ kpi: k[key], title: t("k_" + key) })} />;
  const pname = (p: any) => (lang === "ar" ? p.name_ar : p.name).replace(" (DEMO)", "").replace(" (عرض توضيحي)", "");
  const byProject = d.by_project.map((p: any) => ({ ...p, label: p.code, potential: +p.potential, at_risk: +p.at_risk, submitted: +p.submitted, approved: +p.approved, collected: +p.collected }));
  const byType = d.by_type.map((x: any) => ({ name: label("entitlement_types", x.type), value: +x.value, count: x.count })).sort((a: any, b: any) => b.value - a.value);
  const pipeline = d.pipeline.filter((s: any) => s.count > 0).map((s: any) => ({ name: label("claim_stages", s.stage), count: s.count, value: +s.value }));
  const trend = d.trend.map((m: any) => ({ month: m.month, detected: +m.detected, submitted: +m.submitted, approved: +m.approved }));
  const yTick = (v: number) => fmtMoney(v, lang, { compact: true });
  const maxRisk = Math.max(1, ...d.by_project.flatMap((p: any) => Object.values(p.risk) as number[]));

  return (
    <div>
      <PageHeader title={t("exec_title")} subtitle={t("exec_sub")} actions={d.demo_data_present && <Badge tone="amber">DEMO DATA</Badge>} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {tile("total_contract_value", money(k.total_contract_value.value), `${k.total_contract_value.ids.length} ${t("nav_projects")}`)}
        {tile("potential_entitlements", money(k.potential_entitlements.value), `${k.potential_entitlements.count} ${t("count")} · ${k.potential_entitlements.unquantified} ${t("unquantified")}`, "gold")}
        {tile("revenue_at_risk", money(k.revenue_at_risk.value), `${k.revenue_at_risk.count} ${t("count")}`, "risk")}
        {tile("critical_deadlines", fmtNum(k.critical_deadlines.value, lang), `${k.critical_deadlines.overdue} ${t("overdue")}`, k.critical_deadlines.overdue ? "risk" : undefined)}
        {tile("evidence_completeness", fmtPct(k.evidence_completeness.value, lang))}
        {tile("claim_conversion_rate", fmtPct(k.claim_conversion_rate.value, lang), k.claim_conversion_rate.decided ? `${k.claim_conversion_rate.approved}/${k.claim_conversion_rate.decided}` : undefined)}
        {tile("claims_in_preparation", money(k.claims_in_preparation.value), `${k.claims_in_preparation.count} ${t("count")}`)}
        {tile("claims_submitted", money(k.claims_submitted.value), `${k.claims_submitted.count} ${t("count")}`)}
        {tile("claims_approved", money(k.claims_approved.value), `${k.claims_approved.count} ${t("count")}`)}
        {tile("claims_rejected", money(k.claims_rejected.value), `${k.claims_rejected.count} ${t("count")}`)}
        {tile("outstanding_approved", money(k.outstanding_approved.value))}
        {tile("cash_collected", money(k.cash_collected.value))}
      </div>
      <p className="mt-2 text-xs text-slate-500">{t("disclaimer")}</p>

      <div className="mt-6 grid gap-5 xl:grid-cols-2">
        <Card title={t("ch_exposure")} subtitle={lang === "ar" ? "المستحقات المحتملة والمعرضة للخطر" : "Potential entitlements and the part at risk"}>
          {byProject.length === 0 ? <Empty>{t("none")}</Empty> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={byProject} barGap={2} margin={{ left: 8, right: 8 }}>
                <CartesianGrid vertical={false} stroke="#eef0f3" />
                <XAxis dataKey="label" reversed={rtl} tick={{ fontSize: 12 }} tickLine={false} axisLine={{ stroke: "#d0d5dd" }} />
                <YAxis orientation={rtl ? "right" : "left"} tickFormatter={yTick} tick={{ fontSize: 11 }} width={70} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v: number) => fmtMoney(v, lang)} contentStyle={tipStyle} cursor={{ fill: "#f2f4f7" }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="potential" name={t("potential")} fill={S.s1} radius={[4, 4, 0, 0]} maxBarSize={44} />
                <Bar dataKey="at_risk" name={t("at_risk")} fill={S.s2} radius={[4, 4, 0, 0]} maxBarSize={44} />
              </BarChart>
            </ResponsiveContainer>)}
        </Card>

        <Card title={t("ch_by_type")}>
          {byType.length === 0 ? <Empty>{t("none")}</Empty> : (
            <div dir="ltr"><ResponsiveContainer width="100%" height={260}>
              <BarChart data={byType} layout="vertical" margin={{ left: 8, right: 84 }}>
                <CartesianGrid horizontal={false} stroke="#eef0f3" />
                <XAxis type="number" tickFormatter={yTick} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" width={190} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v: number) => fmtMoney(v, lang)} contentStyle={tipStyle} cursor={{ fill: "#f2f4f7" }} />
                <Bar dataKey="value" name={t("potential")} fill={S.s1} radius={[0, 4, 4, 0]} maxBarSize={22}
                  label={{ position: "right", fontSize: 11, fill: "#475467", formatter: (v: number) => (v ? yTick(v) : "") }} />
              </BarChart>
            </ResponsiveContainer></div>)}
        </Card>

        <Card title={t("ch_sub_vs_app")} subtitle={lang === "ar" ? "حسب المشروع" : "By project"}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={byProject} barGap={2} margin={{ left: 8, right: 8 }}>
              <CartesianGrid vertical={false} stroke="#eef0f3" />
              <XAxis dataKey="label" reversed={rtl} tick={{ fontSize: 12 }} tickLine={false} axisLine={{ stroke: "#d0d5dd" }} />
              <YAxis orientation={rtl ? "right" : "left"} tickFormatter={yTick} tick={{ fontSize: 11 }} width={70} tickLine={false} axisLine={false} />
              <Tooltip formatter={(v: number) => fmtMoney(v, lang)} contentStyle={tipStyle} cursor={{ fill: "#f2f4f7" }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="submitted" name={t("submitted")} fill={S.seq[0]} radius={[4, 4, 0, 0]} maxBarSize={36} />
              <Bar dataKey="approved" name={t("approved")} fill={S.seq[2]} radius={[4, 4, 0, 0]} maxBarSize={36} />
              <Bar dataKey="collected" name={t("collected")} fill={S.seq[3]} radius={[4, 4, 0, 0]} maxBarSize={36} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title={t("ch_pipeline")} subtitle={lang === "ar" ? "عدد المطالبات في كل مرحلة" : "Number of claims per stage"}>
          {pipeline.length === 0 ? <Empty>{t("none")}</Empty> : (
            <div dir="ltr"><ResponsiveContainer width="100%" height={250}>
              <BarChart data={pipeline} layout="vertical" margin={{ left: 8, right: 84 }}>
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" width={190} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tipStyle} cursor={{ fill: "#f2f4f7" }} formatter={(v: number, _n, p: any) => [`${v} · ${fmtMoney(p.payload.value, lang)}`, t("count")]} />
                <Bar dataKey="count" name={t("count")} fill={S.s1} radius={[0, 4, 4, 0]} maxBarSize={20} label={{ position: "right", fontSize: 11, fill: "#475467" }} />
              </BarChart>
            </ResponsiveContainer></div>)}
        </Card>

        <Card title={t("ch_trend")}>
          {trend.length === 0 ? <Empty>{t("none")}</Empty> : (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={trend} margin={{ left: 8, right: 16 }}>
                <CartesianGrid vertical={false} stroke="#eef0f3" />
                <XAxis dataKey="month" reversed={rtl} tick={{ fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#d0d5dd" }} />
                <YAxis orientation={rtl ? "right" : "left"} tickFormatter={yTick} tick={{ fontSize: 11 }} width={70} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v: number) => fmtMoney(v, lang)} contentStyle={tipStyle} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line dataKey="detected" name={t("detected")} stroke={S.s1} strokeWidth={2} dot={{ r: 4 }} />
                <Line dataKey="submitted" name={t("submitted")} stroke={S.s2} strokeWidth={2} dot={{ r: 4 }} />
                <Line dataKey="approved" name={t("approved")} stroke={S.s3} strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>)}
        </Card>

        <Card title={t("ch_heatmap")} subtitle={lang === "ar" ? "عدد المستحقات المفتوحة حسب مستوى المخاطر" : "Open entitlements by risk level"}>
          <table className="w-full text-sm">
            <thead><tr><th className="th">{t("nav_projects")}</th>{["high", "medium", "low"].map((l) => <th key={l} className="th text-center">{t(l)}</th>)}</tr></thead>
            <tbody>{d.by_project.map((p: any) => (
              <tr key={p.project_id} className="border-t border-slate-100">
                <td className="td"><Link className="text-brand-600 hover:underline" to={`/projects/${p.project_id}/entitlements`}>{p.code} · {pname(p)}</Link></td>
                {["high", "medium", "low"].map((l) => { const n = p.risk[l]; const a = n / maxRisk;
                  return <td key={l} className="p-1"><div className="num grid h-10 place-items-center rounded-md text-sm font-semibold"
                    style={{ background: n ? `rgba(${l === "high" ? "208,59,59" : l === "medium" ? "237,161,0" : "27,175,122"},${0.15 + 0.6 * a})` : "#f2f4f7", color: a > 0.6 ? "#fff" : "#101828" }}>{n}</div></td>; })}
              </tr>))}</tbody>
          </table>
        </Card>

        <Card title={t("ch_deadlines")} actions={<Link to="/deadlines" className="text-xs text-brand-600">{t("calendar")}</Link>}>
          {d.deadlines.length === 0 ? <Empty>{t("none")}</Empty> : (
            <ul className="divide-y divide-slate-100">{d.deadlines.slice(0, 8).map((x: any) => (
              <li key={x.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <div className="flex min-w-0 items-center gap-2">
                  {x.overdue ? <ShieldAlert className="h-4 w-4 shrink-0 text-red-600" /> : x.due_date ? <CalendarClock className="h-4 w-4 shrink-0 text-slate-400" /> : <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />}
                  <Link to={x.entitlement_id ? `/entitlements/${x.entitlement_id}` : "/deadlines"} className="truncate text-navy-900 hover:underline">{x.title}</Link>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {x.certainty !== "determined" && <Badge tone={x.certainty === "ambiguous" ? "violet" : "slate"}>{x.certainty}</Badge>}
                  <span className={clsx("num text-xs", x.overdue ? "font-semibold text-red-700" : x.days_left !== null && x.days_left <= 7 ? "font-semibold text-amber-700" : "text-slate-600")}>
                    {x.due_date ? `${fmtDate(x.due_date, lang)}${x.days_left !== null ? ` · ${x.days_left} ${t("days")}` : ""}` : t("undetermined")}</span>
                </div>
              </li>))}</ul>)}
        </Card>

        <Card title={t("ch_aging")}>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={d.aging} margin={{ left: 8, right: 8 }}>
              <CartesianGrid vertical={false} stroke="#eef0f3" />
              <XAxis dataKey="bucket" reversed={rtl} tick={{ fontSize: 12 }} tickLine={false} axisLine={{ stroke: "#d0d5dd" }} />
              <YAxis orientation={rtl ? "right" : "left"} allowDecimals={false} tick={{ fontSize: 11 }} width={30} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tipStyle} cursor={{ fill: "#f2f4f7" }} />
              <Bar dataKey="count" name={t("count")} fill={S.s1} radius={[4, 4, 0, 0]} maxBarSize={48} label={{ position: "top", fontSize: 11, fill: "#475467" }} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title={t("ch_top")} className="xl:col-span-2">
          <table className="w-full">
            <thead><tr><th className="th">{t("nav_projects")}</th><th className="th">{t("contract_value")}</th><th className="th">{t("potential")}</th><th className="th">{t("at_risk")}</th><th className="th">{t("submitted")}</th><th className="th">{t("approved")}</th><th className="th">{t("collected")}</th></tr></thead>
            <tbody>{d.by_project.map((p: any) => (
              <tr key={p.project_id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="td"><Link className="font-medium text-brand-600" to={`/projects/${p.project_id}`}>{p.code} · {pname(p)}</Link> {p.is_demo && <Badge tone="amber">DEMO</Badge>}</td>
                {["contract_value", "potential", "at_risk", "submitted", "approved", "collected"].map((f) => <td key={f} className="td num">{fmtMoney(p[f], lang)}</td>)}
              </tr>))}</tbody>
          </table>
        </Card>
      </div>
      <Drill kpi={drill?.kpi || null} title={drill?.title || ""} onClose={() => setDrill(null)} />
    </div>
  );
}
