"""Generators for the DEMO document set. All wording is original, fictional and marked DEMO DATA.
These are not real legal agreements. Dates are relative to the seeding date so the demo stays current."""

from __future__ import annotations

import io
from datetime import date, timedelta
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
BANNER = "DEMO DATA - fictional document for demonstration only; not a real legal agreement."

CONTRACT_CLAUSES: list[tuple[str, str, str]] = [
    ("1", "General Provisions", ""),
    ("1.1", "Definitions",
     "In this Contract the Employer means Example Development Company (DEMO) and the Contractor means Example "
     "Construction Company (DEMO). The Engineer is the person appointed by the Employer to act for the purposes of the "
     "Contract. The Works means the New Administrative and Commercial Complex described in the Specification."),
    ("1.3", "Communications",
     "All notices, instructions, consents and determinations shall be in writing and delivered by hand, courier or the "
     "agreed electronic system. An oral instruction shall have no effect unless confirmed in writing by the Engineer."),
    ("2", "The Employer", ""),
    ("2.1", "Right of Access to the Site",
     "The Employer shall give the Contractor right of access to, and possession of, each part of the Site within the "
     "times stated in the Appendix to Tender. If the Contractor suffers delay and/or incurs Cost as a result of a failure "
     "by the Employer to give such right or possession within such time, the Contractor shall give notice to the Engineer "
     "and shall be entitled subject to Sub-Clause 20.1 to an extension of time for any such delay and payment of any "
     "such Cost, which shall be included in the Contract Price."),
    ("2.4", "Employer's Financial Arrangements",
     "The Employer shall submit, within twenty-eight (28) days after receiving any request from the Contractor, reasonable "
     "evidence that financial arrangements have been made to pay the Contract Price."),
    ("4", "The Contractor", ""),
    ("4.1", "Contractor's General Obligations",
     "The Contractor shall design (to the extent specified), execute and complete the Works in accordance with the "
     "Contract and with the Engineer's instructions, and shall remedy any defects in the Works."),
    ("4.12", "Unforeseeable Physical Conditions",
     "If the Contractor encounters physical conditions which he considers to have been Unforeseeable, the Contractor shall "
     "give notice to the Engineer as soon as practicable. If the Contractor suffers delay and/or incurs Cost due to these "
     "conditions, the Contractor shall be entitled subject to Sub-Clause 20.1 to an extension of time and payment of any "
     "such Cost."),
    ("8", "Commencement, Delays and Suspension", ""),
    ("8.4", "Extension of Time for Completion",
     "The Contractor shall be entitled subject to Sub-Clause 20.1 to an extension of the Time for Completion if and to the "
     "extent that completion is or will be delayed by any of the following causes: (a) a Variation; (b) a cause of delay "
     "giving an entitlement to extension of time under a Sub-Clause of these Conditions; (c) any delay, impediment or "
     "prevention caused by or attributable to the Employer or the Employer's other contractors on the Site."),
    ("8.7", "Delay Damages",
     "If the Contractor fails to comply with the Time for Completion, the Contractor shall pay delay damages of 0.1% of the "
     "Contract Price for every day which shall elapse between the Time for Completion and the date of the Taking-Over "
     "Certificate, subject to a maximum of 10% of the Contract Price."),
    ("8.8", "Suspension of Work",
     "The Engineer may at any time instruct the Contractor to suspend progress of part or all of the Works. If the "
     "Contractor suffers delay and/or incurs Cost from complying with such instruction, the Contractor shall give notice "
     "and shall be entitled subject to Sub-Clause 20.1 to an extension of time and payment of such Cost."),
    ("13", "Variations and Adjustments", ""),
    ("13.1", "Right to Vary",
     "Variations may be initiated by the Engineer at any time prior to issuing the Taking-Over Certificate for the Works, "
     "either by an instruction or by a request for the Contractor to submit a proposal. A Variation may include additional "
     "work, changes to the quantities of any item of work included in the Contract, and changes to levels, positions or "
     "dimensions of any part of the Works. The Contractor shall be entitled to have each Variation valued in accordance "
     "with Sub-Clause 13.3."),
    ("13.2", "Variation Procedure",
     "Each Variation shall be instructed in writing. Within fourteen (14) days after receiving an instruction, the "
     "Contractor shall submit a description of the work, a proposal for its valuation and any proposed modification to "
     "the programme. No payment shall be made for additional work executed without a written instruction of the Engineer."),
    ("13.3", "Valuation of Variations",
     "Each Variation shall be measured and valued at the rates and prices in the Bill of Quantities. Where no rate or price "
     "is appropriate, a new rate shall be derived from the relevant rates, or failing which from reasonable Cost plus a "
     "profit of five per cent (5%)."),
    ("13.7", "Adjustments for Changes in Cost",
     "The Contract Price shall be adjusted for rises or falls in the cost of reinforcing steel and cement only, in "
     "accordance with the formula in the Particular Conditions and the official indices published by CAPMAS. Except as "
     "provided in this Sub-Clause, the Contractor shall not be entitled to additional payment for changes in the cost of "
     "labour, Goods or other inputs, which are deemed to be included in the Accepted Contract Amount."),
    ("14", "Contract Price and Payment", ""),
    ("14.3", "Application for Interim Payment Certificates",
     "The Contractor shall submit a Statement to the Engineer after the end of each month showing in detail the amounts to "
     "which the Contractor considers himself entitled, together with supporting documents."),
    ("14.6", "Issue of Interim Payment Certificates",
     "The Engineer shall, within twenty-eight (28) days after receiving a Statement and supporting documents, issue to the "
     "Employer an Interim Payment Certificate which shall state the amount which the Engineer fairly determines to be due."),
    ("14.7", "Payment",
     "The Employer shall pay to the Contractor the amount certified in each Interim Payment Certificate within fifty-six "
     "(56) days after the Engineer receives the Statement and supporting documents."),
    ("14.8", "Delayed Payment",
     "If the Contractor does not receive payment in accordance with Sub-Clause 14.7, the Contractor shall be entitled to "
     "receive financing charges compounded monthly on the amount unpaid during the period of delay, calculated at the "
     "Central Bank of Egypt lending rate plus three percentage points. The Contractor shall be entitled to this payment "
     "without formal notice or certification."),
    ("14.9", "Retention",
     "Retention Money of five per cent (5%) shall be deducted from each Interim Payment Certificate. Fifty per cent (50%) of "
     "the Retention Money shall be released upon the issue of the Taking-Over Certificate and the balance after the expiry "
     "of the Defects Notification Period."),
    ("20", "Claims, Disputes and Arbitration", ""),
    ("20.1", "Contractor's Claims",
     "If the Contractor considers himself to be entitled to any extension of the Time for Completion and/or any additional "
     "payment under any Clause of these Conditions or otherwise in connection with the Contract, the Contractor shall give "
     "notice to the Engineer describing the event or circumstance giving rise to the claim. The notice shall be given as "
     "soon as practicable, and not later than twenty-eight (28) days after the Contractor became aware, or should have "
     "become aware, of the event or circumstance. If the Contractor fails to give notice of a claim within such period of "
     "28 days, the Time for Completion shall not be extended, the Contractor shall not be entitled to additional payment, "
     "and the Employer shall be discharged from all liability in connection with the claim. Within forty-two (42) days "
     "after the Contractor became aware of the event or circumstance, the Contractor shall send to the Engineer a fully "
     "detailed claim which includes full supporting particulars of the basis of the claim and of the extension of time "
     "and/or additional payment claimed. The Contractor shall keep such contemporary records as may be necessary to "
     "substantiate any claim."),
    ("20.6", "Arbitration",
     "Any dispute not settled amicably shall be finally settled by arbitration under the Rules of the Cairo Regional Centre "
     "for International Commercial Arbitration. The seat of arbitration shall be Cairo and the language shall be Arabic "
     "and English."),
]

AR_PARTICULAR = [
    ("المادة (1): أحكام عامة",
     "تسري هذه الشروط الخاصة على عقد مشروع المجمع الإداري والتجاري الجديد (بيانات عرض توضيحي)، وتكون لها الأولوية على "
     "الشروط العامة في حالة التعارض."),
    ("المادة (5): المستخلصات والدفعات",
     "يلتزم صاحب العمل بصرف قيمة كل مستخلص معتمد خلال ستين (60) يوماً من تاريخ تقديمه إلى المهندس، ويستقطع نسبة 5% "
     "محتجزات من كل مستخلص."),
    ("المادة (8): التأخير ومد المدة",
     "يحق للمقاول المطالبة بمد مدة التنفيذ في حالة تأخر صاحب العمل في تسليم أي جزء من الموقع، بشرط أن يخطر المقاول "
     "المهندس كتابياً خلال واحد وعشرين (21) يوماً من تاريخ علمه بالتأخير، وإلا يسقط حقه في المطالبة."),
    ("المادة (13): الأعمال الإضافية",
     "لا يجوز للمقاول تنفيذ أية أعمال إضافية إلا بناءً على أمر تغيير كتابي من المهندس، وتُحاسب الأعمال الإضافية بفئات "
     "جدول الكميات، وفي حالة عدم وجود فئة مماثلة يتم الاتفاق على فئة جديدة."),
]

BOQ_ROWS = [
    ("A.01", "Excavation in all types of soil for foundations, including disposal", "m3", 9800, 185),
    ("A.02", "Plain concrete blinding C15, 10 cm thick", "m3", 640, 2400),
    ("B.01", "Reinforced concrete C35 for raft, walls and slabs including formwork", "m3", 14200, 4850),
    ("B.02", "High tensile reinforcement steel, supplied, cut, bent and fixed", "ton", 1850, 41500),
    ("C.01", "Bituminous waterproofing membrane, two layers", "m2", 12400, 260),
    ("D.01", "Block work 20 cm thick", "m2", 21000, 410),
    ("E.01", "External landscaping works", "LS", 1, 3500000),
]


def contract_pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    if "DemoSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("DemoSans", str(FONT_DIR / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DemoSans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 20 * mm

    def new_page():
        nonlocal y
        c.setFont("DemoSans", 7)
        c.drawString(18 * mm, 10 * mm, BANNER)
        c.showPage()
        y = h - 20 * mm

    def line(text, font="DemoSans", size=9.5, gap=4.6):
        nonlocal y
        if y < 22 * mm:
            new_page()
        c.setFont(font, size)
        c.drawString(18 * mm, y, text)
        y -= gap * mm

    def wrap(text, width=98):
        words, cur, out = text.split(), "", []
        for wd in words:
            if len(cur) + len(wd) + 1 > width:
                out.append(cur)
                cur = wd
            else:
                cur = (cur + " " + wd).strip()
        if cur:
            out.append(cur)
        return out

    line("DEMO DATA - CONDITIONS OF CONTRACT", "DemoSans-Bold", 14, 7)
    line("New Administrative and Commercial Complex - Contract No. DEMO/NAC/2026/01", "DemoSans-Bold", 10, 6)
    line("Employer: Example Development Company (DEMO)   Contractor: Example Construction Company (DEMO)")
    line("Accepted Contract Amount: EGP 100,000,000 (one hundred million Egyptian Pounds)")
    line(BANNER, "DemoSans", 8, 8)
    for num, title, body in CONTRACT_CLAUSES:
        if not body:
            y -= 2 * mm
            if y < 40 * mm:
                new_page()
            line(f"{num} {title}", "DemoSans-Bold", 11, 6)
            continue
        if y < 35 * mm:
            new_page()
        line(f"{num} {title}", "DemoSans-Bold", 10, 5)
        for ln in wrap(body):
            line(ln)
        y -= 2 * mm
    c.setFont("DemoSans", 7)
    c.drawString(18 * mm, 10 * mm, BANNER)
    c.save()
    return buf.getvalue()


def particular_conditions_docx_ar() -> bytes:
    import docx
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    d = docx.Document()

    def p(text, bold=False):
        para = d.add_paragraph()
        ppr = para._p.get_or_add_pPr()
        b = OxmlElement("w:bidi")
        b.set(qn("w:val"), "1")
        ppr.append(b)
        r = para.add_run(text)
        r.bold = bold
        rpr = r._r.get_or_add_rPr()
        rt = OxmlElement("w:rtl")
        rt.set(qn("w:val"), "1")
        rpr.append(rt)

    p("بيانات عرض توضيحي — مستند افتراضي وليس عقدًا قانونيًا حقيقيًا", True)
    p("الشروط الخاصة — عقد مقاولة مشروع المجمع الإداري والتجاري الجديد", True)
    p("الطرف الأول: شركة مثال للتطوير العقاري (صاحب العمل). الطرف الثاني: شركة مثال للمقاولات (المقاول).")
    for title, body in AR_PARTICULAR:
        p(title, True)
        p(body)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def boq_xlsx() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["DEMO DATA — Bill of Quantities — New Administrative and Commercial Complex"])
    ws.append([])
    ws.append(["Item", "Description", "Unit", "Qty", "Rate (EGP)", "Amount (EGP)"])
    for ref, desc, unit, qty, rate in BOQ_ROWS:
        ws.append([ref, desc, unit, qty, rate, qty * rate])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def site_instruction_png(d: date) -> bytes:
    """A 'scanned' engineer's site instruction (image only — exercises OCR)."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1700, 2000), "white")
    dr = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(FONT_DIR / "DejaVuSans.ttf"), 34)
    fb = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 40)
    lines = [
        ("DEMO DATA - fictional document", f),
        ("", f),
        ("ENGINEER'S SITE INSTRUCTION No. SI-014", fb),
        (f"Date: {d.strftime('%d %B %Y')}", f),
        ("From: The Engineer - Example Consulting Engineers (DEMO)", f),
        ("To: Example Construction Company (DEMO)", f),
        ("Project: New Administrative and Commercial Complex", f),
        ("", f),
        ("Subject: Additional underground water tank and pump room", f),
        ("", f),
        ("You are hereby instructed to construct an additional", f),
        ("underground fire-fighting water tank and pump room adjacent", f),
        ("to Block C, as shown on revised drawing S-C-210 Rev. B.", f),
        ("This work is additional to the original scope of the Works.", f),
        ("Please proceed immediately to maintain the programme.", f),
        ("", f),
        ("Signed: Resident Engineer", f),
    ]
    y = 120
    for text, font in lines:
        dr.text((120, y), text, fill="black", font=font)
        y += 70
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def minutes_docx(d: date, *, title: str, items: list[str]) -> bytes:
    import docx

    doc = docx.Document()
    doc.add_paragraph("DEMO DATA - fictional document")
    doc.add_heading(title, level=1)
    doc.add_paragraph(f"Date: {d.strftime('%d %B %Y')}")
    doc.add_paragraph("Attendees: Employer's representative, the Engineer, Contractor's Project Manager")
    doc.add_paragraph("Agenda: progress, site handover, instructions")
    for i, it in enumerate(items, start=1):
        doc.add_paragraph(f"{i}. {it}")
    doc.add_paragraph("Action items recorded as above.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def letter_pdf(lines: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    if "DemoSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("DemoSans", str(FONT_DIR / "DejaVuSans.ttf")))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = A4[1] - 25 * mm
    c.setFont("DemoSans", 10)
    for ln in ["DEMO DATA - fictional document", "", *lines]:
        c.drawString(20 * mm, y, ln)
        y -= 6 * mm
    c.save()
    return buf.getvalue()


def email_eml(d: date, frm: str, to: str, subject: str, body: str) -> bytes:
    from datetime import UTC, datetime
    from email.message import EmailMessage
    from email.utils import format_datetime

    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = frm, to, subject
    m["Date"] = format_datetime(datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC))
    m.set_content("DEMO DATA - fictional e-mail\n\n" + body)
    return bytes(m)


def daily_report_txt(d: date, body: str) -> bytes:
    return (f"DEMO DATA - fictional document\nDAILY REPORT / SITE DIARY\nDate: {d.isoformat()}\n"
            f"Weather: clear\nManpower: 142\nEquipment on site: 2 excavators, 1 tower crane\n\n{body}\n").encode()


def rel(today: date, days_ago: int) -> date:
    return today - timedelta(days=days_ago)
