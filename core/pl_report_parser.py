# ==========================================================
# FC Hub - P&L Report Parser
# ----------------------------------------------------------
# Parses the bookkeeping software's "Special Category Tag Type
# Analysis" (Income & Expenses YTD) CSV export into the same
# ParsedLedgerRow shape used by the ledger_audit_parser, so the
# existing BankImportWindow can import it with categories intact.
#
# Expected header row (first row):
#   ReportName,EffectiveDate,Textbox64,FinCatName,YTD4,Textbox10,
#   MainName,YTD,Textbox11,SubCategory,YTD1,Textbox12,
#   DateDescription,YTD2,Textbox13,Type1,YTD3
#
# Key columns:
#   col 6  MainName        "116 . Fee / Consulting Income"
#   col 12 DateDescription "2026/01/27 : 102 LOPER AVENUE : "
#   col 13 YTD2            individual transaction amount (signed)
# ==========================================================

import csv
import re

from core.ledger_audit_parser import ParsedLedgerRow


class PLReportParseError(ValueError):
    pass


def parse_pl_report(filepath):
    """Returns list[ParsedLedgerRow] from a P&L Category Analysis CSV.
    Amounts from the source are already signed (negative = expense)."""

    lines = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(filepath, "r", encoding=encoding, newline="") as f:
                lines = f.readlines()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if lines is None:
        raise PLReportParseError("Could not read the file — unrecognised encoding.")

    if not lines:
        raise PLReportParseError("File is empty.")

    header = lines[0].strip()
    if not header.lower().startswith("reportname"):
        raise PLReportParseError(
            "Not a P&L Category Analysis export — first row does not start with 'ReportName'."
        )

    reader = csv.reader(line.rstrip("\r\n") for line in lines[1:])
    rows = []
    for raw in reader:
        if not raw or not any(c.strip() for c in raw):
            continue
        if len(raw) < 14:
            continue

        main_name = raw[6].strip()
        date_desc = raw[12].strip()
        amount_str = raw[13].strip()

        if not date_desc or not amount_str:
            continue

        try:
            amount = float(amount_str)
        except ValueError:
            continue

        date = _extract_date(date_desc)
        if not date:
            continue
        description = _extract_description(date_desc)
        category = _clean_category(main_name)
        transaction_type = "Income" if amount > 0 else "Expense"

        rows.append(ParsedLedgerRow(
            date=date,
            description=description,
            amount_minor=round(abs(amount) * 100),
            transaction_type=transaction_type,
            category=category,
            account="",
        ))

    return rows


def _extract_date(date_desc):
    """Pull 'YYYY/MM/DD' from 'YYYY/MM/DD : description : '."""
    match = re.match(r"(\d{4})/(\d{2})/(\d{2})", date_desc)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _extract_description(date_desc):
    """Pull the middle part from 'YYYY/MM/DD : description : '."""
    parts = date_desc.split(" : ")
    if len(parts) >= 2:
        return parts[1].strip().rstrip(" :")
    return date_desc.strip()


def _clean_category(main_name):
    """Strip numeric prefix: '116 . Fee / Consulting Income' -> 'Fee / Consulting Income'."""
    cleaned = re.sub(r"^\d+\s*\.\s*", "", main_name)
    return cleaned.strip()
