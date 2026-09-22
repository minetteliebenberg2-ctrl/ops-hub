import os
import tempfile
from datetime import datetime

import pytest

from core.crm_repository import CustomerRepository
from core.crm_service import CRMService
from core.database import Database
from core.payment_repository import PaymentAllocationRepository
from core.picklist_repository import PicklistOptionRepository
from core.quote_document_repository import QuoteDocumentRepository
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


def make_customer(crm_service, name="Komatsu Africa"):
    customer = crm_service.new_customer()
    customer.name = name
    customer.status = "Active"
    customer.payment_terms = "Standard"
    return crm_service.save_customer(customer)


def test_new_quote_snapshots_customer_payment_terms(crm_service, quote_service):
    customer = make_customer(crm_service)

    quote = quote_service.new_quote(customer.id)

    assert quote.payment_terms_snapshot == "Standard"
    assert quote.deposit_percentage == 65.0
    assert quote.balance_percentage == 35.0


def test_new_quote_snapshots_customer_vat_number(crm_service, quote_service):
    customer = make_customer(crm_service)
    customer.vat_number = "4123456789"
    customer = crm_service.save_customer(customer)

    quote = quote_service.new_quote(customer.id)

    assert quote.vat_number == "4123456789"


def test_new_quote_leaves_vat_number_blank_when_customer_has_none(crm_service, quote_service):
    customer = make_customer(crm_service)

    quote = quote_service.new_quote(customer.id)

    assert quote.vat_number == ""


def test_new_quote_snapshots_customer_registration_number(crm_service, quote_service):
    customer = make_customer(crm_service)
    customer.registration_number = "1926/900691/07"
    customer = crm_service.save_customer(customer)

    quote = quote_service.new_quote(customer.id)

    assert quote.registration_number == "1926/900691/07"


def test_new_quote_leaves_registration_number_blank_when_customer_has_none(crm_service, quote_service):
    customer = make_customer(crm_service)

    quote = quote_service.new_quote(customer.id)

    assert quote.registration_number == ""


def test_new_quote_snapshots_customer_name_as_bill_to_name(crm_service, quote_service):
    customer = make_customer(crm_service, name="The Cavaleros Group")

    quote = quote_service.new_quote(customer.id)

    assert quote.bill_to_name == "The Cavaleros Group"


def test_bill_to_name_is_editable_independently_of_customer_name(crm_service, quote_service):
    """She often quotes a managing agent and only learns the real
    billing entity later - bill_to_name must stay a per-quote override,
    never re-synced from the customer after creation."""
    customer = make_customer(crm_service, name="The Cavaleros Group")
    quote = quote_service.new_quote(customer.id)
    quote = quote_service.save_quote(quote, "tester")

    quote.bill_to_name = "Turtium Investments (Pty) Ltd"
    quote_service.save_quote(quote, "tester")

    reloaded = quote_service.get_quote(quote.id)
    assert reloaded.bill_to_name == "Turtium Investments (Pty) Ltd"


def test_new_quote_for_netting_customer_snapshots_100_percent_upfront(crm_service, quote_service):
    customer = crm_service.new_customer()
    customer.name = "Rebosis Property"
    customer.status = "Active"
    customer.payment_terms = "Netting"
    customer = crm_service.save_customer(customer)

    quote = quote_service.new_quote(customer.id)

    assert quote.deposit_percentage == 100.0
    assert quote.balance_percentage == 0.0


def test_quote_number_is_scoped_per_customer(crm_service, quote_service):
    komatsu = make_customer(crm_service, "Komatsu Africa")
    rebosis = make_customer(crm_service, "Rebosis Property")

    quote1 = quote_service.save_quote(quote_service.new_quote(komatsu.id), "minette")
    quote2 = quote_service.save_quote(quote_service.new_quote(komatsu.id), "minette")
    quote3 = quote_service.save_quote(quote_service.new_quote(rebosis.id), "minette")

    line_item = quote_service.new_line_item(quote1.id)
    line_item.structure_type = "Cantilever"
    line_item.quantity = 1
    line_item.unit_price_minor = 100000
    quote_service.save_line_item(line_item)

    line_item2 = quote_service.new_line_item(quote2.id)
    line_item2.structure_type = "Cantilever"
    line_item2.quantity = 1
    line_item2.unit_price_minor = 100000
    quote_service.save_line_item(line_item2)

    line_item3 = quote_service.new_line_item(quote3.id)
    line_item3.structure_type = "Cantilever"
    line_item3.quantity = 1
    line_item3.unit_price_minor = 100000
    quote_service.save_line_item(line_item3)

    number1 = quote_service.issue_quote(quote1.id, "minette")
    number2 = quote_service.issue_quote(quote2.id, "minette")
    number3 = quote_service.issue_quote(quote3.id, "minette")

    yy = f"{datetime.now().year % 100:02d}"
    assert number1 == f"KOM-Q_{yy}/001"
    assert number2 == f"KOM-Q_{yy}/002"
    assert number3 == f"REB-Q_{yy}/001"


def test_cannot_issue_a_quote_with_no_line_items(crm_service, quote_service):
    customer = make_customer(crm_service)
    quote = quote_service.save_quote(quote_service.new_quote(customer.id), "minette")

    with pytest.raises(ValueError):
        quote_service.issue_quote(quote.id, "minette")


def test_cannot_issue_the_same_quote_twice(crm_service, quote_service):
    customer = make_customer(crm_service)
    quote = quote_service.save_quote(quote_service.new_quote(customer.id), "minette")
    line_item = quote_service.new_line_item(quote.id)
    line_item.structure_type = "Cantilever"
    line_item.unit_price_minor = 100000
    quote_service.save_line_item(line_item)

    quote_service.issue_quote(quote.id, "minette")

    with pytest.raises(ValueError):
        quote_service.issue_quote(quote.id, "minette")


def test_line_item_totals_recalculate_on_save_and_delete(crm_service, quote_service):
    customer = make_customer(crm_service)
    quote = quote_service.save_quote(quote_service.new_quote(customer.id), "minette")

    item1 = quote_service.new_line_item(quote.id)
    item1.structure_type = "Cantilever"
    item1.quantity = 2
    item1.unit_price_minor = 150000
    quote_service.save_line_item(item1)

    item2 = quote_service.new_line_item(quote.id)
    item2.structure_type = "Standard"
    item2.quantity = 1
    item2.unit_price_minor = 80000
    quote_service.save_line_item(item2)

    updated = quote_service.get_quote(quote.id)
    assert updated.subtotal_minor == 2 * 150000 + 80000
    assert updated.total_minor == updated.subtotal_minor
    assert updated.vat_minor == 0

    quote_service.delete_line_item(item2.id, quote.id)
    after_delete = quote_service.get_quote(quote.id)
    assert after_delete.subtotal_minor == 2 * 150000


def test_only_draft_quotes_can_be_deleted(crm_service, quote_service):
    customer = make_customer(crm_service)
    quote = quote_service.save_quote(quote_service.new_quote(customer.id), "minette")
    line_item = quote_service.new_line_item(quote.id)
    line_item.structure_type = "Cantilever"
    line_item.unit_price_minor = 100000
    quote_service.save_line_item(line_item)
    quote_service.issue_quote(quote.id, "minette")

    with pytest.raises(ValueError):
        quote_service.delete_draft_quote(quote.id)


def test_archive_requires_a_reason(crm_service, quote_service):
    customer = make_customer(crm_service)
    quote = quote_service.save_quote(quote_service.new_quote(customer.id), "minette")

    with pytest.raises(ValueError):
        quote_service.archive_quote(quote.id, "minette", "")


def test_delete_quote_removes_a_draft(crm_service, quote_service):
    customer = make_customer(crm_service)
    quote = quote_service.save_quote(quote_service.new_quote(customer.id), "minette")

    quote_service.delete_quote(quote.id)

    assert quote_service.get_quote(quote.id) is None


def test_delete_quote_removes_an_issued_quote_unlike_delete_draft_quote(crm_service, quote_service):
    customer = make_customer(crm_service)
    quote = quote_service.save_quote(quote_service.new_quote(customer.id), "minette")
    line_item = quote_service.new_line_item(quote.id)
    line_item.structure_type = "Cantilever"
    line_item.unit_price_minor = 100000
    quote_service.save_line_item(line_item)
    quote_service.issue_quote(quote.id, "minette")

    quote_service.delete_quote(quote.id)

    assert quote_service.get_quote(quote.id) is None


def test_delete_quote_cascades_to_line_items(crm_service, quote_service):
    customer = make_customer(crm_service)
    quote = quote_service.save_quote(quote_service.new_quote(customer.id), "minette")
    line_item = quote_service.new_line_item(quote.id)
    line_item.structure_type = "Cantilever"
    line_item.unit_price_minor = 100000
    quote_service.save_line_item(line_item)

    quote_service.delete_quote(quote.id)

    assert quote_service.list_line_items(quote.id) == []


def test_delete_quote_on_a_missing_quote_is_a_no_op(crm_service, quote_service):
    quote_service.delete_quote("does-not-exist")
