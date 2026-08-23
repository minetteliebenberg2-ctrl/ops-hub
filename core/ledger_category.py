# ==========================================================
# FC Hub - Ledger Category
# ----------------------------------------------------------
# Purpose:
# One self-service category for the general ledger (Income or
# Expense), backed by the ledger_categories table (migration v0020).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class LedgerCategory:

    id: str = ""
    name: str = ""
    category_type: str = "Expense"
    active: bool = True
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
