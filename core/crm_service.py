# ==========================================================
# FC Utilities - CRM Service
# ----------------------------------------------------------
# Purpose:
# Business service layer for CRM.
#
# Author: Minette & James
# Version: 2.0
# ==========================================================

from datetime import datetime
from uuid import uuid4

from core.activity import Activity
from core.address import Address
from core.client_folder_service import ClientFolderService
from core.contact import Contact
from core.crm_repository import (
    AddressRepository,
    ActivityRepository,
    ContactRepository,
    CustomerRepository,
    SiteRepository,
)
from core.crm_validation import CRMValidation
from core.customer import Customer
from core.pdf_customer_extractor import ExtractedContact, split_address_lines
from core.site import Site


class CRMService:

    def __init__(
        self,
        customer_repository=None,
        contact_repository=None,
        address_repository=None,
        site_repository=None,
        activity_repository=None,
        validation=None,
        client_folder_service=None,
    ):

        self.customers = customer_repository or CustomerRepository()
        self.contacts = contact_repository or ContactRepository()
        self.addresses = address_repository or AddressRepository()
        self.sites = site_repository or SiteRepository()
        self.activities = activity_repository or ActivityRepository()
        self.validation = validation or CRMValidation()
        # Deliberately NOT called automatically from save_customer() -
        # folder creation is an explicit call at each real "a customer
        # was actually created" site (see import_contact() below, and
        # modules/crm/windows.py), not a hidden side effect of every
        # save. Plain instantiation here is side-effect-free (lazy -
        # nothing touches disk until ensure_client_folder() runs), so
        # this default is safe even for tests that never call it.
        self.client_folder_service = client_folder_service or ClientFolderService()

    # --------------------------------------------------
    # Customers
    # --------------------------------------------------

    def save_customer(self, customer):

        now = self._timestamp()

        if not customer.id:
            customer.id = self._id()
            customer.created_at = now

        if not customer.created_at:
            customer.created_at = now

        customer.updated_at = now

        customer.name = customer.name.strip()
        customer.email = customer.email.strip()
        customer.phone = customer.phone.strip()
        customer.website = customer.website.strip()
        customer.vat_number = customer.vat_number.strip()

        self.validation.validate_customer(customer)

        return self.customers.save(customer)

    # --------------------------------------------------

    def archive_customer(self, customer_id, actor, reason):

        if not reason.strip():
            raise ValueError("An archive reason is required.")

        self.customers.archive(customer_id, actor, reason.strip())

    # --------------------------------------------------

    def reactivate_customer(self, customer_id, actor):

        self.customers.reactivate(customer_id, actor)

    # --------------------------------------------------

    def delete_customer(self, customer_id, actor):
        """Move to the Recycle Bin - independent of Archive. Blocked if
        the customer still has any Contacts/Addresses/Sites/Activities
        on file (her choice, confirmed 2026-08-07: block rather than
        cascade-recycle the whole tree as one unit)."""

        if self.contacts.list_for_customer(customer_id):
            raise ValueError("This customer still has contacts on file - delete those first.")
        if self.addresses.list_for_customer(customer_id):
            raise ValueError("This customer still has addresses on file - delete those first.")
        if self.sites.list_for_customer(customer_id):
            raise ValueError("This customer still has sites on file - delete those first.")
        if self.activities.list_for_customer(customer_id):
            raise ValueError("This customer still has activity history on file - delete those first.")

        self.customers.soft_delete(customer_id, actor)

    # --------------------------------------------------

    def restore_customer(self, customer_id, actor):

        self.customers.restore(customer_id, actor)

    # --------------------------------------------------

    def purge_customer(self, customer_id):
        """Permanent, irreversible - only ever called from the Recycle
        Bin's "Permanently Delete", never the normal delete flow."""

        self.customers.delete(customer_id)

    # --------------------------------------------------

    def list_deleted_customers(self):

        return self.customers.list_deleted()

    # --------------------------------------------------

    def find_possible_duplicate_customers(self, customer):
        """Warn-only duplicate detection (master spec 7.1): matches on
        normalized email or case-insensitive name, excluding the customer
        being saved."""

        matches = {}

        for match in self.customers.find_by_normalized_email(customer.email, customer.id):
            matches[match.id] = match

        for match in self.customers.find_by_name(customer.name, customer.id):
            matches[match.id] = match

        return list(matches.values())

    # --------------------------------------------------

    def get_customer(self, customer_id):

        return self.customers.get(customer_id)

    # --------------------------------------------------

    def list_customers(self):

        return self.customers.list_all()

    # --------------------------------------------------

    def search_customers(self, term):

        if not term.strip():
            return self.list_customers()

        return self.customers.search(term)

    # --------------------------------------------------
    # Contacts
    # --------------------------------------------------

    def save_contact(self, contact):

        now = self._timestamp()

        if not contact.id:
            contact.id = self._id()
            contact.created_at = now

        if not contact.created_at:
            contact.created_at = now

        contact.updated_at = now

        contact.name = contact.name.strip()
        contact.email = contact.email.strip()
        contact.phone = contact.phone.strip()
        contact.mobile = contact.mobile.strip()

        self.validation.validate_contact(contact)

        return self.contacts.save(contact)

    # --------------------------------------------------

    def set_primary_contact(self, customer_id, contact_id, actor):

        contact = self.contacts.get(contact_id)
        if contact is None or contact.customer_id != customer_id:
            raise ValueError("The contact does not belong to this customer.")

        self.contacts.set_primary(customer_id, contact_id, actor)

    # --------------------------------------------------

    def move_contact_to_customer(self, contact_id, new_customer_id, actor):
        """Reassign a contact to a different customer, e.g. correcting a
        Communications import that created a customer named after a person
        instead of their actual company."""

        contact = self.contacts.get(contact_id)
        if contact is None:
            raise ValueError("Contact not found.")
        target = self.customers.get(new_customer_id)
        if target is None:
            raise ValueError("Target customer not found.")

        contact.customer_id = new_customer_id
        contact.is_primary = False
        contact.updated_by = actor
        return self.save_contact(contact)

    # --------------------------------------------------

    def archive_contact(self, contact_id, actor, reason):

        if not reason.strip():
            raise ValueError("An archive reason is required.")

        self.contacts.archive(contact_id, actor, reason.strip())

    # --------------------------------------------------

    def reactivate_contact(self, contact_id, actor):

        self.contacts.reactivate(contact_id, actor)

    # --------------------------------------------------

    def delete_contact(self, contact_id, actor):
        """Contacts have no children of their own - nothing to block on."""

        self.contacts.soft_delete(contact_id, actor)

    # --------------------------------------------------

    def restore_contact(self, contact_id, actor):

        self.contacts.restore(contact_id, actor)

    # --------------------------------------------------

    def purge_contact(self, contact_id):

        self.contacts.delete(contact_id)

    # --------------------------------------------------

    def list_deleted_contacts(self):

        return self.contacts.list_deleted()

    # --------------------------------------------------

    def list_contacts(self, customer_id):

        return self.contacts.list_for_customer(customer_id)

    # --------------------------------------------------

    def list_all_contacts(self):
        """Every contact across every customer - for cross-customer views
        (e.g. the Dashboard's total contact count) where list_contacts's
        single-customer scope doesn't apply."""

        return self.contacts.list_all()

    # --------------------------------------------------

    def convert_customer_to_contact(self, customer_id, target_customer_id, actor):
        """Convert a customer record that was mistakenly created for a
        person (e.g. a Communications import created "Andreas Savas" as
        his own customer instead of recognizing he belongs to "Cavaleros
        Group") into a contact of the correct company, then archive the
        original customer record.

        Reuses an existing contact under the target customer if one
        already matches by email or name, rather than creating a
        duplicate - this is the common case, since the correct contact
        often already exists alongside the mistaken customer record.
        """

        source = self.customers.get(customer_id)
        if source is None:
            raise ValueError("Customer not found.")

        target = self.customers.get(target_customer_id)
        if target is None:
            raise ValueError("Target company not found.")

        if source.id == target.id:
            raise ValueError("A customer cannot be converted into a contact of itself.")

        normalized_email = source.email.strip().lower()
        normalized_name = source.name.strip().lower()

        contact = None
        for candidate in self.list_contacts(target_customer_id):
            if normalized_email and candidate.email.strip().lower() == normalized_email:
                contact = candidate
                break
            if candidate.name.strip().lower() == normalized_name:
                contact = candidate
                break

        if contact is None:
            contact = self.new_contact(target_customer_id)
            contact.name = source.name
            contact.email = source.email
            contact.phone = source.phone
            contact.notes = source.notes
            contact.updated_by = actor
            contact = self.save_contact(contact)

        self.archive_customer(source.id, actor, f"Converted to a contact of {target.name}.")

        return contact

    # --------------------------------------------------
    # Addresses
    # --------------------------------------------------

    def save_address(self, address):

        now = self._timestamp()

        if not address.id:
            address.id = self._id()
            address.created_at = now

        if not address.created_at:
            address.created_at = now

        address.updated_at = now

        address.line1 = address.line1.strip()
        address.line2 = address.line2.strip()
        address.city = address.city.strip()
        address.province = address.province.strip()
        address.postal_code = address.postal_code.strip()
        address.country = address.country.strip()

        self.validation.validate_address(address)

        return self.addresses.save(address)

    # --------------------------------------------------

    def archive_address(self, address_id, actor, reason):

        if not reason.strip():
            raise ValueError("An archive reason is required.")

        self.addresses.archive(address_id, actor, reason.strip())

    # --------------------------------------------------

    def reactivate_address(self, address_id, actor):

        self.addresses.reactivate(address_id, actor)

    # --------------------------------------------------

    def delete_address(self, address_id, actor):
        """Blocked if a Site still references this address - deleting it
        would leave that Site pointing at nothing."""

        if self.addresses.count_sites_using(address_id) > 0:
            raise ValueError("This address is still in use by a site - change or delete that site first.")

        self.addresses.soft_delete(address_id, actor)

    # --------------------------------------------------

    def restore_address(self, address_id, actor):

        self.addresses.restore(address_id, actor)

    # --------------------------------------------------

    def purge_address(self, address_id):

        self.addresses.delete(address_id)

    # --------------------------------------------------

    def list_deleted_addresses(self):

        return self.addresses.list_deleted()

    # --------------------------------------------------

    def list_addresses(self, customer_id):

        return self.addresses.list_for_customer(customer_id)

    # --------------------------------------------------
    # Sites
    # --------------------------------------------------

    def save_site(self, site):

        now = self._timestamp()

        if not site.id:
            site.id = self._id()
            site.created_at = now

        if not site.created_at:
            site.created_at = now

        site.updated_at = now

        self.validation.validate_site(site)

        if site.address_id:
            address = self.addresses.get(site.address_id)
            if address is None or address.customer_id != site.customer_id:
                raise ValueError("The site's address must belong to the same customer.")

        return self.sites.save(site)

    # --------------------------------------------------

    def archive_site(self, site_id, actor, reason):

        if not reason.strip():
            raise ValueError("An archive reason is required.")

        self.sites.archive(site_id, actor, reason.strip())

    # --------------------------------------------------

    def reactivate_site(self, site_id, actor):

        self.sites.reactivate(site_id, actor)

    # --------------------------------------------------

    def delete_site(self, site_id, actor):
        """Move to the Recycle Bin. A Site's real "children" (Site Plan,
        Site Images, Site Visits, Job Cards, Quotes) live in other
        modules CRMService doesn't own - the caller (modules/crm/windows.py)
        is responsible for checking those and raising before this is
        ever called; this method only performs the delete itself."""

        self.sites.soft_delete(site_id, actor)

    # --------------------------------------------------

    def restore_site(self, site_id, actor):

        self.sites.restore(site_id, actor)

    # --------------------------------------------------

    def purge_site(self, site_id):

        self.sites.delete(site_id)

    # --------------------------------------------------

    def list_deleted_sites(self):

        return self.sites.list_deleted()

    # --------------------------------------------------

    def list_sites(self, customer_id=None):

        if customer_id:
            return self.sites.list_for_customer(customer_id)

        return self.sites.list_all()

    # --------------------------------------------------
    # Activities
    # --------------------------------------------------

    def save_activity(self, activity):

        now = self._timestamp()

        if not activity.id:
            activity.id = self._id()
            activity.created_at = now

        if not activity.created_at:
            activity.created_at = now

        activity.updated_at = now

        self.validation.validate_activity(activity)

        return self.activities.save(activity)

    # --------------------------------------------------

    def list_activities(self, customer_id=None):

        if customer_id:
            return self.activities.list_for_customer(customer_id)

        return self.activities.list_all()

    # --------------------------------------------------

    def delete_activity(self, activity_id, actor):
        """Activities have no children of their own - nothing to block
        on. Never had an Archive concept either (no archived_at column) -
        this is the first removal option they've ever had."""

        self.activities.soft_delete(activity_id, actor)

    # --------------------------------------------------

    def restore_activity(self, activity_id, actor):

        self.activities.restore(activity_id, actor)

    # --------------------------------------------------

    def purge_activity(self, activity_id):

        self.activities.delete(activity_id)

    # --------------------------------------------------

    def list_deleted_activities(self):

        return self.activities.list_deleted()

    # --------------------------------------------------
    # Communications import (unchanged contract)
    # --------------------------------------------------

    def import_contact(self, candidate, action, payload=None):

        payload = payload or {}
        email = str(candidate.normalized_email or candidate.original_email).strip()
        name = str(candidate.display_name or email).strip()

        if action in ("Link to Existing Contact", "Add Email to Existing Contact"):

            matches = self.contacts.find_contacts_by_email(email)

            if not matches:
                raise ValueError("No existing CRM contact matched this email.")

            return {
                "customer_id": matches[0].customer_id,
                "contact_id": matches[0].id,
            }

        if action == "Create New Contact under Existing Customer":

            customer_id = payload.get("customer_id", "")

            if not customer_id:
                raise ValueError("Select an existing customer before importing.")

            contact = self.new_contact(customer_id)
            contact.name = name
            contact.email = email
            contact.source = "Communications"
            saved_contact = self.save_contact(contact)

            return {
                "customer_id": customer_id,
                "contact_id": saved_contact.id,
            }

        if action == "Create New Customer and Contact":

            customer = self.new_customer()
            customer.name = name
            customer.email = email
            customer.status = "Active"
            saved_customer = self.save_customer(customer)
            self.client_folder_service.ensure_client_folder(saved_customer)

            contact = self.new_contact(saved_customer.id)
            contact.name = name
            contact.email = email
            contact.source = "Communications"
            saved_contact = self.save_contact(contact)

            return {
                "customer_id": saved_customer.id,
                "contact_id": saved_contact.id,
            }

        raise ValueError(f"Unsupported CRM import action: {action}")

    # --------------------------------------------------
    # PDF import (core/pdf_customer_extractor.py)
    # --------------------------------------------------

    def import_customer_from_pdf(self, extracted, actor):
        """Creates (or, on an email match, tops up) a customer from an
        ExtractedCustomer. Only ever fills in blanks on an existing
        match - never overwrites a value Minette already has on file.
        Returns (customer, created) where created is False when an
        existing customer was matched/updated instead of a new one
        being made."""

        existing_matches = (
            self.customers.find_by_normalized_email(extracted.email) if extracted.email else []
        )

        if existing_matches:
            customer = existing_matches[0]
            changed = False
            if not customer.vat_number.strip() and extracted.vat_number:
                customer.vat_number = extracted.vat_number
                changed = True
            if not customer.registration_number.strip() and extracted.registration_number:
                customer.registration_number = extracted.registration_number
                changed = True
            if changed:
                customer.updated_by = actor
                self.save_customer(customer)
            # Each document carries one address and its own contact
            # people, so importing a customer's whole document history
            # accumulates every distinct address and person on file
            # rather than the last document read winning.
            self._merge_imported_address(customer, extracted, actor)
            self._merge_imported_contacts(customer, extracted, actor)
            return customer, False

        customer = self.new_customer()
        customer.name = extracted.name
        customer.email = extracted.email
        customer.vat_number = extracted.vat_number
        customer.registration_number = extracted.registration_number
        customer.status = "Active"
        customer.created_by = actor
        customer = self.save_customer(customer)

        self._merge_imported_address(customer, extracted, actor)
        self._merge_imported_contacts(customer, extracted, actor)

        return customer, True

    # --------------------------------------------------

    def _merge_imported_address(self, customer, extracted, actor):
        """Adds the document's address unless that street line is already
        on file. The source documents never label an address as Billing/
        Delivery/Physical/Postal, so every imported address comes in as
        Billing and is re-typed in the CRM if it is something else."""

        if not extracted.address_lines:
            return 0

        line1, line2, city, postal_code = split_address_lines(extracted.address_lines)
        existing = self.list_addresses(customer.id)

        for address in existing:
            if (address.line1 or "").strip().lower() == line1.strip().lower():
                return 0

        address = self.new_address(customer.id)
        address.address_type = "Billing"
        address.line1 = line1
        address.line2 = line2
        address.city = city
        address.postal_code = postal_code
        address.is_primary = not existing
        address.created_by = actor
        self.save_address(address)
        return 1

    # --------------------------------------------------

    def _merge_imported_contacts(self, customer, extracted, actor):
        """Adds every contact person named on the document that isn't
        already on file, matched on email first and then on name. Never
        edits a contact Minette already has."""

        incoming = list(getattr(extracted, "contacts", None) or [])
        if not incoming and extracted.contact_name:
            incoming = [
                ExtractedContact(name=extracted.contact_name, email=extracted.email),
            ]

        existing = self.list_contacts(customer.id)
        seen_emails = {c.email.strip().lower() for c in existing if (c.email or "").strip()}
        seen_names = {c.name.strip().lower() for c in existing if (c.name or "").strip()}

        added = 0
        for item in incoming:
            name = (item.name or "").strip()
            email = (item.email or "").strip()
            if not name and not email:
                continue
            if email and email.lower() in seen_emails:
                continue
            if name and name.lower() in seen_names:
                continue

            contact = self.new_contact(customer.id)
            contact.name = name
            contact.email = email
            contact.phone = (item.phone or "").strip()
            contact.is_primary = not existing and added == 0
            contact.source = "PDF Import"
            contact.created_by = actor
            self.save_contact(contact)

            if email:
                seen_emails.add(email.lower())
            if name:
                seen_names.add(name.lower())
            added += 1

        return added

    # --------------------------------------------------
    # Factories
    # --------------------------------------------------

    def new_customer(self):

        return Customer()

    # --------------------------------------------------

    def new_contact(self, customer_id):

        return Contact(customer_id=customer_id)

    # --------------------------------------------------

    def new_address(self, customer_id):

        return Address(customer_id=customer_id)

    # --------------------------------------------------

    def new_site(self, customer_id):

        return Site(customer_id=customer_id)

    # --------------------------------------------------

    def new_activity(self, customer_id):

        return Activity(customer_id=customer_id)

    # --------------------------------------------------

    def _id(self):

        return str(uuid4())

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now().isoformat(timespec="seconds")
