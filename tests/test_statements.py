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
from core.statement_repository import StatementRepository
from core.statement_service import StatementService


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
def quote_document_service(test_db, quote_service, crm_service):
    return QuoteDocumentService(
        repository=QuoteDocumentRepository(db=test_db),
        quote_service=quote_service,
        crm_service=crm_service,
    )


@pytest.fixture
def statement_service(test_db, quote_document_service):
    return StatementService(
        repository=StatementRepository(db=test_db),
        quote_document_service=quote_document_service,
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


def test_generate_statement_requires_invoices_in_period(crm_service, statement_service):
    customer = make_customer(crm_service)

    with pytest.raises(ValueError):
        statement_service.generate_statement(customer.id, "2000-01-01", "2000-01-31", "minette")


def test_generate_statement_totals_invoices_in_period(crm_service, quote_service, quote_document_service, statement_service):
    customer = make_customer(crm_service)
    invoice1 = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=100000)
    invoice2 = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=50000)

    today = datetime.now().strftime("%Y-%m-%d")
    statement, invoices = statement_service.generate_statement(customer.id, today, today, "minette")

    assert statement.document_number.startswith("KOM-STA_")
    assert statement.total_minor == invoice1.total_minor + invoice2.total_minor
    assert len(invoices) == 2


def test_statement_excludes_invoices_outside_period(crm_service, quote_service, quote_document_service, statement_service):
    customer = make_customer(crm_service)
    make_invoice(quote_service, quote_document_service, customer.id)

    with pytest.raises(ValueError):
        statement_service.generate_statement(customer.id, "2000-01-01", "2000-01-31", "minette")


def test_statement_numbers_are_scoped_per_customer(crm_service, quote_service, quote_document_service, statement_service):
    komatsu = make_customer(crm_service, "Komatsu Africa")
    rebosis = make_customer(crm_service, "Rebosis Property")
    make_invoice(quote_service, quote_document_service, komatsu.id)
    make_invoice(quote_service, quote_document_service, rebosis.id)

    today = datetime.now().strftime("%Y-%m-%d")
    komatsu_statement, _ = statement_service.generate_statement(komatsu.id, today, today, "minette")
    rebosis_statement, _ = statement_service.generate_statement(rebosis.id, today, today, "minette")

    yy = f"{datetime.now().year % 100:02d}"
    assert komatsu_statement.document_number == f"KOM-STA_{yy}/001"
    assert rebosis_statement.document_number == f"REB-STA_{yy}/001"
