# ==========================================================
# FC Utilities - CRM Repository
# ----------------------------------------------------------
# Purpose:
# Database repository layer for CRM.
#
# Author: Minette & James
# Version: 2.0
# ==========================================================

import re

from core.activity import Activity
from core.address import Address
from core.contact import Contact
from core.customer import Customer
from core.database import database
from core.numbering_service import NumberingService
from core.site import Site


def customer_number_prefix(name):
    """First 3 letters of the customer's name, uppercased, padded with 'X'
    if the name has fewer than 3 letters. Each distinct prefix gets its own
    sequence, e.g. Komatsu -> KOM-001, Komatsu Africa -> KOM-002."""

    clean = (name or "").strip()
    clean = re.sub(r"^(?:The|A|An)\s+", "", clean, flags=re.IGNORECASE)
    letters = re.sub(r"[^A-Za-z]", "", clean).upper()
    letters = letters[:3]
    return letters.ljust(3, "X") if letters else "XXX"


class CustomerRepository:

    def __init__(self, db=None, numbering_service=None):

        self.db = db or database
        self.db.initialize()
        self.numbering = numbering_service or NumberingService()

    # --------------------------------------------------

    def save(self, customer):

        with self.db.connect() as connection:

            if not customer.customer_number:
                prefix = customer_number_prefix(customer.name)
                customer.customer_number = self.numbering.allocate(
                    connection,
                    "customer",
                    scope="prefix",
                    scope_id=prefix,
                    prefix=prefix,
                    padding=3,
                )

            connection.execute(
                """
                INSERT INTO customers (
                    id, customer_number, name, customer_type, status,
                    payment_terms, email, phone, website, vat_number,
                    registration_number, notes,
                    created_at, updated_at, created_by, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    customer_type = excluded.customer_type,
                    status = excluded.status,
                    payment_terms = excluded.payment_terms,
                    email = excluded.email,
                    phone = excluded.phone,
                    website = excluded.website,
                    vat_number = excluded.vat_number,
                    registration_number = excluded.registration_number,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    customer.id,
                    customer.customer_number,
                    customer.name,
                    customer.customer_type,
                    customer.status,
                    customer.payment_terms,
                    customer.email,
                    customer.phone,
                    customer.website,
                    customer.vat_number,
                    customer.registration_number,
                    customer.notes,
                    customer.created_at,
                    customer.updated_at,
                    customer.created_by,
                    customer.updated_by,
                ),
            )

        return customer

    # --------------------------------------------------

    def get(self, customer_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM customers WHERE id = ? AND deleted_at IS NULL",
                (customer_id,),
            ).fetchone()

        return self._to_customer(row) if row else None

    # --------------------------------------------------

    def list_all(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM customers WHERE deleted_at IS NULL ORDER BY name COLLATE NOCASE"
            ).fetchall()

        return [self._to_customer(row) for row in rows]

    # --------------------------------------------------

    def search(self, term):

        search_term = f"%{term.strip()}%"

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT customers.*
                FROM customers
                LEFT JOIN customer_contacts
                    ON customer_contacts.customer_id = customers.id
                LEFT JOIN customer_addresses
                    ON customer_addresses.customer_id = customers.id
                WHERE customers.deleted_at IS NULL
                    AND (customers.name LIKE ?
                    OR customers.customer_number LIKE ?
                    OR customers.email LIKE ?
                    OR customers.phone LIKE ?
                    OR customers.website LIKE ?
                    OR customers.vat_number LIKE ?
                    OR customer_contacts.name LIKE ?
                    OR customer_contacts.email LIKE ?
                    OR customer_contacts.phone LIKE ?
                    OR customer_contacts.mobile LIKE ?
                    OR customer_addresses.line1 LIKE ?
                    OR customer_addresses.city LIKE ?
                    OR customer_addresses.province LIKE ?
                    OR customer_addresses.postal_code LIKE ?)
                ORDER BY customers.name COLLATE NOCASE
                """,
                (search_term,) * 14,
            ).fetchall()

        return [self._to_customer(row) for row in rows]

    # --------------------------------------------------

    def find_by_normalized_email(self, email, exclude_id=""):

        normalized = str(email or "").strip().lower()
        if not normalized:
            return []

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM customers
                WHERE lower(email) = ? AND id != ? AND deleted_at IS NULL
                ORDER BY name COLLATE NOCASE
                """,
                (normalized, exclude_id),
            ).fetchall()

        return [self._to_customer(row) for row in rows]

    # --------------------------------------------------

    def find_by_name(self, name, exclude_id=""):

        normalized = str(name or "").strip().lower()
        if not normalized:
            return []

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM customers
                WHERE lower(name) = ? AND id != ? AND deleted_at IS NULL
                ORDER BY name COLLATE NOCASE
                """,
                (normalized, exclude_id),
            ).fetchall()

        return [self._to_customer(row) for row in rows]

    # --------------------------------------------------

    def archive(self, customer_id, actor, reason):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE customers
                SET status = 'Archived',
                    archived_at = ?,
                    archived_by = ?,
                    archive_reason = ?,
                    updated_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, reason, self._timestamp(), actor, customer_id),
            )

    # --------------------------------------------------

    def reactivate(self, customer_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE customers
                SET status = 'Active',
                    archived_at = NULL,
                    archived_by = NULL,
                    archive_reason = '',
                    updated_at = ?,
                    updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, customer_id),
            )

    # --------------------------------------------------

    def delete(self, customer_id):
        """Hard, permanent delete - only ever called from the Recycle Bin
        ("Permanently Delete"), never directly from the normal CRM flow."""

        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM customers WHERE id = ?",
                (customer_id,),
            )

    # --------------------------------------------------

    def soft_delete(self, customer_id, actor):
        """Move to the Recycle Bin - independent of Archive (a customer
        can be Active/Archived AND separately deleted). Hidden from every
        normal query until restored or permanently deleted."""

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE customers SET deleted_at = ?, deleted_by = ? WHERE id = ?",
                (self._timestamp(), actor, customer_id),
            )

    # --------------------------------------------------

    def restore(self, customer_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE customers SET deleted_at = NULL, deleted_by = NULL, updated_at = ?, updated_by = ? WHERE id = ?",
                (self._timestamp(), actor, customer_id),
            )

    # --------------------------------------------------

    def list_deleted(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM customers WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
            ).fetchall()

        return [self._to_customer(row) for row in rows]

    # --------------------------------------------------

    def _timestamp(self):

        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def _to_customer(self, row):

        return Customer(
            id=row["id"],
            customer_number=row["customer_number"] or "",
            name=row["name"],
            customer_type=row["customer_type"],
            status=row["status"],
            payment_terms=row["payment_terms"],
            email=row["email"],
            phone=row["phone"],
            website=row["website"],
            vat_number=row["vat_number"],
            registration_number=row["registration_number"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"] or "",
            updated_by=row["updated_by"] or "",
            archived_at=row["archived_at"] or "",
            archived_by=row["archived_by"] or "",
            archive_reason=row["archive_reason"] or "",
            deleted_at=row["deleted_at"] or "",
            deleted_by=row["deleted_by"] or "",
        )


class ContactRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def save(self, contact):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO customer_contacts (
                    id, customer_id, name, job_title, email, phone, mobile,
                    notes, is_primary, created_at, updated_at, created_by,
                    updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    customer_id = excluded.customer_id,
                    name = excluded.name,
                    job_title = excluded.job_title,
                    email = excluded.email,
                    phone = excluded.phone,
                    mobile = excluded.mobile,
                    notes = excluded.notes,
                    is_primary = excluded.is_primary,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    contact.id,
                    contact.customer_id,
                    contact.name,
                    contact.job_title,
                    contact.email,
                    contact.phone,
                    contact.mobile,
                    contact.notes,
                    1 if contact.is_primary else 0,
                    contact.created_at,
                    contact.updated_at,
                    contact.created_by,
                    contact.updated_by,
                ),
            )

        return contact

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM customer_contacts
                WHERE customer_id = ? AND deleted_at IS NULL
                ORDER BY is_primary DESC, name COLLATE NOCASE
                """,
                (customer_id,),
            ).fetchall()

        return [self._to_contact(row) for row in rows]

    # --------------------------------------------------

    def list_all(self):
        """Every contact across every customer, newest first - used for
        cross-customer views like the Dashboard's total contact count
        and recent-activity feed, as opposed to list_for_customer's
        single-customer scope."""

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM customer_contacts
                WHERE deleted_at IS NULL
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [self._to_contact(row) for row in rows]

    # --------------------------------------------------

    def get(self, contact_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM customer_contacts WHERE id = ? AND deleted_at IS NULL",
                (contact_id,),
            ).fetchone()

        return self._to_contact(row) if row else None

    # --------------------------------------------------

    def find_contacts_by_email(self, email):

        normalized_email = str(email or "").strip().lower()

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM customer_contacts
                WHERE lower(email) = ? AND deleted_at IS NULL
                ORDER BY name COLLATE NOCASE
                """,
                (normalized_email,),
            ).fetchall()

        return [self._to_contact(row) for row in rows]

    # --------------------------------------------------

    def set_primary(self, customer_id, contact_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE customer_contacts
                SET is_primary = 0, updated_at = ?, updated_by = ?
                WHERE customer_id = ? AND id != ?
                """,
                (self._timestamp(), actor, customer_id, contact_id),
            )
            connection.execute(
                """
                UPDATE customer_contacts
                SET is_primary = 1, updated_at = ?, updated_by = ?
                WHERE id = ? AND customer_id = ?
                """,
                (self._timestamp(), actor, contact_id, customer_id),
            )

    # --------------------------------------------------

    def archive(self, contact_id, actor, reason):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE customer_contacts
                SET archived_at = ?, archived_by = ?, archive_reason = ?,
                    updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, reason, self._timestamp(), actor, contact_id),
            )

    # --------------------------------------------------

    def reactivate(self, contact_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE customer_contacts
                SET archived_at = NULL, archived_by = NULL, archive_reason = '',
                    updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, contact_id),
            )

    # --------------------------------------------------

    def delete(self, contact_id):
        """Hard, permanent delete - only ever called from the Recycle Bin."""

        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM customer_contacts WHERE id = ?",
                (contact_id,),
            )

    # --------------------------------------------------

    def soft_delete(self, contact_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE customer_contacts SET deleted_at = ?, deleted_by = ? WHERE id = ?",
                (self._timestamp(), actor, contact_id),
            )

    # --------------------------------------------------

    def restore(self, contact_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE customer_contacts SET deleted_at = NULL, deleted_by = NULL, updated_at = ?, updated_by = ? WHERE id = ?",
                (self._timestamp(), actor, contact_id),
            )

    # --------------------------------------------------

    def list_deleted(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM customer_contacts WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
            ).fetchall()

        return [self._to_contact(row) for row in rows]

    # --------------------------------------------------

    def _timestamp(self):

        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def _to_contact(self, row):

        return Contact(
            id=row["id"],
            customer_id=row["customer_id"],
            is_primary=bool(row["is_primary"]),
            name=row["name"],
            job_title=row["job_title"],
            email=row["email"],
            phone=row["phone"],
            mobile=row["mobile"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"] or "",
            updated_by=row["updated_by"] or "",
            archived_at=row["archived_at"] or "",
            archived_by=row["archived_by"] or "",
            archive_reason=row["archive_reason"] or "",
            deleted_at=row["deleted_at"] or "",
            deleted_by=row["deleted_by"] or "",
        )


class AddressRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def save(self, address):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO customer_addresses (
                    id, customer_id, address_type, line1, line2, city,
                    province, postal_code, country, is_primary, created_at,
                    updated_at, created_by, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    customer_id = excluded.customer_id,
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
                    address.customer_id,
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
                    address.created_by,
                    address.updated_by,
                ),
            )

        return address

    # --------------------------------------------------

    def get(self, address_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM customer_addresses WHERE id = ? AND deleted_at IS NULL",
                (address_id,),
            ).fetchone()

        return self._to_address(row) if row else None

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM customer_addresses
                WHERE customer_id = ? AND deleted_at IS NULL
                ORDER BY is_primary DESC, address_type COLLATE NOCASE
                """,
                (customer_id,),
            ).fetchall()

        return [self._to_address(row) for row in rows]

    # --------------------------------------------------

    def count_sites_using(self, address_id):
        """How many (non-deleted) Sites reference this Address - used to
        block deleting an Address a Site still depends on."""

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM customer_sites WHERE address_id = ? AND deleted_at IS NULL",
                (address_id,),
            ).fetchone()

        return row[0]

    # --------------------------------------------------

    def archive(self, address_id, actor, reason):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE customer_addresses
                SET archived_at = ?, archived_by = ?, archive_reason = ?,
                    updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, reason, self._timestamp(), actor, address_id),
            )

    # --------------------------------------------------

    def reactivate(self, address_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE customer_addresses
                SET archived_at = NULL, archived_by = NULL, archive_reason = '',
                    updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, address_id),
            )

    # --------------------------------------------------

    def delete(self, address_id):
        """Hard, permanent delete - only ever called from the Recycle Bin."""

        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM customer_addresses WHERE id = ?",
                (address_id,),
            )

    # --------------------------------------------------

    def soft_delete(self, address_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE customer_addresses SET deleted_at = ?, deleted_by = ? WHERE id = ?",
                (self._timestamp(), actor, address_id),
            )

    # --------------------------------------------------

    def restore(self, address_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE customer_addresses SET deleted_at = NULL, deleted_by = NULL, updated_at = ?, updated_by = ? WHERE id = ?",
                (self._timestamp(), actor, address_id),
            )

    # --------------------------------------------------

    def list_deleted(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM customer_addresses WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
            ).fetchall()

        return [self._to_address(row) for row in rows]

    # --------------------------------------------------

    def _timestamp(self):

        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def _to_address(self, row):

        return Address(
            id=row["id"],
            customer_id=row["customer_id"],
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
            created_by=row["created_by"] or "",
            updated_by=row["updated_by"] or "",
            archived_at=row["archived_at"] or "",
            archived_by=row["archived_by"] or "",
            archive_reason=row["archive_reason"] or "",
            deleted_at=row["deleted_at"] or "",
            deleted_by=row["deleted_by"] or "",
        )


class SiteRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def save(self, site):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO customer_sites (
                    id, customer_id, address_id, name, site_type, notes,
                    warranty_installed_date,
                    created_at, updated_at, created_by, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    customer_id = excluded.customer_id,
                    address_id = excluded.address_id,
                    name = excluded.name,
                    site_type = excluded.site_type,
                    notes = excluded.notes,
                    warranty_installed_date = excluded.warranty_installed_date,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    site.id,
                    site.customer_id,
                    # customer_sites.address_id is a nullable foreign
                    # key onto customer_addresses. The Site dataclass
                    # defaults it to "", which is not NULL to SQLite
                    # and is not a real address row either, so saving a
                    # site that has no address raised "FOREIGN KEY
                    # constraint failed". Store the absence as NULL.
                    site.address_id or None,
                    site.name,
                    site.site_type,
                    site.notes,
                    site.warranty_installed_date,
                    site.created_at,
                    site.updated_at,
                    site.created_by,
                    site.updated_by,
                ),
            )

        return site

    # --------------------------------------------------

    def get(self, site_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM customer_sites WHERE id = ? AND deleted_at IS NULL", (site_id,),
            ).fetchone()

        return self._to_site(row) if row else None

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM customer_sites
                WHERE customer_id = ? AND deleted_at IS NULL
                ORDER BY name COLLATE NOCASE
                """,
                (customer_id,),
            ).fetchall()

        return [self._to_site(row) for row in rows]

    # --------------------------------------------------

    def list_all(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM customer_sites WHERE deleted_at IS NULL ORDER BY name COLLATE NOCASE"
            ).fetchall()

        return [self._to_site(row) for row in rows]

    # --------------------------------------------------

    def archive(self, site_id, actor, reason):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE customer_sites
                SET archived_at = ?, archived_by = ?, archive_reason = ?,
                    updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, reason, self._timestamp(), actor, site_id),
            )

    # --------------------------------------------------

    def reactivate(self, site_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE customer_sites
                SET archived_at = NULL, archived_by = NULL, archive_reason = '',
                    updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, site_id),
            )

    # --------------------------------------------------

    def delete(self, site_id):
        """Hard, permanent delete - only ever called from the Recycle Bin."""

        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM customer_sites WHERE id = ?",
                (site_id,),
            )

    # --------------------------------------------------

    def soft_delete(self, site_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE customer_sites SET deleted_at = ?, deleted_by = ? WHERE id = ?",
                (self._timestamp(), actor, site_id),
            )

    # --------------------------------------------------

    def restore(self, site_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE customer_sites SET deleted_at = NULL, deleted_by = NULL, updated_at = ?, updated_by = ? WHERE id = ?",
                (self._timestamp(), actor, site_id),
            )

    # --------------------------------------------------

    def list_deleted(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM customer_sites WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
            ).fetchall()

        return [self._to_site(row) for row in rows]

    # --------------------------------------------------

    def _timestamp(self):

        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def _to_site(self, row):

        return Site(
            id=row["id"],
            customer_id=row["customer_id"],
            address_id=row["address_id"] or "",
            name=row["name"],
            site_type=row["site_type"],
            notes=row["notes"],
            warranty_installed_date=row["warranty_installed_date"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"] or "",
            updated_by=row["updated_by"] or "",
            archived_at=row["archived_at"] or "",
            archived_by=row["archived_by"] or "",
            archive_reason=row["archive_reason"] or "",
            deleted_at=row["deleted_at"] or "",
            deleted_by=row["deleted_by"] or "",
        )


class ActivityRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def save(self, activity):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO customer_activities (
                    id, customer_id, contact_id, site_id, source_entity_type,
                    source_entity_id, activity_type, subject, activity_date,
                    status, notes, created_at, updated_at, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    contact_id = excluded.contact_id,
                    site_id = excluded.site_id,
                    source_entity_type = excluded.source_entity_type,
                    source_entity_id = excluded.source_entity_id,
                    activity_type = excluded.activity_type,
                    subject = excluded.subject,
                    activity_date = excluded.activity_date,
                    status = excluded.status,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    activity.id,
                    activity.customer_id,
                    activity.contact_id or None,
                    activity.site_id or None,
                    activity.source_entity_type,
                    activity.source_entity_id,
                    activity.activity_type,
                    activity.subject,
                    activity.activity_date,
                    activity.status,
                    activity.notes,
                    activity.created_at,
                    activity.updated_at,
                    activity.created_by,
                ),
            )

        return activity

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM customer_activities
                WHERE customer_id = ? AND deleted_at IS NULL
                ORDER BY activity_date DESC, subject COLLATE NOCASE
                """,
                (customer_id,),
            ).fetchall()

        return [self._to_activity(row) for row in rows]

    # --------------------------------------------------

    def list_all(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM customer_activities
                WHERE deleted_at IS NULL
                ORDER BY activity_date DESC, subject COLLATE NOCASE
                """
            ).fetchall()

        return [self._to_activity(row) for row in rows]

    # --------------------------------------------------

    def get(self, activity_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM customer_activities WHERE id = ? AND deleted_at IS NULL", (activity_id,),
            ).fetchone()

        return self._to_activity(row) if row else None

    # --------------------------------------------------

    def delete(self, activity_id):
        """Hard, permanent delete - only ever called from the Recycle Bin."""

        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM customer_activities WHERE id = ?",
                (activity_id,),
            )

    # --------------------------------------------------

    def soft_delete(self, activity_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE customer_activities SET deleted_at = ?, deleted_by = ? WHERE id = ?",
                (self._timestamp(), actor, activity_id),
            )

    # --------------------------------------------------

    def restore(self, activity_id, actor):

        with self.db.connect() as connection:
            connection.execute(
                "UPDATE customer_activities SET deleted_at = NULL, deleted_by = NULL, updated_at = ? WHERE id = ?",
                (self._timestamp(), activity_id),
            )

    # --------------------------------------------------

    def list_deleted(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM customer_activities WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
            ).fetchall()

        return [self._to_activity(row) for row in rows]

    # --------------------------------------------------

    def _timestamp(self):

        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def _to_activity(self, row):

        return Activity(
            id=row["id"],
            customer_id=row["customer_id"],
            contact_id=row["contact_id"] or "",
            site_id=row["site_id"] or "",
            source_entity_type=row["source_entity_type"] or "",
            source_entity_id=row["source_entity_id"] or "",
            activity_type=row["activity_type"],
            subject=row["subject"],
            activity_date=row["activity_date"],
            status=row["status"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"] or "",
            deleted_at=row["deleted_at"] or "",
            deleted_by=row["deleted_by"] or "",
        )
