# ==========================================================
# FC Hub - Quote PDF
# ----------------------------------------------------------
# Purpose:
# Render a Quote as a branded PDF: logo, business details,
# customer/site, line items, totals, payment terms, banking.
#
# Author: Minette & James
# Version: 2.0
# ==========================================================

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.app_paths import get_assets_dir
from core.document_pdf import (
    ACCENT_COLOR,
    ACCENT_TINT,
    BODY_FONT,
    BUSINESS_LOCALITY,
    BOLD_FONT,
    FOOTER_HEIGHT,
    GREY_COLOR,
    INK_COLOR,
    PAGE_MARGIN,
    PROOF_OF_PAYMENT_NOTE,
    RULE_COLOR,
    draw_page_frame,
)
from core.quote import format_quote_number


LOGO_PATH = get_assets_dir() / "logo_placeholder.png"



def format_money(minor_units, currency="ZAR"):

    symbol = "R" if currency == "ZAR" else currency + " "
    return f"{symbol}{minor_units / 100:,.2f}"


def push_down_spacer_mm(row_count, baseline_rows=3, max_push_mm=45, min_push_mm=10):
    """Height (in mm) of the spacer between the items table and the
    Totals/Payment Terms/Banking block, so that block sits low on the
    page near the footer instead of right under a short items table -
    Minette asked for the blank space to live in the middle of the
    page, not scattered between sections. Shrinks as the item count
    grows so a longer quote doesn't get pushed onto a second page."""

    shrink = max(0, row_count - baseline_rows) * 9
    return max(min_push_mm, max_push_mm - shrink)


def _filler_row_count(story, tail, build_items_table, width, height, safety_mm=4):
    """How many empty ruled rows fit before the tail would spill onto a
    second page. 0 if the quote already fills (or overflows) page 1."""

    def total_height(flowables):
        return sum(
            f.wrap(width, height)[1] + f.getSpaceBefore() + f.getSpaceAfter()
            for f in flowables
        )

    height -= 12  # SimpleDocTemplate frame padding (6pt top + 6pt bottom)
    used = total_height(story) + total_height(tail)
    if used >= height:
        return 0
    base = build_items_table(0).wrap(width, height)[1]
    row_height = build_items_table(1).wrap(width, height)[1] - base
    if row_height <= 0:
        return 0
    return max(0, int((height - used - safety_mm * mm) // row_height))


def resolved_or_tbc(value):
    """PO Number / VAT No are permanent fields on the PDF meta block -
    Minette wants a visible, deliberate value there (an actual number,
    N/A, or TBC) rather than the row silently disappearing when blank."""

    value = (value or "").strip()
    return value if value else "TBC"


def format_line_item_description(item):
    """The line's own description; falls back to its item type name."""

    if (item.description or "").strip():
        return item.description.strip()
    return (item.structure_type or "").strip() or "Item"


def format_address_lines(address):
    """Non-empty display lines for a structured Address (Billing,
    Delivery, Site, ...), or [] if there's nothing to show."""

    if address is None:
        return []
    lines = []
    if address.line1:
        lines.append(address.line1)
    if address.line2:
        lines.append(address.line2)
    city_line = ", ".join(part for part in (address.city, address.province) if part)
    if address.postal_code:
        city_line = f"{city_line} {address.postal_code}".strip()
    if city_line:
        lines.append(city_line)
    if address.country:
        lines.append(address.country)
    return lines


def generate_quote_pdf(quote, line_items, customer, site, business_settings, output_path, billing_address=None, site_address=None, delivery_address=None, postal_address=None, contact_name=None):

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("QuoteTitle", parent=styles["Heading1"], textColor=INK_COLOR, fontSize=22, leading=24, spaceAfter=0, fontName=BOLD_FONT)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], textColor=ACCENT_COLOR, fontSize=8, leading=10, spaceAfter=3)
    label_style.fontName = BOLD_FONT
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14, textColor=INK_COLOR, fontName=BODY_FONT)
    business_style = ParagraphStyle("Business", parent=body_style, alignment=2)  # TA_RIGHT
    meta_label_style = ParagraphStyle("MetaLabel", parent=styles["Normal"], fontSize=8.5, textColor=GREY_COLOR, fontName=BODY_FONT)
    meta_value_style = ParagraphStyle("MetaValue", parent=styles["Normal"], fontSize=8.5, textColor=INK_COLOR, fontName=BOLD_FONT)
    fine_style = ParagraphStyle("Fine", parent=styles["Normal"], fontSize=7.5, leading=9.8, textColor=GREY_COLOR, fontName=BODY_FONT)
    bank_label_style = ParagraphStyle("BankLabel", parent=styles["Normal"], textColor=ACCENT_COLOR, fontSize=7, leading=9, fontName=BOLD_FONT)
    bank_body_style = ParagraphStyle("BankBody", parent=styles["Normal"], fontSize=8, leading=10.5, textColor=INK_COLOR, fontName=BODY_FONT)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=10 * mm,
        bottomMargin=FOOTER_HEIGHT + 8 * mm,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
    )

    story = []

    # --- Header: logo left, business contact block right ---
    logo_cell = ""
    if LOGO_PATH.is_file():
        logo = Image(str(LOGO_PATH))
        logo._restrictSize(65 * mm, 16 * mm)
        logo_cell = logo

    business_lines = [f"<b>{business_settings.trading_name}</b>"] + ([BUSINESS_LOCALITY] if BUSINESS_LOCALITY else [])
    for value in (business_settings.email, business_settings.phone, business_settings.website):
        if value:
            business_lines.append(value)
    business_cell = Paragraph("<br/>".join(business_lines), business_style)

    header_table = Table([[logo_cell, business_cell]], colWidths=[100 * mm, 82 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        # Kill the default cell padding on the outer edges so the logo and the
        # business block sit flush with the green rule and the tables below,
        # rather than inset by 6pt.
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 3 * mm))

    rule_table = Table([[""]], colWidths=[182 * mm], rowHeights=[1.4])
    rule_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_COLOR)]))
    story.append(rule_table)
    story.append(Spacer(1, 5 * mm))

    # --- Title + meta, and Bill To, side by side ---
    to_lines = [f"<b>{quote.bill_to_name or customer.name}</b>"]
    if contact_name:
        to_lines.append(contact_name)
    if customer.email:
        to_lines.append(customer.email)
    if customer.phone:
        to_lines.append(customer.phone)
    to_lines.extend(format_address_lines(billing_address))
    if delivery_address is not None:
        delivery_lines = format_address_lines(delivery_address)
        if delivery_lines:
            to_lines.append("Delivery:")
            to_lines.extend(delivery_lines)
    if postal_address is not None:
        postal_lines = format_address_lines(postal_address)
        if postal_lines:
            to_lines.append("Postal:")
            to_lines.extend(postal_lines)
    if site is not None:
        to_lines.append(f"Site: {site.name}")
        to_lines.extend(format_address_lines(site_address))

    left_cell_content = [
        Paragraph("QUOTATION", title_style),
        Spacer(1, 6 * mm),
        Paragraph("BILL TO", label_style),
        Paragraph("<br/>".join(to_lines), body_style),
    ]

    meta_rows = [
        [Paragraph("QUOTE #", meta_label_style), Paragraph(format_quote_number(quote), meta_value_style)],
        [Paragraph("DATE", meta_label_style), Paragraph(quote.issue_date or "—", meta_value_style)],
        [Paragraph("VALID UNTIL", meta_label_style), Paragraph(quote.expiry_date or "—", meta_value_style)],
        [Paragraph("PO NUMBER", meta_label_style), Paragraph(resolved_or_tbc(quote.po_number), meta_value_style)],
        [Paragraph("VAT NO", meta_label_style), Paragraph(resolved_or_tbc(quote.vat_number), meta_value_style)],
        [Paragraph("REG NO", meta_label_style), Paragraph(resolved_or_tbc(quote.registration_number), meta_value_style)],
    ]
    meta_table = Table(meta_rows, colWidths=[26 * mm, 36 * mm])
    meta_table.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    # Push down to line up with "BILL TO" instead of the QUOTATION title -
    # matches the height of the title + the spacer above BILL TO.
    right_cell_content = [Spacer(1, 14.5 * mm), meta_table]

    layout_table = Table([[left_cell_content, right_cell_content]], colWidths=[118 * mm, 64 * mm])
    layout_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(layout_table)
    story.append(Spacer(1, 10 * mm))

    # --- Line items ---
    table_data = [["Description", "Qty", "Unit Price", "Amount"]]
    for item in line_items:
        table_data.append([
            Paragraph(format_line_item_description(item), body_style),
            f"{item.quantity:g}",
            format_money(item.unit_price_minor, quote.currency),
            format_money(item.amount_minor, quote.currency),
        ])

    if not line_items:
        table_data.append(["No line items yet.", "", "", ""])

    def build_items_table(filler_rows):
        data = table_data + [["", "", "", ""]] * filler_rows
        table = Table(data, colWidths=[102 * mm, 18 * mm, 30 * mm, 32 * mm], repeatRows=1)
        table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), BODY_FONT),
        ("FONTSIZE", (0, 1), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return table

    items_index = len(story)
    story.append(build_items_table(0))

    # --- Totals, right-aligned, total row tinted ---
    totals_data = [["Subtotal", format_money(quote.subtotal_minor, quote.currency)]]
    if quote.vat_minor:
        totals_data.append(["VAT", format_money(quote.vat_minor, quote.currency)])
    totals_data.append(["Total", format_money(quote.total_minor, quote.currency)])

    totals_table = Table(totals_data, colWidths=[35 * mm, 35 * mm], hAlign="RIGHT")
    total_row = len(totals_data) - 1
    totals_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), BODY_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK_COLOR),
        ("FONTNAME", (0, total_row), (-1, total_row), BOLD_FONT),
        ("FONTSIZE", (0, total_row), (-1, total_row), 12),
        ("BACKGROUND", (0, total_row), (-1, total_row), ACCENT_TINT),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEABOVE", (0, total_row), (-1, total_row), 0.8, ACCENT_COLOR),
    ]))
    tail = [totals_table, Spacer(1, 6 * mm)]

    if quote.notes:
        tail.append(Paragraph("NOTES", label_style))
        tail.append(Paragraph(quote.notes, body_style))
        tail.append(Spacer(1, 3 * mm))

    # --- Single box just above the footer: banking details (highlighted green)
    # stacked over the payment terms and contract wording.
    #
    # The wording below is Minette's approved contract text (rewrite signed off
    # 2026-08-03, replacing the longer wording carried over from the 2026 Estimate
    # spreadsheets). It is contract-forming: acceptance by conduct plus the
    # entire-agreement clause. Do not paraphrase or shorten it without her
    # sign-off - an earlier attempt to "tighten" it silently dropped the
    # entire-agreement sentence. See memory: document_footer_wording.
    #
    # Note: clients in practice almost never return a signed copy, so the
    # "confirming by email, or paying the deposit constitutes acceptance" limb is
    # the one doing the real work - keep it.
    box_rows = []
    banking_row_index = None

    if business_settings.bank_name:
        banking_text = (
            f"<b>{business_settings.bank_name}</b> — {business_settings.bank_account_name}"
            f"  |  Acc: {business_settings.bank_account_number}"
            f"  |  Branch: {business_settings.branch_code}"
        )
        if business_settings.swift_code:
            banking_text += f"  |  Swift: {business_settings.swift_code}"
        banking_row_index = len(box_rows)
        box_rows.append([[
            Paragraph("BANKING DETAILS", bank_label_style),
            Paragraph(banking_text, bank_body_style),
        ]])

    fine_lines = []
    if quote.deposit_percentage is not None:
        fine_lines.append(
            f"<b>Acceptance &amp; Deposit.</b> To proceed, please return this quotation signed, together "
            f"with a {quote.deposit_percentage:g}% deposit; the {quote.balance_percentage:g}% balance is "
            "payable on completion. Signing, confirming by email, or paying the deposit constitutes "
            "acceptance of this quotation and of our Terms &amp; Conditions, which together form the "
            "entire agreement between the parties. "
            + (
                f"Please send the signed quotation and proof of payment to {business_settings.email.strip()}."
                if (business_settings.email or "").strip()
                else "Please send us the signed quotation and proof of payment."
            )
        )
    fine_lines.append(
        "<b>Scope &amp; Pricing.</b> Work is carried out strictly per this quotation. Variations and "
        "out-of-scope work will be quoted and charged separately. Prices are subject to change."
    )
    box_rows.append([Paragraph("<br/>".join(fine_lines), fine_style)])

    terms_box = Table(box_rows, colWidths=[182 * mm])
    box_style = [
        ("BOX", (0, 0), (-1, -1), 0.7, ACCENT_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if banking_row_index is not None:
        box_style.append(("BACKGROUND", (0, banking_row_index), (-1, banking_row_index), ACCENT_TINT))
        box_style.append(("LINEBELOW", (0, banking_row_index), (-1, banking_row_index), 0.5, ACCENT_COLOR))
    terms_box.setStyle(TableStyle(box_style))
    tail.append(terms_box)
    # Pad the items table with empty ruled rows so the totals + terms box
    # sit at the bottom of page 1 - no blank gap (Minette, 2026-09-22).
    story[items_index] = build_items_table(
        _filler_row_count(story, tail, build_items_table, doc.width, doc.height)
    )
    story.extend(tail)

    doc.build(story, onFirstPage=lambda c, d: draw_page_frame(c, d, business_settings), onLaterPages=lambda c, d: draw_page_frame(c, d, business_settings))

    return output_path
