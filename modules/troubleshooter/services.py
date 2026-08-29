"""Troubleshooter orchestration, summaries, and safe text reports."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import sys

from core.app_paths import get_project_root
from core.database import database as default_database
from core.diagnostics.checks import build_default_registry
from core.diagnostics.models import DiagnosticStatus
from core.diagnostics.runner import DiagnosticRunner
from core.migrations.runner import MigrationRunner, MigrationState
from modules.backup.services import BackupService


PROJECT_ROOT = get_project_root()


@dataclass(frozen=True)
class MigrationApplyResult:
    success: bool
    message: str
    state: MigrationState | None = None
    backup_path: Path | None = None


def summarize(results):
    counts = {status: 0 for status in DiagnosticStatus}
    for result in results:
        counts[result.status] += 1
    return {
        "total": len(results),
        "passed": counts[DiagnosticStatus.PASS],
        "warnings": counts[DiagnosticStatus.WARNING],
        "failed": counts[DiagnosticStatus.FAIL],
        "informational": counts[DiagnosticStatus.INFO],
        "blocking": sum(1 for item in results if item.status == DiagnosticStatus.FAIL and item.is_blocking),
    }


class TroubleshooterService:
    def __init__(self, registry=None, database=None, backup_service=None):
        self.registry = registry or build_default_registry()
        self.runner = DiagnosticRunner(self.registry)
        self.database = database or default_database
        self.backup_service = backup_service or BackupService()

    def run_all(self):
        return self.runner.run_all()

    def run_selected(self, check_ids):
        return self.runner.run_selected(check_ids)

    def inspect_migrations(self):
        return MigrationRunner(self.database).inspect()

    def pending_migration_names(self, state):
        migrations = MigrationRunner(self.database).migrations
        by_version = {migration.version: migration.name for migration in migrations}
        return [f"{version}: {by_version.get(version, 'unknown')}" for version in state.pending_versions]

    def apply_pending_migrations(self):
        """Back up, verify, and only then apply pending migrations.

        Mirrors the manual procedure this replaces: a verified backup is a
        precondition for MigrationRunner.migrate(allow_production=True), so
        a failed or unverified backup must abort before any schema change.
        """
        state = self.inspect_migrations()
        if not state.pending_versions:
            return MigrationApplyResult(True, "No pending migrations were found.", state)
        if not state.supported:
            return MigrationApplyResult(False, "The database schema is unsupported or a migration checksum changed; resolve this before migrating.", state)

        backup = self.backup_service.create_backup()
        if not backup.success:
            return MigrationApplyResult(False, f"Backup failed; migrations were not applied.\n\n{backup.message}", state)

        verification = self.backup_service.verify_backup(backup.backup_path)
        if not verification.success:
            return MigrationApplyResult(False, f"Backup verification failed; migrations were not applied.\n\n{verification.message}", state, backup.backup_path)

        try:
            new_state = MigrationRunner(self.database).migrate(allow_production=True, backup_verified=True)
        except Exception as error:
            return MigrationApplyResult(False, f"Migration failed after a verified backup was created.\n\n{error}\n\nBackup: {backup.backup_path}", state, backup.backup_path)

        applied = ", ".join(str(version) for version in state.pending_versions)
        return MigrationApplyResult(True, f"Applied migrations: {applied}\n\nBackup: {backup.backup_path}", new_state, backup.backup_path)

    def export_report(self, results, destination=None, now=None):
        now = now or datetime.now()
        output_dir = PROJECT_ROOT / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        if destination is None:
            base = "ops_hub_diagnostic_" + now.strftime("%Y%m%d_%H%M%S")
            destination = output_dir / f"{base}.txt"
            suffix = 1
            while destination.exists():
                destination = output_dir / f"{base}_{suffix}.txt"
                suffix += 1
        else:
            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(f"Report already exists: {destination}")
        summary = summarize(results)
        lines = [
            "Ops Hub Diagnostic Report", "=" * 25,
            f"Generated: {now.isoformat(timespec='seconds')}",
            f"Python: {sys.version.split()[0]}",
            f"Python executable: {sys.executable}",
            f"Project root: {PROJECT_ROOT}", "",
            "Summary",
            f"Checks run: {summary['total']}", f"Passed: {summary['passed']}",
            f"Warnings: {summary['warnings']}", f"Failed: {summary['failed']}",
            f"Informational: {summary['informational']}", f"Blocking failures: {summary['blocking']}", "",
        ]
        for result in results:
            lines.extend([
                f"[{result.status.value}] {result.category} - {result.name}",
                f"Check ID: {result.check_id}", f"Summary: {result.summary}",
                f"Details: {result.details}", f"Recommendation: {result.recommendation}",
                f"Blocking: {'Yes' if result.is_blocking else 'No'}", "",
            ])
        destination.write_text("\n".join(lines), encoding="utf-8")
        return destination


def safe_filename(value):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "ops_hub_diagnostic"
