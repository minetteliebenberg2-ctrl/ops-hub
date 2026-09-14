# ==========================================================
# FC Hub - Picklist Service
# ----------------------------------------------------------
# Purpose:
# Business rules for user-managed picklists: payment terms
# (with real deposit/balance percentages) and customer types,
# with room for future lists.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime
from uuid import uuid4

from core.picklist import PicklistOption
from core.picklist_repository import PicklistOptionRepository


PAYMENT_TERMS = "payment_terms"
CUSTOMER_TYPE = "customer_type"
LINE_ITEM_TYPE = "line_item_type"
DOCUMENT_CATEGORY = "document_category"

PERCENTAGE_LISTS = {PAYMENT_TERMS}


class PicklistService:

    def __init__(self, repository=None):

        self.repository = repository or PicklistOptionRepository()

    # --------------------------------------------------

    def list_values(self, list_name, include_inactive=False):
        """Just the display strings, in order — the common case for
        populating a dropdown."""

        return [option.value for option in self.repository.list_for(list_name, include_inactive)]

    # --------------------------------------------------

    def list_options(self, list_name, include_inactive=False):

        return self.repository.list_for(list_name, include_inactive)

    # --------------------------------------------------

    def new_option(self, list_name):

        return PicklistOption(list_name=list_name)

    # --------------------------------------------------

    def save_option(self, option, actor=""):

        now = self._timestamp()

        if not option.id:
            option.id = self._id()
            option.created_at = now
            if not option.sort_order:
                option.sort_order = self.repository.next_sort_order(option.list_name)

        if not option.created_at:
            option.created_at = now

        option.updated_at = now
        option.updated_by = actor
        option.value = option.value.strip()

        if not option.value:
            raise ValueError("A value is required.")

        if option.list_name in PERCENTAGE_LISTS:
            deposit = option.deposit_percentage if option.deposit_percentage is not None else 0
            balance = option.balance_percentage if option.balance_percentage is not None else 0
            if round(deposit + balance, 2) != 100:
                raise ValueError("Deposit % and balance % must add up to 100.")

        return self.repository.save(option)

    # --------------------------------------------------

    def deactivate_option(self, option_id, actor=""):

        self.repository.set_active(option_id, False, actor)

    # --------------------------------------------------

    def reactivate_option(self, option_id, actor=""):

        self.repository.set_active(option_id, True, actor)

    # --------------------------------------------------

    def delete_option(self, option_id):

        self.repository.delete(option_id)

    # --------------------------------------------------

    def _id(self):

        return str(uuid4())

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now().isoformat(timespec="seconds")
