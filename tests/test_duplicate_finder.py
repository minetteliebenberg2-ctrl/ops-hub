import hashlib
from pathlib import Path
import threading
import tempfile
import unittest
from unittest.mock import patch

from framework.module_manager import module_manager
from modules.duplicate_finder import services
from modules.duplicate_finder.module import DuplicateFinderModule
from modules.duplicate_finder.services import (
    DuplicateFinderError,
    delete_selected,
    format_size,
    prepare_deletion,
    scan_folder,
    sort_duplicate_rows,
)


class DuplicateFinderServiceTests(unittest.TestCase):
    def make_root(self):
        directory = tempfile.TemporaryDirectory()
        return directory, Path(directory.name)

    @staticmethod
    def write(path: Path, value: bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    def test_empty_directory(self):
        holder, root = self.make_root()
        with holder:
            result = scan_folder(root)
            self.assertEqual(result.files_scanned, 0)
            self.assertEqual(result.duplicate_group_count, 0)
            self.assertEqual(result.recoverable_bytes, 0)

    def test_unique_files_and_matching_sizes_different_content(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "one.txt", b"abcd")
            self.write(root / "two.txt", b"wxyz")
            result = scan_folder(root)
            self.assertEqual(result.files_scanned, 2)
            self.assertEqual(result.unique_files, 2)
            self.assertEqual(result.duplicate_file_count, 0)

    def test_identical_content_different_names_and_sha256_grouping(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "a.bin", b"same content")
            self.write(root / "b.bin", b"same content")
            result = scan_folder(root)
            self.assertEqual(result.duplicate_group_count, 1)
            group = result.groups[0]
            self.assertEqual(group.size, len(b"same content"))
            self.assertEqual(group.sha256, hashlib.sha256(b"same content").hexdigest())
            self.assertEqual(result.duplicate_file_count, 1)
            self.assertEqual(result.recoverable_bytes, len(b"same content"))

    def test_multiple_duplicate_groups_and_recursive_subdirectories(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "a" / "first.txt", b"first")
            self.write(root / "b" / "copy.txt", b"first")
            self.write(root / "c" / "second.txt", b"second")
            self.write(root / "d" / "copy.txt", b"second")
            result = scan_folder(root)
            self.assertEqual(result.duplicate_group_count, 2)
            self.assertEqual(result.duplicate_file_count, 2)
            self.assertEqual(result.recoverable_bytes, len(b"first") + len(b"second"))

    def test_unreadable_or_missing_hash_returns_none(self):
        holder, root = self.make_root()
        with holder:
            self.assertIsNone(services.calculate_hash(root / "missing.txt"))

    def test_file_changed_during_hash_is_skipped(self):
        holder, root = self.make_root()
        with holder:
            target = root / "changing.txt"
            self.write(target, b"before")
            original_hash = services._hash_file
            changed = {"done": False}

            def change_during_hash(path, cancel_event=None):
                if path == target and not changed["done"]:
                    changed["done"] = True
                    path.write_bytes(b"after")
                return original_hash(path, cancel_event)

            with patch("modules.duplicate_finder.services._hash_file", side_effect=change_during_hash):
                result = scan_folder(root)
            self.assertEqual(result.duplicate_group_count, 0)
            self.assertEqual(result.skipped_files, 1)
            self.assertIn("changed while", result.issues[0].reason)

    def test_repeated_scans_are_independent(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "a.txt", b"same")
            self.write(root / "b.txt", b"same")
            first = scan_folder(root)
            second = scan_folder(root)
            self.assertEqual(first.groups, second.groups)
            self.assertEqual(first.recoverable_bytes, second.recoverable_bytes)

    def test_cancellation_is_reported(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "a.txt", b"a")
            cancel = threading.Event()

            def stop_after_first(progress):
                cancel.set()

            result = scan_folder(root, cancel_event=cancel, progress_callback=stop_after_first)
            self.assertTrue(result.cancelled)

    def test_readable_size_and_numeric_sorting(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "small.txt", b"x")
            self.write(root / "small-copy.txt", b"x")
            self.write(root / "large.txt", b"large-content")
            self.write(root / "large-copy.txt", b"large-content")
            result = scan_folder(root)
            rows = list(result.rows())
            self.assertEqual(format_size(1024 * 1024), "1.0 MB")
            ordered = sort_duplicate_rows(rows, "size")
            self.assertLessEqual(ordered[0].size, ordered[-1].size)

    def test_safe_selection_blocks_every_copy(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "a.txt", b"same")
            self.write(root / "b.txt", b"same")
            result = scan_folder(root)
            plan = prepare_deletion(result.groups, [record.path for record in result.groups[0].files])
            self.assertFalse(plan.valid)
            self.assertIn("At least one copy", plan.failures[0].reason)

    def test_selection_outside_current_scan_is_rejected(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "a.txt", b"same")
            self.write(root / "b.txt", b"same")
            result = scan_folder(root)
            plan = prepare_deletion(result.groups, [root / "not-scanned.txt"])
            self.assertFalse(plan.valid)
            self.assertIn("current scan", plan.failures[0].reason)

    def test_recycle_bin_integration_and_remaining_statistics(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "a.txt", b"same")
            self.write(root / "b.txt", b"same")
            result = scan_folder(root)
            moved = []

            def fake_recycle(path):
                moved.append(Path(path))

            deletion = delete_selected(result.groups, [result.groups[0].duplicates[0].path], confirmed=True, recycle_bin=fake_recycle, scan_result=result)
            self.assertEqual(moved, [result.groups[0].duplicates[0].path])
            self.assertEqual(len(deletion.deleted_paths), 1)
            self.assertEqual(deletion.remaining_result.duplicate_group_count, 0)

    def test_partial_recycle_bin_failure_is_reported(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "a.txt", b"same")
            self.write(root / "b.txt", b"same")
            self.write(root / "c.txt", b"other")
            result = scan_folder(root)
            duplicate = result.groups[0].duplicates[0].path
            calls = {"count": 0}

            def fake_recycle(path):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise OSError("controlled Recycle Bin failure")

            deletion = delete_selected(result.groups, [duplicate], confirmed=True, recycle_bin=fake_recycle, scan_result=result)
            self.assertFalse(deletion.success)
            self.assertEqual(len(deletion.failures), 1)
            self.assertEqual(deletion.remaining_result.duplicate_group_count, 1)

    def test_changed_file_is_not_moved_after_scan(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "a.txt", b"same")
            self.write(root / "b.txt", b"same")
            result = scan_folder(root)
            duplicate = result.groups[0].duplicates[0].path
            duplicate.write_bytes(b"changed")
            deletion = delete_selected(result.groups, [duplicate], confirmed=True, recycle_bin=lambda path: None, scan_result=result)
            self.assertFalse(deletion.deleted_paths)
            self.assertIn("changed after scanning", deletion.failures[0].reason)

    def test_report_export(self):
        holder, root = self.make_root()
        with holder:
            self.write(root / "a.txt", b"same")
            self.write(root / "b.txt", b"same")
            result = scan_folder(root)
            report = root / "report.csv"
            services.export_report(result, report)
            text = report.read_text(encoding="utf-8")
            self.assertIn("Original File", text)
            self.assertIn("Recoverable bytes", text)

    def test_no_permanent_delete_calls_in_service(self):
        text = Path(services.__file__).read_text(encoding="utf-8")
        for forbidden in ("os.remove", "os.unlink", ".unlink(", "shutil.rmtree"):
            self.assertNotIn(forbidden, text)


class DuplicateFinderModuleTests(unittest.TestCase):
    def test_metadata_and_discovery(self):
        self.assertEqual(DuplicateFinderModule.module_info.module_id, "duplicate_finder")
        report = module_manager.discover()
        self.assertIn("duplicate_finder", report.registered_module_ids)
        self.assertFalse(report.failures)

    def test_window_import_and_launcher_unchanged(self):
        from modules.duplicate_finder.windows import DuplicateFinderWindow

        self.assertTrue(callable(DuplicateFinderWindow))
        launcher = Path(__file__).parents[1] / "launcher.py"
        text = launcher.read_text(encoding="utf-8")
        self.assertNotIn("duplicate_finder", text)

    def test_duplicate_module_does_not_use_legacy_absolute_imports(self):
        module_root = Path(__file__).parents[1] / "modules" / "duplicate_finder"
        for path in module_root.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("from core.", text)
            self.assertNotIn("from gui.", text)


if __name__ == "__main__":
    unittest.main()
