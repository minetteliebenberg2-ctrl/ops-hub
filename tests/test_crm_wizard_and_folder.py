"""Regression: wizard imports under an existing customer; manual create still works and files a folder."""

import os
import tempfile

import pytest

from core.client_folder_service import ClientFolderService
from core.crm_repository import (
    AddressRepository, ActivityRepository, ContactRepository,
    CustomerRepository, SiteRepository,
)
from core.crm_service import CRMService
from core.customer import Customer
from core.database import Database
from modules.communications.services import ContactCandidate


@pytest.fixture
def env(tmp_path):
    db_path = tempfile.mktemp(suffix=".db")
    db = Database(path=db_path)
    customers = CustomerRepository(db=db)  # runs migrations
    folders = ClientFolderService(database_path=db_path)
    folders.set_clients_root(tmp_path / "Clients")
    svc = CRMService(
        customer_repository=customers,
        contact_repository=ContactRepository(db=db),
        address_repository=AddressRepository(db=db),
        site_repository=SiteRepository(db=db),
        activity_repository=ActivityRepository(db=db),
        client_folder_service=folders,
    )
    yield svc, tmp_path / "Clients"
    if os.path.exists(db_path):
        os.remove(db_path)


def test_import_under_existing_customer_with_payload(env):
    svc, _ = env
    customer = svc.save_customer(Customer(name="Heavenly Flowers Pre-Primary School"))
    cand = ContactCandidate(
        normalized_email="shimone@heavenlyflowers.co.za",
        original_email="Shimone <shimone@heavenlyflowers.co.za>",
        display_name="Shimone",
    )
    result = svc.import_contact(
        cand, "Create New Contact under Existing Customer", {"customer_id": customer.id}
    )
    assert result["customer_id"] == customer.id
    assert any(c.name == "Shimone" for c in svc.list_contacts(customer.id))


def test_existing_customer_action_without_payload_still_refuses(env):
    svc, _ = env
    cand = ContactCandidate(normalized_email="a@b.co.za", original_email="a@b.co.za", display_name="A")
    with pytest.raises(ValueError):
        svc.import_contact(cand, "Create New Contact under Existing Customer", {})


def test_manual_customer_save_then_ensure_folder(env):
    svc, root = env
    customer = svc.save_customer(Customer(name="Manual Client"))
    assert customer.id  # plain create still works with no wizard
    path = svc.client_folder_service.ensure_client_folder(customer)
    assert path is not None and os.path.isdir(path)
    # idempotent
    assert svc.client_folder_service.ensure_client_folder(customer) == path
