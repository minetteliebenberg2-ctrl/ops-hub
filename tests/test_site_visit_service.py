import os
import tempfile

import pytest

from core.crm_repository import ActivityRepository, AddressRepository, ContactRepository, CustomerRepository, SiteRepository
from core.crm_service import CRMService
from core.database import Database
from core.site_visit import COMPLETED, SCHEDULED
from core.site_visit_repository import SiteVisitRepository
from core.site_visit_service import SiteVisitService


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
def site_visit_service(test_db):
    return SiteVisitService(repository=SiteVisitRepository(db=test_db))


def make_customer(crm_service, name="The Cavaleros Group"):
    customer = crm_service.new_customer()
    customer.name = name
    customer.status = "Active"
    customer.payment_terms = "Standard"
    return crm_service.save_customer(customer)


def test_new_visit_requires_customer(site_visit_service):
    visit = site_visit_service.new_visit(customer_id="")
    visit.visit_date = "2026-08-10"

    with pytest.raises(ValueError):
        site_visit_service.save_visit(visit, "minette")


def test_new_visit_requires_date(crm_service, site_visit_service):
    customer = make_customer(crm_service)
    visit = site_visit_service.new_visit(customer.id)

    with pytest.raises(ValueError):
        site_visit_service.save_visit(visit, "minette")


def test_save_and_list_visit_for_customer(crm_service, site_visit_service):
    customer = make_customer(crm_service)
    visit = site_visit_service.new_visit(customer.id)
    visit.visit_date = "2026-08-10"
    visit.visit_time = "10:00 AM"
    visit.notes = "First inspection"

    saved = site_visit_service.save_visit(visit, "minette")

    assert saved.status == SCHEDULED
    listed = site_visit_service.list_visits(customer.id)
    assert len(listed) == 1
    assert listed[0].visit_date == "2026-08-10"
    assert listed[0].notes == "First inspection"


def test_visit_links_to_a_real_site(crm_service, site_visit_service):
    customer = make_customer(crm_service)
    address = crm_service.new_address(customer.id)
    address.address_type = "Site"
    address.line1 = "Eastgate Office Park"
    address = crm_service.save_address(address)
    site = crm_service.new_site(customer.id)
    site.name = "Block C"
    site.address_id = address.id
    site = crm_service.save_site(site)

    visit = site_visit_service.new_visit(customer.id, site.id)
    visit.visit_date = "2026-08-10"
    saved = site_visit_service.save_visit(visit, "minette")

    assert saved.site_id == site.id


def test_mark_complete_changes_status(crm_service, site_visit_service):
    customer = make_customer(crm_service)
    visit = site_visit_service.new_visit(customer.id)
    visit.visit_date = "2026-08-10"
    saved = site_visit_service.save_visit(visit, "minette")

    site_visit_service.mark_complete(saved.id, "minette")

    reloaded = site_visit_service.get_visit(saved.id)
    assert reloaded.status == COMPLETED


def test_archive_requires_reason(crm_service, site_visit_service):
    customer = make_customer(crm_service)
    visit = site_visit_service.new_visit(customer.id)
    visit.visit_date = "2026-08-10"
    saved = site_visit_service.save_visit(visit, "minette")

    with pytest.raises(ValueError):
        site_visit_service.archive_visit(saved.id, "minette", "")

    site_visit_service.archive_visit(saved.id, "minette", "duplicate entry")
    reloaded = site_visit_service.get_visit(saved.id)
    assert reloaded.archived_at != ""


def test_list_all_visits_across_customers(crm_service, site_visit_service):
    customer_a = make_customer(crm_service, name="Cavaleros")
    customer_b = make_customer(crm_service, name="Komatsu")
    for customer in (customer_a, customer_b):
        visit = site_visit_service.new_visit(customer.id)
        visit.visit_date = "2026-08-10"
        site_visit_service.save_visit(visit, "minette")

    assert len(site_visit_service.list_visits()) == 2
    assert len(site_visit_service.list_visits(customer_a.id)) == 1
