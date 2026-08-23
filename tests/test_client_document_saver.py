"""Tests for filing generated documents into a customer's Paperwork
folder - scoped with Minette 2026-08-12 to replace the Save As dialog
that fronted every Quote / Pro-Forma / Tax Invoice / Statement.

Her confirmed decisions, each pinned by a test below:
  - flat in Paperwork, no per-type or per-year subfolders
  - an unnumbered draft overwrites a single Draft_Quote.pdf
  - a locked file says so and offers Retry, never silently relocating
"""

import tempfile
from pathlib import Path

import pytest

from core.client_document_saver import (
    PAPERWORK_SUBFOLDER,
    ClientDocumentSaver,
    safe_filename,
    write_with_retry,
)


class FakeCustomer:
    def __init__(self, name="TAKRAF South Africa", customer_number="TAK-001"):
        self.name = name
        self.customer_number = customer_number


class FakeClientFolders:
    """Stands in for ClientFolderService without touching the real
    clients root or the database."""

    def __init__(self, root):
        self.root = Path(root)

    def ensure_client_folder(self, customer):
        if not customer.customer_number:
            return None
        folder = self.root / f"{customer.name} ({customer.customer_number})"
        for sub in ("Paperwork", "Images", "Site Visit", "Returned Documents"):
            (folder / sub).mkdir(parents=True, exist_ok=True)
        return folder


@pytest.fixture
def saver():
    with tempfile.TemporaryDirectory() as root:
        yield ClientDocumentSaver(client_folder_service=FakeClientFolders(root))


# ------------------------------------------------------------------
# Where documents land
# ------------------------------------------------------------------

def test_document_lands_in_the_customers_paperwork_folder(saver):
    path = saver.paperwork_path(FakeCustomer(), "Q_26-001.pdf")

    assert path.parent.name == PAPERWORK_SUBFOLDER
    assert path.parent.parent.name == "TAKRAF South Africa (TAK-001)"
    assert path.name == "Q_26-001.pdf"


def test_paperwork_folder_is_flat(saver):
    """Her call: no per-type or per-year subfolders. All four document
    types sit side by side so a client's paperwork groups by name."""

    names = ["Q_26-001.pdf", "PF_26-001.pdf", "I_26-001.pdf", "STA_26-001.pdf"]
    parents = {saver.paperwork_path(FakeCustomer(), name).parent for name in names}

    assert len(parents) == 1


def test_paperwork_folder_is_created(saver):
    path = saver.paperwork_path(FakeCustomer(), "Q_26-001.pdf")

    assert path.parent.is_dir()


def test_customer_without_a_number_returns_none(saver):
    """Numbering happens on first save, so there is no folder yet -
    the caller falls back to asking rather than inventing a location."""

    assert saver.paperwork_path(FakeCustomer(customer_number=""), "Q.pdf") is None


def test_missing_customer_returns_none(saver):
    assert saver.paperwork_path(None, "Q.pdf") is None


def test_two_customers_get_separate_folders(saver):
    a = saver.paperwork_path(FakeCustomer("TAKRAF South Africa", "TAK-001"), "Q_26-001.pdf")
    b = saver.paperwork_path(FakeCustomer("Cavaleros Holdings", "CAV-001"), "Q_26-001.pdf")

    assert a != b


# ------------------------------------------------------------------
# Filenames
# ------------------------------------------------------------------

def test_a_revision_does_not_overwrite_the_original(saver):
    """format_quote_number yields "Q_26/001 (Rev 2)", which the call
    site turns into Q_26-001_Rev_2 - a quote she has already sent must
    never be replaced by its revision."""

    original = saver.paperwork_path(FakeCustomer(), "Q_26-001.pdf")
    revision = saver.paperwork_path(FakeCustomer(), "Q_26-001_Rev_2.pdf")

    assert original != revision


def test_regenerating_the_same_document_reuses_one_file(saver):
    """The document number identifies the document; regenerating it is
    a correction, not a second document."""

    first = saver.paperwork_path(FakeCustomer(), "I_26-001.pdf")
    second = saver.paperwork_path(FakeCustomer(), "I_26-001.pdf")

    assert first == second


def test_drafts_share_one_filename(saver):
    """Her call: a draft overwrites the previous draft rather than
    accumulating one file per attempt."""

    first = saver.paperwork_path(FakeCustomer(), "Draft_Quote.pdf")
    second = saver.paperwork_path(FakeCustomer(), "Draft_Quote.pdf")

    assert first == second


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('PO 12/34.pdf', "PO 12-34.pdf"),
        ('Q<>:"|?*.pdf', "Q-------.pdf"),
        ("  spaced.pdf  ", "spaced.pdf"),
    ],
)
def test_safe_filename_strips_characters_windows_forbids(raw, expected):
    assert safe_filename(raw) == expected


def test_safe_filename_never_returns_empty():
    """Whitespace-only and dot-only names would leave nothing to write
    to; anything that still has characters keeps them."""

    assert safe_filename("   ") == "Document"
    assert safe_filename("...") == "Document"
    assert safe_filename("///") == "---"


def test_a_forbidden_character_cannot_escape_the_paperwork_folder(saver):
    """A document number carrying a slash must not be able to write
    outside the customer's own folder."""

    path = saver.paperwork_path(FakeCustomer(), "../../escaped.pdf")

    assert path.parent.name == PAPERWORK_SUBFOLDER


# ------------------------------------------------------------------
# Locked files - the case auto-saving makes far more likely
# ------------------------------------------------------------------

def test_write_succeeds_first_time():
    written = []
    result = write_with_retry(written.append, Path("x.pdf"), on_locked=lambda _p: False)

    assert result == Path("x.pdf")
    assert written == ["x.pdf"]


def test_locked_file_is_retried_and_then_succeeds():
    attempts = []

    def build(path):
        attempts.append(path)
        if len(attempts) < 3:
            raise PermissionError(13, "being used by another process")

    result = write_with_retry(build, Path("Q_26-001.pdf"), on_locked=lambda _p: True)

    assert result == Path("Q_26-001.pdf")
    assert len(attempts) == 3


def test_declining_the_retry_gives_up_without_saving_elsewhere():
    """She chose "tell me plainly and offer Retry" over falling back to
    Save As - cancelling must not quietly write somewhere else."""

    def build(_path):
        raise PermissionError(13, "being used by another process")

    result = write_with_retry(build, Path("Q_26-001.pdf"), on_locked=lambda _p: False)

    assert result is None


def test_on_locked_is_told_which_file_is_blocked():
    seen = []

    def build(_path):
        raise PermissionError(13, "locked")

    def on_locked(path):
        seen.append(path)
        return False

    write_with_retry(build, Path("Paperwork/I_26-001.pdf"), on_locked=on_locked)

    assert seen == [Path("Paperwork/I_26-001.pdf")]


def test_other_errors_are_not_swallowed_as_locking():
    """A genuine failure must reach the caller's error handling rather
    than looping forever on a Retry prompt."""

    def build(_path):
        raise ValueError("reportlab blew up")

    with pytest.raises(ValueError):
        write_with_retry(build, Path("x.pdf"), on_locked=lambda _p: True)


def test_write_with_retry_really_creates_the_file(saver):
    path = saver.paperwork_path(FakeCustomer(), "Q_26-001.pdf")

    write_with_retry(lambda p: Path(p).write_bytes(b"%PDF-1.4"), path, on_locked=lambda _p: False)

    assert path.is_file()
    assert path.read_bytes() == b"%PDF-1.4"
