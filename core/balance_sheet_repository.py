# ==========================================================
# FC Hub - Balance Sheet Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for the balance-sheet chart of accounts and the
# opening balances Minette maintains per financial year.
#
# See migration v0040 for why these are entered rather than
# derived: the ledger is single-entry, so it does not carry the
# other side of a transaction.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from core.database import database

ASSET = "Asset"
LIABILITY = "Liability"
EQUITY = "Equity"

ACCOUNT_TYPES = (ASSET, LIABILITY, EQUITY)


@dataclass
class BalanceSheetAccount:

    id: str = ""
    code: str = ""
    name: str = ""
    account_type: str = ASSET
    statement_group: str = ""
    ledger_account: str = ""
    is_cash: int = 0
    sort_order: int = 0
    is_active: int = 1
    created_at: str = ""
    updated_at: str = ""
    updated_by: str = ""


class BalanceSheetRepository:

    def __init__(self, db=None):
        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _to_account(row):
        return BalanceSheetAccount(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            account_type=row["account_type"],
            statement_group=row["statement_group"],
            ledger_account=row["ledger_account"],
            is_cash=row["is_cash"],
            sort_order=row["sort_order"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
        )

    # --------------------------------------------------
    # Accounts
    # --------------------------------------------------

    def list_accounts(self, active_only=True):
        query = "SELECT * FROM balance_sheet_accounts"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY sort_order, code"

        with self.db.connect() as connection:
            rows = connection.execute(query).fetchall()
        return [self._to_account(row) for row in rows]

    def get_account(self, account_id):
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM balance_sheet_accounts WHERE id = ?", (account_id,)
            ).fetchone()
        return self._to_account(row) if row else None

    def save_account(self, account, actor=""):
        """Insert or update. Generates the id on create - callers must go
        through here rather than writing the table directly."""

        now = self._timestamp()
        if not account.id:
            account.id = str(uuid4())
            account.created_at = now
            account.updated_at = now
            account.updated_by = actor
            with self.db.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO balance_sheet_accounts (
                        id, code, name, account_type, statement_group,
                        ledger_account, is_cash, sort_order, is_active,
                        created_at, updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account.id, account.code, account.name, account.account_type,
                        account.statement_group, account.ledger_account, int(account.is_cash),
                        account.sort_order, int(account.is_active),
                        account.created_at, account.updated_at, account.updated_by,
                    ),
                )
            return account

        account.updated_at = now
        account.updated_by = actor
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE balance_sheet_accounts
                   SET code = ?, name = ?, account_type = ?, statement_group = ?,
                       ledger_account = ?, is_cash = ?, sort_order = ?, is_active = ?,
                       updated_at = ?, updated_by = ?
                 WHERE id = ?
                """,
                (
                    account.code, account.name, account.account_type, account.statement_group,
                    account.ledger_account, int(account.is_cash), account.sort_order,
                    int(account.is_active), account.updated_at, account.updated_by, account.id,
                ),
            )
        return account

    def retire_account(self, account_id, actor=""):
        """Deactivate rather than delete - past years' statements still
        reference the account and should keep rendering."""

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE balance_sheet_accounts SET is_active = 0, updated_at = ?, updated_by = ? "
                "WHERE id = ?",
                (self._timestamp(), actor, account_id),
            )

    # --------------------------------------------------
    # Opening balances
    # --------------------------------------------------

    def opening_balance_minor(self, account_id, financial_year):
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT opening_balance_minor FROM balance_sheet_balances "
                "WHERE account_id = ? AND financial_year = ?",
                (account_id, financial_year),
            ).fetchone()
        return row["opening_balance_minor"] if row else 0

    def list_balances(self, financial_year):
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM balance_sheet_balances WHERE financial_year = ?",
                (financial_year,),
            ).fetchall()
        return {row["account_id"]: row["opening_balance_minor"] for row in rows}

    def set_opening_balance(self, account_id, financial_year, amount_minor, actor="", notes=""):
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO balance_sheet_balances (
                    id, account_id, financial_year, opening_balance_minor,
                    notes, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, financial_year) DO UPDATE SET
                    opening_balance_minor = excluded.opening_balance_minor,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    str(uuid4()), account_id, financial_year, int(amount_minor),
                    notes, self._timestamp(), actor,
                ),
            )
