"""Generic proposal template builder.

Generates a branded A4 proposal .docx with placeholder fields.
Business identity is read from business_settings at generation time.

Run directly to regenerate:
    python modules/proposals/templates/build_proposal_template.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from core.app_paths import get_assets_dir

GREEN = RGBColor(0x1B, 0x7A, 0x3D)
CHARCOAL = RGBColor(0x33, 0x33, 0x33)
GREY = RGBColor(0x70, 0x70, 0x70)
LIGHTGREY = RGBColor(0xAA, 0xAA, 0xAA)
PLACEHOLDER_BG = "FAFAFA"

FONT = "Lato"

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = get_assets_dir()
LOGO_PATH = ASSETS_DIR / "logo_placeholder.png"
ICON_DIR = ASSETS_DIR / "social_icons"


def _load_identity():
    """Read business identity from the database."""
    from core.business_settings_service import BusinessSettingsService
    s = BusinessSettingsService().get_settings()
    return {
        "trading_name": s.legal_name or s.trading_name or "Company Name",
        "email": s.email or "",
        "phone": s.phone or "",
        "website": s.website or "",
        "registration_number": s.registration_number or "",
    }


def set_font(run, size=10.5, color=CHARCOAL, bold=False, italic=False, name=FONT):
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.bold = bold
    run.italic = italic
    run.font.name = name
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), name)


def shade_cell(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def cell_border(cell, style="dashed", color="AAAAAA", size=6):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement('w:tcBorders')
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), style)
        el.set(qn('w:sz'), str(size))
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), color)
        borders.append(el)
    tcPr.append(borders)


def set_row_height(row, cm_height):
    trPr = row._tr.get_or_add_trPr()
    trHeight = OxmlElement('w:trHeight')
    trHeight.set(qn('w:val'), str(int(cm_height * 567)))
    trHeight.set(qn('w:hRule'), 'atLeast')
    trPr.append(trHeight)


def set_bottom_border(paragraph, color="1B7A3D", size=8, space=5):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), str(size))
    bottom.set(qn('w:space'), str(space))
    bottom.set(qn('w:color'), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def page_break(doc):
    doc.add_page_break()


def h1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run(text.upper())
    set_font(run, size=19, color=CHARCOAL, bold=True)
    set_bottom_border(p)
    return p


def h2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text.upper())
    set_font(run, size=12, color=GREEN, bold=True)
    return p


def body(doc, text, size=10.5, color=CHARCOAL, italic=False, bold=False, space_after=6, alignment=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    if alignment:
        p.alignment = alignment
    run = p.add_run(text)
    set_font(run, size=size, color=color, bold=bold, italic=italic)
    return p


def bullet(doc, text, size=10.5):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(text)
    set_font(run, size=size, color=CHARCOAL)
    return p


def field_line(doc, label, blank_width="[ FILL IN ]"):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r1 = p.add_run(f"{label}:  ")
    set_font(r1, size=10.5, color=CHARCOAL, bold=True)
    r2 = p.add_run(blank_width)
    set_font(r2, size=10.5, color=LIGHTGREY)
    return p


def cell_padding(cell, top=60, bottom=60, left=100, right=100):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for edge, value in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:w'), str(value))
        el.set(qn('w:type'), 'dxa')
        tcMar.append(el)
    tcPr.append(tcMar)


def row_bottom_rule(cell, color="E0E0E0", size=4):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement('w:tcBorders')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), str(size))
    bottom.set(qn('w:space'), '0')
    bottom.set(qn('w:color'), color)
    borders.append(bottom)
    tcPr.append(borders)


def styled_table(doc, headers, rows, col_widths_cm):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    hdr_cells = table.rows[0].cells
    set_row_height(table.rows[0], 0.9)
    for i, htext in enumerate(headers):
        hdr_cells[i].width = Cm(col_widths_cm[i])
        shade_cell(hdr_cells[i], "1B7A3D")
        cell_padding(hdr_cells[i])
        hdr_cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = hdr_cells[i].paragraphs[0]
        r = p.add_run(htext)
        set_font(r, size=10, color=RGBColor(0xFF, 0xFF, 0xFF), bold=True)
    for row_index, row_data in enumerate(rows):
        row_cells = table.add_row().cells
        set_row_height(table.rows[row_index + 1], 0.85)
        is_last = row_index == len(rows) - 1
        for i, val in enumerate(row_data):
            row_cells[i].width = Cm(col_widths_cm[i])
            cell_padding(row_cells[i])
            row_cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if not is_last:
                row_bottom_rule(row_cells[i])
            p = row_cells[i].paragraphs[0]
            r = p.add_run(str(val))
            set_font(r, size=10, color=CHARCOAL)
    return table


def photo_grid(doc, count=8, cols=4, cell_w_cm=3.7, cell_h_cm=2.3):
    rows_needed = (count + cols - 1) // cols
    table = doc.add_table(rows=rows_needed, cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    n = 0
    for r in range(rows_needed):
        set_row_height(table.rows[r], cell_h_cm)
        for c in range(cols):
            n += 1
            cell = table.rows[r].cells[c]
            cell.width = Cm(cell_w_cm)
            shade_cell(cell, PLACEHOLDER_BG)
            cell_border(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r1 = p.add_run("\U0001F4F7")
            set_font(r1, size=14, color=RGBColor(0xBB, 0xBB, 0xBB))
            p2 = cell.add_paragraph()
            p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r2 = p2.add_run(f"Photo {n}" if n <= count else "")
            set_font(r2, size=8, color=RGBColor(0xBB, 0xBB, 0xBB), italic=True)
    return table


def add_logo(doc, path, width_cm, alignment=WD_ALIGN_PARAGRAPH.CENTER):
    p = doc.add_paragraph()
    p.alignment = alignment
    run = p.add_run()
    run.add_picture(path, width=Cm(width_cm))
    return p


def build_template():
    """Build a generic proposal template .docx."""
    biz = _load_identity()

    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(1.6)
    section.bottom_margin = Cm(1.6)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

    normal_style = doc.styles['Normal']
    normal_style.font.name = FONT
    normal_style.font.size = Pt(10.5)
    rpr = normal_style.element.get_or_add_rPr()
    rFonts = rpr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rpr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), FONT)

    # ============================================================
    # PAGE 1 -- COVER
    # ============================================================
    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    if LOGO_PATH.is_file():
        add_logo(doc, str(LOGO_PATH), width_cm=9)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(40)
    r = p.add_run("DESIGN  |  CREATE  |  INNOVATE  |  MAINTAIN")
    set_font(r, size=9.5, color=GREY, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(40)
    r = p.add_run("PROPOSAL")
    set_font(r, size=38, color=CHARCOAL, bold=True)

    # Client logo placeholder
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    cell.width = Cm(7)
    shade_cell(cell, PLACEHOLDER_BG)
    cell_border(cell)
    set_row_height(table.rows[0], 3.2)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("[ CLIENT LOGO ]")
    set_font(r, size=11, color=LIGHTGREY, italic=True)

    doc.add_paragraph().paragraph_format.space_after = Pt(20)

    field_line(doc, "Prepared For", "[CLIENT / COMPANY NAME]")
    field_line(doc, "Attention", "[CONTACT PERSON]")
    field_line(doc, "Site", "[SITE NAME / ADDRESS]")
    field_line(doc, "Date", "[DATE]")

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(90)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"Prepared by {biz['trading_name']}")
    set_font(r, size=10.5, color=GREY)

    contact_parts = [x for x in (biz["email"], biz["phone"]) if x]
    if contact_parts:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run("  ·  ".join(contact_parts))
        set_font(r, size=9.5, color=GREY)

    page_break(doc)

    # ============================================================
    # PAGE 2 -- SCOPE OF WORK
    # ============================================================
    h1(doc, "Scope of Work")

    body(
        doc,
        "Every project is considered and specified to fit your site.",
        italic=True, color=GREY, space_after=16,
    )

    h2(doc, "Site Details")
    field_line(doc, "Site / Area", "[SITE / AREA NAME]")
    field_line(doc, "Description", "[PROJECT DESCRIPTION]")

    h2(doc, "Project Timeline")
    styled_table(
        doc,
        ["Phase", "Description", "Duration"],
        [
            ["1. Site Inspection", "Site assessed and measurements taken", "[ ]"],
            ["2. Quotation", "Formal quote issued for sign-off", "[ ]"],
            ["3. Order Confirmation", "Signed quotation + deposit received", "[ ]"],
            ["4. Preparation", "Materials and resources prepared", "[ ]"],
            ["5. Execution", "On-site work completed", "[ ]"],
            ["6. Final Inspection", "Sign-off with site contact", "[ ]"],
        ],
        [4.8, 8.2, 3.0],
    )

    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    h2(doc, "What Is Expected From You")
    from core.quote_document import balance_percent, deposit_percent  # noqa: E402
    bullet(doc, f"A deposit of {deposit_percent()}% is required on confirmation of order, "
                f"{balance_percent()}% balance on completion")
    bullet(doc, "Confirmation of order is a signed quotation and deposit")
    bullet(doc, "The price on the quotation is all-inclusive")
    bullet(doc, "Site access arranged for inspection, work, and final sign-off")

    page_break(doc)

    # ============================================================
    # PAGE 3 -- SITE INSPECTION (photo grid)
    # ============================================================
    h1(doc, "Site Inspection")
    body(doc, "Area: [SITE / AREA NAME]", bold=True, size=12, color=CHARCOAL, space_after=8)

    photo_grid(doc, count=8, cols=4)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    h2(doc, "Notes")
    field_line(doc, "Description", "[PROJECT NOTES]")

    page_break(doc)

    h1(doc, "Additional Site Photos")
    body(
        doc,
        "Optional -- delete this page if 8 photos were enough.",
        italic=True, color=GREY, space_after=12,
    )
    photo_grid(doc, count=8, cols=4)

    page_break(doc)

    # ============================================================
    # PAGE 4 -- THANK YOU / CONTACT
    # ============================================================
    for _ in range(4):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Thank You for the Opportunity")
    set_font(r, size=24, color=CHARCOAL, bold=True)

    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(biz["trading_name"])
    set_font(r, size=12.5, color=CHARCOAL, bold=True)

    contact_lines = [x for x in (biz["email"], biz["phone"], biz["website"]) if x]
    for line in contact_lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(line)
        set_font(r, size=10, color=GREY)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # Social icons (if present)
    if (ICON_DIR / "icon_instagram.png").is_file():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for icon_name in ["instagram", "facebook", "youtube", "linkedin"]:
            icon_path = ICON_DIR / f"icon_{icon_name}.png"
            if icon_path.is_file():
                run = p.add_run()
                run.add_picture(str(icon_path), width=Cm(0.9))
                p.add_run("   ")

    if biz["website"]:
        doc.add_paragraph().paragraph_format.space_after = Pt(8)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = p.add_run(f"\U0001F310 {biz['website']}")
        set_font(r1, size=9, color=GREY)

    out_path = os.path.join(DOCS_DIR, "Proposal_Template_A4.docx")
    doc.save(out_path)
    return out_path


if __name__ == "__main__":
    print("saved:", build_template())
