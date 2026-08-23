# ==========================================================
# FC Hub - Ledger Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for general ledger transactions (personal + business).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime, timezone
from uuid import uuid4

from core.database import database
from core.ledger_transaction import LedgerTransaction


class LedgerTransactionRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def create(self, transaction):

        now = self._timestamp()
        if not transaction.id:
            transaction.id = str(uuid4())
        transaction.created_at = transaction.created_at or now
        transaction.updated_at = now

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO ledger_transactions (
                    id, date, description, amount_minor, transaction_type,
                    category, account, reference, notes, source, import_batch,
                    created_at, updated_at, created_by, receipt_filename
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction.id, transaction.date, transaction.description,
                    transaction.amount_minor, transaction.transaction_type,
                    transaction.category, transaction.account, transaction.reference,
                    transaction.notes, transaction.source, transaction.import_batch,
                    transaction.created_at, transaction.updated_at, transaction.created_by,
                    transaction.receipt_filename,
                ),
            )

        return transaction

    # --------------------------------------------------

    def bulk_create(self, transactions):

        return [self.create(transaction) for transaction in transactions]

    # --------------------------------------------------

    def get(self, transaction_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM ledger_transactions WHERE id = ?", (transaction_id,),
            ).fetchone()
        return self._to_transaction(row) if row else None

    # --------------------------------------------------

    def list_all(self, filters=None):

        query = "SELECT * FROM ledger_transactions WHERE 1=1"
        params = []

        filters = filters or {}
        if filters.get("account"):
            query += " AND account = ?"
            params.append(filters["account"])
        if filters.get("transaction_type"):
            query += " AND transaction_type = ?"
            params.append(filters["transaction_type"])
        if filters.get("category"):
            query += " AND category = ?"
            params.append(filters["category"])
        if filters.get("date_from"):
            query += " AND date >= ?"
            params.append(filters["date_from"])
        if filters.get("date_to"):
            query += " AND date <= ?"
            params.append(filters["date_to"])

        query += " ORDER BY date DESC, created_at DESC"

        with self.db.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._to_transaction(row) for row in rows]

    # --------------------------------------------------

    def list_for_account(self, account):
        """Every imported (non-manual) row for this account - used for
        import de-duplication, regardless of which importer (bank
        statement or ledger audit) the row originally came from."""

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ledger_transactions WHERE account = ? AND source != 'Manual'",
                (account,),
            ).fetchall()
        return [self._to_transaction(row) for row in rows]

    # --------------------------------------------------

    def list_accounts(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT account FROM ("
                "  SELECT account FROM ledger_transactions WHERE account != '' AND account IS NOT NULL"
                "  UNION"
                "  SELECT name AS account FROM bank_accounts"
                ") ORDER BY account",
            ).fetchall()
        return [row["account"] for row in rows]

    def add_account(self, name):

        with self.db.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO bank_accounts (name) VALUES (?)", (name,),
            )

    def delete_account(self, name):

        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM bank_accounts WHERE name = ?", (name,),
            )

    # --------------------------------------------------

    def list_categories(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT category FROM ledger_transactions WHERE category != '' ORDER BY category",
            ).fetchall()
        return [row["category"] for row in rows]

    # --------------------------------------------------

    def update(self, transaction):

        transaction.updated_at = self._timestamp()
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE ledger_transactions
                SET date = ?, description = ?, amount_minor = ?, transaction_type = ?,
                    category = ?, account = ?, reference = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    transaction.date, transaction.description, transaction.amount_minor,
                    transaction.transaction_type, transaction.category, transaction.account,
                    transaction.reference, transaction.notes, transaction.updated_at,
                    transaction.id,
                ),
            )
        return transaction

    # --------------------------------------------------

    def delete(self, transaction_id):

        with self.db.connect() as connection:
            connection.execute("DELETE FROM ledger_transactions WHERE id = ?", (transaction_id,))

    # --------------------------------------------------

    def set_receipt_filename(self, transaction_id, receipt_filename):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE ledger_transactions SET receipt_filename = ?, updated_at = ? WHERE id = ?",
                (receipt_filename, self._timestamp(), transaction_id),
            )

    # --------------------------------------------------

    def _to_transaction(self, row):

        return LedgerTransaction(
            id=row["id"],
            date=row["date"],
            description=row["description"],
            amount_minor=row["amount_minor"],
            transaction_type=row["transaction_type"],
            category=row["category"],
            account=row["account"],
            reference=row["reference"],
            notes=row["notes"],
            source=row["source"],
            import_batch=row["import_batch"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            receipt_filename=row["receipt_filename"] if "receipt_filename" in row.keys() else "",
        )

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
