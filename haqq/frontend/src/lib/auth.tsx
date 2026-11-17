import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api";

export type Me = {
  id: string; email: string; full_name: string; role: string; title: string | null; language: "en" | "ar";
  is_platform_admin: boolean; mfa_enabled: boolean; permissions: string[];
  role_label: { en: string; ar: string };
  organization: { id: string; name: string; name_ar: string | null; is_demo: boolean; onboarding_completed: boolean;
    ai_external_processing: boolean; weekend_days: number[]; holidays: string[]; vat_rate: string; data_retention_days: number;
    default_language: string };
};

type Ctx = { me: Me | null; loading: boolean; login: (email: string, password: string, mfa?: string) => Promise<void>;
  acceptSession: (payload: { access_token: string; user: Me }) => void; logout: () => void; refresh: () => Promise<void>;
  can: (perm: string) => boolean };
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(!!getToken());
  const qc = useQueryClient();

  const refresh = useCallback(async () => {
    if (!getToken()) { setMe(null); setLoading(false); return; }
    try { setMe(await api.get<Me>("/auth/me")); } catch { setToken(null); setMe(null); } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => { setToken(null); setMe(null); qc.clear(); });
    refresh();
  }, [refresh, qc]);

  const acceptSession = (payload: { access_token: string; user: Me }) => { setToken(payload.access_token); setMe(payload.user); };
  const login = async (email: string, password: string, mfa?: string) => {
    const r = await api.post<{ access_token: string; user: Me }>("/auth/login", { email, password, mfa_code: mfa || undefined });
    acceptSession(r);
  };
  const logout = () => { api.post("/auth/logout").catch(() => undefined); setToken(null); setMe(null); qc.clear(); };
  const can = (perm: string) => !!me?.permissions.includes(perm);
  return <AuthCtx.Provider value={{ me, loading, login, acceptSession, logout, refresh, can }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
