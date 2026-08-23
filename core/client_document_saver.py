# ==========================================================
# FC Hub - Client Document Saver
# ----------------------------------------------------------
# Purpose:
# File generated customer documents (Quote / Pro-Forma / Tax
# Invoice / Statement) straight into that customer's own
# "Paperwork" folder instead of asking where to save every
# single time. Scoped with Minette 2026-08-12 - her biggest
# annoyance when quoting.
#
# Confirmed decisions:
#   - Flat in Paperwork, no per-type or per-year subfolders.
#   - Drafts (no number yet) overwrite a single Draft_Quote.pdf.
#   - A locked file (PDF open in a viewer) tells her plainly and
#     offers Retry - it never silently saves somewhere else.
#
# Deliberately keeps the retry loop free of any Tk import: the
# caller passes an on_locked callback, so the whole thing is
# testable without a display.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import re

from core.client_folder_service import ClientFolderService

PAPERWORK_SUBFOLDER = "Paperwork"

# Characters Windows forbids in a filename. The call sites already
# turn "Q_26/001 (Rev 2)" into "Q_26-001_Rev_2"; this is the safety
# net for anything that slips through (a customer-supplied PO number
# in a document number, say).
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')


def safe_filename(name):
    """Filesystem-safe version of name, never empty."""

    cleaned = _INVALID_CHARS.sub("-", name).strip().rstrip(". ")
    return cleaned or "Document"


class ClientDocumentSaver:

    def __init__(self, client_folder_service=None):

        self.client_folders = client_folder_service or ClientFolderService()

    # --------------------------------------------------

    def paperwork_path(self, customer, filename):
        """Where this document should be filed, or None if the customer
        has no folder yet.

        Returns None (rather than raising) for a customer with no
        customer_number - numbering happens on first save, so there is
        no folder to file into yet and the caller should fall back to
        asking. Mirrors ClientFolderService.ensure_client_folder's own
        contract."""

        if customer is None:
            return None

        client_folder = self.client_folders.ensure_client_folder(customer)
        if client_folder is None:
            return None

        paperwork = client_folder / PAPERWORK_SUBFOLDER
        paperwork.mkdir(parents=True, exist_ok=True)
        return paperwork / safe_filename(filename)


# --------------------------------------------------


def write_with_retry(build, path, on_locked):
    """Run build(path), re-offering it while the target file is locked.

    Windows refuses to overwrite a PDF that is open in Adobe/Edge,
    which auto-saving makes far more likely than the old Save As flow
    did - the same filename gets reused every time she regenerates a
    document. on_locked(path) is asked whether to retry; returning
    False gives up and returns None. Any other error propagates to the
    caller's existing error handling."""

    while True:
        try:
            build(str(path))
            return path
        except PermissionError:
            if not on_locked(path):
                return None
