"""Filesystem scanning and safe duplicate-file operations for FC Hub."""

from __future__ import annotations

from dataclasses import dataclass, replace
import csv
import hashlib
import logging
import os
from pathlib import Path
import threading
import time
from typing import Callable, Iterable, Sequence

from send2trash import send2trash


LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[["ScanProgress"], None]


class DuplicateFinderError(ValueError):
    """Raised when a scan or deletion request fails domain validation."""


class ScanCancelled(Exception):
    """Internal signal used to stop hashing promptly."""


@dataclass(frozen=True)
class ScanProgress:
    scanned_files: int
    current_path: Path


@dataclass(frozen=True)
class ScanIssue:
    path: Path
    reason: str


@dataclass(frozen=True)
class FileRecord:
    path: Path
    size: int
    modified_ns: int
    sha256: str


@dataclass(frozen=True)
class DuplicateGroup:
    group_id: str
    sha256: str
    size: int
    files: tuple[FileRecord, ...]

    @property
    def original(self) -> FileRecord:
        return self.files[0]

    @property
    def duplicates(self) -> tuple[FileRecord, ...]:
        return self.files[1:]

    @property
    def recoverable_bytes(self) -> int:
        return max(0, len(self.files) - 1) * self.size


@dataclass(frozen=True)
class DuplicateRow:
    group_id: str
    original: FileRecord
    duplicate: FileRecord

    @property
    def size(self) -> int:
        return self.duplicate.size

    @property
    def sha256(self) -> str:
        return self.duplicate.sha256


@dataclass(frozen=True)
class ScanResult:
    root: Path
    groups: tuple[DuplicateGroup, ...]
    files_scanned: int
    unique_files: int
    skipped_files: int
    issues: tuple[ScanIssue, ...]
    elapsed_seconds: float
    cancelled: bool = False

    @property
    def duplicate_group_count(self) -> int:
        return len(self.groups)

    @property
    def duplicate_file_count(self) -> int:
        return sum(len(group.duplicates) for group in self.groups)

    @property
    def recoverable_bytes(self) -> int:
        return sum(group.recoverable_bytes for group in self.groups)

    @property
    def duplicate_count(self) -> int:
        """Compatibility alias for the number of redundant copies."""

        return self.duplicate_file_count

    def rows(self) -> tuple[DuplicateRow, ...]:
        return tuple(
            DuplicateRow(group.group_id, group.original, duplicate)
            for group in self.groups
            for duplicate in group.duplicates
        )

    def without_paths(self, deleted_paths: Iterable[Path]) -> "ScanResult":
        deleted = {_normalise_path(path) for path in deleted_paths}
        remaining: list[DuplicateGroup] = []
        for group in self.groups:
            files = tuple(file for file in group.files if _normalise_path(file.path) not in deleted)
            if len(files) >= 2:
                remaining.append(replace(group, files=files))
        return replace(self, groups=tuple(remaining))


@dataclass(frozen=True)
class DeletionFailure:
    path: Path
    reason: str


@dataclass(frozen=True)
class DeletionPlan:
    selected: tuple[FileRecord, ...]
    failures: tuple[DeletionFailure, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.failures and bool(self.selected)


@dataclass(frozen=True)
class DeletionResult:
    deleted_paths: tuple[Path, ...]
    failures: tuple[DeletionFailure, ...]
    remaining_result: ScanResult | None = None

    @property
    def success(self) -> bool:
        return bool(self.deleted_paths) and not self.failures

    @property
    def recoverable_bytes(self) -> int:
        return sum(failure.path.stat().st_size for failure in self.failures if failure.path.exists() and failure.path.is_file())

    @property
    def message(self) -> str:
        if self.deleted_paths and self.failures:
            return f"Moved {len(self.deleted_paths)} file(s) to the Recycle Bin; {len(self.failures)} failed."
        if self.deleted_paths:
            return f"Moved {len(self.deleted_paths)} file(s) to the Recycle Bin."
        return "No files were moved to the Recycle Bin."


def _normalise_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def format_size(value: int) -> str:
    """Format bytes for display while retaining raw bytes in all models."""

    if value < 1024:
        return f"{value} B"
    size = float(value)
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
    return f"{value} B"


def sort_duplicate_rows(rows: Sequence[DuplicateRow], column: str, reverse: bool = False) -> list[DuplicateRow]:
    """Sort rows using raw numeric size values rather than formatted text."""

    keys = {
        "group": lambda row: row.group_id.casefold(),
        "original": lambda row: str(row.original.path).casefold(),
        "duplicate": lambda row: str(row.duplicate.path).casefold(),
        "size": lambda row: row.size,
        "hash": lambda row: row.sha256,
    }
    if column not in keys:
        raise DuplicateFinderError(f"Unknown result column: {column}")
    return sorted(rows, key=keys[column], reverse=reverse)


def calculate_hash(path: str | Path, cancel_event: threading.Event | None = None) -> str | None:
    """Calculate SHA-256, returning ``None`` for an unreadable/missing file."""

    try:
        return _hash_file(_normalise_path(path), cancel_event)
    except (OSError, ScanCancelled):
        return None


def _hash_file(path: Path, cancel_event: threading.Event | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            if cancel_event and cancel_event.is_set():
                raise ScanCancelled()
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def scan_folder(
    folder: str | Path,
    *,
    cancel_event: threading.Event | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ScanResult:
    """Recursively scan a folder without following symlinks or reparse loops."""

    root = _normalise_path(folder)
    if not root.is_dir():
        raise DuplicateFinderError("Choose a valid folder before scanning.")
    started = time.perf_counter()
    candidates: list[Path] = []
    issues: list[ScanIssue] = []
    visited: set[str] = set()
    stack = [root]

    while stack:
        if cancel_event and cancel_event.is_set():
            return _result(root, (), len(candidates), 0, issues, started, True)
        current = stack.pop()
        identity = os.path.normcase(str(current))
        if identity in visited:
            continue
        visited.add(identity)
        try:
            with os.scandir(current) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name.casefold())
        except OSError as error:
            issues.append(ScanIssue(current, f"Could not read directory: {error}"))
            continue
        directories: list[Path] = []
        for entry in entries:
            if cancel_event and cancel_event.is_set():
                return _result(root, (), len(candidates), 0, issues, started, True)
            path = Path(entry.path)
            try:
                if entry.is_dir(follow_symlinks=False):
                    if not entry.is_symlink() and not _is_reparse_point(entry):
                        directories.append(path)
                elif entry.is_file(follow_symlinks=False) and not entry.is_symlink() and not _is_reparse_point(entry):
                    candidates.append(path)
                    if progress_callback:
                        progress_callback(ScanProgress(len(candidates), path))
            except OSError as error:
                issues.append(ScanIssue(path, f"Could not inspect entry: {error}"))
        stack.extend(reversed(directories))

    records_by_hash: dict[str, list[FileRecord]] = {}
    for path in sorted(candidates, key=lambda item: str(item).casefold()):
        if cancel_event and cancel_event.is_set():
            return _result(root, (), len(candidates), len(records_by_hash), issues, started, True)
        try:
            before = path.stat()
            digest = _hash_file(path, cancel_event)
            after = path.stat()
            if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
                issues.append(ScanIssue(path, "File changed while it was being scanned."))
                continue
            record = FileRecord(path, after.st_size, after.st_mtime_ns, digest)
            records_by_hash.setdefault(digest, []).append(record)
        except ScanCancelled:
            return _result(root, (), len(candidates), len(records_by_hash), issues, started, True)
        except OSError as error:
            issues.append(ScanIssue(path, f"Could not read file: {error}"))

    groups = tuple(
        DuplicateGroup(
            group_id=digest[:12],
            sha256=digest,
            size=records[0].size,
            files=tuple(sorted(records, key=lambda item: str(item.path).casefold())),
        )
        for digest, records in sorted(records_by_hash.items())
        if len(records) >= 2
    )
    return _result(root, groups, len(candidates), len(records_by_hash), issues, started, False)


def _result(root, groups, files_scanned, unique_files, issues, started, cancelled) -> ScanResult:
    return ScanResult(
        root=root,
        groups=tuple(groups),
        files_scanned=files_scanned,
        unique_files=unique_files,
        skipped_files=len(issues),
        issues=tuple(issues),
        elapsed_seconds=round(time.perf_counter() - started, 2),
        cancelled=cancelled,
    )


def _is_reparse_point(entry: os.DirEntry) -> bool:
    """Skip Windows junctions/reparse points as well as ordinary symlinks."""

    try:
        attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(attributes & 0x400)
    except OSError:
        return True


def prepare_deletion(groups: Sequence[DuplicateGroup], selected_paths: Iterable[str | Path]) -> DeletionPlan:
    """Validate selections and ensure every duplicate group retains a copy."""

    by_path: dict[Path, tuple[DuplicateGroup, FileRecord]] = {}
    for group in groups:
        for record in group.files:
            by_path[_normalise_path(record.path)] = (group, record)
    failures: list[DeletionFailure] = []
    selected_records: list[FileRecord] = []
    selected_by_group: dict[str, set[Path]] = {}
    seen: set[Path] = set()
    for value in selected_paths:
        path = _normalise_path(value)
        if path in seen:
            continue
        seen.add(path)
        match = by_path.get(path)
        if match is None:
            failures.append(DeletionFailure(path, "File was not part of the current scan."))
            continue
        group, record = match
        selected_records.append(record)
        selected_by_group.setdefault(group.group_id, set()).add(path)
    for group in groups:
        selected = selected_by_group.get(group.group_id, set())
        if selected and len(selected) >= len(group.files):
            failures.append(DeletionFailure(group.original.path, "At least one copy must remain in every duplicate group."))
    return DeletionPlan(tuple(selected_records), tuple(failures))


def delete_selected(
    groups: Sequence[DuplicateGroup],
    selected_paths: Iterable[str | Path],
    *,
    confirmed: bool = False,
    recycle_bin=send2trash,
    scan_result: ScanResult | None = None,
) -> DeletionResult:
    """Move selected duplicate copies to the OS Recycle Bin after revalidation."""

    plan = prepare_deletion(groups, selected_paths)
    if not confirmed:
        return DeletionResult((), (DeletionFailure(Path("<selection>"), "Explicit confirmation is required."),), scan_result)
    if not plan.valid:
        return DeletionResult((), plan.failures, scan_result)
    failures = list(plan.failures)
    deleted: list[Path] = []
    records = {_normalise_path(record.path): record for record in plan.selected}
    for path, record in records.items():
        try:
            current = path.stat()
            if not path.is_file():
                raise OSError("Selected path is no longer a file.")
            if current.st_size != record.size or current.st_mtime_ns != record.modified_ns:
                raise OSError("File changed after scanning; scan again before moving it.")
            if _hash_file(path) != record.sha256:
                raise OSError("File content changed after scanning; scan again before moving it.")
            recycle_bin(str(path))
            deleted.append(path)
        except (OSError, RuntimeError, ValueError) as error:
            failures.append(DeletionFailure(path, str(error)))
        except Exception as error:
            LOGGER.exception("Unexpected Recycle Bin failure for %s", path)
            failures.append(DeletionFailure(path, f"Unexpected Recycle Bin failure: {error}"))
    remaining = scan_result.without_paths(deleted) if scan_result else None
    return DeletionResult(tuple(deleted), tuple(failures), remaining)


def export_report(result: ScanResult, filename: str | Path) -> Path:
    """Export duplicate rows and statistics as a UTF-8 CSV report."""

    destination = Path(filename).expanduser()
    if not destination.parent.exists():
        raise DuplicateFinderError("The report destination folder does not exist.")
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Group", "Original File", "Duplicate File", "Size (bytes)", "SHA-256"])
        for row in result.rows():
            writer.writerow([row.group_id, row.original.path, row.duplicate.path, row.size, row.sha256])
        writer.writerow([])
        writer.writerow(["Files scanned", result.files_scanned])
        writer.writerow(["Duplicate groups", result.duplicate_group_count])
        writer.writerow(["Redundant copies", result.duplicate_file_count])
        writer.writerow(["Recoverable bytes", result.recoverable_bytes])
    return destination


__all__ = [
    "DeletionFailure",
    "DeletionPlan",
    "DeletionResult",
    "DuplicateFinderError",
    "DuplicateGroup",
    "DuplicateRow",
    "FileRecord",
    "ScanIssue",
    "ScanProgress",
    "ScanResult",
    "calculate_hash",
    "delete_selected",
    "export_report",
    "format_size",
    "prepare_deletion",
    "scan_folder",
    "sort_duplicate_rows",
]
