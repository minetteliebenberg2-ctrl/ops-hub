# ==========================================================
# FC Hub - Site Plan Service
# ----------------------------------------------------------
# Purpose:
# Business rules for the persistent per-Site diagram: get-or-create
# the plan, set its backdrop image, and manage the rectangles
# (each one a prospective Quote line item at once).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime
from uuid import uuid4

from core.client_folder_service import ClientFolderService
from core.image_processing_service import ImageProcessingService
from core.site_plan import GRID_TEMPLATES, SitePlan, SitePlanItem
from core.site_plan_repository import SitePlanRepository


class SitePlanService:

    def __init__(self, repository=None, client_folder_service=None, image_processor=None):

        self.plans = repository or SitePlanRepository()
        self.client_folder_service = client_folder_service or ClientFolderService()
        self.image_processor = image_processor or ImageProcessingService()

    # --------------------------------------------------

    def get_or_create_plan(self, site, actor=""):
        """Every Site effectively has exactly one plan - create it
        empty (no backdrop yet) the first time it's opened rather than
        making her do a separate "New Plan" step."""

        existing = self.plans.get_for_site(site.id)
        if existing is not None:
            return existing

        now = self._timestamp()
        plan = SitePlan(
            id=self._id(), site_id=site.id, created_at=now, updated_at=now,
            created_by=actor, updated_by=actor,
        )
        return self.plans.save(plan)

    # --------------------------------------------------

    def set_backdrop_image(self, plan, source_path, customer, actor):
        """Process (resize/strip EXIF, same pipeline as any other site
        photo) and save her pasted backdrop image into the customer's
        Images folder, then point this plan at it. Fractional item
        coordinates stay correct automatically - they were never tied
        to the previous backdrop's exact pixel size."""

        client_folder = self.client_folder_service.ensure_client_folder(customer)
        if client_folder is None:
            raise ValueError("This customer has no client folder yet - save the customer first.")

        images_dir = client_folder / "Images"
        # A backdrop is a working drawing surface, not a catalogued site
        # photo, so the taken-at date and the dedup hash are both ignored
        # here - the same grid image may legitimately back several plans.
        stored_filename, width, height, _taken_at, _file_hash = self.image_processor.process(
            source_path, f"{customer.customer_number}_siteplan", images_dir,
        )

        plan.backdrop_filename = stored_filename
        plan.backdrop_width = width
        plan.backdrop_height = height
        plan.updated_at = self._timestamp()
        plan.updated_by = actor
        return self.plans.save(plan)

    # --------------------------------------------------

    def clear_backdrop_image(self, plan, actor):
        """Back to the blank default - the window falls back to its
        bundled grid template whenever backdrop_filename is empty, so
        clearing it is enough; nothing to delete off disk since the
        default grid isn't customer-specific stored data."""

        plan.backdrop_filename = ""
        plan.backdrop_width = 0
        plan.backdrop_height = 0
        plan.updated_at = self._timestamp()
        plan.updated_by = actor
        return self.plans.save(plan)

    # --------------------------------------------------

    def set_grid_orientation(self, plan, orientation, actor):
        """Portrait or landscape for the built-in grid template.

        Most of her sites are car parks - wide, not tall - so the
        portrait-only sheet wasted most of the canvas. Only affects
        plans with no uploaded backdrop of her own."""

        if orientation not in GRID_TEMPLATES:
            raise ValueError(f"Unknown grid orientation: {orientation!r}")

        plan.grid_orientation = orientation
        plan.updated_at = self._timestamp()
        plan.updated_by = actor
        return self.plans.save(plan)

    # --------------------------------------------------

    def backdrop_path(self, plan, customer):

        if not plan.backdrop_filename:
            return None
        client_folder = self.client_folder_service.get_clients_root() / self.client_folder_service.folder_name_for(customer)
        return client_folder / "Images" / plan.backdrop_filename

    # --------------------------------------------------

    def list_items(self, site_plan_id):

        return self.plans.list_items_for_plan(site_plan_id)

    # --------------------------------------------------

    def new_item(self, site_plan_id, x, y, width, height, rotation=0.0):

        return SitePlanItem(
            site_plan_id=site_plan_id, x=x, y=y, width=width, height=height,
            rotation=rotation, quantity=1,
        )

    # --------------------------------------------------

    def save_item(self, item):

        if not item.structure_type:
            raise ValueError("A structure type is required.")

        now = self._timestamp()
        if not item.id:
            item.id = self._id()
            item.created_at = now
        item.updated_at = now

        return self.plans.save_item(item)

    # --------------------------------------------------

    def delete_item(self, item_id):

        self.plans.delete_item(item_id)

    # --------------------------------------------------

    def _id(self):

        return str(uuid4())

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now().isoformat(timespec="seconds")
