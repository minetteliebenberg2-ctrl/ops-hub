"""Safe, reusable backup and restore-preparation services for FC Hub.

The service deliberately keeps filesystem and SQLite work out of the UI.  A
backup is first assembled in a clearly marked staging directory, verified,
and only then atomically renamed to its final timestamped directory.
"""

from __future__ import annotations

import ctypes
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import re
import shutil
import string
import sqlite3
import subprocess
import uuid

from core.app_paths import get_project_root


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = get_project_root()
BACKUP_FORMAT_VERSION = "1.0"
DATABASE_RELATIVE_PATH = Path("database") / "fc_hub.db"
MANIFEST_NAME = "manifest.json"

EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "build",
        "dist",
        "backups",
    }
)
EXCLUDED_SUFFIXES = (".tmp", ".temp", ".part", ".swp", "~")
EXCLUDED_FILE_NAMES = frozenset({".coverage", "coverage.xml"})
SENSITIVE_NAME_PARTS = (
    "password",
    "passwd",
    "credential",
    "secret",
    "token",
    "private_key",
    "private-key",
    "apikey",
    "api_key",
)
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks")


DRIVE_TYPE_NAMES = {
    0: "Unknown",
    1: "No Root Directory",
    2: "Removable",
    3: "Fixed",
    4: "Network",
    5: "CD-ROM",
    6: "RAM Disk",
}
EXTERNAL_DRIVE_TYPES = frozenset({2, 3})  # Removable and Fixed (external USB disks report as Fixed).


class BackupError(RuntimeError):
    """Raised for a preflight or backup-format error."""


@dataclass(frozen=True)
class ModuleBackupContract:
    """Optional module contribution points for future modules."""

    module_id: str
    data_paths: tuple[str, ...] = ()
    required_files: tuple[str, ...] = ()
    excluded_paths: tuple[str, ...] = ()
    restore_order: int = 100
    compatibility_check: str = ""


@dataclass(frozen=True)
class BackupFileRecord:
    path: str
    size: int
    sha256: str
    sensitive: bool = False
    sensitive_reason: str = ""


@dataclass(frozen=True)
class StorageStatus:
    destination: Path
    available: bool
    writable: bool
    free_bytes: int = 0
    required_bytes: int = 0
    same_physical_drive: bool = False
    warning: str = ""
    error: str = ""


@dataclass(frozen=True)
class ExternalDriveInfo:
    letter: str
    root: Path
    drive_type: str
    label: str
    free_bytes: int
    total_bytes: int

    @property
    def display_name(self) -> str:
        label = self.label or "Removable Disk"
        return f"{self.letter}:\\  ({label}, {self.drive_type}, {_format_bytes(self.free_bytes)} free)"


@dataclass(frozen=True)
class VerificationResult:
    success: bool
    status: str
    message: str
    files_checked: int = 0
    missing_files: tuple[str, ...] = ()
    checksum_mismatches: tuple[str, ...] = ()
    incompatible_reason: str = ""


@dataclass(frozen=True)
class BackupSummary:
    path: Path
    created_at: str
    size: int
    status: str
    verification_status: str
    backup_type: str = "full"


@dataclass(frozen=True)
class RestorePreview:
    valid: bool
    backup_path: Path
    target_root: Path
    message: str
    files: tuple[str, ...] = ()
    overwrites: tuple[str, ...] = ()
    sensitive_files: tuple[str, ...] = ()
    verification: VerificationResult | None = None
    requires_application_closed: bool = True


@dataclass(frozen=True)
class BackupResult:
    success: bool
    message: str
    backup_path: Path | None = None
    manifest_path: Path | None = None
    verification: VerificationResult | None = None


@dataclass(frozen=True)
class RestoreResult:
    success: bool
    message: str
    safety_backup: Path | None = None
    restored_files: tuple[str, ...] = ()


def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def _windows_drive_type(root: str) -> int:
    return int(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)))


def _windows_volume_label(root: str) -> str:
    buffer = ctypes.create_unicode_buffer(261)
    succeeded = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root), buffer, ctypes.sizeof(buffer), None, None, None, None, 0
    )
    return buffer.value.strip() if succeeded else ""


def list_external_drives(exclude_drive_letters: frozenset[str] = frozenset()) -> list[ExternalDriveInfo]:
    """List removable and fixed external drives (e.g. USB disks) other than the excluded drives.

    Uses only the Windows ``kernel32`` API through ``ctypes`` so no extra
    dependency is required. Returns an empty list on any non-Windows
    platform or if drive enumeration is unavailable.
    """

    drives: list[ExternalDriveInfo] = []
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    except (AttributeError, OSError):
        return drives

    for index, letter in enumerate(string.ascii_uppercase):
        if not (bitmask & (1 << index)):
            continue
        if letter in exclude_drive_letters:
            continue
        root = f"{letter}:\\"
        try:
            drive_type = _windows_drive_type(root)
        except (AttributeError, OSError):
            continue
        if drive_type not in EXTERNAL_DRIVE_TYPES:
            continue
        path = Path(root)
        if not path.exists():
            continue
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            continue
        drives.append(
            ExternalDriveInfo(
                letter=letter,
                root=path,
                drive_type=DRIVE_TYPE_NAMES.get(drive_type, "Unknown"),
                label=_windows_volume_label(root),
                free_bytes=usage.free,
                total_bytes=usage.total,
            )
        )
    return drives


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return a streaming SHA-256 digest without loading a file in memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BackupService:
    """Central backup service shared by the Backup module and future modules."""

    def __init__(
        self,
        source_root: str | Path | None = None,
        default_destination: str | Path | None = None,
        retention_days: int = 30,
        retention_count: int = 0,
        application_version: str | None = None,
    ):
        self.source_root = Path(source_root or PROJECT_ROOT).expanduser().resolve()
        self.default_destination = Path(default_destination or self.source_root / "backups").expanduser().resolve()
        self.retention_days = max(0, int(retention_days))
        self.retention_count = max(0, int(retention_count))
        self.application_version = application_version or self._detect_application_version()
        self._module_contracts: dict[str, ModuleBackupContract] = {}
        self.audit_events: list[dict[str, str]] = []

    def register_module_contract(self, contract: ModuleBackupContract) -> None:
        """Register optional metadata without requiring changes in existing modules."""

        if not contract.module_id.strip():
            raise ValueError("A module backup contract requires a module ID.")
        self._module_contracts[contract.module_id] = contract

    def list_external_drives(self) -> list[ExternalDriveInfo]:
        """List candidate external drives, excluding the drive FC Hub runs from."""

        source_letter = self.source_root.drive.rstrip(":\\").upper()
        exclude = frozenset({source_letter}) if source_letter else frozenset()
        return list_external_drives(exclude)

    def inspect_destination(self, destination: str | Path | None = None, required_bytes: int = 0) -> StorageStatus:
        """Check destination reachability, writability, free space, and drive risk."""

        path = self._normalise_path(destination or self.default_destination)
        try:
            self._validate_destination_location(path)
        except BackupError as error:
            return StorageStatus(path, False, False, error=str(error))

        parent = path if path.is_dir() else self._nearest_existing_parent(path)
        if not parent or not parent.is_dir():
            return StorageStatus(path, False, False, error="No existing parent directory is available.")
        try:
            usage = shutil.disk_usage(parent)
            writable = os.access(parent, os.W_OK)
        except OSError as error:
            return StorageStatus(path, False, False, error=str(error))
        warning = ""
        same_drive = self._same_physical_drive(path, self.source_root)
        if same_drive:
            warning = "Destination is on the same physical drive as FC Hub."
        if required_bytes and usage.free < required_bytes:
            warning = (warning + " " if warning else "") + "Insufficient free disk space."
        return StorageStatus(
            destination=path,
            available=True,
            writable=writable,
            free_bytes=usage.free,
            required_bytes=required_bytes,
            same_physical_drive=same_drive,
            warning=warning,
            error="" if writable else "Destination is not writable.",
        )

    def create_backup(self, destination: str | Path | None = None, backup_type: str = "full") -> BackupResult:
        """Create, verify, and atomically publish a complete backup."""

        if backup_type != "full":
            return BackupResult(False, f"Backup type '{backup_type}' is not implemented; only full backups are supported.")
        destination_path = self._normalise_path(destination or self.default_destination)
        staging: Path | None = None
        manifest_path: Path | None = None
        try:
            self._validate_destination_location(destination_path)
            source_files, excluded_paths, estimated_size = self._collect_source_files(destination_path)
            storage = self.inspect_destination(destination_path, estimated_size)
            if not storage.available or not storage.writable:
                raise BackupError(storage.error or "Backup destination is unavailable.")
            if storage.free_bytes < estimated_size:
                raise BackupError("Backup destination does not have sufficient free disk space.")
            destination_path.mkdir(parents=True, exist_ok=True)
            if not os.access(destination_path, os.W_OK):
                raise BackupError("Backup destination is not writable.")
            name = self._unique_backup_name(destination_path)
            final_path = destination_path / name
            staging = destination_path / f".{name}.{uuid.uuid4().hex}.INCOMPLETE"
            staging.mkdir()
            manifest_path = staging / MANIFEST_NAME
            self._audit("backup_started", destination=str(destination_path), backup_type=backup_type)
            manifest = self._base_manifest(backup_type, destination_path)
            manifest.update({"status": "incomplete", "excluded_paths": excluded_paths, "files": []})
            self._write_manifest(manifest_path, manifest)

            records: list[BackupFileRecord] = []
            for source_path in source_files:
                relative = source_path.relative_to(self.source_root)
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target)
                records.append(self._record_for_file(target, relative))

            database_source = self.source_root / DATABASE_RELATIVE_PATH
            database_metadata: dict[str, object] = {"present": False}
            if database_source.is_file():
                database_target = staging / DATABASE_RELATIVE_PATH
                database_target.parent.mkdir(parents=True, exist_ok=True)
                database_metadata = self._snapshot_database(database_source, database_target)
                records.append(self._record_for_file(database_target, DATABASE_RELATIVE_PATH))

            manifest["files"] = [asdict(item) for item in sorted(records, key=lambda item: item.path)]
            manifest["included_files"] = [item.path for item in sorted(records, key=lambda item: item.path)]
            manifest["sensitive_files"] = [item.path for item in records if item.sensitive]
            manifest["total_file_count"] = len(records)
            manifest["total_backup_size"] = sum(item.size for item in records)
            manifest["database"] = database_metadata
            manifest["verification"] = {"status": "pending"}
            self._write_manifest(manifest_path, manifest)

            verification = self._verify_manifest_directory(staging, manifest)
            if not verification.success:
                raise BackupError(verification.message)
            manifest["status"] = "verified"
            manifest["verification"] = {
                "status": "verified",
                "verified_at": self._timestamp(),
                "files_checked": verification.files_checked,
            }
            self._write_manifest(manifest_path, manifest)
            staging.rename(final_path)
            self._audit("backup_completed", backup_path=str(final_path), files=str(len(records)))
            self._audit("verification_completed", backup_path=str(final_path), files=str(verification.files_checked))
            return BackupResult(True, "Backup created and verified.", final_path, final_path / MANIFEST_NAME, verification)
        except Exception as error:
            if staging and staging.is_dir():
                try:
                    failure_manifest = self._read_json(manifest_path) if manifest_path and manifest_path.is_file() else self._base_manifest(backup_type, destination_path)
                    failure_manifest.update(
                        {
                            "status": "incomplete",
                            "error": str(error),
                            "failed_at": self._timestamp(),
                        }
                    )
                    self._write_manifest(staging / MANIFEST_NAME, failure_manifest)
                except OSError:
                    LOGGER.exception("Could not write the incomplete backup marker.")
            self._audit("backup_failed", destination=str(destination_path), error=str(error))
            return BackupResult(False, f"Backup failed: {error}", staging, manifest_path)

    def list_backups(self, destination: str | Path | None = None) -> list[BackupSummary]:
        """List final and clearly-marked incomplete backups without modifying them."""

        root = self._normalise_path(destination or self.default_destination)
        if not root.is_dir():
            return []
        summaries: list[BackupSummary] = []
        for path in root.iterdir():
            if not path.is_dir() or (not path.name.startswith("FC_Hub_Backup_") and not path.name.endswith(".INCOMPLETE")):
                continue
            try:
                manifest = self._read_json(path / MANIFEST_NAME)
            except (OSError, ValueError, json.JSONDecodeError):
                summaries.append(BackupSummary(path, "", self._directory_size(path), "incomplete", "missing_manifest"))
                continue
            verification = manifest.get("verification") or {}
            summaries.append(
                BackupSummary(
                    path=path,
                    created_at=str(manifest.get("created_at", "")),
                    size=int(manifest.get("total_backup_size", self._directory_size(path))),
                    status=str(manifest.get("status", "incomplete")),
                    verification_status=str(verification.get("status", "unknown")),
                    backup_type=str(manifest.get("backup_type", "full")),
                )
            )
        return sorted(summaries, key=lambda item: item.created_at, reverse=True)

    def verify_backup(self, backup_path: str | Path) -> VerificationResult:
        """Verify a backup manifest and every listed file without restoring anything."""

        path = Path(backup_path).expanduser().resolve()
        manifest_path = path / MANIFEST_NAME
        if not path.is_dir() or not manifest_path.is_file():
            return VerificationResult(False, "missing_manifest", "Backup manifest is missing.")
        try:
            manifest = self._read_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return VerificationResult(False, "invalid_manifest", f"Backup manifest is invalid: {error}")
        if manifest.get("backup_format_version") != BACKUP_FORMAT_VERSION:
            reason = f"Unsupported backup format: {manifest.get('backup_format_version', 'unknown')}"
            return VerificationResult(False, "incompatible", reason, incompatible_reason=reason)
        if manifest.get("status") != "verified":
            return VerificationResult(False, "incomplete", "Backup is not marked verified and cannot be restored.")
        result = self._verify_manifest_directory(path, manifest)
        if result.success:
            self._audit("verification_completed", backup_path=str(path), files=str(result.files_checked))
        return result

    def prepare_restore(self, backup_path: str | Path, target_root: str | Path | None = None) -> RestorePreview:
        """Return a complete restore preview; this method never writes to disk."""

        path = Path(backup_path).expanduser().resolve()
        target = self._normalise_path(target_root or self.source_root)
        try:
            self._validate_restore_target(target)
        except BackupError as error:
            return RestorePreview(False, path, target, str(error))
        verification = self.verify_backup(path)
        if not verification.success:
            self._audit("restore_cancelled", backup_path=str(path), reason=verification.message)
            return RestorePreview(False, path, target, verification.message, verification=verification)
        manifest = self._read_json(path / MANIFEST_NAME)
        files: list[str] = []
        overwrites: list[str] = []
        sensitive: list[str] = []
        for item in manifest.get("files", []):
            relative = self._safe_relative(item.get("path", ""))
            destination = target / relative
            value = relative.as_posix()
            files.append(value)
            if destination.exists():
                overwrites.append(value)
            if item.get("sensitive"):
                sensitive.append(value)
        self._audit("restore_prepared", backup_path=str(path), files=str(len(files)))
        return RestorePreview(True, path, target, "Restore preview ready; no files were changed.", tuple(files), tuple(overwrites), tuple(sensitive), verification)

    def restore(
        self,
        backup_path: str | Path,
        target_root: str | Path | None = None,
        *,
        confirmation: bool = False,
        application_closed: bool = False,
        safety_backup_destination: str | Path | None = None,
    ) -> RestoreResult:
        """Perform a guarded full restore when explicitly authorized.

        The method is intentionally not called by the UI.  It requires an
        explicit confirmation, a closed application, a verified source backup,
        and a successful pre-restore safety backup.
        """

        path = Path(backup_path).expanduser().resolve()
        target = self._normalise_path(target_root or self.source_root)
        if not confirmation:
            self._audit("restore_cancelled", backup_path=str(path), reason="confirmation_required")
            return RestoreResult(False, "Explicit restore confirmation is required.")
        if not application_closed:
            self._audit("restore_cancelled", backup_path=str(path), reason="application_open")
            return RestoreResult(False, "FC Hub must be closed before a production restore.")
        try:
            self._validate_restore_target(target)
        except BackupError as error:
            self._audit("restore_cancelled", backup_path=str(path), reason=str(error))
            return RestoreResult(False, str(error))
        verification = self.verify_backup(path)
        if not verification.success:
            self._audit("restore_cancelled", backup_path=str(path), reason=verification.message)
            return RestoreResult(False, verification.message)
        safety = self.create_backup(safety_backup_destination or self.default_destination)
        if not safety.success:
            return RestoreResult(False, f"Pre-restore safety backup failed: {safety.message}")
        manifest = self._read_json(path / MANIFEST_NAME)
        restored: list[str] = []
        try:
            for item in manifest.get("files", []):
                relative = self._safe_relative(item.get("path", ""))
                source = path / relative
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                if relative == DATABASE_RELATIVE_PATH:
                    self._restore_database_snapshot(source, destination)
                else:
                    shutil.copy2(source, destination)
                restored.append(relative.as_posix())
        except Exception as error:
            self._audit("backup_failed", backup_path=str(path), error=f"restore: {error}")
            return RestoreResult(False, f"Restore failed after safety backup: {error}", safety.backup_path, tuple(restored))
        self._audit("restore_completed", backup_path=str(path), files=str(len(restored)))
        return RestoreResult(True, "Restore completed.", safety.backup_path, tuple(restored))

    def cleanup_candidates(self, destination: str | Path | None = None, now: datetime | None = None) -> list[BackupSummary]:
        """Return candidates for review; never deletes anything automatically."""

        summaries = [item for item in self.list_backups(destination) if item.status == "verified" and item.verification_status == "verified"]
        if len(summaries) <= 1:
            self._audit("cleanup_requested", destination=str(destination or self.default_destination), candidates="0")
            return []
        current = now or datetime.now(timezone.utc)
        candidates: list[BackupSummary] = []
        for index, item in enumerate(summaries):
            try:
                created = datetime.fromisoformat(item.created_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            too_old = self.retention_days and (current - created).days >= self.retention_days
            too_many = self.retention_count and index >= self.retention_count
            if too_old or too_many:
                candidates.append(item)
        self._audit("cleanup_requested", destination=str(destination or self.default_destination), candidates=str(len(candidates)))
        return candidates

    def _base_manifest(self, backup_type: str, destination: Path) -> dict[str, object]:
        database = self.source_root / DATABASE_RELATIVE_PATH
        return {
            "backup_format_version": BACKUP_FORMAT_VERSION,
            "backup_type": backup_type,
            "created_at": self._timestamp(),
            "source_repository": str(self.source_root),
            "destination": str(destination),
            "status": "incomplete",
            "included_files": [],
            "excluded_paths": [],
            "files": [],
            "total_file_count": 0,
            "total_backup_size": 0,
            "database": {"present": database.is_file()},
            "production_database_sha256": sha256_file(database) if database.is_file() else "",
            "application": {
                "version": self.application_version,
                "git_commit": self._git_commit(),
                "database_schema_version": self._database_schema_version(database),
                "operating_system": platform.platform(),
                "python_version": platform.python_version(),
            },
            "sensitive_files": [],
            "module_contracts": [asdict(item) for item in sorted(self._module_contracts.values(), key=lambda value: value.module_id)],
            "verification": {"status": "pending"},
        }

    def _collect_source_files(self, destination: Path) -> tuple[list[Path], list[dict[str, str]], int]:
        files: list[Path] = []
        excluded: list[dict[str, str]] = []
        for current, directories, names in os.walk(self.source_root, topdown=True, followlinks=False):
            current_path = Path(current)
            relative_current = current_path.relative_to(self.source_root)
            kept_directories: list[str] = []
            for directory in directories:
                relative = relative_current / directory
                reason = self._directory_exclusion_reason(relative)
                if reason:
                    excluded.append({"path": relative.as_posix(), "reason": reason})
                else:
                    kept_directories.append(directory)
            directories[:] = kept_directories
            for name in names:
                path = current_path / name
                if path.is_symlink() or not path.is_file():
                    continue
                relative = path.relative_to(self.source_root)
                if relative == DATABASE_RELATIVE_PATH or relative.name.lower() in {"fc_hub.db-wal", "fc_hub.db-shm"}:
                    excluded.append({"path": relative.as_posix(), "reason": "live SQLite database handled with sqlite backup API"})
                    continue
                reason = self._file_exclusion_reason(relative)
                if reason:
                    excluded.append({"path": relative.as_posix(), "reason": reason})
                    continue
                files.append(path)
        database = self.source_root / DATABASE_RELATIVE_PATH
        estimated = sum(item.stat().st_size for item in files)
        if database.is_file():
            estimated += database.stat().st_size
        return files, excluded, estimated + 64 * 1024

    def _record_for_file(self, path: Path, relative: Path) -> BackupFileRecord:
        sensitive, reason = self._sensitive_classification(relative)
        return BackupFileRecord(relative.as_posix(), path.stat().st_size, sha256_file(path), sensitive, reason)

    def _verify_manifest_directory(self, root: Path, manifest: dict[str, object]) -> VerificationResult:
        missing: list[str] = []
        mismatches: list[str] = []
        checked = 0
        for item in manifest.get("files", []):
            try:
                relative = self._safe_relative(item.get("path", ""))
            except BackupError as error:
                return VerificationResult(False, "unsafe_manifest", str(error))
            path = root / relative
            if not path.is_file():
                missing.append(relative.as_posix())
                continue
            checked += 1
            expected_size = int(item.get("size", -1))
            expected_hash = str(item.get("sha256", ""))
            if path.stat().st_size != expected_size or sha256_file(path) != expected_hash:
                mismatches.append(relative.as_posix())
        if missing or mismatches:
            detail = []
            if missing:
                detail.append("Missing: " + ", ".join(missing))
            if mismatches:
                detail.append("Checksum mismatch: " + ", ".join(mismatches))
            return VerificationResult(False, "failed", "; ".join(detail), checked, tuple(missing), tuple(mismatches))
        return VerificationResult(True, "verified", "All backup files passed size and SHA-256 verification.", checked)

    def _snapshot_database(self, source: Path, target: Path) -> dict[str, object]:
        source_uri = source.resolve().as_uri() + "?mode=ro"
        source_connection = sqlite3.connect(source_uri, uri=True)
        destination_connection = sqlite3.connect(str(target))
        try:
            source_connection.backup(destination_connection)
            schema_version = source_connection.execute("PRAGMA user_version").fetchone()[0]
        finally:
            destination_connection.close()
            source_connection.close()
        return {
            "present": True,
            "relative_path": DATABASE_RELATIVE_PATH.as_posix(),
            "production_sha256": sha256_file(source),
            "snapshot_sha256": sha256_file(target),
            "schema_version": schema_version,
            "method": "sqlite.Connection.backup",
        }

    @staticmethod
    def _restore_database_snapshot(source: Path, target: Path) -> None:
        source_connection = sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True)
        target_connection = sqlite3.connect(str(target))
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()

    def _validate_destination_location(self, destination: Path) -> None:
        try:
            relative = destination.relative_to(self.source_root)
        except ValueError:
            return
        if not relative.parts or relative.parts[0].casefold() != "backups":
            raise BackupError("Backup destination cannot be inside the source tree except C:\\FC_Hub\\backups.")

    def _validate_restore_target(self, target: Path) -> None:
        try:
            target.relative_to(self.source_root)
        except ValueError as error:
            raise BackupError("Restore target must be inside the FC Hub source directory.") from error

    def _safe_relative(self, value: str) -> Path:
        relative = Path(str(value))
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise BackupError(f"Unsafe relative backup path: {value}")
        return relative

    def _normalise_path(self, path: str | Path) -> Path:
        value = Path(path).expanduser()
        if not value.is_absolute():
            value = self.source_root / value
        return value.resolve()

    @staticmethod
    def _nearest_existing_parent(path: Path) -> Path | None:
        candidate = path
        while candidate != candidate.parent and not candidate.exists():
            candidate = candidate.parent
        return candidate if candidate.exists() else None

    @staticmethod
    def _same_physical_drive(left: Path, right: Path) -> bool:
        return left.drive.casefold() == right.drive.casefold()

    @staticmethod
    def _unique_backup_name(destination: Path) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        base = f"FC_Hub_Backup_{stamp}"
        candidate = destination / base
        counter = 1
        while candidate.exists():
            candidate = destination / f"{base}_{counter:02d}"
            counter += 1
        return candidate.name

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> dict[str, object]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Manifest root must be an object.")
        return value

    @staticmethod
    def _directory_size(path: Path) -> int:
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())

    @staticmethod
    def _directory_exclusion_reason(relative: Path) -> str:
        if relative.name.casefold() in EXCLUDED_DIRECTORY_NAMES:
            return "explicit excluded directory"
        return ""

    @staticmethod
    def _file_exclusion_reason(relative: Path) -> str:
        name = relative.name.casefold()
        if name in EXCLUDED_FILE_NAMES or name.endswith(EXCLUDED_SUFFIXES):
            return "temporary or generated file"
        if name.endswith(".recovery") or name.startswith(("recovery_copy", "recovered_copy")):
            return "generated recovery copy"
        return ""

    @staticmethod
    def _sensitive_classification(relative: Path) -> tuple[bool, str]:
        name = relative.name.casefold()
        if name == ".env" or any(part in name for part in SENSITIVE_NAME_PARTS):
            return True, "filename may contain credentials, tokens, or secrets"
        if name.endswith(SENSITIVE_SUFFIXES):
            return True, "private-key or certificate material"
        if relative.parts and relative.parts[0].casefold() in {"config", "configuration"} and name.endswith((".json", ".yaml", ".yml", ".ini", ".toml")):
            return True, "configuration file may contain credentials or private settings"
        return False, ""

    def _database_schema_version(self, database: Path) -> int | str:
        if not database.is_file():
            return "unknown"
        try:
            connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                return int(connection.execute("PRAGMA user_version").fetchone()[0])
            finally:
                connection.close()
        except sqlite3.Error:
            return "unreadable"

    def _git_commit(self) -> str:
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.source_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return completed.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return "unknown"

    def _detect_application_version(self) -> str:
        launcher = self.source_root / "launcher.py"
        try:
            text = launcher.read_text(encoding="utf-8")
        except OSError:
            return "unknown"
        match = re.search(r"Version:\s*([^\s*]+)", text, flags=re.IGNORECASE)
        return match.group(1) if match else "unknown"

    def _audit(self, event: str, **details: str) -> None:
        payload = {"event": event, "at": self._timestamp(), **details}
        self.audit_events.append(payload)
        LOGGER.info("FC Hub backup event: %s", json.dumps(payload, sort_keys=True))


__all__ = [
    "BACKUP_FORMAT_VERSION",
    "BackupError",
    "BackupFileRecord",
    "BackupResult",
    "BackupService",
    "BackupSummary",
    "DATABASE_RELATIVE_PATH",
    "ExternalDriveInfo",
    "ModuleBackupContract",
    "RestorePreview",
    "RestoreResult",
    "StorageStatus",
    "VerificationResult",
    "list_external_drives",
    "sha256_file",
]
