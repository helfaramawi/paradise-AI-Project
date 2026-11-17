const BASE = "/api/v1";
let token: string | null = (() => { try { return sessionStorage.getItem("haqq.token"); } catch { return null; } })();
let onUnauthorized: (() => void) | null = null;

export function setToken(t: string | null) {
  token = t;
  try { t ? sessionStorage.setItem("haqq.token", t) : sessionStorage.removeItem("haqq.token"); } catch { /* storage unavailable */ }
}
export const getToken = () => token;
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn; };

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) { super(message); }
}

async function handle(res: Response) {
  if (res.status === 401 && onUnauthorized && !res.url.includes("/auth/login")) onUnauthorized();
  if (!res.ok) {
    let detail: unknown = undefined;
    let msg = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail;
      msg = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map((d: { msg: string }) => d.msg).join("; ") : msg;
    } catch { /* not json */ }
    throw new ApiError(res.status, msg, detail);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export const api = {
  get: <T = any>(path: string, params?: Record<string, string | number | boolean | undefined | null>): Promise<T> => {
    const qs = params ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => [k, String(v)])).toString() : "";
    return fetch(BASE + path + qs, { headers: headers(false) }).then(handle);
  },
  post: <T = any>(path: string, body?: unknown): Promise<T> =>
    fetch(BASE + path, { method: "POST", headers: headers(), body: body === undefined ? undefined : JSON.stringify(body) }).then(handle),
  put: <T = any>(path: string, body: unknown): Promise<T> =>
    fetch(BASE + path, { method: "PUT", headers: headers(), body: JSON.stringify(body) }).then(handle),
  patch: <T = any>(path: string, body: unknown): Promise<T> =>
    fetch(BASE + path, { method: "PATCH", headers: headers(), body: JSON.stringify(body) }).then(handle),
  del: <T = any>(path: string): Promise<T> => fetch(BASE + path, { method: "DELETE", headers: headers(false) }).then(handle),
  upload: <T = any>(path: string, form: FormData): Promise<T> =>
    fetch(BASE + path, { method: "POST", headers: headers(false), body: form }).then(handle),
  async download(path: string, fallbackName: string) {
    const res = await fetch(BASE + path, { headers: headers(false) });
    if (!res.ok) await handle(res);
    const blob = await res.blob();
    const cd = res.headers.get("content-disposition") || "";
    const m = /filename\*=UTF-8''([^;]+)/.exec(cd) || /filename=([^;]+)/.exec(cd);
    const name = m ? decodeURIComponent(m[1].replace(/"/g, "")) : fallbackName;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  },
  async openBlob(path: string) {
    const res = await fetch(BASE + path, { headers: headers(false) });
    if (!res.ok) await handle(res);
    const url = URL.createObjectURL(await res.blob());
    window.open(url, "_blank", "noopener");
  },
};
