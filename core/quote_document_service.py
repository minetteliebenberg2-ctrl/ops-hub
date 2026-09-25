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
from core.quote_document import (
    BALANCE, DEPOSIT, PRO_FORMA, TAX_INVOICE, deposit_percent,
)
from core.business_settings_repository import BusinessSettingsRepository
from core.business_settings_service import BusinessSettingsService
from core.quote_document_repository import QuoteDocumentRepository
from core.quote_service import QuoteService

DEFAULT_INVOICE_DUE_DAYS = 30


class QuoteDocumentService:

    def __init__(self, repository=None, quote_service=None, crm_service=None,
                 business_settings_service=None):

        self.repository = repository or QuoteDocumentRepository()
        self.quote_service = quote_service or QuoteService()
        self.crm_service = crm_service or CRMService()
        # Bound to the SAME database as the document repository so the
        # deposit % is read from the database this service is actually
        # writing to - tests run against a temp database, and a service
        # that reached past it to the live one would read the wrong
        # split.
        self.business_settings = business_settings_service or BusinessSettingsService(
            settings_repository=BusinessSettingsRepository(db=self.repository.db),
        )

    # --------------------------------------------------

    def _customer_prefix(self, customer_id):
        customer = self.crm_service.get_customer(customer_id)
        if customer and customer.customer_number:
            return customer.customer_number.split("-")[0]
        return ""

    def generate_pro_forma(self, quote_id, actor, notes="", issue_date=""):

        quote = self._require_issued_quote(quote_id)
        issue_date = issue_date or self._today()
        cust_prefix = self._customer_prefix(quote.customer_id)
        prefix = f"{cust_prefix}-PF" if cust_prefix else "PF"
        return self.repository.generate(
            quote, PRO_FORMA, prefix, issue_date, due_date="", notes=notes, actor=actor,
            po_number=quote.po_number, vat_number=quote.vat_number,
            registration_number=quote.registration_number, bill_to_name=quote.bill_to_name,
        )

    # --------------------------------------------------

    def generate_tax_invoice(self, quote_id, actor, notes="", due_days=DEFAULT_INVOICE_DUE_DAYS, issue_date=""):

        quote = self._require_issued_quote(quote_id)
        issue_date = issue_date or self._today()
        due_date = self._due_date(issue_date, due_days)
        cust_prefix = self._customer_prefix(quote.customer_id)
        prefix = f"{cust_prefix}-I" if cust_prefix else "I"
        return self.repository.generate(
            quote, TAX_INVOICE, prefix, issue_date, due_date=due_date, notes=notes, actor=actor,
            po_number=quote.po_number, vat_number=quote.vat_number,
            registration_number=quote.registration_number, bill_to_name=quote.bill_to_name,
        )

    # --------------------------------------------------

    def deposit_percent(self):
        """The deposit split from Business Settings (v0058). Read once
        per call so a change in Settings takes effect immediately."""

        return deposit_percent(self.business_settings)

    def split_amounts(self, total_minor):
        """(deposit, balance) in cents at the configured split, summing
        exactly - the balance is the remainder, never rounded on its own."""

        deposit = int(round(total_minor * self.deposit_percent() / 100))
        return deposit, total_minor - deposit

    def deposit_invoice_for_quote(self, quote_id):

        return next(
            (d for d in self.repository.list_for_quote(quote_id)
             if d.doc_type == TAX_INVOICE and d.invoice_part == DEPOSIT),
            None,
        )

    def generate_deposit_invoice(self, quote_id, actor, notes="", due_days=DEFAULT_INVOICE_DUE_DAYS, issue_date=""):
        """Tax Invoice for the deposit portion: one line, own I_ number."""

        quote = self._require_issued_quote(quote_id)
        deposit, _balance = self.split_amounts(quote.total_minor)
        deposit_vat, _ = self.split_amounts(quote.vat_minor)
        return self._generate_invoice(
            quote, actor, notes, due_days, DEPOSIT, issue_date=issue_date,
            subtotal_minor=deposit - deposit_vat, vat_minor=deposit_vat, total_minor=deposit,
        )

    def generate_balance_invoice(self, quote_id, actor, notes="", due_days=DEFAULT_INVOICE_DUE_DAYS, issue_date=""):
        """Tax Invoice for the balance portion. Needs the deposit invoice first."""

        quote = self._require_issued_quote(quote_id)
        if self.deposit_invoice_for_quote(quote_id) is None:
            raise ValueError(
                f"Generate the Deposit Invoice ({self.deposit_percent()}%) first - the balance invoice deducts it."
            )
        _deposit, balance = self.split_amounts(quote.total_minor)
        deposit_vat, _ = self.split_amounts(quote.vat_minor)
        balance_vat = quote.vat_minor - deposit_vat
        return self._generate_invoice(
            quote, actor, notes, due_days, BALANCE, issue_date=issue_date,
            subtotal_minor=balance - balance_vat, vat_minor=balance_vat, total_minor=balance,
        )

    def _generate_invoice(self, quote, actor, notes, due_days, invoice_part, issue_date="", **amounts):

        issue_date = issue_date or self._today()
        due_date = self._due_date(issue_date, due_days)
        cust_prefix = self._customer_prefix(quote.customer_id)
        prefix = f"{cust_prefix}-I" if cust_prefix else "I"
        return self.repository.generate(
            quote, TAX_INVOICE, prefix, issue_date, due_date=due_date, notes=notes, actor=actor,
            po_number=quote.po_number, vat_number=quote.vat_number,
            registration_number=quote.registration_number, bill_to_name=quote.bill_to_name,
            invoice_part=invoice_part, **amounts,
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

    # --------------------------------------------------

    def _due_date(self, issue_date, due_days):
        """Payment terms run from the document's own issue date, not from
        today - a back-dated invoice must not come out already overdue by
        the number of days it was captured late."""

        try:
            start = datetime.strptime(issue_date[:10], "%Y-%m-%d")
        except (TypeError, ValueError):
            start = datetime.now()
        return (start + timedelta(days=due_days)).strftime("%Y-%m-%d")

    # --------------------------------------------------

    def set_document_dates(self, document_id, issue_date=None, due_date=None, actor=""):
        """Move an existing document's dates. Number and amounts untouched."""

        for value in (issue_date, due_date):
            if value:
                self._validate_date(value)
        return self.repository.set_dates(
            document_id, issue_date=issue_date, due_date=due_date, actor=actor,
        )

    # --------------------------------------------------

    @staticmethod
    def _validate_date(value):

        try:
            datetime.strptime(value[:10], "%Y-%m-%d")
        except (TypeError, ValueError):
            raise ValueError(f"'{value}' is not a date. Use YYYY-MM-DD, for example 2026-08-14.")
