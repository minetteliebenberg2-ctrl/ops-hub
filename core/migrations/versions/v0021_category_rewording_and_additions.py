"""Migration 0021: Ledger category rewording and additions from
Minette's own reference workbook.

Follow-up agreed 2026-08-04/2026-08-05 to the category list seeded by
v0020. Minette pointed at `Financial_system_auto_categorised_March
2026.xlsx` in `C:\\For Claude\\Updated Accounting\\` - a category list
and Description-to-Category map she built by hand from her real bank
data, plainer and more specific to her business than the generic
bookkeeping-export categories v0020 seeded. Confirmed with her
directly (not guessed) before this migration was written:

1. Four existing categories are reworded to her plainer terms. This is
   a full rename, not just relabeling the category list: every
   existing transaction already tagged with the old name is
   re-pointed at the new name too, so reporting/category breakdowns
   stay consistent under the new wording. This is a bulk taxonomy
   correction rather than an individual user edit, so - unlike
   `LedgerService.update_category` - it does NOT write rows to
   `ledger_transaction_edits`: that table backs the single-level
   global Undo button, and bulk-writing dozens of rows into it here
   would bury Undo under this migration instead of her next real edit.
   - "Bank Charges" -> "Bank Fees"
   - "Credit Card Expenses" -> "Credit Card Payment"
   - "Telephone / Fax / Internet" -> "Cell Phone/Communication"
   - "Entertainment & Meals" -> "Business Meals"

2. New categories are added for real supplier/expense breakdowns her
   workbook already tracks that the current list lumps into generic
   buckets: Netting Suppliers, Steel Supplier, Paint Supplier, Casual
   Staff, IT Services (all Expense, counted in business totals same as
   any other expense category).

3. New personal-life categories are added using the same
   "visible but excluded from business totals" treatment already
   applied to "Bank:  Inter-account Transfers" / "Unassigned Receipts"
   (see TRANSFER_LIKE_CATEGORIES in core/ledger_service.py, extended in
   this migration's application code): Home Loan, Airport, Clothing,
   Pharmacy, Local Shop (Expense), and Loan repayment (Income - family
   loan repayments like "Payment From Mamma", a real money movement but
   not real business income).

Confirmed explicitly: existing transactions are NOT retagged into the
new supplier categories (Knittex/Plusnet/Chemvet/Dura Paints purchases
already recorded under "Direct Selling Costs" stay there) - only new
imports going forward use the new categories. See
core/ledger_service.py AUTO_CATEGORY_RULES for the forward-only rule
additions.
"""

import sqlite3
import uuid
from datetime import datetime, timezone

from core.migrations.runner import Migration, migration_checksum


VERSION = 21
NAME = "category_rewording_and_additions"

# Old name -> new name. Applied to both ledger_categories.name and
# every ledger_transactions.category currently set to the old name.
RENAMES = {
    "Bank Charges": "Bank Fees",
    "Credit Card Expenses": "Credit Card Payment",
    "Telephone / Fax / Internet": "Cell Phone/Communication",
    "Entertainment & Meals": "Business Meals",
}

# New business categories - counted in business totals like any other.
NEW_BUSINESS_EXPENSE_CATEGORIES = [
    "Netting Suppliers",
    "Steel Supplier",
    "Paint Supplier",
    "Casual Staff",
    "IT Services",
]

# New personal-life categories - visible in the ledger and category
# breakdown, but excluded from Total Income/Total Expenses/Net Profit,
# same treatment as "Bank:  Inter-account Transfers".
NEW_PERSONAL_EXPENSE_CATEGORIES = [
    "Home Loan",
    "Airport",
    "Clothing",
    "Pharmacy",
    "Local Shop",
]
NEW_PERSONAL_INCOME_CATEGORIES = [
    "Loan repayment",
]

PAYLOAD = "\n;\n".join(
    " ".join(item.split())
    for item in (
        *[f"RENAME {old} -> {new}" for old, new in RENAMES.items()],
        *[f"ADD EXPENSE {name}" for name in NEW_BUSINESS_EXPENSE_CATEGORIES],
        *[f"ADD EXPENSE PERSONAL {name}" for name in NEW_PERSONAL_EXPENSE_CATEGORIES],
        *[f"ADD INCOME PERSONAL {name}" for name in NEW_PERSONAL_INCOME_CATEGORIES],
    )
)


def apply(connection):

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # 1. Rename existing categories and cascade onto transactions
    # already tagged with the old name.
    for old_name, new_name in RENAMES.items():
        connection.execute(
            "UPDATE ledger_categories SET name = ?, updated_at = ? WHERE name = ?",
            (new_name, now, old_name),
        )
        connection.execute(
            "UPDATE ledger_transactions SET category = ? WHERE category = ?",
            (new_name, old_name),
        )

    # 2. Add new categories (skip any that already exist by name, so
    # this migration is safe to reason about even if a name collides
    # with something added by hand before this ran).
    def insert_if_new(name, category_type):
        existing = connection.execute(
            "SELECT id FROM ledger_categories WHERE name = ?", (name,),
        ).fetchone()
        if existing is not None:
            return
        connection.execute(
            "INSERT INTO ledger_categories (id, name, category_type, active, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            (str(uuid.uuid4()), name, category_type, now, now),
        )

    for name in NEW_BUSINESS_EXPENSE_CATEGORIES:
        insert_if_new(name, "Expense")
    for name in NEW_PERSONAL_EXPENSE_CATEGORIES:
        insert_if_new(name, "Expense")
    for name in NEW_PERSONAL_INCOME_CATEGORIES:
        insert_if_new(name, "Income")


def verify(connection):

    for old_name in RENAMES:
        row = connection.execute(
            "SELECT id FROM ledger_categories WHERE name = ?", (old_name,),
        ).fetchone()
        if row is not None:
            raise sqlite3.DatabaseError(f"Migration v0021 left old category name '{old_name}' in place.")

    for new_name in list(RENAMES.values()) + NEW_BUSINESS_EXPENSE_CATEGORIES + NEW_PERSONAL_EXPENSE_CATEGORIES + NEW_PERSONAL_INCOME_CATEGORIES:
        row = connection.execute(
            "SELECT id FROM ledger_categories WHERE name = ?", (new_name,),
        ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError(f"Migration v0021 did not create category '{new_name}'.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
