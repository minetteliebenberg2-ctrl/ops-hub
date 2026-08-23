# ==========================================================
# FC Hub - Job Card Service
# ----------------------------------------------------------
# Purpose:
# Business rules for Job Cards: create one against a customer/site
# (allocating its number), edit its header fields, and manage its
# work-log entries.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import date, datetime
from uuid import uuid4

from core.job_card import JobCard, JobCardEntry, CLOSED, OPEN
from core.job_card_repository import JobCardRepository


class JobCardService:

    def __init__(self, repository=None):

        self.job_cards = repository or JobCardRepository()

    # --------------------------------------------------

    def create_job_card(self, customer, site, actor, purchase_order=""):

        job_card = self.job_cards.create(customer.id, site.id, actor)
        job_card.purchase_order = purchase_order
        job_card.bill_to_name = customer.name
        return self.job_cards.save(job_card, actor)

    # --------------------------------------------------

    def create_job_card_from_quote(self, customer, site_id, actor, purchase_order="",
                                    quote_number="", bill_to="", accepted_date=""):
        """Create a job card from an accepted quote. site_id may be empty."""

        job_card = self.job_cards.create(customer.id, site_id or "", actor)
        job_card.purchase_order = purchase_order
        job_card.bill_to_name = bill_to or customer.name
        notes_parts = []
        if quote_number:
            notes_parts.append(f"Created from accepted quote {quote_number}")
        if accepted_date:
            notes_parts.append(f"Accepted: {accepted_date}")
        job_card.notes = "\n".join(notes_parts)
        return self.job_cards.save(job_card, actor)

    # --------------------------------------------------

    def save_job_card(self, job_card, actor):

        return self.job_cards.save(job_card, actor)

    # --------------------------------------------------

    def get_job_card(self, job_card_id):

        return self.job_cards.get(job_card_id)

    # --------------------------------------------------

    def list_job_cards_for_site(self, site_id):

        return self.job_cards.list_for_site(site_id)

    # --------------------------------------------------

    def list_job_cards_for_customer(self, customer_id):

        return self.job_cards.list_for_customer(customer_id)

    # --------------------------------------------------

    def close_job_card(self, job_card, actor):

        job_card.status = CLOSED
        return self.job_cards.save(job_card, actor)

    # --------------------------------------------------

    def reopen_job_card(self, job_card, actor):

        job_card.status = OPEN
        return self.job_cards.save(job_card, actor)

    # --------------------------------------------------

    def archive_job_card(self, job_card_id, actor, reason):

        if not reason.strip():
            raise ValueError("An archive reason is required.")
        self.job_cards.archive(job_card_id, actor, reason.strip())

    # --------------------------------------------------

    def reactivate_job_card(self, job_card_id, actor):

        self.job_cards.reactivate(job_card_id, actor)

    # --------------------------------------------------
    # Entries
    # --------------------------------------------------

    def list_entries(self, job_card_id):

        return self.job_cards.list_entries_for_card(job_card_id)

    # --------------------------------------------------

    def new_entry(self, job_card_id):

        return JobCardEntry(job_card_id=job_card_id, entry_date=date.today().isoformat())

    # --------------------------------------------------

    def save_entry(self, entry):

        if not entry.entry_date:
            raise ValueError("A date is required.")

        now = self._timestamp()
        if not entry.id:
            entry.id = str(uuid4())
            entry.created_at = now
        entry.updated_at = now

        return self.job_cards.save_entry(entry)

    # --------------------------------------------------

    def delete_entry(self, entry_id):

        self.job_cards.delete_entry(entry_id)

    # --------------------------------------------------

    @staticmethod
    def _timestamp():

        return datetime.now().isoformat()
