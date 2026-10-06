"""Auto-fix engine for diagnostic issues. Every fix backs up the DB first."""

import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.app_paths import get_project_root
from core.database import database


PROJECT_ROOT = get_project_root()


@dataclass(frozen=True)
class FixResult:
    check_id: str
    success: bool
    message: str
    changes: int = 0
    backup_path: str = ""


def _backup_db():
    """Create a timestamped copy of the live DB before any fix."""
    src = Path(database.path)
    if not src.exists():
        raise FileNotFoundError(f"Database not found: {src}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = src.parent / f"fc_hub_backup_pre_fix_{stamp}.db"
    shutil.copy2(src, dest)
    return str(dest)


def _rw_connection():
    return sqlite3.connect(database.path)


# ── Registry ───────────────────────────────────────────────

_FIXERS = {}


def fixer(check_id):
    def decorator(fn):
        _FIXERS[check_id] = fn
        return fn
    return decorator


def can_fix(check_id):
    return check_id in _FIXERS


def available_fixers():
    return dict(_FIXERS)


def run_fix(check_id):
    fn = _FIXERS.get(check_id)
    if fn is None:
        return FixResult(check_id, False, "No auto-fix available for this check.")
    backup = _backup_db()
    try:
        result = fn(backup)
        return result
    except Exception as e:
        return FixResult(check_id, False, f"Fix failed: {e}\nBackup at: {backup}", backup_path=backup)


# ── FK violation fixer ─────────────────────────────────────

@fixer("data.fk_violations")
def fix_fk_violations(backup):
    with closing(_rw_connection()) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if not violations:
            return FixResult("data.fk_violations", True, "No violations to fix.", backup_path=backup)
        changes = 0
        for table, rowid, ref_table, fk_idx in violations:
            fks = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
            matching = [fk for fk in fks if fk[0] == fk_idx]
            if not matching:
                continue
            col = matching[0][3]
            conn.execute(f"UPDATE {table} SET {col} = NULL WHERE rowid = ?", (rowid,))
            changes += 1
        conn.commit()
    return FixResult("data.fk_violations", True, f"NULLed {changes} dangling reference(s).", changes, backup)


# ── Orphaned record fixer ──────────────────────────────────

@fixer("data.orphaned_records")
def fix_orphaned_records(backup):
    from core.diagnostics.checks.data_checks import OrphanedRecordCheck
    changes = 0
    with closing(_rw_connection()) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for child, fk_col, parent, pk_col, label in OrphanedRecordCheck.PARENT_CHECKS:
            if child not in tables or parent not in tables:
                continue
            sql = (
                f"UPDATE {child} SET {fk_col} = NULL "
                f"WHERE {fk_col} IS NOT NULL AND {fk_col} != '' "
                f"AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE p.{pk_col} = {child}.{fk_col})"
            )
            cursor = conn.execute(sql)
            changes += cursor.rowcount
        conn.commit()
    return FixResult("data.orphaned_records", True, f"NULLed {changes} orphaned reference(s).", changes, backup)


# ── Soft-deleted reference fixer ───────────────────────────

@fixer("data.soft_deleted_refs")
def fix_soft_deleted_refs(backup):
    from core.diagnostics.checks.data_checks import SoftDeletedReferenceCheck
    changes = 0
    with closing(_rw_connection()) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for child, fk_col, parent, label in SoftDeletedReferenceCheck.CHECKS:
            if child not in tables or parent not in tables:
                continue
            parent_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({parent})")}
            if "deleted_at" not in parent_cols:
                continue
            cursor = conn.execute(
                f"UPDATE {child} SET {fk_col} = NULL "
                f"WHERE {fk_col} IN ("
                f"  SELECT p.id FROM {parent} p WHERE p.deleted_at IS NOT NULL"
                f") AND {fk_col} IS NOT NULL"
            )
            changes += cursor.rowcount
        conn.commit()
    return FixResult("data.soft_deleted_refs", True, f"NULLed {changes} reference(s) to deleted records.", changes, backup)


# ── Client folder creator ──────────────────────────────────

@fixer("files.client_folders")
def fix_client_folders(backup):
    conn = sqlite3.connect(f"file:{Path(database.path).resolve().as_posix()}?mode=ro", uri=True)
    with closing(conn):
        customers = conn.execute(
            "SELECT customer_number, name FROM customers WHERE deleted_at IS NULL"
        ).fetchall()
    created = 0
    for cnum, name in customers:
        folder = PROJECT_ROOT / "Paperwork" / (cnum or name)
        if not folder.is_dir():
            folder.mkdir(parents=True, exist_ok=True)
            created += 1
    return FixResult("files.client_folders", True, f"Created {created} missing folder(s).", created, backup)


# ── DB VACUUM ──────────────────────────────────────────────

@fixer("files.db_size")
def fix_db_size(backup):
    with closing(_rw_connection()) as conn:
        before = Path(database.path).stat().st_size
        conn.execute("VACUUM")
        after = Path(database.path).stat().st_size
    saved = (before - after) / (1024 * 1024)
    return FixResult("files.db_size", True, f"VACUUM complete. Saved {saved:.1f} MB.", backup_path=backup)
