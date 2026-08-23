from pathlib import Path
import tempfile
import unittest

from core.database import Database
from core.migrations.runner import MigrationRunner
from core.migrations.versions.v0001_baseline import MIGRATION as BASELINE
from core.migrations.versions.v0002_candidate_signature_fields import MIGRATION as SIGNATURE_FIELDS
from core.migrations.versions.v0003_crm_relationship_integrity import MIGRATION as RELATIONSHIP_INTEGRITY
from core.migrations.versions.v0004_crm_numbering_and_sites import MIGRATION as NUMBERING_AND_SITES
from core.migrations.versions.v0005_business_settings import BUSINESS_SETTINGS_ID
from core.migrations.versions.v0005_business_settings import MIGRATION as BUSINESS_SETTINGS


ALL_MIGRATIONS_THROUGH_V0005 = (
    BASELINE, SIGNATURE_FIELDS, RELATIONSHIP_INTEGRITY, NUMBERING_AND_SITES, BUSINESS_SETTINGS,
)


class BusinessSettingsMigrationTests(unittest.TestCase):
    def make_database(self, directory, name="test.db"):
        return Database(Path(directory) / name)

    def test_fresh_database_reaches_version_five_with_only_migrations_through_v0005(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)

            state = MigrationRunner(database, migrations=ALL_MIGRATIONS_THROUGH_V0005).migrate()

            self.assertEqual(state.current_version, 5)
            self.assertEqual(state.pending_versions, ())

    def test_business_settings_is_seeded_with_known_details(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                row = connection.execute(
                    "SELECT * FROM business_settings WHERE id = ?",
                    (BUSINESS_SETTINGS_ID,),
                ).fetchone()

            self.assertIsNotNone(row)
            self.assertEqual(row["trading_name"], "")
            self.assertEqual(row["registration_number"], "")
            self.assertEqual(row["vat_registered"], 0)
            self.assertEqual(row["bank_account_number"], "")

    def test_business_address_is_seeded(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                rows = connection.execute("SELECT * FROM business_addresses").fetchall()

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["city"], "")
            self.assertEqual(rows[0]["is_primary"], 1)

    def test_business_settings_upsert_preserves_single_row(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                connection.execute(
                    "UPDATE business_settings SET trading_name = 'Renamed Co' WHERE id = ?",
                    (BUSINESS_SETTINGS_ID,),
                )
                count = connection.execute("SELECT COUNT(*) FROM business_settings").fetchone()[0]

            self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
