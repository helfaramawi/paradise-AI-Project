"""Executive report exports (PDF via ReportLab, Excel via openpyxl), English or Arabic.

Every section labels the nature of its content: FACT (from dataset), ESTIMATE (simulation),
ASSUMPTION, or RECOMMENDATION.
"""

from __future__ import annotations

import io
import os
from datetime import UTC, datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")
FONT_CANDIDATES = [
    (os.path.join(_ASSETS, "DejaVuSans.ttf"), os.path.join(_ASSETS, "DejaVuSans-Bold.ttf")),  # vendored, Arabic-capable
    ("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]
_FONT = None



HOTEL_FIELDS = ("hotel_rooms", "hotel_occupancy_pct", "hotel_adr_egp", "hotel_staff_fte", "hotel_staff_utilization_pct",
                "hotel_fixed_opex", "hotel_guest_score_pct", "hotel_asset_value", "hotel_capex_reserve")
HOTEL_ROWS = [("savings_pct_at_deadline", "Net return at deadline (% of asset value)", "العائد الصافي في الموعد (% من قيمة الأصل)"),
              ("stabilised_yield_pct", "Stabilised return (% of asset value)", "العائد بعد الاستقرار (% من قيمة الأصل)"),
              ("steady_state_net_run_rate", "Stabilised net return (EGP M/yr)", "العائد الصافي بعد الاستقرار (مليون/سنة)"),
              ("one_off_implementation_cost", "Capital investment (EGP M)", "الاستثمار الرأسمالي"),
              ("payback_years", "Payback (years)", "فترة الاسترداد (سنة)"),
              ("net_benefit_12m", "12m net benefit incl. capital (EGP M)", "صافي المنفعة 12 شهراً شاملة الاستثمار"),
              ("max_delay_increase_pct", "Peak rooms out of service (%)", "أقصى نسبة غرف خارج الخدمة"),
              ("min_csat_pct", "Lowest guest score (%)", "أدنى تقييم للنزلاء"),
              ("staff_surplus_fte", "Surplus staff", "العمالة الزائدة")]

def _font() -> tuple[str, str]:
    global _FONT
    if _FONT:
        return _FONT
    for reg, bold in FONT_CANDIDATES:
        if os.path.exists(reg):
            pdfmetrics.registerFont(TTFont("FMSans", reg))
            pdfmetrics.registerFont(TTFont("FMSans-Bold", bold if os.path.exists(bold) else reg))
            _FONT = ("FMSans", "FMSans-Bold")
            return _FONT
    _FONT = ("Helvetica", "Helvetica-Bold")
    return _FONT


def _ar(text: str) -> str:
    """Shape and reorder Arabic for PDF rendering."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except Exception:  # noqa: BLE001
        return text


def _t(lang: str, en: str, ar: str) -> str:
    return _ar(ar) if lang == "ar" else en


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


LABELS = {
    "title": ("Future Mirror AI — Executive Decision Dossier", "مرآة المستقبل — ملف القرار التنفيذي"),
    "summary": ("1. Decision summary", "1. ملخص القرار"),
    "context": ("2. Business context [FACT — synthetic dataset]", "2. سياق العمل [حقيقة — بيانات افتراضية]"),
    "dq": ("3. Data quality assessment", "3. تقييم جودة البيانات"),
    "objectives": ("4. Objectives and constraints", "4. الأهداف والقيود"),
    "futures": ("5. Alternative futures [ESTIMATE — Monte Carlo]", "5. المستقبلات البديلة [تقدير — مونت كارلو]"),
    "assumptions": ("6. Simulation assumptions [ASSUMPTION]", "6. افتراضات المحاكاة [افتراض]"),
    "risks": ("7. Risk analysis [ESTIMATE]", "7. تحليل المخاطر [تقدير]"),
    "court": ("8. Agent Court findings", "8. نتائج محكمة الوكلاء"),
    "collisions": ("9. Decision collisions", "9. تعارضات القرار"),
    "governance": ("10. Governance findings and required approvals", "10. نتائج الحوكمة والموافقات المطلوبة"),
    "rec": ("11. Recommendation [RECOMMENDATION]", "11. التوصية [توصية]"),
    "roadmap": ("12. Next steps and implementation roadmap", "12. الخطوات التالية وخارطة التنفيذ"),
    "kpis": ("13. Expected vs actual KPIs", "13. المؤشرات المتوقعة مقابل الفعلية"),
}


def build_pdf(dossier: dict[str, Any], lang: str = "en", comparisons: list[dict] | None = None) -> bytes:
    reg, bold = _font()
    align = TA_RIGHT if lang == "ar" else TA_LEFT
    h1 = ParagraphStyle("h1", fontName=bold, fontSize=17, leading=22, textColor=colors.HexColor("#0B1F3A"), alignment=align)
    h2 = ParagraphStyle("h2", fontName=bold, fontSize=12.5, leading=17, spaceBefore=10, spaceAfter=4,
                        textColor=colors.HexColor("#1E4E8C"), alignment=align)
    body = ParagraphStyle("b", fontName=reg, fontSize=9, leading=13, alignment=align)
    small = ParagraphStyle("s", fontName=reg, fontSize=7.5, leading=10, textColor=colors.HexColor("#555555"), alignment=align)

    def P(en: str, ar: str | None = None, st=body) -> Paragraph:  # noqa: ANN001
        return Paragraph(_esc(_t(lang, en, ar if ar is not None else en)), st)

    def H(key: str) -> Paragraph:
        en, ar = LABELS[key]
        return Paragraph(_esc(_t(lang, en, ar)), h2)

    def table(rows: list[list[str]], widths: list[float] | None = None) -> Table:
        data = [[Paragraph(_esc(_ar(c) if lang == "ar" else c), small if i else ParagraphStyle(
            "th", parent=small, fontName=bold, textColor=colors.white)) for c in r] for i, r in enumerate(rows)]
        if lang == "ar":
            data = [list(reversed(r)) for r in data]
            widths = list(reversed(widths)) if widths else None
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1F3A")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D3E0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FA")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return t

    d = dossier["decision"]
    ds = dossier["dataset"]
    run = dossier.get("run") or {}
    sim = dossier.get("simulation") or {}
    rec = (run.get("result") or {}).get("recommendation", {})
    res = sim.get("results", {})
    story: list[Any] = [Paragraph(_esc(_t(lang, *LABELS["title"])), h1), Spacer(1, 3)]
    story.append(P(f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC · Decision {d['id'][:8]} · Run {str(run.get('id', ''))[:8]} · "
                   f"Mode: {run.get('mode', 'n/a')} · Model {sim.get('model', {}).get('version', 'n/a') if sim.get('model') else 'n/a'} · "
                   f"Seed {sim.get('seed', 'n/a')} · Fingerprint {sim.get('input_fingerprint', 'n/a')}", None, small))
    story.append(P("SYNTHETIC DEMONSTRATION DATA — not verified company facts.",
                   "بيانات عرض افتراضية — ليست حقائق متحقق منها عن الشركة.", small))

    story += [H("summary"), P(d["title"]), P(d["question"]), Spacer(1, 4)]
    if rec:
        story.append(P(rec.get("headline_en", ""), rec.get("headline_ar", "")))

    data = ds["data"]
    story += [H("context"), table([
        [_t("en", "Metric", ""), "Value"] if lang == "en" else ["المؤشر", "القيمة"],
        *[[k.replace("_", " "), f"{v:,.2f}" if isinstance(v, float) else str(v)] for k, v in data.items()
          if k in (HOTEL_FIELDS if (d.get("controls") or {}).get("domain") == "hotel" else
                   ("annual_revenue", "overdue_receivables", "ontime_collection_rate_pct", "inhouse_recovery_rate_pct",
                    "writeoff_rate_pct", "key_account_overdue_share_pct", "collections_team_fte", "complaint_rate_pct",
                    "csat_pct", "opening_cash")
                   if (d.get("controls") or {}).get("domain") == "collections" else
                   ("annual_opex", "annual_revenue", "employees", "active_projects", "gross_margin_pct", "utilization_pct",
                    "avg_project_delay_pct", "csat_pct", "software_cost", "infrastructure_cost", "contractor_cost",
                    "personnel_cost"))]], [90 * mm, 60 * mm])]

    val = ds.get("validation") or {}
    story += [H("dq"), P(f"Quality score: {val.get('quality_score', 0):.0%}",
                         f"درجة الجودة: {val.get('quality_score', 0):.0%}")]
    story.append(table([["Code", "Severity", "Check"] if lang == "en" else ["الرمز", "الخطورة", "الفحص"],
                        *[[c["code"], c["severity"], c["title_ar"] if lang == "ar" else c["title_en"]]
                          for c in val.get("checks", [])]], [22 * mm, 22 * mm, 126 * mm]))
    story.append(P(val.get("interpretation_en", ""), val.get("interpretation_ar", ""), small))

    story += [H("objectives")]
    for o in d.get("objectives", []):
        story.append(P(f"• {o['description_en']}", f"• {o['description_ar']}"))
    for c in d.get("constraints", []):
        story.append(P(f"• [{c['kind']}] {c['description_en']} ({c['operator']} {c['threshold']})",
                       f"• [{c['kind']}] {c['description_ar']} ({c['operator']} {c['threshold']})"))

    if res:
        story += [H("futures")]
        hdr = ["Metric", "Future A", "Future B", "Future C"] if lang == "en" else ["المؤشر", "أ", "ب", "ج"]
        def q(k: str, m: str, fmt: str = "{:,.1f}") -> str:
            s = res[k]["summary"][m]
            return f"{fmt.format(s['p50'])} [{fmt.format(s['p10'])}–{fmt.format(s['p90'])}]"
        rows = [hdr]
        collections = (d.get("controls") or {}).get("domain") == "collections"
        hotel = (d.get("controls") or {}).get("domain") == "hotel"
        metric_rows = HOTEL_ROWS if hotel else ([("savings_pct_at_deadline", "Collections uplift % at deadline", "نسبة زيادة المتحصلات"),
                        ("run_rate_savings_at_deadline", "Extra collections a year (EGP M)", "المتحصلات الإضافية سنوياً"),
                        ("agency_fees_12m", "Agency fees 12m (EGP M)", "عمولات شركة التحصيل 12 شهراً"),
                        ("one_off_implementation_cost", "Implementation cost (EGP M)", "تكلفة التنفيذ"),
                        ("net_benefit_12m", "12m net cash benefit (EGP M)", "صافي المنفعة النقدية 12 شهراً"),
                        ("dso_days_at_deadline", "DSO at deadline (days)", "فترة التحصيل في الموعد (يوم)"),
                        ("max_delay_increase_pct", "Complaint rate increase (pts)", "زيادة الشكاوى"),
                        ("min_csat_pct", "Minimum CSAT (%)", "أدنى رضا عملاء"),
                        ("relationship_loss_pct", "Key-account attrition (% revenue)", "فقد كبار العملاء (% من الإيرادات)")]
                       if collections else
                       [("savings_pct_at_deadline", "Savings % at deadline", "نسبة الوفورات"),
                        ("run_rate_savings_at_deadline", "Run-rate savings (EGP M)", "الوفورات السنوية"),
                        ("one_off_implementation_cost", "Implementation cost (EGP M)", "تكلفة التنفيذ"),
                        ("net_benefit_12m", "12m net benefit (EGP M)", "صافي المنفعة 12 شهراً"),
                        ("max_delay_increase_pct", "Delay increase (pts)", "زيادة التأخير"),
                        ("min_csat_pct", "Minimum CSAT (%)", "أدنى رضا عملاء"),
                        ("peak_utilization_pct", "Peak utilisation (%)", "أقصى استغلال")])
        for m, en, ar in metric_rows:
            rows.append([ar if lang == "ar" else en, q("A", m), q("B", m), q("C", m)])
        rows.append(["P(meet target)" if lang == "en" else "احتمال تحقيق الهدف",
                     *[f"{res[k]['probabilities']['meet_target']:.0%}" for k in "ABC"]])
        rows.append(["Constraints violated" if lang == "en" else "القيود غير المستوفاة",
                     *[", ".join(res[k]["constraints_violated"]) or "—" for k in "ABC"]])
        at_risk_label = (("Client segments at risk", "شرائح عملاء معرضة للخطر") if collections
                         else ("Spaces closed > 3 months", "مساحات مغلقة أكثر من 3 أشهر") if hotel
                         else ("Projects at risk (DES)", "مشروعات معرضة للخطر"))
        rows.append([at_risk_label[lang == "ar"], *[str(res[k]["project_portfolio"]["projects_at_risk"]) for k in "ABC"]])
        story.append(table(rows, [52 * mm, 39 * mm, 39 * mm, 39 * mm]))
        story.append(P("Values: median [P10–P90] over Monte Carlo iterations.", "القيم: الوسيط [P10–P90] عبر تكرارات مونت كارلو.", small))

        story += [H("assumptions")]
        params = (sim.get("meta") or {}).get("controls", {})
        story.append(P(f"Controls: {params}", None, small))
        sens = res["A"].get("sensitivity", [])[:6]
        story.append(table([["Parameter", "Low", "High", "NB swing (EGP M)"] if lang == "en" else ["المعامل", "أدنى", "أعلى", "التذبذب"],
                            *[[s["label_ar"] if lang == "ar" else s["label_en"], str(s["low_value"]), str(s["high_value"]),
                               f"{s['swing']:.2f}"] for s in sens]], [80 * mm, 25 * mm, 25 * mm, 40 * mm]))

    story += [PageBreak(), H("risks")]
    risks = [r for r in dossier.get("risks", []) if r["scenario_key"] == (rec.get("recommended_strategy") or "B")]
    story.append(table([["Risk", "Prob.", "Impact (EGP M)", "Severity", "Mitigation"] if lang == "en" else
                        ["الخطر", "الاحتمال", "الأثر", "الخطورة", "التخفيف"],
                        *[[r["title_ar"] if lang == "ar" else r["title_en"], f"{r['probability']:.0%}", f"{r['impact_egp_m']:.2f}",
                           r["severity"], r["mitigation_ar"] if lang == "ar" else r["mitigation_en"]] for r in risks]],
                       [42 * mm, 16 * mm, 22 * mm, 18 * mm, 72 * mm]))

    story += [H("court")]
    for f in [x for x in dossier.get("findings", []) if x["phase"] == "court"][:18]:
        story.append(P(f"[{f['agent_key'].upper()} · {f['claim_type'].upper()} · {f['stance']}] {f['text_en']}",
                       f"[{f['agent_key'].upper()} · {f['claim_type']} · {f['stance']}] {f['text_ar']}", small))
    for o in dossier.get("objections", []):
        story.append(P(f"RED TEAM → {o['target_agent'].upper()} ({o['severity']}): {o['text_en']} — Response: "
                       f"{o.get('response_en') or ''} [{o['resolution']}]",
                       f"الفريق الأحمر ← {o['target_agent']} ({o['severity']}): {o['text_ar']} — الرد: {o.get('response_ar') or ''}",
                       small))

    story += [H("collisions")]
    for c in dossier.get("collisions", []):
        story.append(P(f"{c['rule_code']} [{c['severity']}] {c['title_en']}", f"{c['rule_code']} [{c['severity']}] {c['title_ar']}"))

    story += [H("governance")]
    for g in dossier.get("governance", []):
        story.append(P(f"Future {g['scenario_key']}: {g['outcome']} — required roles: {', '.join(g['required_roles']) or '—'}",
                       f"المستقبل {g['scenario_key']}: {g['outcome']} — الأدوار: {', '.join(g['required_roles']) or '—'}"))
    for a in dossier.get("approvals", []):
        story.append(P(f"Approval request ({a['scenario_key']}): {a['status']} · pending: {', '.join(a['pending_roles']) or '—'}",
                       f"طلب اعتماد ({a['scenario_key']}): {a['status']}", small))

    if rec:
        story += [H("rec"), P(rec.get("headline_en", ""), rec.get("headline_ar", "")),
                  P(rec.get("method_en", ""), rec.get("method_ar", ""), small)]
        for o in rec.get("realistic_options", []):
            story.append(P(f"• Future {o['strategy_key']} over {o['implementation_months']} months: achievable "
                           f"{o['achievable_reduction_pct']:.1f}% with hard constraints satisfied",
                           f"• المستقبل {o['strategy_key']} خلال {o['implementation_months']} شهراً: خفض ممكن "
                           f"{o['achievable_reduction_pct']:.1f}% مع استيفاء القيود الإلزامية"))
        story.append(P(rec.get("disclaimer_en", ""), rec.get("disclaimer_ar", ""), small))
        story += [H("roadmap")]
        for s in rec.get("next_steps", []):
            story.append(P(f"• {s['en']}", f"• {s['ar']}"))
        for r in rec.get("roadmap", []):
            story.append(P(f"Months {r['phase']}: {r['en']}", f"الأشهر {r['phase']}: {r['ar']}"))

    story += [H("kpis")]
    if comparisons:
        story.append(table([["Month", "Metric", "Predicted", "Actual", "Error %", "In band"] if lang == "en" else
                            ["الشهر", "المؤشر", "المتوقع", "الفعلي", "الخطأ", "ضمن النطاق"],
                            *[[str(c["month"]), c["metric"], f"{c['predicted']:.2f}", f"{c['actual']:.2f}",
                               f"{c['error_pct']:.1f}", "✓" if c["within_interval"] else "✗"] for c in comparisons]],
                           [16 * mm, 50 * mm, 26 * mm, 26 * mm, 22 * mm, 22 * mm]))
    else:
        story.append(P("No actual outcomes recorded yet.", "لم تُسجل نتائج فعلية بعد."))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm,
                            bottomMargin=14 * mm, title="Future Mirror AI Decision Dossier")
    doc.build(story)
    return buf.getvalue()


def build_excel(dossier: dict[str, Any], lang: str = "en", comparisons: list[dict] | None = None) -> bytes:
    wb = Workbook()
    hdr_font = Font(bold=True, color="FFFFFF")
    hdr_fill = PatternFill("solid", fgColor="0B1F3A")

    def sheet(title: str, headers: list[str], rows: list[list[Any]]):
        ws = wb.create_sheet(title[:31])
        ws.sheet_view.rightToLeft = lang == "ar"
        ws.append(headers)
        for c in ws[1]:
            c.font, c.fill = hdr_font, hdr_fill
        for r in rows:
            ws.append(r)
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(60, max(12, max(len(str(c.value or "")) for c in col) + 2))
        for rr in ws.iter_rows(min_row=2):
            for c in rr:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        return ws

    wb.remove(wb.active)
    d, ds = dossier["decision"], dossier["dataset"]
    run = dossier.get("run") or {}
    rec = (run.get("result") or {}).get("recommendation", {})
    sim = dossier.get("simulation") or {}
    res = sim.get("results", {})
    ar = lang == "ar"
    sheet("Summary" if not ar else "الملخص", ["Field", "Value", "Nature"], [
        ["Decision", d["title"], "input"], ["Question", d["question"], "input"],
        ["Status", d["status"], "fact"], ["Recommendation", rec.get("headline_ar" if ar else "headline_en", ""), "recommendation"],
        ["Run mode", run.get("mode", ""), "fact"], ["Model version", (sim.get("model") or {}).get("version", ""), "fact"],
        ["Seed", sim.get("seed", ""), "fact"], ["Input fingerprint", sim.get("input_fingerprint", ""), "fact"],
        ["Data", "SYNTHETIC demonstration dataset", "label"]])
    sheet("Dataset", ["Field", "Value", "Provenance"], [[k, v, ds["provenance"].get(k, "")] for k, v in ds["data"].items()])
    sheet("Data quality", ["Code", "Severity", "Title", "Detail"],
          [[c["code"], c["severity"], c["title_ar" if ar else "title_en"], c["detail_ar" if ar else "detail_en"]]
           for c in (ds.get("validation") or {}).get("checks", [])])
    if res:
        metrics = list(res["A"]["summary"].keys())
        rows = []
        for k in ["BASELINE", "A", "B", "C"]:
            for m in metrics:
                s = res[k]["summary"][m]
                rows.append([k, m, s["expected"], s["p10"], s["p50"], s["p90"], "estimate"])
        sheet("Futures", ["Scenario", "Metric", "Expected", "P10", "P50", "P90", "Nature"], rows)
        traj_rows = []
        for k in ["BASELINE", "A", "B", "C"]:
            t = res[k]["trajectory"]
            for mth in range(len(t["opex_monthly"]["expected"])):
                traj_rows.append([k, mth, *[t[m]["expected"][mth] for m in t]])
        sheet("Time machine", ["Scenario", "Month", *res["A"]["trajectory"].keys()], traj_rows)
        sheet("Constraints", ["Scenario", "Code", "Name", "P(satisfied)", "Required", "Status"],
              [[k, c["code"], c["name_ar" if ar else "name_en"], c["probability_satisfied"], c["required_probability"], c["status"]]
               for k in "ABC" for c in res[k]["constraints"]])
        sheet("Sensitivity", ["Scenario", "Parameter", "Low", "High", "NB@low", "NB@high", "Swing"],
              [[k, s["parameter"], s["low_value"], s["high_value"], s["net_benefit_at_low"], s["net_benefit_at_high"], s["swing"]]
               for k in "ABC" for s in res[k].get("sensitivity", [])])
    sheet("Agent findings", ["Agent", "Phase", "Code", "Claim type", "Future", "Stance", "Confidence", "Evidence quality", "Text"],
          [[f["agent_key"], f["phase"], f["code"], f["claim_type"], f["strategy_key"] or "", f["stance"], f["confidence"],
            f["evidence_quality"], f["text_ar" if ar else "text_en"]] for f in dossier.get("findings", [])])
    sheet("Objections", ["Raised by", "Target", "Type", "Severity", "Objection", "Response", "Resolution"],
          [[o["raised_by"], o["target_agent"], o["objection_type"], o["severity"], o["text_ar" if ar else "text_en"],
            o.get("response_ar" if ar else "response_en") or "", o["resolution"]] for o in dossier.get("objections", [])])
    sheet("Collisions", ["Rule", "Future", "Severity", "Score", "Title"],
          [[c["rule_code"], c["strategy_key"] or "all", c["severity"], c["severity_score"], c["title_ar" if ar else "title_en"]]
           for c in dossier.get("collisions", [])])
    sheet("Risks", ["Future", "Code", "Risk", "Probability", "Impact EGP M", "Severity", "Basis"],
          [[r["scenario_key"], r["risk_code"], r["title_ar" if ar else "title_en"], r["probability"], r["impact_egp_m"],
            r["severity"], r["basis"]] for r in dossier.get("risks", [])])
    sheet("Governance", ["Future", "Outcome", "Required roles"],
          [[g["scenario_key"], g["outcome"], ", ".join(g["required_roles"])] for g in dossier.get("governance", [])])
    sheet("Expected vs actual", ["Month", "Metric", "Predicted", "P10", "P90", "Actual", "Error %", "Within band"],
          [[c["month"], c["metric"], c["predicted"], c["predicted_p10"], c["predicted_p90"], c["actual"], c["error_pct"],
            c["within_interval"]] for c in (comparisons or [])])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
