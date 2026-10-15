import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Brain,
  Briefcase,
  CheckCircle2,
  Gavel,
  Loader2,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Swords,
  TrendingUp,
  Users,
  Workflow,
  Wrench,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { useI18n } from "@/lib/app";
import type { DictKey } from "@/i18n/dict";

export const cn = (...c: ClassValue[]) => twMerge(clsx(c));

export const FUTURE_COLOR: Record<string, string> = { A: "var(--fa)", B: "var(--fb)", C: "var(--fc)", BASELINE: "var(--fbase)" };
export const FUTURE_LETTER_AR: Record<string, string> = { A: "أ", B: "ب", C: "ج", BASELINE: "—" };

export function futureLabel(k: string, lang: string) {
  if (k === "BASELINE") return lang === "ar" ? "الوضع الحالي" : "Status quo";
  return lang === "ar" ? `المستقبل ${FUTURE_LETTER_AR[k]}` : `Future ${k}`;
}

// ------------------------------------------------------------------ primitives
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "outline" | "danger" | "subtle";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: LucideIcon;
};
export function Button({ variant = "primary", size = "md", loading, icon: Icon, className, children, disabled, ...p }: BtnProps) {
  return (
    <button
      {...p}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 disabled:opacity-50 disabled:cursor-not-allowed",
        size === "sm" && "h-8 px-3 text-xs",
        size === "md" && "h-10 px-4 text-sm",
        size === "lg" && "h-12 px-6 text-base",
        variant === "primary" &&
          "bg-gradient-to-r from-accent to-accent2 text-white shadow-glow hover:brightness-110",
        variant === "ghost" && "text-ink2 hover:bg-panel2",
        variant === "outline" && "border border-line bg-panel/60 text-ink hover:border-accent/60",
        variant === "subtle" && "bg-panel2 text-ink hover:bg-line/60",
        variant === "danger" && "bg-critical/90 text-white hover:bg-critical",
        className,
      )}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </button>
  );
}

export function Card({ className, children, title, subtitle, action, ...p }: {
  className?: string; children?: ReactNode; title?: ReactNode; subtitle?: ReactNode; action?: ReactNode;
  [k: string]: unknown;
}) {
  return (
    <section className={cn("card p-5", className)} {...p}>
      {(title || action) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h3 className="font-display text-[15px] font-semibold text-ink">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Badge({ children, tone = "neutral", className, icon: Icon }: {
  children: ReactNode; tone?: "neutral" | "good" | "warn" | "serious" | "critical" | "accent" | "violet"; className?: string; icon?: LucideIcon;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium",
        tone === "neutral" && "border-line bg-panel2 text-ink2",
        tone === "good" && "border-good/40 bg-good/10 text-good",
        tone === "warn" && "border-warn/40 bg-warn/10 text-amber-600 dark:text-warn",
        tone === "serious" && "border-serious/40 bg-serious/10 text-orange-600 dark:text-serious",
        tone === "critical" && "border-critical/40 bg-critical/10 text-critical dark:text-red-400",
        tone === "accent" && "border-accent/40 bg-accent/10 text-accent",
        tone === "violet" && "border-accent2/40 bg-accent2/10 text-accent2",
        className,
      )}
    >
      {Icon && <Icon className="h-3 w-3" />}
      {children}
    </span>
  );
}

const STATUS_TONE: Record<string, Parameters<typeof Badge>[0]["tone"]> = {
  approved: "good", completed: "good", allowed: "good", acceptable: "good", analyzed: "accent", resolved: "good",
  pending_approval: "warn", pending: "warn", requires_approval: "warn", conditional: "warn", running: "accent",
  analyzing: "accent", queued: "neutral", partially: "warn", needs_analysis: "serious",
  rejected: "critical", failed: "critical", denied: "critical", blocked: "critical", not_acceptable: "critical",
  cancelled: "neutral", draft: "neutral", unresolved: "critical",
  critical: "critical", high: "serious", medium: "warn", low: "neutral",
};
const STATUS_ICON: Record<string, LucideIcon> = {
  approved: CheckCircle2, completed: CheckCircle2, allowed: ShieldCheck, acceptable: CheckCircle2,
  denied: XCircle, blocked: ShieldAlert, rejected: XCircle, failed: XCircle, not_acceptable: XCircle,
  critical: AlertTriangle, high: AlertTriangle, requires_approval: Scale, running: Loader2,
};
export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const key = (`st.${status}` as DictKey);
  const sevKey = (`sev.${status}` as DictKey);
  const resKey = (`court.res.${status}` as DictKey);
  const label = t(key) !== key ? t(key) : t(sevKey) !== sevKey ? t(sevKey) : t(resKey) !== resKey ? t(resKey) : status;
  const Icon = STATUS_ICON[status];
  return (
    <Badge tone={STATUS_TONE[status] || "neutral"} icon={Icon} className={status === "running" ? "[&>svg]:animate-spin" : ""}>
      {label}
    </Badge>
  );
}

const CLAIM_TONE: Record<string, Parameters<typeof Badge>[0]["tone"]> = {
  fact: "good", estimate: "accent", assumption: "warn", hypothesis: "violet", recommendation: "neutral",
};
export function ClaimBadge({ type }: { type: string }) {
  const { t } = useI18n();
  return <Badge tone={CLAIM_TONE[type]}>{t(`claim.${type}` as DictKey)}</Badge>;
}

export function StanceBadge({ stance }: { stance: string }) {
  const { t } = useI18n();
  const tone = stance === "support" ? "good" : stance === "oppose" ? "critical" : stance === "conditional" ? "warn" : "neutral";
  return <Badge tone={tone}>{t(`stance.${stance}` as DictKey)}</Badge>;
}

export function FutureChip({ k, className }: { k: string; className?: string }) {
  const { lang } = useI18n();
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-semibold", className)}>
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: FUTURE_COLOR[k] }} />
      {futureLabel(k, lang)}
    </span>
  );
}

export function Stat({ label, value, sub, tone, icon: Icon, className }: {
  label: ReactNode; value: ReactNode; sub?: ReactNode; tone?: "good" | "critical" | "warn"; icon?: LucideIcon; className?: string;
}) {
  return (
    <div className={cn("card p-4", className)}>
      <div className="flex items-center justify-between">
        <span className="label">{label}</span>
        {Icon && <Icon className="h-4 w-4 text-muted" />}
      </div>
      <div
        className={cn(
          "mt-2 font-display text-2xl font-semibold text-ink",
          tone === "good" && "text-good",
          tone === "critical" && "text-critical dark:text-red-400",
          tone === "warn" && "text-amber-600 dark:text-warn",
        )}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </div>
  );
}

export function Input(p: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...p}
      className={cn(
        "h-10 w-full rounded-xl border border-line bg-panel px-3 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30",
        p.className,
      )}
    />
  );
}
export function Textarea(p: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...p}
      className={cn(
        "w-full rounded-xl border border-line bg-panel p-3 text-sm leading-relaxed text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30",
        p.className,
      )}
    />
  );
}
export function Select({ className, ...p }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...p}
      className={cn("h-10 rounded-xl border border-line bg-panel px-3 text-sm text-ink focus:border-accent focus:outline-none", className)}
    />
  );
}

export function SliderField({ label, value, min, max, step = 1, onChange, format, hint }: {
  label: ReactNode; value: number; min: number; max: number; step?: number; onChange: (v: number) => void;
  format?: (v: number) => string; hint?: ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-ink2">{label}</span>
        <span className="num text-sm font-semibold text-ink">{format ? format(value) : value}</span>
      </div>
      <input type="range" className="w-full" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))} aria-label={typeof label === "string" ? label : undefined} />
      {hint && <div className="mt-0.5 text-[11px] text-muted">{hint}</div>}
    </label>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 text-sm">
      <span className="text-ink2">{label}</span>
      <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={cn("relative h-6 w-11 rounded-full transition", checked ? "bg-accent" : "bg-line")}>
        <span className={cn("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all", checked ? "start-[22px]" : "start-0.5")} />
      </button>
    </label>
  );
}

export function Tabs<T extends string>({ value, onChange, items, className }: {
  value: T; onChange: (v: T) => void; items: { value: T; label: ReactNode }[]; className?: string;
}) {
  return (
    <div className={cn("inline-flex rounded-xl border border-line bg-panel2/60 p-1", className)} role="tablist">
      {items.map((i) => (
        <button key={i.value} role="tab" aria-selected={value === i.value} onClick={() => onChange(i.value)}
          className={cn("relative rounded-lg px-3 py-1.5 text-xs font-medium transition",
            value === i.value ? "text-ink" : "text-muted hover:text-ink2")}>
          {value === i.value && (
            <motion.span layoutId={`tab-${items.map((x) => x.value).join("")}`} className="absolute inset-0 rounded-lg bg-panel shadow"
              transition={{ type: "spring", duration: 0.4 }} />
          )}
          <span className="relative">{i.label}</span>
        </button>
      ))}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, icon: Icon }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; icon?: LucideIcon }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="flex items-start gap-3">
        {Icon && (
          <div className="mt-1 grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-accent/20 to-accent2/20 text-accent">
            <Icon className="h-5 w-5" />
          </div>
        )}
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-ink md:text-[28px]">{title}</h1>
          {subtitle && <p className="mt-1 max-w-3xl text-sm text-muted">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-2 p-8 text-sm text-muted">
      <Loader2 className="h-4 w-4 animate-spin" /> {label || t("loading")}
    </div>
  );
}

export function Empty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="card grid-bg flex flex-col items-center justify-center gap-4 p-12 text-center text-sm text-muted">
      {children}
      {action}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="rounded-xl border border-critical/40 bg-critical/10 p-3 text-sm text-critical dark:text-red-300" role="alert">
      {msg}
    </div>
  );
}

export function Bar({ value, max = 1, color = "rgb(var(--accent))", className }: { value: number; max?: number; color?: string; className?: string }) {
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-panel2", className)}>
      <motion.div className="h-full rounded-full" style={{ background: color }} initial={{ width: 0 }} animate={{ width: `${w}%` }}
        transition={{ duration: 0.6 }} />
    </div>
  );
}

// ------------------------------------------------------------------ agents
export const AGENT_META: Record<string, { icon: LucideIcon; color: string }> = {
  orchestrator: { icon: Workflow, color: "#8b9dc3" },
  strategy: { icon: TrendingUp, color: "#6250d6" },
  cfo: { icon: Briefcase, color: "#2a78d6" },
  coo: { icon: Wrench, color: "#1baf7a" },
  hr: { icon: Users, color: "#e87ba4" },
  delivery: { icon: Brain, color: "#eb6834" },
  legal: { icon: Gavel, color: "#c98500" },
  risk: { icon: ShieldAlert, color: "#e34948" },
  redteam: { icon: Swords, color: "#d03b3b" },
  governance: { icon: Scale, color: "#9085e9" },
};

export function AgentAvatar({ k, size = 36, active }: { k: string; size?: number; active?: boolean }) {
  const m = AGENT_META[k] || AGENT_META.orchestrator;
  const Icon = m.icon;
  return (
    <div
      className={cn("relative grid shrink-0 place-items-center rounded-xl text-white", active && "animate-pulseRing")}
      style={{ width: size, height: size, background: `linear-gradient(135deg, ${m.color}, ${m.color}aa)` }}
    >
      <Icon style={{ width: size * 0.5, height: size * 0.5 }} />
    </div>
  );
}

export function useAgentName() {
  const { lang } = useI18n();
  return (agents: Record<string, { name_en: string; name_ar: string }> | undefined, k: string) => {
    const a = agents?.[k];
    if (!a) return k;
    return lang === "ar" ? a.name_ar : a.name_en;
  };
}
