import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import docx
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

FONT = "Poppins"

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = get_assets_dir()
LOGO_PATH = ASSETS_DIR / "logo_placeholder.png"
ICON_DIR = ASSETS_DIR / "social_icons"

CLIENT_LOGOS = {
    "Komatsu": r"C:\users\minet\OneDrive\Documents\FacilitiesCo\FacilitiesCo Pty\FC Clients\Komatsu\Komatsu Logo.png",
    "Blend Property Group": r"C:\users\minet\OneDrive\Documents\FacilitiesCo\FacilitiesCo Pty\FC Clients\Blend Property Group\Blend Property Logo.png",
    "Astron": r"C:\users\minet\OneDrive\Documents\FacilitiesCo\FacilitiesCo Pty\FC Clients\Astron\astron Logo.jpg",
    "Benjamin Prep": r"C:\users\minet\OneDrive\Documents\FacilitiesCo\FacilitiesCo Pty\FC Clients\School\Benjamin Prep Logo-05.png",
}
CLIENTS_NO_LOGO = [
    "Digistics", "BDO", "DSV", "CoSpace", "Rebosis Property Fund",
    "Ascension Properties", "Saint Gobain", "Tarloy Properties",
    "Insimbi Alloy", "The Cavaleros Property Group", "Little Porcupine Schools",
]


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


doc = Document()
section = doc.sections[0]
section.top_margin = Cm(1.6)
section.bottom_margin = Cm(1.6)
section.left_margin = Cm(2.2)
section.right_margin = Cm(2.2)

# Set the document's default (Normal style) font to Poppins so any
# un-styled text also renders correctly.
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
# PAGE 1 — COVER
# ============================================================
doc.add_paragraph().paragraph_format.space_after = Pt(6)
add_logo(doc, str(LOGO_PATH), width_cm=9)
# Logo already includes the "SHADE SOLUTIONS" sub-line baked in - no
# separate text needed here.

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
r = p.add_run("Prepared by Minette Liebenberg")
set_font(r, size=10.5, color=GREY)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("minette@facilitiesco.com  \u00b7  083 378 5122")
set_font(r, size=9.5, color=GREY)

page_break(doc)

# ============================================================
# PAGE 2 — SCOPE OF WORK (How We Work intro folded in briefly)
# ============================================================
h1(doc, "Scope of Work")

body(
    doc,
    "Everything we do is considered, directed through strategy and concept \u2014 "
    "structures, netting and cable specified to fit your site, not off-the-shelf.",
    italic=True, color=GREY, space_after=16,
)

h2(doc, "Site Details")
field_line(doc, "Site / Area", "[e.g. Directors Parking]")
field_line(doc, "Structure Colour", "[COLOUR]")
field_line(doc, "Netting Colour", "[COLOUR]")
field_line(doc, "Netting Size", "[SINGLE / DOUBLE / TRIPLE]")
field_line(doc, "Dimensions", "[WIDTH x LENGTH]")

h2(doc, "Project Timeline")
styled_table(
    doc,
    ["Phase", "Description", "Duration"],
    [
        ["1. Site Inspection", "Measurements taken, structures assessed", "[ ]"],
        ["2. Quotation", "Formal quote issued for sign-off", "[ ]"],
        ["3. Order Confirmation", "Signed quotation + deposit received", "[ ]"],
        ["4. Fabrication", "Steelwork and netting prepared to spec", "[ ]"],
        ["5. Installation", "On-site installation and tensioning", "[ ]"],
        ["6. Final Inspection", "Sign-off with site contact", "[ ]"],
    ],
    [4.8, 8.2, 3.0],
)

doc.add_paragraph().paragraph_format.space_after = Pt(4)
h2(doc, "What Is Expected From You")
from core.quote_document import balance_percent, deposit_percent  # noqa: E402
bullet(doc, f"A deposit of {deposit_percent()}% is required on confirmation of order, "
            f"{balance_percent()}% balance on completion")
bullet(doc, "Confirmation of order is a signed quotation and deposit sent to FacilitiesCo")
bullet(doc, "The price on the quotation is all-inclusive \u2014 VAT is not applicable")
bullet(doc, "Site access arranged for inspection, installation, and final sign-off")

page_break(doc)

# ============================================================
# PAGE 3 — SITE INSPECTION (compact photo grid, one page)
# ============================================================
h1(doc, "Site Inspection")
body(doc, "Area: [SITE / AREA NAME]", bold=True, size=12, color=CHARCOAL, space_after=8)

photo_grid(doc, count=8, cols=4)
doc.add_paragraph().paragraph_format.space_after = Pt(4)

h2(doc, "Net Replacement")
styled_table(
    doc,
    ["Description", "Quantity"],
    [["Two Car Nets (Double)", "[ ]"], ["Three Car Nets (Triple)", "[ ]"]],
    [11.0, 5.0],
)

doc.add_paragraph().paragraph_format.space_after = Pt(4)
h2(doc, "Painting Requirements")
styled_table(
    doc,
    ["Painting Level", "Number of Structures"],
    [
        ["Light", "[ ]"],
        ["Medium", "[ ]"],
        ["Full", "[ ]"],
    ],
    [11.0, 5.0],
)

doc.add_paragraph().paragraph_format.space_after = Pt(4)
h2(doc, "Material Notes")
bullet(doc, "Netting Type: 80% UV Block \u2610   90% UV Block \u2610")
bullet(doc, "Colour: [COLOUR]  \u00b7  All nets secured with galvanised fixings")
bullet(doc, "Tensioned to fit per structure spec, using 5mm 6x19 fibre core galvanised cable")

page_break(doc)

h1(doc, "Additional Site Photos")
body(
    doc,
    "Optional -- delete this page if 8 photos were enough. Duplicate the grid "
    "below (copy a row, paste) for more than 16 in total.",
    italic=True, color=GREY, space_after=12,
)
photo_grid(doc, count=8, cols=4)

page_break(doc)

# ============================================================
# PAGE 4 — TECHNICAL SPECIFICATIONS
# ============================================================
h1(doc, "Technical Specifications")

h2(doc, "Structural Steel")
bullet(doc, "Cantilever \u2014 Anchor Poles: 152mm / 165mm round tubing (3mm wall thickness)")
bullet(doc, "Cantilever \u2014 Main Frame: 50mm / 57mm round tubing (2mm wall thickness)")
bullet(doc, "Four Post \u2014 Anchor Poles: 76mm / 101mm round tubing (3mm wall thickness)")
bullet(doc, "Four Post \u2014 Main Frame: 50mm round tubing (2mm wall thickness)")
bullet(doc, "Foundations: 600mm\u2013800mm deep pole planting, secured with ready-mix concrete")
bullet(doc, "Designed for high wind conditions (120\u2013140 km/h when correctly installed)")

h2(doc, "Shade Netting")
bullet(doc, "Knittex Z25 UV-stabilised shade netting")
bullet(doc, "High durability and tear resistance, wide range of colours available")

h2(doc, "Cable Tensioning System (Certified)")
bullet(doc, "5mm 6x19 Fibre Core Galvanised Steel Cable, secured with Crosby clamps")
bullet(doc, "Breaking Load: 13.6 kN (\u2248 1,385 kg)  \u00b7  Tested Breaking Load: 14.3 kN")

h2(doc, "Stitching & Thread \u2014 Coats Dabond AWF")
bullet(doc, "Bonded, twisted continuous filament polyester thread with a PFC-free anti-wick finish")
bullet(doc, "Blocks water migrating through stitched seams for genuinely water-repellent stitching")
bullet(doc, "Excellent bleach, mildew and rot resistance for long-term outdoor exposure")
bullet(doc, "Tex 80 (5,700 cN) for standard seams, Tex 135 (9,310 cN) for heavy-duty seams")

page_break(doc)

# ============================================================
# PAGE 5 — WHY INVEST
# ============================================================
h1(doc, "Why Invest in Shade Structures")

pairs = [
    ("Protection", "Protect yourself and valuable assets from UV sun rays and hail."),
    ("Warranty", "8-year manufacturer's warranty on shade netting, guaranteed against defective materials and workmanship."),
    ("Flexible Design", "Structures can be adjoined, back-to-back, side-by-side, or built to custom shapes and sizes."),
    ("Wide Application", "Residential parking bays, outdoor entertaining areas, playgrounds, nurseries and gardening venues."),
    ("Sustainability", "Re-netting and repairs to existing structures and netting extend service life without a full rebuild."),
    ("Structure Choice", "Four options to suit the site: Standard Four-Post, Semi-Cantilevered, Full Cantilevered, or Shade Sails."),
    ("Build Quality", "All-steel construction on the framework, with netting made to measure for each individual structure."),
    ("After-Sales", "Complete after-sales service and support for the life of the structure."),
]
for title, desc in pairs:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run(title)
    set_font(r, size=11, color=GREEN, bold=True)
    body(doc, desc, space_after=10)

page_break(doc)

# ============================================================
# PAGE 6 — TYPES OF STRUCTURES
# ============================================================
h1(doc, "Types of Structures")

h2(doc, "Four Post / Standard")
body(
    doc,
    "Four steel posts anchor the structure, one on each corner. Four hoops complete the "
    "structural element, rolled to create a dome effect. Suits any parking or outdoor "
    "area needing shade \u2014 over playgrounds, pools, grandstands, picnic areas and campsites.",
    space_after=8,
)
styled_table(doc, ["Size", "Dimensions"], [["Single", "3m x 5m"], ["Double", "5m x 5m"], ["Triple", "7.5m x 5m"]], [11.0, 5.0])

doc.add_paragraph().paragraph_format.space_after = Pt(6)
h2(doc, "Cantilever")
body(
    doc,
    "The structure extends from a wall or post, to which it must be firmly attached \u2014 "
    "substantial engineering and proper load calculations for a genuinely dramatic effect. "
    "Two upright columns at the back allow total access when turning into the bay.",
    space_after=8,
)
styled_table(doc, ["Size", "Dimensions"], [["Single", "3m x 5m"], ["Double", "5m x 5m"], ["Triple", "7.5m x 5m"]], [11.0, 5.0])

doc.add_paragraph().paragraph_format.space_after = Pt(6)
h2(doc, "Shade Sail")
body(
    doc,
    "Tensioned fabric stretched between fixing points \u2014 wall brackets, poles, or a "
    "combination of both. A flexible option for irregular areas where a post-and-hoop "
    "structure isn't practical.",
    space_after=8,
)

page_break(doc)

# ============================================================
# PAGE 7 — CLIENTS (logo grid, one page)
# ============================================================
h1(doc, "Our Clients")
body(doc, "A few of the businesses we've worked with:", space_after=14)

all_client_cells = list(CLIENT_LOGOS.items()) + [(name, None) for name in CLIENTS_NO_LOGO]
cols = 3
rows_needed = (len(all_client_cells) + cols - 1) // cols
ctable = doc.add_table(rows=rows_needed, cols=cols)
ctable.alignment = WD_TABLE_ALIGNMENT.CENTER
idx = 0
for r in range(rows_needed):
    set_row_height(ctable.rows[r], 2.6)
    for c in range(cols):
        cell = ctable.rows[r].cells[c]
        cell.width = Cm(5.6)
        cell_border(cell, style="single", color="E5E5E5", size=4)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        if idx < len(all_client_cells):
            name, logo_path = all_client_cells[idx]
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if logo_path and os.path.exists(logo_path):
                run = p.add_run()
                run.add_picture(logo_path, width=Cm(3.6))
            else:
                r1 = p.add_run(name)
                set_font(r1, size=9.5, color=GREY, italic=True)
        idx += 1

page_break(doc)

# ============================================================
# PAGE 8 — THANK YOU / CONTACT (with social + WhatsApp)
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
r = p.add_run("Minette Liebenberg")
set_font(r, size=12.5, color=CHARCOAL, bold=True)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Director, Shade Solutions by FacilitiesCo")
set_font(r, size=10, color=GREY)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("minette@facilitiesco.com  \u00b7  083 378 5122")
set_font(r, size=10, color=GREY)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("sales@facilitiesco.com  \u00b7  010 015 0532")
set_font(r, size=10, color=GREY)

doc.add_paragraph().paragraph_format.space_after = Pt(10)

# Real pictogram icons (camera/f/play/in), same handle @facilitiesco
# on every platform.
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
for icon_name in ["instagram", "facebook", "youtube", "linkedin"]:
    run = p.add_run()
    run.add_picture(str(ICON_DIR / f"icon_{icon_name}.png"), width=Cm(0.9))
    p.add_run("   ")

doc.add_paragraph().paragraph_format.space_after = Pt(8)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
icons = [
    ("\U0001F310", "www.facilitiesco.com"),
    ("", "@facilitiesco"),
]
for i, (icon, label) in enumerate(icons):
    r1 = p.add_run(f"{icon} {label}".strip())
    set_font(r1, size=9, color=GREY)
    if i < len(icons) - 1:
        r2 = p.add_run("    \u00b7    ")
        set_font(r2, size=9, color=LIGHTGREY)

out_path = os.path.join(DOCS_DIR, "FacilitiesCo_Proposal_Template_A4.docx")
doc.save(out_path)
print("saved:", out_path)
