# ==========================================================
# FC Hub - Supplier Pricing Service
# ----------------------------------------------------------
# Purpose:
# Business rules for user-editable supplier cost items -
# steel, netting, paint, hardware, labour add-ons - so quote
# and structure costing never depends on hardcoded numbers
# that go stale as supplier prices change.
#
# Author: Minette & Claude
# Version: 1.0
# ==========================================================

from datetime import datetime
from uuid import uuid4

from core.supplier_pricing import SupplierPriceItem
from core.supplier_pricing_repository import CATEGORIES, SupplierPriceItemRepository


class SupplierPricingService:

    def __init__(self, repository=None):

        self.repository = repository or SupplierPriceItemRepository()

    # --------------------------------------------------

    def list_items(self, category, include_inactive=False):

        return self.repository.list_for_category(category, include_inactive)

    # --------------------------------------------------

    def new_item(self, category):

        return SupplierPriceItem(category=category)

    # --------------------------------------------------

    def save_item(self, item, actor=""):

        now = self._timestamp()

        if not item.id:
            item.id = self._id()
            item.created_at = now
            if not item.sort_order:
                item.sort_order = self.repository.next_sort_order(item.category)

        if not item.created_at:
            item.created_at = now

        item.updated_at = now
        item.updated_by = actor
        item.item_name = item.item_name.strip()
        item.supplier_name = item.supplier_name.strip()
        item.unit = item.unit.strip()
        item.spec = (item.spec or "").strip()

        if item.category not in CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(CATEGORIES)}.")
        if not item.item_name:
            raise ValueError("An item name is required.")
        if not item.supplier_name:
            raise ValueError("A supplier is required.")
        if not item.unit:
            raise ValueError("A unit is required.")
        if item.cost_minor < 0:
            raise ValueError("Cost cannot be negative.")

        return self.repository.save(item)

    # --------------------------------------------------

    def deactivate_item(self, item_id, actor=""):

        self.repository.set_active(item_id, False, actor)

    # --------------------------------------------------

    def reactivate_item(self, item_id, actor=""):

        self.repository.set_active(item_id, True, actor)

    # --------------------------------------------------

    def delete_item(self, item_id):

        self.repository.delete(item_id)

    # --------------------------------------------------

    def _id(self):

        return str(uuid4())

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now().isoformat(timespec="seconds")
