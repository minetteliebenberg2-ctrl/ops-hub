"""Tests for the data integrity and file system diagnostic checks."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from core.diagnostics.checks.data_checks import (
    ForeignKeyViolationCheck,
    OrphanedRecordCheck,
    DuplicateDocumentNumberCheck,
    SplitInvoiceAmountCheck,
    SoftDeletedReferenceCheck,
    BusinessSettingsCheck,
    NumberingSequenceCheck,
)
from core.diagnostics.checks.file_checks import (
    DatabaseBackupAgeCheck,
    AssetFileCheck,
    DatabaseSizeCheck,
)
from core.diagnostics.models import DiagnosticStatus
from core.diagnostics.fixers import can_fix, run_fix, available_fixers


class TestCheckRegistration:
    def test_all_checks_load(self):
        from core.diagnostics.checks import build_default_registry
        registry = build_default_registry()
        assert len(registry) >= 22

    def test_fixers_registered(self):
        fixers = available_fixers()
        assert "data.fk_violations" in fixers
        assert "data.orphaned_records" in fixers
        assert "data.soft_deleted_refs" in fixers
        assert "files.client_folders" in fixers
        assert "files.db_size" in fixers

    def test_can_fix_returns_false_for_unknown(self):
        assert not can_fix("nonexistent.check")


class TestForeignKeyViolationCheck:
    def test_no_violations(self, tmp_path):
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE parents (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE children (id TEXT, parent_id TEXT REFERENCES parents(id))")
        conn.execute("INSERT INTO parents VALUES ('p1')")
        conn.execute("INSERT INTO children VALUES ('c1', 'p1')")
        conn.commit()
        conn.close()
        check = ForeignKeyViolationCheck()
        with patch("core.diagnostics.checks.data_checks._ro_connection", return_value=sqlite3.connect(f"file:{db}?mode=ro", uri=True)):
            result = check.run()
        assert result.status == DiagnosticStatus.PASS

    def test_with_violations(self, tmp_path):
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("CREATE TABLE parents (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE children (id TEXT, parent_id TEXT REFERENCES parents(id))")
        conn.execute("INSERT INTO children VALUES ('c1', 'missing')")
        conn.commit()
        conn.close()
        check = ForeignKeyViolationCheck()
        with patch("core.diagnostics.checks.data_checks._ro_connection", return_value=sqlite3.connect(f"file:{db}?mode=ro", uri=True)):
            result = check.run()
        assert result.status == DiagnosticStatus.FAIL


class TestOrphanedRecordCheck:
    def test_no_orphans(self, tmp_path):
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE customers (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE quotes (id TEXT, customer_id TEXT)")
        conn.execute("INSERT INTO customers VALUES ('c1')")
        conn.execute("INSERT INTO quotes VALUES ('q1', 'c1')")
        conn.commit()
        conn.close()
        check = OrphanedRecordCheck()
        with patch("core.diagnostics.checks.data_checks._ro_connection", return_value=sqlite3.connect(f"file:{db}?mode=ro", uri=True)):
            result = check.run()
        assert result.status == DiagnosticStatus.PASS


class TestDuplicateDocumentNumberCheck:
    def test_no_duplicates(self, tmp_path):
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE quote_documents (id TEXT, document_number TEXT)")
        conn.execute("INSERT INTO quote_documents VALUES ('d1', 'GHH-PF_26/001')")
        conn.execute("INSERT INTO quote_documents VALUES ('d2', 'GHH-PF_26/002')")
        conn.commit()
        conn.close()
        check = DuplicateDocumentNumberCheck()
        with patch("core.diagnostics.checks.data_checks._ro_connection", return_value=sqlite3.connect(f"file:{db}?mode=ro", uri=True)):
            result = check.run()
        assert result.status == DiagnosticStatus.PASS

    def test_with_duplicates(self, tmp_path):
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE quote_documents (id TEXT, document_number TEXT)")
        conn.execute("INSERT INTO quote_documents VALUES ('d1', 'GHH-PF_26/001')")
        conn.execute("INSERT INTO quote_documents VALUES ('d2', 'GHH-PF_26/001')")
        conn.commit()
        conn.close()
        check = DuplicateDocumentNumberCheck()
        with patch("core.diagnostics.checks.data_checks._ro_connection", return_value=sqlite3.connect(f"file:{db}?mode=ro", uri=True)):
            result = check.run()
        assert result.status == DiagnosticStatus.WARNING


class TestBusinessSettingsCheck:
    def test_complete_settings(self, tmp_path):
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE business_settings (company_name TEXT, email TEXT, phone TEXT)")
        conn.execute("INSERT INTO business_settings VALUES ('Test Co', 'a@b.com', '012345')")
        conn.commit()
        conn.close()
        check = BusinessSettingsCheck()
        with patch("core.diagnostics.checks.data_checks._ro_connection", return_value=sqlite3.connect(f"file:{db}?mode=ro", uri=True)):
            result = check.run()
        assert result.status == DiagnosticStatus.PASS

    def test_missing_settings(self, tmp_path):
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE business_settings (company_name TEXT, email TEXT, phone TEXT)")
        conn.execute("INSERT INTO business_settings VALUES ('Test Co', '', '')")
        conn.commit()
        conn.close()
        check = BusinessSettingsCheck()
        with patch("core.diagnostics.checks.data_checks._ro_connection", return_value=sqlite3.connect(f"file:{db}?mode=ro", uri=True)):
            result = check.run()
        assert result.status == DiagnosticStatus.WARNING


class TestAssetFileCheck:
    def test_assets_present(self, tmp_path):
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "logo_placeholder.png").write_bytes(b"PNG")
        check = AssetFileCheck()
        with patch("core.diagnostics.checks.file_checks.PROJECT_ROOT", tmp_path):
            result = check.run()
        assert result.status == DiagnosticStatus.PASS


class TestDatabaseSizeCheck:
    def test_small_db(self, tmp_path):
        db_dir = tmp_path / "database"
        db_dir.mkdir()
        db = db_dir / "fc_hub.db"
        db.write_bytes(b"x" * 1024)
        check = DatabaseSizeCheck()
        with patch("core.diagnostics.checks.file_checks.PROJECT_ROOT", tmp_path):
            result = check.run()
        assert result.status == DiagnosticStatus.PASS
