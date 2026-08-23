"""Migration 0040: balance-sheet accounts and their per-year balances.

The ledger is a single-entry cashbook - every row is Income or Expense
against a category and a bank account. That is enough to produce an
income statement and a cash flow, but a balance sheet needs assets,
liabilities and equity, and those simply are not in the data: a
single-entry row never records the other side of the transaction.

Minette chose (2026-08-14) to keep capturing exactly as she does now
rather than rebuild the ledger as double-entry. So the balance-sheet
figures are maintained directly, the same way the yellow cells work in
the standalone Excel workbook (tools/build_accounting_workbook.py):
she enters the opening balance for each account at the start of the
financial year, and the statement adds the movement it can derive.

`balance_sheet_accounts` is the chart of balance-sheet accounts,
seeded with a standard small-company set she can edit. `is_cash`
marks the accounts that represent money in the bank, so the Cash Flow
and the balance sheet agree on what counts as cash. `ledger_account`
optionally ties one to the `account` value used on ledger rows, which
is what lets a bank account's movement be derived rather than typed.

`balance_sheet_balances` holds one opening balance per account per
financial year (the year is the calendar year the March start falls
in, so 2026 means March 2026 - February 2027).
"""

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 40
NAME = "balance_sheet_accounts"

CREATE_ACCOUNTS = """
CREATE TABLE balance_sheet_accounts (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL,
    statement_group TEXT NOT NULL,
    ledger_account TEXT NOT NULL DEFAULT '',
    is_cash INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT ''
)
"""

CREATE_BALANCES = """
CREATE TABLE balance_sheet_balances (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    financial_year INTEGER NOT NULL,
    opening_balance_minor INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT '',
    UNIQUE (account_id, financial_year),
    FOREIGN KEY (account_id) REFERENCES balance_sheet_accounts (id) ON DELETE CASCADE
)
"""

INDEX_BALANCES = (
    "CREATE INDEX idx_balance_sheet_balances_year "
    "ON balance_sheet_balances (financial_year)"
)

# (code, name, type, group, is_cash)
SEED_ACCOUNTS = (
    ("1000", "Bank - Current Account", "Asset", "Current Assets", 1),
    ("1010", "Bank - Savings Account", "Asset", "Current Assets", 1),
    ("1020", "Petty Cash", "Asset", "Current Assets", 1),
    ("1100", "Trade Debtors (Accounts Receivable)", "Asset", "Current Assets", 0),
    ("1200", "Stock on Hand", "Asset", "Current Assets", 0),
    ("1500", "Plant & Equipment", "Asset", "Non-Current Assets", 0),
    ("1510", "Motor Vehicles", "Asset", "Non-Current Assets", 0),
    ("1520", "Office Equipment & Computers", "Asset", "Non-Current Assets", 0),
    ("1590", "Accumulated Depreciation", "Asset", "Non-Current Assets", 0),
    ("2000", "Trade Creditors (Accounts Payable)", "Liability", "Current Liabilities", 0),
    ("2100", "Credit Card", "Liability", "Current Liabilities", 0),
    ("2200", "SARS - PAYE/UIF/SDL", "Liability", "Current Liabilities", 0),
    ("2210", "SARS - Income Tax Payable", "Liability", "Current Liabilities", 0),
    ("2300", "Customer Deposits Held", "Liability", "Current Liabilities", 0),
    ("2500", "Long Term Loans", "Liability", "Non-Current Liabilities", 0),
    ("2600", "Directors Loan Account", "Liability", "Non-Current Liabilities", 0),
    ("3000", "Share Capital", "Equity", "Equity", 0),
    ("3100", "Retained Earnings", "Equity", "Equity", 0),
)

STATEMENTS = (CREATE_ACCOUNTS, CREATE_BALANCES, INDEX_BALANCES)

PAYLOAD = "\n;\n".join(
    " ".join(statement.split()) for statement in STATEMENTS + (str(SEED_ACCOUNTS),)
)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for sort_order, (code, name, account_type, group, is_cash) in enumerate(SEED_ACCOUNTS, start=1):
        connection.execute(
            """
            INSERT INTO balance_sheet_accounts (
                id, code, name, account_type, statement_group,
                ledger_account, is_cash, sort_order, is_active,
                created_at, updated_at, updated_by
            )
            VALUES (?, ?, ?, ?, ?, '', ?, ?, 1, ?, ?, 'system')
            """,
            (str(uuid4()), code, name, account_type, group, is_cash, sort_order, now, now),
        )


def verify(connection):
    for table in ("balance_sheet_accounts", "balance_sheet_balances"):
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        if not exists:
            raise sqlite3.DatabaseError(f"Migration v0040 did not create '{table}'.")

    seeded = connection.execute("SELECT COUNT(*) FROM balance_sheet_accounts").fetchone()[0]
    if seeded < len(SEED_ACCOUNTS):
        raise sqlite3.DatabaseError(
            f"Migration v0040 seeded {seeded} accounts, expected {len(SEED_ACCOUNTS)}."
        )

    cash = connection.execute(
        "SELECT COUNT(*) FROM balance_sheet_accounts WHERE is_cash = 1"
    ).fetchone()[0]
    if not cash:
        raise sqlite3.DatabaseError("Migration v0040 seeded no cash accounts.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
