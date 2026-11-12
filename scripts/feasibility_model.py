"""Feasibility Monte Carlo behind the feasibility study (docs/Future_Mirror_AI_SaaS_Feasibility_Study_EN.docx and _AR.docx).

Compares SaaS only, on-premises only and hybrid (on-prem now, SaaS gated at month 12).
Units: EGP million, monthly steps, 60 months; loss probabilities are reported at 36 and 60 months.
All inputs in BASE are assumptions to replace with real pipeline and pricing data.

Usage: python scripts/feasibility_model.py out.json   (needs numpy; takes a few minutes)
"""
import numpy as np, json, sys
N = 20000; T = 60; H = 36
tri = lambda rng, a, m, b, n=N: rng.triangular(a, m, b, n)

BASE = dict(
  # SaaS
  saas_team=0.95, saas_new=(0.4, 1.2, 2.5), saas_arpu=(0.025, 0.045, 0.08), saas_churn=(0.01, 0.02, 0.04),
  saas_var=(0.20, 0.28, 0.40), saas_cloud=0.12, saas_mkt=0.35, public_block=(0.3, 0.5, 0.7),
  # On-prem
  op_team=0.55, op_sales=0.20, op_deals_y=(1.0, 3.0, 6.0), op_lic=(1.5, 3.0, 5.0), op_impl=(0.5, 1.0, 2.0),
  op_impl_margin=0.4, op_support=0.20, op_first=(5, 8, 12),
)

GATE=[0.0]
def simulate(option, seed=1, over=None):
    p = dict(BASE); p.update(over or {})
    rng = np.random.default_rng(seed)
    cash = np.zeros((N, T + 1))
    # common on-prem stream
    def onprem(scale_team=1.0):
        rate = tri(rng, *p["op_deals_y"]) / 12
        lic = tri(rng, *p["op_lic"]); impl = tri(rng, *p["op_impl"]); first = tri(rng, *p["op_first"])
        flows = np.zeros((N, T)); installed = np.zeros(N); inst12 = np.zeros(N)
        for t in range(T):
            deals = rng.poisson(rate) * (t >= first)
            rev = deals * (lic + impl) + installed * lic * p["op_support"] / 12
            cost = deals * impl * (1 - p["op_impl_margin"]) + (p["op_team"] + p["op_sales"]) * scale_team
            installed += deals
            if t == 11: inst12[:] = installed
            flows[:, t] = rev - cost
        return flows, inst12
    def saas(start, team, ga_months):
        ga = start + tri(rng, *ga_months)
        newm = tri(rng, *p["saas_new"]); arpu = tri(rng, *p["saas_arpu"]); churn = tri(rng, *p["saas_churn"])
        var = tri(rng, *p["saas_var"]); block = tri(rng, *p["public_block"])
        newm = newm * (1 - block) / (1 - 0.5)  # public-sector share that refuses cloud; 0.5 is the reference
        flows = np.zeros((N, T)); cust = np.zeros(N)
        for t in range(T):
            live = t >= ga; on = t >= start
            ramp = np.clip((t - ga) / 6, 0, 1)
            cust = cust * (1 - churn) + rng.poisson(np.maximum(newm * ramp, 0)) * live
            rev = cust * arpu
            cost = on * team + live * (p["saas_cloud"] + p["saas_mkt"]) + rev * var
            flows[:, t] = rev - cost
        return flows, cust
    if option == "saas":
        f, cust = saas(0, p["saas_team"], (7, 9, 13)); extra = cust
    elif option == "onprem":
        f, extra = onprem()
    else:  # hybrid: on-prem now; SaaS build from month 12 only if >=2 installs (gate), lighter team reusing code
        f, inst = onprem()
        g, cust = saas(12, p["saas_team"] * 0.75, (5, 6, 9))
        gate = inst >= 2  # go/no-go at month 12: at least two paying on-prem installations
        GATE[0] = float(gate.mean())
        f = f + g * gate[:, None]; extra = cust * gate
    cash[:, 1:] = np.cumsum(f, 1)
    return cash, extra

def stats(cash):
    end = cash[:, H]
    mflow = np.diff(cash, axis=1)
    run_be36 = float((mflow[:, H-3:H].mean(1) > 0).mean())
    ok = np.minimum.accumulate(cash[:, ::-1], 1)[:, ::-1][:, 1:] >= 0
    be = np.where(ok.any(1), np.argmax(ok, 1) + 1.0, np.nan)
    return dict(p_loss=float((end < 0).mean()), p_loss60=float((cash[:, -1] < 0).mean()), p50_60=float(np.median(cash[:, -1])), run_be36=run_be36, p_loss_big=float((end < -10).mean()),
                p10=float(np.percentile(end, 10)), p50=float(np.percentile(end, 50)), p90=float(np.percentile(end, 90)),
                peak_need_p50=float(np.percentile(-cash[:, :H+1].min(1), 50)), peak_need_p90=float(np.percentile(-cash[:, :H+1].min(1), 90)),
                be_p50=float(np.nanmedian(be)) if np.isfinite(be).any() else None,
                p_be=float(np.isfinite(be).mean()))

out = {}
for o in ["saas", "onprem", "hybrid"]:
    c, _ = simulate(o)
    s = stats(c); out[o] = s; s["gate"] = GATE[0] if o == "hybrid" else None
    q = np.percentile(c, [10, 50, 90], 0)
    out[o]["path"] = [dict(m=int(t), p10=round(q[0, t], 1), p50=round(q[1, t], 1), p90=round(q[2, t], 1)) for t in range(0, H + 1, 3)]
print(json.dumps({k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != "path"} for k, v in out.items()}, indent=1))

# sensitivity for SaaS and hybrid: P(loss) when each driver at its low/high end
def sens(option):
    rows = []
    drivers = [("saas_new", "عملاء جدد شهرياً (سحابي)"), ("saas_arpu", "متوسط الاشتراك الشهري"), ("saas_churn", "معدل الإلغاء الشهري"),
               ("public_block", "نسبة الجهات الحكومية الرافضة للسحابة"), ("op_deals_y", "صفقات محلية سنوياً"), ("op_lic", "قيمة الترخيص المحلي"),
               ("saas_var", "تكلفة السحابة والنموذج اللغوي (% من الإيراد)")]
    base = stats(simulate(option, seed=3)[0])["p_loss"]
    for k, name in drivers:
        a, m, b = BASE[k]
        lo = stats(simulate(option, seed=3, over={k: (a, a + 1e-9, a + 2e-9)})[0])["p_loss"]
        hi = stats(simulate(option, seed=3, over={k: (b - 2e-9, b - 1e-9, b)})[0])["p_loss"]
        rows.append(dict(driver=name, low=round(lo * 100, 1), high=round(hi * 100, 1)))
    return base, rows
for o in ["hybrid", "saas"]:
    b, r = sens(o); out[o + "_sens"] = dict(base=b, rows=r); print(o, round(b, 3), r)
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "out.json", "w"), ensure_ascii=False, indent=1)
