# ==========================================================
# FC Hub - Client Folder Service
# ----------------------------------------------------------
# Purpose:
# One real folder per customer on disk - Paperwork/Images/Site
# Visit/Returned Documents - auto-created wherever a customer is
# really saved. Mapped out with Minette 2026-08-07 as the foundation
# for Site Visit.
#
# Deliberately mirrors modules/documents/services.py's
# DocumentsRepository pattern exactly: its own direct sqlite3
# connection (not core.database's shared connection) and a
# configurable root stored on business_settings, so the location can
# be repointed (e.g. at OneDrive) without rewriting anything. Kept
# decoupled from CRMService's constructor-default chain on purpose -
# folder creation is an explicit call at each real save site, not a
# hidden side effect of "save the customer" itself, so the dozens of
# tests that build throwaway customers never touch the real
# filesystem.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from core.app_paths import get_project_root
from core.database import DATABASE_PATH

DEFAULT_CLIENTS_DIRNAME = "FC Hub - Clients"
SUBFOLDERS = ("Paperwork", "Images", "Site Visit", "Returned Documents")

# Characters Windows forbids in file/folder names.
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')


class ClientFolderService:

    def __init__(self, database_path=None):

        self.database_path = database_path or DATABASE_PATH

    # --------------------------------------------------

    def _connect(self):

        connection = sqlite3.connect(str(self.database_path))
        connection.row_factory = sqlite3.Row
        return connection

    # --------------------------------------------------

    def get_clients_root(self):
        """Where client folders live. Configurable via business_settings
        (e.g. to point at OneDrive); defaults to a folder inside the
        project, same convention as documents_root."""

        configured = ""
        with closing(self._connect()) as connection, connection:
            try:
                row = connection.execute(
                    "SELECT clients_root FROM business_settings WHERE id = 'business'"
                ).fetchone()
                configured = (row["clients_root"] if row else "") or ""
            except sqlite3.OperationalError:
                # Pre-v0025 database - fall through to the default.
                configured = ""

        root = Path(configured) if configured.strip() else get_project_root() / DEFAULT_CLIENTS_DIRNAME
        root.mkdir(parents=True, exist_ok=True)
        return root

    # --------------------------------------------------

    def set_clients_root(self, path):

        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE business_settings SET clients_root = ?, updated_at = ? WHERE id = 'business'",
                (str(path), datetime.now().isoformat(timespec="seconds")),
            )

    # --------------------------------------------------

    def folder_name_for(self, customer):
        """Sanitized, filesystem-safe, unique folder name - the
        customer number suffix guarantees uniqueness even when two
        customers share a name (e.g. two different "Cavaleros"-style
        contacts), and matches the number she already sees everywhere
        else in the app."""

        safe_name = _INVALID_CHARS.sub("", customer.name).strip().rstrip(". ")
        if not safe_name:
            safe_name = "Unnamed Customer"
        return f"{safe_name} ({customer.customer_number})" if customer.customer_number else safe_name

    # --------------------------------------------------

    def ensure_client_folder(self, customer):
        """Create (if missing) this customer's folder and its
        subfolders. Idempotent and safe to call on every save - never
        touches or removes anything already there. Returns None for a
        customer with no customer_number yet (numbering happens on
        first save; nothing meaningful to name a folder yet)."""

        if not customer.customer_number:
            return None

        client_folder = self.get_clients_root() / self.folder_name_for(customer)
        for subfolder in SUBFOLDERS:
            (client_folder / subfolder).mkdir(parents=True, exist_ok=True)
        return client_folder
