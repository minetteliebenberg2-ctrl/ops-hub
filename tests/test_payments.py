import os
import tempfile
from datetime import datetime

import pytest

from core.crm_repository import ActivityRepository, AddressRepository, ContactRepository, CustomerRepository, SiteRepository
from core.crm_service import CRMService
from core.database import Database
from core.payment import ALLOCATED, PARTIALLY_ALLOCATED, UNALLOCATED
from core.payment_repository import PaymentAllocationRepository, PaymentRepository
from core.payment_service import INVOICE_PAID, INVOICE_PARTIALLY_PAID, INVOICE_UNPAID, PaymentService
from core.picklist_repository import PicklistOptionRepository
from core.quote_document_repository import QuoteDocumentRepository
from core.quote_document_service import QuoteDocumentService
from core.quote_repository import QuoteLineItemRepository, QuoteRepository
from core.quote_service import QuoteService


@pytest.fixture
def test_db():
    db_path = tempfile.mktemp(suffix=".db")
    database = Database(db_path)
    yield database
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def crm_service(test_db):
    return CRMService(
        customer_repository=CustomerRepository(db=test_db),
        contact_repository=ContactRepository(db=test_db),
        address_repository=AddressRepository(db=test_db),
        site_repository=SiteRepository(db=test_db),
        activity_repository=ActivityRepository(db=test_db),
    )


@pytest.fixture
def quote_service(test_db):
    return QuoteService(
        quote_repository=QuoteRepository(db=test_db),
        line_item_repository=QuoteLineItemRepository(db=test_db),
        customer_repository=CustomerRepository(db=test_db),
        picklist_repository=PicklistOptionRepository(db=test_db),
        quote_document_repository=QuoteDocumentRepository(db=test_db),
        allocation_repository=PaymentAllocationRepository(db=test_db),
    )


@pytest.fixture
def quote_document_service(test_db, quote_service):
    return QuoteDocumentService(
        repository=QuoteDocumentRepository(db=test_db),
        quote_service=quote_service,
    )


@pytest.fixture
def payment_service(test_db):
    return PaymentService(
        payment_repository=PaymentRepository(db=test_db),
        allocation_repository=PaymentAllocationRepository(db=test_db),
        document_repository=QuoteDocumentRepository(db=test_db),
        activity_repository=ActivityRepository(db=test_db),
    )


def make_customer(crm_service, name="Komatsu Africa"):
    customer = crm_service.new_customer()
    customer.name = name
    customer.status = "Active"
    customer.payment_terms = "Standard"
    return crm_service.save_customer(customer)


def make_invoice(quote_service, quote_document_service, customer_id, unit_price_minor=100000):
    quote = quote_service.save_quote(quote_service.new_quote(customer_id), "minette")
    line_item = quote_service.new_line_item(quote.id)
    line_item.structure_type = "Cantilever"
    line_item.quantity = 1
    line_item.unit_price_minor = unit_price_minor
    quote_service.save_line_item(line_item)
    quote_service.issue_quote(quote.id, "minette")
    quote = quote_service.get_quote(quote.id)
    return quote_document_service.generate_tax_invoice(quote.id, "minette")


def test_log_payment_starts_unallocated(crm_service, payment_service):
    customer = make_customer(crm_service)
    today = datetime.now().strftime("%Y-%m-%d")

    payment = payment_service.log_payment(customer.id, 100000, today, "EFT123", "", "minette")

    assert payment.status == UNALLOCATED
    assert payment_service.get_payment_remaining(payment.id) == 100000


def test_log_payment_requires_positive_amount(crm_service, payment_service):
    customer = make_customer(crm_service)
    today = datetime.now().strftime("%Y-%m-%d")

    with pytest.raises(ValueError):
        payment_service.log_payment(customer.id, 0, today, "EFT123", "", "minette")


def test_full_allocation_marks_payment_and_invoice_paid(crm_service, quote_service, quote_document_service, payment_service):
    customer = make_customer(crm_service)
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=100000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, invoice.total_minor, today, "EFT123", "", "minette")

    payment_service.allocate(payment.id, invoice.id, invoice.total_minor, "minette")

    updated_payment = payment_service.get_payment(payment.id)
    assert updated_payment.status == ALLOCATED
    allocated, balance, status = payment_service.invoice_balance(invoice.id, invoice.total_minor)
    assert allocated == invoice.total_minor
    assert balance == 0
    assert status == INVOICE_PAID


def test_partial_allocation_marks_partially_allocated(crm_service, quote_service, quote_document_service, payment_service):
    customer = make_customer(crm_service)
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=100000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, invoice.total_minor, today, "EFT123", "", "minette")

    payment_service.allocate(payment.id, invoice.id, 40000, "minette")

    updated_payment = payment_service.get_payment(payment.id)
    assert updated_payment.status == PARTIALLY_ALLOCATED
    allocated, balance, status = payment_service.invoice_balance(invoice.id, invoice.total_minor)
    assert allocated == 40000
    assert balance == 60000
    assert status == INVOICE_PARTIALLY_PAID


def test_allocation_cannot_exceed_payment_remaining(crm_service, quote_service, quote_document_service, payment_service):
    customer = make_customer(crm_service)
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=100000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, 50000, today, "EFT123", "", "minette")

    with pytest.raises(ValueError):
        payment_service.allocate(payment.id, invoice.id, 60000, "minette")


def test_allocation_cannot_exceed_invoice_balance(crm_service, quote_service, quote_document_service, payment_service):
    customer = make_customer(crm_service)
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=50000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, 100000, today, "EFT123", "", "minette")

    with pytest.raises(ValueError):
        payment_service.allocate(payment.id, invoice.id, 60000, "minette")


def test_allocation_rejects_other_customers_invoice(crm_service, quote_service, quote_document_service, payment_service):
    komatsu = make_customer(crm_service, "Komatsu Africa")
    rebosis = make_customer(crm_service, "Rebosis Property")
    invoice = make_invoice(quote_service, quote_document_service, rebosis.id)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(komatsu.id, invoice.total_minor, today, "EFT123", "", "minette")

    with pytest.raises(ValueError):
        payment_service.allocate(payment.id, invoice.id, invoice.total_minor, "minette")


def test_one_payment_splits_across_two_invoices(crm_service, quote_service, quote_document_service, payment_service):
    customer = make_customer(crm_service)
    invoice1 = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=50000)
    invoice2 = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=50000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, 100000, today, "EFT123", "", "minette")

    payment_service.allocate(payment.id, invoice1.id, 50000, "minette")
    payment_service.allocate(payment.id, invoice2.id, 50000, "minette")

    assert payment_service.get_payment(payment.id).status == ALLOCATED
    assert payment_service.get_payment_remaining(payment.id) == 0


def test_unallocate_reverses_without_deleting_history(crm_service, quote_service, quote_document_service, payment_service):
    customer = make_customer(crm_service)
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=100000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, invoice.total_minor, today, "EFT123", "", "minette")

    allocation = payment_service.allocate(payment.id, invoice.id, invoice.total_minor, "minette")
    payment_service.unallocate(allocation.id, "minette", "typo")

    assert payment_service.get_payment(payment.id).status == UNALLOCATED
    assert payment_service.get_payment_remaining(payment.id) == invoice.total_minor
    allocated, balance, status = payment_service.invoice_balance(invoice.id, invoice.total_minor)
    assert allocated == 0
    assert balance == invoice.total_minor
    assert status == INVOICE_UNPAID

    history = payment_service.list_allocations_for_payment(payment.id)
    assert len(history) == 2
    assert sum(item.amount_minor for item in history) == 0


def test_get_open_invoices_excludes_fully_paid(crm_service, quote_service, quote_document_service, payment_service):
    customer = make_customer(crm_service)
    invoice1 = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=50000)
    invoice2 = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=50000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, 50000, today, "EFT123", "", "minette")
    payment_service.allocate(payment.id, invoice1.id, 50000, "minette")

    open_invoices = payment_service.get_open_invoices(customer.id)

    document_ids = {entry["document"].id for entry in open_invoices}
    assert invoice1.id not in document_ids
    assert invoice2.id in document_ids


def test_list_invoices_with_status_includes_fully_paid(crm_service, quote_service, quote_document_service, payment_service):
    customer = make_customer(crm_service)
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=50000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, 50000, today, "EFT123", "", "minette")
    payment_service.allocate(payment.id, invoice.id, 50000, "minette")

    all_invoices = payment_service.list_invoices_with_status(customer.id)

    assert len(all_invoices) == 1
    assert all_invoices[0]["status"] == INVOICE_PAID
    assert all_invoices[0]["balance_minor"] == 0


def test_list_invoices_with_status_across_all_customers(crm_service, quote_service, quote_document_service, payment_service):
    komatsu = make_customer(crm_service, "Komatsu Africa")
    rebosis = make_customer(crm_service, "Rebosis Property")
    make_invoice(quote_service, quote_document_service, komatsu.id)
    make_invoice(quote_service, quote_document_service, rebosis.id)

    all_invoices = payment_service.list_invoices_with_status()

    assert len(all_invoices) == 2


def test_allocation_logs_customer_activity(crm_service, quote_service, quote_document_service, payment_service):
    customer = make_customer(crm_service)
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=100000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, invoice.total_minor, today, "EFT123", "", "minette")

    payment_service.allocate(payment.id, invoice.id, invoice.total_minor, "minette")

    activities = crm_service.activities.list_for_customer(customer.id)
    assert any(a.source_entity_type == "payment_allocation" for a in activities)


def test_delete_quote_is_blocked_when_a_payment_is_allocated_against_its_invoice(
    crm_service, quote_service, quote_document_service, payment_service,
):
    customer = make_customer(crm_service)
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=100000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, invoice.total_minor, today, "EFT123", "", "minette")
    payment_service.allocate(payment.id, invoice.id, invoice.total_minor, "minette")

    quote = quote_service.get_quote(invoice.quote_id)
    with pytest.raises(ValueError):
        quote_service.delete_quote(quote.id)

    assert quote_service.get_quote(quote.id) is not None


def test_delete_quote_succeeds_once_the_payment_is_unallocated(
    crm_service, quote_service, quote_document_service, payment_service,
):
    customer = make_customer(crm_service)
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=100000)
    today = datetime.now().strftime("%Y-%m-%d")
    payment = payment_service.log_payment(customer.id, invoice.total_minor, today, "EFT123", "", "minette")
    allocation = payment_service.allocate(payment.id, invoice.id, invoice.total_minor, "minette")

    payment_service.unallocate(allocation.id, "minette")

    quote = quote_service.get_quote(invoice.quote_id)
    quote_service.delete_quote(quote.id)

    assert quote_service.get_quote(quote.id) is None
