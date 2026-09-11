# ==========================================================
# FC Hub - Quote Document Service
# ----------------------------------------------------------
# Purpose:
# Business rules for generating a Pro-Forma or Tax Invoice from an
# issued Quote - the "Quote -> Pro-Forma -> Tax Invoice" step of the
# Master Doc per client flow.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime, timedelta

from core.crm_service import CRMService
from core.quote_document import PRO_FORMA, TAX_INVOICE
from core.quote_document_repository import QuoteDocumentRepository
from core.quote_service import QuoteService

DEFAULT_INVOICE_DUE_DAYS = 30


class QuoteDocumentService:

    def __init__(self, repository=None, quote_service=None, crm_service=None):

        self.repository = repository or QuoteDocumentRepository()
        self.quote_service = quote_service or QuoteService()
        self.crm_service = crm_service or CRMService()

    # --------------------------------------------------

    def _customer_prefix(self, customer_id):
        customer = self.crm_service.get_customer(customer_id)
        if customer and customer.customer_number:
            return customer.customer_number.split("-")[0]
        return ""

    def generate_pro_forma(self, quote_id, actor, notes=""):

        quote = self._require_issued_quote(quote_id)
        issue_date = self._today()
        cust_prefix = self._customer_prefix(quote.customer_id)
        prefix = f"{cust_prefix}-PF" if cust_prefix else "PF"
        return self.repository.generate(
            quote, PRO_FORMA, prefix, issue_date, due_date="", notes=notes, actor=actor,
            po_number=quote.po_number, vat_number=quote.vat_number,
            registration_number=quote.registration_number, bill_to_name=quote.bill_to_name,
        )

    # --------------------------------------------------

    def generate_tax_invoice(self, quote_id, actor, notes="", due_days=DEFAULT_INVOICE_DUE_DAYS):

        quote = self._require_issued_quote(quote_id)
        issue_date = self._today()
        due_date = (datetime.now() + timedelta(days=due_days)).strftime("%Y-%m-%d")
        cust_prefix = self._customer_prefix(quote.customer_id)
        prefix = f"{cust_prefix}-I" if cust_prefix else "I"
        return self.repository.generate(
            quote, TAX_INVOICE, prefix, issue_date, due_date=due_date, notes=notes, actor=actor,
            po_number=quote.po_number, vat_number=quote.vat_number,
            registration_number=quote.registration_number, bill_to_name=quote.bill_to_name,
        )

    # --------------------------------------------------

    def list_for_quote(self, quote_id):

        return self.repository.list_for_quote(quote_id)

    # --------------------------------------------------

    def list_invoices_for_customer(self, customer_id):

        return self.repository.list_for_customer(customer_id, TAX_INVOICE)

    # --------------------------------------------------

    def _require_issued_quote(self, quote_id):

        quote = self.quote_service.get_quote(quote_id)
        if quote is None:
            raise ValueError("Quote not found.")
        if not quote.quote_number:
            raise ValueError("Issue the quote first — a number is required before generating documents from it.")
        line_items = self.quote_service.list_line_items(quote_id)
        if not line_items:
            raise ValueError("This quote has no line items.")
        return quote

    # --------------------------------------------------

    def _today(self):

        return datetime.now().strftime("%Y-%m-%d")
