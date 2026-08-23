"""Workflow tests for CRMService: numbering, primary contact, sites,
activities, archive/reactivate, and duplicate detection. Matches
CRM_MODULE_SPECIFICATION.md section 10."""

import os
import tempfile

import pytest

from core.crm_repository import (
    AddressRepository,
    ActivityRepository,
    ContactRepository,
    CustomerRepository,
    SiteRepository,
    customer_number_prefix,
)
from core.crm_service import CRMService
from core.database import Database


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Komatsu Africa", "KOM"),
        ("3M", "MXX"),
        ("", "XXX"),
        ("   ", "XXX"),
        ("Ab", "ABX"),
        ("O'Brien & Sons", "OBR"),
    ],
)
def test_customer_number_prefix_derivation(name, expected):
    assert customer_number_prefix(name) == expected


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


def _new_customer(service, name="Landlord Co"):
    customer = service.new_customer()
    customer.name = name
    customer.status = "Active"
    return service.save_customer(customer)


def test_customer_number_uses_first_three_letters_of_the_name(crm_service):
    komatsu = _new_customer(crm_service, "Komatsu Africa")
    rebosis = _new_customer(crm_service, "Rebosis Property")

    assert komatsu.customer_number == "KOM-001"
    assert rebosis.customer_number == "REB-001"


def test_second_customer_with_the_same_prefix_gets_the_next_number(crm_service):
    first = _new_customer(crm_service, "Komatsu Africa")
    second = _new_customer(crm_service, "Komatsu Mining")

    assert first.customer_number == "KOM-001"
    assert second.customer_number == "KOM-002"


def test_short_or_symbol_only_names_pad_the_prefix(crm_service):
    customer = _new_customer(crm_service, "3M")

    assert customer.customer_number == "MXX-001"


def test_customer_number_never_changes_on_update(crm_service):
    customer = _new_customer(crm_service)
    original_number = customer.customer_number

    customer.notes = "Updated notes"
    updated = crm_service.save_customer(customer)

    assert updated.customer_number == original_number


def test_setting_primary_contact_demotes_the_previous_primary(crm_service):
    customer = _new_customer(crm_service)

    first = crm_service.new_contact(customer.id)
    first.name = "Alice"
    first = crm_service.save_contact(first)
    crm_service.set_primary_contact(customer.id, first.id, "minette")

    second = crm_service.new_contact(customer.id)
    second.name = "Bob"
    second = crm_service.save_contact(second)
    crm_service.set_primary_contact(customer.id, second.id, "minette")

    contacts = {contact.id: contact for contact in crm_service.list_contacts(customer.id)}
    assert contacts[first.id].is_primary is False
    assert contacts[second.id].is_primary is True


def test_set_primary_contact_rejects_a_contact_from_another_customer(crm_service):
    customer_a = _new_customer(crm_service, "Customer A")
    customer_b = _new_customer(crm_service, "Customer B")

    contact = crm_service.new_contact(customer_a.id)
    contact.name = "Alice"
    contact = crm_service.save_contact(contact)

    with pytest.raises(ValueError):
        crm_service.set_primary_contact(customer_b.id, contact.id, "minette")


def test_multiple_sites_share_one_customer_with_independent_addresses(crm_service):
    landlord = _new_customer(crm_service, "Landlord Co")

    address_a = crm_service.new_address(landlord.id)
    address_a.address_type = "Site"
    address_a.line1 = "1 Main Rd"
    address_a.city = "Johannesburg"
    address_a = crm_service.save_address(address_a)

    address_b = crm_service.new_address(landlord.id)
    address_b.address_type = "Site"
    address_b.line1 = "2 Main Rd"
    address_b.city = "Johannesburg"
    address_b = crm_service.save_address(address_b)

    site_a = crm_service.new_site(landlord.id)
    site_a.name = "Tenant A"
    site_a.address_id = address_a.id
    crm_service.save_site(site_a)

    site_b = crm_service.new_site(landlord.id)
    site_b.name = "Tenant B"
    site_b.address_id = address_b.id
    crm_service.save_site(site_b)

    sites = crm_service.list_sites(landlord.id)
    assert {site.address_id for site in sites} == {address_a.id, address_b.id}


def test_site_cannot_reference_another_customers_address(crm_service):
    customer_a = _new_customer(crm_service, "Customer A")
    customer_b = _new_customer(crm_service, "Customer B")

    address = crm_service.new_address(customer_a.id)
    address.line1 = "1 Main Rd"
    address = crm_service.save_address(address)

    site = crm_service.new_site(customer_b.id)
    site.name = "Cross-customer site"
    site.address_id = address.id

    with pytest.raises(ValueError):
        crm_service.save_site(site)


def test_full_customer_lifecycle_through_service_only(crm_service):
    customer = _new_customer(crm_service)

    contact = crm_service.new_contact(customer.id)
    contact.name = "Alice"
    contact = crm_service.save_contact(contact)
    crm_service.set_primary_contact(customer.id, contact.id, "minette")

    address = crm_service.new_address(customer.id)
    address.line1 = "1 Main Rd"
    address = crm_service.save_address(address)

    site = crm_service.new_site(customer.id)
    site.name = "Main Site"
    site.address_id = address.id
    site = crm_service.save_site(site)

    activity = crm_service.new_activity(customer.id)
    activity.contact_id = contact.id
    activity.site_id = site.id
    activity.subject = "Initial inspection booked"
    activity.activity_type = "Note"
    crm_service.save_activity(activity)

    crm_service.archive_customer(customer.id, "minette", "Test archive")
    archived = crm_service.get_customer(customer.id)
    assert archived.status == "Archived"
    assert archived.archived_by == "minette"

    assert crm_service.list_contacts(customer.id)[0].name == "Alice"
    assert crm_service.list_sites(customer.id)[0].name == "Main Site"
    assert crm_service.list_activities(customer.id)[0].subject == "Initial inspection booked"

    crm_service.reactivate_customer(customer.id, "minette")
    reactivated = crm_service.get_customer(customer.id)
    assert reactivated.status == "Active"
    assert reactivated.archived_at == ""


def test_archive_requires_a_reason(crm_service):
    customer = _new_customer(crm_service)

    with pytest.raises(ValueError):
        crm_service.archive_customer(customer.id, "minette", "")


def test_find_possible_duplicate_customers_matches_email_or_name(crm_service):
    original = _new_customer(crm_service, "Acme Property Group")
    original.email = "info@acme.co.za"
    crm_service.save_customer(original)

    candidate = crm_service.new_customer()
    candidate.name = "Acme Property Group"
    candidate.status = "Active"

    duplicates = crm_service.find_possible_duplicate_customers(candidate)

    assert any(match.id == original.id for match in duplicates)


def test_find_possible_duplicate_customers_ignores_distinct_customers(crm_service):
    _new_customer(crm_service, "Acme Property Group")

    candidate = crm_service.new_customer()
    candidate.name = "Totally Different Co"
    candidate.status = "Active"

    duplicates = crm_service.find_possible_duplicate_customers(candidate)

    assert duplicates == []


def test_convert_customer_to_contact_creates_a_new_contact(crm_service):
    company = _new_customer(crm_service, "Cavaleros Group")
    person = _new_customer(crm_service, "Andreas Savas")
    person.email = "andreas@cavaleros.co.za"
    person.phone = "0833785122"
    person = crm_service.save_customer(person)

    contact = crm_service.convert_customer_to_contact(person.id, company.id, "minette")

    assert contact.customer_id == company.id
    assert contact.name == "Andreas Savas"
    assert contact.email == "andreas@cavaleros.co.za"

    archived_person = crm_service.get_customer(person.id)
    assert archived_person.status == "Archived"
    assert "Cavaleros Group" in archived_person.archive_reason


def test_convert_customer_to_contact_reuses_an_existing_matching_contact(crm_service):
    """Matches the real scenario this feature was built for: a
    Communications import already created a correct contact under the
    right company, alongside a mistaken duplicate customer record for the
    same person. Converting should link to the existing contact, not
    create a second one."""

    company = _new_customer(crm_service, "Cavaleros Group")

    existing_contact = crm_service.new_contact(company.id)
    existing_contact.name = "Andreas Savas"
    existing_contact.email = "andreas@cavaleros.co.za"
    existing_contact = crm_service.save_contact(existing_contact)

    person = _new_customer(crm_service, "Andreas Savas")
    person.email = "andreas@cavaleros.co.za"
    person = crm_service.save_customer(person)

    contact = crm_service.convert_customer_to_contact(person.id, company.id, "minette")

    assert contact.id == existing_contact.id
    assert len(crm_service.list_contacts(company.id)) == 1


def test_convert_customer_to_contact_rejects_converting_into_itself(crm_service):
    person = _new_customer(crm_service, "Andreas Savas")

    with pytest.raises(ValueError):
        crm_service.convert_customer_to_contact(person.id, person.id, "minette")


def test_convert_customer_to_contact_rejects_unknown_target(crm_service):
    person = _new_customer(crm_service, "Andreas Savas")

    with pytest.raises(ValueError):
        crm_service.convert_customer_to_contact(person.id, "does-not-exist", "minette")
