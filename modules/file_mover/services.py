"""Safe, testable filesystem services for the FC Hub File Mover."""

from __future__ import annotations

from dataclasses import dataclass, field
import csv
import hashlib
import logging
import os
from pathlib import Path
import shutil
import threading
import tempfile
import time
from typing import Callable


LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[["MoveProgress"], None]

PENDING = "Pending"
MISSING = "Missing"
EXISTS = "Exists"
MOVED = "Moved"
FAILED = "Failed"


class MoveValidationError(ValueError):
    """Raised when a source/destination relationship is unsafe."""


@dataclass
class FileMovePreview:
    source: Path
    destination: Path
    status: str = PENDING
    error: str = ""
    size: int = 0
    modified_ns: int = 0
    sha256: str = ""


@dataclass
class MovePreview:
    source_folder: Path
    destination_folder: Path
    entries: list[FileMovePreview] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def valid(self) -> bool:
        return bool(self.entries) and not self.blocking_issues and not self.cancelled


@dataclass(frozen=True)
class MoveProgress:
    phase: str
    processed: int
    total: int
    current_path: Path | None = None
    status: str = ""


@dataclass(frozen=True)
class MoveBatchSummary:
    entries: tuple[FileMovePreview, ...]
    moved: int
    skipped: int
    failed: int
    elapsed: float
    cancelled: bool = False
    issues: tuple[str, ...] = ()


def _normalise(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _key(path: str | Path) -> str:
    """Return a Windows-safe, case-insensitive path identity."""

    return os.path.normcase(os.path.normpath(str(_normalise(path))))


def _same_file(left: Path, right: Path) -> bool:
    if _key(left) == _key(right):
        return True
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except (OSError, ValueError):
        return False


def _inside(child: Path, parent: Path) -> bool:
    """Use path components, never string-prefix comparisons."""

    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_reparse_point(entry: os.DirEntry) -> bool:
    try:
        attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(attributes & 0x400)
    except OSError:
        return True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_relationship(source_folder: Path, destination_folder: Path) -> list[str]:
    source = _normalise(source_folder)
    destination = _normalise(destination_folder)
    issues: list[str] = []
    if _key(source) == _key(destination):
        issues.append("The destination folder cannot be the same as the source folder.")
    elif _inside(destination, source):
        issues.append("The destination folder cannot be inside the source folder.")
    return issues


def _scan_files(
    folder: Path,
    *,
    cancel_event: threading.Event | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[Path], list[str], bool]:
    files: list[Path] = []
    issues: list[str] = []
    visited: set[str] = set()
    stack = [folder]
    while stack:
        if cancel_event and cancel_event.is_set():
            return files, issues, True
        current = stack.pop()
        identity = _key(current)
        if identity in visited:
            continue
        visited.add(identity)
        try:
            with os.scandir(current) as iterator:
                entries = sorted(iterator, key=lambda item: item.name.casefold())
        except OSError as error:
            issues.append(f"{current}: could not scan directory ({error})")
            continue
        directories: list[Path] = []
        for entry in entries:
            if cancel_event and cancel_event.is_set():
                return files, issues, True
            path = Path(entry.path)
            try:
                if entry.is_dir(follow_symlinks=False):
                    if not entry.is_symlink() and not _is_reparse_point(entry):
                        directories.append(path)
                elif entry.is_file(follow_symlinks=False) and not entry.is_symlink() and not _is_reparse_point(entry):
                    files.append(path)
                    if progress_callback:
                        progress_callback(MoveProgress("preview", len(files), 0, path, "Scanning"))
            except OSError as error:
                issues.append(f"{path}: could not inspect entry ({error})")
        stack.extend(reversed(directories))
    files.sort(key=_key)
    return files, issues, False


def build_preview(
    source_folder: str | Path,
    destination_folder: str | Path,
    *,
    cancel_event: threading.Event | None = None,
    progress_callback: ProgressCallback | None = None,
) -> MovePreview:
    """Scan one source folder and build a deterministic flattened preview."""

    source = _normalise(source_folder)
    destination = _normalise(destination_folder)
    issues: list[str] = []
    if not source.is_dir():
        issues.append("Choose a valid source folder.")
        return MovePreview(source, destination, issues=issues, blocking_issues=list(issues))
    if not destination.is_dir():
        issues.append("Choose an existing destination folder.")
        return MovePreview(source, destination, issues=issues, blocking_issues=list(issues))
    relationship_issues = _validate_relationship(source, destination)
    issues.extend(relationship_issues)
    if relationship_issues:
        return MovePreview(source, destination, issues=issues, blocking_issues=list(relationship_issues))
    files, scan_issues, cancelled = _scan_files(
        source,
        cancel_event=cancel_event,
        progress_callback=progress_callback,
    )
    issues.extend(scan_issues)
    if cancelled:
        issues.append("Preview cancelled before scanning completed.")
    entries: list[FileMovePreview] = []
    for path in files:
        try:
            stat = path.stat()
            entries.append(FileMovePreview(path, destination / path.name, size=stat.st_size, modified_ns=stat.st_mtime_ns))
        except OSError as error:
            entries.append(FileMovePreview(path, destination / path.name, status=FAILED, error=f"Source could not be inspected: {error}"))
    blocking_issues: list[str] = []
    if not os.access(destination, os.W_OK):
        blocking_issues.append("The destination folder is not writable.")
    try:
        required_bytes = sum(entry.size for entry in entries if entry.status == PENDING)
        if shutil.disk_usage(destination).free < required_bytes:
            blocking_issues.append("The destination does not have enough free disk space.")
    except OSError as error:
        blocking_issues.append(f"Destination storage could not be checked: {error}")
    issues.extend(issue for issue in blocking_issues if issue not in issues)
    return MovePreview(source, destination, entries, issues, blocking_issues, cancelled)


def _validate_entry(preview: MovePreview, entry: FileMovePreview) -> str | None:
    source = _normalise(entry.source)
    destination_folder = _normalise(preview.destination_folder)
    expected_destination = destination_folder / source.name
    if _key(entry.destination) != _key(expected_destination):
        return "The preview destination changed and is no longer safe."
    if _same_file(source, entry.destination):
        return "Source and destination resolve to the same file."
    if not source.exists():
        return "Source file is missing."
    if not source.is_file():
        return "Source path is no longer a regular file."
    if not destination_folder.is_dir():
        return "Destination folder is no longer available."
    if _inside(destination_folder, preview.source_folder):
        return "Destination folder is inside the source folder."
    try:
        current = source.stat()
    except OSError as error:
        return f"Source could not be inspected: {error}"
    if current.st_size != entry.size or current.st_mtime_ns != entry.modified_ns:
        return "Source file changed after the preview was created."
    if entry.sha256:
        try:
            if _sha256_file(source) != entry.sha256:
                return "Source file content changed after the preview was created."
        except OSError as error:
            return f"Source could not be read: {error}"
    if entry.destination.exists():
        return "Destination file already exists."
    return None


def revalidate_preview(preview: MovePreview) -> None:
    """Revalidate every pending entry immediately before execution."""

    relationship_issues = _validate_relationship(preview.source_folder, preview.destination_folder)
    if relationship_issues:
        preview.issues.extend(issue for issue in relationship_issues if issue not in preview.issues)
        preview.blocking_issues.extend(issue for issue in relationship_issues if issue not in preview.blocking_issues)
    destination_issues: list[str] = []
    if not preview.destination_folder.is_dir():
        destination_issues.append("Destination folder is no longer available.")
    elif not os.access(preview.destination_folder, os.W_OK):
        destination_issues.append("The destination folder is not writable.")
    else:
        try:
            pending_size = sum(entry.size for entry in preview.entries if entry.status == PENDING)
            if shutil.disk_usage(preview.destination_folder).free < pending_size:
                destination_issues.append("The destination does not have enough free disk space.")
        except OSError as error:
            destination_issues.append(f"Destination storage could not be checked: {error}")
    if destination_issues:
        preview.issues.extend(issue for issue in destination_issues if issue not in preview.issues)
        preview.blocking_issues.extend(issue for issue in destination_issues if issue not in preview.blocking_issues)
        for entry in preview.entries:
            if entry.status == PENDING:
                entry.status = FAILED
                entry.error = destination_issues[0]
        return
    for entry in preview.entries:
        if entry.status != PENDING:
            continue
        error = relationship_issues[0] if relationship_issues else _validate_entry(preview, entry)
        if error:
            if error == "Source file is missing.":
                entry.status = MISSING
            elif error == "Destination file already exists.":
                entry.status = EXISTS
            else:
                entry.status = FAILED
            entry.error = error
            continue
        try:
            current = entry.source.stat()
            entry.size = current.st_size
            entry.modified_ns = current.st_mtime_ns
            entry.sha256 = _sha256_file(entry.source)
        except FileNotFoundError:
            entry.status = MISSING
            entry.error = "Source file is missing."
        except OSError as error:
            entry.status = FAILED
            entry.error = f"Source could not be read: {error}"


def _same_filesystem(source: Path, destination_folder: Path) -> bool:
    try:
        return source.stat().st_dev == destination_folder.stat().st_dev
    except OSError:
        return source.drive.casefold() == destination_folder.drive.casefold()


def _safe_move(entry: FileMovePreview) -> tuple[bool, str]:
    """Move one validated file without knowingly overwriting a destination."""

    source = entry.source
    destination = entry.destination
    if destination.exists():
        return False, "Destination file already exists."
    if _same_filesystem(source, destination.parent):
        try:
            # On Windows, os.rename refuses an existing destination. The
            # existence check above is repeated as close to the operation as
            # possible to prevent an intentional overwrite.
            if destination.exists():
                return False, "Destination file already exists."
            os.rename(source, destination)
            if not destination.is_file() or destination.stat().st_size != entry.size:
                return False, "Moved destination failed post-move verification."
            return True, ""
        except FileExistsError:
            return False, "Destination file appeared during the move."
        except OSError as error:
            return False, str(error)

    staging: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            return False, "Destination file appeared during the move."
        descriptor, staging_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".fc-hub-incomplete", dir=str(destination.parent)
        )
        os.close(descriptor)
        staging = Path(staging_name)
        shutil.copy2(source, staging)
        if staging.stat().st_size != entry.size or _sha256_file(staging) != entry.sha256:
            raise OSError("Copied destination failed size or SHA-256 verification.")
        if destination.exists():
            raise FileExistsError("Destination file appeared during the move.")
        try:
            # Linking the verified staging file is an atomic no-overwrite
            # publication on the destination filesystem.
            os.link(staging, destination)
            staging.unlink()
        except FileExistsError:
            raise
        except OSError:
            # Windows rename refuses to replace an existing destination and
            # preserves atomic publication when hard links are unavailable.
            if os.name != "nt":
                raise
            os.rename(staging, destination)
        source.unlink()
        return True, ""
    except OSError as error:
        if staging and staging.exists():
            try:
                staging.unlink()
            except OSError:
                LOGGER.warning("Could not remove incomplete destination %s", staging, exc_info=True)
        return False, str(error)


def execute_move(
    preview: MovePreview,
    *,
    confirmed: bool = False,
    cancel_event: threading.Event | None = None,
    progress_callback: ProgressCallback | None = None,
) -> MoveBatchSummary:
    """Execute the complete current preview after confirmation and validation."""

    started = time.perf_counter()
    if not confirmed:
        return MoveBatchSummary(tuple(preview.entries), 0, 0, len(preview.entries), 0.0, issues=("Explicit confirmation is required before moving files.",))
    if not preview.valid:
        return MoveBatchSummary(tuple(preview.entries), 0, 0, len(preview.entries), 0.0, issues=tuple(preview.issues or ["Build a valid preview first."]))
    revalidate_preview(preview)
    pending = [entry for entry in preview.entries if entry.status == PENDING]
    moved = 0
    cancelled = False
    processed_count = 0
    for processed, entry in enumerate(pending, start=1):
        if cancel_event and cancel_event.is_set():
            cancelled = True
            break
        if progress_callback:
            progress_callback(MoveProgress("move", processed - 1, len(pending), entry.source, entry.status))
        if entry.destination.exists():
            entry.status = EXISTS
            entry.error = "Destination file appeared during the move."
            processed_count = processed
            continue
        success, error = _safe_move(entry)
        if success:
            entry.status = MOVED
            entry.error = ""
            moved += 1
        elif error == "Destination file already exists." or "appeared during" in error:
            entry.status = EXISTS
            entry.error = error
        else:
            entry.status = FAILED
            entry.error = error
        processed_count = processed
        if progress_callback:
            progress_callback(MoveProgress("move", processed, len(pending), entry.source, entry.status))
    if progress_callback:
        progress_callback(MoveProgress("move", processed_count, len(pending), None, "Cancelled" if cancelled else "Complete"))
    skipped = sum(entry.status in {MISSING, EXISTS} for entry in preview.entries)
    failed = sum(entry.status == FAILED for entry in preview.entries)
    return MoveBatchSummary(tuple(preview.entries), moved, skipped, failed, round(time.perf_counter() - started, 2), cancelled, tuple(preview.issues))


def export_csv(preview: MovePreview, filename: str | Path) -> Path:
    """Export the original three columns plus optional error details."""

    destination = Path(filename).expanduser()
    with destination.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Source", "Destination", "Status", "Error"])
        for entry in preview.entries:
            writer.writerow([str(entry.source), str(entry.destination), entry.status, entry.error])
    return destination


def format_size(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    size = float(value)
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
    return f"{value} B"


__all__ = [
    "EXISTS",
    "FAILED",
    "FileMovePreview",
    "MISSING",
    "MOVED",
    "MoveBatchSummary",
    "MoveProgress",
    "MovePreview",
    "MoveValidationError",
    "PENDING",
    "build_preview",
    "execute_move",
    "export_csv",
    "format_size",
    "revalidate_preview",
]
