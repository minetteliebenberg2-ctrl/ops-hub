# ==========================================================
# FC Hub - Bank Statement Parser
# ----------------------------------------------------------
# Purpose:
# Parses FNB's "Account Transaction History" CSV export (the format
# confirmed against Minette's real exports in
# C:\For Claude\29 July FC OS\accounting\transaction_history_*.zip)
# into plain rows ready for the ledger - no Excel step in between.
#
# Real format:
#   ACCOUNT TRANSACTION HISTORY
#
#   Name:, Minette, Liebenberg
#   Account:, 63130416414, [Gold Business Account]
#   Balance:, 1796.48, 764.27
#
#   Date, Amount, Balance, Description
#   2026/04/02, -1000.00, 1796.48, ML
#   ...
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import csv
import re
from dataclasses import dataclass


@dataclass
class ParsedBankRow:

    date: str
    description: str
    amount_minor: int
    transaction_type: str


class BankStatementParseError(ValueError):
    pass


def parse_fnb_statement(filepath):
    """Returns (account_label, list[ParsedBankRow], closing_balance_minor,
    statement_date). account_label is the bracketed name from the
    "Account:" line (e.g. "Gold Business Account"), or "" if the export
    doesn't include one. closing_balance_minor is the FIRST number on
    the "Balance:" header line (the account's closing/current balance
    as of the statement - confirmed against real exports that this
    matches the most recent transaction row's own Balance column value;
    the second number is "available balance" and is ignored).
    statement_date is the date of the most recent (first) transaction
    row, or "" if there are no rows. Both are None/"" if the header
    didn't carry a Balance: line."""

    lines = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(filepath, "r", encoding=encoding, newline="") as f:
                lines = f.readlines()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if lines is None:
        raise BankStatementParseError("Could not read the file - unrecognised encoding.")

    account_label = ""
    closing_balance_minor = None
    header_index = None

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith("account:"):
            match = re.search(r"\[(.*?)\]", stripped)
            if match:
                account_label = match.group(1).strip()
        if stripped.lower().startswith("balance:"):
            parts = [p.strip() for p in stripped.split(",")]
            if len(parts) >= 2:
                try:
                    closing_balance_minor = round(float(parts[1]) * 100)
                except ValueError:
                    closing_balance_minor = None
        # Flexible header detection: strip quotes/whitespace, accept
        # tab or comma delimiters, match "date" as the first field.
        header_clean = stripped.strip('"').strip()
        header_fields = re.split(r'[,\t]', header_clean)
        if header_fields and header_fields[0].strip().strip('"').lower() == "date" and len(header_fields) >= 3:
            header_index = index
            break

    if header_index is None:
        raise BankStatementParseError(
            "Could not find the 'Date, Amount, Balance, Description' header row - "
            "is this a real FNB Account Transaction History export?"
        )

    rows = []
    # See ledger_audit_parser.py's matching comment: stripping line
    # endings before csv.reader avoids phantom empty rows from a
    # trailing \r (files are opened with newline="" above). Blank rows
    # are already skipped below regardless, but this keeps the two
    # parsers consistent and avoids relying on that skip as the only
    # safety net.
    data_lines = (line.rstrip("\r\n") for line in lines[header_index + 1:])
    reader = csv.reader(data_lines)
    for raw_row in reader:
        if not raw_row or not any(cell.strip() for cell in raw_row):
            continue
        if len(raw_row) < 4:
            continue

        date_str, amount_str, _balance_str, *description_parts = raw_row
        date_str = date_str.strip()
        amount_str = amount_str.strip()
        description = ",".join(description_parts).strip()

        if not date_str or not amount_str:
            continue

        try:
            date = _normalize_date(date_str)
            amount = float(amount_str)
        except ValueError:
            continue

        transaction_type = "Income" if amount > 0 else "Expense"
        rows.append(ParsedBankRow(
            date=date,
            description=description,
            amount_minor=round(abs(amount) * 100),
            transaction_type=transaction_type,
        ))

    statement_date = rows[0].date if rows else ""
    return account_label, rows, closing_balance_minor, statement_date


def _normalize_date(value):
    """FNB exports 'YYYY/MM/DD' - convert to the app's 'YYYY-MM-DD'."""

    parts = value.replace("/", "-").split("-")
    if len(parts) != 3:
        raise ValueError(f"Unrecognised date format: {value}")
    year, month, day = parts
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
