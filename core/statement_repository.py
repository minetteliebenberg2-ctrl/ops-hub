# ==========================================================
# FC Hub - Statement Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for per-customer, per-period Statements and the
# Tax Invoices each one references.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime, timezone
from uuid import uuid4

from core.database import database
from core.numbering_service import NumberingService
from core.statement import Statement


class StatementRepository:

    def __init__(self, db=None, numbering_service=None):

        self.db = db or database
        self.db.initialize()
        self.numbering = numbering_service or NumberingService()

    # --------------------------------------------------

    def create(self, customer_id, period_start, period_end, notes, currency, total_minor, invoice_document_ids, actor):

        with self.db.connect() as connection:
            cust_row = connection.execute(
                "SELECT customer_number FROM customers WHERE id = ?",
                (customer_id,),
            ).fetchone()
            cust_prefix = cust_row["customer_number"].split("-")[0] if cust_row and cust_row["customer_number"] else ""
            prefix = f"{cust_prefix}-STA" if cust_prefix else "STA"
            document_number = self.numbering.allocate_yearly(
                connection,
                "statement",
                scope_id=customer_id,
                prefix=prefix,
                padding=3,
            )

            now = self._timestamp()
            statement = Statement(
                id=str(uuid4()),
                customer_id=customer_id,
                document_number=document_number,
                period_start=period_start,
                period_end=period_end,
                notes=notes,
                currency=currency,
                total_minor=total_minor,
                created_at=now,
                updated_at=now,
                created_by=actor,
            )

            connection.execute(
                """
                INSERT INTO statements (
                    id, customer_id, document_number, period_start, period_end,
                    notes, currency, total_minor, created_at, updated_at, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    statement.id, statement.customer_id, statement.document_number,
                    statement.period_start, statement.period_end, statement.notes,
                    statement.currency, statement.total_minor,
                    statement.created_at, statement.updated_at, statement.created_by,
                ),
            )

            for document_id in invoice_document_ids:
                connection.execute(
                    "INSERT INTO statement_line_items (id, statement_id, quote_document_id) VALUES (?, ?, ?)",
                    (str(uuid4()), statement.id, document_id),
                )

        return statement

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM statements WHERE customer_id = ? ORDER BY period_start",
                (customer_id,),
            ).fetchall()
        return [self._to_statement(row) for row in rows]

    # --------------------------------------------------

    def _to_statement(self, row):

        return Statement(
            id=row["id"],
            customer_id=row["customer_id"],
            document_number=row["document_number"],
            period_start=row["period_start"],
            period_end=row["period_end"],
            notes=row["notes"],
            currency=row["currency"],
            total_minor=row["total_minor"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
        )

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
