"""Tests for real Delete + Recycle Bin on core CRM entities (Customer,
Contact, Address, Site, Activity) - scoped with Minette 2026-08-07 via
AskUserQuestion: financial records excluded (not part of this scope),
recycle bin sits until manually emptied, delete is BLOCKED if the
record has children rather than cascade-recycling the whole tree."""

import os
import tempfile

import pytest

from core.crm_repository import (
    AddressRepository,
    ActivityRepository,
    ContactRepository,
    CustomerRepository,
    SiteRepository,
)
from core.crm_service import CRMService
from core.database import Database


@pytest.fixture
def crm_service():
    db_path = tempfile.mktemp(suffix=".db")
    test_db = Database(path=db_path)
    service = CRMService(
        customer_repository=CustomerRepository(db=test_db),
        contact_repository=ContactRepository(db=test_db),
        address_repository=AddressRepository(db=test_db),
        site_repository=SiteRepository(db=test_db),
        activity_repository=ActivityRepository(db=test_db),
    )
    yield service
    if os.path.exists(db_path):
        os.remove(db_path)


def _new_customer(service, name="Test Co"):
    customer = service.new_customer()
    customer.name = name
    customer.status = "Active"
    return service.save_customer(customer)


# --------------------------------------------------
# Customer
# --------------------------------------------------

def test_delete_customer_with_no_children_succeeds(crm_service):
    customer = _new_customer(crm_service)

    crm_service.delete_customer(customer.id, "minette")

    assert crm_service.get_customer(customer.id) is None
    assert customer.id not in [c.id for c in crm_service.list_customers()]


def test_delete_customer_blocked_by_contact(crm_service):
    customer = _new_customer(crm_service)
    contact = crm_service.new_contact(customer.id)
    contact.name = "Someone"
    crm_service.save_contact(contact)

    with pytest.raises(ValueError, match="contacts"):
        crm_service.delete_customer(customer.id, "minette")

    # Not actually deleted - still findable
    assert crm_service.get_customer(customer.id) is not None


def test_delete_customer_blocked_by_address(crm_service):
    customer = _new_customer(crm_service)
    address = crm_service.new_address(customer.id)
    address.address_type = "Billing"
    address.line1 = "1 Test Rd"
    crm_service.save_address(address)

    with pytest.raises(ValueError, match="addresses"):
        crm_service.delete_customer(customer.id, "minette")


def test_delete_customer_blocked_by_site(crm_service):
    # A Site always requires an Address, so a customer with a Site also
    # necessarily has an Address - the address check (checked first)
    # fires before the site-specific one ever would in practice. Real
    # behavior, not a bug: either message correctly blocks the delete.
    customer = _new_customer(crm_service)
    address = crm_service.new_address(customer.id)
    address.address_type = "Site"
    address.line1 = "1 Test Rd"
    address = crm_service.save_address(address)
    site = crm_service.new_site(customer.id)
    site.name = "Main Site"
    site.address_id = address.id
    crm_service.save_site(site)

    with pytest.raises(ValueError, match="addresses|sites"):
        crm_service.delete_customer(customer.id, "minette")


def test_delete_customer_blocked_by_activity(crm_service):
    customer = _new_customer(crm_service)
    activity = crm_service.new_activity(customer.id)
    activity.activity_type = "Note"
    activity.subject = "Called"
    activity.activity_date = "2026-08-07"
    crm_service.save_activity(activity)

    with pytest.raises(ValueError, match="activity"):
        crm_service.delete_customer(customer.id, "minette")


def test_deleted_customer_is_hidden_from_search_and_duplicate_detection(crm_service):
    customer = _new_customer(crm_service, "Findable Co")
    crm_service.delete_customer(customer.id, "minette")

    assert customer.id not in [c.id for c in crm_service.search_customers("Findable")]

    probe = crm_service.new_customer()
    probe.name = "Findable Co"
    assert crm_service.find_possible_duplicate_customers(probe) == []


def test_restore_customer_brings_it_back(crm_service):
    customer = _new_customer(crm_service)
    crm_service.delete_customer(customer.id, "minette")

    crm_service.restore_customer(customer.id, "minette")

    assert crm_service.get_customer(customer.id) is not None
    assert customer.id in [c.id for c in crm_service.list_customers()]


def test_list_deleted_customers(crm_service):
    keep = _new_customer(crm_service, "Keep Co")
    gone = _new_customer(crm_service, "Gone Co")
    crm_service.delete_customer(gone.id, "minette")

    deleted = crm_service.list_deleted_customers()

    assert [c.id for c in deleted] == [gone.id]
    assert keep.id not in [c.id for c in deleted]


def test_purge_customer_is_permanent(crm_service):
    customer = _new_customer(crm_service)
    crm_service.delete_customer(customer.id, "minette")

    crm_service.purge_customer(customer.id)

    assert crm_service.list_deleted_customers() == []
    assert crm_service.get_customer(customer.id) is None


# --------------------------------------------------
# Contact / Activity - no children, delete always succeeds
# --------------------------------------------------

def test_delete_contact_and_restore(crm_service):
    customer = _new_customer(crm_service)
    contact = crm_service.new_contact(customer.id)
    contact.name = "Jane"
    contact = crm_service.save_contact(contact)

    crm_service.delete_contact(contact.id, "minette")
    assert contact.id not in [c.id for c in crm_service.list_contacts(customer.id)]

    crm_service.restore_contact(contact.id, "minette")
    assert contact.id in [c.id for c in crm_service.list_contacts(customer.id)]


def test_delete_activity_and_restore(crm_service):
    customer = _new_customer(crm_service)
    activity = crm_service.new_activity(customer.id)
    activity.activity_type = "Note"
    activity.subject = "Test"
    activity.activity_date = "2026-08-07"
    activity = crm_service.save_activity(activity)

    crm_service.delete_activity(activity.id, "minette")
    assert activity.id not in [a.id for a in crm_service.list_activities(customer.id)]

    crm_service.restore_activity(activity.id, "minette")
    assert activity.id in [a.id for a in crm_service.list_activities(customer.id)]


# --------------------------------------------------
# Address - blocked if a Site still references it
# --------------------------------------------------

def test_delete_address_blocked_when_site_uses_it(crm_service):
    customer = _new_customer(crm_service)
    address = crm_service.new_address(customer.id)
    address.address_type = "Site"
    address.line1 = "1 Test Rd"
    address = crm_service.save_address(address)
    site = crm_service.new_site(customer.id)
    site.name = "Main Site"
    site.address_id = address.id
    crm_service.save_site(site)

    with pytest.raises(ValueError, match="site"):
        crm_service.delete_address(address.id, "minette")


def test_delete_address_succeeds_when_unused(crm_service):
    customer = _new_customer(crm_service)
    address = crm_service.new_address(customer.id)
    address.address_type = "Billing"
    address.line1 = "1 Test Rd"
    address = crm_service.save_address(address)

    crm_service.delete_address(address.id, "minette")

    assert address.id not in [a.id for a in crm_service.list_addresses(customer.id)]


# --------------------------------------------------
# Site
# --------------------------------------------------

def test_delete_site_and_restore(crm_service):
    customer = _new_customer(crm_service)
    address = crm_service.new_address(customer.id)
    address.address_type = "Site"
    address.line1 = "1 Test Rd"
    address = crm_service.save_address(address)
    site = crm_service.new_site(customer.id)
    site.name = "Main Site"
    site.address_id = address.id
    site = crm_service.save_site(site)

    crm_service.delete_site(site.id, "minette")
    assert site.id not in [s.id for s in crm_service.list_sites(customer.id)]
    assert crm_service.sites.get(site.id) is None

    crm_service.restore_site(site.id, "minette")
    assert site.id in [s.id for s in crm_service.list_sites(customer.id)]


def test_list_deleted_sites(crm_service):
    customer = _new_customer(crm_service)
    address = crm_service.new_address(customer.id)
    address.address_type = "Site"
    address.line1 = "1 Test Rd"
    address = crm_service.save_address(address)
    site = crm_service.new_site(customer.id)
    site.name = "Main Site"
    site.address_id = address.id
    site = crm_service.save_site(site)

    crm_service.delete_site(site.id, "minette")

    deleted = crm_service.list_deleted_sites()
    assert [s.id for s in deleted] == [site.id]


def test_purge_site_is_permanent(crm_service):
    customer = _new_customer(crm_service)
    address = crm_service.new_address(customer.id)
    address.address_type = "Site"
    address.line1 = "1 Test Rd"
    address = crm_service.save_address(address)
    site = crm_service.new_site(customer.id)
    site.name = "Main Site"
    site.address_id = address.id
    site = crm_service.save_site(site)

    crm_service.delete_site(site.id, "minette")
    crm_service.purge_site(site.id)

    assert crm_service.list_deleted_sites() == []
