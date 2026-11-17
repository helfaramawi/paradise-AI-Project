import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Button, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { DeadlineTable } from "./ProjectDetail";

export default function DeadlineCalendar() {
  const { t, lang, dir } = useI18n();
  const { can, me } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["all-deadlines"], queryFn: () => api.get<any[]>("/deadlines") });
  const scan = useMutation({ mutationFn: () => api.post<any>("/deadlines/scan"), onSuccess: () => { qc.invalidateQueries({ queryKey: ["notifications"] }); qc.invalidateQueries({ queryKey: ["all-deadlines"] }); } });
  const [cursor, setCursor] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const weekend = me?.organization.weekend_days || [4, 5];
  const cells = useMemo(() => {
    const first = new Date(cursor);
    const start = new Date(first); start.setDate(1 - ((first.getDay() + 1) % 7)); // weeks start Saturday (Egypt)
    return Array.from({ length: 42 }, (_, i) => { const d = new Date(start); d.setDate(start.getDate() + i); return d; });
  }, [cursor]);
  const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const byDay = useMemo(() => { const m: Record<string, any[]> = {}; (q.data || []).forEach((d) => { if (d.due_date) (m[d.due_date] ||= []).push(d); }); return m; }, [q.data]);
  const today = iso(new Date());
  const pyWeekday = (d: Date) => (d.getDay() + 6) % 7;
  const fmtMonth = new Intl.DateTimeFormat(lang === "ar" ? "ar-EG" : "en-GB", { month: "long", year: "numeric" }).format(cursor);
  const wd = Array.from({ length: 7 }, (_, i) => new Intl.DateTimeFormat(lang === "ar" ? "ar-EG" : "en-GB", { weekday: "short" }).format(cells[i]));
  const Prev = dir === "rtl" ? ChevronRight : ChevronLeft; const Next = dir === "rtl" ? ChevronLeft : ChevronRight;
  return (
    <div>
      <PageHeader title={t("calendar")} actions={can("deadline.manage") && <Button variant="secondary" loading={scan.isPending} onClick={() => scan.mutate()}>{t("scan_now")}</Button>} />
      {scan.data && <div className="mb-4"><Alert tone="ok">{scan.data.notifications} {t("notifications")}</Alert></div>}
      {q.isLoading ? <Spinner /> : (<>
        <Card title={fmtMonth} actions={<><button className="rounded p-1.5 hover:bg-slate-100" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}><Prev className="h-4 w-4" /></button>
          <button className="rounded p-1.5 hover:bg-slate-100" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}><Next className="h-4 w-4" /></button></>}>
          <div className="grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 text-xs">
            {wd.map((w) => <div key={w} className="bg-slate-50 p-2 text-center font-semibold text-slate-500">{w}</div>)}
            {cells.map((d) => { const k = iso(d); const items = byDay[k] || []; const inMonth = d.getMonth() === cursor.getMonth();
              return (
                <div key={k} className={clsx("min-h-24 p-1.5", weekend.includes(pyWeekday(d)) ? "bg-slate-50" : "bg-white", !inMonth && "opacity-40")}>
                  <div className={clsx("num mb-1 inline-grid h-6 w-6 place-items-center rounded-full", k === today && "bg-navy-800 text-white")}>{d.getDate()}</div>
                  {items.map((x) => <Link key={x.id} to={x.entitlement_id ? `/entitlements/${x.entitlement_id}` : `/projects/${x.project_id}/deadlines`}
                    className={clsx("mb-1 block truncate rounded px-1 py-0.5", x.overdue ? "bg-red-100 text-red-800" : x.certainty === "determined" ? "bg-brand-50 text-brand-700" : "bg-amber-100 text-amber-900")} title={x.title}>{x.title}</Link>)}
                </div>); })}
          </div>
          <div className="mt-2 flex gap-4 text-xs text-slate-500"><span>■ <span className="text-red-700">{t("overdue")}</span></span><span>■ <span className="text-amber-700">{lang === "ar" ? "تقديري/غامض" : "estimated / ambiguous"}</span></span><span>■ <span className="text-brand-700">{lang === "ar" ? "محدد" : "determined"}</span></span></div>
        </Card>
        <Card className="mt-5" title={t("deadlines")}><DeadlineTable rows={q.data || []} lang={lang} /></Card>
      </>)}
    </div>
  );
}
