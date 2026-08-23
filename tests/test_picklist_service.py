import os
import tempfile

import pytest

from core.database import Database
from core.picklist_repository import PicklistOptionRepository
from core.picklist_service import CUSTOMER_TYPE, PAYMENT_TERMS, PicklistService


@pytest.fixture
def service():
    db_path = tempfile.mktemp(suffix=".db")
    test_db = Database(db_path)
    result = PicklistService(repository=PicklistOptionRepository(db=test_db))
    yield result
    if os.path.exists(db_path):
        os.remove(db_path)


def test_seeded_payment_terms_are_listed_in_order(service):
    assert service.list_values(PAYMENT_TERMS) == ["Standard", "Netting"]


def test_seeded_customer_types_are_listed(service):
    types = service.list_values(CUSTOMER_TYPE)
    assert "Commercial" in types
    assert "Other" in types


def test_can_add_a_custom_payment_term(service):
    option = service.new_option(PAYMENT_TERMS)
    option.value = "Quarterly"
    option.deposit_percentage = 50
    option.balance_percentage = 50

    service.save_option(option, "minette")

    assert "Quarterly" in service.list_values(PAYMENT_TERMS)


def test_new_options_append_after_existing_ones_not_jump_to_the_front(service):
    option = service.new_option(PAYMENT_TERMS)
    option.value = "Quarterly"
    option.deposit_percentage = 50
    option.balance_percentage = 50

    service.save_option(option, "minette")

    assert service.list_values(PAYMENT_TERMS) == ["Standard", "Netting", "Quarterly"]


def test_payment_term_percentages_must_add_up_to_100(service):
    option = service.new_option(PAYMENT_TERMS)
    option.value = "Broken"
    option.deposit_percentage = 40
    option.balance_percentage = 40

    with pytest.raises(ValueError):
        service.save_option(option, "minette")


def test_customer_type_does_not_require_percentages(service):
    option = service.new_option(CUSTOMER_TYPE)
    option.value = "Non-Profit"

    service.save_option(option, "minette")

    assert "Non-Profit" in service.list_values(CUSTOMER_TYPE)


def test_deactivating_an_option_removes_it_from_default_listing(service):
    options = service.list_options(PAYMENT_TERMS)
    target = options[0]

    service.deactivate_option(target.id, "minette")

    assert target.value not in service.list_values(PAYMENT_TERMS)
    assert target.value in service.list_values(PAYMENT_TERMS, include_inactive=True)


def test_reactivating_restores_it(service):
    options = service.list_options(PAYMENT_TERMS)
    target = options[0]
    service.deactivate_option(target.id, "minette")

    service.reactivate_option(target.id, "minette")

    assert target.value in service.list_values(PAYMENT_TERMS)


def test_deleting_an_option_removes_it_permanently(service):
    option = service.new_option(CUSTOMER_TYPE)
    option.value = "Temp Type"
    saved = service.save_option(option, "minette")

    service.delete_option(saved.id)

    assert "Temp Type" not in service.list_values(CUSTOMER_TYPE, include_inactive=True)


def test_value_is_required(service):
    option = service.new_option(CUSTOMER_TYPE)

    with pytest.raises(ValueError):
        service.save_option(option, "minette")
