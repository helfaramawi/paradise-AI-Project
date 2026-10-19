"""Decision intake: structured interpretation of an executive question (English or Arabic).

Rule-based parser that extracts the target, timeline and constraints. The result is always
shown to the user for confirmation in the intake wizard; nothing is silently assumed.
"""

from __future__ import annotations

import re
from typing import Any

_WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "nine": 9, "ten": 10, "twelve": 12, "eighteen": 18}
_AR_NUM = {"شهر": 1, "شهرين": 2, "ثلاثة": 3, "أربعة": 4, "خمسة": 5, "ستة": 6, "سبعة": 7, "ثمانية": 8,
           "تسعة": 9, "عشرة": 10, "اثني عشر": 12}
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٪", "0123456789%")

MAX_QUESTION_CHARS = 4000

# Controls a hotel question sets when the executive has not: rooms out of service (%), guest-score floor (%),
# capital budget (EGP M) and no automation programme.
HOTEL_CONTROL_DEFAULTS = {"acceptable_delay_increase_pct": 35.0, "min_csat_pct": 60.0, "implementation_budget": 40.0,
                          "automation_investment": 0.0}


def sanitize(text: str) -> str:
    """Strip control characters and cap length (prompt-injection hygiene for any downstream LLM)."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text[:MAX_QUESTION_CHARS].strip()


def parse_decision(question: str) -> dict[str, Any]:
    q = sanitize(question)
    ql = q.lower().translate(_AR_DIGITS)
    found: dict[str, Any] = {"detected": [], "language": "ar" if re.search(r"[؀-ۿ]", q) else "en"}

    pct = re.search(r"(\d{1,2}(?:\.\d+)?)\s*%", ql) or re.search(r"(\d{1,2})\s*(?:percent|بالمائة|في المائة)", ql)
    if pct:
        found["cost_reduction_target_pct"] = float(pct.group(1))
        found["detected"].append("target")

    months = re.search(r"(\d{1,2})\s*(?:months?|أشهر|شهور|شهرا|شهراً)", ql)
    if months:
        found["implementation_months"] = int(months.group(1))
    else:
        for w, n in _WORD_NUM.items():
            if re.search(rf"\b{w}\s+months?\b", ql):
                found["implementation_months"] = n
                break
        else:
            for w, n in _AR_NUM.items():
                if f"{w} أشهر" in q or f"{w} شهور" in q or (w == "شهرين" and w in q):
                    found["implementation_months"] = n
                    break
    if "implementation_months" in found:
        found["detected"].append("timeline")

    opex = re.search(r"(?:egp|جنيه)?\s*(\d{2,4}(?:\.\d+)?)\s*(?:million|m\b|مليون)", ql)
    if opex:
        found["annual_opex"] = float(opex.group(1))
        found["detected"].append("cost_base")

    flags = {
        "no_terminations": [r"without (?:terminating|firing|laying off|layoffs?)", r"no (?:layoffs?|terminations?)",
                            r"دون (?:إنهاء|الاستغناء|تسريح)", r"بدون (?:إنهاء|تسريح|الاستغناء)"],
        "protect_delivery": [r"project delivery", r"delivery", r"تسليم المشروعات", r"التسليم"],
        "protect_contracts": [r"contract", r"تعاقد", r"العقود"],
        "protect_csat": [r"customer satisfaction", r"رضا العملاء"],
    }
    for key, pats in flags.items():
        if any(re.search(p, ql) for p in pats):
            found[key] = True
            found["detected"].append(key)
    if re.search(r"hotel|فندق|فندقي", ql):
        # A state-owned hotel asset: how to get the most out of it. The question rarely states a number, so the
        # controls get documented defaults (shown for confirmation in the intake wizard).
        found["category"] = "asset_utilization"
        found["domain"] = "hotel"
        rooms = re.search(r"(\d{2,4})\s*(?:rooms?|غرفه|غرفة|غرف)", ql)
        if rooms:
            found["hotel_rooms"] = int(rooms.group(1))
            found["detected"].append("rooms")
        name = re.search(r"(?:فندق|hotel)\s+([^\s\d،,(]+)", q, re.IGNORECASE)
        if name:
            found["asset_name"] = name.group(1)
        if re.search(r"مقترحات|بدائل|خيارات|proposals|options|alternatives", ql):
            found["detected"].append("proposals")
        if re.search(r"منطقة الحرة|المنطقة الحرة|free zone", ql):
            found["detected"].append("free_zone")
        found.pop("annual_opex", None)
        found["detected"] = [d for d in found["detected"] if d not in ("cost_base", "protect_contracts", "protect_delivery")]
        for k in ("protect_contracts", "protect_delivery"):
            found.pop(k, None)
        found.setdefault("cost_reduction_target_pct", 6.0)
        found.setdefault("implementation_months", 12)
        found.update(HOTEL_CONTROL_DEFAULTS)
    elif re.search(r"collect|receivable|overdue|debt|dso|متحصلات|تحصيل|المديونيات|مستحقات|الذمم|المتأخرات", ql):
        found["category"] = "collections_improvement"
        found["domain"] = "collections"
        # The percentage stays in cost_reduction_target_pct (the generic target control); here it is a
        # collections uplift, not a cost cut.
        if re.search(r"agency|third[- ]party|outsourc|شركة تحصيل|شركات تحصيل|طرف ثالث|تعهيد", ql):
            found["detected"].append("collection_agency")
            found["mentions_agency"] = True
        found.pop("annual_opex", None)
        found["detected"] = [d for d in found["detected"] if d not in ("cost_base", "protect_contracts")]
        found.pop("protect_contracts", None)
    elif re.search(r"cost|expense|opex|تكالیف|التكاليف|مصروفات|نفقات", ql):
        found["category"] = "opex_optimization"
        found["domain"] = "opex"
    else:
        found["category"] = "unsupported"
    return found


def objectives_and_constraints(controls: dict[str, Any], baseline: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    t = controls["cost_reduction_target_pct"]
    D = controls["implementation_months"]
    if controls.get("domain") == "collections":
        return _collections_objectives(controls, t, D)
    if controls.get("domain") == "hotel":
        return _hotel_objectives(controls, t, D)
    objectives = [
        {"key": "cost_reduction", "metric": "savings_pct_at_deadline", "target_value": t, "priority": 1,
         "description_en": f"Reduce operating costs by {t:.0f}% within {D} months",
         "description_ar": f"خفض التكاليف التشغيلية بنسبة {t:.0f}% خلال {D} أشهر"},
        {"key": "project_delivery", "metric": "max_delay_increase_pct", "target_value": controls["acceptable_delay_increase_pct"],
         "priority": 2, "description_en": "Protect project delivery", "description_ar": "حماية تسليم المشروعات"},
        {"key": "customer_satisfaction", "metric": "min_csat_pct", "target_value": controls["min_csat_pct"], "priority": 2,
         "description_en": "Maintain customer satisfaction", "description_ar": "الحفاظ على رضا العملاء"},
    ]
    constraints = [
        {"key": "no_terminations", "kind": "hard", "metric": "workforce_termination", "operator": "<=", "threshold": 0,
         "description_en": "No employee terminations", "description_ar": "عدم إنهاء خدمة أي موظف"},
        {"key": "delivery", "kind": "hard", "metric": "max_delay_increase_pct", "operator": "<=",
         "threshold": controls["acceptable_delay_increase_pct"],
         "description_en": "Delay increase within acceptable limit", "description_ar": "زيادة التأخير ضمن الحد المقبول"},
        {"key": "contracts", "kind": "hard", "metric": "contractual_delay", "operator": "<=",
         "threshold": baseline.get("contractual_delay_tolerance_pct", 10.0),
         "description_en": "Do not breach contractual delay tolerance", "description_ar": "عدم تجاوز حد التأخير التعاقدي"},
        {"key": "csat", "kind": "hard", "metric": "min_csat_pct", "operator": ">=", "threshold": controls["min_csat_pct"],
         "description_en": "Customer satisfaction floor", "description_ar": "الحد الأدنى لرضا العملاء"},
        {"key": "budget", "kind": "soft", "metric": "one_off_implementation_cost", "operator": "<=",
         "threshold": controls["implementation_budget"],
         "description_en": "Implementation budget", "description_ar": "ميزانية التنفيذ"},
    ]
    return objectives, constraints


def _collections_objectives(controls: dict[str, Any], t: float, D: int) -> tuple[list[dict], list[dict]]:
    objectives = [
        {"key": "collections_uplift", "metric": "savings_pct_at_deadline", "target_value": t, "priority": 1,
         "description_en": f"Collect {t:.0f}% more cash per month within {D} months",
         "description_ar": f"زيادة المتحصلات الشهرية بنسبة {t:.0f}% خلال {D} أشهر"},
        {"key": "customer_relationships", "metric": "max_delay_increase_pct", "target_value": controls["acceptable_delay_increase_pct"],
         "priority": 2, "description_en": "Protect customer relationships", "description_ar": "حماية العلاقة مع العملاء"},
        {"key": "customer_satisfaction", "metric": "min_csat_pct", "target_value": controls["min_csat_pct"], "priority": 2,
         "description_en": "Maintain customer satisfaction", "description_ar": "الحفاظ على رضا العملاء"},
    ]
    constraints = [
        {"key": "no_terminations", "kind": "hard", "metric": "workforce_termination", "operator": "<=", "threshold": 0,
         "description_en": "No employee terminations", "description_ar": "عدم إنهاء خدمة أي موظف"},
        {"key": "complaints", "kind": "hard", "metric": "max_delay_increase_pct", "operator": "<=",
         "threshold": controls["acceptable_delay_increase_pct"],
         "description_en": "Complaint-rate increase within the acceptable limit", "description_ar": "زيادة الشكاوى ضمن الحد المقبول"},
        {"key": "attrition", "kind": "hard", "metric": "relationship_loss_pct", "operator": "<=", "threshold": 1.0,
         "description_en": "Key-account attrition at most 1% of revenue", "description_ar": "فقد كبار العملاء لا يتجاوز 1% من الإيرادات"},
        {"key": "csat", "kind": "hard", "metric": "min_csat_pct", "operator": ">=", "threshold": controls["min_csat_pct"],
         "description_en": "Customer satisfaction floor", "description_ar": "الحد الأدنى لرضا العملاء"},
        {"key": "budget", "kind": "soft", "metric": "one_off_implementation_cost", "operator": "<=",
         "threshold": controls["implementation_budget"],
         "description_en": "Implementation budget", "description_ar": "ميزانية التنفيذ"},
    ]
    return objectives, constraints


def _hotel_objectives(controls: dict[str, Any], t: float, D: int) -> tuple[list[dict], list[dict]]:
    objectives = [
        {"key": "asset_return", "metric": "savings_pct_at_deadline", "target_value": t, "priority": 1,
         "description_en": f"Net annual return of {t:.0f}% of the asset value within {D} months",
         "description_ar": f"عائد سنوي صافٍ {t:.0f}% من قيمة الأصل خلال {D} شهراً"},
        {"key": "service_continuity", "metric": "max_delay_increase_pct", "target_value": controls["acceptable_delay_increase_pct"],
         "priority": 2, "description_en": "Keep the hotel serving guests during the works", "description_ar": "استمرار خدمة النزلاء أثناء الأعمال"},
        {"key": "guest_experience", "metric": "min_csat_pct", "target_value": controls["min_csat_pct"], "priority": 2,
         "description_en": "Maintain the guest score", "description_ar": "الحفاظ على تقييم النزلاء"},
    ]
    constraints = [
        {"key": "no_terminations", "kind": "hard", "metric": "workforce_termination", "operator": "<=", "threshold": 0,
         "description_en": "No employee terminations", "description_ar": "عدم إنهاء خدمة أي موظف"},
        {"key": "rooms_out", "kind": "hard", "metric": "max_delay_increase_pct", "operator": "<=",
         "threshold": controls["acceptable_delay_increase_pct"],
         "description_en": "Rooms out of service within the limit", "description_ar": "الغرف خارج الخدمة ضمن الحد"},
        {"key": "staff_surplus", "kind": "hard", "metric": "staff_surplus_fte", "operator": "<=", "threshold": 25.0,
         "description_en": "Surplus staff within the redeployment capacity", "description_ar": "العمالة الزائدة ضمن طاقة إعادة التوزيع"},
        {"key": "guest_score", "kind": "hard", "metric": "min_csat_pct", "operator": ">=", "threshold": controls["min_csat_pct"],
         "description_en": "Guest score floor", "description_ar": "الحد الأدنى لتقييم النزلاء"},
        {"key": "budget", "kind": "soft", "metric": "one_off_implementation_cost", "operator": "<=",
         "threshold": controls["implementation_budget"],
         "description_en": "Capital budget", "description_ar": "الموازنة الاستثمارية"},
    ]
    return objectives, constraints
