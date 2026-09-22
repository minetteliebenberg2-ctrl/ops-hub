# ==========================================================
# FC Hub - Statement Service
# ----------------------------------------------------------
# Purpose:
# Business rules for generating a per-customer, per-period Statement
# from that customer's issued Tax Invoices - the last step of the
# Quote -> Pro-Forma -> Tax Invoice -> Statement flow.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from core.quote_document import PRO_FORMA, TAX_INVOICE
from core.quote_document_service import QuoteDocumentService
from core.statement_repository import StatementRepository


class StatementService:

    def __init__(self, repository=None, quote_document_service=None):

        self.repository = repository or StatementRepository()
        self.quote_documents = quote_document_service or QuoteDocumentService()

    # --------------------------------------------------

    def generate_statement(self, customer_id, period_start, period_end, actor, notes=""):
        """Build a statement from every Tax Invoice issued to this
        customer with an issue_date inside [period_start, period_end]
        (inclusive, both YYYY-MM-DD)."""

        invoices = [
            invoice
            for invoice in self.quote_documents.list_invoices_for_customer(customer_id)
            if period_start <= invoice.issue_date <= period_end
        ]
        if not invoices:
            raise ValueError("No Tax Invoices were issued to this customer in that period.")

        currency = invoices[0].currency
        total_minor = sum(invoice.total_minor for invoice in invoices)

        statement = self.repository.create(
            customer_id, period_start, period_end, notes, currency, total_minor,
            [invoice.id for invoice in invoices], actor,
        )
        return statement, invoices

    # --------------------------------------------------

    def build_lines(self, customer_id, period_start, period_end, quote_service=None):
        """Editable starting lines for a customer's Statement. One line per
        quote, using the furthest document it has reached:
        Tax Invoice > Pro-Forma > Accepted Quote. Dated inside the period
        (inclusive). Each line: dict(ref, date, description, amount_minor,
        document_id or "", currency)."""

        from core.quote import format_quote_number
        from core.quote_service import QuoteService

        quote_service = quote_service or QuoteService()
        documents = self.quote_documents.repository.list_for_customer(customer_id)
        by_quote = {}
        for document in documents:
            by_quote.setdefault(document.quote_id, []).append(document)

        lines = []
        for quote in quote_service.list_quotes(customer_id=customer_id):
            docs = by_quote.pop(quote.id, [])
            split_docs = [d for d in docs if d.doc_type == TAX_INVOICE and getattr(d, "invoice_part", "")]
            if split_docs:
                # Split deposit / balance: every part is its own invoice line.
                for doc in split_docs:
                    line = {
                        "ref": doc.document_number, "date": doc.issue_date,
                        "description": f"Tax Invoice ({doc.invoice_part.capitalize()})",
                        "amount_minor": doc.total_minor,
                        "document_id": doc.id, "currency": doc.currency,
                    }
                    if period_start <= (line["date"] or "")[:10] <= period_end:
                        lines.append(line)
                continue
            chosen = next((d for d in docs if d.doc_type == TAX_INVOICE), None)                 or next((d for d in docs if d.doc_type == PRO_FORMA), None)
            if chosen is not None:
                line = {
                    "ref": chosen.document_number, "date": chosen.issue_date,
                    "description": chosen.doc_type, "amount_minor": chosen.total_minor,
                    "document_id": chosen.id, "currency": chosen.currency,
                }
            elif quote.status == "Accepted" and quote.quote_number:
                line = {
                    "ref": format_quote_number(quote),
                    "date": quote.accepted_date or quote.issue_date,
                    "description": "Accepted Quote", "amount_minor": quote.total_minor,
                    "document_id": "", "currency": quote.currency,
                }
            else:
                continue
            if period_start <= (line["date"] or "")[:10] <= period_end:
                lines.append(line)

        lines.sort(key=lambda l: l["date"] or "")
        return lines

    # --------------------------------------------------

    def save_statement(self, customer_id, period_start, period_end, lines, actor, notes="", currency="ZAR"):
        """Save a Statement from (possibly hand-adjusted) lines."""

        if not lines:
            raise ValueError("The statement has no lines.")
        total_minor = sum(line["amount_minor"] for line in lines)
        document_ids = [line["document_id"] for line in lines if line.get("document_id")]
        return self.repository.create(
            customer_id, period_start, period_end, notes, currency, total_minor, document_ids, actor,
        )

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        return self.repository.list_for_customer(customer_id)
