# ==========================================================
# FC Hub - Supplier Pricing Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for supplier_price_items.
#
# Author: Minette & Claude
# Version: 1.0
# ==========================================================

from core.database import database
from core.supplier_pricing import SupplierPriceItem


CATEGORIES = ("Steel", "Netting", "Paint", "Hardware", "Labour")


class SupplierPriceItemRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def next_sort_order(self, category):

        with self.db.connect() as connection:
            value = connection.execute(
                "SELECT MAX(sort_order) FROM supplier_price_items WHERE category = ?",
                (category,),
            ).fetchone()[0]

        return (value or 0) + 1

    # --------------------------------------------------

    def list_for_category(self, category, include_inactive=False):

        query = "SELECT * FROM supplier_price_items WHERE category = ?"
        params = [category]

        if not include_inactive:
            query += " AND is_active = 1"

        query += " ORDER BY sort_order, item_name COLLATE NOCASE, supplier_name COLLATE NOCASE"

        with self.db.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._to_item(row) for row in rows]

    # --------------------------------------------------

    def get(self, item_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM supplier_price_items WHERE id = ?",
                (item_id,),
            ).fetchone()

        return self._to_item(row) if row else None

    # --------------------------------------------------

    def save(self, item):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO supplier_price_items (
                    id, category, item_name, supplier_name, spec, unit,
                    cost_minor, sort_order, is_active, created_at, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    category = excluded.category,
                    item_name = excluded.item_name,
                    supplier_name = excluded.supplier_name,
                    spec = excluded.spec,
                    unit = excluded.unit,
                    cost_minor = excluded.cost_minor,
                    sort_order = excluded.sort_order,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    item.id,
                    item.category,
                    item.item_name,
                    item.supplier_name,
                    item.spec,
                    item.unit,
                    item.cost_minor,
                    item.sort_order,
                    1 if item.is_active else 0,
                    item.created_at,
                    item.updated_at,
                    item.updated_by,
                ),
            )

        return item

    # --------------------------------------------------

    def set_active(self, item_id, is_active, actor):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE supplier_price_items
                SET is_active = ?, updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (1 if is_active else 0, self._timestamp(), actor, item_id),
            )

    # --------------------------------------------------

    def delete(self, item_id):

        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM supplier_price_items WHERE id = ?",
                (item_id,),
            )

    # --------------------------------------------------

    def _timestamp(self):

        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def _to_item(self, row):

        return SupplierPriceItem(
            id=row["id"],
            category=row["category"],
            item_name=row["item_name"],
            supplier_name=row["supplier_name"],
            spec=row["spec"],
            unit=row["unit"],
            cost_minor=row["cost_minor"],
            sort_order=row["sort_order"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
        )
