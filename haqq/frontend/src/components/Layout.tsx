import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Bell, BarChart3, Building2, CalendarClock, CreditCard, FileSpreadsheet, Languages, LogOut, Settings, ShieldCheck, Users } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, useI18n } from "../lib/i18n";

export function Logo({ light = false }: { light?: boolean }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid h-9 w-9 place-items-center rounded-lg bg-gold-500 text-lg font-bold text-navy-950">ح</div>
      <div className="leading-tight">
        <div className={clsx("text-base font-bold tracking-wide", light ? "text-white" : "text-navy-900")}>HAQQ <span className="font-ar">حقّك</span></div>
        <div className={clsx("text-[10px]", light ? "text-slate-300" : "text-slate-500")}>{t("by_pais")}</div>
      </div>
    </div>
  );
}

function Item({ to, icon, children, end }: { to: string; icon: ReactNode; children: ReactNode; end?: boolean }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => clsx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
      isActive ? "bg-white/10 font-medium text-white" : "text-slate-300 hover:bg-white/5 hover:text-white")}>
      {icon}<span>{children}</span>
    </NavLink>
  );
}

function Notifications() {
  const { t, lang } = useI18n();
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["notifications"], queryFn: () => api.get<any[]>("/notifications"), refetchInterval: 60000 });
  const readAll = useMutation({ mutationFn: () => api.post("/notifications/read-all"), onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }) });
  const unread = (q.data || []).filter((n) => !n.read).length;
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-label={t("notifications")}>
        <Bell className="h-5 w-5" />
        {unread > 0 && <span className="absolute -top-0.5 end-0 grid h-4 min-w-4 place-items-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">{unread}</span>}
      </button>
      {open && (
        <div className="absolute end-0 z-40 mt-2 w-96 rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b px-4 py-2.5"><span className="text-sm font-semibold">{t("notifications")}</span>
            <button className="text-xs text-brand-600" onClick={() => readAll.mutate()}>{t("mark_all_read")}</button></div>
          <div className="max-h-96 overflow-y-auto">
            {(q.data || []).length === 0 && <p className="p-4 text-sm text-slate-500">{t("none")}</p>}
            {(q.data || []).map((n) => (
              <Link key={n.id} to={n.link || "#"} onClick={() => setOpen(false)} className={clsx("block border-b border-slate-100 px-4 py-3 text-sm hover:bg-slate-50", !n.read && "bg-brand-50/40")}>
                <div className="font-medium text-navy-900">{n.title}</div>
                <div className="mt-0.5 text-xs text-slate-500">{fmtDate(n.created_at, lang)} · email: {n.email_status}</div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const { me, logout, can } = useAuth();
  const { t, lang, setLang, pick } = useI18n();
  const ic = "h-4 w-4";
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-navy-950 px-3 py-5 lg:flex">
        <div className="px-2 pb-6"><Logo light /></div>
        <nav className="flex-1 space-y-1">
          {can("dashboard.executive") && <Item to="/" end icon={<BarChart3 className={ic} />}>{t("nav_dashboard")}</Item>}
          <Item to="/projects" icon={<Building2 className={ic} />}>{t("nav_projects")}</Item>
          <Item to="/deadlines" icon={<CalendarClock className={ic} />}>{t("nav_deadlines")}</Item>
          {can("report.export") && <Item to="/reports" icon={<FileSpreadsheet className={ic} />}>{t("nav_reports")}</Item>}
          <div className="px-3 pb-1 pt-5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">{t("nav_admin")}</div>
          <Item to="/admin/users" icon={<Users className={ic} />}>{t("nav_users")}</Item>
          {(can("admin.org") || can("audit.read")) && <Item to="/admin/settings" icon={<Settings className={ic} />}>{t("nav_settings")}</Item>}
          <Item to="/admin/subscription" icon={<CreditCard className={ic} />}>{t("nav_subscription")}</Item>
          {me?.is_platform_admin && <Item to="/platform" icon={<ShieldCheck className={ic} />}>{t("nav_platform")}</Item>}
        </nav>
        <div className="rounded-lg bg-white/5 p-3 text-xs text-slate-300">
          <div className="font-medium text-white">{me?.full_name}</div>
          <div>{pick(me?.role_label)}</div>
          <div className="mt-1 truncate text-slate-400">{lang === "ar" ? me?.organization.name_ar || me?.organization.name : me?.organization.name}</div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:px-8">
          <div className="lg:hidden"><Logo /></div>
          <div className="hidden text-sm text-slate-500 lg:block">{t("tagline")}</div>
          <div className="flex items-center gap-1">
            <Notifications />
            <button onClick={() => setLang(lang === "ar" ? "en" : "ar")} className="flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm text-slate-600 hover:bg-slate-100" data-testid="lang-toggle">
              <Languages className="h-4 w-4" />{t("language")}
            </button>
            <button onClick={logout} className="flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm text-slate-600 hover:bg-slate-100"><LogOut className="h-4 w-4" />{t("logout")}</button>
          </div>
        </header>
        {me?.organization.is_demo && <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs font-medium text-amber-900 lg:px-8">{t("demo_banner")}</div>}
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
