"""Text extraction from PDF (text layer + OCR fallback), DOCX, XLSX, images, e-mail and plain text.

Returns page-level text so every downstream finding can cite a page. Formats without fixed pagination
(DOCX, e-mail) are split into *estimated* pages and flagged as such.
"""

from __future__ import annotations

import email
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from email import policy

from ..config import get_settings
from ..core.text import norm, normalize_digits

log = logging.getLogger("haqq.extraction")

ALLOWED = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".eml": "message/rfc822",
    ".txt": "text/plain",
}
_MAGIC = {
    ".pdf": [b"%PDF"],
    ".docx": [b"PK\x03\x04"],
    ".xlsx": [b"PK\x03\x04"],
    ".png": [b"\x89PNG"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".tif": [b"II*\x00", b"MM\x00*"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
}
ESTIMATED_PAGE_CHARS = 3000


class UnsupportedFile(ValueError):
    pass


def sniff(filename: str, data: bytes) -> tuple[str, str]:
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED:
        raise UnsupportedFile(f"File type '{ext or 'none'}' is not supported")
    sigs = _MAGIC.get(ext)
    if sigs and not any(data.startswith(s) for s in sigs):
        raise UnsupportedFile("File content does not match its extension")
    if ext in (".txt", ".eml"):
        try:
            data[:4096].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedFile("Text files must be UTF-8") from exc
    return ext, ALLOWED[ext]


@dataclass
class Page:
    number: int
    text: str
    method: str
    estimated: bool = False


@dataclass
class BoqRow:
    sheet: str
    row_number: int
    item_ref: str | None
    description: str
    unit: str | None
    quantity: Decimal | None
    rate: Decimal | None
    amount: Decimal | None


@dataclass
class Extraction:
    pages: list[Page]
    method: str
    ocr_pages: int = 0
    boq_rows: list[BoqRow] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)


# ----------------------------------------------------------------- OCR


def _ocr_image(img) -> str:
    import pytesseract

    return pytesseract.image_to_string(img, lang=get_settings().ocr_languages)


def ocr_available() -> bool:
    if not get_settings().ocr_enabled:
        return False
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001 - binary missing
        return False


# ----------------------------------------------------------------- formats


def _pdf(data: bytes) -> Extraction:
    import pdfplumber

    s = get_settings()
    pages: list[Page] = []
    ocr_count = 0
    can_ocr = ocr_available()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if len(text.strip()) < s.ocr_min_chars_per_page and can_ocr:
                try:
                    img = page.to_image(resolution=300).original
                    ocr_text = _ocr_image(img)
                    if len(ocr_text.strip()) > len(text.strip()):
                        pages.append(Page(i, ocr_text, "ocr"))
                        ocr_count += 1
                        continue
                except Exception as exc:  # noqa: BLE001
                    log.warning("OCR failed on page %s: %s", i, exc)
            pages.append(Page(i, text, "text"))
    method = "pdf_text" if ocr_count == 0 else ("pdf_ocr" if ocr_count == len(pages) else "pdf_text+ocr")
    meta = {}
    if not can_ocr and any(len(p.text.strip()) < s.ocr_min_chars_per_page for p in pages):
        meta["warning"] = "Some pages have no text layer and OCR is not available; they could not be read."
    return Extraction(pages, method, ocr_count, meta=meta)


def _paginate(blocks: list[str], method: str) -> list[Page]:
    pages, buf, n = [], [], 1
    size = 0
    for b in blocks:
        if b == "\f":
            if buf:
                pages.append(Page(n, "\n".join(buf), method, estimated=True))
                n += 1
                buf, size = [], 0
            continue
        buf.append(b)
        size += len(b)
        if size >= ESTIMATED_PAGE_CHARS:
            pages.append(Page(n, "\n".join(buf), method, estimated=True))
            n += 1
            buf, size = [], 0
    if buf or not pages:
        pages.append(Page(n, "\n".join(buf), method, estimated=True))
    return pages


def _docx(data: bytes) -> Extraction:
    import docx
    from docx.oxml.ns import qn

    d = docx.Document(io.BytesIO(data))
    blocks: list[str] = []
    for el in d.element.body.iterchildren():
        if el.tag == qn("w:p"):
            if el.findall(".//" + qn("w:br")) and any(b.get(qn("w:type")) == "page" for b in el.iter(qn("w:br"))):
                blocks.append("\f")
            txt = "".join(t.text or "" for t in el.iter(qn("w:t")))
            if txt.strip():
                blocks.append(txt)
        elif el.tag == qn("w:tbl"):
            for row in el.iter(qn("w:tr")):
                cells = ["".join(t.text or "" for t in c.iter(qn("w:t"))).strip() for c in row.iter(qn("w:tc"))]
                if any(cells):
                    blocks.append(" | ".join(cells))
    core = d.core_properties
    return Extraction(_paginate(blocks, "docx"), "docx", meta={"author": core.author, "title": core.title})


_HEADERS = {
    "item": ["item", "ref", "no", "بند", "رقم", "م"],
    "description": ["description", "desc", "work", "بيان", "وصف", "الاعمال", "البيان"],
    "unit": ["unit", "uom", "وحده", "الوحده"],
    "quantity": ["qty", "quantity", "كميه", "الكميه"],
    "rate": ["rate", "unit price", "price", "فئه", "سعر", "الفئه", "سعر الوحده"],
    "amount": ["amount", "total", "value", "اجمالي", "الاجمالي", "القيمه", "المبلغ"],
}


def _num(v) -> Decimal | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    s = normalize_digits(str(v)).replace(",", "").replace("٬", "").strip()
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _match_header(cells: list) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for idx, c in enumerate(cells):
        if c is None:
            continue
        v = norm(str(c)).strip()
        for key, words in _HEADERS.items():
            if key in mapping:
                continue
            if any(v == w or (len(w) > 2 and w in v) for w in words):
                mapping[key] = idx
                break
    return mapping if {"description", "quantity"} <= mapping.keys() or {"description", "rate"} <= mapping.keys() else None


def _xlsx(data: bytes) -> Extraction:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    pages: list[Page] = []
    rows_out: list[BoqRow] = []
    for n, ws in enumerate(wb.worksheets, start=1):
        lines = []
        header = None
        for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            cells = list(row)
            if not any(c not in (None, "") for c in cells):
                continue
            lines.append(" | ".join("" if c is None else str(c) for c in cells))
            if header is None:
                header = _match_header(cells)
                continue
            desc = cells[header["description"]] if header["description"] < len(cells) else None
            if not desc:
                continue

            def g(k, cells=cells, header=header):
                i = header.get(k)
                return cells[i] if i is not None and i < len(cells) else None

            qty, rate, amount = _num(g("quantity")), _num(g("rate")), _num(g("amount"))
            if qty is None and rate is None and amount is None:
                continue
            if amount is None and qty is not None and rate is not None:
                amount = (qty * rate).quantize(Decimal("0.01"))
            rows_out.append(BoqRow(ws.title, r_idx, str(g("item")) if g("item") is not None else None, str(desc),
                                   str(g("unit")) if g("unit") is not None else None, qty, rate, amount))
        pages.append(Page(n, f"[Sheet: {ws.title}]\n" + "\n".join(lines), "xlsx"))
    return Extraction(pages, "xlsx", boq_rows=rows_out, meta={"sheets": [w.title for w in wb.worksheets]})


def _image(data: bytes) -> Extraction:
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    meta = {"width": img.width, "height": img.height}
    if ocr_available():
        return Extraction([Page(1, _ocr_image(img), "ocr")], "image_ocr", 1, meta=meta)
    meta["warning"] = "OCR is not available; image stored as evidence without text."
    return Extraction([Page(1, "", "none")], "image", meta=meta)


def _email(data: bytes) -> Extraction:
    msg = email.message_from_bytes(data, policy=policy.default)
    body = msg.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body else ""
    if body and body.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    header = f"From: {msg['from']}\nTo: {msg['to']}\nDate: {msg['date']}\nSubject: {msg['subject']}\n\n"
    meta = {"from": str(msg["from"] or ""), "to": str(msg["to"] or ""), "subject": str(msg["subject"] or ""),
            "date": str(msg["date"] or ""),
            "attachments": [p.get_filename() for p in msg.iter_attachments() if p.get_filename()]}
    pages = _paginate((header + text).split("\n"), "email")
    return Extraction(pages, "email", meta=meta)


def _text(data: bytes) -> Extraction:
    text = data.decode("utf-8", errors="replace")
    return Extraction(_paginate(text.split("\n"), "text"), "text")


def extract(ext: str, data: bytes) -> Extraction:
    handler = {".pdf": _pdf, ".docx": _docx, ".xlsx": _xlsx, ".eml": _email, ".txt": _text}.get(ext, _image)
    return handler(data)


# ----------------------------------------------------------------- dates

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
     "december"], start=1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})
_AR_MONTHS = {"يناير": 1, "فبراير": 2, "مارس": 3, "ابريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7, "اغسطس": 8,
              "سبتمبر": 9, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}


def find_dates(text: str) -> list[date]:
    t = norm(text)
    out: list[date] = []
    for m in re.finditer(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t):
        out.append((int(m[1]), int(m[2]), int(m[3])))
    for m in re.finditer(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b", t):
        out.append((int(m[3]), int(m[2]), int(m[1])))
    for m in re.finditer(r"\b(\d{1,2})\s+([a-z]{3,9})\s*,?\s+(\d{4})\b", t):
        if m[2] in _MONTHS:
            out.append((int(m[3]), _MONTHS[m[2]], int(m[1])))
    for m in re.finditer(r"\b([a-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b", t):
        if m[1] in _MONTHS:
            out.append((int(m[3]), _MONTHS[m[1]], int(m[2])))
    for m in re.finditer(r"(\d{1,2})\s+([؀-ۿ]+)\s+(\d{4})", t):
        if m[2] in _AR_MONTHS:
            out.append((int(m[3]), _AR_MONTHS[m[2]], int(m[1])))
    result = []
    for y, mo, d in out:
        try:
            if 1990 <= y <= 2100:
                result.append(date(y, mo, d))
        except ValueError:
            continue
    return result
