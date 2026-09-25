import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from framework.module_manager import ModuleManager
from modules.backup.services import BackupService, DATABASE_RELATIVE_PATH, ModuleBackupContract


def create_test_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO sample(value) VALUES ('preserved')")
        connection.commit()
    finally:
        connection.close()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BackupServiceTests(unittest.TestCase):
    def make_source(self, root: Path) -> Path:
        root.mkdir(parents=True)
        (root / "database").mkdir()
        (root / "documents").mkdir()
        (root / "config").mkdir()
        (root / "modules" / "sample").mkdir(parents=True)
        (root / "database" / "app.db").touch()
        create_test_database(root / "database" / "app.db")
        (root / "documents" / "notes.txt").write_text("notes", encoding="utf-8")
        (root / "config" / "mail.ini").write_text("password=report-only", encoding="utf-8")
        (root / "modules" / "sample" / "data.json").write_text("{}", encoding="utf-8")
        (root / "PROJECT_RULES.md").write_text("rules", encoding="utf-8")
        (root / ".git").mkdir()
        (root / ".git" / "objects").write_text("excluded", encoding="utf-8")
        (root / ".venv").mkdir()
        (root / ".venv" / "ignored.txt").write_text("excluded", encoding="utf-8")
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "ignored.pyc").write_bytes(b"excluded")
        (root / "temporary.tmp").write_text("excluded", encoding="utf-8")
        (root / "backups").mkdir()
        (root / "backups" / "old.txt").write_text("must not recurse", encoding="utf-8")
        return root

    def test_full_backup_manifest_checksum_and_exclusions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_source(Path(directory) / "source")
            destination = Path(directory) / "external-backups"
            before = digest(root / DATABASE_RELATIVE_PATH)
            service = BackupService(root, destination, application_version="test")
            service.register_module_contract(ModuleBackupContract("sample", data_paths=("modules/sample",)))

            result = service.create_backup()

            self.assertTrue(result.success, result.message)
            self.assertTrue(result.backup_path.name.startswith("Ops_Hub_Backup_"))
            manifest = json.loads((result.backup_path / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["backup_format_version"], "1.0")
            self.assertEqual(manifest["status"], "verified")
            self.assertEqual(manifest["application"]["version"], "test")
            self.assertIn("config/mail.ini", manifest["included_files"])
            self.assertIn("config/mail.ini", manifest["sensitive_files"])
            backed_up_paths = {item["path"] for item in manifest["files"]}
            for excluded in ("backups/old.txt", ".git/objects", ".venv/ignored.txt", "__pycache__/ignored.pyc", "temporary.tmp"):
                self.assertNotIn(excluded, backed_up_paths)
            self.assertEqual(before, digest(root / DATABASE_RELATIVE_PATH))
            self.assertEqual(service.verify_backup(result.backup_path).status, "verified")

    def test_failed_verification_and_incomplete_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_source(Path(directory) / "source")
            service = BackupService(root, Path(directory) / "backups")
            result = service.create_backup()
            self.assertTrue(result.success)
            target = result.backup_path / "documents" / "notes.txt"
            target.write_text("tampered", encoding="utf-8")
            verification = service.verify_backup(result.backup_path)
            self.assertFalse(verification.success)
            self.assertIn("documents/notes.txt", verification.checksum_mismatches)

    def test_copy_failure_leaves_incomplete_staging_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_source(Path(directory) / "source")
            destination = Path(directory) / "backups"
            service = BackupService(root, destination)
            original_copy = __import__("shutil").copy2

            def fail_notes(source, target, *args, **kwargs):
                if Path(source).name == "notes.txt":
                    raise OSError("controlled copy failure")
                return original_copy(source, target, *args, **kwargs)

            with patch("modules.backup.services.shutil.copy2", side_effect=fail_notes):
                result = service.create_backup()
            self.assertFalse(result.success)
            self.assertIsNotNone(result.backup_path)
            self.assertTrue(result.backup_path.name.endswith(".INCOMPLETE"))
            marker = json.loads((result.backup_path / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(marker["status"], "incomplete")

    def test_restore_preview_guards_and_safe_restore_in_temp_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_source(Path(directory) / "source")
            destination = Path(directory) / "backups"
            service = BackupService(root, destination)
            backup = service.create_backup()
            self.assertTrue(backup.success)
            target = root / "restore-target"
            target.mkdir()
            preview = service.prepare_restore(backup.backup_path, target)
            self.assertTrue(preview.valid, preview.message)
            self.assertIn("documents/notes.txt", preview.files)
            blocked = service.restore(backup.backup_path, target, confirmation=True, application_closed=False, safety_backup_destination=Path(directory) / "safety")
            self.assertFalse(blocked.success)
            restored = service.restore(backup.backup_path, target, confirmation=True, application_closed=True, safety_backup_destination=Path(directory) / "safety")
            self.assertTrue(restored.success, restored.message)
            self.assertEqual((target / "documents" / "notes.txt").read_text(encoding="utf-8"), "notes")

    def test_unsafe_manifest_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_source(Path(directory) / "source")
            service = BackupService(root, Path(directory) / "backups")
            backup = service.create_backup()
            self.assertTrue(backup.success)
            manifest_path = backup.backup_path / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"].append({"path": "../outside.txt", "size": 0, "sha256": ""})
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = service.verify_backup(backup.backup_path)
            self.assertEqual(result.status, "unsafe_manifest")
            preview = service.prepare_restore(backup.backup_path)
            self.assertFalse(preview.valid)

    def test_history_and_cleanup_are_non_destructive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_source(Path(directory) / "source")
            destination = Path(directory) / "backups"
            service = BackupService(root, destination, retention_days=1)
            first = service.create_backup()
            self.assertTrue(first.success)
            history = service.list_backups()
            self.assertEqual(len(history), 1)
            self.assertEqual(service.cleanup_candidates(), [])
            self.assertTrue(first.backup_path.exists())


class BackupModuleDiscoveryTests(unittest.TestCase):
    def test_native_module_metadata(self):
        from modules.backup.module import BackupModule

        module = BackupModule()
        self.assertEqual(module.info.module_id, "backup")
        self.assertEqual(module.info.name, "Backup")
        self.assertTrue(callable(module.create_window))

    def test_production_discovery_includes_backup_without_launcher_registration(self):
        from framework.module_manager import module_manager

        report = module_manager.discover()
        self.assertIn("backup", report.registered_module_ids)
        self.assertFalse(report.failures)
        launcher = Path(__file__).parents[1] / "launcher.py"
        text = launcher.read_text(encoding="utf-8")
        self.assertNotIn("modules.backup", text)


if __name__ == "__main__":
    unittest.main()
