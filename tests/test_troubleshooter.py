from datetime import datetime
import tempfile
import unittest
from pathlib import Path

from core.diagnostics.models import DiagnosticResult, DiagnosticStatus
from modules.troubleshooter.services import TroubleshooterService, safe_filename, summarize


def sample_results():
    return [
        DiagnosticResult("one", "Test", "Unicode ✓", DiagnosticStatus.PASS, "Healthy", "All good", "None"),
        DiagnosticResult("two", "Test", "Warning", DiagnosticStatus.WARNING, "Review", "Details", "Take care"),
        DiagnosticResult("three", "Test", "Failure", DiagnosticStatus.FAIL, "Broken", "Details", "Repair", True),
        DiagnosticResult("four", "Test", "Info", DiagnosticStatus.INFO, "Notice", "Details", "None"),
    ]


class TroubleshooterTests(unittest.TestCase):
    def test_summary_counts_all_statuses(self):
        self.assertEqual(summarize(sample_results()), {"total": 4, "passed": 1, "warnings": 1, "failed": 1, "informational": 1, "blocking": 1})

    def test_report_contains_required_fields_and_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "health.txt"
            path = TroubleshooterService().export_report(sample_results(), destination, datetime(2026, 7, 21, 10, 30))
            text = path.read_text(encoding="utf-8")
            for expected in ("FC Hub Troubleshooter", "Checks run: 4", "Blocking failures: 1", "Unicode ✓", "Recommendation: Repair"):
                self.assertIn(expected, text)

    def test_report_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "existing.txt"
            destination.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                TroubleshooterService().export_report(sample_results(), destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "keep")

    def test_safe_filename(self):
        self.assertEqual(safe_filename("Health: 21/07 ✓"), "Health_21_07")

    def test_troubleshooter_and_launcher_import_without_gui_start(self):
        try:
            import customtkinter  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("customtkinter is not installed in the bundled verification runtime")
        import launcher
        from modules.troubleshooter.utility import TroubleshooterUtility
        from modules.troubleshooter.windows import TroubleshooterWindow
        self.assertTrue(callable(launcher.main))
        self.assertEqual(TroubleshooterUtility.__name__, "TroubleshooterUtility")
        self.assertEqual(TroubleshooterWindow.__name__, "TroubleshooterWindow")


if __name__ == "__main__":
    unittest.main()
