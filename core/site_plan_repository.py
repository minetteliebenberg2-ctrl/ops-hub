# ==========================================================
# FC Hub - Site Plan Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for site_plans / site_plan_items - mirrors
# SiteVisitRepository's pattern (core/site_visit_repository.py).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime

from core.database import database
from core.site_plan import PORTRAIT, SitePlan, SitePlanItem


class SitePlanRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def save(self, plan):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO site_plans (
                    id, site_id, backdrop_filename, backdrop_width, backdrop_height,
                    grid_orientation, created_at, updated_at, created_by, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    backdrop_filename = excluded.backdrop_filename,
                    backdrop_width = excluded.backdrop_width,
                    backdrop_height = excluded.backdrop_height,
                    grid_orientation = excluded.grid_orientation,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    plan.id,
                    plan.site_id,
                    plan.backdrop_filename,
                    plan.backdrop_width,
                    plan.backdrop_height,
                    plan.grid_orientation,
                    plan.created_at,
                    plan.updated_at,
                    plan.created_by,
                    plan.updated_by,
                ),
            )

        return plan

    # --------------------------------------------------

    def get(self, plan_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM site_plans WHERE id = ?", (plan_id,),
            ).fetchone()

        return self._to_plan(row) if row else None

    # --------------------------------------------------

    def get_for_site(self, site_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM site_plans WHERE site_id = ?", (site_id,),
            ).fetchone()

        return self._to_plan(row) if row else None

    # --------------------------------------------------

    def save_item(self, item):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO site_plan_items (
                    id, site_plan_id, x, y, width, height, rotation,
                    structure_type, car_bays, description, quantity, unit_price_minor,
                    sort_order, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    x = excluded.x,
                    y = excluded.y,
                    width = excluded.width,
                    height = excluded.height,
                    rotation = excluded.rotation,
                    structure_type = excluded.structure_type,
                    car_bays = excluded.car_bays,
                    description = excluded.description,
                    quantity = excluded.quantity,
                    unit_price_minor = excluded.unit_price_minor,
                    sort_order = excluded.sort_order,
                    updated_at = excluded.updated_at
                """,
                (
                    item.id,
                    item.site_plan_id,
                    item.x,
                    item.y,
                    item.width,
                    item.height,
                    item.rotation,
                    item.structure_type,
                    item.car_bays,
                    item.description,
                    item.quantity,
                    item.unit_price_minor,
                    item.sort_order,
                    item.created_at,
                    item.updated_at,
                ),
            )

        return item

    # --------------------------------------------------

    def list_items_for_plan(self, site_plan_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM site_plan_items WHERE site_plan_id = ? ORDER BY sort_order",
                (site_plan_id,),
            ).fetchall()

        return [self._to_item(row) for row in rows]

    # --------------------------------------------------

    def delete_item(self, item_id):

        with self.db.connect() as connection:
            connection.execute("DELETE FROM site_plan_items WHERE id = ?", (item_id,))

    # --------------------------------------------------

    def _to_plan(self, row):

        return SitePlan(
            id=row["id"],
            site_id=row["site_id"],
            backdrop_filename=row["backdrop_filename"],
            backdrop_width=row["backdrop_width"],
            backdrop_height=row["backdrop_height"],
            grid_orientation=row["grid_orientation"] or PORTRAIT,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"] or "",
            updated_by=row["updated_by"] or "",
        )

    # --------------------------------------------------

    def _to_item(self, row):

        return SitePlanItem(
            id=row["id"],
            site_plan_id=row["site_plan_id"],
            x=row["x"],
            y=row["y"],
            width=row["width"],
            height=row["height"],
            rotation=row["rotation"] or 0.0,
            structure_type=row["structure_type"],
            car_bays=row["car_bays"],
            description=row["description"],
            quantity=row["quantity"],
            unit_price_minor=row["unit_price_minor"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
