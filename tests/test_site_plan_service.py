"""Tests for SitePlanService - the persistent per-Site diagram data
layer, mapped out with Minette 2026-08-07."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.client_folder_service import ClientFolderService
from core.crm_repository import ActivityRepository, AddressRepository, ContactRepository, CustomerRepository, SiteRepository
from core.crm_service import CRMService
from core.database import Database
from core.image_processing_service import MAX_DIMENSION
from core.site_plan_repository import SitePlanRepository
from core.site_plan_service import SitePlanService


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


class SitePlanServiceTests(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        temp_path = Path(self._temp.name)

        db_path = tempfile.mktemp(suffix=".db")
        self.addCleanup(lambda: os.path.exists(db_path) and os.remove(db_path))
        self.test_db = Database(db_path)

        settings_db_path = temp_path / "settings.db"
        _build_client_folder_schema(settings_db_path)
        self.folder_service = ClientFolderService(database_path=settings_db_path)
        self.folder_service.set_clients_root(temp_path / "Clients")

        self.crm_service = CRMService(
            customer_repository=CustomerRepository(db=self.test_db),
            contact_repository=ContactRepository(db=self.test_db),
            address_repository=AddressRepository(db=self.test_db),
            site_repository=SiteRepository(db=self.test_db),
            activity_repository=ActivityRepository(db=self.test_db),
            client_folder_service=self.folder_service,
        )
        customer = self.crm_service.new_customer()
        customer.name = "The Cavaleros Group"
        customer.status = "Active"
        customer.payment_terms = "Standard"
        self.customer = self.crm_service.save_customer(customer)

        address = self.crm_service.new_address(self.customer.id)
        address.address_type = "Site"
        address.line1 = "Eastgate Office Park"
        address = self.crm_service.save_address(address)
        site = self.crm_service.new_site(self.customer.id)
        site.name = "Block A"
        site.address_id = address.id
        self.site = self.crm_service.save_site(site)

        self.service = SitePlanService(repository=SitePlanRepository(db=self.test_db), client_folder_service=self.folder_service)

        self.backdrop_source = temp_path / "google_screenshot.jpg"
        Image.new("RGB", (1200, 900), color="green").save(self.backdrop_source, "JPEG")

    def test_get_or_create_plan_creates_once(self):
        first = self.service.get_or_create_plan(self.site, "minette")
        second = self.service.get_or_create_plan(self.site, "minette")

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.backdrop_filename, "")

    def test_set_backdrop_image_processes_and_saves_a_real_file(self):
        plan = self.service.get_or_create_plan(self.site, "minette")

        updated = self.service.set_backdrop_image(plan, self.backdrop_source, self.customer, "minette")

        self.assertNotEqual(updated.backdrop_filename, "")
        # The 1200x900 source goes through the same downscale as any
        # site photo (MAX_DIMENSION on the long edge), keeping 4:3.
        self.assertEqual(updated.backdrop_width, MAX_DIMENSION)
        self.assertEqual(updated.backdrop_height, MAX_DIMENSION * 3 // 4)
        path = self.service.backdrop_path(updated, self.customer)
        self.assertTrue(path.is_file())

    def test_backdrop_path_is_none_before_a_backdrop_is_set(self):
        plan = self.service.get_or_create_plan(self.site, "minette")
        self.assertIsNone(self.service.backdrop_path(plan, self.customer))

    def test_clear_backdrop_image_resets_to_the_default_grid(self):
        plan = self.service.get_or_create_plan(self.site, "minette")
        plan = self.service.set_backdrop_image(plan, self.backdrop_source, self.customer, "minette")
        self.assertNotEqual(plan.backdrop_filename, "")

        cleared = self.service.clear_backdrop_image(plan, "minette")

        self.assertEqual(cleared.backdrop_filename, "")
        self.assertEqual(cleared.backdrop_width, 0)
        self.assertEqual(cleared.backdrop_height, 0)
        self.assertIsNone(self.service.backdrop_path(cleared, self.customer))

    def test_save_item_requires_structure_type(self):
        plan = self.service.get_or_create_plan(self.site, "minette")
        item = self.service.new_item(plan.id, x=0.1, y=0.1, width=0.2, height=0.15)

        with self.assertRaises(ValueError):
            self.service.save_item(item)

    def test_save_and_list_items_carries_car_bays(self):
        plan = self.service.get_or_create_plan(self.site, "minette")
        item = self.service.new_item(plan.id, x=0.1, y=0.2, width=0.15, height=0.1)
        item.structure_type = "Cantilever"
        item.car_bays = 2

        self.service.save_item(item)

        items = self.service.list_items(plan.id)
        self.assertEqual(items[0].car_bays, 2)

    def test_save_and_list_items_carries_quote_line_item_fields(self):
        plan = self.service.get_or_create_plan(self.site, "minette")
        item = self.service.new_item(plan.id, x=0.1, y=0.2, width=0.15, height=0.1)
        item.structure_type = "Restitch Net"
        item.description = "Block A - net 3"
        item.quantity = 2
        item.unit_price_minor = 177500

        saved = self.service.save_item(item)

        self.assertEqual(saved.amount_minor, 355000)
        items = self.service.list_items(plan.id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].structure_type, "Restitch Net")
        self.assertEqual(items[0].x, 0.1)

    def test_delete_item(self):
        plan = self.service.get_or_create_plan(self.site, "minette")
        item = self.service.new_item(plan.id, x=0.1, y=0.1, width=0.1, height=0.1)
        item.structure_type = "Replace Cable"
        saved = self.service.save_item(item)

        self.service.delete_item(saved.id)

        self.assertEqual(self.service.list_items(plan.id), [])

    def test_items_are_scoped_to_their_own_plan(self):
        plan_a = self.service.get_or_create_plan(self.site, "minette")
        item = self.service.new_item(plan_a.id, x=0.1, y=0.1, width=0.1, height=0.1)
        item.structure_type = "Restitch Net"
        self.service.save_item(item)

        address2 = self.crm_service.new_address(self.customer.id)
        address2.address_type = "Site"
        address2.line1 = "Eastgate Office Park"
        address2 = self.crm_service.save_address(address2)
        site_b = self.crm_service.new_site(self.customer.id)
        site_b.name = "Block B"
        site_b.address_id = address2.id
        site_b = self.crm_service.save_site(site_b)
        plan_b = self.service.get_or_create_plan(site_b, "minette")

        self.assertEqual(len(self.service.list_items(plan_a.id)), 1)
        self.assertEqual(len(self.service.list_items(plan_b.id)), 0)


if __name__ == "__main__":
    unittest.main()
