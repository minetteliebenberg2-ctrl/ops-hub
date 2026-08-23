# ==========================================================
# FC Hub - Documents module templates
# ----------------------------------------------------------
# Purpose:
# Build the two branded blank templates the Documents module
# creates new files from: a letterhead (.docx) for letters, and a
# spreadsheet (.xlsx) carrying the same header. Both mirror the
# PDF documents' header: logo, trading name, Germiston locality and
# contact block, green rule, and the MAINTAIN tagline footer.
#
# Run directly to regenerate both after a brand change:
#   python modules/documents/templates/build_templates.py
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, Side

from core.app_paths import get_assets_dir
from core.document_pdf import BUSINESS_LOCALITY, TAGLINE


TEMPLATE_DIR = Path(__file__).resolve().parent
LOGO_PATH = get_assets_dir() / "logo_placeholder.png"

LETTERHEAD_PATH = TEMPLATE_DIR / "FacilitiesCo_Letterhead.docx"
SPREADSHEET_PATH = TEMPLATE_DIR / "FacilitiesCo_Spreadsheet.xlsx"

# Matches ACCENT_COLOR / INK_COLOR / GREY_COLOR in core/document_pdf.py.
ACCENT_HEX = "1B7A3D"
INK_HEX = "3A3A3A"
GREY_HEX = "6B7280"

ACCENT_RGB = RGBColor(0x1B, 0x7A, 0x3D)
INK_RGB = RGBColor(0x3A, 0x3A, 0x3A)
GREY_RGB = RGBColor(0x6B, 0x72, 0x80)

FONT = "Lato"

TRADING_NAME = "Shade Solutions by FacilitiesCo (Pty) Ltd"
CONTACT_LINES = (
    BUSINESS_LOCALITY,
    "sales@facilitiesco.com",
    "010 015 0532 / 083 378 5122",
    "www.facilitiesco.com",
)
REGISTRATION_LINE = "Reg: 2024/772013/07  |  Not VAT registered"


def _set_font(run, size=10.5, color=INK_RGB, bold=False, italic=False):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    # Word needs the east-asian font set too or it silently substitutes.
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), FONT)


def _add_bottom_rule(paragraph, hex_color=ACCENT_HEX, size=12):
    """Green rule under the header, drawn as a paragraph border so it repeats
    correctly if the header block is reused."""

    p_pr = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), hex_color)
    borders.append(bottom)
    p_pr.append(borders)


def build_letterhead():
    """Blank letterhead: branded header, empty body for the user to type into,
    branded footer. Deliberately contains no placeholder body text - Minette
    writes the letter, the template only supplies the chrome."""

    doc = Document()

    section = doc.sections[0]
    section.top_margin = Cm(1.4)
    section.bottom_margin = Cm(1.4)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)

    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(10.5)

    # --- Header: logo left, contact block right ---
    header = section.header
    header_para = header.paragraphs[0]
    header_para.alignment = WD_ALIGN_PARAGRAPH.LEFT

    table = header.add_table(rows=1, cols=2, width=Cm(17.0))
    table.autofit = False
    logo_cell, contact_cell = table.rows[0].cells
    logo_cell.width = Cm(9.0)
    contact_cell.width = Cm(8.0)

    logo_para = logo_cell.paragraphs[0]
    if LOGO_PATH.is_file():
        logo_para.add_run().add_picture(str(LOGO_PATH), width=Cm(6.4))

    contact_para = contact_cell.paragraphs[0]
    contact_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = contact_para.add_run(TRADING_NAME)
    _set_font(run, size=10, bold=True)
    for line in CONTACT_LINES:
        contact_para.add_run("\n")
        _set_font(contact_para.add_run(line), size=9.5, color=INK_RGB)

    rule_para = header.add_paragraph()
    rule_para.paragraph_format.space_before = Pt(4)
    rule_para.paragraph_format.space_after = Pt(0)
    _add_bottom_rule(rule_para)

    # --- Body: Date / To / Re, then space to write, then a sign-off ---
    # Carried over from Minette's previous letterhead (C:\For Claude\Documents\
    # FC Letterhead.pdf), which had these fields and a "Prepared By" block. That
    # version is superseded: it still said SUSTAIN and printed her home address.
    doc.add_paragraph()
    for label in ("Date:", "To:", "Re:"):
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(2)
        _set_font(paragraph.add_run(label), size=10.5, bold=True)

    for _ in range(3):
        doc.add_paragraph()

    signoff = doc.add_paragraph()
    signoff.paragraph_format.space_before = Pt(24)
    _set_font(signoff.add_run("Prepared By: "), size=10.5, bold=True)
    _set_font(signoff.add_run("Minette Liebenberg"), size=10.5)
    for line in ("Director", "Shade Solutions by FacilitiesCo",
                 "sales@facilitiesco.com", "010 015 0532 / 083 378 5122"):
        signoff.add_run("\n")
        _set_font(signoff.add_run(line), size=10)

    # --- Footer: tagline + registration, mirroring the PDF footer ---
    footer = section.footer
    footer_para = footer.paragraphs[0]
    footer_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _set_font(footer_para.add_run(TAGLINE), size=8, color=INK_RGB, bold=True)
    footer_para.add_run("\n")
    _set_font(footer_para.add_run(REGISTRATION_LINE), size=7.5, color=GREY_RGB)

    doc.save(str(LETTERHEAD_PATH))
    return LETTERHEAD_PATH


def build_spreadsheet():
    """Blank branded workbook with the same header as the letterhead, so a
    schedule or costing sheet sent to a client looks like it came from the
    same business as the quote."""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"

    sheet.column_dimensions["A"].width = 30
    for column in ("B", "C", "D", "E", "F"):
        sheet.column_dimensions[column].width = 16

    # Logo sits over the top-left; rows sized to clear it.
    sheet.row_dimensions[1].height = 34
    sheet.row_dimensions[2].height = 34
    if LOGO_PATH.is_file():
        image = XLImage(str(LOGO_PATH))
        # Preserve aspect ratio at roughly the letterhead's logo width.
        image.width, image.height = 240, 56
        sheet.add_image(image, "A1")

    trading = sheet["D1"]
    trading.value = TRADING_NAME
    trading.font = Font(name=FONT, size=10, bold=True, color=INK_HEX)
    trading.alignment = Alignment(horizontal="right")
    sheet.merge_cells("D1:F1")

    for offset, line in enumerate(CONTACT_LINES, start=2):
        cell = sheet.cell(row=offset, column=4)
        cell.value = line
        cell.font = Font(name=FONT, size=9, color=INK_HEX)
        cell.alignment = Alignment(horizontal="right")
        sheet.merge_cells(start_row=offset, start_column=4, end_row=offset, end_column=6)

    # Green rule under the header block.
    rule = Side(style="medium", color=ACCENT_HEX)
    for column in range(1, 7):
        sheet.cell(row=6, column=column).border = Border(bottom=rule)

    footer_row = 8
    footer = sheet.cell(row=footer_row, column=1)
    footer.value = TAGLINE
    footer.font = Font(name=FONT, size=8, bold=True, color=INK_HEX)

    registration = sheet.cell(row=footer_row + 1, column=1)
    registration.value = REGISTRATION_LINE
    registration.font = Font(name=FONT, size=7.5, color=GREY_HEX)

    # Leave the user on the first free cell below the header.
    sheet.freeze_panes = "A7"

    workbook.save(str(SPREADSHEET_PATH))
    return SPREADSHEET_PATH


if __name__ == "__main__":
    print("saved:", build_letterhead())
    print("saved:", build_spreadsheet())
