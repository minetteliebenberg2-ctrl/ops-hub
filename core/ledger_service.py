# ==========================================================
# FC Hub - Ledger Service
# ----------------------------------------------------------
# Purpose:
# Business rules for the general accounting ledger - manual entry and
# direct FNB bank statement import (no Excel step), covering personal
# and business transactions across a full financial/calendar year.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.bank_statement_parser import parse_fnb_statement
from core.ledger_audit_parser import parse_ledger_audit
from core.ledger_category import LedgerCategory
from core.ledger_category_repository import LedgerCategoryRepository
from core.ledger_repository import LedgerTransactionRepository
from core.merchant_key import merchant_key, merchant_matches
from core.ledger_transaction import (
    EXPENSE, INCOME, SOURCE_BANK_IMPORT, SOURCE_LEDGER_IMPORT, SOURCE_MANUAL, LedgerTransaction,
)


# Real chart of accounts, not a generic guess - extracted from
# Minette's actual bookkeeping software export (the "Transaction
# Analysis - with ledger posting details" audit, see
# core/ledger_audit_parser.py) so these are the exact category names
# her bookkeeper already uses. Split Income/Expense by how each
# category was actually used across ~400 real transactions (a
# category used as both, like "Bank: Inter-account Transfers", is
# listed under whichever type it appeared as most).
INCOME_CATEGORIES = [
    "Sales Income",
    "Bank:  Inter-account Transfers",
    "Unassigned Receipts",
    "Sundry Income",
    "Other Income",
]

EXPENSE_CATEGORIES = [
    "General Expenses",
    "Direct Selling Costs",
    "Subcontract Costs",
    "Personal Expenses through Business Accounts",
    "Bank Fees",
    "Insurance / Security",
    "Groceries",
    "Op Cost: General Operating",
    "Payroll Expenses",
    "Business Insurance",
    "Business Meals",
    "Motor V: Fuel & Oil",
    "Motor Vehicle Expenses",
    "Motor V: Repairs & Maintenance",
    "Cell Phone/Communication",
    "Operating Costs",
    "Directors Fees & Remuneration",
    "Credit Card Payment",
    "Repairs & Maintenance",
    "Cleaning & Gardening",
    "Bad Debts",
    "Unassigned Payments",
    "Subscriptions and membership fees",
    "Liabilities: Long Term",
    "Accounting",
    "Legal Fees",
    "Normal Taxation",
    "Share Holders/ Directors/ Members Loans",
    "Loans (Private) From:",
    "Loans (Private) To / (From):",
    "General Exp: Gifts",
    "Personal care / hygene / wellness",
    "Staff Welfare",
    "Security",
    "Dividends /  Pft/Loss Distribution",
    "Subcontractor Wages",
    "Office Supplies",
    "Miscellaneous",
]

# Categories that are real money movements but not real income/expense
# for reporting purposes - personal funds moved into the business,
# family loans, personal-life spending, and unassigned/unreconciled
# receipts. Confirmed with Minette 2026-08-04: still shown in the
# ledger and in the category breakdown (so they're auditable), but
# excluded from Total Income / Total Expenses / Net Profit and the
# monthly trend chart so they don't inflate the real numbers.
#
# Extended 2026-08-05 (migration v0021) with personal-life categories
# from her reference workbook (Home Loan, Airport, Clothing, Pharmacy,
# Local Shop, Loan repayment) - same "visible but excluded" treatment,
# confirmed with her directly rather than assumed.
TRANSFER_LIKE_CATEGORIES = {
    "Bank:  Inter-account Transfers",
    "Unassigned Receipts",
    "Home Loan",
    "Airport",
    "Clothing",
    "Pharmacy",
    "Local Shop",
    "Loan repayment",
}

# Auto-categorization rules for bank-statement imports.
#
# Ops Hub is a generic tool, so the account-specific rule set this
# started life with (FacilitiesCo subcontractors, netting/steel/paint
# suppliers, and the owner's personal payees) was removed on
# 2026-09-23. The bank already categorises its own statements, and a
# rule matching someone else's payee names would mis-tag every row.
#
# What is left is deliberately neutral: bank-generated descriptions
# and the revenue authority. Nothing here names a person, a customer
# or a supplier. Anything unmatched is imported UNCATEGORISED and is
# tagged by hand or through the bulk-recategorise screen, which is
# where saved rules (migration v0032) live - those are the user's own
# and always win over this list.
AUTO_CATEGORY_RULES = [
    ("#MONTHLY ACCOUNT FEE", "Bank Fees"),
    ("#SERVICE FEES", "Bank Fees"),
    ("SARS", "Normal Taxation"),
]


class LedgerService:

    def __init__(self, repository=None, category_repository=None):

        self.repository = repository or LedgerTransactionRepository()
        self.category_repository = category_repository or LedgerCategoryRepository(db=self.repository.db)

    # --------------------------------------------------
    # Manual entry
    # --------------------------------------------------

    def add_transaction(self, date, description, amount_minor, transaction_type, category,
                         account, reference, notes, actor):

        if amount_minor <= 0:
            raise ValueError("Amount must be greater than zero.")
        if transaction_type not in (INCOME, EXPENSE):
            raise ValueError("Transaction type must be Income or Expense.")
        if not date:
            raise ValueError("A date is required.")

        transaction = LedgerTransaction(
            date=date,
            description=description.strip(),
            amount_minor=amount_minor,
            transaction_type=transaction_type,
            category=category,
            account=account,
            reference=reference.strip(),
            notes=notes.strip(),
            source=SOURCE_MANUAL,
            created_by=actor,
        )
        return self.repository.create(transaction)

    # --------------------------------------------------
    # Bank statement import
    # --------------------------------------------------

    def import_bank_statement(self, filepath, actor, account_override=""):
        """Parses an FNB CSV export and inserts new rows only - rows
        already present for that account (matched on date + amount +
        description, counted rather than uniqued so genuinely repeated
        same-day transactions aren't wrongly skipped) are left alone, so
        re-importing an overlapping month is always safe."""

        account_label, parsed_rows, closing_balance_minor, statement_date = parse_fnb_statement(filepath)
        account = account_override.strip() or account_label or "Unspecified Account"

        if not parsed_rows:
            return {"imported": 0, "skipped_duplicates": 0, "account": account}

        existing = self.repository.list_for_account(account)
        existing_counts = Counter(
            (row.date, row.amount_minor, row.description) for row in existing
        )

        import_batch = Path(filepath).name
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        to_insert = []
        skipped = 0

        categorised = 0
        for row in parsed_rows:
            key = (row.date, row.amount_minor, row.description)
            if existing_counts[key] > 0:
                existing_counts[key] -= 1
                skipped += 1
                continue

            category = self._auto_category(row.description)
            if category:
                categorised += 1
            to_insert.append(LedgerTransaction(
                date=row.date,
                description=row.description,
                amount_minor=row.amount_minor,
                transaction_type=row.transaction_type,
                category=category,
                account=account,
                reference="",
                notes="",
                source=SOURCE_BANK_IMPORT,
                import_batch=import_batch,
                created_at=now,
                created_by=actor,
            ))

        self.repository.bulk_create(to_insert)

        if closing_balance_minor is not None and statement_date:
            self._upsert_reconciliation_snapshot(account, closing_balance_minor, statement_date)

        return {
            "imported": len(to_insert),
            "skipped_duplicates": skipped,
            "account": account,
            "categorised": categorised,
            "uncategorised": len(to_insert) - categorised,
        }

    # --------------------------------------------------

    def _upsert_reconciliation_snapshot(self, account, statement_balance_minor, statement_date):
        """Records the "last known bank balance" for this account,
        refreshed on every FNB import - see get_reconciliation."""

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self.repository.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO account_reconciliation_snapshots (account, statement_balance_minor, statement_date, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(account) DO UPDATE SET
                    statement_balance_minor = excluded.statement_balance_minor,
                    statement_date = excluded.statement_date,
                    updated_at = excluded.updated_at
                """,
                (account, statement_balance_minor, statement_date, now),
            )

    # --------------------------------------------------

    def get_reconciliation(self, account):
        """Returns {ledger_balance_minor, statement_balance_minor,
        statement_date, difference_minor} for this account, or None if
        it has never been imported (no snapshot yet).

        NOTE: ledger_balance_minor is SUM(Income) - SUM(Expense) across
        ALL transactions ever recorded for this account (all time, not
        date-filtered). This is only accurate if the ledger contains
        every transaction for the account since it was opened - a
        mismatch could mean a missing import, OR just that the ledger
        doesn't go back that far. It is not proof of an error either
        way, just a number worth checking."""

        with self.repository.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM account_reconciliation_snapshots WHERE account = ?", (account,),
            ).fetchone()
        if row is None:
            return None

        transactions = self.repository.list_all({"account": account})
        income = sum(t.amount_minor for t in transactions if t.transaction_type == INCOME)
        expenses = sum(t.amount_minor for t in transactions if t.transaction_type == EXPENSE)
        ledger_balance_minor = income - expenses

        return {
            "ledger_balance_minor": ledger_balance_minor,
            "statement_balance_minor": row["statement_balance_minor"],
            "statement_date": row["statement_date"],
            "difference_minor": ledger_balance_minor - row["statement_balance_minor"],
        }

    # --------------------------------------------------
    # Bookkeeping ledger export import
    # --------------------------------------------------

    def import_ledger_audit(self, filepath, actor, account_override=""):
        """Parses a "Transaction Analysis - with ledger posting
        details" export from Minette's bookkeeping software - richer
        than a raw bank statement since every row already carries the
        real category her bookkeeper assigned. Shares the same
        de-duplication approach as import_bank_statement, and checks
        against imported rows from *either* importer, so importing the
        same account from both a bank statement and a ledger audit
        export never double-counts a transaction."""

        parsed_rows = parse_ledger_audit(filepath)
        account = account_override.strip() or (parsed_rows[0].account if parsed_rows else "") or "Unspecified Account"

        if not parsed_rows:
            return {"imported": 0, "skipped_duplicates": 0, "account": account}

        existing = self.repository.list_for_account(account)
        existing_counts = Counter(
            (row.date, row.amount_minor, row.description) for row in existing
        )

        import_batch = Path(filepath).name
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        to_insert = []
        skipped = 0

        categorised = 0
        for row in parsed_rows:
            key = (row.date, row.amount_minor, row.description)
            if existing_counts[key] > 0:
                existing_counts[key] -= 1
                skipped += 1
                continue

            to_insert.append(LedgerTransaction(
                date=row.date,
                description=row.description,
                amount_minor=row.amount_minor,
                transaction_type=row.transaction_type,
                category=row.category,
                account=account,
                reference="",
                notes="",
                source=SOURCE_LEDGER_IMPORT,
                import_batch=import_batch,
                created_at=now,
                created_by=actor,
            ))

        self.repository.bulk_create(to_insert)

        return {
            "imported": len(to_insert),
            "skipped_duplicates": skipped,
            "account": account,
            "categorised": categorised,
            "uncategorised": len(to_insert) - categorised,
        }

    def import_pl_report(self, filepath, actor, account_override=""):
        """Parses a bookkeeping 'Income & Expenses YTD / Special Category
        Tag Type Analysis' CSV export. Rows arrive pre-categorized (the
        category is embedded in the MainName column). Uses the same
        de-duplication logic as import_ledger_audit."""

        from core.pl_report_parser import parse_pl_report
        parsed_rows = parse_pl_report(filepath)
        account = account_override.strip() or "Bookkeeping Import"

        if not parsed_rows:
            return {"imported": 0, "skipped_duplicates": 0, "account": account}

        existing = self.repository.list_for_account(account)
        existing_counts = Counter(
            (row.date, row.amount_minor, row.description) for row in existing
        )

        import_batch = Path(filepath).name
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        to_insert = []
        skipped = 0

        for row in parsed_rows:
            key = (row.date, row.amount_minor, row.description)
            if existing_counts[key] > 0:
                existing_counts[key] -= 1
                skipped += 1
                continue

            to_insert.append(LedgerTransaction(
                date=row.date,
                description=row.description,
                amount_minor=row.amount_minor,
                transaction_type=row.transaction_type,
                category=row.category,
                account=account,
                reference="",
                notes="",
                source=SOURCE_LEDGER_IMPORT,
                import_batch=import_batch,
                created_at=now,
                created_by=actor,
            ))

        self.repository.bulk_create(to_insert)

        return {
            "imported": len(to_insert),
            "skipped_duplicates": skipped,
            "account": account,
        }

    # --------------------------------------------------

    def _auto_category(self, description):

        # Rules Minette saved herself always win over the built-in list -
        # they are the more recent, more specific decision.
        saved = self.category_for_key(merchant_key(description))
        if saved:
            return saved

        upper = description.upper()
        for keyword, category in AUTO_CATEGORY_RULES:
            if keyword in upper:
                return category
        return ""

    # --------------------------------------------------
    # Bulk recategorise + saved rules
    # --------------------------------------------------

    def find_similar_transactions(self, description, exclude_id=None, same_category_only=None):
        """Every other transaction from the same merchant as `description`.

        Returns [] when the description yields no usable merchant key,
        so a meaningless description can never sweep up unrelated rows.
        """

        key = merchant_key(description)
        if not key:
            return []

        matches = []
        for transaction in self.repository.list_all():
            if exclude_id and transaction.id == exclude_id:
                continue
            if not merchant_matches(merchant_key(transaction.description), key):
                continue
            if same_category_only is not None and (transaction.category or "") != same_category_only:
                continue
            matches.append(transaction)
        return matches

    # --------------------------------------------------

    def bulk_update_category(self, transaction_ids, category, actor=""):
        """Recategorises many transactions, auditing each one so Undo and
        the edit history behave exactly as they do for a single edit."""

        updated = 0
        for transaction_id in transaction_ids:
            transaction = self.repository.get(transaction_id)
            if transaction is None or transaction.category == category:
                continue
            self.record_edit(transaction_id, "category", transaction.category, category, actor)
            transaction.category = category
            self.repository.update(transaction)
            updated += 1
        return updated

    # --------------------------------------------------

    def category_for_key(self, match_key):

        if not match_key:
            return ""
        with self.repository.db.connect() as connection:
            row = connection.execute(
                "SELECT category FROM ledger_category_rules WHERE match_key = ? AND is_active = 1",
                (match_key,),
            ).fetchone()
            if row:
                return row["category"]

            # No exact rule. The bank rarely prints a merchant the same way
            # twice, so fall back to the same tolerant match the bulk
            # recategorise uses - longest (most specific) rule wins.
            candidates = connection.execute(
                "SELECT match_key, category FROM ledger_category_rules WHERE is_active = 1"
            ).fetchall()
        best = ""
        best_key = ""
        for candidate in candidates:
            saved_key = candidate["match_key"] or ""
            if merchant_matches(saved_key, match_key) and len(saved_key) > len(best_key):
                best_key, best = saved_key, candidate["category"]
        return best

    # --------------------------------------------------

    def save_category_rule(self, match_key, category, transaction_type="", actor=""):
        """Remembers "this merchant means this category" for future
        imports. Re-saving the same merchant updates the rule rather than
        creating a competing second one."""

        key = (match_key or "").strip().upper()
        if not key:
            raise ValueError("A merchant is required for a rule.")
        if not category:
            raise ValueError("A category is required for a rule.")

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self.repository.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO ledger_category_rules
                    (id, match_key, category, transaction_type, is_active,
                     created_at, created_by, updated_at, updated_by)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(match_key) DO UPDATE SET
                    category = excluded.category,
                    transaction_type = excluded.transaction_type,
                    is_active = 1,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (str(uuid4()), key, category, transaction_type, now, actor, now, actor),
            )
        return key

    # --------------------------------------------------

    def list_category_rules(self):

        with self.repository.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ledger_category_rules ORDER BY match_key COLLATE NOCASE"
            ).fetchall()
        return [dict(row) for row in rows]

    # --------------------------------------------------

    def delete_category_rule(self, rule_id):

        with self.repository.db.connect() as connection:
            connection.execute("DELETE FROM ledger_category_rules WHERE id = ?", (rule_id,))

    # --------------------------------------------------
    # Reading
    # --------------------------------------------------

    def list_transactions(self, filters=None):

        return self.repository.list_all(filters)

    # --------------------------------------------------

    def list_accounts(self):

        return self.repository.list_accounts()

    def add_account(self, name):

        name = name.strip()
        if not name:
            raise ValueError("Account name cannot be empty.")
        self.repository.add_account(name)

    def delete_account(self, name):

        self.repository.delete_account(name)

    # --------------------------------------------------

    def list_categories(self, category_type=None, active_only=True):
        """Self-service categories, read from the database (ledger_categories
        table, migration v0020) rather than the hardcoded Python lists -
        those stay as documentation/fallback and as the migration's seed
        reference. Also folds in any category name actually used on a
        transaction but missing from the table (e.g. very old data),
        so nothing already in the ledger goes missing from a filter list."""

        configured = [c.name for c in self.category_repository.list_all(category_type=category_type, active_only=active_only)]
        # Only fold in a "used on a transaction" category name if it
        # isn't already known to the categories table at all (active
        # or retired) - a retired category must stay hidden from this
        # list even though old transactions still use it, otherwise
        # retiring would never actually take effect.
        known_names = {c.name for c in self.category_repository.list_all(category_type=category_type, active_only=False)}
        used = self.repository.list_categories()
        combined = configured + [c for c in used if c not in configured and c not in known_names]
        return sorted(combined, key=lambda n: n.lower())

    # --------------------------------------------------
    # Category CRUD (Settings)
    # --------------------------------------------------

    def add_category(self, name, category_type, actor):

        name = (name or "").strip()
        if not name:
            raise ValueError("A category name is required.")
        if category_type not in (INCOME, EXPENSE):
            raise ValueError("Category type must be Income or Expense.")
        if self.category_repository.get_by_name(name) is not None:
            raise ValueError(f'A category named "{name}" already exists.')

        category = LedgerCategory(name=name, category_type=category_type, active=True, created_by=actor)
        return self.category_repository.create(category)

    # --------------------------------------------------

    def rename_category(self, category_id, new_name):

        category = self.category_repository.get(category_id)
        if category is None:
            raise ValueError("Category not found.")
        new_name = (new_name or "").strip()
        if not new_name:
            raise ValueError("A category name is required.")
        existing = self.category_repository.get_by_name(new_name)
        if existing is not None and existing.id != category_id:
            raise ValueError(f'A category named "{new_name}" already exists.')
        category.name = new_name
        return self.category_repository.update(category)

    # --------------------------------------------------

    def retire_category(self, category_id):
        """Hides the category from new-entry dropdowns without deleting
        it or breaking transactions that already use it."""

        category = self.category_repository.get(category_id)
        if category is None:
            raise ValueError("Category not found.")
        category.active = False
        return self.category_repository.update(category)

    # --------------------------------------------------

    def reactivate_category(self, category_id):

        category = self.category_repository.get(category_id)
        if category is None:
            raise ValueError("Category not found.")
        category.active = True
        return self.category_repository.update(category)

    # --------------------------------------------------

    def update_category(self, transaction_id, category, actor=""):

        transaction = self.repository.get(transaction_id)
        if transaction is None:
            raise ValueError("Transaction not found.")
        old_value = transaction.category
        if old_value != category:
            self.record_edit(transaction_id, "category", old_value, category, actor)
        transaction.category = category
        return self.repository.update(transaction)

    # --------------------------------------------------
    # Audit trail + undo
    # --------------------------------------------------

    def record_edit(self, transaction_id, field_name, old_value, new_value, actor):
        """Appends one row to ledger_transaction_edits - the audit trail,
        and the mechanism behind Undo (see undo_last_edit). Values are
        stored as plain strings."""

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self.repository.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO ledger_transaction_edits
                    (id, transaction_id, field_name, old_value, new_value, undone, edited_at, edited_by)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (str(uuid4()), transaction_id, field_name, str(old_value), str(new_value), now, actor),
            )

    # --------------------------------------------------

    def undo_last_edit(self, actor):
        """Finds the most recent un-undone edit (across all
        transactions), reverts that field back to old_value, marks it
        undone, and logs the revert itself as a new append-only edit
        row (never mutates a past edit row's old_value/new_value).
        Returns {transaction_id, field_name, reverted_to} for the UI.
        Raises ValueError if there's nothing to undo."""

        with self.repository.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM ledger_transaction_edits WHERE undone = 0 ORDER BY edited_at DESC, rowid DESC LIMIT 1",
            ).fetchone()

        if row is None:
            raise ValueError("Nothing to undo.")

        transaction_id = row["transaction_id"]
        field_name = row["field_name"]
        old_value = row["old_value"]
        new_value = row["new_value"]

        transaction = self.repository.get(transaction_id)
        if transaction is None:
            raise ValueError("The transaction for this edit no longer exists.")

        if field_name == "amount_minor":
            transaction.amount_minor = int(old_value)
        elif field_name == "category":
            transaction.category = old_value
        elif field_name == "description":
            transaction.description = old_value
        elif field_name == "date":
            transaction.date = old_value
        elif field_name == "account":
            transaction.account = old_value
        elif field_name == "receipt_filename":
            self.repository.set_receipt_filename(transaction_id, old_value)
        else:
            raise ValueError(f"Don't know how to undo field '{field_name}'.")

        if field_name != "receipt_filename":
            self.repository.update(transaction)

        with self.repository.db.connect() as connection:
            connection.execute(
                "UPDATE ledger_transaction_edits SET undone = 1 WHERE id = ?", (row["id"],),
            )

        # Log the revert itself, append-only - old_value is the value
        # that was just reverted away FROM (new_value on the original
        # row), new_value is the restored value.
        self.record_edit(transaction_id, field_name, new_value, old_value, actor)

        return {"transaction_id": transaction_id, "field_name": field_name, "reverted_to": old_value}

    # --------------------------------------------------
    # Receipt attachment
    # --------------------------------------------------

    def attach_receipt(self, transaction_id, source_filepath, actor):

        import shutil
        import uuid as uuid_module
        from pathlib import Path as _Path

        from modules.documents.services import DocumentsRepository

        transaction = self.repository.get(transaction_id)
        if transaction is None:
            raise ValueError("Transaction not found.")

        source_path = _Path(source_filepath)
        if not source_path.is_file():
            raise FileNotFoundError(f"No such file: {source_path}")

        receipts_dir = DocumentsRepository().get_documents_root() / "Ledger Receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)

        destination = receipts_dir / source_path.name
        if destination.exists():
            destination = receipts_dir / f"{transaction_id[:8]}_{uuid_module.uuid4().hex[:8]}_{source_path.name}"

        shutil.copy2(source_path, destination)

        old_value = transaction.receipt_filename
        self.record_edit(transaction_id, "receipt_filename", old_value, destination.name, actor)
        self.repository.set_receipt_filename(transaction_id, destination.name)

        return destination.name

    # --------------------------------------------------

    def get_receipt_path(self, transaction_id):

        from modules.documents.services import DocumentsRepository

        transaction = self.repository.get(transaction_id)
        if transaction is None or not transaction.receipt_filename:
            return None
        return DocumentsRepository().get_documents_root() / "Ledger Receipts" / transaction.receipt_filename

    # --------------------------------------------------

    def delete_transaction(self, transaction_id):

        self.repository.delete(transaction_id)

    # --------------------------------------------------
    # Reporting
    # --------------------------------------------------

    def get_summary(self, date_from=None, date_to=None, account=None):

        filters = {}
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to
        if account:
            filters["account"] = account

        transactions = self.repository.list_all(filters)
        real_transactions = [t for t in transactions if t.category not in TRANSFER_LIKE_CATEGORIES]

        total_income = sum(t.amount_minor for t in real_transactions if t.transaction_type == INCOME)
        total_expenses = sum(t.amount_minor for t in real_transactions if t.transaction_type == EXPENSE)

        by_category = {}
        by_month = {}
        for t in transactions:
            category_key = f"{t.transaction_type}/{t.category or '(Uncategorized)'}"
            by_category[category_key] = by_category.get(category_key, 0) + t.amount_minor

            if t.category in TRANSFER_LIKE_CATEGORIES:
                continue
            month_key = t.date[:7] if len(t.date) >= 7 else "Unknown"
            month_bucket = by_month.setdefault(month_key, {"Income": 0, "Expense": 0})
            month_bucket[t.transaction_type] += t.amount_minor

        return {
            "transaction_count": len(transactions),
            "total_income_minor": total_income,
            "total_expenses_minor": total_expenses,
            "net_profit_minor": total_income - total_expenses,
            "by_category": by_category,
            "by_month": dict(sorted(by_month.items())),
        }
