import os
import tempfile

import pytest

from core.crm_repository import ActivityRepository, AddressRepository, ContactRepository, CustomerRepository, SiteRepository
from core.crm_service import CRMService
from core.database import Database
from core.payment_repository import PaymentAllocationRepository, PaymentRepository
from core.payment_service import PaymentService
from core.picklist_repository import PicklistOptionRepository
from core.quote_document_repository import QuoteDocumentRepository
from core.quote_document_service import QuoteDocumentService
from core.quote_repository import QuoteLineItemRepository, QuoteRepository
from core.quote_service import QuoteService
from core.site_visit_repository import SiteVisitRepository
from core.site_visit_service import SiteVisitService
from modules.dashboard.dashboard_data import DashboardData


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


@pytest.fixture
def site_visit_service(test_db):
    return SiteVisitService(repository=SiteVisitRepository(db=test_db))


@pytest.fixture
def dashboard_data(crm_service, quote_service, payment_service, site_visit_service):
    return DashboardData(
        crm_service=crm_service, quote_service=quote_service, payment_service=payment_service,
        site_visit_service=site_visit_service,
    )


def make_customer(crm_service, name="Komatsu Africa"):
    customer = crm_service.new_customer()
    customer.name = name
    customer.status = "Active"
    customer.payment_terms = "Standard"
    return crm_service.save_customer(customer)


def make_invoice(quote_service, quote_document_service, customer_id, unit_price_minor=100000, due_days=30):
    quote = quote_service.save_quote(quote_service.new_quote(customer_id), "minette")
    line_item = quote_service.new_line_item(quote.id)
    line_item.structure_type = "Cantilever"
    line_item.quantity = 1
    line_item.unit_price_minor = unit_price_minor
    quote_service.save_line_item(line_item)
    quote_service.issue_quote(quote.id, "minette")
    quote = quote_service.get_quote(quote.id)
    return quote_document_service.generate_tax_invoice(quote.id, "minette", due_days=due_days)


def test_outstanding_invoices_count_is_zero_with_no_invoices(dashboard_data):
    assert dashboard_data.get_outstanding_invoices_count() == 0


def test_outstanding_invoices_count_excludes_fully_paid(crm_service, quote_service, quote_document_service, payment_service, dashboard_data):
    customer = make_customer(crm_service)
    paid = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=100000)
    make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=50000)

    payment = payment_service.log_payment(customer.id, 100000, "2026-01-01", "EFT", "", "minette")
    payment_service.allocate(payment.id, paid.id, 100000, "minette")

    assert dashboard_data.get_outstanding_invoices_count() == 1


def test_overdue_invoices_excludes_invoices_not_yet_due(crm_service, quote_service, quote_document_service, dashboard_data):
    customer = make_customer(crm_service)
    make_invoice(quote_service, quote_document_service, customer.id, due_days=30)

    assert dashboard_data.get_overdue_invoices() == []


def test_overdue_invoices_reports_real_past_due_balance(crm_service, quote_service, quote_document_service, dashboard_data):
    customer = make_customer(crm_service, name="The Cavaleros Group")
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=150000, due_days=-10)

    overdue = dashboard_data.get_overdue_invoices()

    assert len(overdue) == 1
    assert overdue[0]["invoice_number"] == invoice.document_number
    assert overdue[0]["customer"] == "The Cavaleros Group"
    assert overdue[0]["amount"] == "R 1,500.00"
    assert overdue[0]["days_overdue"] == 10


def test_overdue_invoices_excludes_fully_paid_even_if_past_due(crm_service, quote_service, quote_document_service, payment_service, dashboard_data):
    customer = make_customer(crm_service)
    invoice = make_invoice(quote_service, quote_document_service, customer.id, unit_price_minor=100000, due_days=-5)

    payment = payment_service.log_payment(customer.id, 100000, "2026-01-01", "EFT", "", "minette")
    payment_service.allocate(payment.id, invoice.id, 100000, "minette")

    assert dashboard_data.get_overdue_invoices() == []


def test_overdue_invoices_worst_overdue_first(crm_service, quote_service, quote_document_service, dashboard_data):
    customer = make_customer(crm_service)
    make_invoice(quote_service, quote_document_service, customer.id, due_days=-2)
    make_invoice(quote_service, quote_document_service, customer.id, due_days=-20)

    overdue = dashboard_data.get_overdue_invoices()

    assert [row["days_overdue"] for row in overdue] == [20, 2]


def test_upcoming_site_visits_is_empty_with_no_real_visits(dashboard_data):
    assert dashboard_data.get_upcoming_site_visits() == []
    assert dashboard_data.get_upcoming_site_visits_count() == 0


def test_upcoming_site_visits_shows_real_scheduled_visits(crm_service, site_visit_service, dashboard_data):
    customer = make_customer(crm_service, name="The Cavaleros Group")
    visit = site_visit_service.new_visit(customer.id)
    visit.visit_date = "2099-01-01"
    visit.visit_time = "10:00 AM"
    site_visit_service.save_visit(visit, "minette")

    assert dashboard_data.get_upcoming_site_visits_count() == 1
    upcoming = dashboard_data.get_upcoming_site_visits()
    assert len(upcoming) == 1
    assert upcoming[0]["customer"] == "The Cavaleros Group"
    assert upcoming[0]["date"] == "2099-01-01"


def test_upcoming_site_visits_excludes_completed_and_past(crm_service, site_visit_service, dashboard_data):
    customer = make_customer(crm_service)

    past = site_visit_service.new_visit(customer.id)
    past.visit_date = "2020-01-01"
    site_visit_service.save_visit(past, "minette")

    completed = site_visit_service.new_visit(customer.id)
    completed.visit_date = "2099-01-01"
    saved_completed = site_visit_service.save_visit(completed, "minette")
    site_visit_service.mark_complete(saved_completed.id, "minette")

    assert dashboard_data.get_upcoming_site_visits_count() == 0
    assert dashboard_data.get_upcoming_site_visits() == []


def make_site(crm_service, customer_id, warranty_installed_date=""):
    address = crm_service.new_address(customer_id)
    address.address_type = "Site"
    address.line1 = "Eastgate Office Park"
    address = crm_service.save_address(address)
    site = crm_service.new_site(customer_id)
    site.name = "Block A"
    site.address_id = address.id
    site.warranty_installed_date = warranty_installed_date
    return crm_service.save_site(site)


def test_warranties_expiring_count_ignores_sites_with_no_warranty_date(crm_service, dashboard_data):
    customer = make_customer(crm_service)
    make_site(crm_service, customer.id)

    assert dashboard_data.get_warranties_expiring_count() == 0


def test_warranties_expiring_count_flags_expired_site(crm_service, dashboard_data):
    customer = make_customer(crm_service)
    make_site(crm_service, customer.id, warranty_installed_date="2020-01-01")

    assert dashboard_data.get_warranties_expiring_count() == 1


def make_issued_quote(quote_service, customer_id, validity_days=7):
    quote = quote_service.save_quote(quote_service.new_quote(customer_id), "minette")
    line_item = quote_service.new_line_item(quote.id)
    line_item.structure_type = "Cantilever"
    line_item.quantity = 1
    line_item.unit_price_minor = 100000
    quote_service.save_line_item(line_item)
    quote_service.issue_quote(quote.id, "minette", validity_days=validity_days)
    return quote_service.get_quote(quote.id)


def test_stale_quotes_ignores_quotes_with_plenty_of_time_left(crm_service, quote_service, dashboard_data):
    customer = make_customer(crm_service)
    make_issued_quote(quote_service, customer.id, validity_days=30)

    assert dashboard_data.get_stale_quotes() == []


def test_stale_quotes_flags_quote_expiring_soon(crm_service, quote_service, dashboard_data):
    customer = make_customer(crm_service, name="The Cavaleros Group")
    quote = make_issued_quote(quote_service, customer.id, validity_days=2)

    stale = dashboard_data.get_stale_quotes()

    assert len(stale) == 1
    assert stale[0]["customer"] == "The Cavaleros Group"
    assert stale[0]["days"] == 2
    assert stale[0]["status_label"] == "Expires in 2d"


def test_stale_quotes_flags_already_expired_quote(crm_service, quote_service, dashboard_data):
    customer = make_customer(crm_service)
    make_issued_quote(quote_service, customer.id, validity_days=-5)

    stale = dashboard_data.get_stale_quotes()

    assert len(stale) == 1
    assert stale[0]["days"] == -5
    assert stale[0]["status_label"] == "Expired 5d ago"


def test_stale_quotes_excludes_draft_quotes(crm_service, quote_service, dashboard_data):
    customer = make_customer(crm_service)
    quote_service.save_quote(quote_service.new_quote(customer.id), "minette")

    assert dashboard_data.get_stale_quotes() == []


def test_stale_quotes_excludes_quotes_already_decided(crm_service, quote_service, dashboard_data):
    customer = make_customer(crm_service)
    quote = make_issued_quote(quote_service, customer.id, validity_days=1)

    quote_service.set_status(quote.id, "Accepted", "minette")

    assert dashboard_data.get_stale_quotes() == []


def test_stale_quotes_worst_first(crm_service, quote_service, dashboard_data):
    customer = make_customer(crm_service)
    make_issued_quote(quote_service, customer.id, validity_days=1)
    make_issued_quote(quote_service, customer.id, validity_days=-10)

    stale = dashboard_data.get_stale_quotes()

    assert [row["days"] for row in stale] == [-10, 1]
