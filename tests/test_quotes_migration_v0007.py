from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.database import Database
from core.migrations.runner import MigrationRunner


class QuotesMigrationTests(unittest.TestCase):
    def make_database(self, directory, name="test.db"):
        return Database(Path(directory) / name)

    def test_fresh_database_reaches_version_seven(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)

            state = database.initialize()

            # Tracks the newest migration rather than a hardcoded number, so
            # adding a migration doesn't break an unrelated test.
            self.assertEqual(state.current_version, MigrationRunner(database).latest_version)
            self.assertEqual(state.pending_versions, ())

    def test_quote_number_uniqueness_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                connection.execute(
                    "INSERT INTO customers (id, name, customer_number, created_at, updated_at) "
                    "VALUES ('c1', 'Co', 'FAC-001', 'now', 'now')"
                )
                connection.execute(
                    "INSERT INTO quotes (id, quote_number, customer_id, created_at, updated_at) "
                    "VALUES ('q1', 'FAC-001-Q-001', 'c1', 'now', 'now')"
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO quotes (id, quote_number, customer_id, created_at, updated_at) "
                        "VALUES ('q2', 'FAC-001-Q-001', 'c1', 'now', 'now')"
                    )

    def test_quote_customer_foreign_key_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO quotes (id, customer_id, created_at, updated_at) "
                        "VALUES ('q1', 'missing-customer', 'now', 'now')"
                    )

    def test_line_item_cascades_on_quote_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            database = self.make_database(directory)
            database.initialize()

            with database.connect() as connection:
                connection.execute(
                    "INSERT INTO customers (id, name, customer_number, created_at, updated_at) "
                    "VALUES ('c1', 'Co', 'FAC-001', 'now', 'now')"
                )
                connection.execute(
                    "INSERT INTO quotes (id, customer_id, created_at, updated_at) "
                    "VALUES ('q1', 'c1', 'now', 'now')"
                )
                connection.execute(
                    "INSERT INTO quote_line_items (id, quote_id, structure_type, created_at, updated_at) "
                    "VALUES ('li1', 'q1', 'Cantilever', 'now', 'now')"
                )
                connection.execute("DELETE FROM quotes WHERE id = 'q1'")
                remaining = connection.execute(
                    "SELECT COUNT(*) FROM quote_line_items WHERE quote_id = 'q1'"
                ).fetchone()[0]

            self.assertEqual(remaining, 0)


if __name__ == "__main__":
    unittest.main()
