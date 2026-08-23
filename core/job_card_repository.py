# ==========================================================
# FC Hub - Job Card Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for job_cards / job_card_entries, and Job Card
# numbering (same yearly per-customer scheme as Quote/Pro-Forma/
# Invoice/Statement - see core/quote_document_repository.py for
# the identical allocate-then-insert pattern this mirrors).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime, timezone
from uuid import uuid4

from core.database import database
from core.job_card import JobCard, JobCardEntry
from core.numbering_service import NumberingService

JOB_CARD_DOCUMENT_TYPE = "job_card"
JOB_CARD_PREFIX = "J"


class JobCardRepository:

    def __init__(self, db=None, numbering_service=None):

        self.db = db or database
        self.db.initialize()
        self.numbering = numbering_service or NumberingService()

    # --------------------------------------------------

    def create(self, customer_id, site_id, actor):
        """Allocate the next J_YY/NNN number for this customer and
        insert a new, empty (Open, no entries yet) Job Card - number
        allocation and insert happen on the same connection so they
        commit or roll back together."""

        with self.db.connect() as connection:
            job_card_number = self.numbering.allocate_yearly(
                connection, JOB_CARD_DOCUMENT_TYPE, scope_id=customer_id, prefix=JOB_CARD_PREFIX, padding=3,
            )

            now = self._timestamp()
            job_card = JobCard(
                id=str(uuid4()),
                customer_id=customer_id,
                site_id=site_id,
                job_card_number=job_card_number,
                created_at=now,
                updated_at=now,
                created_by=actor,
                updated_by=actor,
            )

            connection.execute(
                """
                INSERT INTO job_cards (
                    id, customer_id, site_id, job_card_number, purchase_order,
                    bill_to_name, delivery_address, status, notes,
                    created_at, updated_at, created_by, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_card.id, job_card.customer_id, job_card.site_id, job_card.job_card_number,
                    job_card.purchase_order, job_card.bill_to_name, job_card.delivery_address,
                    job_card.status, job_card.notes, job_card.created_at, job_card.updated_at,
                    job_card.created_by, job_card.updated_by,
                ),
            )

        return job_card

    # --------------------------------------------------

    def save(self, job_card, actor):
        """Update the editable fields only - job_card_number is
        allocated once at creation and never changes."""

        job_card.updated_at = self._timestamp()
        job_card.updated_by = actor

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE job_cards
                SET purchase_order = ?, bill_to_name = ?, delivery_address = ?,
                    status = ?, notes = ?, updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (
                    job_card.purchase_order, job_card.bill_to_name, job_card.delivery_address,
                    job_card.status, job_card.notes, job_card.updated_at, job_card.updated_by,
                    job_card.id,
                ),
            )

        return job_card

    # --------------------------------------------------

    def get(self, job_card_id):

        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM job_cards WHERE id = ?", (job_card_id,)).fetchone()

        return self._to_job_card(row) if row else None

    # --------------------------------------------------

    def list_for_site(self, site_id):
        """Everything for this site, archived included - matching every
        other list method in this app (e.g. SiteRepository.list_for_customer),
        the archived filter is applied by the window, not the repository."""

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM job_cards WHERE site_id = ? ORDER BY created_at DESC", (site_id,),
            ).fetchall()

        return [self._to_job_card(row) for row in rows]

    # --------------------------------------------------

    def list_for_customer(self, customer_id):
        """All job cards for a customer across all sites, most recent first."""

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM job_cards WHERE customer_id = ? ORDER BY created_at DESC",
                (customer_id,),
            ).fetchall()

        return [self._to_job_card(row) for row in rows]

    # --------------------------------------------------

    def archive(self, job_card_id, actor, reason):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE job_cards
                SET archived_at = ?, archived_by = ?, archive_reason = ?, updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, reason, self._timestamp(), actor, job_card_id),
            )

    # --------------------------------------------------

    def reactivate(self, job_card_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE job_cards
                SET archived_at = NULL, archived_by = NULL, archive_reason = '', updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, job_card_id),
            )

    # --------------------------------------------------
    # Entries
    # --------------------------------------------------

    def save_entry(self, entry):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO job_card_entries (
                    id, job_card_id, entry_date, work_type, job_summary, description,
                    staff, completed, director_signoff, sort_order, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    entry_date = excluded.entry_date,
                    work_type = excluded.work_type,
                    job_summary = excluded.job_summary,
                    description = excluded.description,
                    staff = excluded.staff,
                    completed = excluded.completed,
                    director_signoff = excluded.director_signoff,
                    sort_order = excluded.sort_order,
                    updated_at = excluded.updated_at
                """,
                (
                    entry.id, entry.job_card_id, entry.entry_date, entry.work_type, entry.job_summary,
                    entry.description, entry.staff, int(entry.completed), entry.director_signoff,
                    entry.sort_order, entry.created_at, entry.updated_at,
                ),
            )

        return entry

    # --------------------------------------------------

    def list_entries_for_card(self, job_card_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM job_card_entries WHERE job_card_id = ? ORDER BY entry_date, sort_order",
                (job_card_id,),
            ).fetchall()

        return [self._to_entry(row) for row in rows]

    # --------------------------------------------------

    def delete_entry(self, entry_id):

        with self.db.connect() as connection:
            connection.execute("DELETE FROM job_card_entries WHERE id = ?", (entry_id,))

    # --------------------------------------------------

    def _to_job_card(self, row):

        return JobCard(
            id=row["id"],
            customer_id=row["customer_id"],
            site_id=row["site_id"],
            job_card_number=row["job_card_number"],
            purchase_order=row["purchase_order"],
            bill_to_name=row["bill_to_name"],
            delivery_address=row["delivery_address"],
            status=row["status"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"] or "",
            updated_by=row["updated_by"] or "",
            archived_at=row["archived_at"] or "",
            archived_by=row["archived_by"] or "",
            archive_reason=row["archive_reason"] or "",
        )

    # --------------------------------------------------

    def _to_entry(self, row):

        return JobCardEntry(
            id=row["id"],
            job_card_id=row["job_card_id"],
            entry_date=row["entry_date"],
            work_type=row["work_type"],
            job_summary=row["job_summary"],
            description=row["description"],
            staff=row["staff"],
            completed=bool(row["completed"]),
            director_signoff=row["director_signoff"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # --------------------------------------------------

    @staticmethod
    def _timestamp():

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
