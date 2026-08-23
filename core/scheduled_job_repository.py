from datetime import datetime

from core.database import database
from core.scheduled_job import ScheduledJob


class ScheduledJobRepository:

    def __init__(self, db=None):
        self.db = db or database
        self.db.initialize()

    def save(self, job):
        with self.db.connect() as con:
            con.execute(
                """INSERT INTO scheduled_jobs
                   (id, customer_id, site_id, quote_id, job_card_id, title,
                    description, status, start_date, end_date, assigned_to,
                    notes, created_at, updated_at, created_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     title=excluded.title, description=excluded.description,
                     status=excluded.status, start_date=excluded.start_date,
                     end_date=excluded.end_date, assigned_to=excluded.assigned_to,
                     notes=excluded.notes, updated_at=excluded.updated_at""",
                (job.id, job.customer_id, job.site_id, job.quote_id,
                 job.job_card_id, job.title, job.description, job.status,
                 job.start_date, job.end_date, job.assigned_to, job.notes,
                 job.created_at, job.updated_at, job.created_by),
            )
        return job

    def get(self, job_id):
        with self.db.connect() as con:
            row = con.execute("SELECT * FROM scheduled_jobs WHERE id = ?", (job_id,)).fetchone()
        return self._to_obj(row) if row else None

    def list_all(self):
        with self.db.connect() as con:
            rows = con.execute("SELECT * FROM scheduled_jobs ORDER BY start_date").fetchall()
        return [self._to_obj(r) for r in rows]

    def list_for_month(self, year_month):
        with self.db.connect() as con:
            rows = con.execute(
                "SELECT * FROM scheduled_jobs WHERE start_date LIKE ? ORDER BY start_date",
                (f"{year_month}%",),
            ).fetchall()
        return [self._to_obj(r) for r in rows]

    def list_for_customer(self, customer_id):
        with self.db.connect() as con:
            rows = con.execute(
                "SELECT * FROM scheduled_jobs WHERE customer_id = ? ORDER BY start_date",
                (customer_id,),
            ).fetchall()
        return [self._to_obj(r) for r in rows]

    def delete(self, job_id):
        with self.db.connect() as con:
            con.execute("DELETE FROM scheduled_jobs WHERE id = ?", (job_id,))

    def _to_obj(self, row):
        return ScheduledJob(
            id=row["id"],
            customer_id=row["customer_id"],
            site_id=row["site_id"] or "",
            quote_id=row["quote_id"] or "",
            job_card_id=row["job_card_id"] or "",
            title=row["title"],
            description=row["description"],
            status=row["status"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            assigned_to=row["assigned_to"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"] or "",
        )
