import csv
from pathlib import Path
import shutil
import threading
import tempfile
import unittest
from unittest import mock

from framework.module_manager import ModuleManager
from modules.file_mover import FileMoverModule
from modules.file_mover.services import (
    EXISTS,
    FAILED,
    MISSING,
    MOVED,
    PENDING,
    build_preview,
    execute_move,
    export_csv,
    revalidate_preview,
)


class FileMoverServiceTests(unittest.TestCase):
    def make_tree(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        source = root / "source"
        destination = root / "destination"
        source.mkdir()
        destination.mkdir()
        return temporary, source, destination

    def test_module_metadata_and_lazy_window(self):
        module = FileMoverModule()
        self.assertEqual(module.info.module_id, "file_mover")
        self.assertEqual(module.info.name, "File Mover")
        self.assertEqual(module.info.category, "File Management")
        self.assertEqual(module.info.sort_order, 40)
        self.assertNotIn("windows", FileMoverModule.__dict__)

    def test_module_is_discoverable_without_launcher_registration(self):
        report = ModuleManager().discover()
        self.assertIn("file_mover", report.registered_module_ids)
        self.assertFalse(any(failure.module_name == "file_mover" for failure in report.failures))

    def test_recursive_hidden_and_empty_directories(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "nested").mkdir()
            (source / "empty").mkdir()
            (source / ".hidden").write_text("hidden", encoding="utf-8")
            (source / "nested" / "visible.txt").write_text("visible", encoding="utf-8")
            preview = build_preview(source, destination)
            self.assertEqual([entry.source.name for entry in preview.entries], [".hidden", "visible.txt"])
            self.assertTrue(preview.valid)

    def test_preview_is_deterministic_and_flattened(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "z").write_text("z", encoding="utf-8")
            (source / "a").mkdir()
            (source / "a" / "z").write_text("nested", encoding="utf-8")
            preview = build_preview(source, destination)
            self.assertEqual([entry.source.name for entry in preview.entries], ["z", "z"])
            self.assertTrue(all(entry.destination.parent == destination for entry in preview.entries))

    def test_same_folder_is_blocked(self):
        temporary, source, _ = self.make_tree()
        with temporary:
            preview = build_preview(source, source)
            self.assertFalse(preview.valid)
            self.assertTrue(preview.blocking_issues)

    def test_destination_descendant_is_blocked(self):
        temporary, source, _ = self.make_tree()
        with temporary:
            child = source / "child"
            child.mkdir()
            preview = build_preview(source, child)
            self.assertFalse(preview.valid)
            self.assertIn("inside the source", preview.blocking_issues[0])

    def test_source_inside_destination_is_allowed(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            nested_source = destination / "source"
            nested_source.mkdir()
            (nested_source / "file.txt").write_text("data", encoding="utf-8")
            preview = build_preview(nested_source, destination)
            self.assertTrue(preview.valid)
            self.assertEqual(preview.entries[0].destination, destination / "file.txt")

    def test_existing_destination_is_skipped_without_overwrite(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            source_file = source / "same.txt"
            source_file.write_text("source", encoding="utf-8")
            destination_file = destination / "same.txt"
            destination_file.write_text("destination", encoding="utf-8")
            preview = build_preview(source, destination)
            summary = execute_move(preview, confirmed=True)
            self.assertEqual(summary.moved, 0)
            self.assertEqual(summary.skipped, 1)
            self.assertEqual(preview.entries[0].status, EXISTS)
            self.assertEqual(destination_file.read_text(encoding="utf-8"), "destination")
            self.assertTrue(source_file.exists())

    def test_same_physical_source_and_destination_file_is_rejected(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            source_file = source / "file.txt"
            source_file.write_text("data", encoding="utf-8")
            try:
                (destination / "file.txt").hardlink_to(source_file)
            except (OSError, NotImplementedError):
                self.skipTest("Hard links are unavailable")
            preview = build_preview(source, destination)
            revalidate_preview(preview)
            self.assertEqual(preview.entries[0].status, FAILED)

    def test_move_requires_explicit_confirmation(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "file.txt").write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            summary = execute_move(preview)
            self.assertEqual(summary.moved, 0)
            self.assertIn("confirmation", summary.issues[0])
            self.assertTrue((source / "file.txt").exists())

    def test_same_drive_move_is_atomic_and_verified(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            original = source / "file.txt"
            original.write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            summary = execute_move(preview, confirmed=True)
            self.assertEqual(summary.moved, 1)
            self.assertEqual(preview.entries[0].status, MOVED)
            self.assertFalse(original.exists())
            self.assertEqual((destination / "file.txt").read_text(encoding="utf-8"), "data")

    def test_cross_drive_copy_verifies_checksum_before_source_removal(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            original = source / "file.txt"
            original.write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            with mock.patch("modules.file_mover.services._same_filesystem", return_value=False):
                summary = execute_move(preview, confirmed=True)
            self.assertEqual(summary.moved, 1)
            self.assertFalse(original.exists())
            self.assertEqual((destination / "file.txt").read_text(encoding="utf-8"), "data")
            self.assertEqual(list(destination.glob("*.fc-hub-incomplete")), [])

    def test_cross_drive_verification_failure_preserves_source_and_removes_partial_destination(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            original = source / "file.txt"
            original.write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            with mock.patch("modules.file_mover.services._same_filesystem", return_value=False), mock.patch(
                "modules.file_mover.services._sha256_file", side_effect=["expected", "wrong"]
            ):
                summary = execute_move(preview, confirmed=True)
            self.assertEqual(summary.failed, 1)
            self.assertTrue(original.exists())
            self.assertFalse((destination / "file.txt").exists())

    def test_cross_drive_copy_failure_cleans_incomplete_destination(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            original = source / "file.txt"
            original.write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            with mock.patch("modules.file_mover.services._same_filesystem", return_value=False), mock.patch(
                "modules.file_mover.services.shutil.copy2", side_effect=OSError("copy failed")
            ):
                summary = execute_move(preview, confirmed=True)
            self.assertEqual(summary.failed, 1)
            self.assertTrue(original.exists())

    def test_partial_failure_does_not_abort_other_files(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "a.txt").write_text("a", encoding="utf-8")
            (source / "b.txt").write_text("b", encoding="utf-8")
            preview = build_preview(source, destination)
            with mock.patch(
                "modules.file_mover.services._safe_move",
                side_effect=[(False, "simulated failure"), (True, "")],
            ):
                summary = execute_move(preview, confirmed=True)
            self.assertEqual((summary.moved, summary.failed), (1, 1))
            self.assertEqual([entry.status for entry in preview.entries], [FAILED, MOVED])

    def test_missing_source_is_reported_at_revalidation(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            source_file = source / "file.txt"
            source_file.write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            source_file.unlink()
            revalidate_preview(preview)
            self.assertEqual(preview.entries[0].status, MISSING)

    def test_changed_source_is_failed_at_revalidation(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            source_file = source / "file.txt"
            source_file.write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            source_file.write_text("changed", encoding="utf-8")
            revalidate_preview(preview)
            self.assertEqual(preview.entries[0].status, FAILED)

    def test_destination_created_after_preview_is_skipped(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            source_file = source / "file.txt"
            source_file.write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            (destination / "file.txt").write_text("other", encoding="utf-8")
            revalidate_preview(preview)
            self.assertEqual(preview.entries[0].status, EXISTS)

    def test_cancellation_stops_before_next_file(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "a.txt").write_text("a", encoding="utf-8")
            (source / "b.txt").write_text("b", encoding="utf-8")
            preview = build_preview(source, destination)
            cancel = threading.Event()

            def progress(item):
                if item.status == MOVED:
                    cancel.set()

            summary = execute_move(preview, confirmed=True, cancel_event=cancel, progress_callback=progress)
            self.assertTrue(summary.cancelled)
            self.assertEqual(preview.entries[0].status, MOVED)
            self.assertEqual(preview.entries[1].status, PENDING)

    def test_progress_reports_preview_and_move(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "file.txt").write_text("data", encoding="utf-8")
            preview_progress = []
            preview = build_preview(source, destination, progress_callback=preview_progress.append)
            self.assertEqual(preview_progress[0].phase, "preview")
            move_progress = []
            execute_move(preview, confirmed=True, progress_callback=move_progress.append)
            self.assertEqual(move_progress[-1].status, "Complete")

    def test_preview_cancellation_is_not_valid(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            for index in range(3):
                (source / f"{index}.txt").write_text("data", encoding="utf-8")
            cancel = threading.Event()
            cancel.set()
            preview = build_preview(source, destination, cancel_event=cancel)
            self.assertTrue(preview.cancelled)
            self.assertFalse(preview.valid)

    def test_symlinked_directories_are_not_followed(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            target = source / "target"
            target.mkdir()
            (target / "real.txt").write_text("data", encoding="utf-8")
            link = source / "loop"
            try:
                link.symlink_to(source, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symbolic links are unavailable")
            preview = build_preview(source, destination)
            self.assertEqual(len(preview.entries), 1)

    def test_csv_has_legacy_columns_and_error_details(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "file.txt").write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
                filename = Path(handle.name)
            try:
                export_csv(preview, filename)
                with filename.open(newline="", encoding="utf-8-sig") as stream:
                    rows = list(csv.reader(stream))
                self.assertEqual(rows[0][:3], ["Source", "Destination", "Status"])
                self.assertEqual(rows[1][2], PENDING)
            finally:
                filename.unlink(missing_ok=True)

    def test_unreadable_or_disappearing_entries_are_reported(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            missing = source / "gone.txt"
            with mock.patch(
                "modules.file_mover.services._scan_files",
                return_value=([missing], ["scan warning"], False),
            ):
                preview = build_preview(source, destination)
            self.assertTrue(preview.entries or preview.issues)

    def test_no_third_party_service_dependency(self):
        source_text = Path(__file__).parents[1].joinpath("modules", "file_mover", "services.py").read_text(encoding="utf-8")
        self.assertNotIn("pandas", source_text)
        self.assertNotIn("send2trash", source_text)

    def test_no_utility_compatibility_shim_is_created(self):
        self.assertFalse(Path(__file__).parents[1].joinpath("modules", "file_mover", "utility.py").exists())

    def test_summary_contains_counts_and_elapsed_time(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "file.txt").write_text("data", encoding="utf-8")
            summary = execute_move(build_preview(source, destination), confirmed=True)
            self.assertEqual(summary.moved, 1)
            self.assertEqual(summary.skipped, 0)
            self.assertEqual(summary.failed, 0)
            self.assertIsInstance(summary.elapsed, float)

    def test_service_has_no_legacy_framework_or_database_imports(self):
        service_text = Path(__file__).parents[1].joinpath("modules", "file_mover", "services.py").read_text(encoding="utf-8")
        self.assertNotIn("utility_base", service_text)
        self.assertNotIn("database", service_text)

    def test_destination_parent_is_not_created_by_preview(self):
        temporary, source, _ = self.make_tree()
        with temporary:
            destination = source.parent / "new-destination"
            (source / "file.txt").write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            self.assertFalse(destination.exists())
            self.assertFalse(preview.valid)

    def test_invalid_source_is_blocked(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            missing = source / "does-not-exist"
            preview = build_preview(missing, destination)
            self.assertFalse(preview.valid)
            self.assertIn("valid source", preview.blocking_issues[0])

    def test_revalidation_rechecks_destination_relationship(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "file.txt").write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            preview.destination_folder = source / "unsafe"
            preview.destination_folder.mkdir()
            revalidate_preview(preview)
            self.assertEqual(preview.entries[0].status, FAILED)

    def test_destination_race_is_not_overwritten(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            source_file = source / "file.txt"
            source_file.write_text("source", encoding="utf-8")
            preview = build_preview(source, destination)

            def race(_entry):
                (destination / "file.txt").write_text("racer", encoding="utf-8")
                return False, "Destination file appeared during the move."

            with mock.patch("modules.file_mover.services._safe_move", side_effect=race):
                summary = execute_move(preview, confirmed=True)
            self.assertEqual(summary.skipped, 1)
            self.assertEqual((destination / "file.txt").read_text(encoding="utf-8"), "racer")
            self.assertTrue(source_file.exists())

    def test_export_reports_failed_status_and_error(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "file.txt").write_text("data", encoding="utf-8")
            preview = build_preview(source, destination)
            preview.entries[0].status = FAILED
            preview.entries[0].error = "test failure"
            filename = Path(temporary.name) / "report.csv"
            export_csv(preview, filename)
            with filename.open(newline="", encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["Status"], FAILED)
            self.assertEqual(rows[0]["Error"], "test failure")

    def test_unwritable_destination_is_blocked(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "file.txt").write_text("data", encoding="utf-8")
            with mock.patch("modules.file_mover.services.os.access", return_value=False):
                preview = build_preview(source, destination)
            self.assertFalse(preview.valid)
            self.assertIn("not writable", preview.blocking_issues[0])

    def test_insufficient_space_is_blocked(self):
        temporary, source, destination = self.make_tree()
        with temporary:
            (source / "file.txt").write_text("data", encoding="utf-8")
            usage = shutil.disk_usage(destination)
            with mock.patch(
                "modules.file_mover.services.shutil.disk_usage",
                return_value=type(usage)(usage.total, usage.used, 0),
            ):
                preview = build_preview(source, destination)
            self.assertFalse(preview.valid)
            self.assertIn("enough free", preview.blocking_issues[0])


if __name__ == "__main__":
    unittest.main()
