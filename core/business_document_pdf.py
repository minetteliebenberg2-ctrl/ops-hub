# ==========================================================
# FC Hub - Pro-Forma / Tax Invoice / Statement PDFs
# ----------------------------------------------------------
# Purpose:
# Render Pro-Forma, Tax Invoice, and Statement documents with the
# same branding as generate_quote_pdf (core/quote_pdf.py), the last
# three steps of the Quote -> Pro-Forma -> Tax Invoice -> Statement
# flow. Pro-Forma/Tax Invoice reuse the issued quote's line items;
# Statement lists the customer's Tax Invoices for a period.
#
# Author: Minette & James
# Version: 1.0
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
from core.quote_document import PRO_FORMA, TAX_INVOICE
from core.quote_pdf import format_address_lines, format_line_item_description, format_money, push_down_spacer_mm, resolved_or_tbc


LOGO_PATH = get_assets_dir() / "logo_placeholder.png"

DOCUMENT_TITLES = {
    PRO_FORMA: "PRO FORMA INVOICE",
    TAX_INVOICE: "TAX INVOICE",
}


def _styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("DocTitle", parent=styles["Heading1"], textColor=INK_COLOR, fontSize=22, leading=24, spaceAfter=0, fontName=BOLD_FONT),
        "label": ParagraphStyle("Label", parent=styles["Normal"], textColor=ACCENT_COLOR, fontSize=8, leading=10, spaceAfter=3, fontName=BOLD_FONT),
        "body": ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14, textColor=INK_COLOR, fontName=BODY_FONT),
        "business": ParagraphStyle("Business", parent=styles["Normal"], fontSize=10, leading=14, textColor=INK_COLOR, alignment=2, fontName=BODY_FONT),
        "meta_label": ParagraphStyle("MetaLabel", parent=styles["Normal"], fontSize=8.5, textColor=GREY_COLOR, fontName=BODY_FONT),
        "meta_value": ParagraphStyle("MetaValue", parent=styles["Normal"], fontSize=8.5, textColor=INK_COLOR, fontName=BOLD_FONT),
        "small": ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=11, textColor=GREY_COLOR, fontName=BODY_FONT),
        "fine": ParagraphStyle("Fine", parent=styles["Normal"], fontSize=7.5, leading=9.8, textColor=GREY_COLOR, fontName=BODY_FONT),
        "bank_label": ParagraphStyle("BankLabel", parent=styles["Normal"], textColor=ACCENT_COLOR, fontSize=7, leading=9, fontName=BOLD_FONT),
        "bank_body": ParagraphStyle("BankBody", parent=styles["Normal"], fontSize=8, leading=10.5, textColor=INK_COLOR, fontName=BODY_FONT),
    }


def _header_and_rule(story, business_settings, styles):
    logo_cell = ""
    if LOGO_PATH.is_file():
        logo = Image(str(LOGO_PATH))
        logo._restrictSize(65 * mm, 16 * mm)
        logo_cell = logo

    business_lines = [f"<b>{business_settings.trading_name}</b>", BUSINESS_LOCALITY]
    for value in (business_settings.email, business_settings.phone, business_settings.website):
        if value:
            business_lines.append(value)
    business_cell = Paragraph("<br/>".join(business_lines), styles["business"])

    header_table = Table([[logo_cell, business_cell]], colWidths=[100 * mm, 82 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        # Flush with the green rule and the tables below, not inset by 6pt.
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 5 * mm))

    rule_table = Table([[""]], colWidths=[182 * mm], rowHeights=[1.4])
    rule_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_COLOR)]))
    story.append(rule_table)
    story.append(Spacer(1, 8 * mm))


def _terms_box(business_settings, styles, fine_lines):
    """The single box that sits just above the footer on every document type:
    banking details highlighted in the accent tint, with the document's own
    fine print underneath. Shared so Pro-Forma, Tax Invoice and Statement can
    never drift apart visually."""

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
            Paragraph("BANKING DETAILS", styles["bank_label"]),
            Paragraph(banking_text, styles["bank_body"]),
        ]])

    box_rows.append([Paragraph("<br/>".join(fine_lines), styles["fine"])])

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
    return terms_box


def _totals_table(quote):
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
    return totals_table


def generate_proforma_pdf(document, quote, line_items, customer, site, business_settings, output_path, billing_address=None, site_address=None, delivery_address=None, postal_address=None, contact_name=None):
    return _generate_quote_derived_pdf(
        PRO_FORMA, document, quote, line_items, customer, site, business_settings, output_path,
        billing_address=billing_address, site_address=site_address, delivery_address=delivery_address, postal_address=postal_address, contact_name=contact_name,
    )


def generate_invoice_pdf(document, quote, line_items, customer, site, business_settings, output_path, billing_address=None, site_address=None, delivery_address=None, postal_address=None, contact_name=None, deposit_document=None):
    """Tax Invoice. document.invoice_part selects the variant:
    '' = normal, 'deposit' = one '65% deposit on <quote>' line,
    'balance' = all quote items + full total, less the deposit invoice,
    balance due. deposit_document names the deposit on a balance invoice."""
    return _generate_quote_derived_pdf(
        TAX_INVOICE, document, quote, line_items, customer, site, business_settings, output_path,
        billing_address=billing_address, site_address=site_address, delivery_address=delivery_address, postal_address=postal_address, contact_name=contact_name,
        deposit_document=deposit_document,
    )


def _split_totals_table(rows, bold_row):
    table = Table(rows, colWidths=[70 * mm, 35 * mm], hAlign="RIGHT")
    table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), BODY_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK_COLOR),
        ("FONTNAME", (0, bold_row), (-1, bold_row), BOLD_FONT),
        ("FONTSIZE", (0, bold_row), (-1, bold_row), 12),
        ("BACKGROUND", (0, bold_row), (-1, bold_row), ACCENT_TINT),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEABOVE", (0, bold_row), (-1, bold_row), 0.8, ACCENT_COLOR),
    ]))
    return table


def _generate_quote_derived_pdf(doc_type, document, quote, line_items, customer, site, business_settings, output_path, billing_address=None, site_address=None, delivery_address=None, postal_address=None, contact_name=None, deposit_document=None):

    invoice_part = getattr(document, "invoice_part", "") or ""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=10 * mm,
        bottomMargin=FOOTER_HEIGHT + 8 * mm,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
    )

    story = []
    _header_and_rule(story, business_settings, styles)

    to_lines = [f"<b>{document.bill_to_name or customer.name}</b>"]
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
        Paragraph(DOCUMENT_TITLES[doc_type], styles["title"]),
        Spacer(1, 6 * mm),
        Paragraph("BILL TO", styles["label"]),
        Paragraph("<br/>".join(to_lines), styles["body"]),
    ]

    meta_rows = [
        [Paragraph(f"{doc_type.upper()} #", styles["meta_label"]), Paragraph(document.document_number, styles["meta_value"])],
        [Paragraph("DATE", styles["meta_label"]), Paragraph(document.issue_date or "—", styles["meta_value"])],
        [Paragraph("QUOTE REF", styles["meta_label"]), Paragraph(format_quote_number(quote), styles["meta_value"])],
    ]
    if doc_type == TAX_INVOICE:
        meta_rows.append([Paragraph("DUE DATE", styles["meta_label"]), Paragraph(document.due_date or "—", styles["meta_value"])])
    meta_rows.append([Paragraph("PO NUMBER", styles["meta_label"]), Paragraph(resolved_or_tbc(document.po_number), styles["meta_value"])])
    meta_rows.append([Paragraph("VAT NO", styles["meta_label"]), Paragraph(resolved_or_tbc(document.vat_number), styles["meta_value"])])
    meta_rows.append([Paragraph("REG NO", styles["meta_label"]), Paragraph(resolved_or_tbc(document.registration_number), styles["meta_value"])])

    meta_table = Table(meta_rows, colWidths=[26 * mm, 36 * mm])
    meta_table.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))

    layout_table = Table([[left_cell_content, [meta_table]]], colWidths=[118 * mm, 64 * mm])
    layout_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(layout_table)
    story.append(Spacer(1, 10 * mm))

    table_data = [["Description", "Qty", "Unit Price", "Amount"]]
    if invoice_part == "deposit":
        table_data.append([
            Paragraph(f"65% deposit on {format_quote_number(quote)}", styles["body"]),
            "1",
            format_money(document.total_minor, quote.currency),
            format_money(document.total_minor, quote.currency),
        ])
        shown_rows = 1
    else:
        for item in line_items:
            table_data.append([
                Paragraph(format_line_item_description(item), styles["body"]),
                f"{item.quantity:g}",
                format_money(item.unit_price_minor, quote.currency),
                format_money(item.amount_minor, quote.currency),
            ])
        shown_rows = len(line_items)

    items_table = Table(table_data, colWidths=[102 * mm, 18 * mm, 30 * mm, 32 * mm], repeatRows=1)
    items_table.setStyle(TableStyle([
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
    story.append(items_table)
    story.append(Spacer(1, push_down_spacer_mm(shown_rows) * mm))

    if invoice_part == "deposit":
        rows = []
        if document.vat_minor:
            rows.append(["Subtotal", format_money(document.subtotal_minor, quote.currency)])
            rows.append(["VAT", format_money(document.vat_minor, quote.currency)])
        rows.append(["Deposit due", format_money(document.total_minor, quote.currency)])
        totals = _split_totals_table(rows, len(rows) - 1)
    elif invoice_part == "balance":
        deposit_minor = deposit_document.total_minor if deposit_document is not None else quote.total_minor - document.total_minor
        deposit_ref = deposit_document.document_number if deposit_document is not None else "deposit"
        rows = [["Subtotal", format_money(quote.subtotal_minor, quote.currency)]]
        if quote.vat_minor:
            rows.append(["VAT", format_money(quote.vat_minor, quote.currency)])
        rows.append(["Total", format_money(quote.total_minor, quote.currency)])
        rows.append([f"Less deposit invoiced ({deposit_ref})", "-" + format_money(deposit_minor, quote.currency)])
        rows.append(["Balance due", format_money(document.total_minor, quote.currency)])
        totals = _split_totals_table(rows, len(rows) - 1)
    else:
        totals = _totals_table(quote)
    tail = [totals, Spacer(1, 6 * mm)]

    if document.notes:
        tail.append(Paragraph("NOTES", styles["label"]))
        tail.append(Paragraph(document.notes, styles["body"]))
        tail.append(Spacer(1, 3 * mm))

    # Minette's approved wording (2026-08-03). Deliberately short: the acceptance /
    # entire-agreement clause and the 12.5% p.a. late-payment interest live on the
    # Quote and in the Terms & Conditions, not here - by the time a Pro-Forma or
    # Tax Invoice is issued the client has already accepted the quote and its T&Cs,
    # so repeating an acceptance clause on these documents would be wrong.
    fine_lines = []
    if doc_type == PRO_FORMA:
        fine_lines.append("<b>Not a Tax Invoice.</b>")
    fine_lines.append(
        "Payment due on day of practical completion. Please use the invoice number as "
        "reference when making payment."
    )
    tail.append(_terms_box(business_settings, styles, fine_lines))
    story.extend(tail)

    doc.build(story, onFirstPage=lambda c, d: draw_page_frame(c, d, business_settings), onLaterPages=lambda c, d: draw_page_frame(c, d, business_settings))

    return output_path


def generate_statement_pdf(statement, invoices, customer, business_settings, output_path, billing_address=None, delivery_address=None, lines=None):

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=10 * mm,
        bottomMargin=FOOTER_HEIGHT + 8 * mm,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
    )

    story = []
    _header_and_rule(story, business_settings, styles)

    to_lines = [f"<b>{customer.name}</b>"]
    if customer.email:
        to_lines.append(customer.email)
    if customer.phone:
        to_lines.append(customer.phone)
    if customer.vat_number:
        to_lines.append(f"VAT No: {customer.vat_number}")
    to_lines.extend(format_address_lines(billing_address))
    if delivery_address is not None:
        delivery_lines = format_address_lines(delivery_address)
        if delivery_lines:
            to_lines.append("Delivery:")
            to_lines.extend(delivery_lines)

    left_cell_content = [
        Paragraph("STATEMENT", styles["title"]),
        Spacer(1, 6 * mm),
        Paragraph("TO", styles["label"]),
        Paragraph("<br/>".join(to_lines), styles["body"]),
    ]

    meta_rows = [
        [Paragraph("STATEMENT #", styles["meta_label"]), Paragraph(statement.document_number, styles["meta_value"])],
        [Paragraph("PERIOD", styles["meta_label"]), Paragraph(f"{statement.period_start} to {statement.period_end}", styles["meta_value"])],
    ]
    meta_table = Table(meta_rows, colWidths=[26 * mm, 46 * mm])
    meta_table.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))

    layout_table = Table([[left_cell_content, [meta_table]]], colWidths=[108 * mm, 74 * mm])
    layout_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(layout_table)
    story.append(Spacer(1, 10 * mm))

    if lines is not None:
        table_data = [["Reference", "Date", "Description", "Amount"]]
        for line in lines:
            table_data.append([
                line["ref"],
                (line["date"] or "")[:10] or "—",
                Paragraph(line["description"], styles["body"]),
                format_money(line["amount_minor"], line.get("currency") or statement.currency),
            ])
        invoices = lines
    else:
        table_data = [["Invoice #", "Date", "Due Date", "Amount"]]
        for invoice in invoices:
            table_data.append([
                invoice.document_number,
                invoice.issue_date,
                invoice.due_date or "—",
                format_money(invoice.total_minor, invoice.currency),
            ])

    col_widths = [45 * mm, 25 * mm, 72 * mm, 40 * mm] if lines is not None else [50 * mm, 30 * mm, 30 * mm, 72 * mm]
    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), BODY_FONT),
        ("FONTSIZE", (0, 1), (-1, -1), 9.5),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(items_table)
    story.append(Spacer(1, push_down_spacer_mm(len(invoices)) * mm))

    total_table = Table(
        [["Total Due", format_money(statement.total_minor, statement.currency)]],
        colWidths=[35 * mm, 35 * mm], hAlign="RIGHT",
    )
    total_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), BOLD_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_TINT),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, ACCENT_COLOR),
    ]))
    tail = [total_table, Spacer(1, 8 * mm)]

    if statement.notes:
        tail.append(Paragraph("NOTES", styles["label"]))
        tail.append(Paragraph(statement.notes, styles["body"]))
        tail.append(Spacer(1, 6 * mm))

    # Same banking + fine print box as the other document types - a Statement is
    # asking to be paid, so it needs the banking details just as much.
    tail.append(_terms_box(business_settings, styles, [
        "Please use the document number as reference when making payment. "
        + PROOF_OF_PAYMENT_NOTE
    ]))
    story.extend(tail)

    doc.build(story, onFirstPage=lambda c, d: draw_page_frame(c, d, business_settings), onLaterPages=lambda c, d: draw_page_frame(c, d, business_settings))

    return output_path
