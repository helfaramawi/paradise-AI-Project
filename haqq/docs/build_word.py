"""Builds the HAQQ Word guides (English and Arabic) from the Markdown sources in this folder.

    python haqq/docs/build_word.py            # writes haqq/docs/word/*.docx

Arabic documents are genuinely right-to-left (bidi paragraphs, RTL runs, right-to-left tables); code, paths and
commands stay left-to-right. Re-run after editing any of the Markdown sources.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import docx
from docx.enum.section import WD_ORIENT  # noqa: F401  (kept for future landscape tables)
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
OUT = HERE / "word"
NAVY, BLUE, GOLD, GREY = "0B2545", "13315C", "C49A3A", "667085"
BOOKS = [
    ("USER_GUIDE.md", "HAQQ_User_Guide_EN.docx", "en", "User Guide"),
    ("USER_GUIDE_AR.md", "HAQQ_User_Guide_AR.docx", "ar", "دليل المستخدم"),
    ("OPERATIONS_GUIDE.md", "HAQQ_Operations_Backup_Recovery_Guide_EN.docx", "en", "Operations, Backup & Recovery Guide"),
    ("OPERATIONS_GUIDE_AR.md", "HAQQ_Operations_Backup_Recovery_Guide_AR.docx", "ar", "دليل التشغيل والنسخ الاحتياطي والاستعادة"),
]
INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)")


def _rtl_paragraph(p) -> None:
    ppr = p._p.get_or_add_pPr()
    b = OxmlElement("w:bidi")
    b.set(qn("w:val"), "1")
    ppr.append(b)


def _rtl_run(r) -> None:
    rpr = r._r.get_or_add_rPr()
    e = OxmlElement("w:rtl")
    e.set(qn("w:val"), "1")
    rpr.append(e)


class Writer:
    def __init__(self, lang: str, title: str):
        self.lang, self.rtl = lang, lang == "ar"
        self.d = docx.Document()
        for s in self.d.sections:
            s.left_margin = s.right_margin = Cm(2.2)
            s.top_margin = s.bottom_margin = Cm(2)
        st = self.d.styles["Normal"]
        st.font.name = "Calibri"
        st.font.size = Pt(10.5)
        rf = st.element.rPr.rFonts
        rf.set(qn("w:cs"), "Arial")
        st.element.rPr.append(OxmlElement("w:szCs"))
        st.element.rPr.find(qn("w:szCs")).set(qn("w:val"), "22")
        self.title = title
        self._footer()

    # ---- primitives
    def para(self, text: str = "", *, size=None, bold=False, color=None, align=None, space_after=6, italic=False,
             style=None, keep_ltr=False):
        p = self.d.add_paragraph(style=style)
        if self.rtl and not keep_ltr:
            _rtl_paragraph(p)
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if align is None else align
        elif align is not None:
            p.alignment = align
        p.paragraph_format.space_after = Pt(space_after)
        self.inline(p, text, size=size, bold=bold, color=color, italic=italic, keep_ltr=keep_ltr)
        return p

    def inline(self, p, text, *, size=None, bold=False, color=None, italic=False, keep_ltr=False):
        for part in INLINE.split(text):
            if not part:
                continue
            b, it, code = bold, italic, False
            if part.startswith("**") and part.endswith("**"):
                part, b = part[2:-2], True
                if part.startswith("`") and part.endswith("`"):
                    part, code = part[1:-1], True
            elif part.startswith("`") and part.endswith("`"):
                part, code = part[1:-1], True
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                part, it = part[1:-1], True
            r = p.add_run(part)
            r.bold, r.italic = b, it
            if size:
                r.font.size = Pt(size)
            if color:
                r.font.color.rgb = RGBColor.from_string(color)
            if code:
                r.font.name = "Consolas"
                r.font.size = Pt(9.5)
                r.font.color.rgb = RGBColor.from_string(BLUE)
            elif self.rtl and not keep_ltr:
                _rtl_run(r)
                if b:
                    r._r.get_or_add_rPr().append(OxmlElement("w:bCs"))

    def _footer(self):
        f = self.d.sections[0].footer.paragraphs[0]
        if self.rtl:
            _rtl_paragraph(f)
        f.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = f.add_run(("حقّك — " if self.rtl else "HAQQ — ") + self.title + " · Paradise AI Solutions (PAIS)")
        r.font.size = Pt(8)
        r.font.color.rgb = RGBColor.from_string(GREY)

    def cover(self):
        self.para("", space_after=60)
        self.para("HAQQ · حقّك", size=34, bold=True, color=NAVY, align=WD_ALIGN_PARAGRAPH.CENTER)
        tagline = "اكتشف مستحقاتك التعاقدية قبل أن تضيع" if self.rtl else "Don't lose what your contract entitles you to."
        self.para(tagline, size=14, color=GOLD, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=30)
        self.para(self.title, size=22, bold=True, color=BLUE, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=40)
        meta = (f"الإصدار 0.1 · {date.today().isoformat()}" if self.rtl else f"Version 0.1 · {date.today().isoformat()}")
        self.para(meta, size=11, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER)
        self.para("Paradise AI Solutions (PAIS)", size=11, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER)
        self.d.add_page_break()

    def heading(self, text: str, level: int):
        sizes = {1: 18, 2: 14, 3: 12}
        p = self.para(text, size=sizes.get(level, 12), bold=True, color=NAVY if level == 1 else BLUE, space_after=4)
        p.paragraph_format.space_before = Pt(14 if level <= 2 else 8)
        p.paragraph_format.keep_with_next = True
        if level == 2:
            ppr = p._p.get_or_add_pPr()
            bdr = OxmlElement("w:pBdr")
            bot = OxmlElement("w:bottom")
            for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "2"), ("w:color", GOLD)):
                bot.set(qn(k), v)
            bdr.append(bot)
            ppr.append(bdr)

    def bullet(self, text: str, number: int | None = None):
        if number is None:
            return self.para(text, style="List Bullet", space_after=2)
        # explicit numbers: Word's auto-numbering would continue across sections
        p = self.para(f"{number}. {text}", space_after=3)
        p.paragraph_format.left_indent = Cm(0.6) if not self.rtl else None
        if self.rtl:
            p.paragraph_format.right_indent = Cm(0.6)
        p.paragraph_format.first_line_indent = Cm(-0.6)
        return p

    def code(self, lines: list[str]):
        for ln in lines:
            p = self.d.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.left_indent = Cm(0.6)
            r = p.add_run(ln or " ")
            r.font.name = "Consolas"
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor.from_string(BLUE)
            shd = OxmlElement("w:shd")
            for k, v in (("w:val", "clear"), ("w:color", "auto"), ("w:fill", "F2F4F7")):
                shd.set(qn(k), v)
            p._p.get_or_add_pPr().append(shd)
        self.para("", space_after=4)

    def table(self, rows: list[list[str]]):
        header, body = rows[0], rows[1:]
        t = self.d.add_table(rows=1, cols=len(header))
        t.style = "Light Grid Accent 1"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        if self.rtl:
            bv = OxmlElement("w:bidiVisual")
            bv.set(qn("w:val"), "1")
            t._tbl.tblPr.append(bv)

        def fill(cell, text, bold=False):
            cell.text = ""
            p = cell.paragraphs[0]
            if self.rtl:
                _rtl_paragraph(p)
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            self.inline(p, text, size=9.5, bold=bold)

        for i, h in enumerate(header):
            fill(t.rows[0].cells[i], h, True)
        for row in body:
            cells = t.add_row().cells
            for i, v in enumerate(row[: len(header)]):
                fill(cells[i], v)
        self.para("", space_after=4)

    def image(self, path: Path, caption: str):
        if not path.exists():
            self.para(f"[missing image: {path.name}]", color="B42318")
            return
        self.d.add_picture(str(path), width=Cm(16))
        self.d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.para(caption, size=9, italic=True, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER)

    def save(self, path: Path):
        self.d.save(str(path))


def convert(md_path: Path, out_path: Path, lang: str, title: str) -> None:
    w = Writer(lang, title)
    w.cover()
    lines = md_path.read_text(encoding="utf-8").splitlines()
    i = 0
    first_h1 = True
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            w.code(block)
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            w.table(rows)
            continue
        elif m := re.match(r"!\[([^\]]*)\]\(([^)]+)\)", s):
            w.image(HERE / m.group(2), m.group(1))
        elif m := re.match(r"(#{1,3})\s+(.*)", s):
            level = len(m.group(1))
            if level == 1 and first_h1:
                first_h1 = False  # the cover already carries the title
            else:
                w.heading(m.group(2), level)
        elif m := re.match(r"[*-]\s+(.*)", s):
            w.bullet(m.group(1))
        elif m := re.match(r"(\d+)\.\s+(.*)", s):
            num, text = int(m.group(1)), m.group(2)
            while i + 1 < len(lines) and lines[i + 1].startswith("   ") and lines[i + 1].strip():
                i += 1
                text += " " + lines[i].strip()
            w.bullet(text, number=num)
        elif s.startswith(">"):
            p = w.para(s.lstrip("> ").strip(), italic=True, color=BLUE)
            p.paragraph_format.left_indent = Cm(0.5)
        elif s:
            text = s
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"\s*([#|>*`!-]|\d+\.)", lines[i + 1]):
                i += 1
                text += " " + lines[i].strip()
            w.para(text)
        i += 1
    w.save(out_path)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for src, dst, lang, title in BOOKS:
        convert(HERE / src, OUT / dst, lang, title)
        print(f"wrote {OUT / dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
