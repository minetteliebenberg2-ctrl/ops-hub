import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from framework.module_manager import module_manager
from modules.empty_folder_remover.module import EmptyFolderRemoverModule
from modules.empty_folder_remover.services import EmptyFolderError, EmptyFolderService


class EmptyFolderServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = EmptyFolderService()

    def test_recursive_scan_detects_empty_and_ignores_non_empty_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            empty = root / "empty"
            nested_empty = root / "parent" / "nested"
            non_empty = root / "non-empty"
            empty.mkdir()
            nested_empty.mkdir(parents=True)
            non_empty.mkdir()
            (non_empty / "file.txt").write_text("content", encoding="utf-8")

            result = self.service.scan(root)

            self.assertEqual(set(result.folders), {empty, nested_empty})
            self.assertNotIn(non_empty, result.folders)
            self.assertEqual(result.folders_scanned, 5)
            self.assertEqual(result.empty_folders, 2)
            self.assertEqual(result.skipped_folders, 0)
            self.assertIsInstance(result.elapsed_seconds, float)

    def test_scan_uses_bottom_up_os_walk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch(
                "modules.empty_folder_remover.services.os.walk",
                wraps=os.walk,
            ) as walk:
                self.service.scan(root)
            self.assertFalse(walk.call_args.kwargs["topdown"])

    def test_empty_root_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.service.scan(root)
            self.assertEqual(result.folders, (root,))
            self.assertEqual(result.folders_scanned, 1)
            self.assertEqual(result.empty_folders, 1)

    def test_invalid_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(EmptyFolderError):
                self.service.scan(Path(directory) / "missing")

    def test_permission_error_is_counted_as_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def simulated_walk(folder, **kwargs):
                error = PermissionError("access denied")
                error.filename = str(root / "protected")
                kwargs["onerror"](error)
                yield str(root), [], []

            with patch(
                "modules.empty_folder_remover.services.os.walk",
                side_effect=simulated_walk,
            ):
                result = self.service.scan(root)
            self.assertEqual(result.skipped_folders, 1)
            self.assertEqual(result.issues[0].path, root / "protected")

    def test_deletion_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "empty"
            target.mkdir()
            moved = []
            result = self.service.delete(
                [target],
                confirmed=False,
                recycle_bin=moved.append,
            )
            self.assertFalse(moved)
            self.assertEqual(result.failed_count, 1)

    def test_only_selected_empty_folders_are_sent_to_recycle_bin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = root / "selected"
            untouched = root / "untouched"
            selected.mkdir()
            untouched.mkdir()
            moved = []

            result = self.service.delete(
                [selected],
                confirmed=True,
                recycle_bin=lambda path: moved.append(Path(path)),
            )

            self.assertEqual(moved, [selected])
            self.assertEqual(result.deleted_paths, (selected,))
            self.assertNotIn(untouched, moved)

    def test_folder_that_is_no_longer_empty_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "changed"
            target.mkdir()
            (target / "new.txt").write_text("content", encoding="utf-8")
            moved = []
            result = self.service.delete(
                [target],
                confirmed=True,
                recycle_bin=moved.append,
            )
            self.assertFalse(moved)
            self.assertEqual(result.failed_count, 1)
            self.assertIn("no longer empty", result.failures[0].reason)

    def test_partial_deletion_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()

            def recycle(path):
                if Path(path) == second:
                    raise OSError("controlled failure")

            result = self.service.delete(
                [first, second],
                confirmed=True,
                recycle_bin=recycle,
            )
            self.assertEqual(result.deleted_paths, (first,))
            self.assertEqual(result.failed_count, 1)

    def test_csv_export_has_legacy_column_and_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folders = (root / "one", root / "two")
            destination = root / "empty-folders.csv"
            self.service.export_csv(folders, destination)
            with destination.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows, [["Folder"], [str(folders[0])], [str(folders[1])]])

    def test_csv_export_rejects_missing_destination_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "missing" / "report.csv"
            with self.assertRaises(EmptyFolderError):
                self.service.export_csv([], destination)

    def test_service_contains_no_permanent_recursive_delete(self):
        source = Path(__file__).parents[1].joinpath(
            "modules",
            "empty_folder_remover",
            "services.py",
        ).read_text(encoding="utf-8")
        for forbidden in ("shutil.rmtree", "os.rmdir", ".unlink("):
            self.assertNotIn(forbidden, source)


class EmptyFolderModuleTests(unittest.TestCase):
    def test_metadata_and_registration(self):
        self.assertEqual(
            EmptyFolderRemoverModule.module_info.module_id,
            "empty_folder_remover",
        )
        report = module_manager.discover()
        self.assertIn("empty_folder_remover", report.registered_module_ids)
        self.assertIsInstance(
            module_manager.get("empty_folder_remover"),
            EmptyFolderRemoverModule,
        )
        self.assertFalse(report.failures)

    def test_window_import_and_launcher_remain_decoupled(self):
        from modules.empty_folder_remover.windows import EmptyFolderRemoverWindow

        self.assertTrue(callable(EmptyFolderRemoverWindow))
        launcher = Path(__file__).parents[1] / "launcher.py"
        self.assertNotIn(
            "empty_folder_remover",
            launcher.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
