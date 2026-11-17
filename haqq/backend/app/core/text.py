"""Text utilities shared by the extraction and intelligence engines (Arabic-aware)."""

from __future__ import annotations

import re
import unicodedata

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
ARABIC_RE = re.compile(r"[؀-ۿ]")


def normalize_digits(s: str) -> str:
    return s.translate(_AR_DIGITS)


def normalize_arabic(s: str) -> str:
    """Remove diacritics/tatweel and unify common letter variants (for matching only, never for display)."""
    s = _TASHKEEL.sub("", s)
    s = re.sub("[إأآا]", "ا", s)
    s = s.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return s


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return normalize_arabic(normalize_digits(s)).lower()


def detect_language(s: str) -> str:
    if not s:
        return "unknown"
    ar = len(ARABIC_RE.findall(s))
    latin = len(re.findall(r"[A-Za-z]", s))
    if ar and latin and min(ar, latin) / max(ar, latin) > 0.25:
        return "mixed"
    return "ar" if ar > latin else "en"


_TOKEN = re.compile(r"[a-z0-9]+|[؀-ۿ]+")
_STOP = set("""the a an of and or to in on for by with be is are was were shall will may as at this that from any
such which its it his her their under all other than not no if into upon been has have per
في من على الى إلى عن مع او أو ان أن هذا هذه التي الذي ذلك تلك كل اي أي لا ما قد كان يكون تكون بين وفقا
""".split())
_AR_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")


def tokens(s: str) -> list[str]:
    out = []
    for t in _TOKEN.findall(norm(s)):
        if t in _STOP or len(t) < 2:
            continue
        if ARABIC_RE.match(t):
            for pre in _AR_PREFIXES:
                if t.startswith(pre) and len(t) - len(pre) >= 3:
                    t = t[len(pre):]
                    break
        elif len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


def excerpt(text: str, needle_start: int, needle_end: int, pad: int = 140) -> str:
    a = max(0, needle_start - pad)
    b = min(len(text), needle_end + pad)
    return ("…" if a > 0 else "") + text[a:b].strip() + ("…" if b < len(text) else "")


def sentences(text: str) -> list[tuple[int, int, str]]:
    """Split text into sentences, returning (start, end, sentence)."""
    out = []
    for m in re.finditer(r"(?:[^.!?؟;\n]|(?<=\d)\.(?=\d)|\.(?=[a-z,]))+(?:[.!?؟;]+|\n|$)", text):
        sent = m.group(0).strip()
        if len(sent) > 3:
            out.append((m.start(), m.end(), sent))
    return out
