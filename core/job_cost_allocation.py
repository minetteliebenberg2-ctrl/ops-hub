from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from core.database import database

INCOME = "Income"
EXPENSE = "Expense"


@dataclass
class JobCostAllocation:
    id: str = ""
    job_card_id: str = ""
    ledger_transaction_id: str = ""
    allocation_type: str = ""
    description: str = ""
    amount_minor: int = 0
    cost_bucket: str = ""
    date: str = ""
    notes: str = ""
    created_at: str = ""
    created_by: str = ""


class JobCostAllocationRepository:

    def __init__(self, db=None):
        self.db = db or database
        self.db.initialize()

    def save(self, alloc, actor=""):
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not alloc.id:
            alloc.id = str(uuid4())
        alloc.created_at = alloc.created_at or now
        alloc.created_by = alloc.created_by or actor
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO job_cost_allocations
                   (id, job_card_id, ledger_transaction_id, allocation_type,
                    description, amount_minor, cost_bucket, date, notes,
                    created_at, created_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                    description=?, amount_minor=?, cost_bucket=?, date=?, notes=?""",
                (alloc.id, alloc.job_card_id, alloc.ledger_transaction_id or None,
                 alloc.allocation_type, alloc.description, alloc.amount_minor,
                 alloc.cost_bucket, alloc.date, alloc.notes,
                 alloc.created_at, alloc.created_by,
                 alloc.description, alloc.amount_minor, alloc.cost_bucket,
                 alloc.date, alloc.notes),
            )
        return alloc

    def list_for_job(self, job_card_id):
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM job_cost_allocations WHERE job_card_id=? ORDER BY date, created_at",
                (job_card_id,),
            ).fetchall()
        return [self._to(r) for r in rows]

    def delete(self, alloc_id):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM job_cost_allocations WHERE id=?", (alloc_id,))

    def summary_for_job(self, job_card_id):
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT allocation_type, cost_bucket,
                          SUM(amount_minor) as total
                   FROM job_cost_allocations
                   WHERE job_card_id=?
                   GROUP BY allocation_type, cost_bucket""",
                (job_card_id,),
            ).fetchall()
        income = 0
        expenses = {}
        for r in rows:
            if r["allocation_type"] == INCOME:
                income += r["total"]
            else:
                bucket = r["cost_bucket"] or "other"
                expenses[bucket] = expenses.get(bucket, 0) + r["total"]
        return income, expenses

    def summary_all_jobs(self):
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT job_card_id, allocation_type,
                          SUM(amount_minor) as total
                   FROM job_cost_allocations
                   GROUP BY job_card_id, allocation_type""",
            ).fetchall()
        jobs = {}
        for r in rows:
            jid = r["job_card_id"]
            if jid not in jobs:
                jobs[jid] = {"income": 0, "expense": 0}
            if r["allocation_type"] == INCOME:
                jobs[jid]["income"] += r["total"]
            else:
                jobs[jid]["expense"] += r["total"]
        return jobs

    @staticmethod
    def _to(row):
        return JobCostAllocation(
            id=row["id"],
            job_card_id=row["job_card_id"],
            ledger_transaction_id=row["ledger_transaction_id"] or "",
            allocation_type=row["allocation_type"],
            description=row["description"],
            amount_minor=row["amount_minor"],
            cost_bucket=row["cost_bucket"],
            date=row["date"],
            notes=row["notes"],
            created_at=row["created_at"],
            created_by=row["created_by"],
        )
