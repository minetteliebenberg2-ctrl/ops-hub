# ==========================================================
# FC Hub - Quote Document Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for Pro-Forma / Tax Invoice documents generated
# from an issued Quote, and their per-customer, per-year numbering.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime, timezone
from uuid import uuid4

from core.database import database
from core.numbering_service import NumberingService
from core.quote_document import QuoteDocument


class QuoteDocumentRepository:

    def __init__(self, db=None, numbering_service=None):

        self.db = db or database
        self.db.initialize()
        self.numbering = numbering_service or NumberingService()

    # --------------------------------------------------

    def generate(self, quote, doc_type, prefix, issue_date, due_date, notes, actor, po_number="", vat_number="", registration_number="", bill_to_name=""):
        """Snapshot the given (issued) quote's totals into a new
        Pro-Forma/Tax Invoice, allocating its number in the same
        Q_/PF_/I_/STA_ family, scoped to the quote's customer and reset
        yearly."""

        with self.db.connect() as connection:
            document_number = self.numbering.allocate_yearly(
                connection,
                doc_type,
                scope_id=quote.customer_id,
                prefix=prefix,
                padding=3,
            )

            now = self._timestamp()
            document = QuoteDocument(
                id=str(uuid4()),
                quote_id=quote.id,
                customer_id=quote.customer_id,
                doc_type=doc_type,
                document_number=document_number,
                issue_date=issue_date,
                due_date=due_date,
                po_number=po_number,
                vat_number=vat_number,
                registration_number=registration_number,
                bill_to_name=bill_to_name,
                notes=notes,
                status="Issued",
                currency=quote.currency,
                subtotal_minor=quote.subtotal_minor,
                vat_minor=quote.vat_minor,
                total_minor=quote.total_minor,
                created_at=now,
                updated_at=now,
                created_by=actor,
            )

            connection.execute(
                """
                INSERT INTO quote_documents (
                    id, quote_id, customer_id, doc_type, document_number,
                    issue_date, due_date, po_number, vat_number, registration_number,
                    bill_to_name, notes, status, currency,
                    subtotal_minor, vat_minor, total_minor,
                    created_at, updated_at, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.id, document.quote_id, document.customer_id,
                    document.doc_type, document.document_number,
                    document.issue_date, document.due_date, document.po_number, document.vat_number,
                    document.registration_number, document.bill_to_name, document.notes,
                    document.status, document.currency,
                    document.subtotal_minor, document.vat_minor, document.total_minor,
                    document.created_at, document.updated_at, document.created_by,
                ),
            )

        return document

    # --------------------------------------------------

    def get(self, document_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM quote_documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        return self._to_document(row) if row else None

    # --------------------------------------------------

    def list_all(self, doc_type=None):

        with self.db.connect() as connection:
            if doc_type:
                rows = connection.execute(
                    "SELECT * FROM quote_documents WHERE doc_type = ? ORDER BY issue_date DESC",
                    (doc_type,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM quote_documents ORDER BY issue_date DESC",
                ).fetchall()
        return [self._to_document(row) for row in rows]

    # --------------------------------------------------

    def list_for_quote(self, quote_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM quote_documents WHERE quote_id = ? ORDER BY created_at",
                (quote_id,),
            ).fetchall()
        return [self._to_document(row) for row in rows]

    # --------------------------------------------------

    def list_for_customer(self, customer_id, doc_type=None):

        with self.db.connect() as connection:
            if doc_type:
                rows = connection.execute(
                    "SELECT * FROM quote_documents WHERE customer_id = ? AND doc_type = ? ORDER BY issue_date",
                    (customer_id, doc_type),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM quote_documents WHERE customer_id = ? ORDER BY issue_date",
                    (customer_id,),
                ).fetchall()
        return [self._to_document(row) for row in rows]

    # --------------------------------------------------

    def _to_document(self, row):

        return QuoteDocument(
            id=row["id"],
            quote_id=row["quote_id"],
            customer_id=row["customer_id"],
            doc_type=row["doc_type"],
            document_number=row["document_number"],
            issue_date=row["issue_date"],
            due_date=row["due_date"],
            po_number=row["po_number"] or "",
            vat_number=row["vat_number"] or "",
            registration_number=row["registration_number"] or "",
            bill_to_name=row["bill_to_name"] or "",
            notes=row["notes"],
            status=row["status"],
            currency=row["currency"],
            subtotal_minor=row["subtotal_minor"],
            vat_minor=row["vat_minor"],
            total_minor=row["total_minor"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
        )

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
