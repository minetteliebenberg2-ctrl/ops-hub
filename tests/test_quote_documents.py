import os
import tempfile
from datetime import datetime

import pytest

from core.crm_repository import CustomerRepository
from core.crm_service import CRMService
from core.database import Database
from core.picklist_repository import PicklistOptionRepository
from core.payment_repository import PaymentAllocationRepository
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
    from core.crm_repository import AddressRepository, ActivityRepository, ContactRepository, SiteRepository

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


def make_customer(crm_service, name="Komatsu Africa"):
    customer = crm_service.new_customer()
    customer.name = name
    customer.status = "Active"
    customer.payment_terms = "Standard"
    return crm_service.save_customer(customer)


def make_issued_quote(quote_service, customer_id):
    quote = quote_service.save_quote(quote_service.new_quote(customer_id), "minette")
    line_item = quote_service.new_line_item(quote.id)
    line_item.structure_type = "Cantilever"
    line_item.quantity = 1
    line_item.unit_price_minor = 100000
    quote_service.save_line_item(line_item)
    quote_service.issue_quote(quote.id, "minette")
    return quote_service.get_quote(quote.id)


def test_generate_pro_forma_requires_issued_quote(crm_service, quote_service, quote_document_service):
    customer = make_customer(crm_service)
    draft_quote = quote_service.save_quote(quote_service.new_quote(customer.id), "minette")

    with pytest.raises(ValueError):
        quote_document_service.generate_pro_forma(draft_quote.id, "minette")


def test_generate_pro_forma_requires_quote_to_exist(quote_document_service):
    with pytest.raises(ValueError):
        quote_document_service.generate_pro_forma("no-such-quote-id", "minette")


def test_generate_pro_forma_snapshots_quote_totals(crm_service, quote_service, quote_document_service):
    customer = make_customer(crm_service)
    quote = make_issued_quote(quote_service, customer.id)

    document = quote_document_service.generate_pro_forma(quote.id, "minette")

    assert document.document_number.startswith("PF_")
    assert document.total_minor == quote.total_minor
    assert document.customer_id == customer.id
    assert document.quote_id == quote.id


def test_generate_pro_forma_snapshots_quote_vat_and_registration_number(crm_service, quote_service, quote_document_service):
    customer = make_customer(crm_service)
    customer.vat_number = "4123456789"
    customer.registration_number = "1926/900691/07"
    customer = crm_service.save_customer(customer)
    quote = make_issued_quote(quote_service, customer.id)

    document = quote_document_service.generate_pro_forma(quote.id, "minette")

    assert document.vat_number == "4123456789"
    assert document.registration_number == "1926/900691/07"


def test_generate_pro_forma_snapshots_quote_bill_to_name(crm_service, quote_service, quote_document_service):
    customer = make_customer(crm_service, name="The Cavaleros Group")
    quote = make_issued_quote(quote_service, customer.id)
    quote.bill_to_name = "Turtium Investments (Pty) Ltd"
    quote_service.save_quote(quote, "minette")

    document = quote_document_service.generate_pro_forma(quote.id, "minette")

    assert document.bill_to_name == "Turtium Investments (Pty) Ltd"


def test_generate_tax_invoice_sets_due_date_and_number_prefix(crm_service, quote_service, quote_document_service):
    customer = make_customer(crm_service)
    quote = make_issued_quote(quote_service, customer.id)

    document = quote_document_service.generate_tax_invoice(quote.id, "minette", due_days=15)

    assert document.document_number.startswith("I_")
    assert document.issue_date == datetime.now().strftime("%Y-%m-%d")
    assert document.due_date != ""
    assert document.due_date > document.issue_date


def test_document_numbers_are_scoped_per_customer_and_increment(crm_service, quote_service, quote_document_service):
    komatsu = make_customer(crm_service, "Komatsu Africa")
    rebosis = make_customer(crm_service, "Rebosis Property")

    komatsu_quote_1 = make_issued_quote(quote_service, komatsu.id)
    komatsu_quote_2 = make_issued_quote(quote_service, komatsu.id)
    rebosis_quote_1 = make_issued_quote(quote_service, rebosis.id)

    pf1 = quote_document_service.generate_pro_forma(komatsu_quote_1.id, "minette")
    pf2 = quote_document_service.generate_pro_forma(komatsu_quote_2.id, "minette")
    pf3 = quote_document_service.generate_pro_forma(rebosis_quote_1.id, "minette")

    yy = f"{datetime.now().year % 100:02d}"
    assert pf1.document_number == f"PF_{yy}/001"
    assert pf2.document_number == f"PF_{yy}/002"
    assert pf3.document_number == f"PF_{yy}/001"


def test_pro_forma_and_tax_invoice_number_sequences_are_independent(crm_service, quote_service, quote_document_service):
    customer = make_customer(crm_service)
    quote = make_issued_quote(quote_service, customer.id)

    pro_forma = quote_document_service.generate_pro_forma(quote.id, "minette")
    invoice = quote_document_service.generate_tax_invoice(quote.id, "minette")

    yy = f"{datetime.now().year % 100:02d}"
    assert pro_forma.document_number == f"PF_{yy}/001"
    assert invoice.document_number == f"I_{yy}/001"


def test_list_for_quote_returns_generated_documents(crm_service, quote_service, quote_document_service):
    customer = make_customer(crm_service)
    quote = make_issued_quote(quote_service, customer.id)

    quote_document_service.generate_pro_forma(quote.id, "minette")
    quote_document_service.generate_tax_invoice(quote.id, "minette")

    documents = quote_document_service.list_for_quote(quote.id)
    assert {d.doc_type for d in documents} == {"Pro-Forma", "Tax Invoice"}
