# ==========================================================
# FC Hub - Site Image Service
# ----------------------------------------------------------
# Purpose:
# Orchestrates a real photo upload: process the file (resize/rename/
# strip EXIF), save it into the customer's own Images folder, and
# record it. Mapped out with Minette 2026-08-07 - photos are taken at
# ~99% of her site visits.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import os
from datetime import datetime
from uuid import uuid4

from core.client_folder_service import ClientFolderService
from core.image_processing_service import ImageProcessingService
from core.site_image import SiteImage
from core.site_image_repository import SiteImageRepository


class SiteImageService:

    def __init__(self, repository=None, client_folder_service=None, image_processor=None):

        self.images = repository or SiteImageRepository()
        self.client_folder_service = client_folder_service or ClientFolderService()
        self.image_processor = image_processor or ImageProcessingService()

    # --------------------------------------------------

    def upload_image(self, source_path, customer, actor, site_id="", site_visit_id="", caption=""):
        """Process a source file straight into this customer's real
        Images folder and record it. Raises ValueError if the customer
        has no folder yet (no customer_number - shouldn't happen for a
        saved customer, but fail loudly rather than silently write
        somewhere unexpected)."""

        client_folder = self.client_folder_service.ensure_client_folder(customer)
        if client_folder is None:
            raise ValueError("This customer has no client folder yet - save the customer first.")

        images_dir = client_folder / "Images"
        stored_filename, width, height, taken_at, file_hash = self.image_processor.process(
            source_path, customer.customer_number, images_dir,
        )

        existing = self.images.list_for_customer(customer.id)
        for ex in existing:
            if getattr(ex, "file_hash", "") == file_hash and file_hash:
                (images_dir / stored_filename).unlink(missing_ok=True)
                raise ValueError(f"Duplicate photo — this image was already uploaded as '{ex.original_filename}'.")

        source_size = os.path.getsize(source_path)
        saved_size = os.path.getsize(images_dir / stored_filename)

        now = datetime.now().isoformat(timespec="seconds")
        image = SiteImage(
            id=str(uuid4()),
            customer_id=customer.id,
            site_id=site_id,
            site_visit_id=site_visit_id,
            stored_filename=stored_filename,
            original_filename=os.path.basename(str(source_path)),
            caption=caption.strip(),
            width=width,
            height=height,
            taken_at=taken_at,
            created_at=now,
            updated_at=now,
            created_by=actor,
            file_hash=file_hash,
            file_size=saved_size,
        )
        return self.images.save(image)

    # --------------------------------------------------

    def image_path(self, image, customer):
        """Full path to the stored file, for display/export."""

        client_folder = self.client_folder_service.get_clients_root() / self.client_folder_service.folder_name_for(customer)
        return client_folder / "Images" / image.stored_filename

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        return self.images.list_for_customer(customer_id)

    # --------------------------------------------------

    def list_for_visit(self, site_visit_id):

        return self.images.list_for_visit(site_visit_id)

    # --------------------------------------------------

    def update_caption(self, image_id, caption, actor):

        image = self.images.get(image_id)
        if image is None:
            raise ValueError("Image not found.")
        image.caption = caption.strip()
        image.updated_at = datetime.now().isoformat(timespec="seconds")
        return self.images.save(image)

    # --------------------------------------------------

    def archive_image(self, image_id, actor, reason):

        if not reason.strip():
            raise ValueError("An archive reason is required.")
        self.images.archive(image_id, actor, reason.strip())

    # --------------------------------------------------

    def update_tags(self, image_id, tags, actor):
        """tags: comma-separated string or list of strings."""

        image = self.images.get(image_id)
        if image is None:
            raise ValueError("Image not found.")
        if isinstance(tags, (list, tuple)):
            tags = ", ".join(t.strip() for t in tags if t.strip())
        image.tags = tags.strip()
        image.updated_at = datetime.now().isoformat(timespec="seconds")
        return self.images.save(image)

    # --------------------------------------------------

    def update_album(self, image_id, album, actor):

        image = self.images.get(image_id)
        if image is None:
            raise ValueError("Image not found.")
        image.album = album.strip()
        image.updated_at = datetime.now().isoformat(timespec="seconds")
        return self.images.save(image)

    # --------------------------------------------------

    def list_albums(self, customer_id):
        """Distinct album names in use for a customer, non-empty, sorted."""

        names = {img.album for img in self.list_for_customer(customer_id) if img.album}
        return sorted(names)

    # --------------------------------------------------

    def list_tags(self, customer_id):
        """Distinct tags in use for a customer, non-empty, sorted."""

        tags = set()
        for img in self.list_for_customer(customer_id):
            tags.update(img.tag_list)
        return sorted(tags)
