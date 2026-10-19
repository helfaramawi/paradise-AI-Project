"""Declarative governance policy engine (enforced in code, outside any LLM prompt).

Policies are JSON documents stored in the database:

    {"when": {"all": [{"fact": "action.levers.workforce_termination", "op": "gt", "value": 0}]},
     "roles": ["cfo"], "message_en": "...", "message_ar": "..."}

Conditions support nested ``all`` / ``any`` / ``not`` and the operators below. The engine is
deliberately small and deterministic so it can be unit-tested exhaustively; it mirrors the
evaluation model of Open Policy Agent (input document + policies -> decision) so policies can
be ported to Rego later without changing call sites.

Outcome precedence: any matching ``deny`` -> denied; else any ``require_approval`` ->
requires_approval (union of roles); else allowed. AI agent recommendations are NOT an input
that can override a deny.
"""

from __future__ import annotations

from typing import Any

_MISSING = object()


def resolve(fact: str, ctx: dict[str, Any]) -> Any:
    cur: Any = ctx
    for part in fact.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def _cmp(op: str, left: Any, right: Any) -> bool:
    if left is _MISSING:
        return op == "missing"
    match op:
        case "eq": return left == right
        case "ne": return left != right
        case "gt": return left is not None and left > right
        case "gte": return left is not None and left >= right
        case "lt": return left is not None and left < right
        case "lte": return left is not None and left <= right
        case "in": return left in right
        case "contains": return right in (left or [])
        case "truthy": return bool(left)
        case "falsy": return not bool(left)
        case "exists": return True
        case "missing": return False
        case "len_gt": return len(left or []) > right
    raise ValueError(f"Unknown operator {op}")


def evaluate_condition(cond: dict[str, Any], ctx: dict[str, Any]) -> bool:
    if "all" in cond:
        return all(evaluate_condition(c, ctx) for c in cond["all"])
    if "any" in cond:
        return any(evaluate_condition(c, ctx) for c in cond["any"])
    if "not" in cond:
        return not evaluate_condition(cond["not"], ctx)
    return _cmp(cond["op"], resolve(cond["fact"], ctx), cond.get("value"))


def evaluate_policies(policies: list[dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any]:
    results = []
    denied = False
    roles: list[str] = []
    acknowledgements: list[str] = []
    for p in policies:
        if not p.get("enabled", True):
            results.append({"code": p["code"], "matched": False, "skipped": True, "effect": p["effect"]})
            continue
        rule = p["rule"]
        if rule.get("kind") == "procedural":
            # Enforced procedurally elsewhere (e.g. separation of duties in approval service).
            results.append({"code": p["code"], "matched": False, "procedural": True, "effect": p["effect"],
                            "name_en": p.get("name_en"), "name_ar": p.get("name_ar")})
            continue
        matched = evaluate_condition(rule["when"], ctx)
        r = {
            "code": p["code"], "matched": matched, "effect": p["effect"],
            "name_en": p.get("name_en"), "name_ar": p.get("name_ar"),
            "message_en": rule.get("message_en", ""), "message_ar": rule.get("message_ar", ""),
        }
        if matched:
            if p["effect"] == "deny":
                denied = True
            elif p["effect"] == "require_approval":
                for role in rule.get("roles", []):
                    if role not in roles:
                        roles.append(role)
                r["roles"] = rule.get("roles", [])
            elif p["effect"] == "require_acknowledgement":
                acknowledgements.append(p["code"])
        results.append(r)
    outcome = "denied" if denied else ("requires_approval" if roles else "allowed")
    return {
        "outcome": outcome,
        "required_roles": [] if denied else roles,
        "acknowledgements": acknowledgements,
        "policy_results": results,
        "deny_reasons": [r for r in results if r.get("matched") and r["effect"] == "deny"],
    }


def _c(fact: str, op: str, value: Any = None) -> dict[str, Any]:
    return {"fact": fact, "op": op, "value": value}


DEFAULT_POLICIES: list[dict[str, Any]] = [
    {
        "code": "GOV-001", "effect": "deny", "locked": True,
        "name_en": "No employee terminations", "name_ar": "حظر إنهاء خدمة الموظفين",
        "description_en": "Any strategy or action that terminates employees is prohibited while the decision "
                          "carries a no-termination constraint.",
        "description_ar": "يُحظر أي إجراء يتضمن إنهاء خدمة موظفين طالما تضمن القرار قيد عدم الإنهاء.",
        "rule": {"when": {"any": [
            {"all": [_c("action.levers.workforce_termination", "gt", 0), _c("decision.no_terminations", "truthy")]},
            _c("action.type", "eq", "workforce.terminate"),
        ]},
            "message_en": "Blocked: the action terminates employees, which violates the no-termination constraint.",
            "message_ar": "مرفوض: الإجراء يتضمن إنهاء خدمة موظفين وهو ما يخالف قيد عدم الإنهاء."},
    },
    {
        "code": "GOV-002", "effect": "deny", "locked": True,
        "name_en": "AI agents cannot execute decisions", "name_ar": "وكلاء الذكاء الاصطناعي لا ينفذون القرارات",
        "description_en": "Agents may analyse and recommend. Any execution request originating from an agent is denied.",
        "description_ar": "يجوز للوكلاء التحليل والتوصية فقط. يُرفض أي طلب تنفيذ صادر عن وكيل.",
        "rule": {"when": {"all": [_c("action.actor_type", "eq", "agent"), _c("action.mode", "eq", "execute")]},
                 "message_en": "Blocked: execution requested by an AI agent. Only authorised humans may execute.",
                 "message_ar": "مرفوض: طلب تنفيذ من وكيل ذكاء اصطناعي. التنفيذ للمخولين من البشر فقط."},
    },
    {
        "code": "GOV-003", "effect": "deny", "locked": True,
        "name_en": "External system writes disabled", "name_ar": "الكتابة في الأنظمة الخارجية معطلة",
        "description_en": "MVP is read-only with respect to ERP and other external systems.",
        "description_ar": "النسخة الحالية للقراءة فقط بالنسبة لأنظمة تخطيط الموارد والأنظمة الخارجية.",
        "rule": {"when": {"all": [_c("action.external_write", "truthy"),
                                  _c("platform.external_actions_enabled", "falsy")]},
                 "message_en": "Blocked: external writes are disabled on this platform.",
                 "message_ar": "مرفوض: الكتابة في الأنظمة الخارجية معطلة على هذه المنصة."},
    },
    {
        "code": "GOV-004", "effect": "require_approval",
        "name_en": "CFO approval above EGP 1M impact", "name_ar": "موافقة المدير المالي فوق مليون جنيه",
        "description_en": "Actions with financial impact of EGP 1M or more require CFO approval.",
        "description_ar": "الإجراءات ذات الأثر المالي مليون جنيه فأكثر تتطلب موافقة المدير المالي.",
        "rule": {"when": _c("action.financial_impact", "gte", 1.0), "roles": ["cfo"],
                 "message_en": "Financial impact ≥ EGP 1M requires CFO approval.",
                 "message_ar": "الأثر المالي ≥ مليون جنيه يتطلب موافقة المدير المالي."},
    },
    {
        "code": "GOV-005", "effect": "require_approval",
        "name_en": "CEO approval above EGP 5M impact", "name_ar": "موافقة الرئيس التنفيذي فوق 5 ملايين",
        "description_en": "Actions with financial impact of EGP 5M or more require CEO approval.",
        "description_ar": "الإجراءات ذات الأثر المالي 5 ملايين جنيه فأكثر تتطلب موافقة الرئيس التنفيذي.",
        "rule": {"when": _c("action.financial_impact", "gte", 5.0), "roles": ["ceo"],
                 "message_en": "Financial impact ≥ EGP 5M requires CEO approval.",
                 "message_ar": "الأثر المالي ≥ 5 ملايين جنيه يتطلب موافقة الرئيس التنفيذي."},
    },
    {
        "code": "GOV-006", "effect": "require_approval",
        "name_en": "Legal review of contract changes", "name_ar": "مراجعة قانونية لتعديل العقود",
        "description_en": "Contractor reductions or vendor renegotiations change contracts and require Legal review.",
        "description_ar": "خفض المتعاقدين أو إعادة التفاوض مع الموردين يغير العقود ويتطلب مراجعة قانونية.",
        "rule": {"when": {"any": [_c("action.levers.contractor_reduction", "gt", 0),
                                  _c("action.levers.vendor_renegotiation", "gt", 0)]},
                 "roles": ["legal"],
                 "message_en": "Contract changes require General Counsel review.",
                 "message_ar": "تعديل العقود يتطلب مراجعة المستشار القانوني."},
    },
    {
        "code": "GOV-007", "effect": "require_approval",
        "name_en": "HR review of workforce impact", "name_ar": "مراجعة الموارد البشرية لأثر القوى العاملة",
        "description_en": "Changes to workload, reallocation or retraining require HR review.",
        "description_ar": "تغيير عبء العمل أو إعادة التوزيع أو التأهيل يتطلب مراجعة الموارد البشرية.",
        "rule": {"when": {"any": [_c("action.levers.operating_model_redesign", "gt", 0),
                                  _c("analysis.peak_utilization_pct", "gt", 85)]},
                 "roles": ["hr"],
                 "message_en": "Workforce impact requires HR Director review.",
                 "message_ar": "أثر القوى العاملة يتطلب مراجعة مدير الموارد البشرية."},
    },
    {
        "code": "GOV-008", "effect": "require_approval",
        "name_en": "COO sign-off on delivery impact", "name_ar": "موافقة مدير العمليات على أثر التسليم",
        "description_en": "Any modelled increase in project delay requires COO sign-off.",
        "description_ar": "أي زيادة متوقعة في تأخير المشروعات تتطلب موافقة مدير العمليات.",
        "rule": {"when": _c("analysis.max_delay_increase_pct", "gt", 0.5), "roles": ["coo"],
                 "message_en": "Modelled delivery delay requires COO sign-off.",
                 "message_ar": "التأخير المتوقع في التسليم يتطلب موافقة مدير العمليات."},
    },
    {
        "code": "GOV-009", "effect": "deny", "locked": False,
        "name_en": "Unresolved critical collisions block approval", "name_ar": "التعارضات الحرجة غير المحلولة تمنع الاعتماد",
        "description_en": "A strategy with an unresolved critical Decision Collision cannot be approved; "
                          "request further analysis or revise the strategy.",
        "description_ar": "لا يمكن اعتماد استراتيجية بها تعارض حرج غير محلول؛ اطلب تحليلاً إضافياً أو عدّل الاستراتيجية.",
        "rule": {"when": _c("analysis.critical_collisions", "gt", 0),
                 "message_en": "Blocked: unresolved critical decision collision.",
                 "message_ar": "مرفوض: يوجد تعارض حرج غير محلول في القرار."},
    },
    {
        "code": "GOV-010", "effect": "require_approval",
        "name_en": "Executive acceptance of constraint risk", "name_ar": "قبول تنفيذي لمخاطر القيود",
        "description_en": "If a hard constraint fails at the selected risk tolerance, CEO and COO must "
                          "explicitly accept the risk.",
        "description_ar": "إذا لم يتحقق قيد إلزامي عند مستوى تحمل المخاطر المختار، يجب أن يقبل الرئيس التنفيذي "
                          "ومدير العمليات المخاطرة صراحة.",
        "rule": {"when": _c("analysis.hard_constraints_violated", "len_gt", 0), "roles": ["ceo", "coo"],
                 "message_en": "Hard constraint at risk: explicit executive risk acceptance required.",
                 "message_ar": "قيد إلزامي معرض للخطر: يلزم قبول تنفيذي صريح للمخاطرة."},
    },
    {
        "code": "GOV-011", "effect": "require_acknowledgement",
        "name_en": "Acknowledge data quality errors", "name_ar": "الإقرار بأخطاء جودة البيانات",
        "description_en": "Approvers must acknowledge open data-quality errors in the dataset.",
        "description_ar": "يجب على المعتمدين الإقرار بأخطاء جودة البيانات المفتوحة.",
        "rule": {"when": _c("dataset.has_errors", "truthy"),
                 "message_en": "Dataset contains unresolved consistency errors.",
                 "message_ar": "البيانات تحتوي على أخطاء اتساق غير محلولة."},
    },
    {
        "code": "GOV-012", "effect": "deny",
        "name_en": "Implementation spend hard cap", "name_ar": "الحد الأقصى لإنفاق التنفيذ",
        "description_en": "Strategies whose P90 one-off implementation cost exceeds EGP 20M are denied.",
        "description_ar": "تُرفض الاستراتيجيات التي تتجاوز تكلفة تنفيذها (P90) 20 مليون جنيه.",
        "rule": {"when": _c("analysis.implementation_cost_p90", "gt", 20.0),
                 "message_en": "Blocked: implementation cost exceeds the EGP 20M hard cap.",
                 "message_ar": "مرفوض: تكلفة التنفيذ تتجاوز الحد الأقصى البالغ 20 مليون جنيه."},
    },
    {
        "code": "GOV-013", "effect": "deny", "locked": True,
        "name_en": "Separation of duties", "name_ar": "الفصل بين المهام",
        "description_en": "The requester of an approval cannot approve it; one approver cannot satisfy two roles.",
        "description_ar": "لا يجوز لمقدم طلب الاعتماد اعتماده؛ ولا يجوز لمعتمد واحد استيفاء دورين.",
        "rule": {"kind": "procedural"},
    },
    {
        "code": "GOV-014", "effect": "deny", "locked": True,
        "name_en": "Consequential automation requires authorisation",
        "name_ar": "الأتمتة ذات الأثر تتطلب تفويضاً",
        "description_en": "Consequential automation workflows run in dry-run mode unless live execution is "
                          "enabled by an administrator AND the related decision is approved.",
        "description_ar": "تعمل مسارات الأتمتة ذات الأثر في وضع المحاكاة ما لم يفعّل المسؤول التنفيذ الفعلي "
                          "ويُعتمد القرار المرتبط.",
        "rule": {"when": {"all": [_c("action.type", "eq", "automation.run"), _c("action.consequential", "truthy"),
                                  _c("action.dry_run", "falsy"),
                                  {"any": [_c("platform.external_actions_enabled", "falsy"),
                                           _c("decision.status", "ne", "approved")]}]},
                 "message_en": "Blocked: consequential automation cannot run live without authorisation.",
                 "message_ar": "مرفوض: لا يمكن تشغيل الأتمتة ذات الأثر فعلياً دون تفويض."},
    },
    {
        "code": "GOV-015", "effect": "require_approval",
        "name_en": "Customer data shared with a third party", "name_ar": "مشاركة بيانات العملاء مع طرف ثالث",
        "description_en": "Placing receivables with a collection agency shares customer personal data. A data-processing "
                          "agreement under the Personal Data Protection Law (Law 151 of 2020) and General Counsel "
                          "approval are required.",
        "description_ar": "تسليم المديونيات لشركة تحصيل يعني مشاركة بيانات العملاء الشخصية، ويتطلب اتفاقية معالجة بيانات "
                          "وفق قانون حماية البيانات الشخصية (القانون 151 لسنة 2020) وموافقة المستشار القانوني.",
        "rule": {"when": _c("action.levers.agency_placement", "gt", 0), "roles": ["legal"],
                 "message_en": "Sharing customer data with a collection agency requires a data-processing agreement and Legal approval.",
                 "message_ar": "مشاركة بيانات العملاء مع شركة تحصيل تتطلب اتفاقية معالجة بيانات وموافقة الشؤون القانونية."},
    },
    {
        "code": "GOV-016", "effect": "deny", "locked": False,
        "name_en": "Fair collection conduct", "name_ar": "التحصيل العادل",
        "description_en": "High-frequency contact, pressure tactics and early legal escalation against customers are "
                          "prohibited; legal action on a debt is decided case by case by Legal.",
        "description_ar": "يُحظر التواصل المكثف وأساليب الضغط والتصعيد القانوني المبكر مع العملاء؛ وأي إجراء قانوني على "
                          "مديونية تقرره الشؤون القانونية لكل حالة على حدة.",
        "rule": {"when": _c("action.levers.aggressive_tactics", "gt", 0),
                 "message_en": "Blocked: aggressive collection practices violate the fair-collection policy.",
                 "message_ar": "مرفوض: أساليب التحصيل الحادة تخالف سياسة التحصيل العادل."},
    },
    {
        "code": "GOV-017", "effect": "require_approval",
        "name_en": "Long-term use of a state-owned asset", "name_ar": "الانتفاع طويل الأجل بأصل مملوك للدولة",
        "description_en": "Leasing or granting usufruct of a state-owned asset for more than 3 years requires a public tender "
                          "under the Public Contracts Law (Law 182 of 2018), an independent valuation, Legal review, a staff "
                          "transfer plan reviewed by HR and approval by the CEO.",
        "description_ar": "تأجير أصل مملوك للدولة أو منح حق انتفاع به لأكثر من 3 سنوات يتطلب مناقصة عامة وفق قانون التعاقدات "
                          "العامة (القانون 182 لسنة 2018) وتقييماً مستقلاً ومراجعة قانونية وخطة لنقل العاملين تراجعها الموارد "
                          "البشرية وموافقة الرئيس التنفيذي.",
        "rule": {"when": _c("action.levers.lease_to_operator", "gt", 0), "roles": ["legal", "hr", "ceo"],
                 "message_en": "A long-term lease of a state-owned asset requires a public tender, Legal, HR and CEO approval.",
                 "message_ar": "التأجير طويل الأجل لأصل مملوك للدولة يتطلب مناقصة عامة وموافقة القانونية والموارد البشرية والرئيس التنفيذي."},
    },
    {
        "code": "GOV-018", "effect": "require_approval",
        "name_en": "Capital investment in a state-owned asset", "name_ar": "الاستثمار الرأسمالي في أصل مملوك للدولة",
        "description_en": "Capital investment above EGP 50M (P90) in a state-owned asset requires an independent feasibility "
                          "study and CFO and CEO approval.",
        "description_ar": "الاستثمار الرأسمالي فوق 50 مليون جنيه (P90) في أصل مملوك للدولة يتطلب دراسة جدوى مستقلة وموافقة "
                          "المدير المالي والرئيس التنفيذي.",
        "rule": {"when": _c("analysis.capital_investment_p90", "gt", 50.0), "roles": ["cfo", "ceo"],
                 "message_en": "Capital investment above EGP 50M requires a feasibility study and CFO and CEO approval.",
                 "message_ar": "الاستثمار فوق 50 مليون جنيه يتطلب دراسة جدوى وموافقة المدير المالي والرئيس التنفيذي."},
    },
]
