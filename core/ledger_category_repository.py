# ==========================================================
# FC Hub - Ledger Category Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for self-service ledger categories (ledger_categories
# table, migration v0020) - lets Minette add/rename/retire her own
# categories from Settings instead of a code change.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime, timezone
from uuid import uuid4

from core.database import database
from core.ledger_category import LedgerCategory


class LedgerCategoryRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def create(self, category):

        now = self._timestamp()
        if not category.id:
            category.id = str(uuid4())
        category.created_at = category.created_at or now
        category.updated_at = now

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO ledger_categories (
                    id, name, category_type, active, created_at, updated_at, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category.id, category.name, category.category_type,
                    1 if category.active else 0, category.created_at,
                    category.updated_at, category.created_by,
                ),
            )
        return category

    # --------------------------------------------------

    def get(self, category_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM ledger_categories WHERE id = ?", (category_id,),
            ).fetchone()
        return self._to_category(row) if row else None

    # --------------------------------------------------

    def get_by_name(self, name):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM ledger_categories WHERE name = ?", (name,),
            ).fetchone()
        return self._to_category(row) if row else None

    # --------------------------------------------------

    def list_all(self, category_type=None, active_only=True):

        query = "SELECT * FROM ledger_categories WHERE 1=1"
        params = []
        if category_type:
            query += " AND category_type = ?"
            params.append(category_type)
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY name"

        with self.db.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._to_category(row) for row in rows]

    # --------------------------------------------------

    def update(self, category):

        category.updated_at = self._timestamp()
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE ledger_categories
                SET name = ?, category_type = ?, active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    category.name, category.category_type,
                    1 if category.active else 0, category.updated_at, category.id,
                ),
            )
        return category

    # --------------------------------------------------

    def _to_category(self, row):

        return LedgerCategory(
            id=row["id"],
            name=row["name"],
            category_type=row["category_type"],
            active=bool(row["active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
        )

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
