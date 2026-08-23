from pathlib import Path
import tempfile
import unittest

from core.database import Database
from core.migrations.runner import MigrationRunner
from core.migrations.versions.v0001_baseline import MIGRATION as BASELINE
from core.migrations.versions.v0002_candidate_signature_fields import MIGRATION as SIGNATURE_FIELDS
from core.migrations.versions.v0003_crm_relationship_integrity import MIGRATION as RELATIONSHIP_INTEGRITY
from core.migrations.versions.v0004_crm_numbering_and_sites import MIGRATION as NUMBERING_AND_SITES
from core.migrations.versions.v0005_business_settings import MIGRATION as BUSINESS_SETTINGS
from core.migrations.versions.v0006_picklists import MIGRATION as PICKLISTS


ALL_MIGRATIONS_THROUGH_V0006 = (
    BASELINE, SIGNATURE_FIELDS, RELATIONSHIP_INTEGRITY, NUMBERING_AND_SITES, BUSINESS_SETTINGS, PICKLISTS,
)


class PicklistsMigrationTests(unittest.TestCase):
    def make_database(self, directory, name="test.db"):
        return Database(Path(directory) / name)

    def test_fresh_database_reaches_version_six_with_only_migrations_through_v0006(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)

            state = MigrationRunner(database, migrations=ALL_MIGRATIONS_THROUGH_V0006).migrate()

            self.assertEqual(state.current_version, 6)
            self.assertEqual(state.pending_versions, ())

    def test_payment_terms_are_seeded_with_percentages(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                rows = connection.execute(
                    "SELECT value, deposit_percentage, balance_percentage FROM picklist_options "
                    "WHERE list_name = 'payment_terms' ORDER BY sort_order"
                ).fetchall()

            values = {row["value"]: (row["deposit_percentage"], row["balance_percentage"]) for row in rows}
            self.assertEqual(values["Standard"], (65.0, 35.0))
            self.assertEqual(values["Netting"], (100.0, 0.0))

    def test_customer_types_are_seeded_without_percentages(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                rows = connection.execute(
                    "SELECT value FROM picklist_options WHERE list_name = 'customer_type' ORDER BY sort_order"
                ).fetchall()

            self.assertEqual([row["value"] for row in rows], ["Commercial", "Residential", "Body Corporate", "Government", "Other"])


if __name__ == "__main__":
    unittest.main()
