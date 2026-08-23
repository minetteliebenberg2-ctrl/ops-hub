# ==========================================================
# FC Hub - Site Visit Service
# ----------------------------------------------------------
# Purpose:
# Business rules for scheduling/completing Site Visits against a
# real customer (and optionally one of their Sites).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime
from uuid import uuid4

from core.site_visit import COMPLETED, SCHEDULED
from core.site_visit_repository import SiteVisitRepository


class SiteVisitService:

    def __init__(self, repository=None):

        self.visits = repository or SiteVisitRepository()

    # --------------------------------------------------

    def new_visit(self, customer_id, site_id=""):

        from core.site_visit import SiteVisit

        return SiteVisit(customer_id=customer_id, site_id=site_id, status=SCHEDULED)

    # --------------------------------------------------

    def save_visit(self, visit, actor=""):

        if not visit.customer_id:
            raise ValueError("Select a customer for this site visit.")
        if not visit.visit_date:
            raise ValueError("A visit date is required.")

        now = self._timestamp()

        if not visit.id:
            visit.id = self._id()
            visit.created_at = now
            visit.created_by = actor

        if not visit.created_at:
            visit.created_at = now

        visit.updated_at = now
        visit.updated_by = actor

        return self.visits.save(visit)

    # --------------------------------------------------

    def get_visit(self, visit_id):

        return self.visits.get(visit_id)

    # --------------------------------------------------

    def list_visits(self, customer_id=None):

        if customer_id:
            return self.visits.list_for_customer(customer_id)
        return self.visits.list_all()

    # --------------------------------------------------

    def mark_complete(self, visit_id, actor):

        visit = self.visits.get(visit_id)
        if visit is None:
            raise ValueError("Site visit not found.")

        visit.status = COMPLETED
        return self.save_visit(visit, actor)

    # --------------------------------------------------

    def archive_visit(self, visit_id, actor, reason):

        if not reason.strip():
            raise ValueError("An archive reason is required.")

        self.visits.archive(visit_id, actor, reason.strip())

    # --------------------------------------------------

    def reactivate_visit(self, visit_id, actor):

        self.visits.reactivate(visit_id, actor)

    # --------------------------------------------------

    def _id(self):

        return str(uuid4())

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now().isoformat(timespec="seconds")
