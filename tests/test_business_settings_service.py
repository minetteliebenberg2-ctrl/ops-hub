import os
import tempfile

import pytest

from core.business_settings_repository import (
    BusinessAddressRepository,
    BusinessSettingsRepository,
)
from core.business_settings_service import BusinessSettingsService
from core.database import Database


@pytest.fixture
def service():
    db_path = tempfile.mktemp(suffix=".db")
    test_db = Database(db_path)
    result = BusinessSettingsService(
        settings_repository=BusinessSettingsRepository(db=test_db),
        address_repository=BusinessAddressRepository(db=test_db),
    )
    yield result
    if os.path.exists(db_path):
        os.remove(db_path)


def test_get_settings_returns_the_seeded_row(service):
    settings = service.get_settings()

    assert settings.trading_name == ""
    assert settings.vat_registered is False


def test_save_settings_updates_the_single_row(service):
    settings = service.get_settings()
    settings.trading_name = "Test Trading Co"
    settings.phone = "012 345 6789"

    saved = service.save_settings(settings, "minette")

    assert saved.phone == "012 345 6789"
    assert service.get_settings().phone == "012 345 6789"


def test_save_settings_requires_a_trading_name(service):
    settings = service.get_settings()
    settings.trading_name = ""

    with pytest.raises(ValueError):
        service.save_settings(settings, "minette")


def test_new_address_can_be_added_and_listed(service):
    address = service.new_address()
    address.address_type = "Postal"
    address.line1 = "PO Box 123"
    address.city = "Germiston"

    service.save_address(address, "minette")

    addresses = service.list_addresses()
    assert any(item.line1 == "PO Box 123" for item in addresses)


def test_address_requires_line1(service):
    address = service.new_address()

    with pytest.raises(ValueError):
        service.save_address(address, "minette")


def test_delete_address_removes_it(service):
    address = service.new_address()
    address.line1 = "1 Test St"
    saved = service.save_address(address, "minette")

    service.delete_address(saved.id)

    assert saved.id not in {item.id for item in service.list_addresses()}
