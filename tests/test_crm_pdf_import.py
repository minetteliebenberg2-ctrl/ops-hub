"""Regression tests for CRMService.import_customer_from_pdf."""

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
from core.pdf_customer_extractor import ExtractedContact, ExtractedCustomer


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


def test_import_creates_customer_address_and_contact(crm_service):
    extracted = ExtractedCustomer(
        name="Dominique Fuchsloch",
        address_lines=["2 Skypass Road", "Solheim", "Germiston"],
        contact_name="Dominique",
        email="spiritual@iburst.co.za",
        vat_number="",
        registration_number="",
    )

    customer, created = crm_service.import_customer_from_pdf(extracted, "minette")

    assert created is True
    assert customer.name == "Dominique Fuchsloch"
    assert customer.email == "spiritual@iburst.co.za"
    assert customer.customer_number

    addresses = crm_service.addresses.list_for_customer(customer.id)
    assert len(addresses) == 1
    assert addresses[0].address_type == "Billing"
    assert addresses[0].line1 == "2 Skypass Road"
    assert addresses[0].is_primary is True

    contacts = crm_service.contacts.list_for_customer(customer.id)
    assert len(contacts) == 1
    assert contacts[0].name == "Dominique"
    # Note: Contact.source isn't persisted by ContactRepository today
    # (pre-existing gap, also affects Communications imports - flagged
    # separately, not this feature's scope) so it can't be asserted
    # here even though import_customer_from_pdf does set it.


def test_reimporting_the_same_email_does_not_create_a_duplicate(crm_service):
    first = ExtractedCustomer(name="Mr John Zeller", email="john.zeller@sandvik.com", address_lines=["84 Alma Road"])
    crm_service.import_customer_from_pdf(first, "minette")

    second = ExtractedCustomer(name="Mr John Zeller", email="john.zeller@sandvik.com", address_lines=["84 Alma Road"])
    customer, created = crm_service.import_customer_from_pdf(second, "minette")

    assert created is False
    assert len(crm_service.list_customers()) == 1
    assert customer.name == "Mr John Zeller"


def test_reimport_fills_in_a_blank_vat_number_but_never_overwrites_an_existing_one(crm_service):
    first = ExtractedCustomer(name="TAKRAF South Africa", email="azwi.masuvhe@takraf.com", vat_number="")
    customer, _ = crm_service.import_customer_from_pdf(first, "minette")
    assert customer.vat_number == ""

    second = ExtractedCustomer(name="TAKRAF South Africa", email="azwi.masuvhe@takraf.com", vat_number="4123456789")
    customer, created = crm_service.import_customer_from_pdf(second, "minette")
    assert created is False
    assert customer.vat_number == "4123456789"

    third = ExtractedCustomer(name="TAKRAF South Africa", email="azwi.masuvhe@takraf.com", vat_number="9999999999")
    customer, _ = crm_service.import_customer_from_pdf(third, "minette")
    assert customer.vat_number == "4123456789"


def test_reimport_fills_in_a_blank_registration_number_but_never_overwrites_an_existing_one(crm_service):
    first = ExtractedCustomer(name="CMH Multifranchise Westrand", email="scotth@cmh.co.za", registration_number="")
    customer, _ = crm_service.import_customer_from_pdf(first, "minette")
    assert customer.registration_number == ""

    second = ExtractedCustomer(
        name="CMH Multifranchise Westrand", email="scotth@cmh.co.za", registration_number="1926/900691/07",
    )
    customer, created = crm_service.import_customer_from_pdf(second, "minette")
    assert created is False
    assert customer.registration_number == "1926/900691/07"

    third = ExtractedCustomer(
        name="CMH Multifranchise Westrand", email="scotth@cmh.co.za", registration_number="9999/999999/99",
    )
    customer, _ = crm_service.import_customer_from_pdf(third, "minette")
    assert customer.registration_number == "1926/900691/07"


def test_import_without_an_address_creates_no_address_row(crm_service):
    extracted = ExtractedCustomer(name="SE4RA Trading", email="kgalalelo@se4ra.co.za", address_lines=[])

    customer, _ = crm_service.import_customer_from_pdf(extracted, "minette")

    assert crm_service.addresses.list_for_customer(customer.id) == []


def test_every_contact_named_on_the_document_is_imported(crm_service):
    # The Cavaleros documents name Phillimon in the "Attention:" header
    # and Thamsi in the body - both are real people she deals with, so
    # both come in. Only the header one owns the document's email.
    extracted = ExtractedCustomer(
        name="The Cavaleros Group",
        email="phillimon@cavaleros.co.za",
        contact_name="Phillimon",
        contacts=[
            ExtractedContact(name="Phillimon", email="phillimon@cavaleros.co.za"),
            ExtractedContact(name="Thamsi"),
        ],
    )

    customer, _ = crm_service.import_customer_from_pdf(extracted, "minette")

    contacts = crm_service.contacts.list_for_customer(customer.id)
    assert {c.name for c in contacts} == {"Phillimon", "Thamsi"}
    primary = [c for c in contacts if c.is_primary]
    assert len(primary) == 1
    assert primary[0].name == "Phillimon"


def test_reimporting_adds_a_new_contact_without_duplicating_the_known_one(crm_service):
    first = ExtractedCustomer(
        name="The Cavaleros Group",
        email="phillimon@cavaleros.co.za",
        contact_name="Phillimon",
        contacts=[ExtractedContact(name="Phillimon", email="phillimon@cavaleros.co.za")],
    )
    customer, _ = crm_service.import_customer_from_pdf(first, "minette")

    second = ExtractedCustomer(
        name="The Cavaleros Group",
        email="phillimon@cavaleros.co.za",
        contact_name="Phillimon",
        contacts=[
            ExtractedContact(name="Phillimon", email="phillimon@cavaleros.co.za"),
            ExtractedContact(name="Thamsi"),
        ],
    )
    customer, created = crm_service.import_customer_from_pdf(second, "minette")

    assert created is False
    contacts = crm_service.contacts.list_for_customer(customer.id)
    assert sorted(c.name for c in contacts) == ["Phillimon", "Thamsi"]


def test_a_second_document_adds_its_address_instead_of_being_dropped(crm_service):
    # Each old quote carries the site address it was raised against, so
    # importing a customer's document history builds up their real list
    # of addresses rather than only keeping the first one seen.
    first = ExtractedCustomer(
        name="The Cavaleros Group",
        email="phillimon@cavaleros.co.za",
        address_lines=["Block B, Eastgate Office Park", "Johannesburg, 2198"],
    )
    customer, _ = crm_service.import_customer_from_pdf(first, "minette")

    second = ExtractedCustomer(
        name="The Cavaleros Group",
        email="phillimon@cavaleros.co.za",
        address_lines=["11 Riley Road, Bedfordview", "Johannesburg, 2007"],
    )
    customer, created = crm_service.import_customer_from_pdf(second, "minette")

    assert created is False
    addresses = crm_service.addresses.list_for_customer(customer.id)
    assert len(addresses) == 2
    assert {a.line1 for a in addresses} == {
        "Block B, Eastgate Office Park",
        "11 Riley Road, Bedfordview",
    }
    # Only the first import claims primary - a later document never
    # silently promotes itself over the address she's been using.
    assert [a.is_primary for a in addresses].count(True) == 1


def test_the_same_address_on_two_documents_is_not_duplicated(crm_service):
    lines = ["Block B, Eastgate Office Park", "Johannesburg, 2198"]
    first = ExtractedCustomer(
        name="The Cavaleros Group", email="phillimon@cavaleros.co.za", address_lines=lines,
    )
    crm_service.import_customer_from_pdf(first, "minette")

    second = ExtractedCustomer(
        name="The Cavaleros Group", email="phillimon@cavaleros.co.za", address_lines=list(lines),
    )
    customer, _ = crm_service.import_customer_from_pdf(second, "minette")

    assert len(crm_service.addresses.list_for_customer(customer.id)) == 1


def test_two_different_customers_with_no_email_both_get_created(crm_service):
    # No email means dedupe can't run - each import is trusted as its
    # own customer rather than guessed to be a match.
    a = ExtractedCustomer(name="Susan / Werner van Wyk", email="", address_lines=["7 Randhart Manor"])
    b = ExtractedCustomer(name="Susan / Werner van Wyk", email="", address_lines=["7 Randhart Manor"])

    crm_service.import_customer_from_pdf(a, "minette")
    _customer, created = crm_service.import_customer_from_pdf(b, "minette")

    assert created is True
    assert len(crm_service.list_customers()) == 2
