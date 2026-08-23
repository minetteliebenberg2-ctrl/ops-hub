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


class CRMRelationshipIntegrityMigrationTests(unittest.TestCase):
    def make_database(self, directory, name="test.db"):
        return Database(Path(directory) / name)

    def seed_legacy_customer(self, connection, customer_id="customer-1", name="Preserved Co"):
        connection.execute(
            """
            INSERT INTO customers (id, name, created_at, updated_at)
            VALUES (?, ?, 'now', 'now')
            """,
            (customer_id, name),
        )

    def test_fresh_database_reaches_version_three_with_only_migrations_through_v0003(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)

            runner = MigrationRunner(
                database,
                migrations=(BASELINE, SIGNATURE_FIELDS, RELATIONSHIP_INTEGRITY),
            )
            state = runner.migrate()

            self.assertEqual(state.current_version, 3)
            self.assertEqual(state.pending_versions, ())

    def test_applies_cleanly_over_existing_baseline_and_signature_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            with database.connect() as connection:
                BASELINE.apply(connection)
                self.seed_legacy_customer(connection)
                connection.execute(
                    """
                    INSERT INTO customer_sites (
                        id, customer_id, name, created_at, updated_at
                    )
                    VALUES ('site-1', 'customer-1', 'Main Site', 'now', 'now')
                    """
                )
                connection.execute(
                    """
                    INSERT INTO customer_activities (
                        id, customer_id, subject, created_at, updated_at
                    )
                    VALUES ('activity-1', 'customer-1', 'Site visit', 'now', 'now')
                    """
                )

            runner = MigrationRunner(
                database,
                migrations=(BASELINE, SIGNATURE_FIELDS, RELATIONSHIP_INTEGRITY),
            )
            state = runner.migrate()

            self.assertEqual(state.current_version, 3)
            with database.connect() as connection:
                site = connection.execute(
                    "SELECT customer_id, name FROM customer_sites WHERE id = 'site-1'"
                ).fetchone()
                activity = connection.execute(
                    "SELECT customer_id, subject FROM customer_activities WHERE id = 'activity-1'"
                ).fetchone()
            self.assertEqual(site["customer_id"], "customer-1")
            self.assertEqual(site["name"], "Main Site")
            self.assertEqual(activity["customer_id"], "customer-1")
            self.assertEqual(activity["subject"], "Site visit")

    def test_orphaned_site_is_preserved_in_holding_table_not_dropped(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            with database.connect() as connection:
                BASELINE.apply(connection)
                connection.execute(
                    """
                    INSERT INTO customer_sites (
                        id, customer_id, name, created_at, updated_at
                    )
                    VALUES ('orphan-site', 'missing-customer', 'Ghost Site', 'now', 'now')
                    """
                )

            runner = MigrationRunner(database, migrations=(BASELINE, SIGNATURE_FIELDS, RELATIONSHIP_INTEGRITY))
            runner.migrate()

            with database.connect() as connection:
                live = connection.execute(
                    "SELECT * FROM customer_sites WHERE id = 'orphan-site'"
                ).fetchone()
                orphaned = connection.execute(
                    "SELECT customer_id, name, orphaned_reason FROM customer_sites_orphaned_v0003 "
                    "WHERE id = 'orphan-site'"
                ).fetchone()
            self.assertIsNone(live)
            self.assertIsNotNone(orphaned)
            self.assertEqual(orphaned["customer_id"], "missing-customer")
            self.assertEqual(orphaned["name"], "Ghost Site")
            self.assertIn("did not match", orphaned["orphaned_reason"])

    def test_orphaned_activity_is_preserved_in_holding_table_not_dropped(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            with database.connect() as connection:
                BASELINE.apply(connection)
                connection.execute(
                    """
                    INSERT INTO customer_activities (
                        id, customer_id, subject, created_at, updated_at
                    )
                    VALUES ('orphan-activity', 'missing-customer', 'Ghost Activity', 'now', 'now')
                    """
                )

            runner = MigrationRunner(database, migrations=(BASELINE, SIGNATURE_FIELDS, RELATIONSHIP_INTEGRITY))
            runner.migrate()

            with database.connect() as connection:
                live = connection.execute(
                    "SELECT * FROM customer_activities WHERE id = 'orphan-activity'"
                ).fetchone()
                orphaned = connection.execute(
                    "SELECT customer_id, subject FROM customer_activities_orphaned_v0003 "
                    "WHERE id = 'orphan-activity'"
                ).fetchone()
            self.assertIsNone(live)
            self.assertIsNotNone(orphaned)
            self.assertEqual(orphaned["subject"], "Ghost Activity")

    def test_activity_with_invalid_contact_is_kept_with_contact_nulled(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            with database.connect() as connection:
                BASELINE.apply(connection)
                self.seed_legacy_customer(connection)
                connection.execute(
                    """
                    INSERT INTO customer_activities (
                        id, customer_id, contact_id, subject, created_at, updated_at
                    )
                    VALUES ('activity-2', 'customer-1', 'missing-contact', 'Call', 'now', 'now')
                    """
                )

            runner = MigrationRunner(database, migrations=(BASELINE, SIGNATURE_FIELDS, RELATIONSHIP_INTEGRITY))
            runner.migrate()

            with database.connect() as connection:
                activity = connection.execute(
                    "SELECT customer_id, contact_id, subject FROM customer_activities WHERE id = 'activity-2'"
                ).fetchone()
            self.assertEqual(activity["customer_id"], "customer-1")
            self.assertIsNone(activity["contact_id"])
            self.assertEqual(activity["subject"], "Call")

    def test_foreign_keys_are_enforced_after_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO customer_sites (
                            id, customer_id, name, created_at, updated_at
                        )
                        VALUES ('bad-site', 'missing-customer', 'Bad Site', 'now', 'now')
                        """
                    )

    def test_new_columns_and_is_primary_default(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                self.seed_legacy_customer(connection)
                connection.execute(
                    """
                    INSERT INTO customer_contacts (
                        id, customer_id, name, created_at, updated_at
                    )
                    VALUES ('contact-1', 'customer-1', 'Jane', 'now', 'now')
                    """
                )
                contact = connection.execute(
                    "SELECT is_primary, archive_reason FROM customer_contacts WHERE id = 'contact-1'"
                ).fetchone()
                customer = connection.execute(
                    "SELECT archive_reason FROM customers WHERE id = 'customer-1'"
                ).fetchone()

            self.assertEqual(contact["is_primary"], 0)
            self.assertEqual(contact["archive_reason"], "")
            self.assertEqual(customer["archive_reason"], "")


if __name__ == "__main__":
    unittest.main()
