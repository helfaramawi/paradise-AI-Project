"""Deterministic contract intelligence: document classification, clause segmentation, clause
categorisation and extraction of obligations, entitlements, conditions, exclusions and time limits.

Everything returned here is traceable: each extracted item carries the exact source sentence, and each
clause carries its document page range. Nothing is inferred that is not present in the text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from ..core.text import detect_language, norm, sentences
from .extraction import Page
from .taxonomy import (
    CLAUSE_CATEGORIES,
    CONDITION_PATTERNS,
    DETAILED_WORDS,
    DOC_TYPES,
    ENTITLEMENT_PATTERNS,
    EXCLUSION_PATTERNS,
    OBLIGATION_PATTERNS,
    PAYMENT_WORDS,
    RESPONSE_WORDS,
    TIME_BAR_PATTERNS,
)

ENGINE_VERSION = "contract-rules-1.2"


@lru_cache
def _kw(table_id: str) -> dict[str, list[str]]:
    table = DOC_TYPES if table_id == "doc" else CLAUSE_CATEGORIES
    return {k: [norm(w) for w in v["kw"]] for k, v in table.items()}


def _count(text: str, kw: str) -> int:
    if re.match(r"^[a-z]", kw):
        return len(re.findall(r"(?<![a-z])" + re.escape(kw), text))
    return text.count(kw)


# ------------------------------------------------------------------ document classification


def classify_document(text: str, filename: str = "", ext: str = "", meta: dict | None = None) -> tuple[str, float, dict]:
    """Keyword-scored document type. Returns (type, confidence 0..1, scores)."""
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff") and len(text.strip()) < 80:
        return "photo", 0.9, {}
    if ext == ".xlsx":
        t = norm(text[:6000])
        if any(k in t for k in ("qty", "quantity", "الكميه", "rate", "الفئه", "unit")):
            return "boq", 0.85, {}
    head = norm((filename or "") + "\n" + text[:8000])
    scores: dict[str, float] = {}
    for dtype, words in _kw("doc").items():
        hits = sum(min(_count(head, w), 3) for w in words)
        if hits:
            scores[dtype] = hits * DOC_TYPES[dtype]["w"]
    if ext == ".eml":
        scores["email"] = scores.get("email", 0) + 4
    # long, clause-numbered documents are contracts
    if len(text) > 15000 and len(re.findall(r"(?m)^\s*(?:clause|article|sub-clause|الماده|البند)?\s*\d+\.\d+", norm(text))) > 8:
        scores["contract"] = scores.get("contract", 0) + 10
    if not scores:
        return "other", 0.2, {}
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    conf = round(min(0.95, 0.35 + 0.6 * scores[best] / total), 2)
    return best, conf, {k: round(v, 2) for k, v in sorted(scores.items(), key=lambda kv: -kv[1])[:4]}


# ------------------------------------------------------------------ clause segmentation

_AR_ORDINALS = {"الاولي": 1, "الاول": 1, "الثانيه": 2, "الثاني": 2, "الثالثه": 3, "الثالث": 3, "الرابعه": 4,
                "الرابع": 4, "الخامسه": 5, "الخامس": 5, "السادسه": 6, "السادس": 6, "السابعه": 7, "السابع": 7,
                "الثامنه": 8, "الثامن": 8, "التاسعه": 9, "التاسع": 9, "العاشره": 10, "العاشر": 10}

_HEAD_EN = re.compile(
    r"^\s*(?:(?:sub-?clause|clause|article|section)\s+)(?P<num>\d+(?:\.\d+){0,3})\s*[:.\-–—]?\s*(?P<title>.{0,150})$",
    re.I)
_HEAD_NUM = re.compile(r"^\s*(?P<num>\d{1,2}(?:\.\d{1,2}){1,3})\.?\s+(?P<title>[^\d].{1,140})$")
_HEAD_TOP = re.compile(r"^\s*(?P<num>\d{1,2})\.?\s+(?P<title>[A-Z][A-Za-z ,'&/\-]{2,80})$")
_HEAD_AR = re.compile(
    r"^\s*(?:الماده|ماده|البند|بند)\s*(?:رقم\s*)?[(\[]?\s*(?P<num>\d+(?:[.\-/]\d+)*|[؀-ۿ]+)\s*[)\]]?\s*[:\-–—]?\s*(?P<title>.{0,150})$")


@dataclass
class RawClause:
    number: str
    title: str
    parent_title: str | None
    page_start: int
    page_end: int
    lines: list[str] = field(default_factory=list)
    page_is_estimated: bool = False

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()


def _heading(line: str) -> tuple[str, str] | None:
    raw = line.strip()
    if not raw or len(raw) > 170:
        return None
    n = norm(raw)
    m = _HEAD_AR.match(n)
    if m:
        num = m["num"]
        if not num[0].isdigit():
            if num not in _AR_ORDINALS:
                return None
            num = str(_AR_ORDINALS[num])
        # title from the original string (keep proper Arabic letters)
        orig = re.split(r"[:\-–—)\]]", raw, maxsplit=1)
        title = orig[1].strip(" :-–—") if len(orig) > 1 else m["title"].strip()
        return num.replace("-", ".").replace("/", "."), title
    m = _HEAD_EN.match(raw)
    if m:
        title = m["title"].strip(" .:-–—")
        # a cross-reference that wrapped onto a new line ("Sub-Clause 20.1 to an extension…") is not a heading
        if title and not (title[0].isupper() or title[0].isdigit() or detect_language(title) == "ar"):
            return None
        if len(title.split()) > 14:
            return None
        return m["num"], title
    m = _HEAD_NUM.match(raw)
    if m:
        title = m["title"].strip()
        if title.endswith((".", "،")) and len(title.split()) > 7:
            return None
        # Body sentences that start with a number are not headings: headings are short and do not end
        # like a sentence clause in the middle of text.
        if len(title) <= 90 and not title.endswith((",", ";")) and (title[0].isupper() or detect_language(title) == "ar"):
            return m["num"], title.strip(" .:")
        return None
    m = _HEAD_TOP.match(raw)
    if m and len(raw.split()) <= 8:
        return m["num"], m["title"].strip()
    return None


_PARA = re.compile(r"^\s*(?P<num>\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\.?\s+(?P<body>\S.{39,})$")


def segment_clauses(pages: list[Page]) -> list[RawClause]:
    clauses: list[RawClause] = []
    current: RawClause | None = None
    top_titles: dict[str, str] = {}
    for page in pages:
        for line in page.text.splitlines():
            h = _heading(line)
            inline_body = None
            if not h and current is not None:
                pm = _PARA.match(line)
                if pm and pm["num"].split(".")[0] == current.number.split(".")[0] and pm["num"] != current.number:
                    words = pm["body"].split()
                    h = (pm["num"], " ".join(words[:8]) + ("…" if len(words) > 8 else ""))
                    inline_body = pm["body"]
            if h:
                num, title = h
                if current:
                    clauses.append(current)
                top = num.split(".")[0]
                parent = top_titles.get(top) if "." in num else None
                if "." not in num:
                    top_titles[num] = title
                current = RawClause(num, title or f"Clause {num}", parent, page.number, page.number,
                                    page_is_estimated=page.estimated)
                if inline_body:
                    current.lines.append(inline_body)
                continue
            if current is not None:
                current.lines.append(line)
                current.page_end = page.number
    if current:
        clauses.append(current)
    # drop empty headings (pure parents) and merge duplicate numbers from tables of contents
    out: list[RawClause] = []
    seen: dict[str, RawClause] = {}
    for c in clauses:
        if len(c.text) < 25:
            continue
        if c.number in seen and len(c.text) <= len(seen[c.number].text):
            continue
        if c.number in seen:
            out.remove(seen[c.number])
        seen[c.number] = c
        out.append(c)
    return out


# ------------------------------------------------------------------ clause analysis

_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "forty-two": 42, "forty-five": 45,
    "fifty": 50, "fifty-six": 56, "sixty": 60, "seventy": 70, "eighty": 80, "eighty-four": 84, "ninety": 90,
    "twenty-one": 21, "twenty-eight": 28, "twenty eight": 28, "twenty-one ": 21,
    "سبعه": 7, "سبع": 7, "عشره": 10, "عشر": 10, "اربعه عشر": 14, "خمسه عشر": 15, "واحد وعشرين": 21,
    "ثمانيه وعشرين": 28, "ثلاثين": 30, "خمسه واربعين": 45, "اثنين واربعين": 42, "سته وخمسين": 56, "ستين": 60,
    "تسعين": 90, "ثلاثه": 3, "خمسه": 5,
}
_PERIOD = re.compile(
    r"(?P<lead>within|not later than|no later than|not more than|no more than|before the expiry of|a period of|"
    r"after|خلال|في موعد لا يتجاوز|في مده لا تتجاوز|بحد اقصي|في غضون|مده|بعد)\s+"
    r"(?P<span>[^.;:\n]{0,45}?)"
    r"(?P<unit>days?|يوما|يوم|ايام|weeks?|اسابيع|اسبوع)"
    r"(?P<after>[^.;\n]{0,160})")
_DAYTYPE_WORK = re.compile(r"working|business|عمل")
_DAYTYPE_CAL = re.compile(r"calendar|تقويمي|ميلادي")
_TRIGGER = re.compile(
    r"(after|from|of|following|upon)\s+(the\s+)?(date\s+(on\s+)?which\s+|date\s+of\s+|receipt\s+of\s+|issue\s+of\s+)?"
    r"(?P<trig>[^.;\n]{4,140})|(من تاريخ|من وقت|اعتبارا من|من)\s+(?P<trig_ar>[^.;\n]{4,140})")


def _resolve_number(span: str) -> int | None:
    m = re.search(r"\(?\b(\d{1,3})\b\)?", span)
    if m:
        return int(m.group(1))
    s = span.strip()
    for words, val in sorted(_NUM_WORDS.items(), key=lambda kv: -len(kv[0])):
        if words.strip() and words.strip() in s:
            return val
    return None


def _kind(sent: str) -> str:
    if any(re.search(p, sent) for p in DETAILED_WORDS) and re.search(r"claim|مطالب", sent):
        return "detailed_claim"
    if re.search(r"give notice|notify|notice of|notice shall|shall notify|of a claim|اخطار|اشعار|يخطر|ابلاغ", sent):
        return "notice"
    if re.search(r"\bclaim|مطالب", sent) and not any(re.search(p, sent) for p in PAYMENT_WORDS[:3]):
        return "notice"
    if any(re.search(p, sent) for p in PAYMENT_WORDS):
        return "payment"
    if any(re.search(p, sent) for p in RESPONSE_WORDS):
        return "response"
    return "other"


def unwrap(text: str) -> str:
    """Join soft line-wraps (PDF/DOCX layout) so sentences are analysed whole."""
    return re.sub(r"[ \t]*\n[ \t]*", " ", text).strip()


def extract_time_limits(text: str) -> list[dict]:
    """Time periods stated in the text, with the exact sentence, day type and trigger wording."""
    text = unwrap(text)
    out = []
    for _s, _e, sent in sentences(text):
        ns = norm(sent)
        for m in _PERIOD.finditer(ns):
            n = _resolve_number(m["span"])
            if not n or n > 730:
                continue
            unit = m["unit"]
            days = n * 7 if unit.startswith(("week", "اسبوع", "اسابيع")) else n
            ctx = m["span"] + " " + m["unit"] + " " + m["after"][:25]
            day_type = "working" if _DAYTYPE_WORK.search(ctx) else ("calendar" if _DAYTYPE_CAL.search(ctx) else "unspecified")
            trig = _TRIGGER.search(m["after"])
            trigger = None
            if trig:
                trigger = re.split(r"[,،]| and | then |\bو(?:الا|في)\b", (trig.group("trig") or trig.group("trig_ar") or ""))[0].strip()
            out.append({
                "days": days, "stated": f"{n} {unit}", "day_type": day_type, "kind": _kind(ns),
                "trigger": trigger, "time_bar": any(re.search(p, ns) for p in TIME_BAR_PATTERNS),
                "sentence": sent.strip()[:600],
            })
    # the same period restated in a clause (e.g. in its time-bar sentence) is one requirement
    uniq: dict[tuple, dict] = {}
    for t in out:
        key = (t["days"], t["kind"])
        if key in uniq:
            first = uniq[key]
            first["time_bar"] = first["time_bar"] or t["time_bar"]
            if first["day_type"] == "unspecified":
                first["day_type"] = t["day_type"]
            first["trigger"] = first["trigger"] or t["trigger"]
            continue
        uniq[key] = t
    return list(uniq.values())


def _matching_sentences(text: str, patterns: list[str], limit: int = 6) -> list[str]:
    text = unwrap(text)
    found = []
    for _s, _e, sent in sentences(text):
        ns = norm(sent)
        if any(re.search(p, ns) for p in patterns):
            found.append(sent.strip()[:500])
            if len(found) >= limit:
                break
    return found


def categorize(title: str, text: str, parent: str = "") -> tuple[str, list[str], float, dict]:
    nt, nb, npar = norm(title), norm(text), norm(parent)
    scores: dict[str, float] = {}
    # phrase matches in the title take precedence: score them, then blank them so their words are not re-counted
    for cat, words in _kw("clause").items():
        for w in sorted((w for w in words if " " in w), key=len, reverse=True):
            n = _count(nt, w)
            if n:
                scores[cat] = scores.get(cat, 0.0) + 10.0 * n
                nt = nt.replace(w, " ")
    for cat, words in _kw("clause").items():
        s = 0.0
        for w in words:
            f = 2.0 if " " in w else 1.0
            s += f * (4.0 * _count(nt, w) + 1.0 * _count(npar, w) + min(_count(nb, w), 4))
        if s:
            scores[cat] = scores.get(cat, 0.0) + s
    if not scores:
        return "general", [], 0.3, {}
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, best_score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    conf = 0.45 + 0.35 * (1 - second / best_score if best_score else 0) + min(0.15, best_score / 80)
    secondary = [c for c, v in ranked[1:4] if v >= best_score * 0.4]
    return best, secondary, round(min(conf, 0.95), 2), dict(ranked[:5])


def _percentages(text: str) -> list[dict]:
    text = unwrap(text)
    out = []
    for _s, _e, sent in sentences(text):
        ns = norm(sent)
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(%|٪|percent|per cent|في المائه|بالمائه|في المئه|في الالف|‰)", ns):
            out.append({"value": float(m.group(1)), "unit": "per_mille" if m.group(2) in ("في الالف", "‰") else "percent",
                        "sentence": sent.strip()[:400]})
    return out[:8]


@dataclass
class AnalyzedClause:
    number: str
    title: str
    parent_title: str | None
    text: str
    language: str
    page_start: int
    page_end: int
    page_is_estimated: bool
    category: str
    secondary_categories: list[str]
    confidence: float
    obligations: list[str]
    entitlements: list[str]
    conditions: list[str]
    exclusions: list[str]
    time_limits: list[dict]
    percentages: list[dict]
    risk_flags: list[dict]


def analyze_clause(rc: RawClause) -> AnalyzedClause:
    text = rc.text
    cat, secondary, conf, _ = categorize(rc.title, text, rc.parent_title or "")
    time_limits = extract_time_limits(text)
    exclusions = _matching_sentences(text, EXCLUSION_PATTERNS)
    clause_time_bar = bool(_matching_sentences(text, TIME_BAR_PATTERNS, 1))
    for t in time_limits:
        if clause_time_bar and t["kind"] == "notice" and not t["time_bar"]:
            t["time_bar"] = True
            t["time_bar_source"] = "clause"
    risk: list[dict] = []
    if any(t["time_bar"] for t in time_limits) or _matching_sentences(text, TIME_BAR_PATTERNS, 1):
        risk.append({"code": "time_bar", "en": "Contains time-bar / waiver language",
                     "ar": "يتضمن نص سقوط حق أو تنازل"})
    if exclusions:
        risk.append({"code": "exclusion", "en": "Contains an exclusion or limitation of entitlement",
                     "ar": "يتضمن استثناء أو قيدًا على الاستحقاق"})
    if any(t["day_type"] == "unspecified" for t in time_limits):
        risk.append({"code": "day_type_unspecified", "en": "Day type (calendar/working) not stated in this clause",
                     "ar": "نوع الأيام (تقويمية/عمل) غير محدد في هذا البند"})
    if re.search(r"\b(reasonable|promptly|as soon as practicable|in due course)\b|في اقرب وقت|في وقت مناسب", norm(text)):
        risk.append({"code": "ambiguous_period", "en": "Uses an undefined period (e.g. 'promptly', 'reasonable time')",
                     "ar": "يستخدم مدة غير محددة (مثل: في أقرب وقت)"})
    return AnalyzedClause(
        number=rc.number, title=rc.title[:400], parent_title=rc.parent_title, text=text,
        language=detect_language(text), page_start=rc.page_start, page_end=rc.page_end,
        page_is_estimated=rc.page_is_estimated, category=cat, secondary_categories=secondary, confidence=conf,
        obligations=_matching_sentences(text, OBLIGATION_PATTERNS),
        entitlements=_matching_sentences(text, ENTITLEMENT_PATTERNS),
        conditions=_matching_sentences(text, CONDITION_PATTERNS),
        exclusions=exclusions, time_limits=time_limits, percentages=_percentages(text), risk_flags=risk,
    )


def analyze_contract(pages: list[Page]) -> list[AnalyzedClause]:
    return [analyze_clause(rc) for rc in segment_clauses(pages)]
