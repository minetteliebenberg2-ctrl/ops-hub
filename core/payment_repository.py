# ==========================================================
# FC Hub - Payment Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for Payments and their PaymentAllocations against Tax
# Invoices (quote_documents).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime, timezone
from uuid import uuid4

from core.database import database
from core.payment import Payment
from core.payment_allocation import PaymentAllocation


class PaymentRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def create(self, customer_id, amount_minor, date, reference, notes, actor):

        now = self._timestamp()
        payment = Payment(
            id=str(uuid4()),
            customer_id=customer_id,
            amount_minor=amount_minor,
            date=date,
            reference=reference,
            notes=notes,
            created_at=now,
            updated_at=now,
            created_by=actor,
        )

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO payments (
                    id, customer_id, amount_minor, date, reference, notes,
                    status, created_at, updated_at, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payment.id, payment.customer_id, payment.amount_minor,
                    payment.date, payment.reference, payment.notes,
                    payment.status, payment.created_at, payment.updated_at,
                    payment.created_by,
                ),
            )

        return payment

    # --------------------------------------------------

    def get(self, payment_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM payments WHERE id = ?", (payment_id,),
            ).fetchone()
        return self._to_payment(row) if row else None

    # --------------------------------------------------

    def list_all(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM payments ORDER BY date DESC, created_at DESC",
            ).fetchall()
        return [self._to_payment(row) for row in rows]

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM payments WHERE customer_id = ? ORDER BY date DESC, created_at DESC",
                (customer_id,),
            ).fetchall()
        return [self._to_payment(row) for row in rows]

    # --------------------------------------------------

    def update_status(self, payment_id, status):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE payments SET status = ?, updated_at = ? WHERE id = ?",
                (status, self._timestamp(), payment_id),
            )

    # --------------------------------------------------

    def _to_payment(self, row):

        return Payment(
            id=row["id"],
            customer_id=row["customer_id"],
            amount_minor=row["amount_minor"],
            date=row["date"],
            reference=row["reference"],
            notes=row["notes"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
        )

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PaymentAllocationRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def create(self, payment_id, quote_document_id, amount_minor, notes, actor):

        allocation = PaymentAllocation(
            id=str(uuid4()),
            payment_id=payment_id,
            quote_document_id=quote_document_id,
            amount_minor=amount_minor,
            notes=notes,
            created_at=self._timestamp(),
            created_by=actor,
        )

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO payment_allocations (
                    id, payment_id, quote_document_id, amount_minor,
                    notes, created_at, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    allocation.id, allocation.payment_id, allocation.quote_document_id,
                    allocation.amount_minor, allocation.notes, allocation.created_at,
                    allocation.created_by,
                ),
            )

        return allocation

    # --------------------------------------------------

    def get(self, allocation_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM payment_allocations WHERE id = ?", (allocation_id,),
            ).fetchone()
        return self._to_allocation(row) if row else None

    # --------------------------------------------------

    def list_for_payment(self, payment_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM payment_allocations WHERE payment_id = ? ORDER BY created_at",
                (payment_id,),
            ).fetchall()
        return [self._to_allocation(row) for row in rows]

    # --------------------------------------------------

    def list_for_document(self, quote_document_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM payment_allocations WHERE quote_document_id = ? ORDER BY created_at",
                (quote_document_id,),
            ).fetchall()
        return [self._to_allocation(row) for row in rows]

    # --------------------------------------------------

    def sum_for_payment(self, payment_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(amount_minor), 0) AS total FROM payment_allocations WHERE payment_id = ?",
                (payment_id,),
            ).fetchone()
        return row["total"]

    # --------------------------------------------------

    def sum_for_document(self, quote_document_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(amount_minor), 0) AS total FROM payment_allocations WHERE quote_document_id = ?",
                (quote_document_id,),
            ).fetchone()
        return row["total"]

    # --------------------------------------------------

    def _to_allocation(self, row):

        return PaymentAllocation(
            id=row["id"],
            payment_id=row["payment_id"],
            quote_document_id=row["quote_document_id"],
            amount_minor=row["amount_minor"],
            notes=row["notes"],
            created_at=row["created_at"],
            created_by=row["created_by"],
        )

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
