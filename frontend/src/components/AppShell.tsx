import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  BadgeCheck,
  Cable,
  Clock3,
  Database,
  FlaskConical,
  Gauge,
  GitCompareArrows,
  History,
  Landmark,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Octagon,
  PlusCircle,
  Scale,
  ShieldCheck,
  Sparkles,
  Sun,
  Swords,
  Users,
  Workflow,
  X,
  type LucideIcon,
} from "lucide-react";
import { useAuth, useI18n, useTheme } from "@/lib/app";
import { usePlatform } from "@/lib/hooks";
import type { DictKey } from "@/i18n/dict";
import { Badge, cn } from "./ui";

type Item = { to: string; key: DictKey; icon: LucideIcon; perm?: string };
const GROUPS: { key: DictKey; items: Item[] }[] = [
  {
    key: "nav.group.command",
    items: [
      { to: "/", key: "nav.command", icon: LayoutDashboard },
      { to: "/decisions", key: "nav.workspace", icon: Landmark },
      { to: "/decisions/new", key: "nav.intake", icon: PlusCircle, perm: "decision.create" },
    ],
  },
  {
    key: "nav.group.decision",
    items: [
      { to: "/execution", key: "nav.execution", icon: Activity },
      { to: "/court", key: "nav.court", icon: Swords },
      { to: "/futures", key: "nav.futures", icon: GitCompareArrows },
      { to: "/time-machine", key: "nav.timemachine", icon: Clock3 },
      { to: "/lab", key: "nav.lab", icon: FlaskConical, perm: "simulation.run" },
      { to: "/financial", key: "nav.financial", icon: Gauge },
      { to: "/risk", key: "nav.risk", icon: ShieldCheck },
      { to: "/approvals", key: "nav.approvals", icon: BadgeCheck },
      { to: "/history", key: "nav.history", icon: History },
      { to: "/outcomes", key: "nav.outcomes", icon: Sparkles },
    ],
  },
  {
    key: "nav.group.platform",
    items: [
      { to: "/data", key: "nav.data", icon: Database },
      { to: "/automation", key: "nav.automation", icon: Workflow },
      { to: "/governance", key: "nav.governance", icon: Scale },
      { to: "/admin", key: "nav.admin", icon: Users },
    ],
  },
];

function Logo() {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-3 px-2">
      <img src="/favicon.svg" className="h-9 w-9" alt="" />
      <div className="leading-tight">
        <div className="font-display text-[15px] font-semibold text-ink">{t("appName")}</div>
        <div className="text-[10.5px] text-muted">{t("tagline")}</div>
      </div>
    </div>
  );
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n();
  const { can } = useAuth();
  return (
    <nav className="mt-6 space-y-5">
      {GROUPS.map((g) => (
        <div key={g.key}>
          <div className="label mb-1.5 px-3">{t(g.key)}</div>
          <div className="space-y-0.5">
            {g.items.filter((i) => !i.perm || can(i.perm)).map((i) => (
              <NavLink key={i.to} to={i.to} end={i.to === "/" || i.to === "/decisions"} onClick={onNavigate}
                className={({ isActive }) => cn(
                  "group relative flex items-center gap-3 rounded-xl px-3 py-2 text-[13px] transition",
                  isActive ? "bg-gradient-to-r from-accent/15 to-transparent text-ink" : "text-ink2 hover:bg-panel2 hover:text-ink",
                )}>
                {({ isActive }) => (
                  <>
                    {isActive && <motion.span layoutId="nav-active" className="absolute inset-y-1 start-0 w-0.5 rounded-full bg-accent" />}
                    <i.icon className={cn("h-4 w-4", isActive ? "text-accent" : "text-muted group-hover:text-ink2")} />
                    {t(i.key)}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { t, lang, setLang } = useI18n();
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();
  const { data: platform } = usePlatform();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 overflow-y-auto border-e border-line/60 bg-panel/50 p-4 backdrop-blur-xl scroll-thin lg:block">
        <Logo />
        <Nav />
      </aside>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-50 bg-black/50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}>
            <motion.aside initial={{ x: lang === "ar" ? 300 : -300 }} animate={{ x: 0 }} exit={{ x: lang === "ar" ? 300 : -300 }}
              className="absolute inset-y-0 start-0 w-72 overflow-y-auto bg-panel p-4" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between"><Logo /><button onClick={() => setOpen(false)} aria-label="close"><X className="h-5 w-5" /></button></div>
              <Nav onNavigate={() => setOpen(false)} />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex flex-wrap items-center gap-2 border-b border-line/60 bg-bg/70 px-4 py-2.5 backdrop-blur-xl md:px-6">
          <button className="lg:hidden" onClick={() => setOpen(true)} aria-label="menu"><Menu className="h-5 w-5" /></button>
          <div className="flex flex-1 flex-wrap items-center gap-1.5" data-testid="platform-chips">
            <Badge tone="warn" icon={Database}>{t("chip.synthetic")}</Badge>
            {platform && (
              <Badge tone={platform.llm.mode === "rule_based" ? "violet" : "accent"} icon={Cable}>
                {platform.llm.mode === "rule_based" ? t("chip.rule") : `${t("chip.llm")} · ${platform.llm.provider}`}
              </Badge>
            )}
            {platform && !platform.external_actions_enabled && <Badge tone="good" icon={ShieldCheck}>{t("chip.extOff")}</Badge>}
            {platform?.emergency_stop && <Badge tone="critical" icon={Octagon} className="animate-pulse">{t("chip.stop")}</Badge>}
          </div>
          <button onClick={() => setLang(lang === "en" ? "ar" : "en")} data-testid="lang-toggle"
            className="h-8 rounded-lg border border-line px-2.5 text-xs font-semibold text-ink2 hover:border-accent">
            {lang === "en" ? "العربية" : "English"}
          </button>
          <button onClick={toggle} className="grid h-8 w-8 place-items-center rounded-lg border border-line text-ink2 hover:border-accent"
            aria-label={theme === "dark" ? t("theme.light") : t("theme.dark")} data-testid="theme-toggle">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          {user && (
            <div className="flex items-center gap-2 ps-2">
              <div className="hidden text-end leading-tight sm:block">
                <div className="text-xs font-semibold text-ink">{user.full_name}</div>
                <div className="text-[10.5px] text-muted">{user.roles.map((r) => (lang === "ar" ? r.name_ar : r.name_en)).join(", ")}</div>
              </div>
              <button onClick={() => { logout(); nav("/login"); }} className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:text-ink" aria-label={t("logout")}>
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          )}
        </header>
        <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-6 md:px-6">{children}</main>
      </div>
    </div>
  );
}
