from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.database import DATABASE_PATH, Database
from core.diagnostics.checks.system_checks import DatabaseHealthCheck
from core.diagnostics.models import DiagnosticStatus
from core.migrations.runner import (
    Migration,
    MigrationChecksumError,
    MigrationError,
    MigrationRunner,
    ProductionMigrationBlockedError,
    UnsupportedSchemaError,
    migration_checksum,
)
from core.migrations.versions.v0001_baseline import (
    MIGRATION as BASELINE,
    _TABLES,
)
from core.migrations.versions.v0002_candidate_signature_fields import (
    MIGRATION as SIGNATURE_FIELDS,
    NEW_COLUMNS as SIGNATURE_FIELD_COLUMNS,
)
from modules.backup.services import BackupService


class DatabaseMigrationTests(unittest.TestCase):
    def make_database(self, directory, name="test.db"):
        path = Path(directory) / name
        self.assertNotEqual(path.resolve(), DATABASE_PATH.resolve())
        return Database(path)

    def test_fresh_database_reaches_baseline_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)

            first = database.initialize()
            second = database.initialize()

            # Track the newest migration rather than a hardcoded number, so
            # adding a migration doesn't break an unrelated test.
            latest = MigrationRunner(database).latest_version
            self.assertEqual(first.current_version, latest)
            self.assertEqual(second.current_version, latest)
            self.assertEqual(second.pending_versions, ())
            with database.connect() as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table'
                        """
                    )
                }
                history = connection.execute(
                    "SELECT version, name FROM schema_migrations ORDER BY version"
                ).fetchall()
                user_version = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]
            self.assertTrue(set(_TABLES).issubset(tables))
            self.assertEqual(
                [tuple(row) for row in history],
                [
                    (1, "baseline"),
                    (2, "candidate_signature_fields"),
                    (3, "crm_relationship_integrity"),
                    (4, "crm_numbering_and_sites"),
                    (5, "business_settings"),
                    (6, "picklists"),
                    (7, "quotes"),
                    (8, "quote_number_per_customer"),
                    (9, "line_item_type_picklist"),
                    (10, "quote_documents_and_statements"),
                    (11, "maintenance_line_item_types"),
                    (12, "purchase_order_number"),
                    (13, "quote_revisions"),
                    (14, "quote_vat_number"),
                    (15, "line_item_colour_and_additional_height"),
                    (16, "new_net_line_item_types"),
                    (17, "documents"),
                    (18, "payments"),
                    (19, "ledger_transactions"),
                    (20, "ledger_categories_audit_receipts"),
                    (21, "category_rewording_and_additions"),
                    (22, "customer_registration_number"),
                    (23, "quote_bill_to_name"),
                    (24, "site_visits"),
                    (25, "client_folders_and_warranty"),
                    (26, "site_images"),
                    (27, "site_plans"),
                    (28, "site_plan_item_car_bays"),
                    (29, "job_cards"),
                    (30, "crm_soft_delete"),
                    (31, "supplier_pricing"),
                    (32, "ledger_category_rules"),
                    (33, "anchor_pole_76mm"),
                    (34, "supplier_pricing_vat_basis"),
                    (35, "correct_flatbar_and_angle_prices"),
                    (36, "site_plan_item_rotation"),
                    (37, "site_plan_grid_orientation"),
                    (38, "rename_standard_to_four_post"),
                    (39, "purge_orphaned_child_rows"),
                    (40, "balance_sheet_accounts"),
                    (41, "proposals"),
                    (42, "site_visit_measurements"),
                    (43, "site_image_tags_album"),
                    (44, "scheduled_jobs"),
                    (45, "site_image_hash_size"),
                    (46, "quote_accepted_date"),
                    (47, "job_cost_items"),
                    (48, "fix_account_labels_and_categories"),
                    (49, "bank_accounts_table"),
                    (50, "bank_accounts_noop"),
                    (51, "annual_compliance"),
                    (52, "site_plan_net_measurements"),
                    (53, "picklist_category"),
                    (54, "quote_print_address_flags"),
                    (55, "job_cost_allocations"),
                    (56, "document_category_picklist"),
                ],
            )
            self.assertEqual(user_version, MigrationRunner(database).latest_version)

    def test_supported_legacy_schema_is_adopted_without_data_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            with database.connect() as connection:
                BASELINE.apply(connection)
                connection.execute(
                    """
                    INSERT INTO customers (
                        id, name, created_at, updated_at
                    )
                    VALUES ('customer-1', 'Preserved', 'now', 'now')
                    """
                )

            runner = MigrationRunner(database)
            state = runner.migrate()

            self.assertEqual(state.current_version, runner.latest_version)
            with database.connect() as connection:
                row = connection.execute(
                    "SELECT name FROM customers WHERE id = 'customer-1'"
                ).fetchone()
            self.assertEqual(row[0], "Preserved")

    def test_supported_legacy_schema_is_reported_as_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            with database.connect() as connection:
                BASELINE.apply(connection)

            state = MigrationRunner(database).inspect()
            result = DatabaseHealthCheck(database.path).run()

            self.assertEqual(state.schema_status, "supported legacy")
            runner = MigrationRunner(database)
            self.assertEqual(
                state.pending_versions,
                tuple(range(1, runner.latest_version + 1)),
            )
            self.assertEqual(result.status, DiagnosticStatus.WARNING)
            self.assertIn("Pending migrations: 1, 2, 3, 4, 5, 6, 7", result.details)

    def test_unsupported_schema_is_rejected_without_history_write(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            with database.connect() as connection:
                connection.execute(
                    "CREATE TABLE unexpected (id INTEGER PRIMARY KEY)"
                )

            with self.assertRaises(UnsupportedSchemaError):
                MigrationRunner(database).migrate()

            with database.connect() as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table'
                        """
                    )
                }
            self.assertEqual(tables, {"unexpected"})

    def test_failed_migration_rolls_back_and_does_not_advance(self):
        def fail(connection):
            connection.execute(
                "CREATE TABLE should_roll_back (id INTEGER PRIMARY KEY)"
            )
            raise RuntimeError("controlled migration failure")

        failing = Migration(
            version=2,
            name="controlled_failure",
            checksum=migration_checksum("controlled failure"),
            apply=fail,
            verify=lambda connection: None,
        )
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            runner = MigrationRunner(
                database,
                migrations=(BASELINE, failing),
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "controlled migration failure",
            ):
                runner.migrate()

            with database.connect() as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table'
                        """
                    )
                }
                versions = [
                    row[0]
                    for row in connection.execute(
                        "SELECT version FROM schema_migrations"
                    )
                ]
                user_version = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]
            self.assertNotIn("should_roll_back", tables)
            self.assertEqual(versions, [1])
            self.assertEqual(user_version, 1)

    def test_checksum_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()
            changed = replace(
                BASELINE,
                checksum=migration_checksum("changed baseline"),
            )

            with self.assertRaises(MigrationChecksumError):
                MigrationRunner(
                    database,
                    migrations=(changed,),
                ).migrate()

    def test_migration_order_requires_unique_contiguous_versions(self):
        second = Migration(
            version=2,
            name="second",
            checksum=migration_checksum("second"),
            apply=lambda connection: None,
            verify=lambda connection: None,
        )
        third = replace(second, version=3, name="third")
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            with self.assertRaises(MigrationError):
                MigrationRunner(
                    database,
                    migrations=(BASELINE, third),
                )
            with self.assertRaises(MigrationError):
                MigrationRunner(
                    database,
                    migrations=(BASELINE, BASELINE),
                )

    def test_every_database_connection_enables_foreign_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()
            with database.connect() as connection:
                enabled = connection.execute(
                    "PRAGMA foreign_keys"
                ).fetchone()[0]
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO customer_contacts (
                            id, customer_id, name, created_at, updated_at
                        )
                        VALUES ('contact-1', 'missing', 'Invalid', 'now', 'now')
                        """
                    )
            self.assertEqual(enabled, 1)

    def test_verification_reports_foreign_key_violations(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()
            connection = sqlite3.connect(database.path)
            try:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute(
                    """
                    INSERT INTO customer_contacts (
                        id, customer_id, name, created_at, updated_at
                    )
                    VALUES ('orphan', 'missing', 'Orphan', 'now', 'now')
                    """
                )
                connection.commit()
            finally:
                connection.close()

            state = MigrationRunner(database).inspect()
            result = DatabaseHealthCheck(database.path).run()

            self.assertTrue(state.foreign_key_violations)
            self.assertEqual(result.status, DiagnosticStatus.FAIL)

    def test_production_path_is_blocked_before_connecting(self):
        class ProtectedDatabase:
            path = DATABASE_PATH

            def connect(self):
                raise AssertionError("Production connection was attempted.")

        with self.assertRaises(ProductionMigrationBlockedError):
            MigrationRunner(
                ProtectedDatabase(),
                production_path=DATABASE_PATH,
            ).migrate()

    def test_diagnostics_reports_current_and_pending_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()
            result = DatabaseHealthCheck(database.path).run()

            self.assertEqual(result.status, DiagnosticStatus.PASS)
            latest = MigrationRunner(database).latest_version
            self.assertIn(f"Schema version: {latest}", result.details)
            self.assertIn("Pending migrations: none", result.details)
            self.assertIn("Checksum: valid", result.details)

    def test_backup_reads_mirrored_user_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "database").mkdir()
            database = Database(root / "database" / "fc_hub.db")
            database.initialize()
            service = BackupService(
                source_root=root,
                default_destination=root / "backup-output",
            )

            self.assertEqual(
                service._database_schema_version(database.path),
                MigrationRunner(database).latest_version,
            )

    def test_signature_fields_migration_adds_expected_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)

            state = database.initialize()

            self.assertEqual(state.current_version, MigrationRunner(database).latest_version)
            with database.connect() as connection:
                columns = {
                    row[1]
                    for row in connection.execute(
                        'PRAGMA table_info("communication_candidates")'
                    )
                }
                history_names = [
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM schema_migrations ORDER BY version"
                    )
                ]
            self.assertTrue(set(SIGNATURE_FIELD_COLUMNS).issubset(columns))
            self.assertEqual(
                history_names,
                [
                    "baseline",
                    SIGNATURE_FIELDS.name,
                    "crm_relationship_integrity",
                    "crm_numbering_and_sites",
                    "business_settings",
                    "picklists",
                    "quotes",
                    "quote_number_per_customer",
                    "line_item_type_picklist",
                    "quote_documents_and_statements",
                    "maintenance_line_item_types",
                    "purchase_order_number",
                    "quote_revisions",
                    "quote_vat_number",
                    "line_item_colour_and_additional_height",
                    "new_net_line_item_types",
                    "documents",
                    "payments",
                    "ledger_transactions",
                    "ledger_categories_audit_receipts",
                    "category_rewording_and_additions",
                    "customer_registration_number",
                    "quote_bill_to_name",
                    "site_visits",
                    "client_folders_and_warranty",
                    "site_images",
                    "site_plans",
                    "site_plan_item_car_bays",
                    "job_cards",
                    "crm_soft_delete",
                    "supplier_pricing",
                    "ledger_category_rules",
                    "anchor_pole_76mm",
                    "supplier_pricing_vat_basis",
                    "correct_flatbar_and_angle_prices",
                    "site_plan_item_rotation",
                    "site_plan_grid_orientation",
                    "rename_standard_to_four_post",
                    "purge_orphaned_child_rows",
                    "balance_sheet_accounts",
                    "proposals",
                    "site_visit_measurements",
                    "site_image_tags_album",
                    "scheduled_jobs",
                    "site_image_hash_size",
                    "quote_accepted_date",
                    "job_cost_items",
                    "fix_account_labels_and_categories",
                    "bank_accounts_table",
                    "bank_accounts_noop",
                    "annual_compliance",
                    "site_plan_net_measurements",
                    "picklist_category",
                    "quote_print_address_flags",
                    "job_cost_allocations",
                    "document_category_picklist",
                ],
            )


if __name__ == "__main__":
    unittest.main()
