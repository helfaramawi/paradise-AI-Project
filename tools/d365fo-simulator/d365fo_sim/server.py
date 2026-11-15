"""Dynamics 365 Finance & Operations simulator: Entra ID token endpoint + OData data entities.

It answers the same requests a real F&O environment does for a read-only integration:

* ``POST /{tenant}/oauth2/v2.0/token`` (client credentials, ``scope=<environment URL>/.default``)
* ``GET /data/<EntitySet>`` with OData query options and ``cross-company=true``
* ``GET /data`` (service document) and ``GET /data/$metadata`` (types inferred from the data)

``GET /`` shows the test data in the browser (Arabic, right to left). Everything is synthetic.
This is a test double for Future Mirror's connector, not a reproduction of the F&O product.
"""

from __future__ import annotations

import html
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .arabic_data import FM_ACCOUNT_MAPPING, Dataset, generate
from .odata import ODataError, apply_query

ENTITY_TYPES = {"LegalEntities": "LegalEntity", "MainAccounts": "MainAccount", "CustomersV3": "CustomerV3",
                "VendorsV2": "VendorV2", "GeneralJournalAccountEntries": "GeneralJournalAccountEntry"}
NS = "Microsoft.Dynamics.DataEntities"


@dataclass
class Settings:
    tenant_id: str = "7d3c1f2a-5b6e-4c8d-9a01-2b3c4d5e6f70"
    client_id: str = "c9e5b8d4-1a2b-4c3d-8e9f-0a1b2c3d4e5f"
    client_secret: str = "fm-sim-secret-2026"
    default_company: str = "EGMF"
    page_size: int = 1000
    public_urls: list[str] = field(default_factory=lambda: ["https://d365fo-sim:8443", "https://localhost:8443"])
    token_lifetime_s: int = 3599

    @classmethod
    def from_env(cls) -> Settings:
        d = cls()
        return cls(
            tenant_id=os.environ.get("SIM_TENANT_ID", d.tenant_id),
            client_id=os.environ.get("SIM_CLIENT_ID", d.client_id),
            client_secret=os.environ.get("SIM_CLIENT_SECRET") or d.client_secret,
            default_company=os.environ.get("SIM_DEFAULT_COMPANY", d.default_company),
            page_size=int(os.environ.get("SIM_PAGE_SIZE", d.page_size)),
            public_urls=[u.strip().rstrip("/") for u in os.environ.get("SIM_PUBLIC_URLS", ",".join(d.public_urls)).split(",")
                         if u.strip()])


def _odata_error(status: int, message: str, code: str = "") -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _aad_error(status: int, error: str, aadsts: str) -> JSONResponse:
    return JSONResponse({"error": error, "error_description": f"{aadsts}\r\nTrace ID: simulator\r\nTimestamp: "
                                                               f"{time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}",
                         "error_codes": [int(aadsts.split(":")[0][6:])]}, status_code=status)


def _edm(values: list[Any]) -> str:
    v = next((x for x in values if x is not None), "")
    if isinstance(v, bool):
        return "Edm.Boolean"
    if isinstance(v, int | float):
        return "Edm.Decimal"
    if isinstance(v, str) and len(v) == 20 and v[4] == "-" and v[10] == "T":
        return "Edm.DateTimeOffset"
    return "Edm.String"


def create_app(settings: Settings | None = None, data: Dataset | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    ds = data or generate()
    sets = ds.entity_sets()
    tokens: dict[str, float] = {}
    app = FastAPI(title="Dynamics 365 F&O simulator", docs_url=None, redoc_url=None, openapi_url=None)

    def base_url(request: Request) -> str:
        return str(request.base_url).rstrip("/")

    def accepted_scopes(request: Request) -> set[str]:
        return {f"{u}/.default" for u in [*cfg.public_urls, base_url(request)]}

    # ---------------------------------------------------------------- Entra ID (client credentials)
    @app.post("/{tenant}/oauth2/v2.0/token")
    def token(tenant: str, request: Request, grant_type: str = Form(""), client_id: str = Form(""),
              client_secret: str = Form(""), scope: str = Form("")) -> Response:
        if tenant.lower() != cfg.tenant_id.lower():
            return _aad_error(400, "invalid_request", f"AADSTS90002: Tenant '{tenant}' not found.")
        if grant_type != "client_credentials":
            return _aad_error(400, "unsupported_grant_type", "AADSTS70003: The app requested an unsupported grant type.")
        if client_id.lower() != cfg.client_id.lower():
            return _aad_error(400, "unauthorized_client", f"AADSTS700016: Application with identifier '{client_id}' "
                                                          "was not found in the directory.")
        if not secrets.compare_digest(client_secret, cfg.client_secret):
            return _aad_error(401, "invalid_client", "AADSTS7000215: Invalid client secret provided.")
        if scope.rstrip("/") not in accepted_scopes(request):
            return _aad_error(400, "invalid_scope", f"AADSTS500011: The resource principal named "
                                                    f"{scope.removesuffix('/.default')} was not found in the tenant.")
        tok = secrets.token_urlsafe(32)
        tokens[tok] = time.time() + cfg.token_lifetime_s
        return JSONResponse({"token_type": "Bearer", "expires_in": cfg.token_lifetime_s, "ext_expires_in": cfg.token_lifetime_s,
                             "access_token": tok})

    def authorised(request: Request) -> bool:
        auth = request.headers.get("authorization", "")
        tok = auth[7:] if auth.lower().startswith("bearer ") else ""
        return bool(tok) and tokens.get(tok, 0) > time.time()

    # ---------------------------------------------------------------- OData
    @app.get("/data")
    def service_document(request: Request) -> Response:
        if not authorised(request):
            return _odata_error(401, "Authorization has been denied for this request.", "Unauthorized")
        return JSONResponse({"@odata.context": f"{base_url(request)}/data/$metadata",
                             "value": [{"name": n, "kind": "EntitySet", "url": n} for n in sets]})

    @app.get("/data/$metadata")
    def metadata(request: Request) -> Response:
        if not authorised(request):
            return _odata_error(401, "Authorization has been denied for this request.", "Unauthorized")
        types, container = [], []
        for name, rows in sets.items():
            props = "".join(f'<Property Name="{p}" Type="{_edm([r.get(p) for r in rows[:50]])}"/>'
                            for p in (rows[0].keys() if rows else []))
            types.append(f'<EntityType Name="{ENTITY_TYPES[name]}">{props}</EntityType>')
            container.append(f'<EntitySet Name="{name}" EntityType="{NS}.{ENTITY_TYPES[name]}"/>')
        xml = ('<?xml version="1.0" encoding="utf-8"?><edmx:Edmx Version="4.0" '
               'xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx"><edmx:DataServices>'
               f'<Schema Namespace="{NS}" xmlns="http://docs.oasis-open.org/odata/ns/edm">{"".join(types)}'
               f'<EntityContainer Name="Resources">{"".join(container)}</EntityContainer></Schema>'
               '</edmx:DataServices></edmx:Edmx>')
        return Response(xml, media_type="application/xml")

    @app.get("/data/{entity_set}")
    def entity(entity_set: str, request: Request) -> Response:
        if not authorised(request):
            return _odata_error(401, "Authorization has been denied for this request.", "Unauthorized")
        if entity_set not in sets:
            return _odata_error(404, f"Resource not found for the segment '{entity_set}'.")
        params = dict(request.query_params)
        rows = sets[entity_set]
        if rows and "dataAreaId" in rows[0] and params.get("cross-company", "").lower() != "true":
            rows = [r for r in rows if r["dataAreaId"] == cfg.default_company.lower()]
        try:
            offset = int(params.pop("$skiptoken", 0))
            result, total = apply_query(rows, params, f"{NS}.{ENTITY_TYPES[entity_set]}")
        except (ODataError, ValueError) as exc:
            return _odata_error(400, f"The query specified in the URI is not valid. {exc}")
        page_size = cfg.page_size
        prefer = request.headers.get("prefer", "")
        if "odata.maxpagesize=" in prefer:
            try:
                page_size = min(page_size, int(prefer.split("odata.maxpagesize=")[1].split(",")[0]))
            except ValueError:
                pass
        page = result[offset: offset + page_size]
        body: dict[str, Any] = {"@odata.context": f"{base_url(request)}/data/$metadata#{entity_set}"}
        if params.get("$count", "").lower() == "true":
            body["@odata.count"] = total
        body["value"] = page
        if offset + page_size < len(result):
            body["@odata.nextLink"] = (f"{base_url(request)}/data/{entity_set}?"
                                       f"{urlencode({**params, '$skiptoken': offset + page_size})}")
        return JSONResponse(body, headers={"OData-Version": "4.0"})

    # ---------------------------------------------------------------- browser view
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> str:
        companies = [le["LegalEntityId"] for le in ds.legal_entities]
        rows = "".join(
            f"<tr><td>{html.escape(n)}</td>" + "".join(
                f'<td><a href="/browse/{n}?company={c.lower()}">'
                f'{sum(1 for r in sets[n] if r.get("dataAreaId") == c.lower()):,}</a></td>' for c in companies) + "</tr>"
            for n in ("CustomersV3", "VendorsV2", "GeneralJournalAccountEntries"))
        les = "".join(f"<li><b>{le['LegalEntityId']}</b> · {html.escape(le['Name'])} · {html.escape(le['AddressCity'])}</li>"
                      for le in ds.legal_entities)
        first, last = ds.gl_entries[0]["AccountingDate"][:10], max(r["AccountingDate"][:10] for r in ds.gl_entries)
        mapping = ", ".join(f"{p} → {c}" for p, c in FM_ACCOUNT_MAPPING.items())
        return _page("محاكي Dynamics 365 F&O", f"""
<p>بيئة اختبار تحاكي واجهة OData في Dynamics 365 Finance &amp; Operations لاختبار موصّل مرآة المستقبل.
كل البيانات وهمية ومولّدة آلياً. <span dir="ltr">Synthetic test data, not a Microsoft product.</span></p>
<h2>الشركات</h2><ul>{les}</ul>
<h2>البيانات</h2><table><tr><th>الكيان</th>{"".join(f"<th>{c}</th>" for c in companies)}</tr>{rows}
<tr><td>MainAccounts</td><td colspan="{len(companies)}"><a href="/browse/MainAccounts">{len(ds.main_accounts)}</a></td></tr></table>
<p>القيود من {first} إلى {last}.</p>
<p><a href="/explorer">مستكشف OData</a>: سجّل الدخول بالسر ثم جرّب الاستعلامات التي يرسلها الموصّل.</p>
<h2>بيانات الاتصال</h2><table dir="ltr">
<tr><td>Environment URL / Authority</td><td>{html.escape(base_url(request))} (from Docker: https://d365fo-sim:8443)</td></tr>
<tr><td>Tenant ID</td><td>{cfg.tenant_id}</td></tr><tr><td>Client ID</td><td>{cfg.client_id}</td></tr>
<tr><td>Client secret</td><td>FM_D365_FO_CLIENT_SECRET in .env</td></tr>
<tr><td>Default company</td><td>{cfg.default_company} (use legal_entity for another)</td></tr>
<tr><td>Account mapping</td><td>{html.escape(mapping)}</td></tr></table>""")

    @app.get("/browse/{entity_set}", response_class=HTMLResponse)
    def browse(entity_set: str, company: str = "", page: int = 1) -> Response:
        if entity_set not in sets:
            return HTMLResponse(_page("غير موجود", "<p>الكيان غير موجود.</p>"), status_code=404)
        rows = [r for r in sets[entity_set] if not company or r.get("dataAreaId") == company.lower()]
        per = 100
        page = max(1, page)
        chunk = rows[(page - 1) * per: page * per]
        cols = list(rows[0].keys()) if rows else []
        head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
        body = "".join("<tr>" + "".join(f"<td>{html.escape(_fmt(r.get(c)))}</td>" for c in cols) + "</tr>" for r in chunk)
        pages = (len(rows) + per - 1) // per
        nav = " ".join(f'<a href="?company={company}&page={p}">{p}</a>' if p != page else f"<b>{p}</b>"
                       for p in range(1, pages + 1)) if pages > 1 else ""
        return HTMLResponse(_page(f"{entity_set} {company.upper()}",
                                  f'<p><a href="/">رجوع</a> · {len(rows):,} سجل</p><div class="scroll"><table>'
                                  f"<tr>{head}</tr>{body}</table></div><p class='nav'>{nav}</p>"))

    @app.get("/explorer", response_class=HTMLResponse)
    def explorer() -> str:
        """Interactive OData explorer: sign in with the client secret, then run the connector's queries."""
        presets = [
            ("مستند الخدمة", "/data"),
            ("البيانات الوصفية", "/data/$metadata"),
            ("الحسابات الرئيسية", "/data/MainAccounts?$select=MainAccountId,Name,MainAccountType&$top=8"),
            ("عملاء بورسعيد", "/data/CustomersV3?cross-company=true&$filter=AddressCity eq 'بورسعيد'"
                              "&$select=dataAreaId,CustomerAccount,OrganizationName,CreditLimit&$count=true"),
            ("قيود الرواتب", "/data/GeneralJournalAccountEntries?cross-company=true&$filter=dataAreaId eq 'egmf' "
                             "and MainAccount eq '610100' and AccountingDate ge 2026-10-01T00:00:00Z"
                             "&$select=AccountingDate,LedgerAccount,Text,AccountingCurrencyAmount"),
            ("ما يقرؤه الموصّل", "/data/GeneralJournalAccountEntries?cross-company=true&$filter=AccountingDate ge "
                                 "2025-11-01T00:00:00Z and AccountingDate le 2026-10-31T23:59:59Z and dataAreaId eq "
                                 "'egmf'&$select=LedgerAccount,AccountingCurrencyAmount"),
            ("خطأ: حقل غير موجود", "/data/GeneralJournalAccountEntries?$select=Amount&$top=1"),
        ]
        buttons = "".join(f'<button class="preset" data-q="{html.escape(q)}">{html.escape(label)}</button>'
                          for label, q in presets)
        return EXPLORER.replace("{{TENANT}}", cfg.tenant_id).replace("{{CLIENT}}", cfg.client_id) \
            .replace("{{PRESETS}}", buttons)

    return app


EXPLORER = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>مستكشف OData</title><style>
body{font-family:"Segoe UI",Tahoma,Arial,sans-serif;margin:0;color:#0f172a;background:#f1f5f9}
header{background:#0f172a;color:#f8fafc;padding:14px 24px;display:flex;gap:16px;align-items:baseline}
header h1{font-size:20px;margin:0} header span{color:#94a3b8;font-size:13px} header a{color:#93c5fd;margin-inline-start:auto}
main{display:grid;grid-template-columns:360px 1fr;gap:16px;padding:16px 24px}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px}
.card h2{font-size:15px;margin:0 0 10px} label{display:block;font-size:12px;color:#475569;margin:8px 0 3px}
input{width:100%;box-sizing:border-box;padding:7px 9px;border:1px solid #cbd5e1;border-radius:6px;font:13px Consolas,monospace;direction:ltr}
button{font:inherit;font-size:13px;border:0;border-radius:6px;padding:7px 12px;cursor:pointer}
#btn-token,#btn-run{background:#1d4ed8;color:#fff;margin-top:10px}
.preset{display:block;width:100%;text-align:start;background:#eef2ff;color:#1e3a8a;margin-top:6px}
.preset.on{background:#1d4ed8;color:#fff}
#tok{font-size:12px;margin-top:8px;color:#64748b;direction:ltr;text-align:left;word-break:break-all}
#tok.ok{color:#047857} #tok.bad{color:#b91c1c}
.req{display:flex;gap:8px;align-items:center} .req input{flex:1} .req b{font:13px Consolas,monospace;color:#047857}
#status{font-size:13px;margin:10px 0 6px;color:#334155} #status.bad{color:#b91c1c}
pre{direction:ltr;text-align:left;background:#0b1220;color:#e2e8f0;border-radius:8px;padding:14px;margin:0;
  height:560px;overflow:auto;font:13px/1.55 Consolas,monospace;white-space:pre-wrap}
.k{color:#93c5fd}.s{color:#fcd34d}.n{color:#86efac}
</style></head><body>
<header><h1>مستكشف OData</h1><span>محاكي Dynamics 365 F&amp;O · بيانات اختبار وهمية</span><a href="/">الرئيسية</a></header>
<main><div>
<div class="card"><h2>١. تسجيل الدخول (Entra ID)</h2>
<label>Tenant ID</label><input id="tenant" value="{{TENANT}}">
<label>Client ID</label><input id="client" value="{{CLIENT}}">
<label>Client secret</label><input id="secret" type="password" placeholder="FM_D365_FO_CLIENT_SECRET">
<button id="btn-token">الحصول على رمز الدخول</button><div id="tok">لا يوجد رمز بعد</div></div>
<div class="card" style="margin-top:16px"><h2>٢. استعلامات جاهزة</h2>{{PRESETS}}</div>
</div><div class="card"><h2>٣. الطلب والاستجابة</h2>
<div class="req"><b>GET</b><input id="url" value="/data"><button id="btn-run">تنفيذ</button></div>
<div id="status">اختر استعلاماً أو اكتب رابطاً ثم اضغط تنفيذ.</div><pre id="out"></pre></div></main>
<script>
let token = "";
const $ = (id) => document.getElementById(id);
const esc = (s) => s.replace(/[&<>]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function color(json) {
  return esc(json).replace(/("(?:[^"\\\\]|\\\\.)*")(\\s*:)?|\\b(-?\\d+(?:\\.\\d+)?|true|false|null)\\b/g,
    (m, str, colon, num) => str ? (colon ? `<span class="k">${str}</span>${colon}` : `<span class="s">${str}</span>`)
                                : `<span class="n">${num}</span>`);
}
$("btn-token").onclick = async () => {
  const body = new URLSearchParams({grant_type: "client_credentials", client_id: $("client").value,
    client_secret: $("secret").value, scope: location.origin + "/.default"});
  const r = await fetch(`/${$("tenant").value}/oauth2/v2.0/token`, {method: "POST", body});
  const j = await r.json();
  if (r.ok) { token = j.access_token; $("tok").className = "ok";
    $("tok").textContent = `Bearer ${token.slice(0, 18)}… · expires_in ${j.expires_in}s`; }
  else { token = ""; $("tok").className = "bad"; $("tok").textContent = `${r.status} ${j.error}: ${j.error_description.split("\\r")[0]}`; }
};
async function run() {
  const url = $("url").value.trim(), t0 = performance.now();
  const r = await fetch(url, {headers: token ? {Authorization: "Bearer " + token} : {}});
  const ms = Math.round(performance.now() - t0), text = await r.text();
  let out = text, note = "";
  try {
    const j = JSON.parse(text);
    if (Array.isArray(j.value)) {
      note = ` · ${j.value.length.toLocaleString("en")} سجل في هذه الصفحة` +
        (j["@odata.count"] !== undefined ? ` · العدد الكلي ${j["@odata.count"]}` : "") +
        (j["@odata.nextLink"] ? " · توجد صفحة تالية (@odata.nextLink)" : "");
      if (j.value.length > 6) j.value = [...j.value.slice(0, 6), `… و${(j.value.length - 6).toLocaleString("en")} سجل آخر`];
    }
    out = color(JSON.stringify(j, null, 2));
  } catch { out = esc(text.replace(/></g, ">\\n<")); }
  $("status").className = r.ok ? "" : "bad";
  $("status").textContent = `HTTP ${r.status} · ${ms} ms${note}`;
  $("out").innerHTML = out;
}
$("btn-run").onclick = run;
document.querySelectorAll(".preset").forEach((b) => b.onclick = () => {
  document.querySelectorAll(".preset").forEach((x) => x.classList.remove("on"));
  b.classList.add("on"); $("url").value = b.dataset.q; run();
});
</script></body></html>"""


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, date):
        return v.isoformat()
    return "" if v is None else str(v)


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>
body{{font-family:"Segoe UI",Tahoma,Arial,sans-serif;margin:24px;color:#1f2937;background:#fff}}
h1{{font-size:22px}} h2{{font-size:17px;margin-top:24px}} table{{border-collapse:collapse;font-size:13px}}
td,th{{border:1px solid #d1d5db;padding:5px 9px;text-align:start;white-space:nowrap}} th{{background:#f3f4f6}}
a{{color:#1d4ed8}} .scroll{{overflow-x:auto}} .nav{{line-height:2}}</style></head>
<body><h1>{html.escape(title)}</h1>{body}</body></html>"""
