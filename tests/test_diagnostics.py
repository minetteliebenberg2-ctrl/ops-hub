import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from core.diagnostics.checks import system_checks
from core.diagnostics.checks.system_checks import (
    BackupHealthCheck,
    DatabaseHealthCheck,
    DependencyCheck,
    FilesystemAccessCheck,
    ImportHealthCheck,
    ProjectStructureCheck,
)
from core.diagnostics.models import DiagnosticResult, DiagnosticStatus
from core.diagnostics.registry import DiagnosticRegistry
from core.diagnostics.runner import DiagnosticRunner
from core.database import Database


class GoodCheck:
    check_id, category, name = "test.good", "Test", "Good"

    def run(self):
        return DiagnosticResult(self.check_id, self.category, self.name, DiagnosticStatus.PASS, "Passed", "Details", "None")


class WarningCheck:
    check_id, category, name = "test.warning", "Test", "Warning"

    def run(self):
        return DiagnosticResult(self.check_id, self.category, self.name, DiagnosticStatus.WARNING, "Warning", "Details", "Review")


class BrokenCheck:
    check_id, category, name = "test.broken", "Test", "Broken"

    def run(self):
        raise RuntimeError("controlled test failure")


def create_database(path, complete=True):
    if complete:
        Database(path).initialize()
        return
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            'CREATE TABLE "customers" (id TEXT PRIMARY KEY)'
        )
        connection.commit()


class DiagnosticsTests(unittest.TestCase):
    def test_result_requires_central_status_and_fields(self):
        result = DiagnosticResult("id", "Category", "Name", DiagnosticStatus.FAIL, "Summary", "Details", "Recommendation", True)
        self.assertTrue(result.is_blocking)
        self.assertEqual(len(DiagnosticStatus), 4)
        with self.assertRaises(ValueError):
            DiagnosticResult("", "Category", "Name", DiagnosticStatus.PASS, "Summary", "", "")

    def test_registry_prevents_duplicates_and_preserves_order(self):
        registry = DiagnosticRegistry()
        registry.register(WarningCheck())
        registry.register(GoodCheck())
        self.assertEqual([item.check_id for item in registry.get_checks()], ["test.warning", "test.good"])
        with self.assertRaises(ValueError):
            registry.register(GoodCheck())

    def test_runner_continues_and_converts_exceptions(self):
        registry = DiagnosticRegistry()
        for check in (GoodCheck(), BrokenCheck(), WarningCheck()):
            registry.register(check)
        results = DiagnosticRunner(registry).run_all()
        self.assertEqual([item.status for item in results], [DiagnosticStatus.PASS, DiagnosticStatus.FAIL, DiagnosticStatus.WARNING])
        self.assertIn("RuntimeError", results[1].details)

    def test_runner_selected_and_unknown(self):
        registry = DiagnosticRegistry()
        registry.register(GoodCheck())
        registry.register(WarningCheck())
        results = DiagnosticRunner(registry).run_selected(["test.warning", "missing"])
        self.assertEqual([item.check_id for item in results], ["test.warning", "missing"])
        self.assertEqual(results[1].status, DiagnosticStatus.FAIL)

    def test_project_structure_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for item in ("core", "framework", "gui", "modules", "database"):
                (root / item).mkdir()
            (root / "launcher.py").write_text("", encoding="utf-8")
            self.assertEqual(ProjectStructureCheck(root).run().status, DiagnosticStatus.WARNING)
            (root / "launcher.py").unlink()
            self.assertEqual(ProjectStructureCheck(root).run().status, DiagnosticStatus.FAIL)

    def test_project_structure_check_in_a_frozen_build_only_expects_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(system_checks, "FROZEN", True):
                self.assertEqual(ProjectStructureCheck(root).run().status, DiagnosticStatus.FAIL)
                (root / "database").mkdir()
                result = ProjectStructureCheck(root).run()
                self.assertEqual(result.status, DiagnosticStatus.WARNING)
                self.assertNotIn("launcher.py", result.details)

    def test_dependency_check_in_a_frozen_build_reports_info_without_requirements_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(system_checks, "FROZEN", True):
                result = DependencyCheck(root).run()
                self.assertEqual(result.status, DiagnosticStatus.INFO)
                self.assertIn("bundled", result.summary)

    def test_dependency_check_fails_cleanly_when_requirements_file_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = DependencyCheck(root).run()
            self.assertEqual(result.status, DiagnosticStatus.FAIL)
            self.assertIn("requirements.txt", result.summary)

    def test_import_health_check_in_a_frozen_build_does_not_expect_a_launcher_module(self):
        with patch.object(system_checks, "FROZEN", True):
            result = ImportHealthCheck().run()
            self.assertNotIn("launcher", result.details)

    def test_filesystem_probe_is_cleaned_up(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(FilesystemAccessCheck([root]).run().status, DiagnosticStatus.PASS)
            self.assertEqual(list(root.iterdir()), [])
            self.assertEqual(FilesystemAccessCheck([root / "missing"]).run().status, DiagnosticStatus.FAIL)

    def test_database_health_no_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.db"
            create_database(path)
            before = path.read_bytes()
            self.assertEqual(DatabaseHealthCheck(path).run().status, DiagnosticStatus.PASS)
            self.assertEqual(path.read_bytes(), before)

    def test_database_missing_table_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incomplete = root / "incomplete.db"
            create_database(incomplete, complete=False)
            self.assertEqual(DatabaseHealthCheck(incomplete).run().status, DiagnosticStatus.FAIL)
            corrupt = root / "corrupt.db"
            corrupt.write_bytes(b"not a sqlite database")
            registry = DiagnosticRegistry()
            registry.register(DatabaseHealthCheck(corrupt))
            self.assertEqual(DiagnosticRunner(registry).run_all()[0].status, DiagnosticStatus.FAIL)

    def test_backup_health_uses_native_service_without_creating_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = BackupHealthCheck(root).run()
            self.assertEqual(result.status, DiagnosticStatus.INFO)
            self.assertIn("Backup service is available", result.summary)
            self.assertFalse((root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
