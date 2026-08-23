"""Regression tests for CRM contact import."""

import os
import tempfile

import pytest

from core.client_folder_service import ClientFolderService
from core.crm_repository import (
    AddressRepository,
    ActivityRepository,
    ContactRepository,
    CustomerRepository,
    SiteRepository,
)
from core.crm_service import CRMService
from core.database import Database
from modules.communications.services import ContactCandidate


@pytest.fixture
def crm_service(tmp_path):
    db_path = tempfile.mktemp(suffix=".db")
    test_db = Database(path=db_path)
    customer_repository = CustomerRepository(db=test_db)  # runs migrations via db.initialize()
    # import_contact()'s "Create New Customer and Contact" path calls
    # ensure_client_folder() - point it at a throwaway temp dir so
    # tests never create real folders under the actual project.
    folder_service = ClientFolderService(database_path=db_path)
    folder_service.set_clients_root(tmp_path / "Clients")
    service = CRMService(
        customer_repository=customer_repository,
        contact_repository=ContactRepository(db=test_db),
        address_repository=AddressRepository(db=test_db),
        site_repository=SiteRepository(db=test_db),
        activity_repository=ActivityRepository(db=test_db),
        client_folder_service=folder_service,
    )
    yield service
    if os.path.exists(db_path):
        os.remove(db_path)


def test_new_customer_is_named_after_the_person_not_the_domain(crm_service):
    candidate = ContactCandidate(
        normalized_email="sarahjones88@gmail.com",
        original_email="Sarah Jones <sarahjones88@gmail.com>",
        display_name="Sarah Jones",
    )

    result = crm_service.import_contact(candidate, "Create New Customer and Contact")
    customer = crm_service.get_customer(result["customer_id"])

    assert customer.name == "Sarah Jones"
    assert customer.name != "gmail.com"


def test_two_gmail_contacts_become_two_different_customers(crm_service):
    for name, email in [
        ("Sarah Jones", "sarahjones88@gmail.com"),
        ("Mike Peters", "mikepeters@gmail.com"),
    ]:
        candidate = ContactCandidate(
            normalized_email=email,
            original_email=f"{name} <{email}>",
            display_name=name,
        )
        crm_service.import_contact(candidate, "Create New Customer and Contact")

    names = {c.name for c in crm_service.list_customers()}
    assert names == {"Sarah Jones", "Mike Peters"}
