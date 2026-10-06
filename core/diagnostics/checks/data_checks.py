"""Data integrity checks — orphaned records, broken references, amount mismatches."""

import sqlite3
from contextlib import closing
from pathlib import Path

from core.app_paths import get_project_root
from core.diagnostics.models import DiagnosticResult, DiagnosticStatus


PROJECT_ROOT = get_project_root()


class Check:
    description = ""

    def result(self, status, summary, details="", recommendation="No action required.", blocking=False, fixable=False):
        return DiagnosticResult(
            self.check_id, self.category, self.name, status, summary,
            details or summary, recommendation, blocking,
        )


def _default_db_path():
    try:
        from core.database import database
        return Path(database.path)
    except Exception:
        return PROJECT_ROOT / "database" / "fc_hub.db"


def _ro_connection(path=None):
    path = Path(path) if path else _default_db_path()
    if not path.exists():
        return None
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


# ── FK violation scan ──────────────────────────────────────

class ForeignKeyViolationCheck(Check):
    check_id = "data.fk_violations"
    category = "Data Integrity"
    name = "Foreign key violations"

    def run(self):
        conn = _ro_connection()
        if conn is None:
            return self.result(DiagnosticStatus.INFO, "Database not found; skipping.")
        with closing(conn):
            conn.execute("PRAGMA foreign_keys = ON")
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if not violations:
            return self.result(DiagnosticStatus.PASS, "No foreign key violations found.")
        by_table = {}
        for table, rowid, ref_table, fk_idx in violations:
            by_table.setdefault(table, []).append((rowid, ref_table))
        lines = []
        for table, refs in sorted(by_table.items()):
            lines.append(f"{table}: {len(refs)} violation(s) → {refs[0][1]}")
        details = f"{len(violations)} violation(s) across {len(by_table)} table(s):\n" + "\n".join(lines)
        return self.result(
            DiagnosticStatus.FAIL, f"{len(violations)} foreign key violation(s) found.",
            details, "Run Fix to NULL out dangling references, or restore from backup.", True,
        )


# ── Orphaned records (child rows whose parent is deleted or missing) ───

class OrphanedRecordCheck(Check):
    check_id = "data.orphaned_records"
    category = "Data Integrity"
    name = "Orphaned records"

    PARENT_CHECKS = [
        ("quotes", "customer_id", "customers", "id", "Quotes without a customer"),
        ("quote_line_items", "quote_id", "quotes", "id", "Line items without a quote"),
        ("quote_documents", "quote_id", "quotes", "id", "Documents without a quote"),
        ("quote_documents", "customer_id", "customers", "id", "Documents without a customer"),
        ("payments", "customer_id", "customers", "id", "Payments without a customer"),
        ("payment_allocations", "payment_id", "payments", "id", "Allocations without a payment"),
        ("payment_allocations", "quote_document_id", "quote_documents", "id", "Allocations without a document"),
        ("statements", "customer_id", "customers", "id", "Statements without a customer"),
        ("statement_line_items", "statement_id", "statements", "id", "Statement lines without a statement"),
        ("job_cards", "customer_id", "customers", "id", "Job cards without a customer"),
        ("job_card_entries", "job_card_id", "job_cards", "id", "Job card entries without a job card"),
        ("site_visits", "customer_id", "customers", "id", "Site visits without a customer"),
        ("site_images", "customer_id", "customers", "id", "Site images without a customer"),
        ("site_plans", "site_id", "customer_sites", "id", "Site plans without a site"),
        ("site_plan_items", "site_plan_id", "site_plans", "id", "Site plan items without a plan"),
        ("customer_contacts", "customer_id", "customers", "id", "Contacts without a customer"),
        ("customer_addresses", "customer_id", "customers", "id", "Addresses without a customer"),
        ("customer_sites", "customer_id", "customers", "id", "Sites without a customer"),
        ("customer_activities", "customer_id", "customers", "id", "Activities without a customer"),
        ("job_cost_allocations", "job_card_id", "job_cards", "id", "Cost allocations without a job card"),
    ]

    def run(self):
        conn = _ro_connection()
        if conn is None:
            return self.result(DiagnosticStatus.INFO, "Database not found; skipping.")
        issues = []
        with closing(conn):
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for child, fk_col, parent, pk_col, label in self.PARENT_CHECKS:
                if child not in tables or parent not in tables:
                    continue
                sql = (
                    f"SELECT COUNT(*) FROM {child} c "
                    f"WHERE c.{fk_col} IS NOT NULL AND c.{fk_col} != '' "
                    f"AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE p.{pk_col} = c.{fk_col})"
                )
                count = conn.execute(sql).fetchone()[0]
                if count:
                    issues.append(f"{label}: {count}")
        if not issues:
            return self.result(DiagnosticStatus.PASS, "No orphaned records found.", f"Checked {len(self.PARENT_CHECKS)} relationships.")
        details = "\n".join(issues)
        return self.result(
            DiagnosticStatus.WARNING, f"{len(issues)} orphaned record type(s) found.",
            details, "Run Fix to NULL out orphaned references or soft-delete the records.",
        )


# ── Duplicate document numbers ─────────────────────────────

class DuplicateDocumentNumberCheck(Check):
    check_id = "data.duplicate_doc_numbers"
    category = "Data Integrity"
    name = "Duplicate document numbers"

    def run(self):
        conn = _ro_connection()
        if conn is None:
            return self.result(DiagnosticStatus.INFO, "Database not found; skipping.")
        issues = []
        with closing(conn):
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "quote_documents" in tables:
                dupes = conn.execute(
                    "SELECT document_number, COUNT(*) c FROM quote_documents "
                    "WHERE document_number IS NOT NULL AND document_number != '' "
                    "GROUP BY document_number HAVING c > 1"
                ).fetchall()
                for num, count in dupes:
                    issues.append(f"Document {num}: {count} copies")
            if "quotes" in tables:
                dupes = conn.execute(
                    "SELECT quote_number, COUNT(*) c FROM quotes "
                    "WHERE quote_number IS NOT NULL AND quote_number != '' "
                    "GROUP BY quote_number HAVING c > 1"
                ).fetchall()
                for num, count in dupes:
                    issues.append(f"Quote {num}: {count} copies")
            if "job_cards" in tables:
                dupes = conn.execute(
                    "SELECT job_card_number, COUNT(*) c FROM job_cards "
                    "WHERE job_card_number IS NOT NULL AND job_card_number != '' "
                    "GROUP BY job_card_number HAVING c > 1"
                ).fetchall()
                for num, count in dupes:
                    issues.append(f"Job card {num}: {count} copies")
        if not issues:
            return self.result(DiagnosticStatus.PASS, "No duplicate document numbers found.")
        return self.result(
            DiagnosticStatus.WARNING, f"{len(issues)} duplicate number(s) found.",
            "\n".join(issues), "Review and renumber the duplicates manually — automated renumbering risks breaking printed documents.",
        )


# ── Split invoice amount validation ───────────────────────

class SplitInvoiceAmountCheck(Check):
    check_id = "data.split_invoice_amounts"
    category = "Data Integrity"
    name = "Split invoice amounts"

    def run(self):
        conn = _ro_connection()
        if conn is None:
            return self.result(DiagnosticStatus.INFO, "Database not found; skipping.")
        issues = []
        with closing(conn):
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "quote_documents" not in tables or "quotes" not in tables:
                return self.result(DiagnosticStatus.INFO, "Quote tables not found; skipping.")
            cols = {r[1] for r in conn.execute("PRAGMA table_info(quotes)")}
            if "split_invoice" not in cols:
                return self.result(DiagnosticStatus.INFO, "Split invoice not enabled; skipping.")
            rows = conn.execute(
                "SELECT q.id, q.quote_number, q.total_minor, "
                "SUM(CASE WHEN qd.invoice_part = 'deposit' THEN qd.total_minor ELSE 0 END) as dep, "
                "SUM(CASE WHEN qd.invoice_part = 'balance' THEN qd.total_minor ELSE 0 END) as bal "
                "FROM quotes q JOIN quote_documents qd ON qd.quote_id = q.id "
                "WHERE q.split_invoice = 1 AND qd.doc_type = 'Tax Invoice' "
                "GROUP BY q.id HAVING (dep + bal) != q.total_minor AND dep > 0 AND bal > 0"
            ).fetchall()
            for _, qnum, total, dep, bal in rows:
                issues.append(f"{qnum}: deposit {dep} + balance {bal} = {dep+bal}, quote total {total}")
        if not issues:
            return self.result(DiagnosticStatus.PASS, "All split invoices sum correctly.")
        return self.result(
            DiagnosticStatus.FAIL, f"{len(issues)} split invoice mismatch(es).",
            "\n".join(issues), "Review the deposit/balance amounts on the listed quotes.", True,
        )


# ── Soft-deleted records still referenced ──────────────────

class SoftDeletedReferenceCheck(Check):
    check_id = "data.soft_deleted_refs"
    category = "Data Integrity"
    name = "References to deleted records"

    CHECKS = [
        ("quotes", "customer_id", "customers", "Quotes referencing deleted customers"),
        ("job_cards", "customer_id", "customers", "Job cards referencing deleted customers"),
        ("site_visits", "customer_id", "customers", "Site visits referencing deleted customers"),
        ("site_images", "customer_id", "customers", "Images referencing deleted customers"),
        ("quotes", "site_id", "customer_sites", "Quotes referencing deleted sites"),
    ]

    def run(self):
        conn = _ro_connection()
        if conn is None:
            return self.result(DiagnosticStatus.INFO, "Database not found; skipping.")
        issues = []
        with closing(conn):
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for child, fk_col, parent, label in self.CHECKS:
                if child not in tables or parent not in tables:
                    continue
                parent_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({parent})")}
                if "deleted_at" not in parent_cols:
                    continue
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {child} c "
                    f"JOIN {parent} p ON p.id = c.{fk_col} "
                    f"WHERE p.deleted_at IS NOT NULL AND c.{fk_col} IS NOT NULL"
                ).fetchone()[0]
                if count:
                    issues.append(f"{label}: {count}")
        if not issues:
            return self.result(DiagnosticStatus.PASS, "No live records reference deleted parents.")
        return self.result(
            DiagnosticStatus.WARNING, f"{len(issues)} reference type(s) point to deleted records.",
            "\n".join(issues), "These records may be invisible in the UI. Review and reassign or soft-delete them.",
        )


# ── Business settings completeness ─────────────────────────

class BusinessSettingsCheck(Check):
    check_id = "data.business_settings"
    category = "Configuration"
    name = "Business settings"

    REQUIRED = ["email", "phone"]
    NAME_COLS = ["company_name", "trading_name", "legal_name"]

    def run(self):
        conn = _ro_connection()
        if conn is None:
            return self.result(DiagnosticStatus.INFO, "Database not found; skipping.")
        with closing(conn):
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "business_settings" not in tables:
                return self.result(DiagnosticStatus.WARNING, "No business_settings table.", "", "Run the app once to initialise settings.")
            row = conn.execute("SELECT * FROM business_settings LIMIT 1").fetchone()
            if row is None:
                return self.result(DiagnosticStatus.WARNING, "Business settings row is empty.", "", "Open Settings → Business Settings and fill in the details.")
            cols = [r[1] for r in conn.execute("PRAGMA table_info(business_settings)")]
            settings = dict(zip(cols, row))
        has_name = any(settings.get(c) for c in self.NAME_COLS)
        missing = [] if has_name else ["company name"]
        missing += [f for f in self.REQUIRED if not settings.get(f)]
        if missing:
            return self.result(
                DiagnosticStatus.WARNING, f"{len(missing)} required setting(s) are blank.",
                "Missing: " + ", ".join(missing), "Open Settings → Business Settings and complete the listed fields.",
            )
        return self.result(DiagnosticStatus.PASS, "Business settings are complete.", f"Company: {settings.get('company_name', 'N/A')}")


# ── Numbering sequence gaps ────────────────────────────────

class NumberingSequenceCheck(Check):
    check_id = "data.numbering_sequences"
    category = "Data Integrity"
    name = "Numbering sequences"

    def run(self):
        conn = _ro_connection()
        if conn is None:
            return self.result(DiagnosticStatus.INFO, "Database not found; skipping.")
        issues = []
        with closing(conn):
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "numbering_sequences" not in tables:
                return self.result(DiagnosticStatus.INFO, "Numbering table not found; skipping.")
            seqs = conn.execute("SELECT id, prefix, document_type, last_reset_year, next_value FROM numbering_sequences").fetchall()
            if not seqs:
                return self.result(DiagnosticStatus.INFO, "No numbering sequences configured.")
            for sid, prefix, doc_type, year, next_val in seqs:
                if next_val < 1:
                    issues.append(f"{prefix}-{doc_type}_{year}: next_value is {next_val} (should be ≥ 1)")
        if not issues:
            return self.result(DiagnosticStatus.PASS, f"{len(seqs)} numbering sequence(s) are valid.")
        return self.result(
            DiagnosticStatus.WARNING, f"{len(issues)} numbering issue(s).",
            "\n".join(issues), "Review and correct the sequence values in the database.",
        )


DATA_CHECKS = [
    ForeignKeyViolationCheck,
    OrphanedRecordCheck,
    DuplicateDocumentNumberCheck,
    SplitInvoiceAmountCheck,
    SoftDeletedReferenceCheck,
    BusinessSettingsCheck,
    NumberingSequenceCheck,
]
