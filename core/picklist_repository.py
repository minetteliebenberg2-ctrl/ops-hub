# ==========================================================
# FC Hub - Picklist Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for picklist_options.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from core.database import database
from core.picklist import PicklistOption


class PicklistOptionRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def next_sort_order(self, list_name):

        with self.db.connect() as connection:
            value = connection.execute(
                "SELECT MAX(sort_order) FROM picklist_options WHERE list_name = ?",
                (list_name,),
            ).fetchone()[0]

        return (value or 0) + 1

    # --------------------------------------------------

    def list_for(self, list_name, include_inactive=False):

        query = "SELECT * FROM picklist_options WHERE list_name = ?"
        params = [list_name]

        if not include_inactive:
            query += " AND is_active = 1"

        query += " ORDER BY sort_order, value COLLATE NOCASE"

        with self.db.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._to_option(row) for row in rows]

    # --------------------------------------------------

    def get(self, option_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM picklist_options WHERE id = ?",
                (option_id,),
            ).fetchone()

        return self._to_option(row) if row else None

    # --------------------------------------------------

    def save(self, option):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO picklist_options (
                    id, list_name, value, deposit_percentage,
                    balance_percentage, rate_low_minor, rate_standard_minor,
                    rate_high_minor, sort_order, is_active, created_at,
                    updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    value = excluded.value,
                    deposit_percentage = excluded.deposit_percentage,
                    balance_percentage = excluded.balance_percentage,
                    rate_low_minor = excluded.rate_low_minor,
                    rate_standard_minor = excluded.rate_standard_minor,
                    rate_high_minor = excluded.rate_high_minor,
                    sort_order = excluded.sort_order,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    option.id,
                    option.list_name,
                    option.value,
                    option.deposit_percentage,
                    option.balance_percentage,
                    option.rate_low_minor,
                    option.rate_standard_minor,
                    option.rate_high_minor,
                    option.sort_order,
                    1 if option.is_active else 0,
                    option.created_at,
                    option.updated_at,
                    option.updated_by,
                ),
            )

        return option

    # --------------------------------------------------

    def set_active(self, option_id, is_active, actor):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE picklist_options
                SET is_active = ?, updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (1 if is_active else 0, self._timestamp(), actor, option_id),
            )

    # --------------------------------------------------

    def delete(self, option_id):

        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM picklist_options WHERE id = ?",
                (option_id,),
            )

    # --------------------------------------------------

    def _timestamp(self):

        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def _to_option(self, row):

        return PicklistOption(
            id=row["id"],
            list_name=row["list_name"],
            value=row["value"],
            deposit_percentage=row["deposit_percentage"],
            balance_percentage=row["balance_percentage"],
            rate_low_minor=row["rate_low_minor"],
            rate_standard_minor=row["rate_standard_minor"],
            rate_high_minor=row["rate_high_minor"],
            sort_order=row["sort_order"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
        )
