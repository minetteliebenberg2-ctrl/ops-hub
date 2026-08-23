"""Tests for JobCardService - a per-job/PO work log, scoped with
Minette 2026-08-07 from a real paper form. One Job Card per job/PO
(not persistent per Site like the Site Plan), numbered the same way
as Quote/Pro-Forma/Invoice/Statement (J_26/001)."""

import os
import tempfile

import pytest

from core.crm_repository import AddressRepository, ActivityRepository, ContactRepository, CustomerRepository, SiteRepository
from core.crm_service import CRMService
from core.database import Database
from core.job_card import CLOSED, OPEN
from core.job_card_repository import JobCardRepository
from core.job_card_service import JobCardService


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
def job_card_service(test_db):
    return JobCardService(repository=JobCardRepository(db=test_db))


@pytest.fixture
def customer_and_site(crm_service):
    customer = crm_service.new_customer()
    customer.name = "Cosen Properties (Pty) Ltd"
    customer.status = "Active"
    customer.payment_terms = "Standard"
    customer = crm_service.save_customer(customer)

    address = crm_service.new_address(customer.id)
    address.address_type = "Site"
    address.line1 = "Eastgate Office Park"
    address = crm_service.save_address(address)

    site = crm_service.new_site(customer.id)
    site.name = "South Boulevard"
    site.address_id = address.id
    site = crm_service.save_site(site)

    return customer, site


def test_create_job_card_allocates_a_yearly_number(job_card_service, customer_and_site):
    customer, site = customer_and_site

    job_card = job_card_service.create_job_card(customer, site, "minette", purchase_order="8295")

    assert job_card.job_card_number.startswith("J_")
    assert job_card.customer_id == customer.id
    assert job_card.site_id == site.id
    assert job_card.purchase_order == "8295"
    assert job_card.bill_to_name == customer.name
    assert job_card.status == OPEN


def test_create_job_card_numbers_increment_per_customer(job_card_service, customer_and_site):
    customer, site = customer_and_site

    first = job_card_service.create_job_card(customer, site, "minette")
    second = job_card_service.create_job_card(customer, site, "minette")

    assert first.job_card_number != second.job_card_number


def test_list_job_cards_for_site(job_card_service, customer_and_site):
    customer, site = customer_and_site
    job_card_service.create_job_card(customer, site, "minette")
    job_card_service.create_job_card(customer, site, "minette")

    job_cards = job_card_service.list_job_cards_for_site(site.id)

    assert len(job_cards) == 2


def test_close_and_reopen_job_card(job_card_service, customer_and_site):
    customer, site = customer_and_site
    job_card = job_card_service.create_job_card(customer, site, "minette")

    closed = job_card_service.close_job_card(job_card, "minette")
    assert closed.status == CLOSED

    reopened = job_card_service.reopen_job_card(closed, "minette")
    assert reopened.status == OPEN


def test_save_entry_requires_a_date(job_card_service, customer_and_site):
    customer, site = customer_and_site
    job_card = job_card_service.create_job_card(customer, site, "minette")
    entry = job_card_service.new_entry(job_card.id)
    entry.entry_date = ""

    with pytest.raises(ValueError):
        job_card_service.save_entry(entry)


def test_save_and_list_entries(job_card_service, customer_and_site):
    customer, site = customer_and_site
    job_card = job_card_service.create_job_card(customer, site, "minette")

    entry = job_card_service.new_entry(job_card.id)
    entry.work_type = "Repairs"
    entry.job_summary = "3 Nets"
    entry.description = "Collect Nets"
    entry.staff = "(2) J"
    job_card_service.save_entry(entry)

    entry2 = job_card_service.new_entry(job_card.id)
    entry2.entry_date = "2026-05-05"
    entry2.work_type = "Repairs"
    entry2.job_summary = "3 Nets"
    entry2.description = "Refit Nets"
    entry2.staff = "(1) G"
    entry2.completed = True
    entry2.director_signoff = "MH"
    job_card_service.save_entry(entry2)

    entries = job_card_service.list_entries(job_card.id)
    assert len(entries) == 2
    completed = [e for e in entries if e.completed]
    assert len(completed) == 1
    assert completed[0].director_signoff == "MH"


def test_delete_entry(job_card_service, customer_and_site):
    customer, site = customer_and_site
    job_card = job_card_service.create_job_card(customer, site, "minette")
    entry = job_card_service.new_entry(job_card.id)
    entry.work_type = "Repairs"
    job_card_service.save_entry(entry)

    job_card_service.delete_entry(entry.id)

    assert job_card_service.list_entries(job_card.id) == []


def test_archive_job_card_requires_a_reason(job_card_service, customer_and_site):
    customer, site = customer_and_site
    job_card = job_card_service.create_job_card(customer, site, "minette")

    with pytest.raises(ValueError):
        job_card_service.archive_job_card(job_card.id, "minette", "")


def test_archive_and_reactivate_job_card(job_card_service, customer_and_site):
    customer, site = customer_and_site
    job_card = job_card_service.create_job_card(customer, site, "minette")

    job_card_service.archive_job_card(job_card.id, "minette", "Cancelled")
    archived = job_card_service.get_job_card(job_card.id)
    assert archived.archived_at != ""

    job_card_service.reactivate_job_card(job_card.id, "minette")
    reactivated = job_card_service.get_job_card(job_card.id)
    assert reactivated.archived_at == ""


# ------------------------------------------------------------------
# Regression: name collision between the Site Visit form and Job Card
# ------------------------------------------------------------------

def test_no_duplicate_top_level_definitions_in_site_visit_windows():
    """modules/site_visit/windows.py held TWO classes named JobCardWindow
    (the New Site Visit form, and the unrelated Job Card feature). Python
    keeps only the later definition, so both of the Site Visit form's
    entry points raised TypeError the moment a user clicked them - a
    crash that shipped because nothing imported the shadowed class by
    name. Guard the whole file, not just that one name."""

    import ast
    from collections import Counter
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "modules" / "site_visit" / "windows.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = Counter(
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    )
    duplicates = sorted(name for name, count in names.items() if count > 1)

    assert not duplicates, f"shadowed top-level definitions in {source.name}: {duplicates}"


def test_site_visit_window_entry_points_match_their_constructors():
    """The two Site Visit entry points must call a constructor that
    actually accepts their arguments - the collision made both of these
    call the Job Card constructor instead."""

    import inspect

    from modules.site_visit.windows import NewSiteVisitWindow
    from modules.site_visit.windows import JobCardWindow

    visit_params = inspect.signature(NewSiteVisitWindow.__init__).parameters
    assert "on_saved" in visit_params
    assert "customer" not in visit_params

    card_params = inspect.signature(JobCardWindow.__init__).parameters
    assert "customer" in card_params and "job_card" in card_params
