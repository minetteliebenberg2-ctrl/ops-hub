# ==========================================================
# FC Hub - Site Visit Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for site_visits - mirrors SiteRepository's pattern
# (core/crm_repository.py) exactly.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime

from core.database import database
from core.site_visit import SiteVisit


class SiteVisitRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def save(self, visit):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO site_visits (
                    id, customer_id, site_id, visit_date, visit_time, notes,
                    status, created_at, updated_at, created_by, updated_by,
                    measurements_json, checklist_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    customer_id = excluded.customer_id,
                    site_id = excluded.site_id,
                    visit_date = excluded.visit_date,
                    visit_time = excluded.visit_time,
                    notes = excluded.notes,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by,
                    measurements_json = excluded.measurements_json,
                    checklist_json = excluded.checklist_json
                """,
                (
                    visit.id,
                    visit.customer_id,
                    visit.site_id or None,
                    visit.visit_date,
                    visit.visit_time,
                    visit.notes,
                    visit.status,
                    visit.created_at,
                    visit.updated_at,
                    visit.created_by,
                    visit.updated_by,
                    visit.measurements_json or "{}",
                    visit.checklist_json or "{}",
                ),
            )

        return visit

    # --------------------------------------------------

    def get(self, visit_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM site_visits WHERE id = ?", (visit_id,),
            ).fetchone()

        return self._to_visit(row) if row else None

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM site_visits
                WHERE customer_id = ?
                ORDER BY visit_date, visit_time
                """,
                (customer_id,),
            ).fetchall()

        return [self._to_visit(row) for row in rows]

    # --------------------------------------------------

    def list_all(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM site_visits ORDER BY visit_date, visit_time"
            ).fetchall()

        return [self._to_visit(row) for row in rows]

    # --------------------------------------------------

    def archive(self, visit_id, actor, reason):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE site_visits
                SET archived_at = ?, archived_by = ?, archive_reason = ?,
                    updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, reason, self._timestamp(), actor, visit_id),
            )

    # --------------------------------------------------

    def reactivate(self, visit_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE site_visits
                SET archived_at = NULL, archived_by = NULL, archive_reason = '',
                    updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, visit_id),
            )

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def _to_visit(self, row):

        return SiteVisit(
            id=row["id"],
            customer_id=row["customer_id"],
            site_id=row["site_id"] or "",
            visit_date=row["visit_date"],
            visit_time=row["visit_time"],
            notes=row["notes"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"] or "",
            updated_by=row["updated_by"] or "",
            archived_at=row["archived_at"] or "",
            archived_by=row["archived_by"] or "",
            archive_reason=row["archive_reason"] or "",
            measurements_json=row["measurements_json"] if "measurements_json" in row.keys() else "{}",
            checklist_json=row["checklist_json"] if "checklist_json" in row.keys() else "{}",
        )
