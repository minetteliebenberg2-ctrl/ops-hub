# ==========================================================
# FC Hub - Ledger Audit Parser
# ----------------------------------------------------------
# Purpose:
# Parses the "Transaction Analysis - with ledger posting details"
# export from Minette's bookkeeping software (confirmed against her
# real export in C:\For Claude\Updated Accounting\
# B_TransactionAnalysisLedgerAudit_*.csv) - a double-entry ledger, not
# a raw bank feed. Richer than the FNB bank statement: every
# transaction already carries the real category her bookkeeper used
# (e.g. "Insurance / Security", "Motor V: Fuel & Oil",
# "Bank:  Inter-account Transfers"), so importing this needs no
# keyword guessing.
#
# Real format: semicolon-delimited, South African number formatting
# (comma decimal, space thousands separator - "1 850,00"), one
# transaction = two consecutive rows (a double-entry DR/CR pair):
#
#   Posting Date;Transaction Date;Description;Amount;Tax;Category Name;
#   Detail Description;Transaction Type;DR Amount;CR Amount
#   2025/09/01;2025/09/01;FFW LI ...;285,94;N;Insurance / Security;;
#   Payment (Auto);285,94;0,00
#   ;;;;;Gold Business Account;;Payment (Auto);0,00;285,94
#
# One row's Category Name is the real account (e.g. "Gold Business
# Account") and the other is the real category - but which one holds
# which varies per row (see the pair above vs the "FUEL" example in
# the real file, where the account and category swap sides). There's
# no reliable per-row flag for this, so the account name is
# identified as whichever Category Name value recurs on almost every
# row across the whole file (the account touches every transaction;
# individual expense/income categories don't) - confirmed against the
# real export: "Gold Business Account" appears 408 times, the next
# most common value ("General Expenses") only 47.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import csv
from collections import Counter
from dataclasses import dataclass


@dataclass
class ParsedLedgerRow:

    date: str
    description: str
    amount_minor: int
    transaction_type: str
    category: str
    account: str


class LedgerAuditParseError(ValueError):
    pass


def parse_ledger_audit(filepath):
    """Returns list[ParsedLedgerRow]."""

    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        lines = f.readlines()

    header_index = None
    for index, line in enumerate(lines):
        if line.strip().lower().startswith("posting date;"):
            header_index = index
            break

    if header_index is None:
        raise LedgerAuditParseError(
            "Could not find the 'Posting Date;Transaction Date;...' header row - "
            "is this a real ledger/transaction analysis export?"
        )

    # Feeding csv.reader an iterable of already-split lines (rather
    # than the open file object directly) can misparse if a line still
    # carries a trailing \r (a real risk here since the file is opened
    # with newline="" to control encoding) - csv.reader can treat a
    # bare embedded \r as its own line terminator, producing phantom
    # empty rows that desync the date-row/blank-row pairing below.
    # Stripping line endings before handing lines to csv.reader avoids
    # that entirely.
    data_lines = (line.rstrip("\r\n") for line in lines[header_index + 1:])
    reader = [row for row in csv.reader(data_lines, delimiter=";") if any(cell.strip() for cell in row)]
    pairs = _group_into_pairs(reader)
    if not pairs:
        return []

    account_name = _detect_account_name(pairs)

    rows = []
    for first, second in pairs:
        category_a = first[5].strip() if len(first) > 5 else ""
        category_b = second[5].strip() if len(second) > 5 else ""

        if category_a == account_name:
            category = category_b
        elif category_b == account_name:
            category = category_a
        else:
            # Neither side matched the detected account - fall back to
            # whichever isn't blank, so the row still imports with
            # *some* category rather than being silently dropped.
            category = category_a or category_b

        transaction_type_raw = first[7].strip() if len(first) > 7 else ""
        transaction_type = "Income" if "receipt" in transaction_type_raw.lower() else "Expense"

        try:
            date = _normalize_date(first[0].strip())
            amount_minor = _parse_sa_amount(first[3])
        except (ValueError, IndexError):
            continue

        rows.append(ParsedLedgerRow(
            date=date,
            description=(first[2].strip() if len(first) > 2 else ""),
            amount_minor=amount_minor,
            transaction_type=transaction_type,
            category=category,
            account=account_name,
        ))

    return rows


def _group_into_pairs(reader_rows):
    """Each real transaction is two consecutive rows: the first has a
    Posting Date, the second is blank-dated (the double-entry
    counterpart). Rows that don't fit this shape are skipped rather
    than guessed at."""

    pairs = []
    index = 0
    while index < len(reader_rows):
        row = reader_rows[index]
        if not row or not any(cell.strip() for cell in row):
            index += 1
            continue
        if len(row) < 10 or not row[0].strip():
            index += 1
            continue

        if index + 1 < len(reader_rows) and _is_pair_row(reader_rows[index + 1]):
            pairs.append((row, reader_rows[index + 1]))
            index += 2
        else:
            # No counterpart row - still import it standalone against
            # itself, so an unusual single-row entry isn't lost.
            pairs.append((row, row))
            index += 1

    return pairs


def _is_pair_row(row):

    return bool(row) and len(row) >= 10 and not row[0].strip() and any(cell.strip() for cell in row)


def _detect_account_name(pairs):

    counts = Counter()
    for first, second in pairs:
        if len(first) > 5:
            counts[first[5].strip()] += 1
        if len(second) > 5 and second is not first:
            counts[second[5].strip()] += 1
    counts.pop("", None)
    if not counts:
        return "Unspecified Account"
    return counts.most_common(1)[0][0]


def _parse_sa_amount(value):
    """South African number formatting: '1 850,00' -> 1850.00,
    returned as integer cents."""

    cleaned = value.strip().replace("\xa0", " ").replace(" ", "").replace(",", ".")
    if not cleaned:
        raise ValueError("Empty amount")
    return round(abs(float(cleaned)) * 100)


def _normalize_date(value):

    parts = value.replace("/", "-").split("-")
    if len(parts) != 3:
        raise ValueError(f"Unrecognised date format: {value}")
    year, month, day = parts
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
