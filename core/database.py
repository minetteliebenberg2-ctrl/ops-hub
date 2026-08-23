# ==========================================================
# FC Hub - Database
# ----------------------------------------------------------
# Purpose:
# Shared SQLite database access and schema setup.
#
# Author: Minette & James
# Version: 2.0
# ==========================================================

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from core.app_paths import get_project_root
from core.migrations.runner import MigrationRunner


DATABASE_DIR = get_project_root() / "database"
DATABASE_PATH = DATABASE_DIR / "app.db"


class Database:

    def __init__(self, path=None):

        self.path = Path(path) if path else DATABASE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------

    @contextmanager
    def connect(self):

        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
        if foreign_keys != 1:
            connection.close()
            raise sqlite3.DatabaseError(
                "SQLite foreign-key enforcement could not be enabled."
            )

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # --------------------------------------------------

    def initialize(self):

        runner = MigrationRunner(
            self,
            production_path=DATABASE_PATH,
        )
        if self.path.resolve() == DATABASE_PATH.resolve():
            return runner.inspect()
        return runner.migrate()


database = Database()
