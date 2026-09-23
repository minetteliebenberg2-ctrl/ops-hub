# ==========================================================
# FC Hub - Ledger Income Statement PDF
# ----------------------------------------------------------
# Purpose:
# A branded PDF Income Statement for a date range - total income,
# total expenses, net profit, and a category-by-category breakdown -
# for records/COIDA. Mirrors the visual style of core/quote_pdf.py
# and core/document_pdf.py (Lato where available, brand green).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.document_pdf import BODY_FONT, BOLD_FONT, PAGE_MARGIN

BRAND_GREEN = colors.HexColor("#1B7A3D")
WARN_COLOR = colors.HexColor("#CC6600")
GREY_COLOR = colors.HexColor("#666666")
INK_COLOR = colors.HexColor("#1A1A1A")


def format_money(minor_units, currency="ZAR"):

    symbol = "R" if currency == "ZAR" else currency + " "
    return f"{symbol}{minor_units / 100:,.2f}"


def generate_income_statement_pdf(summary, business_settings, date_from, date_to, output_path):
    """summary: the dict returned by LedgerService.get_summary(date_from, date_to)."""

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "IncomeStatementTitle", parent=styles["Title"], fontName=BOLD_FONT,
        fontSize=18, textColor=BRAND_GREEN, spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "IncomeStatementSubtitle", parent=styles["Normal"], fontName=BODY_FONT,
        fontSize=10, textColor=GREY_COLOR, spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "SectionHeading", parent=styles["Heading2"], fontName=BOLD_FONT,
        fontSize=12, textColor=INK_COLOR, spaceBefore=14, spaceAfter=6,
    )

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=PAGE_MARGIN, rightMargin=PAGE_MARGIN, topMargin=PAGE_MARGIN, bottomMargin=PAGE_MARGIN,
    )

    story = []
    business_name = getattr(business_settings, "trading_name", "") or "Business"
    story.append(Paragraph(business_name, title_style))
    story.append(Paragraph("Income Statement", subtitle_style))
    date_range = f"{date_from or '(beginning)'} to {date_to or '(today)'}"
    story.append(Paragraph(f"Period: {date_range}", subtitle_style))

    totals_data = [
        ["Total Income", format_money(summary["total_income_minor"])],
        ["Total Expenses", format_money(summary["total_expenses_minor"])],
        ["Net Profit", format_money(summary["net_profit_minor"])],
    ]
    totals_table = Table(totals_data, colWidths=[100 * mm, 60 * mm])
    totals_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), BODY_FONT),
        ("FONTNAME", (0, 2), (-1, 2), BOLD_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("TEXTCOLOR", (1, 0), (1, 0), BRAND_GREEN),
        ("TEXTCOLOR", (1, 1), (1, 1), WARN_COLOR),
        ("TEXTCOLOR", (1, 2), (1, 2), BRAND_GREEN if summary["net_profit_minor"] >= 0 else WARN_COLOR),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#CCCCCC")),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(totals_table)

    story.append(Paragraph("Income by Category", section_style))
    income_rows = _category_rows(summary["by_category"], "Income")
    story.append(_category_table(income_rows))

    story.append(Paragraph("Expenses by Category", section_style))
    expense_rows = _category_rows(summary["by_category"], "Expense")
    story.append(_category_table(expense_rows))

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f"Based on {summary['transaction_count']} transactions in the ledger.",
        ParagraphStyle("Footnote", parent=styles["Normal"], fontName=BODY_FONT, fontSize=8, textColor=GREY_COLOR),
    ))

    doc.build(story)
    return output_path


def _category_rows(by_category, transaction_type):

    rows = []
    for key, amount in sorted(by_category.items(), key=lambda item: -item[1]):
        prefix = f"{transaction_type}/"
        if key.startswith(prefix):
            rows.append((key[len(prefix):], amount))
    return rows


def _category_table(rows):

    if not rows:
        return Paragraph("No transactions in this category.", getSampleStyleSheet()["Normal"])

    data = [["Category", "Amount"]] + [[name, format_money(amount)] for name, amount in rows]
    subtotal = sum(amount for _, amount in rows)
    data.append(["Subtotal", format_money(subtotal)])

    table = Table(data, colWidths=[110 * mm, 50 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
        ("FONTNAME", (0, -1), (-1, -1), BOLD_FONT),
        ("FONTNAME", (0, 1), (-1, -2), BODY_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#CCCCCC")),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table
