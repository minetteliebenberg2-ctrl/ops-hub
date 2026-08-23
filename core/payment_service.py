# ==========================================================
# FC Hub - Payment Service
# ----------------------------------------------------------
# Purpose:
# Business rules for logging customer payments and allocating them
# against Tax Invoices (quote_documents) - Phase 1, manual entry only.
# No auto-matching or bank-statement import yet.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import date, datetime

from core.activity import Activity
from core.crm_repository import ActivityRepository
from core.payment import ALLOCATED, PARTIALLY_ALLOCATED, UNALLOCATED
from core.payment_repository import PaymentAllocationRepository, PaymentRepository
from core.quote_document import TAX_INVOICE
from core.quote_document_repository import QuoteDocumentRepository

INVOICE_UNPAID = "Unpaid"
INVOICE_PARTIALLY_PAID = "Partially Paid"
INVOICE_PAID = "Paid"
INVOICE_OVERPAID = "Overpaid"


class PaymentService:

    def __init__(self, payment_repository=None, allocation_repository=None,
                 document_repository=None, activity_repository=None):

        self.payments = payment_repository or PaymentRepository()
        self.allocations = allocation_repository or PaymentAllocationRepository()
        self.documents = document_repository or QuoteDocumentRepository()
        self.activities = activity_repository or ActivityRepository()

    # --------------------------------------------------
    # Logging payments
    # --------------------------------------------------

    def log_payment(self, customer_id, amount_minor, date, reference, notes, actor):

        if not customer_id:
            raise ValueError("Select a customer for this payment.")
        if amount_minor <= 0:
            raise ValueError("Payment amount must be greater than zero.")
        if not date:
            raise ValueError("A payment date is required.")

        return self.payments.create(customer_id, amount_minor, date, reference, notes, actor)

    # --------------------------------------------------

    def list_payments(self):

        return self.payments.list_all()

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        return self.payments.list_for_customer(customer_id)

    # --------------------------------------------------

    def get_payment(self, payment_id):

        return self.payments.get(payment_id)

    # --------------------------------------------------

    def get_payment_remaining(self, payment_id):

        payment = self._require_payment(payment_id)
        allocated = self.allocations.sum_for_payment(payment_id)
        return payment.amount_minor - allocated

    # --------------------------------------------------

    def list_allocations_for_payment(self, payment_id):

        return self.allocations.list_for_payment(payment_id)

    # --------------------------------------------------
    # Invoice balances
    # --------------------------------------------------

    def get_open_invoices(self, customer_id):
        """Every Tax Invoice issued to this customer with a positive
        balance still outstanding, each with its allocated/balance/status."""

        invoices = self.documents.list_for_customer(customer_id, TAX_INVOICE)
        open_invoices = []
        for invoice in invoices:
            allocated, balance, status = self.invoice_balance(invoice.id, invoice.total_minor)
            if balance > 0:
                open_invoices.append({
                    "document": invoice,
                    "allocated_minor": allocated,
                    "balance_minor": balance,
                    "status": status,
                    "days_overdue": self.days_overdue(invoice.due_date, balance),
                })
        return open_invoices

    # --------------------------------------------------

    def list_invoices_with_status(self, customer_id=None):
        """Every Tax Invoice (all statuses, including fully Paid) either
        for one customer or across all customers - for screens that need
        to show real paid/balance status rather than just what's still
        outstanding (see get_open_invoices for that narrower case)."""

        if customer_id:
            invoices = self.documents.list_for_customer(customer_id, TAX_INVOICE)
        else:
            invoices = self.documents.list_all(TAX_INVOICE)

        results = []
        for invoice in invoices:
            allocated, balance, status = self.invoice_balance(invoice.id, invoice.total_minor)
            results.append({
                "document": invoice,
                "allocated_minor": allocated,
                "balance_minor": balance,
                "status": status,
                "days_overdue": self.days_overdue(invoice.due_date, balance),
            })
        return results

    # --------------------------------------------------

    def invoice_balance(self, quote_document_id, total_minor):

        allocated = self.allocations.sum_for_document(quote_document_id)
        balance = total_minor - allocated
        if allocated <= 0:
            status = INVOICE_UNPAID
        elif allocated < total_minor:
            status = INVOICE_PARTIALLY_PAID
        elif allocated == total_minor:
            status = INVOICE_PAID
        else:
            status = INVOICE_OVERPAID
        return allocated, balance, status

    # --------------------------------------------------

    def days_overdue(self, due_date, balance_minor):
        """How many days past its due date an invoice is, given it
        still has a positive balance outstanding - 0 if not overdue
        (not yet due, no due date on file, or already settled)."""

        if balance_minor <= 0 or not due_date:
            return 0
        try:
            due = datetime.strptime(due_date, "%Y-%m-%d").date()
        except ValueError:
            return 0
        overdue = (date.today() - due).days
        return overdue if overdue > 0 else 0

    # --------------------------------------------------
    # Allocating
    # --------------------------------------------------

    def allocate(self, payment_id, quote_document_id, amount_minor, actor, notes=""):

        if amount_minor <= 0:
            raise ValueError("Allocation amount must be greater than zero.")

        payment = self._require_payment(payment_id)
        invoice = self.documents.get(quote_document_id)
        if invoice is None:
            raise ValueError("Invoice not found.")
        if invoice.doc_type != TAX_INVOICE:
            raise ValueError("Payments can only be allocated to Tax Invoices.")
        if invoice.customer_id != payment.customer_id:
            raise ValueError("This invoice belongs to a different customer than the payment.")

        remaining_payment = self.get_payment_remaining(payment_id)
        if amount_minor > remaining_payment:
            raise ValueError("Allocation exceeds the unallocated balance of this payment.")

        _, invoice_balance, _ = self.invoice_balance(quote_document_id, invoice.total_minor)
        if amount_minor > invoice_balance:
            raise ValueError("Allocation exceeds this invoice's outstanding balance.")

        allocation = self.allocations.create(payment_id, quote_document_id, amount_minor, notes, actor)
        self._recompute_payment_status(payment_id)
        self._log_activity(
            payment, invoice, amount_minor,
            f"Payment of {self._format_amount(amount_minor)} allocated to {invoice.document_number}",
            actor,
        )
        return allocation

    # --------------------------------------------------

    def unallocate(self, allocation_id, actor, notes=""):

        allocation = self.allocations.get(allocation_id)
        if allocation is None:
            raise ValueError("Allocation not found.")

        payment = self._require_payment(allocation.payment_id)
        invoice = self.documents.get(allocation.quote_document_id)

        reversal = self.allocations.create(
            allocation.payment_id, allocation.quote_document_id, -allocation.amount_minor,
            notes or "Reversal", actor,
        )
        self._recompute_payment_status(allocation.payment_id)
        if invoice is not None:
            self._log_activity(
                payment, invoice, allocation.amount_minor,
                f"Allocation of {self._format_amount(allocation.amount_minor)} to {invoice.document_number} reversed",
                actor,
            )
        return reversal

    # --------------------------------------------------

    def _recompute_payment_status(self, payment_id):

        payment = self._require_payment(payment_id)
        allocated = self.allocations.sum_for_payment(payment_id)
        if allocated <= 0:
            status = UNALLOCATED
        elif allocated < payment.amount_minor:
            status = PARTIALLY_ALLOCATED
        else:
            status = ALLOCATED
        self.payments.update_status(payment_id, status)

    # --------------------------------------------------

    def _log_activity(self, payment, invoice, amount_minor, subject, actor):

        now = datetime.now().isoformat(timespec="seconds")
        self.activities.save(Activity(
            id=self._id(),
            customer_id=payment.customer_id,
            source_entity_type="payment_allocation",
            source_entity_id=payment.id,
            activity_type="Payment",
            subject=subject,
            activity_date=now[:10],
            status="Completed",
            notes="",
            created_at=now,
            updated_at=now,
            created_by=actor,
        ))

    # --------------------------------------------------

    def _require_payment(self, payment_id):

        payment = self.payments.get(payment_id)
        if payment is None:
            raise ValueError("Payment not found.")
        return payment

    # --------------------------------------------------

    def _format_amount(self, amount_minor):

        return f"R {amount_minor / 100:,.2f}"

    # --------------------------------------------------

    def _id(self):

        from uuid import uuid4
        return str(uuid4())
