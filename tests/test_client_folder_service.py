"""Tests for ClientFolderService - the real per-customer folder tree
(Paperwork/Images/Site Visit/Returned Documents) mapped out with
Minette 2026-08-07 as the foundation for Site Visit.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.client_folder_service import SUBFOLDERS, ClientFolderService
from core.customer import Customer


def _build_schema(path):
    """Minimal schema matching migration v0025's business_settings column."""

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


class ClientFolderServiceTests(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.database_path = Path(self._temp.name) / "test.db"
        _build_schema(self.database_path)
        self.root = Path(self._temp.name) / "Clients"
        self.service = ClientFolderService(database_path=self.database_path)
        self.service.set_clients_root(self.root)

    def test_clients_root_is_created_and_configurable(self):
        self.assertEqual(self.service.get_clients_root(), self.root)
        self.assertTrue(self.root.is_dir())

    def test_folder_name_includes_customer_number_for_uniqueness(self):
        customer = Customer(name="The Cavaleros Group", customer_number="CAV-001")
        self.assertEqual(self.service.folder_name_for(customer), "The Cavaleros Group (CAV-001)")

    def test_folder_name_strips_windows_invalid_characters(self):
        customer = Customer(name='A/B: "Shade" Co? *', customer_number="ABC-001")
        name = self.service.folder_name_for(customer)
        for char in '<>:"/\\|?*':
            self.assertNotIn(char, name)

    def test_ensure_client_folder_creates_all_subfolders(self):
        customer = Customer(name="Komatsu Africa", customer_number="KOM-001")

        folder = self.service.ensure_client_folder(customer)

        self.assertEqual(folder, self.root / "Komatsu Africa (KOM-001)")
        for subfolder in SUBFOLDERS:
            self.assertTrue((folder / subfolder).is_dir(), subfolder)

    def test_ensure_client_folder_is_idempotent(self):
        customer = Customer(name="Komatsu Africa", customer_number="KOM-001")

        first = self.service.ensure_client_folder(customer)
        (first / "Images" / "test.jpg").write_text("placeholder")
        second = self.service.ensure_client_folder(customer)

        self.assertEqual(first, second)
        self.assertTrue((second / "Images" / "test.jpg").is_file())

    def test_ensure_client_folder_returns_none_without_a_customer_number(self):
        customer = Customer(name="Not Yet Numbered", customer_number="")

        self.assertIsNone(self.service.ensure_client_folder(customer))

    def test_two_customers_with_the_same_name_get_different_folders(self):
        first = Customer(name="Cavaleros", customer_number="CAV-001")
        second = Customer(name="Cavaleros", customer_number="CAV-002")

        first_folder = self.service.ensure_client_folder(first)
        second_folder = self.service.ensure_client_folder(second)

        self.assertNotEqual(first_folder, second_folder)


if __name__ == "__main__":
    unittest.main()
