"""Entitlement Discovery Engine (deterministic, explainable).

Correlates CONTRACT CLAUSES + PROJECT EVENT + LINKED EVIDENCE + FINANCIAL DATA + DEADLINES and produces
*potential* entitlements. It never concludes that a claim is valid: the strongest status it can assign is
``potential``. ``substantiated`` and ``rejected`` are set only by a human reviewer.

Every statement in the explanation carries a citation to a clause (document + page) or a linked document,
or is explicitly listed as an assumption.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ..core.text import excerpt, norm
from .bm25 import BM25
from .deadlines import Calendar, compute
from .embeddings import cosine, embed
from .taxonomy import (
    CLAUSE_CATEGORIES,
    ENTITLEMENT_TYPES,
    EVENT_CATEGORIES,
    EVENT_RULES,
    EVIDENCE_RULES,
)

ENGINE_VERSION = "entitlement-1.3"
CLAUSE_MIN_SCORE = 0.45
_TIMEBAR_COND = re.compile(r"fails to give notice|failure to give notice|not given within|time[- ]barred|discharged from "
                           r"(all )?liability|لم يخطر|عدم الاخطار|يسقط حق")
TYPE_ENT_KEYWORDS = {
    "extension_of_time": ["extension", "time for completion", "مد مده", "تمديد", "مد المده"],
    "prolongation_cost": ["cost", "payment", "تكاليف", "تعويض"],
    "variation_payment": ["variation", "valued", "additional", "اضافي", "تقييم"],
    "additional_cost": ["cost", "payment", "تكاليف", "تعويض"],
    "suspension_cost": ["cost", "تكاليف"],
}
_WRITTEN_COND = re.compile(r"without (a |an )?(prior )?written|unless .{0,40}in writing|الا بناء علي امر .{0,15}كتابي|دون امر .{0,10}كتابي")

TYPE_CORE_CATEGORIES: dict[str, list[str]] = {
    "variation_payment": ["variations", "valuation", "instructions_design"],
    "extension_of_time": ["delay_eot", "site_access", "employer_obligations"],
    "prolongation_cost": ["delay_eot", "site_access", "claims_notices"],
    "additional_cost": ["unforeseen_conditions", "claims_notices"],
    "late_payment_financing": ["payment"],
    "price_adjustment": ["price_adjustment"],
    "disruption_cost": ["claims_notices", "delay_eot", "employer_obligations"],
    "suspension_cost": ["suspension"],
    "retention_release": ["retention"],
}


@dataclass
class EventIn:
    id: str
    ref: str
    title: str
    description: str
    category: str
    event_date: date
    awareness_date: date | None = None
    est_cost_impact: Decimal | None = None
    est_time_impact_days: int | None = None
    responsible_party: str | None = None
    category_source: str = "user"
    suggested_category_confidence: float | None = None
    currency: str = "EGP"


@dataclass
class ClauseIn:
    id: str
    number: str
    title: str
    text: str
    category: str
    secondary_categories: list[str]
    time_limits: list[dict]
    exclusions: list[str]
    conditions: list[str]
    entitlements: list[str]
    document_id: str
    document_title: str
    page_start: int
    page_end: int
    verification_status: str = "unverified"
    embedding: list[float] | None = None


@dataclass
class DocIn:
    id: str
    title: str
    doc_type: str
    doc_date: date | None
    author_party: str | None
    pages: list[tuple[int, str]]


@dataclass
class ValuationIn:
    total: Decimal
    status: str  # draft|verified
    currency: str


@dataclass
class Finding:
    entitlement_type: str
    title: str
    status: str
    primary_clause_id: str | None
    related_clause_ids: list[str]
    clause_scores: list[dict]
    conditions: list[dict]
    evidence_available: list[dict]
    evidence_missing: list[dict]
    evidence_completeness: float
    financial_impact: Decimal | None
    financial_basis: str
    time_impact_days: int | None
    notice: dict
    detailed_claim: dict | None
    exclusions: list[dict]
    risk_level: str
    risk_factors: list[dict]
    confidence: float
    confidence_breakdown: dict
    explanation: list[dict]
    facts: list[dict]
    assumptions: list[dict]
    recommended_actions: list[dict]
    contradictions: list[dict] = field(default_factory=list)


def _cite_clause(c: ClauseIn, quote: str | None = None) -> dict:
    return {"type": "clause", "clause_id": c.id, "clause_number": c.number, "clause_title": c.title,
            "document_id": c.document_id, "document_title": c.document_title, "page": c.page_start,
            "page_end": c.page_end, "quote": (quote or c.text[:400]).strip(),
            "verification_status": c.verification_status}


def _best_page(doc: DocIn, query: str) -> tuple[int, str]:
    if not doc.pages:
        return 1, ""
    if len(doc.pages) == 1:
        p, t = doc.pages[0]
        return p, t
    scores = BM25([t for _, t in doc.pages]).score(query)
    i = max(range(len(scores)), key=scores.__getitem__)
    return doc.pages[i]


def _cite_doc(doc: DocIn, query: str) -> dict:
    page, text = _best_page(doc, query)
    q = [t for t in norm(query).split() if len(t) > 3]
    pos = -1
    nt = norm(text)
    for t in q:
        pos = nt.find(t)
        if pos >= 0:
            break
    quote = excerpt(text, max(pos, 0), max(pos, 0) + 1, 180) if text else ""
    return {"type": "document", "document_id": doc.id, "document_title": doc.title, "doc_type": doc.doc_type,
            "doc_date": doc.doc_date.isoformat() if doc.doc_date else None, "page": page, "quote": quote.strip()}


# ------------------------------------------------------------------ clause ranking


def rank_clauses(event: EventIn, clauses: list[ClauseIn]) -> list[dict]:
    if not clauses:
        return []
    rules = EVENT_RULES.get(event.category, EVENT_RULES["other"])["clauses"]
    query = f"{event.title}. {event.description}"
    bm = BM25([f"{c.title} {c.text}" for c in clauses]).score(query)
    top = max(bm) or 1.0
    qv = embed(query)
    ranked = []
    for c, b in zip(clauses, bm, strict=True):
        cat = rules.get(c.category, 0.0)
        for sc in c.secondary_categories:
            cat = max(cat, 0.7 * rules.get(sc, 0.0))
        lex = b / top
        sem = max(0.0, cosine(qv, c.embedding or embed(c.title + " " + c.text)))
        score = 0.55 * cat + 0.30 * lex + 0.15 * sem
        ranked.append({"clause": c, "score": round(score, 3),
                       "breakdown": {"category_fit": round(cat, 3), "lexical": round(lex, 3),
                                     "semantic": round(sem, 3)}})
    ranked.sort(key=lambda r: -r["score"])
    return ranked


# ------------------------------------------------------------------ evidence


def assess_evidence(etype: str, event: EventIn, docs: list[DocIn], clauses: list[ClauseIn]) -> tuple[list, list, float]:
    query = f"{event.title} {event.description}"
    available, missing = [], []
    reqs = EVIDENCE_RULES.get(etype, [])
    weight_total = weight_ok = 0.0
    for r in reqs:
        w = 2.0 if r["critical"] else 1.0
        weight_total += w
        matches = []
        if r["code"] == "adjustment_mechanism":
            matches = [_cite_clause(c) for c in clauses if c.category == "price_adjustment"][:2]
        else:
            for d in docs:
                if d.doc_type not in r["docs"]:
                    continue
                if r["code"] == "contractor_notice" and d.author_party not in (None, "contractor"):
                    continue
                if r["code"] == "written_instruction" and d.author_party == "contractor" and d.doc_type in ("letter", "email"):
                    continue
                matches.append(_cite_doc(d, query))
        item = {"code": r["code"], "en": r["en"], "ar": r["ar"], "critical": r["critical"]}
        if matches:
            weight_ok += w
            available.append({**item, "sources": matches})
        else:
            missing.append(item)
    completeness = round(weight_ok / weight_total, 2) if weight_total else 0.0
    return available, missing, completeness


def find_contradictions(event: EventIn, docs: list[DocIn]) -> list[dict]:
    out = []
    pat = re.compile(r"(reject|not approved|deny|denied|not instructed|no instruction|is not entitled|"
                     r"رفض|غير معتمد|لم يتم التكليف|لا يحق|غير مستحق)")
    for d in docs:
        if d.author_party == "contractor":
            continue
        for page, text in d.pages:
            m = pat.search(norm(text))
            if m:
                out.append({"en": f"'{d.title}' (p.{page}) contains wording that may dispute the entitlement.",
                            "ar": f"المستند '{d.title}' (ص {page}) يتضمن عبارات قد تنازع في الاستحقاق.",
                            "citation": {"type": "document", "document_id": d.id, "document_title": d.title,
                                         "page": page, "quote": excerpt(text, m.start(), m.end(), 160)}})
                break
    if re.search(r"\b(verbal|oral|orally|phone)\b|شفهي|شفاهه|تليفوني", norm(event.description)):
        out.append({"en": "The event description indicates the instruction may have been oral; written confirmation "
                          "is usually required to support a variation.",
                    "ar": "يشير وصف الحدث إلى أن التعليمات قد تكون شفهية؛ وعادة ما يلزم تأكيد كتابي لدعم المطالبة.",
                    "citation": None})
    return out


# ------------------------------------------------------------------ notice


def _notice_requirement(primary: ClauseIn | None, related: list[ClauseIn], kind: str) -> tuple[dict | None, ClauseIn | None, list[int]]:
    """Find the applicable time limit of `kind` — primary clause first, then claims/notice clauses."""
    candidates: list[tuple[dict, ClauseIn]] = []
    pool = ([primary] if primary else []) + [c for c in related if c is not primary]
    for c in pool:
        for t in c.time_limits:
            if t["kind"] == kind:
                candidates.append((t, c))
    if not candidates:
        return None, None, []
    alt = sorted({t["days"] for t, _ in candidates})
    t, c = candidates[0]
    return t, c, alt


def evaluate_notice(event: EventIn, primary: ClauseIn | None, related: list[ClauseIn], docs: list[DocIn],
                    cal: Calendar, today: date, kind: str = "notice") -> dict:
    req, clause, alternatives = _notice_requirement(primary, related, kind)
    trigger = event.awareness_date or event.event_date
    if req is None:
        return {"kind": kind, "required": None, "status": "not_identified", "certainty": "undetermined",
                "notes": [{"code": "no_notice_clause",
                           "en": "No explicit time limit for this step was found in the analysed contract documents. "
                                 "This does not mean none applies — verify manually.",
                           "ar": "لم يُعثر على مهلة صريحة لهذه الخطوة في مستندات العقد المحللة، وهذا لا يعني عدم "
                                 "وجودها — يجب التحقق يدويًا."}]}
    res = compute(trigger, event.awareness_date is not None, req["days"], req["day_type"], cal,
                  alternatives=alternatives if len(alternatives) > 1 else None, trigger_wording=req.get("trigger"))
    given = None
    for d in docs:
        if d.doc_type == "notice" and d.author_party in (None, "contractor") and d.doc_date and d.doc_date >= event.event_date:
            if given is None or d.doc_date < given.doc_date:
                given = d
    status = "due"
    if given and res.due_date:
        status = "given_on_time" if given.doc_date <= res.due_date else "given_late"
    elif given:
        status = "given"
    elif res.due_date and res.due_date < today:
        status = "overdue"
    days_left = (res.due_date - today).days if res.due_date else None
    return {
        "kind": kind, "required": True, "status": status, "days_remaining": days_left,
        "period_days": req["days"], "stated": req["stated"], "day_type": req["day_type"], "time_bar": req["time_bar"],
        "trigger_wording": req.get("trigger"), "trigger_date": trigger.isoformat(),
        "due_date": res.due_date.isoformat() if res.due_date else None, "certainty": res.certainty,
        "notes": res.notes, "calculation": res.calculation, "alternatives": alternatives,
        "clause": _cite_clause(clause, req["sentence"]) if clause else None,
        "notice_document": {"document_id": given.id, "document_title": given.title,
                            "doc_date": given.doc_date.isoformat()} if given else None,
    }


# ------------------------------------------------------------------ main


def _label(table: dict, key: str, lang: str) -> str:
    return table.get(key, {}).get(lang, key)


def discover(event: EventIn, clauses: list[ClauseIn], docs: list[DocIn], *, valuations: dict[str, ValuationIn],
             cal: Calendar, today: date) -> list[Finding]:
    rules = EVENT_RULES.get(event.category, EVENT_RULES["other"])
    ranked = rank_clauses(event, clauses)
    claims_clauses = [c for c in clauses if c.category == "claims_notices"]
    findings = []
    contradictions = find_contradictions(event, docs)
    for etype in rules["types"]:
        core = TYPE_CORE_CATEGORIES.get(etype, [])
        ent_kw = TYPE_ENT_KEYWORDS.get(etype, [])
        rule_cats = {k for k, w in rules["clauses"].items() if w >= 0.9}
        candidates = [r for r in ranked if r["clause"].category in core
                      or any(s in core for s in r["clause"].secondary_categories)
                      or (r["clause"].category in rule_cats and r["clause"].entitlements
                          and any(k in norm(" ".join(r["clause"].entitlements)) for k in ent_kw))]
        # selection score for the *primary* clause: favour clauses that state an entitlement
        for r in candidates:
            sel = r["score"] + (0.12 if r["clause"].entitlements else 0.0) - (0.05 if r["clause"].exclusions else 0.0)
            r["selection"] = round(min(1.0, sel), 3)
        candidates.sort(key=lambda r: -r["selection"])
        # The primary clause is the one that CONFERS the right; procedural/limiting clauses become related clauses.
        conferring = [r for r in candidates if r["clause"].entitlements and r["score"] >= CLAUSE_MIN_SCORE * 0.8]
        pool = conferring or candidates
        primary_r = pool[0] if pool and pool[0]["selection"] >= CLAUSE_MIN_SCORE else None
        primary = primary_r["clause"] if primary_r else None
        related = [r["clause"] for r in ranked[:6] if r["score"] >= CLAUSE_MIN_SCORE * 0.8 and r["clause"] is not primary]
        for c in claims_clauses:
            if c not in related and c is not primary:
                related.append(c)

        available, missing, completeness = assess_evidence(etype, event, docs, clauses)
        notice = evaluate_notice(event, primary, related, docs, cal, today, "notice")
        detailed = evaluate_notice(event, primary, related, docs, cal, today, "detailed_claim")
        if detailed["status"] == "not_identified":
            detailed = None

        tinfo = ENTITLEMENT_TYPES[etype]
        val = valuations.get(etype)
        if not tinfo["financial"]:
            fin, basis = None, "not_applicable"
        elif val:
            fin, basis = val.total, "valuation_verified" if val.status == "verified" else "valuation_draft"
        elif event.est_cost_impact is not None:
            fin, basis = Decimal(event.est_cost_impact), "event_estimate"
        else:
            fin, basis = None, "not_quantified"
        time_days = event.est_time_impact_days if tinfo["time"] else None

        # ---- explanation with citations
        explanation: list[dict] = [{
            "kind": "event",
            "en": f"Event {event.ref} ({_label(EVENT_CATEGORIES, event.category, 'en')}) on {event.event_date.isoformat()}: {event.title}.",
            "ar": f"الحدث {event.ref} ({_label(EVENT_CATEGORIES, event.category, 'ar')}) بتاريخ {event.event_date.isoformat()}: {event.title}.",
            "citation": None}]
        facts: list[dict] = [{"en": f"Recorded event: {event.title} ({event.event_date.isoformat()}).",
                              "ar": f"حدث مسجل: {event.title} ({event.event_date.isoformat()}).", "source": "event_register"}]
        assumptions: list[dict] = []
        exclusions: list[dict] = []
        conditions: list[dict] = []
        if primary:
            quote = primary.entitlements[0] if primary.entitlements else primary.text[:400]
            explanation.append({
                "kind": "clause",
                "en": f"Clause {primary.number} '{primary.title}' ({_label(CLAUSE_CATEGORIES, primary.category, 'en')}) "
                      f"matches this event type" + (" and contains entitlement wording." if primary.entitlements
                                                    else ", but does not state an entitlement explicitly."),
                "ar": f"البند {primary.number} '{primary.title}' ({_label(CLAUSE_CATEGORIES, primary.category, 'ar')}) "
                      f"يتوافق مع نوع الحدث" + ("، ويتضمن نصًا على الاستحقاق." if primary.entitlements
                                               else "، لكنه لا ينص صراحة على استحقاق."),
                "citation": _cite_clause(primary, quote)})
            facts.append({"en": f"Clause {primary.number} text (quoted).", "ar": f"نص البند {primary.number} (مقتبس).",
                          "source": "clause", "citation": _cite_clause(primary, quote)})
            for cond in primary.conditions[:3]:
                conditions.append({"text": cond, "citation": _cite_clause(primary, cond)})
            avail_codes = {a["code"] for a in available}
            for ex_clause in [primary, *[c for c in related if c.category == primary.category][:2]]:
                for ex in ex_clause.exclusions[:3]:
                    item = {"text": ex, "clause_number": ex_clause.number, "citation": _cite_clause(ex_clause, ex),
                            "blocking": True}
                    if _TIMEBAR_COND.search(norm(ex)):
                        item["blocking"] = False
                        item["kind"] = "time_bar"
                        item["note"] = {"en": "Time-bar provision: it bites if notice is not given in time — see the notice "
                                              "requirement and deadline below.",
                                        "ar": "نص سقوط حق: يسري إذا لم يُقدم الإخطار في موعده — راجع متطلب الإخطار والموعد أدناه."}
                    elif _WRITTEN_COND.search(norm(ex)) and "written_instruction" in avail_codes:
                        item["blocking"] = False
                        item["satisfied_by"] = "written_instruction"
                        item["note"] = {"en": "This limitation applies to work done WITHOUT a written instruction; a written "
                                              "instruction is on file. Confirm it was issued by an authorised person.",
                                        "ar": "ينطبق هذا القيد على الأعمال المنفذة دون تعليمات مكتوبة؛ وتوجد تعليمات مكتوبة "
                                              "بالملف. يجب التأكد من صدورها من شخص مفوض."}
                    exclusions.append(item)
            if primary.verification_status != "verified":
                assumptions.append({"code": "clause_unverified",
                                    "en": f"Clause {primary.number} was extracted automatically and has not yet been verified by a reviewer.",
                                    "ar": f"تم استخراج البند {primary.number} آليًا ولم يتم التحقق منه بعد من مراجع."})
        else:
            explanation.append({
                "kind": "gap",
                "en": "No clause in the analysed contract documents was found that clearly provides for this type of "
                      "entitlement. Expert review is required before any claim is considered.",
                "ar": "لم يُعثر في مستندات العقد المحللة على بند ينص بوضوح على هذا النوع من الاستحقاق. يلزم مراجعة "
                      "خبير قبل النظر في أي مطالبة.",
                "citation": None})
        for a in available:
            src = a["sources"][0]
            explanation.append({"kind": "evidence",
                                "en": f"Evidence found — {a['en']}: '{src['document_title']}' (p.{src['page']}).",
                                "ar": f"دليل متوفر — {a['ar']}: '{src['document_title']}' (ص {src['page']}).",
                                "citation": src})
            facts.append({"en": f"{a['en']}: {src['document_title']}.", "ar": f"{a['ar']}: {src['document_title']}.",
                          "source": "document", "citation": src})
        for x in exclusions:
            if x["blocking"]:
                explanation.append({"kind": "exclusion",
                                    "en": f"Clause {x['clause_number']} contains a limitation that may exclude or restrict this entitlement — legal review required.",
                                    "ar": f"البند {x['clause_number']} يتضمن قيدًا قد يستبعد هذا الاستحقاق أو يحد منه — يلزم مراجعة قانونية.",
                                    "citation": x["citation"]})
            else:
                explanation.append({"kind": "exclusion", "en": f"Clause {x['clause_number']}: {x['note']['en']}",
                                    "ar": f"البند {x['clause_number']}: {x['note']['ar']}", "citation": x["citation"]})
        for m in missing:
            explanation.append({"kind": "gap", "en": f"Missing {'critical ' if m['critical'] else ''}evidence — {m['en']}.",
                                "ar": f"دليل {'جوهري ' if m['critical'] else ''}ناقص — {m['ar']}.", "citation": None})
        if notice.get("required"):
            explanation.append({
                "kind": "deadline",
                "en": f"Notice requirement: {notice['stated']} ({notice['day_type']}) from {notice.get('trigger_wording') or 'the triggering event'}"
                      f"; computed due date {notice['due_date']} ({notice['certainty']}).",
                "ar": f"متطلب الإخطار: {notice['stated']} ({notice['day_type']}) من {notice.get('trigger_wording') or 'تاريخ الحدث'}"
                      f"؛ تاريخ الاستحقاق المحسوب {notice['due_date']} ({notice['certainty']}).",
                "citation": notice["clause"]})
            assumptions.extend(notice["notes"])
        else:
            assumptions.extend(notice["notes"])
        if basis == "event_estimate":
            assumptions.append({"code": "cost_estimate_unverified",
                                "en": "Financial impact is the estimate entered on the event; it is not yet supported by a valuation worksheet.",
                                "ar": "الأثر المالي هو التقدير المدخل على الحدث، ولم يُدعم بعد بورقة تقييم."})
        if etype in ("extension_of_time", "prolongation_cost"):
            assumptions.append({"code": "no_eot_conclusion",
                                "en": "HAQQ does not conclude that an extension of time is due: entitlement depends on the "
                                      "contract conditions, causation and a delay analysis of the critical path.",
                                "ar": "لا يقرر حقّك استحقاق مد المدة: فذلك يتوقف على شروط العقد وعلاقة السببية وتحليل "
                                      "التأخير على المسار الحرج."})

        # ---- risk
        risk_factors: list[dict] = []
        if notice.get("status") == "overdue":
            risk_factors.append({"code": "notice_overdue", "severity": "high",
                                 "en": f"Notice deadline {notice['due_date']} has passed with no contractor notice on record"
                                       + (" — the clause contains time-bar language." if notice.get("time_bar") else "."),
                                 "ar": f"انقضى موعد الإخطار {notice['due_date']} دون وجود إخطار من المقاول"
                                       + (" — ويتضمن البند نص سقوط حق." if notice.get("time_bar") else ".")})
        elif notice.get("status") == "given_late":
            risk_factors.append({"code": "notice_late", "severity": "high", "en": "Notice appears to have been given after the deadline.",
                                 "ar": "يبدو أن الإخطار قُدم بعد الموعد المحدد."})
        elif notice.get("status") == "due" and notice.get("days_remaining") is not None and notice["days_remaining"] <= 7:
            risk_factors.append({"code": "notice_imminent", "severity": "high",
                                 "en": f"Notice due in {notice['days_remaining']} day(s).",
                                 "ar": f"الإخطار مستحق خلال {notice['days_remaining']} يوم."})
        blocking_ex = [x for x in exclusions if x["blocking"]]
        if blocking_ex:
            risk_factors.append({"code": "exclusion", "severity": "medium",
                                 "en": "The applicable clause contains an exclusion or limitation.",
                                 "ar": "البند المنطبق يتضمن استثناءً أو قيدًا."})
        crit_missing = [m for m in missing if m["critical"]]
        if crit_missing:
            risk_factors.append({"code": "critical_evidence_missing", "severity": "medium",
                                 "en": f"{len(crit_missing)} critical evidence item(s) missing.",
                                 "ar": f"عدد {len(crit_missing)} من الأدلة الجوهرية ناقصة."})
        if contradictions:
            risk_factors.append({"code": "contradiction", "severity": "medium",
                                 "en": "Potentially contradictory evidence was found.", "ar": "توجد أدلة قد تكون متعارضة."})
        if notice.get("certainty") == "ambiguous":
            risk_factors.append({"code": "ambiguous_deadline", "severity": "medium",
                                 "en": "Conflicting notice periods in the contract.", "ar": "مدد إخطار متعارضة في العقد."})
        sev = [r["severity"] for r in risk_factors]
        risk_level = "high" if "high" in sev else ("medium" if sev else "low")

        # ---- status (never above 'potential')
        if primary is None:
            status = "requires_expert_verification"
        elif blocking_ex or notice.get("status") in ("overdue", "given_late") and notice.get("time_bar"):
            status = "requires_expert_verification"
        elif crit_missing:
            status = "insufficient_evidence"
        else:
            status = "potential"

        # ---- confidence
        clause_c = primary_r["score"] if primary_r else 0.0
        class_c = 1.0 if event.category_source == "user" else (event.suggested_category_confidence or 0.5)
        notice_c = {"determined": 1.0, "estimated": 0.6, "ambiguous": 0.35, "undetermined": 0.2}.get(notice.get("certainty"), 0.2)
        quant_c = {"valuation_verified": 1.0, "valuation_draft": 0.7, "event_estimate": 0.4,
                   "not_quantified": 0.0, "not_applicable": 0.7}[basis]
        breakdown = {"clause_match": round(clause_c, 2), "evidence_completeness": completeness,
                     "event_classification": round(class_c, 2), "notice_clarity": notice_c, "quantification": quant_c}
        conf = 0.35 * clause_c + 0.30 * completeness + 0.15 * class_c + 0.10 * notice_c + 0.10 * quant_c
        if blocking_ex:
            conf -= 0.15
            breakdown["exclusion_penalty"] = -0.15
        if contradictions:
            conf -= 0.10
            breakdown["contradiction_penalty"] = -0.10
        conf = round(max(0.05, min(conf, 0.95)), 2)

        # ---- recommended actions
        actions: list[dict] = []
        if notice.get("status") in ("due",) and notice.get("due_date"):
            actions.append({"priority": 1, "en": f"Issue a written notice under Clause {notice['clause']['clause_number']} before {notice['due_date']}.",
                            "ar": f"إصدار إخطار كتابي وفقًا للبند {notice['clause']['clause_number']} قبل {notice['due_date']}."})
        if notice.get("status") == "overdue":
            actions.append({"priority": 1, "en": "Notice period appears to have expired — obtain urgent legal advice on time-bar and any waiver/estoppel arguments; issue notice immediately.",
                            "ar": "يبدو أن مهلة الإخطار انقضت — يلزم رأي قانوني عاجل بشأن سقوط الحق، وإصدار الإخطار فورًا."})
        if notice.get("status") == "not_identified":
            actions.append({"priority": 2, "en": "Confirm with the contracts team whether any notice requirement applies.",
                            "ar": "التأكد مع فريق العقود من وجود متطلبات إخطار منطبقة."})
        for m in crit_missing:
            actions.append({"priority": 2, "en": f"Obtain: {m['en']}.", "ar": f"استيفاء: {m['ar']}."})
        if tinfo["financial"] and basis in ("not_quantified", "event_estimate"):
            actions.append({"priority": 3, "en": "Prepare the valuation worksheet using BOQ rates and cost records.",
                            "ar": "إعداد ورقة التقييم باستخدام فئات جدول الكميات وسجلات التكلفة."})
        if etype in ("extension_of_time", "prolongation_cost"):
            actions.append({"priority": 3, "en": "Commission a critical-path delay analysis against the approved programme.",
                            "ar": "إعداد تحليل تأخير على المسار الحرج مقابل البرنامج الزمني المعتمد."})
        if primary is None or blocking_ex:
            actions.append({"priority": 2, "en": "Refer to the legal reviewer for contractual verification.",
                            "ar": "إحالة الحالة إلى المراجع القانوني للتحقق التعاقدي."})
        actions.append({"priority": 4, "en": "Commercial Director to review this finding and decide whether to pursue a claim.",
                        "ar": "مراجعة المدير التجاري لهذه النتيجة واتخاذ قرار بشأن متابعة المطالبة."})

        findings.append(Finding(
            entitlement_type=etype,
            title=f"{tinfo['en']} — {event.title}",
            status=status,
            primary_clause_id=primary.id if primary else None,
            related_clause_ids=[c.id for c in related[:6]],
            clause_scores=[{"clause_id": r["clause"].id, "clause_number": r["clause"].number, "score": r["score"],
                            "breakdown": r["breakdown"]} for r in ranked[:8]],
            conditions=conditions, evidence_available=available, evidence_missing=missing,
            evidence_completeness=completeness, financial_impact=fin, financial_basis=basis,
            time_impact_days=time_days, notice=notice, detailed_claim=detailed, exclusions=exclusions,
            risk_level=risk_level, risk_factors=risk_factors, confidence=conf, confidence_breakdown=breakdown,
            explanation=explanation, facts=facts, assumptions=assumptions,
            recommended_actions=sorted(actions, key=lambda a: a["priority"]), contradictions=contradictions,
        ))
    return findings


def classify_event(text: str) -> tuple[str, float, dict]:
    """Keyword classification of a free-text event description into an event category."""
    t = norm(text)
    scores: dict[str, float] = {}
    for cat, spec in EVENT_CATEGORIES.items():
        s = sum(t.count(norm(k)) for k in spec["kw"])
        if s:
            scores[cat] = s
    if not scores:
        return "other", 0.2, {}
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, v = ranked[0]
    total = sum(scores.values())
    return best, round(min(0.9, 0.3 + 0.6 * v / total), 2), dict(ranked[:4])
