# ==========================================================
# FC Hub - Business Settings Service
# ----------------------------------------------------------
# Purpose:
# Business service layer for FacilitiesCo's own settings and
# addresses.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime
from uuid import uuid4

from core.business_settings import BusinessAddress, BusinessSettings
from core.business_settings_repository import (
    BusinessAddressRepository,
    BusinessSettingsRepository,
)


class BusinessSettingsService:

    def __init__(self, settings_repository=None, address_repository=None):

        self.settings_repository = settings_repository or BusinessSettingsRepository()
        self.address_repository = address_repository or BusinessAddressRepository()

    # --------------------------------------------------

    def get_settings(self):

        return self.settings_repository.get() or BusinessSettings()

    # --------------------------------------------------

    def save_settings(self, settings, actor=""):

        now = self._timestamp()

        if not settings.created_at:
            settings.created_at = now

        settings.updated_at = now
        settings.updated_by = actor

        settings.trading_name = settings.trading_name.strip()
        settings.legal_name = settings.legal_name.strip()
        settings.registration_number = settings.registration_number.strip()
        settings.vat_number = settings.vat_number.strip()
        settings.email = settings.email.strip()
        settings.phone = settings.phone.strip()
        settings.website = settings.website.strip()

        if not settings.trading_name:
            raise ValueError("Trading name is required.")

        return self.settings_repository.save(settings)

    # --------------------------------------------------

    def list_addresses(self):

        return self.address_repository.list_all()

    # --------------------------------------------------

    def new_address(self):

        return BusinessAddress()

    # --------------------------------------------------

    def save_address(self, address, actor=""):

        now = self._timestamp()

        if not address.id:
            address.id = self._id()
            address.created_at = now

        if not address.created_at:
            address.created_at = now

        address.updated_at = now
        address.updated_by = actor

        address.line1 = address.line1.strip()
        address.line2 = address.line2.strip()
        address.city = address.city.strip()
        address.province = address.province.strip()
        address.postal_code = address.postal_code.strip()
        address.country = address.country.strip()

        if not address.line1:
            raise ValueError("Address line 1 is required.")

        return self.address_repository.save(address)

    # --------------------------------------------------

    def delete_address(self, address_id):

        self.address_repository.delete(address_id)

    # --------------------------------------------------

    def _id(self):

        return str(uuid4())

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now().isoformat(timespec="seconds")
