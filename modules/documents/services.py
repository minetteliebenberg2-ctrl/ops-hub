# ==========================================================
# FC Hub - Documents services
# ----------------------------------------------------------
# Purpose:
# Storage and retrieval for the Documents module: the branded
# letterhead/spreadsheet templates you create new files from, and
# the compliance paperwork (Tax Compliance, COIDA, bank
# confirmations, insurance) you store and have to keep current.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import shutil
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from core.app_paths import get_project_root
from core.database import DATABASE_PATH


# Document categories are user-managed (Settings -> Document Types,
# picklist_options list_name "document_category") rather than fixed here -
# see core/picklist_service.DOCUMENT_CATEGORY. This module doesn't validate
# category against that list: a category deleted from Settings should not
# retroactively invalidate documents already filed under it.

# Documents whose lapse actually bites: a client asks mid-tender and the
# certificate turns out to have expired. Anything inside this window is
# surfaced on the Dashboard.
EXPIRY_WARNING_DAYS = 30

DEFAULT_DOCUMENTS_DIRNAME = "documents"


@dataclass
class Document:
    id: str = ""
    title: str = ""
    category: str = "Compliance"
    stored_filename: str = ""
    original_filename: str = ""
    issue_date: str = ""
    expiry_date: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    updated_by: str = ""

    def days_until_expiry(self, today=None):
        """Whole days until expiry_date, negative if already lapsed, or None
        if this document doesn't expire / the date is unparseable."""

        if not self.expiry_date.strip():
            return None
        parsed = parse_date(self.expiry_date)
        if parsed is None:
            return None
        return (parsed - (today or date.today())).days

    @property
    def is_expired(self):
        days = self.days_until_expiry()
        return days is not None and days < 0

    @property
    def is_expiring_soon(self):
        days = self.days_until_expiry()
        return days is not None and 0 <= days <= EXPIRY_WARNING_DAYS


def parse_date(value):
    """Accept the date formats that show up across FC Hub and Windows date
    pickers rather than forcing one on the user."""

    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DocumentsRepository:

    def __init__(self, database_path=None):
        self.database_path = Path(database_path) if database_path else DATABASE_PATH

    def _connect(self):
        connection = sqlite3.connect(str(self.database_path))
        connection.row_factory = sqlite3.Row
        return connection

    # ----- documents root -------------------------------------------------

    def get_documents_root(self):
        """Where document files live. Configurable via business_settings so it
        can be repointed at OneDrive later; defaults to a folder inside the
        project, which the Backup module already covers."""

        configured = ""
        with closing(self._connect()) as connection, connection:
            try:
                row = connection.execute(
                    "SELECT documents_root FROM business_settings WHERE id = 'business'"
                ).fetchone()
                configured = (row["documents_root"] if row else "") or ""
            except sqlite3.OperationalError:
                # Pre-v0017 database - fall through to the default.
                configured = ""

        root = Path(configured) if configured.strip() else get_project_root() / DEFAULT_DOCUMENTS_DIRNAME
        root.mkdir(parents=True, exist_ok=True)
        return root

    def set_documents_root(self, path):
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE business_settings SET documents_root = ?, updated_at = ? WHERE id = 'business'",
                (str(path), _now()),
            )

    # ----- queries --------------------------------------------------------

    def list_documents(self, category=None):
        query = "SELECT * FROM documents"
        params = ()
        if category:
            query += " WHERE category = ?"
            params = (category,)
        query += " ORDER BY category, title"
        with closing(self._connect()) as connection, connection:
            return [self._to_document(row) for row in connection.execute(query, params)]

    def get(self, document_id):
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        return self._to_document(row) if row else None

    def expiring_documents(self, within_days=EXPIRY_WARNING_DAYS, today=None):
        """Expired first (most overdue first), then those lapsing soonest -
        the order you'd want to act on them."""

        today = today or date.today()
        results = []
        for document in self.list_documents():
            days = document.days_until_expiry(today)
            if days is not None and days <= within_days:
                results.append(document)
        return sorted(results, key=lambda d: d.days_until_expiry(today))

    # ----- mutations ------------------------------------------------------

    def add_document(self, source_path, title, category="Compliance", issue_date="",
                     expiry_date="", notes="", updated_by=""):
        """Copy a file from anywhere on the machine into the documents root and
        record it. The original is left untouched."""

        source_path = Path(source_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"No such file: {source_path}")

        title = (title or source_path.stem).strip()
        if not title:
            raise ValueError("A document needs a title.")

        root = self.get_documents_root()
        document_id = str(uuid.uuid4())
        # Prefix with the id so two files of the same name can coexist and a
        # row always maps to exactly one file on disk.
        stored_filename = f"{document_id[:8]}_{source_path.name}"
        shutil.copy2(source_path, root / stored_filename)

        now = _now()
        document = Document(
            id=document_id, title=title, category=category,
            stored_filename=stored_filename, original_filename=source_path.name,
            issue_date=issue_date, expiry_date=expiry_date, notes=notes,
            created_at=now, updated_at=now, updated_by=updated_by,
        )
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO documents (id, title, category, stored_filename,
                       original_filename, issue_date, expiry_date, notes,
                       created_at, updated_at, updated_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (document.id, document.title, document.category, document.stored_filename,
                 document.original_filename, document.issue_date, document.expiry_date,
                 document.notes, document.created_at, document.updated_at, document.updated_by),
            )
        return document

    def update_document(self, document_id, **fields):
        allowed = {"title", "category", "issue_date", "expiry_date", "notes"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get(document_id)

        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                f"UPDATE documents SET {assignments} WHERE id = ?",
                (*updates.values(), document_id),
            )
        return self.get(document_id)

    def delete_document(self, document_id, remove_file=True):
        """Remove the row, and by default the stored copy too. The user's
        original file, wherever they added it from, is never touched."""

        document = self.get(document_id)
        if document is None:
            return False

        if remove_file:
            stored = self.get_documents_root() / document.stored_filename
            if stored.is_file():
                stored.unlink()

        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        return True

    def file_path(self, document):
        return self.get_documents_root() / document.stored_filename

    # ----- helpers --------------------------------------------------------

    @staticmethod
    def _to_document(row):
        return Document(
            id=row["id"], title=row["title"], category=row["category"],
            stored_filename=row["stored_filename"], original_filename=row["original_filename"],
            issue_date=row["issue_date"], expiry_date=row["expiry_date"], notes=row["notes"],
            created_at=row["created_at"], updated_at=row["updated_at"], updated_by=row["updated_by"],
        )
