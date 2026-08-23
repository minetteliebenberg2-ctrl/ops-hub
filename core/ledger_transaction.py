# ==========================================================
# FC Hub - Ledger Transaction
# ----------------------------------------------------------
# Purpose:
# One row in the general accounting ledger (personal + business),
# persisted to the database - manual entry or bank statement import.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass

INCOME = "Income"
EXPENSE = "Expense"

SOURCE_MANUAL = "Manual"
SOURCE_BANK_IMPORT = "Bank Import"
SOURCE_LEDGER_IMPORT = "Ledger Import"


@dataclass
class LedgerTransaction:

    id: str = ""
    date: str = ""
    description: str = ""
    amount_minor: int = 0
    transaction_type: str = EXPENSE
    category: str = ""
    account: str = ""
    reference: str = ""
    notes: str = ""
    source: str = SOURCE_MANUAL
    import_batch: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    receipt_filename: str = ""
