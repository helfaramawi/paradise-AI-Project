import clsx from "clsx";
import { AlertTriangle, CheckCircle2, CircleAlert, Info, Loader2, X } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useI18n } from "../lib/i18n";

export function Card({ children, className, title, actions, subtitle }: { children: ReactNode; className?: string; title?: ReactNode; actions?: ReactNode; subtitle?: ReactNode }) {
  return (
    <section className={clsx("rounded-xl border border-slate-200 bg-white shadow-card", className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <div><h3 className="text-sm font-semibold text-navy-900">{title}</h3>{subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}</div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" | "gold"; size?: "sm" | "md"; loading?: boolean; icon?: ReactNode };
export function Button({ variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest }: BtnProps) {
  return (
    <button {...rest} disabled={disabled || loading} className={clsx(
      "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
      size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-4 py-2 text-sm",
      variant === "primary" && "bg-navy-800 text-white hover:bg-navy-700",
      variant === "gold" && "bg-gold-500 text-navy-950 hover:bg-gold-400",
      variant === "secondary" && "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
      variant === "ghost" && "text-slate-600 hover:bg-slate-100",
      variant === "danger" && "bg-red-600 text-white hover:bg-red-700", className)}>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}{children}
    </button>
  );
}

export function Badge({ children, tone = "slate", className }: { children: ReactNode; tone?: "slate" | "blue" | "green" | "amber" | "red" | "navy" | "violet"; className?: string }) {
  const tones = { slate: "bg-slate-100 text-slate-700 ring-slate-200", blue: "bg-brand-50 text-brand-700 ring-brand-100",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-200", amber: "bg-amber-50 text-amber-800 ring-amber-200",
    red: "bg-red-50 text-red-700 ring-red-200", navy: "bg-navy-900 text-white ring-navy-900", violet: "bg-violet-50 text-violet-700 ring-violet-200" };
  return <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset", tones[tone], className)}>{children}</span>;
}

const STATUS_TONE: Record<string, "slate" | "blue" | "green" | "amber" | "red" | "violet"> = {
  potential: "blue", insufficient_evidence: "amber", requires_expert_verification: "violet", substantiated: "green", rejected: "red",
  processed: "green", processing: "blue", uploaded: "slate", failed: "red", verified: "green", unverified: "slate", corrected: "blue",
  open: "blue", completed: "green", waived: "slate", pending: "slate", accepted: "green", needs_info: "amber",
};
export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return <Badge tone={STATUS_TONE[status] || "slate"}>{label || status.replace(/_/g, " ")}</Badge>;
}

/** Status colours are reserved for state and always paired with an icon + label. */
export function RiskBadge({ level }: { level: string }) {
  const { t } = useI18n();
  if (level === "high") return <Badge tone="red"><AlertTriangle className="h-3 w-3" />{t("high")}</Badge>;
  if (level === "medium") return <Badge tone="amber"><CircleAlert className="h-3 w-3" />{t("medium")}</Badge>;
  return <Badge tone="green"><CheckCircle2 className="h-3 w-3" />{t("low")}</Badge>;
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2" title={`${pct}%`}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-navy-700" style={{ width: `${pct}%` }} /></div>
      <span className="num text-xs text-slate-600">{pct}%</span>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useI18n();
  return <div className="flex items-center gap-2 p-6 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />{label || t("loading")}</div>;
}

export function Empty({ children, icon }: { children: ReactNode; icon?: ReactNode }) {
  return <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">{icon}{children}</div>;
}

export function Alert({ tone = "info", children, title }: { tone?: "info" | "warn" | "error" | "ok"; children: ReactNode; title?: ReactNode }) {
  const map = { info: ["bg-brand-50 border-brand-100 text-navy-800", Info], warn: ["bg-amber-50 border-amber-200 text-amber-900", AlertTriangle],
    error: ["bg-red-50 border-red-200 text-red-800", CircleAlert], ok: ["bg-emerald-50 border-emerald-200 text-emerald-800", CheckCircle2] } as const;
  const [cls, Icon] = map[tone];
  return <div className={clsx("flex gap-2.5 rounded-lg border p-3 text-sm", cls)}><Icon className="mt-0.5 h-4 w-4 shrink-0" /><div>{title && <div className="font-semibold">{title}</div>}{children}</div></div>;
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; wide?: boolean }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-navy-950/40 p-4 pt-16" onClick={onClose}>
      <div className={clsx("w-full rounded-xl bg-white shadow-xl", wide ? "max-w-4xl" : "max-w-lg")} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h3 className="font-semibold text-navy-900">{title}</h3>
          <button onClick={onClose} className="rounded p-1 text-slate-500 hover:bg-slate-100" aria-label="close"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Tabs({ tabs, active, onChange }: { tabs: { key: string; label: ReactNode; count?: number }[]; active: string; onChange: (k: string) => void }) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-slate-200">
      {tabs.map((tb) => (
        <button key={tb.key} onClick={() => onChange(tb.key)} className={clsx("whitespace-nowrap border-b-2 px-3.5 py-2.5 text-sm font-medium transition",
          active === tb.key ? "border-navy-800 text-navy-900" : "border-transparent text-slate-500 hover:text-slate-800")}>
          {tb.label}{tb.count !== undefined && <span className="ms-1.5 rounded-full bg-slate-100 px-1.5 text-xs text-slate-600">{tb.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Field({ label, children, hint }: { label: ReactNode; children: ReactNode; hint?: ReactNode }) {
  return <label className="block"><span className="label">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}</label>;
}

export function PageHeader({ title, subtitle, actions, crumbs }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; crumbs?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>{crumbs && <div className="mb-1 text-xs text-slate-500">{crumbs}</div>}
        <h1 className="text-2xl font-semibold tracking-tight text-navy-900">{title}</h1>{subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-500">{subtitle}</p>}</div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function DemoBadge() {
  return <Badge tone="amber">DEMO</Badge>;
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return <p className="mt-2 text-sm text-red-600">{error instanceof Error ? error.message : String(error)}</p>;
}
