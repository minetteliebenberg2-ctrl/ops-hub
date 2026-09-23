# ==========================================================
# FC Hub - Business Settings Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for business_settings (single row) and
# business_addresses.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from core.business_settings import BusinessAddress, BusinessSettings
from core.database import database


SETTINGS_ID = "business"


class BusinessSettingsRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def get(self):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM business_settings WHERE id = ?",
                (SETTINGS_ID,),
            ).fetchone()

        return self._to_settings(row) if row else None

    # --------------------------------------------------

    def save(self, settings):

        settings.id = SETTINGS_ID

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO business_settings (
                    id, trading_name, legal_name, registration_number,
                    vat_registered, vat_number, email, phone, website,
                    bank_name, bank_account_name, bank_account_number,
                    branch_code, swift_code, deposit_percent, notes,
                    created_at, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    trading_name = excluded.trading_name,
                    legal_name = excluded.legal_name,
                    registration_number = excluded.registration_number,
                    vat_registered = excluded.vat_registered,
                    vat_number = excluded.vat_number,
                    email = excluded.email,
                    phone = excluded.phone,
                    website = excluded.website,
                    bank_name = excluded.bank_name,
                    bank_account_name = excluded.bank_account_name,
                    bank_account_number = excluded.bank_account_number,
                    branch_code = excluded.branch_code,
                    swift_code = excluded.swift_code,
                    deposit_percent = excluded.deposit_percent,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    settings.id,
                    settings.trading_name,
                    settings.legal_name,
                    settings.registration_number,
                    1 if settings.vat_registered else 0,
                    settings.vat_number,
                    settings.email,
                    settings.phone,
                    settings.website,
                    settings.bank_name,
                    settings.bank_account_name,
                    settings.bank_account_number,
                    settings.branch_code,
                    settings.swift_code,
                    int(settings.deposit_percent or 65),
                    settings.notes,
                    settings.created_at,
                    settings.updated_at,
                    settings.updated_by,
                ),
            )

        return settings

    # --------------------------------------------------

    def _to_settings(self, row):

        return BusinessSettings(
            id=row["id"],
            trading_name=row["trading_name"],
            legal_name=row["legal_name"],
            registration_number=row["registration_number"],
            vat_registered=bool(row["vat_registered"]),
            vat_number=row["vat_number"],
            email=row["email"],
            phone=row["phone"],
            website=row["website"],
            bank_name=row["bank_name"],
            bank_account_name=row["bank_account_name"],
            bank_account_number=row["bank_account_number"],
            branch_code=row["branch_code"],
            swift_code=row["swift_code"],
            deposit_percent=int(row["deposit_percent"] or 65) if "deposit_percent" in row.keys() else 65,
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
        )


class BusinessAddressRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def list_all(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM business_addresses ORDER BY is_primary DESC, address_type COLLATE NOCASE"
            ).fetchall()

        return [self._to_address(row) for row in rows]

    # --------------------------------------------------

    def get(self, address_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM business_addresses WHERE id = ?",
                (address_id,),
            ).fetchone()

        return self._to_address(row) if row else None

    # --------------------------------------------------

    def save(self, address):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO business_addresses (
                    id, address_type, line1, line2, city, province,
                    postal_code, country, is_primary, created_at, updated_at,
                    updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    address_type = excluded.address_type,
                    line1 = excluded.line1,
                    line2 = excluded.line2,
                    city = excluded.city,
                    province = excluded.province,
                    postal_code = excluded.postal_code,
                    country = excluded.country,
                    is_primary = excluded.is_primary,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    address.id,
                    address.address_type,
                    address.line1,
                    address.line2,
                    address.city,
                    address.province,
                    address.postal_code,
                    address.country,
                    1 if address.is_primary else 0,
                    address.created_at,
                    address.updated_at,
                    address.updated_by,
                ),
            )

        return address

    # --------------------------------------------------

    def delete(self, address_id):

        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM business_addresses WHERE id = ?",
                (address_id,),
            )

    # --------------------------------------------------

    def _to_address(self, row):

        return BusinessAddress(
            id=row["id"],
            address_type=row["address_type"],
            line1=row["line1"],
            line2=row["line2"],
            city=row["city"],
            province=row["province"],
            postal_code=row["postal_code"],
            country=row["country"],
            is_primary=bool(row["is_primary"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
        )
