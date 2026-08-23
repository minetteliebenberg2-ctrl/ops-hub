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

    def list_for_customer(self, customer_id):

        return self.repository.list_for_customer(customer_id)
