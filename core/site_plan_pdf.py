# ==========================================================
# FC Hub - Site Plan PDF
# ----------------------------------------------------------
# Purpose:
# Export a Site Plan - the backdrop plus every structure drawn on
# it - as a LANDSCAPE PDF she can send or take to site. Asked for
# 2026-08-12, alongside the landscape grid template: her sites are
# car parks, which are wide rather than tall, so a portrait page
# wastes most of the sheet.
#
# Structures are drawn as real rotated polygons (see
# core/site_plan_geometry.py), so the printed plan matches what she
# drew on screen, angles and all.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from pathlib import Path

from PIL import Image as PILImage, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.document_pdf import (
    ACCENT_COLOR,
    BODY_FONT,
    BOLD_FONT,
    BUSINESS_LOCALITY,
    FOOTER_HEIGHT,
    GREY_COLOR,
    INK_COLOR,
    PAGE_MARGIN,
    RULE_COLOR,
    draw_page_frame,
)
from core.app_paths import get_assets_dir
from core.site_plan_geometry import rotated_corners
from core.structure_catalog import size_label_for

LOGO_PATH = get_assets_dir() / "logo_placeholder.png"

# Printed on white, so a stronger blue than the canvas's #4FC3F7.
STRUCTURE_OUTLINE = (21, 101, 192)
STRUCTURE_LABEL = (13, 71, 161)

# Enough resolution to stay crisp across a landscape A4 without
# producing a needlessly enormous PDF.
RENDER_WIDTH_PX = 2000


def render_plan_image(backdrop_path, items, render_width=RENDER_WIDTH_PX):
    """Draw the backdrop with every structure on it, as a PIL image.

    Structures are stored as fractions of the backdrop, so this works
    at any resolution - the printed page just uses a bigger one than
    the screen."""

    backdrop = PILImage.open(backdrop_path).convert("RGB")

    scale = render_width / backdrop.width
    width = max(1, round(backdrop.width * scale))
    height = max(1, round(backdrop.height * scale))
    canvas = backdrop.resize((width, height), PILImage.Resampling.LANCZOS)

    draw = ImageDraw.Draw(canvas)
    line_width = max(2, round(width / 500))

    try:
        font = ImageFont.truetype("arial.ttf", max(12, round(width / 90)))
    except Exception:
        font = ImageFont.load_default()

    for item in items:
        item_width = item.width * width
        item_height = item.height * height
        centre_x = (item.x + item.width / 2) * width
        centre_y = (item.y + item.height / 2) * height

        corners = rotated_corners(centre_x, centre_y, item_width, item_height, item.rotation)
        draw.polygon(corners, outline=STRUCTURE_OUTLINE, width=line_width)

        label = item.structure_type or "(untitled)"
        draw.text((corners[0][0] + 4, corners[0][1] + 4), label, fill=STRUCTURE_LABEL, font=font)

    return canvas


def _size_text(item):
    """Blank rather than "N/A" for a structure with no size - this is a
    drawing schedule, not a form to be filled in."""

    label = size_label_for(item.structure_type, item.car_bays) or ""
    return "" if label.strip().upper() in ("N/A", "NA") else label


def generate_site_plan_pdf(plan, items, customer, site, business_settings, output_path, backdrop_path):
    """One landscape page: the plan itself, plus a list of what is on
    it. Deliberately no prices - this is the drawing, not the quote."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    page_size = landscape(A4)
    page_width, _page_height = page_size

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PlanTitle", parent=styles["Heading1"], textColor=INK_COLOR,
        fontSize=20, leading=22, spaceAfter=0, fontName=BOLD_FONT,
    )
    business_style = ParagraphStyle(
        "Business", parent=styles["Normal"], fontSize=9, leading=12,
        textColor=INK_COLOR, fontName=BODY_FONT, alignment=2,
    )
    meta_style = ParagraphStyle(
        "Meta", parent=styles["Normal"], fontSize=9, leading=12,
        textColor=GREY_COLOR, fontName=BODY_FONT,
    )
    cell_style = ParagraphStyle(
        "Cell", parent=styles["Normal"], fontSize=8.5, leading=11,
        textColor=INK_COLOR, fontName=BODY_FONT,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        topMargin=10 * mm,
        bottomMargin=FOOTER_HEIGHT + 8 * mm,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
    )

    story = []

    logo_cell = ""
    if LOGO_PATH.is_file():
        logo = Image(str(LOGO_PATH))
        logo._restrictSize(60 * mm, 15 * mm)
        logo_cell = logo

    business_lines = [f"<b>{business_settings.trading_name}</b>"] + ([BUSINESS_LOCALITY] if BUSINESS_LOCALITY else [])
    for value in (business_settings.email, business_settings.phone, business_settings.website):
        if value:
            business_lines.append(value)

    usable_width = page_width - 2 * PAGE_MARGIN
    header = Table(
        [[logo_cell, Paragraph("<br/>".join(business_lines), business_style)]],
        colWidths=[usable_width * 0.55, usable_width * 0.45],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(header)

    story.append(Paragraph("Site Plan", title_style))
    site_name = site.name if site is not None and site.name else "Unnamed Site"
    story.append(Paragraph(f"{customer.name} &nbsp;|&nbsp; {site_name}", meta_style))
    story.append(Spacer(1, 5 * mm))

    # --- the plan itself ---
    # The drawing is the point of a landscape export, so it gets the
    # rest of page one rather than being squeezed above a table. On a
    # landscape A4 the header, title and footer leave roughly 120mm of
    # height, and the grid's aspect means a full-page-width plan would
    # need ~185mm - so height, not width, is always the limit here.
    if backdrop_path is not None and Path(backdrop_path).is_file():
        plan_image = render_plan_image(backdrop_path, items)

        available_height = 118 * mm
        aspect = plan_image.height / plan_image.width
        draw_width = usable_width
        draw_height = draw_width * aspect
        if draw_height > available_height:
            draw_height = available_height
            draw_width = draw_height / aspect

        temporary = output_path.with_suffix(".plan.png")
        plan_image.save(temporary)
        story.append(Image(str(temporary), width=draw_width, height=draw_height))
    else:
        temporary = None
        story.append(Paragraph("No backdrop image available for this plan.", meta_style))

    # --- what is on it ---
    # Its own page, so a long site never pushes the drawing around and
    # a single extra structure never half-spills onto a second page.
    if items:
        story.append(PageBreak())
        story.append(Paragraph("Structures", title_style))
        story.append(Paragraph(f"{customer.name} &nbsp;|&nbsp; {site_name}", meta_style))
        story.append(Spacer(1, 5 * mm))
    else:
        story.append(Spacer(1, 5 * mm))
    rows = [["#", "Structure", "Size", "Description", "Qty"]]
    for index, item in enumerate(items, start=1):
        rows.append([
            str(index),
            Paragraph(item.structure_type or "(untitled)", cell_style),
            Paragraph(_size_text(item), cell_style),
            Paragraph(item.description or "", cell_style),
            f"{item.quantity:g}",
        ])
    if len(rows) == 1:
        rows.append(["", Paragraph("No structures drawn yet.", cell_style), "", "", ""])

    table = Table(
        rows,
        colWidths=[10 * mm, 45 * mm, 32 * mm, usable_width - 117 * mm, 30 * mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)

    def on_page(canvas, document):
        draw_page_frame(canvas, document, business_settings)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)

    # The rendered plan is only needed while the document is building.
    if temporary is not None and Path(temporary).is_file():
        try:
            Path(temporary).unlink()
        except OSError:
            pass

    return output_path
