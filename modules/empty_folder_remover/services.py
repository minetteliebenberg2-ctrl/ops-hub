"""Scanning, Recycle Bin deletion, and CSV export for empty folders."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import time
from typing import Iterable

from send2trash import send2trash


LOGGER = logging.getLogger(__name__)


class EmptyFolderError(ValueError):
    """Raised when an empty-folder operation fails validation."""


@dataclass(frozen=True)
class ScanIssue:
    path: Path
    reason: str


@dataclass(frozen=True)
class ScanResult:
    root: Path
    folders: tuple[Path, ...]
    folders_scanned: int
    empty_folders: int
    skipped_folders: int
    elapsed_seconds: float
    issues: tuple[ScanIssue, ...] = ()


@dataclass(frozen=True)
class DeletionFailure:
    path: Path
    reason: str


@dataclass(frozen=True)
class DeletionResult:
    deleted_paths: tuple[Path, ...]
    failures: tuple[DeletionFailure, ...]

    @property
    def deleted_count(self) -> int:
        return len(self.deleted_paths)

    @property
    def failed_count(self) -> int:
        return len(self.failures)


class EmptyFolderService:
    """Reusable service for all Empty Folder Remover business operations."""

    def scan(self, folder: str | Path) -> ScanResult:
        """Recursively find empty folders using the legacy bottom-up traversal."""

        root = Path(folder).expanduser().resolve(strict=False)
        if not root.is_dir():
            raise EmptyFolderError("Choose a valid folder before scanning.")

        started = time.perf_counter()
        empty_folders: list[Path] = []
        issues: list[ScanIssue] = []
        folders_scanned = 0

        def record_walk_error(error: OSError) -> None:
            path = Path(error.filename) if error.filename else root
            issues.append(ScanIssue(path, str(error)))
            LOGGER.warning("Could not scan folder %s: %s", path, error)

        for current_folder, directories, files in os.walk(
            root,
            topdown=False,
            onerror=record_walk_error,
            followlinks=False,
        ):
            folders_scanned += 1
            if not directories and not files:
                empty_folders.append(Path(current_folder))

        return ScanResult(
            root=root,
            folders=tuple(empty_folders),
            folders_scanned=folders_scanned,
            empty_folders=len(empty_folders),
            skipped_folders=len(issues),
            elapsed_seconds=round(time.perf_counter() - started, 2),
            issues=tuple(issues),
        )

    def delete(
        self,
        folders: Iterable[str | Path],
        *,
        confirmed: bool = False,
        recycle_bin=send2trash,
    ) -> DeletionResult:
        """Move only the explicitly supplied folders to the operating system Recycle Bin."""

        selected: list[Path] = []
        seen: set[Path] = set()
        for folder in folders:
            path = Path(folder).expanduser().resolve(strict=False)
            if path not in seen:
                selected.append(path)
                seen.add(path)

        if not confirmed:
            return DeletionResult(
                (),
                (DeletionFailure(Path("<selection>"), "Explicit confirmation is required."),),
            )

        deleted: list[Path] = []
        failures: list[DeletionFailure] = []
        for path in selected:
            try:
                if not path.is_dir():
                    raise OSError("Selected folder no longer exists or is not a folder.")
                if any(path.iterdir()):
                    raise OSError("Selected folder is no longer empty.")
                recycle_bin(str(path))
                deleted.append(path)
            except (OSError, RuntimeError, ValueError) as error:
                failures.append(DeletionFailure(path, str(error)))
            except Exception as error:
                LOGGER.exception("Unexpected Recycle Bin failure for %s", path)
                failures.append(DeletionFailure(path, f"Unexpected Recycle Bin failure: {error}"))

        return DeletionResult(tuple(deleted), tuple(failures))

    def export_csv(self, folders: Iterable[str | Path], filename: str | Path) -> Path:
        """Export empty-folder paths using the legacy single-column CSV layout."""

        destination = Path(filename).expanduser()
        if not destination.parent.is_dir():
            raise EmptyFolderError("The report destination folder does not exist.")
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Folder"])
            for folder in folders:
                writer.writerow([str(Path(folder))])
        return destination


__all__ = [
    "DeletionFailure",
    "DeletionResult",
    "EmptyFolderError",
    "EmptyFolderService",
    "ScanIssue",
    "ScanResult",
]
