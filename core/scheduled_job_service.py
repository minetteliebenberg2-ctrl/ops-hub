from datetime import datetime
from uuid import uuid4

from core.scheduled_job import ScheduledJob
from core.scheduled_job_repository import ScheduledJobRepository


class ScheduledJobService:

    def __init__(self, repo=None):
        self.repo = repo or ScheduledJobRepository()

    def create(self, customer_id, title, start_date, end_date="",
               site_id="", quote_id="", job_card_id="",
               assigned_to="", description="", notes="", actor=""):
        now = datetime.now().isoformat(timespec="seconds")
        job = ScheduledJob(
            id=str(uuid4()),
            customer_id=customer_id,
            site_id=site_id,
            quote_id=quote_id,
            job_card_id=job_card_id,
            title=title.strip(),
            description=description.strip(),
            status="Scheduled",
            start_date=start_date,
            end_date=end_date or start_date,
            assigned_to=assigned_to.strip(),
            notes=notes.strip(),
            created_at=now,
            updated_at=now,
            created_by=actor,
        )
        return self.repo.save(job)

    def update(self, job_id, **kwargs):
        job = self.repo.get(job_id)
        if job is None:
            raise ValueError("Scheduled job not found.")
        for key in ("title", "description", "status", "start_date", "end_date",
                     "assigned_to", "notes", "site_id", "quote_id", "job_card_id"):
            if key in kwargs:
                setattr(job, key, kwargs[key])
        job.updated_at = datetime.now().isoformat(timespec="seconds")
        return self.repo.save(job)

    def delete(self, job_id):
        self.repo.delete(job_id)

    def list_all(self):
        return self.repo.list_all()

    def list_for_month(self, year_month):
        return self.repo.list_for_month(year_month)

    def list_for_customer(self, customer_id):
        return self.repo.list_for_customer(customer_id)

    def get(self, job_id):
        return self.repo.get(job_id)
