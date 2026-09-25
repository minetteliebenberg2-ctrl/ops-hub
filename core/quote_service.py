# ==========================================================
# FC Hub - Quote Service
# ----------------------------------------------------------
# Purpose:
# Business rules for quotes: numbering (via QuoteRepository),
# payment-terms snapshotting, line-item totals, and status
# transitions.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime, timedelta
from uuid import uuid4

from core.crm_repository import CustomerRepository
from core.payment_repository import PaymentAllocationRepository
from core.picklist_repository import PicklistOptionRepository
from core.picklist_service import PAYMENT_TERMS
from core.quote import Quote
from core.quote_document_repository import QuoteDocumentRepository
from core.quote_line_item import QuoteLineItem
from core.quote_repository import QuoteLineItemRepository, QuoteRepository


DEFAULT_VALIDITY_DAYS = 7


def validate_document_date(value):
    """YYYY-MM-DD or nothing. Dates are typed by hand on the date-editing
    dialogs, and a bad one would silently exclude the document from every
    statement period rather than raising."""

    try:
        datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        raise ValueError(f"'{value}' is not a date. Use YYYY-MM-DD, for example 2026-08-14.")


class QuoteService:

    def __init__(
        self,
        quote_repository=None,
        line_item_repository=None,
        customer_repository=None,
        picklist_repository=None,
        quote_document_repository=None,
        allocation_repository=None,
    ):

        self.quotes = quote_repository or QuoteRepository()
        self.line_items = line_item_repository or QuoteLineItemRepository()
        self.customers = customer_repository or CustomerRepository()
        self.picklists = picklist_repository or PicklistOptionRepository()
        self.quote_documents = quote_document_repository or QuoteDocumentRepository()
        self.allocations = allocation_repository or PaymentAllocationRepository()

    # --------------------------------------------------
    # Quotes
    # --------------------------------------------------

    def new_quote(self, customer_id, site_id=""):

        customer = self.customers.get(customer_id)
        if customer is None:
            raise ValueError("Customer not found.")

        deposit, balance = self._payment_split(customer.payment_terms)

        return Quote(
            customer_id=customer_id,
            site_id=site_id,
            payment_terms_snapshot=customer.payment_terms,
            deposit_percentage=deposit,
            balance_percentage=balance,
            # Starting default only - same "editable snapshot" pattern
            # as payment_terms_snapshot above. Migration v0014 made
            # vat_number deliberately per-quote (a quote can be
            # drafted before the customer's VAT is confirmed), but it
            # should still start from whatever's already on the
            # customer's CRM record instead of blank/TBC when known.
            vat_number=customer.vat_number,
            registration_number=customer.registration_number,
            # Same reasoning, one step further: which name goes on the
            # document isn't always the customer on file either - she
            # often quotes a managing agent and only learns which legal
            # entity to actually bill later. Starts as the customer's
            # name, stays editable per-quote/document.
            bill_to_name=customer.name,
        )

    # --------------------------------------------------

    def _payment_split(self, payment_terms_value):

        for option in self.picklists.list_for(PAYMENT_TERMS, include_inactive=True):
            if option.value == payment_terms_value:
                return option.deposit_percentage, option.balance_percentage
        return None, None

    # --------------------------------------------------

    def save_quote(self, quote, actor=""):

        now = self._timestamp()

        if not quote.id:
            quote.id = self._id()
            quote.created_at = now
            quote.created_by = actor

        if not quote.created_at:
            quote.created_at = now

        quote.updated_at = now
        quote.updated_by = actor

        if not quote.customer_id:
            raise ValueError("A customer is required.")

        return self.quotes.save(quote)

    # --------------------------------------------------

    def get_quote(self, quote_id):

        return self.quotes.get(quote_id)

    # --------------------------------------------------

    def list_quotes(self, customer_id=None):

        if customer_id:
            return self.quotes.list_for_customer(customer_id)
        return self.quotes.list_all()

    # --------------------------------------------------

    def issue_quote(self, quote_id, actor, validity_days=DEFAULT_VALIDITY_DAYS, issue_date=""):

        quote = self.quotes.get(quote_id)
        if quote is None:
            raise ValueError("Quote not found.")
        if not self.line_items.list_for_quote(quote_id):
            raise ValueError("Add at least one line item before issuing a quote.")

        issue_date = issue_date or datetime.now().date().isoformat()
        validate_document_date(issue_date)
        expiry_date = (
            datetime.strptime(issue_date[:10], "%Y-%m-%d") + timedelta(days=validity_days)
        ).date().isoformat()

        return self.quotes.issue(quote_id, issue_date, expiry_date, actor)

    # --------------------------------------------------

    def create_quote_revision(self, quote_id, actor):
        """Start a new, editable version of an issued quote that keeps its
        quote number - the fix for 'I can't edit an issued quote': don't
        edit it, revise it. The original stays untouched; issue the
        revision when it's ready to replace it as the live version."""

        return self.quotes.create_revision(quote_id, actor)

    # --------------------------------------------------

    def set_status(self, quote_id, status, actor):
        """A quote cannot be Accepted before it has been issued. Allowing it
        created a dead end (2026-09-25, Cavaleros): the quote sat Accepted
        with no number, so Issue Quote refused it as "not a Draft" and every
        invoice refused it as "not issued"."""

        if status == "Accepted":
            quote = self.quotes.get(quote_id)
            if quote is None:
                raise ValueError("Quote not found.")
            if not quote.quote_number:
                raise ValueError(
                    "Issue this quote before marking it Accepted - it has no quote number yet."
                )
        self.quotes.set_status(quote_id, status, actor)

    # --------------------------------------------------

    def set_quote_dates(self, quote_id, actor, issue_date=None, accepted_date=None, expiry_date=None):
        """Correct a quote's own dates so it sits in the right place on the
        Statement. Validated, because a typo here silently drops the quote
        out of every statement period."""

        for value in (issue_date, accepted_date, expiry_date):
            if value:
                validate_document_date(value)
        self.quotes.set_dates(
            quote_id, actor, issue_date=issue_date,
            accepted_date=accepted_date, expiry_date=expiry_date,
        )
        return self.quotes.get(quote_id)

    # --------------------------------------------------

    def archive_quote(self, quote_id, actor, reason):

        if not reason.strip():
            raise ValueError("An archive reason is required.")
        self.quotes.archive(quote_id, actor, reason.strip())

    # --------------------------------------------------

    def delete_draft_quote(self, quote_id):

        quote = self.quotes.get(quote_id)
        if quote is None:
            return
        if quote.status != "Draft":
            raise ValueError("Only a Draft quote (never issued) can be deleted.")
        self.quotes.delete(quote_id)

    # --------------------------------------------------

    def delete_quote(self, quote_id):
        """Hard-deletes a quote of any status - unlike delete_draft_quote,
        this also removes an Issued quote (and, via cascade, its line
        items and any Pro-Forma/Tax Invoice generated from it). Only
        guard: refuses if a real payment has been allocated against one
        of its generated documents, so a moment of carelessness can't
        silently erase money that's actually been tracked. A quote
        with no payments against it - typically a mistake or test
        entry - can always be removed; the freed quote number is not
        reused automatically."""

        quote = self.quotes.get(quote_id)
        if quote is None:
            return

        for document in self.quote_documents.list_for_quote(quote_id):
            # Allocation history is append-only (see PaymentService.
            # unallocate - a reversal is a new negative row, nothing is
            # ever deleted), so a document with fully-reversed history
            # still has allocation rows. Check the net amount still
            # outstanding, not just whether any row exists.
            if self.allocations.sum_for_document(document.id) != 0:
                raise ValueError(
                    "This quote has a payment allocated against one of its documents "
                    f"({document.doc_type} {document.document_number}) and can't be deleted. "
                    "Unallocate the payment first if you're sure you want to remove it."
                )

        self.quotes.delete(quote_id)

    # --------------------------------------------------
    # Line items
    # --------------------------------------------------

    def new_line_item(self, quote_id):

        return QuoteLineItem(quote_id=quote_id)

    # --------------------------------------------------

    def save_line_item(self, line_item):

        now = self._timestamp()

        if not line_item.id:
            line_item.id = self._id()
            line_item.created_at = now

        if not line_item.created_at:
            line_item.created_at = now

        line_item.updated_at = now

        if not line_item.structure_type:
            raise ValueError("A structure type is required.")

        line_item.amount_minor = round(line_item.quantity * line_item.unit_price_minor)

        saved = self.line_items.save(line_item)
        self.recalculate_totals(line_item.quote_id)
        return saved

    # --------------------------------------------------

    def delete_line_item(self, line_item_id, quote_id):

        self.line_items.delete(line_item_id)
        self.recalculate_totals(quote_id)

    # --------------------------------------------------

    def list_line_items(self, quote_id):

        return self.line_items.list_for_quote(quote_id)

    # --------------------------------------------------

    def recalculate_totals(self, quote_id):

        quote = self.quotes.get(quote_id)
        if quote is None:
            return

        subtotal = sum(item.amount_minor for item in self.line_items.list_for_quote(quote_id))
        # FacilitiesCo is not VAT registered (confirmed business rule) - no
        # VAT line is added to quotes it issues.
        quote.subtotal_minor = subtotal
        quote.vat_minor = 0
        quote.total_minor = subtotal
        self.quotes.save(quote)

    # --------------------------------------------------

    def _id(self):

        return str(uuid4())

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now().isoformat(timespec="seconds")
