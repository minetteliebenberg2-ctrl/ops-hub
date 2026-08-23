from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from framework.module_manager import module_manager
from modules.batch_renamer.module import BatchRenamerModule
from modules.batch_renamer.services import ScanResult, build_preview, execute_rename, scan_folder


def content_hash(path):
    return sha256(path.read_bytes()).hexdigest()


class BatchRenamerServiceTests(unittest.TestCase):
    def test_recursive_deterministic_scan_excludes_directories_and_hidden_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "z.txt").write_text("z", encoding="utf-8")
            (root / "a.txt").write_text("a", encoding="utf-8")
            (root / ".hidden.txt").write_text("hidden", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "b.txt").write_text("b", encoding="utf-8")
            result = scan_folder(root)
            self.assertEqual([path.relative_to(root).as_posix() for path in result.files], ["a.txt", "nested/b.txt", "z.txt"])
            self.assertEqual([item.path.name for item in result.skipped], [".hidden.txt"])
            self.assertNotIn(nested, result.files)

    def test_empty_prefix_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("a", encoding="utf-8")
            preview = build_preview(root, "")
            self.assertFalse(preview.valid)
            self.assertIn("empty_prefix", {issue.code for issue in preview.issues})

    def test_duplicate_proposed_destinations_are_blocked_case_insensitively(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("a", encoding="utf-8")
            with patch("modules.batch_renamer.services.scan_folder", return_value=ScanResult(root, [root / "a.txt", root / "A.txt"])):
                preview = build_preview(root, "prefix-")
            self.assertFalse(preview.valid)
            self.assertIn("duplicate_destination", {issue.code for issue in preview.issues})

    def test_existing_destination_collision_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("a", encoding="utf-8")
            (root / "prefix-a.txt").write_text("existing", encoding="utf-8")
            preview = build_preview(root, "prefix-")
            self.assertFalse(preview.valid)
            self.assertIn("destination_exists", {issue.code for issue in preview.issues})

    def test_windows_case_insensitive_existing_collision_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("a", encoding="utf-8")
            (root / "PREFIX-A.TXT").write_text("existing", encoding="utf-8")
            preview = build_preview(root, "prefix-")
            self.assertFalse(preview.valid)
            self.assertIn("destination_exists", {issue.code for issue in preview.issues})

    def test_invalid_windows_filename_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("a", encoding="utf-8")
            preview = build_preview(root, "bad:name-")
            self.assertFalse(preview.valid)
            self.assertIn("invalid_filename", {issue.code for issue in preview.issues})

    def test_valid_rename_changes_names_only_and_preserves_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "a.txt"
            second = root / "b.txt"
            first.write_bytes(b"alpha\x00content")
            second.write_bytes(b"beta\x00content")
            hashes = {first.name: content_hash(first), second.name: content_hash(second)}
            preview = build_preview(root, "new-")
            result = execute_rename(preview, root, "new-")
            self.assertTrue(result.complete_success)
            self.assertEqual(result.renamed_count, 2)
            self.assertEqual(content_hash(root / "new-a.txt"), hashes["a.txt"])
            self.assertEqual(content_hash(root / "new-b.txt"), hashes["b.txt"])
            self.assertTrue((root / "new-a.txt").is_file())
            self.assertFalse((root / "a.txt").exists())

    def test_stale_preview_rejects_folder_contents_and_prefix_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("a", encoding="utf-8")
            preview = build_preview(root, "new-")
            (root / "b.txt").write_text("b", encoding="utf-8")
            stale = execute_rename(preview, root, "new-")
            self.assertEqual(stale.renamed_count, 0)
            self.assertIn("stale_files", {issue.code for issue in stale.validation_issues})
            fresh = build_preview(root, "new-")
            prefix_changed = execute_rename(fresh, root, "other-")
            self.assertIn("stale_prefix", {issue.code for issue in prefix_changed.validation_issues})

    def test_unexpected_failure_stops_and_reports_unprocessed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("a.txt", "b.txt", "c.txt"):
                (root / name).write_text(name, encoding="utf-8")
            preview = build_preview(root, "new-")
            original_rename = Path.rename
            calls = []

            def fail_on_second(source, destination):
                calls.append(source.name)
                if len(calls) == 2:
                    raise OSError("controlled rename failure")
                return original_rename(source, destination)

            with patch.object(Path, "rename", new=fail_on_second):
                result = execute_rename(preview, root, "new-")
            self.assertEqual(result.renamed_count, 1)
            self.assertEqual(result.failed_count, 1)
            self.assertEqual(len(result.not_processed), 1)
            self.assertEqual(result.failed_file[0].name, "b.txt")
            self.assertFalse((root / "new-c.txt").exists())

    def test_module_is_discoverable_without_launcher_or_framework_changes(self):
        report = module_manager.discover()
        self.assertIn("batch_renamer", report.registered_module_ids)
        self.assertIsInstance(module_manager.get("batch_renamer"), BatchRenamerModule)
        self.assertEqual(module_manager.get("batch_renamer").info.name, "Batch Renamer")


if __name__ == "__main__":
    unittest.main()
