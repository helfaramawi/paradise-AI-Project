"""Deterministic claim valuation. All arithmetic uses Decimal and every total carries its formula.

The LLM never performs these calculations. Overheads, profit and VAT are only applied when the user
sets them, and are flagged as requiring contractual support.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ENGINE_VERSION = "valuation-1.0"
CENT = Decimal("0.01")
CATEGORIES = {
    "direct_work": {"en": "Direct work (BOQ / new rates)", "ar": "أعمال مباشرة (فئات المقايسة / فئات جديدة)"},
    "labour": {"en": "Labour", "ar": "العمالة"},
    "equipment": {"en": "Equipment", "ar": "المعدات"},
    "material": {"en": "Materials", "ar": "المواد"},
    "subcontractor": {"en": "Subcontractors", "ar": "مقاولو الباطن"},
    "site_overheads": {"en": "Extended site overheads", "ar": "المصروفات غير المباشرة الممتدة للموقع"},
    "prolongation": {"en": "Prolongation (time-related costs)", "ar": "تكاليف إطالة المدة"},
    "other": {"en": "Other", "ar": "أخرى"},
}


def q(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class LineIn:
    category: str
    description: str
    quantity: Decimal
    rate: Decimal
    unit: str | None = None
    source: str | None = None


def calculate(lines: list[LineIn], *, overhead_pct: Decimal = Decimal("0"), profit_pct: Decimal = Decimal("0"),
              vat_applicable: bool = False, vat_rate: Decimal = Decimal("14"), currency: str = "EGP",
              fx_rate_to_egp: Decimal = Decimal("1")) -> dict:
    if overhead_pct < 0 or profit_pct < 0 or vat_rate < 0 or fx_rate_to_egp <= 0:
        raise ValueError("Percentages must be non-negative and the FX rate positive")
    line_out, by_cat = [], {}
    for i, ln in enumerate(lines, start=1):
        if ln.category not in CATEGORIES:
            raise ValueError(f"Unknown cost category '{ln.category}'")
        amount = q(Decimal(ln.quantity) * Decimal(ln.rate))
        by_cat[ln.category] = by_cat.get(ln.category, Decimal("0")) + amount
        line_out.append({"line": i, "category": ln.category, "description": ln.description, "quantity": str(ln.quantity),
                         "unit": ln.unit, "rate": str(ln.rate), "amount": str(amount),
                         "formula": f"{ln.quantity} × {ln.rate} = {amount}", "source": ln.source})
    direct = q(sum(by_cat.values(), Decimal("0")))
    overhead = q(direct * overhead_pct / 100)
    subtotal1 = direct + overhead
    profit = q(subtotal1 * profit_pct / 100)
    net = q(subtotal1 + profit)
    vat = q(net * vat_rate / 100) if vat_applicable else Decimal("0.00")
    gross = q(net + vat)
    gross_egp = q(gross * fx_rate_to_egp)
    steps = [
        {"key": "direct", "en": "Direct costs (sum of lines)", "ar": "التكاليف المباشرة (مجموع البنود)",
         "formula": " + ".join(str(v) for v in by_cat.values()) or "0", "value": str(direct)},
        {"key": "overhead", "en": f"Overheads @ {overhead_pct}%", "ar": f"مصروفات عمومية {overhead_pct}%",
         "formula": f"{direct} × {overhead_pct}% = {overhead}", "value": str(overhead)},
        {"key": "profit", "en": f"Profit @ {profit_pct}%", "ar": f"ربح {profit_pct}%",
         "formula": f"({direct} + {overhead}) × {profit_pct}% = {profit}", "value": str(profit)},
        {"key": "net", "en": "Net claim value (excl. VAT)", "ar": "صافي قيمة المطالبة (بدون ضريبة)",
         "formula": f"{direct} + {overhead} + {profit} = {net}", "value": str(net)},
        {"key": "vat", "en": f"VAT @ {vat_rate}%" + ("" if vat_applicable else " (not applied)"),
         "ar": f"ضريبة القيمة المضافة {vat_rate}%" + ("" if vat_applicable else " (غير مطبقة)"),
         "formula": f"{net} × {vat_rate}% = {vat}" if vat_applicable else "—", "value": str(vat)},
        {"key": "gross", "en": f"Total ({currency})", "ar": f"الإجمالي ({currency})",
         "formula": f"{net} + {vat} = {gross}", "value": str(gross)},
    ]
    if currency != "EGP":
        steps.append({"key": "gross_egp", "en": "Total in EGP", "ar": "الإجمالي بالجنيه المصري",
                      "formula": f"{gross} × {fx_rate_to_egp} = {gross_egp}", "value": str(gross_egp)})
    flags = []
    if overhead_pct > 0 or profit_pct > 0:
        flags.append({"code": "markup_needs_basis", "en": "Overheads/profit are recoverable only where the contract "
                      "provides for them (e.g. 'Cost Plus Profit'). Verify the clause.",
                      "ar": "لا تسترد المصروفات العمومية/الأرباح إلا إذا نص العقد على ذلك. تحقق من البند."})
    if vat_applicable:
        flags.append({"code": "vat_treatment", "en": "VAT treatment is an accounting consideration; confirm with Finance.",
                      "ar": "معالجة ضريبة القيمة المضافة اعتبار محاسبي؛ يجب التأكد مع الإدارة المالية."})
    return {"lines": line_out, "by_category": {k: str(q(v)) for k, v in by_cat.items()}, "direct": str(direct),
            "overhead": str(overhead), "profit": str(profit), "net": str(net), "vat": str(vat), "gross": str(gross),
            "gross_egp": str(gross_egp), "currency": currency, "steps": steps, "flags": flags,
            "engine": ENGINE_VERSION}
