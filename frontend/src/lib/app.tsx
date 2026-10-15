import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { dictionaries, type DictKey, type Lang } from "@/i18n/dict";
import { api, getToken, setToken } from "./api";

function store(key: string, value?: string): string | null {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
  return value ?? null;
}

// ------------------------------------------------------------------ i18n
type I18n = {
  lang: Lang;
  dir: "ltr" | "rtl";
  setLang: (l: Lang) => void;
  t: (k: DictKey) => string;
  pick: (en?: string | null, ar?: string | null) => string;
  num: (v: number | null | undefined, digits?: number) => string;
  egp: (v: number | null | undefined, digits?: number) => string;
  pct: (v: number | null | undefined, digits?: number) => string;
  prob: (v: number | null | undefined) => string;
  date: (v: string | Date | null | undefined, withTime?: boolean) => string;
};

const I18nCtx = createContext<I18n>(null as unknown as I18n);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>((store("fm_lang") as Lang) || "en");
  const dir = lang === "ar" ? "rtl" : "ltr";
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
  }, [lang, dir]);
  const setLang = useCallback((l: Lang) => {
    store("fm_lang", l);
    setLangState(l);
  }, []);
  const value = useMemo<I18n>(() => {
    const locale = lang === "ar" ? "ar-EG" : "en-US";
    const nf = (d: number) => new Intl.NumberFormat(locale, { minimumFractionDigits: d, maximumFractionDigits: d });
    const ok = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);
    return {
      lang,
      dir,
      setLang,
      t: (k) => dictionaries[lang][k] ?? dictionaries.en[k] ?? k,
      pick: (e, a) => (lang === "ar" ? a || e || "" : e || a || ""),
      num: (v, d = 1) => (ok(v) ? nf(d).format(v) : "—"),
      egp: (v, d = 1) => (ok(v) ? `${nf(d).format(v)} ${lang === "ar" ? "مليون ج.م" : "EGP M"}` : "—"),
      pct: (v, d = 1) => (ok(v) ? `${nf(d).format(v)}%` : "—"),
      prob: (v) => (ok(v) ? new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 }).format(v) : "—"),
      date: (v, withTime = true) =>
        v
          ? new Intl.DateTimeFormat(locale, withTime ? { dateStyle: "medium", timeStyle: "short" } : { dateStyle: "medium" }).format(
              new Date(v),
            )
          : "—",
    };
  }, [lang, dir, setLang]);
  return <I18nCtx.Provider value={value}>{children}</I18nCtx.Provider>;
}

export const useI18n = () => useContext(I18nCtx);

// ------------------------------------------------------------------ theme
type Theme = "dark" | "light";
const ThemeCtx = createContext<{ theme: Theme; toggle: () => void }>({ theme: "dark", toggle: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>((store("fm_theme") as Theme) || "dark");
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  const toggle = useCallback(() => {
    setTheme((t) => {
      const n = t === "dark" ? "light" : "dark";
      store("fm_theme", n);
      return n;
    });
  }, []);
  return <ThemeCtx.Provider value={{ theme, toggle }}>{children}</ThemeCtx.Provider>;
}
export const useTheme = () => useContext(ThemeCtx);

// ------------------------------------------------------------------ auth
export type User = {
  id: string;
  email: string;
  full_name: string;
  title: string;
  roles: { key: string; name_en: string; name_ar: string }[];
  permissions: string[];
};

type Auth = {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  can: (perm: string) => boolean;
  hasRole: (role: string) => boolean;
};
const AuthCtx = createContext<Auth>(null as unknown as Auth);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setReady(true));
    const onUnauth = () => setUser(null);
    window.addEventListener("fm:unauthorized", onUnauth);
    return () => window.removeEventListener("fm:unauthorized", onUnauth);
  }, []);
  const value = useMemo<Auth>(
    () => ({
      user,
      ready,
      login: async (email, password) => {
        const r = await api<{ access_token: string; user: User }>("/auth/login", { method: "POST", json: { email, password } });
        setToken(r.access_token);
        setUser(r.user);
      },
      logout: () => {
        setToken(null);
        setUser(null);
      },
      can: (p) => !!user?.permissions.includes(p),
      hasRole: (r) => !!user?.roles.some((x) => x.key === r),
    }),
    [user, ready],
  );
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
export const useAuth = () => useContext(AuthCtx);

// ------------------------------------------------------------------ active decision
const ActiveCtx = createContext<{ activeId: string | null; setActive: (id: string | null) => void }>({
  activeId: null,
  setActive: () => {},
});
export function ActiveDecisionProvider({ children }: { children: ReactNode }) {
  const [activeId, setActiveId] = useState<string | null>(store("fm_active"));
  const setActive = useCallback((id: string | null) => {
    if (id) store("fm_active", id);
    setActiveId(id);
  }, []);
  return <ActiveCtx.Provider value={{ activeId, setActive }}>{children}</ActiveCtx.Provider>;
}
export const useActiveDecision = () => useContext(ActiveCtx);
