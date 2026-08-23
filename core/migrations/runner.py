"""Ordered, transactional migration runner for the existing FC Hub database."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import pkgutil
from pathlib import Path
import sqlite3
from typing import Callable, Iterable

from core.app_paths import get_project_root


HISTORY_TABLE = "schema_migrations"
DEFAULT_PRODUCTION_PATH = get_project_root() / "database" / "fc_hub.db"


class MigrationError(RuntimeError):
    """Base error for migration validation or execution failures."""


class MigrationChecksumError(MigrationError):
    """Raised when an applied migration no longer matches its checksum."""


class UnsupportedSchemaError(MigrationError):
    """Raised when an unversioned database is not the approved legacy schema."""


class ProductionMigrationBlockedError(MigrationError):
    """Raised when production migration lacks explicit backup authorisation."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    checksum: str
    apply: Callable[[sqlite3.Connection], None]
    verify: Callable[[sqlite3.Connection], None]
    matches_legacy: Callable[[sqlite3.Connection], bool] | None = None


@dataclass(frozen=True)
class MigrationState:
    current_version: int
    latest_version: int
    pending_versions: tuple[int, ...]
    checksum_status: str
    integrity_status: str
    foreign_keys_enabled: bool
    foreign_key_violations: tuple[tuple, ...]
    schema_status: str
    supported: bool


def migration_checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_migrations() -> tuple[Migration, ...]:
    package = importlib.import_module("core.migrations.versions")
    migrations = []
    for module_info in pkgutil.iter_modules(
        package.__path__,
        package.__name__ + ".",
    ):
        if module_info.name.rsplit(".", 1)[-1].startswith("v"):
            module = importlib.import_module(module_info.name)
            migrations.append(module.MIGRATION)
    return validate_migrations(migrations)


def validate_migrations(
    migrations: Iterable[Migration],
) -> tuple[Migration, ...]:
    ordered = tuple(sorted(migrations, key=lambda item: item.version))
    versions = [item.version for item in ordered]
    if not ordered:
        raise MigrationError("At least one migration is required.")
    if any(version < 1 for version in versions):
        raise MigrationError("Migration versions must be positive integers.")
    if len(versions) != len(set(versions)):
        raise MigrationError("Duplicate migration versions are not allowed.")
    expected = list(range(1, versions[-1] + 1))
    if versions != expected:
        raise MigrationError(
            f"Migration versions must be contiguous: expected {expected}, "
            f"found {versions}."
        )
    for migration in ordered:
        if not migration.name.strip():
            raise MigrationError(
                f"Migration {migration.version} has no name."
            )
        if len(migration.checksum) != 64:
            raise MigrationError(
                f"Migration {migration.version} has an invalid checksum."
            )
    return ordered


class MigrationRunner:
    def __init__(
        self,
        database,
        migrations=None,
        production_path=None,
    ):
        self.database = database
        self.migrations = validate_migrations(
            migrations if migrations is not None else load_migrations()
        )
        self.production_path = (
            Path(production_path).resolve()
            if production_path is not None
            else DEFAULT_PRODUCTION_PATH.resolve()
        )

    @property
    def latest_version(self):
        return self.migrations[-1].version

    def migrate(
        self,
        *,
        allow_production=False,
        backup_verified=False,
    ):
        self._guard_production(allow_production, backup_verified)
        path = Path(self.database.path)
        existed = path.exists() and path.stat().st_size > 0

        with self.database.connect() as connection:
            has_history = self._has_history(connection)
            if not has_history:
                application_tables = self._application_tables(connection)
                if application_tables:
                    baseline = self.migrations[0]
                    if not self._is_supported_legacy(connection, baseline):
                        raise UnsupportedSchemaError(
                            "The unversioned database does not match the "
                            "approved FC Hub legacy baseline."
                        )
                    self._adopt_baseline(connection, baseline)
                elif existed:
                    raise UnsupportedSchemaError(
                        "The existing database contains no supported FC Hub "
                        "schema."
                    )

            applied = self._applied(connection)
            self._validate_applied(applied)
            for migration in self.migrations:
                if migration.version not in applied:
                    self._apply_one(connection, migration)
                    applied[migration.version] = migration

        return self.inspect()

    def inspect(self):
        path = Path(self.database.path)
        if not path.is_file() or path.stat().st_size == 0:
            return MigrationState(
                current_version=0,
                latest_version=self.latest_version,
                pending_versions=tuple(
                    item.version for item in self.migrations
                ),
                checksum_status="not applied",
                integrity_status="missing",
                foreign_keys_enabled=True,
                foreign_key_violations=(),
                schema_status="fresh",
                supported=True,
            )

        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            foreign_keys_enabled = (
                connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            )
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            violations = tuple(
                tuple(row)
                for row in connection.execute("PRAGMA foreign_key_check")
            )
            if not self._has_history(connection):
                baseline = self.migrations[0]
                supported = self._is_supported_legacy(connection, baseline)
                return MigrationState(
                    current_version=0,
                    latest_version=self.latest_version,
                    pending_versions=tuple(
                        item.version for item in self.migrations
                    ),
                    checksum_status="not recorded",
                    integrity_status=integrity,
                    foreign_keys_enabled=foreign_keys_enabled,
                    foreign_key_violations=violations,
                    schema_status=(
                        "supported legacy"
                        if supported
                        else "unsupported"
                    ),
                    supported=supported,
                )

            applied = self._applied(connection)
            try:
                self._validate_applied(applied)
                checksum_status = "valid"
                supported = True
            except MigrationChecksumError:
                checksum_status = "mismatch"
                supported = False
            current = max(applied, default=0)
            return MigrationState(
                current_version=current,
                latest_version=self.latest_version,
                pending_versions=tuple(
                    item.version
                    for item in self.migrations
                    if item.version not in applied
                ),
                checksum_status=checksum_status,
                integrity_status=integrity,
                foreign_keys_enabled=foreign_keys_enabled,
                foreign_key_violations=violations,
                schema_status="versioned",
                supported=supported,
            )

    def _apply_one(self, connection, migration):
        try:
            connection.execute("BEGIN")
            self._ensure_history(connection)
            migration.apply(connection)
            migration.verify(connection)
            connection.execute(
                """
                INSERT INTO schema_migrations (
                    version, name, checksum, applied_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    migration.version,
                    migration.name,
                    migration.checksum,
                    self._timestamp(),
                ),
            )
            connection.execute(
                f"PRAGMA user_version = {migration.version}"
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _adopt_baseline(self, connection, migration):
        try:
            connection.execute("BEGIN")
            self._ensure_history(connection)
            migration.verify(connection)
            connection.execute(
                """
                INSERT INTO schema_migrations (
                    version, name, checksum, applied_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    migration.version,
                    migration.name,
                    migration.checksum,
                    self._timestamp(),
                ),
            )
            connection.execute(
                f"PRAGMA user_version = {migration.version}"
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _validate_applied(self, applied):
        available = {
            migration.version: migration
            for migration in self.migrations
        }
        for version, record in applied.items():
            migration = available.get(version)
            if migration is None:
                raise MigrationChecksumError(
                    f"Applied migration {version} is not available."
                )
            if (
                record.name != migration.name
                or record.checksum != migration.checksum
            ):
                raise MigrationChecksumError(
                    f"Applied migration {version} checksum or name changed."
                )

    @staticmethod
    def _has_history(connection):
        return connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (HISTORY_TABLE,),
        ).fetchone() is not None

    @staticmethod
    def _ensure_history(connection):
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _application_tables(connection):
        return {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                    AND name NOT LIKE 'sqlite_%'
                    AND name != ?
                """,
                (HISTORY_TABLE,),
            )
        }

    @staticmethod
    def _is_supported_legacy(connection, baseline):
        matcher = baseline.matches_legacy
        return bool(matcher and matcher(connection))

    @staticmethod
    def _applied(connection):
        if not MigrationRunner._has_history(connection):
            return {}
        rows = connection.execute(
            """
            SELECT version, name, checksum
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()
        return {
            row[0]: _AppliedMigration(row[1], row[2])
            for row in rows
        }

    def _guard_production(self, allow_production, backup_verified):
        if Path(self.database.path).resolve() != self.production_path:
            return
        if not allow_production or not backup_verified:
            raise ProductionMigrationBlockedError(
                "Production migration requires explicit authorisation and "
                "a verified pre-migration backup."
            )

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class _AppliedMigration:
    name: str
    checksum: str
