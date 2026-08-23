"""Tests for SiteImageService - the real upload pipeline (process +
save into the customer's own Images folder + record it), mapped out
with Minette 2026-08-07."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.client_folder_service import ClientFolderService
from core.crm_repository import ActivityRepository, AddressRepository, ContactRepository, CustomerRepository, SiteRepository
from core.crm_service import CRMService
from core.customer import Customer
from core.database import Database
from core.site_image_repository import SiteImageRepository
from core.site_image_service import SiteImageService


def _build_client_folder_schema(path):
    connection = sqlite3.connect(str(path))
    connection.executescript(
        """
        CREATE TABLE business_settings (
            id TEXT PRIMARY KEY,
            updated_at TEXT NOT NULL DEFAULT '',
            clients_root TEXT NOT NULL DEFAULT ''
        );
        INSERT INTO business_settings (id) VALUES ('business');
        """
    )
    connection.commit()
    connection.close()


class SiteImageServiceTests(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        temp_path = Path(self._temp.name)

        # site_images uses the shared core.database.Database (real
        # migrations); clients_root uses ClientFolderService's own
        # direct connection (mirrors documents_root) - same split as
        # production, both pointed at throwaway locations here.
        db_path = tempfile.mktemp(suffix=".db")
        self.addCleanup(lambda: os.path.exists(db_path) and os.remove(db_path))
        self.test_db = Database(db_path)

        settings_db_path = temp_path / "settings.db"
        _build_client_folder_schema(settings_db_path)
        self.folder_service = ClientFolderService(database_path=settings_db_path)
        self.folder_service.set_clients_root(temp_path / "Clients")

        self.service = SiteImageService(
            repository=SiteImageRepository(db=self.test_db),
            client_folder_service=self.folder_service,
        )

        self.source_image = temp_path / "phone_photo.jpg"
        Image.new("RGB", (800, 600), color="blue").save(self.source_image, "JPEG")

        crm_service = CRMService(
            customer_repository=CustomerRepository(db=self.test_db),
            contact_repository=ContactRepository(db=self.test_db),
            address_repository=AddressRepository(db=self.test_db),
            site_repository=SiteRepository(db=self.test_db),
            activity_repository=ActivityRepository(db=self.test_db),
            client_folder_service=self.folder_service,
        )
        customer = crm_service.new_customer()
        customer.name = "The Cavaleros Group"
        customer.status = "Active"
        customer.payment_terms = "Standard"
        self.customer = crm_service.save_customer(customer)

    def _distinct_source(self, name, color):
        """A genuinely different photo. Uploads are deduplicated on file
        hash per customer, so any test that needs a second upload has to
        supply a second image, not the same one twice."""

        path = Path(self._temp.name) / name
        Image.new("RGB", (800, 600), color=color).save(path, "JPEG")
        return path

    def test_upload_creates_a_real_file_in_the_customer_images_folder(self):
        image = self.service.upload_image(self.source_image, self.customer, "minette", caption="Block B netting")

        stored_path = self.service.image_path(image, self.customer)
        self.assertTrue(stored_path.is_file())
        self.assertIn("Images", str(stored_path))
        self.assertIn("Cavaleros", str(stored_path))

    def test_upload_records_caption_and_dimensions(self):
        image = self.service.upload_image(self.source_image, self.customer, "minette", caption="  Block B netting  ")

        self.assertEqual(image.caption, "Block B netting")
        self.assertEqual(image.width, 800)
        self.assertEqual(image.height, 600)
        self.assertEqual(image.customer_id, self.customer.id)

    def test_upload_without_customer_number_raises(self):
        unsaved_customer = Customer(id="cust-2", name="Not Yet Saved", customer_number="")

        with self.assertRaises(ValueError):
            self.service.upload_image(self.source_image, unsaved_customer, "minette")

    def test_list_for_customer_returns_uploaded_images(self):
        self.service.upload_image(self.source_image, self.customer, "minette", caption="First")
        self.service.upload_image(
            self._distinct_source("second.jpg", "red"), self.customer, "minette", caption="Second",
        )

        images = self.service.list_for_customer(self.customer.id)
        self.assertEqual(len(images), 2)
        self.assertEqual({img.caption for img in images}, {"First", "Second"})

    def test_list_for_visit_scopes_to_that_visit_only(self):
        from core.site_visit_repository import SiteVisitRepository
        from core.site_visit_service import SiteVisitService

        visit_service = SiteVisitService(repository=SiteVisitRepository(db=self.test_db))
        visit_a = visit_service.new_visit(self.customer.id)
        visit_a.visit_date = "2026-08-10"
        visit_a = visit_service.save_visit(visit_a, "minette")
        visit_b = visit_service.new_visit(self.customer.id)
        visit_b.visit_date = "2026-08-11"
        visit_b = visit_service.save_visit(visit_b, "minette")

        self.service.upload_image(self.source_image, self.customer, "minette", site_visit_id=visit_a.id)
        self.service.upload_image(
            self._distinct_source("visit_b.jpg", "green"),
            self.customer,
            "minette",
            site_visit_id=visit_b.id,
        )

        images = self.service.list_for_visit(visit_a.id)
        self.assertEqual(len(images), 1)

    def test_update_caption(self):
        image = self.service.upload_image(self.source_image, self.customer, "minette", caption="Original")

        self.service.update_caption(image.id, "Updated caption", "minette")

        reloaded = self.service.images.get(image.id)
        self.assertEqual(reloaded.caption, "Updated caption")

    def test_archive_requires_a_reason(self):
        image = self.service.upload_image(self.source_image, self.customer, "minette")

        with self.assertRaises(ValueError):
            self.service.archive_image(image.id, "minette", "")

        self.service.archive_image(image.id, "minette", "duplicate upload")
        reloaded = self.service.images.get(image.id)
        self.assertNotEqual(reloaded.archived_at, "")

    def test_two_uploads_never_collide_on_filename(self):
        first = self.service.upload_image(self.source_image, self.customer, "minette")
        second = self.service.upload_image(
            self._distinct_source("second.jpg", "red"), self.customer, "minette",
        )

        self.assertNotEqual(first.stored_filename, second.stored_filename)
        self.assertTrue(self.service.image_path(first, self.customer).is_file())
        self.assertTrue(self.service.image_path(second, self.customer).is_file())

    def test_uploading_the_same_photo_twice_is_rejected(self):
        """Re-uploading a photo she already has is a mistake, not a
        second photo - it's refused by name so she can see which one."""

        self.service.upload_image(self.source_image, self.customer, "minette")

        with self.assertRaises(ValueError) as caught:
            self.service.upload_image(self.source_image, self.customer, "minette")

        self.assertIn("phone_photo.jpg", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
