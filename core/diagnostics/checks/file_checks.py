"""File system integrity checks — missing assets, orphaned client folders."""

import sqlite3
from contextlib import closing
from pathlib import Path

from core.app_paths import get_project_root
from core.diagnostics.models import DiagnosticResult, DiagnosticStatus


PROJECT_ROOT = get_project_root()


class Check:
    description = ""

    def result(self, status, summary, details="", recommendation="No action required.", blocking=False):
        return DiagnosticResult(
            self.check_id, self.category, self.name, status, summary,
            details or summary, recommendation, blocking,
        )


def _default_db_path():
    try:
        from core.database import database
        return Path(database.path)
    except Exception:
        return PROJECT_ROOT / "database" / "fc_hub.db"


def _ro_connection(path=None):
    path = Path(path) if path else _default_db_path()
    if not path.exists():
        return None
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


class ClientFolderCheck(Check):
    check_id = "files.client_folders"
    category = "Files"
    name = "Client Paperwork folders"

    def run(self):
        conn = _ro_connection()
        if conn is None:
            return self.result(DiagnosticStatus.INFO, "Database not found; skipping.")
        with closing(conn):
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "customers" not in tables:
                return self.result(DiagnosticStatus.INFO, "Customers table not found; skipping.")
            customers = conn.execute(
                "SELECT id, customer_number, name FROM customers WHERE deleted_at IS NULL"
            ).fetchall()
        missing = []
        for cid, cnum, name in customers:
            folder = PROJECT_ROOT / "Paperwork" / (cnum or name or cid)
            if not folder.is_dir():
                missing.append(f"{cnum or name}: {folder}")
        if not missing:
            return self.result(DiagnosticStatus.PASS, f"All {len(customers)} customer Paperwork folders exist.")
        return self.result(
            DiagnosticStatus.INFO,
            f"{len(missing)} customer(s) have no Paperwork folder.",
            "\n".join(missing[:20]) + (f"\n... and {len(missing)-20} more" if len(missing) > 20 else ""),
            "Folders are created automatically when a document is generated. No action needed unless documents were lost.",
        )


class DatabaseBackupAgeCheck(Check):
    check_id = "files.backup_age"
    category = "Files"
    name = "Recent backup check"

    def run(self):
        backup_dir = PROJECT_ROOT / "backups"
        if not backup_dir.is_dir():
            return self.result(DiagnosticStatus.WARNING, "No backups directory found.", "", "Create a backup using the Backup module.")
        from datetime import datetime, timedelta
        backups = sorted(backup_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        backups = [b for b in backups if b.is_dir() and "Backup" in b.name]
        if not backups:
            return self.result(DiagnosticStatus.WARNING, "No backups found.", "", "Create a backup using the Backup module.")
        latest = backups[0]
        age = datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)
        if age > timedelta(days=7):
            return self.result(
                DiagnosticStatus.WARNING,
                f"Latest backup is {age.days} days old.",
                f"Latest: {latest.name}\nAge: {age.days} days",
                "Run a fresh backup. The scheduled backup may not be running.",
            )
        return self.result(
            DiagnosticStatus.PASS,
            f"Latest backup is {age.days} day(s) old.",
            f"Latest: {latest.name}\nBackups on file: {len(backups)}",
        )


class AssetFileCheck(Check):
    check_id = "files.assets"
    category = "Files"
    name = "Required asset files"

    REQUIRED = ["logo_placeholder.png"]

    def run(self):
        assets = PROJECT_ROOT / "assets"
        if not assets.is_dir():
            return self.result(DiagnosticStatus.WARNING, "Assets directory not found.")
        missing = [f for f in self.REQUIRED if not (assets / f).exists()]
        if missing:
            return self.result(
                DiagnosticStatus.WARNING,
                f"{len(missing)} required asset(s) missing.",
                "Missing: " + ", ".join(missing),
                "Restore from a verified backup.",
            )
        return self.result(DiagnosticStatus.PASS, "All required assets are present.")


class DatabaseSizeCheck(Check):
    check_id = "files.db_size"
    category = "Files"
    name = "Database file size"

    def run(self):
        db_path = _default_db_path()
        if not db_path.exists():
            return self.result(DiagnosticStatus.INFO, "Database not found; skipping.")
        size_mb = db_path.stat().st_size / (1024 * 1024)
        if size_mb > 500:
            return self.result(
                DiagnosticStatus.WARNING,
                f"Database is {size_mb:.1f} MB — consider a VACUUM.",
                f"Path: {db_path}\nSize: {size_mb:.1f} MB",
                "Open a terminal and run: sqlite3 fc_hub.db VACUUM",
            )
        return self.result(DiagnosticStatus.PASS, f"Database is {size_mb:.1f} MB.", f"Path: {db_path}")


FILE_CHECKS = [
    ClientFolderCheck,
    DatabaseBackupAgeCheck,
    AssetFileCheck,
    DatabaseSizeCheck,
]
