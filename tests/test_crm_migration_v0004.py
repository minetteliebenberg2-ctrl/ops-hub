from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.database import Database
from core.migrations.runner import MigrationRunner
from core.migrations.versions.v0001_baseline import MIGRATION as BASELINE
from core.migrations.versions.v0002_candidate_signature_fields import (
    MIGRATION as SIGNATURE_FIELDS,
)
from core.migrations.versions.v0003_crm_relationship_integrity import (
    MIGRATION as RELATIONSHIP_INTEGRITY,
)
from core.migrations.versions.v0004_crm_numbering_and_sites import (
    MIGRATION as NUMBERING_AND_SITES,
)


ALL_MIGRATIONS = (BASELINE, SIGNATURE_FIELDS, RELATIONSHIP_INTEGRITY, NUMBERING_AND_SITES)


class CRMNumberingMigrationTests(unittest.TestCase):
    def make_database(self, directory, name="test.db"):
        return Database(Path(directory) / name)

    def test_fresh_database_reaches_version_four_with_only_migrations_through_v0004(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)

            state = MigrationRunner(database, migrations=ALL_MIGRATIONS).migrate()

            self.assertEqual(state.current_version, 4)
            self.assertEqual(state.pending_versions, ())

    def test_existing_customers_are_numbered_sequentially_by_creation_order(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            with database.connect() as connection:
                BASELINE.apply(connection)
                connection.execute(
                    "INSERT INTO customers (id, name, created_at, updated_at) "
                    "VALUES ('c-second', 'Second Co', '2026-01-02T00:00:00Z', '2026-01-02T00:00:00Z')"
                )
                connection.execute(
                    "INSERT INTO customers (id, name, created_at, updated_at) "
                    "VALUES ('c-first', 'First Co', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
                )

            MigrationRunner(database, migrations=ALL_MIGRATIONS).migrate()

            with database.connect() as connection:
                first = connection.execute(
                    "SELECT customer_number FROM customers WHERE id = 'c-first'"
                ).fetchone()[0]
                second = connection.execute(
                    "SELECT customer_number FROM customers WHERE id = 'c-second'"
                ).fetchone()[0]
                sequence = connection.execute(
                    "SELECT next_value FROM numbering_sequences "
                    "WHERE document_type = 'customer' AND scope = 'global'"
                ).fetchone()[0]

            self.assertEqual(first, "FAC-001")
            self.assertEqual(second, "FAC-002")
            self.assertEqual(sequence, 3)

    def test_customer_number_is_unique_and_payment_terms_defaults_to_standard(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                connection.execute(
                    "INSERT INTO customers (id, name, created_at, updated_at) "
                    "VALUES ('c-new', 'New Co', 'now', 'now')"
                )
                customer = connection.execute(
                    "SELECT customer_number, payment_terms FROM customers WHERE id = 'c-new'"
                ).fetchone()

            self.assertIsNone(customer["customer_number"])
            self.assertEqual(customer["payment_terms"], "Standard")

            with database.connect() as connection:
                connection.execute(
                    "UPDATE customers SET customer_number = 'FAC-001' WHERE id = 'c-new'"
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO customers (id, name, customer_number, created_at, updated_at) "
                        "VALUES ('c-dupe', 'Dupe Co', 'FAC-001', 'now', 'now')"
                    )

    def test_multiple_sites_for_one_customer_get_independent_structured_addresses(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            with database.connect() as connection:
                BASELINE.apply(connection)
                connection.execute(
                    "INSERT INTO customers (id, name, created_at, updated_at) "
                    "VALUES ('landlord-1', 'Landlord Co', 'now', 'now')"
                )
                connection.execute(
                    "INSERT INTO customer_sites (id, customer_id, name, address, city, province, created_at, updated_at) "
                    "VALUES ('site-a', 'landlord-1', 'Tenant A', '1 Main Rd', 'Joburg', 'Gauteng', 'now', 'now')"
                )
                connection.execute(
                    "INSERT INTO customer_sites (id, customer_id, name, address, city, province, created_at, updated_at) "
                    "VALUES ('site-b', 'landlord-1', 'Tenant B', '2 Main Rd', 'Joburg', 'Gauteng', 'now', 'now')"
                )

            MigrationRunner(database, migrations=ALL_MIGRATIONS).migrate()

            with database.connect() as connection:
                sites = connection.execute(
                    "SELECT id, address_id FROM customer_sites WHERE customer_id = 'landlord-1' ORDER BY id"
                ).fetchall()
                addresses = {
                    row["id"]: (row["line1"], row["city"])
                    for row in connection.execute(
                        "SELECT id, line1, city FROM customer_addresses WHERE customer_id = 'landlord-1'"
                    ).fetchall()
                }

            self.assertEqual(len(sites), 2)
            self.assertNotEqual(sites[0]["address_id"], sites[1]["address_id"])
            self.assertEqual(addresses[sites[0]["address_id"]], ("1 Main Rd", "Joburg"))
            self.assertEqual(addresses[sites[1]["address_id"]], ("2 Main Rd", "Joburg"))

    def test_no_site_number_column_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                columns = {row[1] for row in connection.execute('PRAGMA table_info("customer_sites")')}

            self.assertNotIn("site_number", columns)

    def test_site_address_foreign_key_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                connection.execute(
                    "INSERT INTO customers (id, name, customer_number, created_at, updated_at) "
                    "VALUES ('c-1', 'Co', 'FAC-001', 'now', 'now')"
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO customer_sites (id, customer_id, name, address_id, created_at, updated_at) "
                        "VALUES ('s-1', 'c-1', 'Site', 'missing-address', 'now', 'now')"
                    )


if __name__ == "__main__":
    unittest.main()
