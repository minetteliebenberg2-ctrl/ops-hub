"""Filesystem services for safe, preview-based batch renaming.

Scanning is recursive because the original FC_Utilities scanner used os.walk.
Only files below the selected folder are considered; directories are never
rename candidates.
"""

from dataclasses import dataclass, field
import ctypes
import os
from pathlib import Path


INVALID_FILENAME_CHARS = set('<>:"/\\|?*')
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4


@dataclass(frozen=True)
class SkippedFile:
    path: Path
    reason: str


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: Path | None = None
    blocking: bool = True


@dataclass(frozen=True)
class PreviewItem:
    source: Path
    destination: Path
    original_name: str
    proposed_name: str
    status: str
    details: str = ""


@dataclass
class ScanResult:
    folder: Path
    files: list[Path] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class RenamePreview:
    folder: Path | None
    prefix: str
    items: list[PreviewItem] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    source_paths: tuple[Path, ...] = ()
    destination_paths: tuple[Path, ...] = ()

    @property
    def valid(self):
        return bool(self.folder and self.items) and not any(issue.blocking for issue in self.issues) and all(item.status == "Ready" for item in self.items)


@dataclass
class RenameExecutionResult:
    attempted_count: int = 0
    renamed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    renamed_files: list[tuple[Path, Path]] = field(default_factory=list)
    failed_file: tuple[Path, Path] | None = None
    not_processed: list[tuple[Path, Path]] = field(default_factory=list)
    skipped_files: list[SkippedFile] = field(default_factory=list)
    error_details: str = ""
    validation_issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def complete_success(self):
        return self.renamed_count > 0 and not self.failed_count and not self.validation_issues


def _normal_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _windows_attributes(path: Path) -> int:
    if os.name != "nt":
        return 0
    try:
        return int(ctypes.windll.kernel32.GetFileAttributesW(str(path)))
    except (AttributeError, OSError):
        return 0


def _is_hidden_or_system(path: Path) -> str | None:
    if path.name.startswith("."):
        return "hidden file"
    attributes = _windows_attributes(path)
    if attributes == -1:
        return "file attributes unavailable"
    if attributes & FILE_ATTRIBUTE_SYSTEM:
        return "Windows system file"
    if attributes & FILE_ATTRIBUTE_HIDDEN:
        return "hidden file"
    return None


def _is_modifiable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.W_OK)


def _destination_exists_windows(path: Path) -> bool:
    if path.exists():
        return True
    try:
        return any(item.name.casefold() == path.name.casefold() for item in path.parent.iterdir())
    except OSError:
        return False


def scan_folder(folder: str | Path) -> ScanResult:
    selected = Path(folder) if folder else Path()
    result = ScanResult(selected)
    if not folder:
        result.issues.append(ValidationIssue("no_folder", "Select a folder before scanning."))
        return result
    if not selected.exists():
        result.issues.append(ValidationIssue("invalid_folder", "The selected folder does not exist.", selected))
        return result
    if not selected.is_dir():
        result.issues.append(ValidationIssue("invalid_folder", "The selected path is not a folder.", selected))
        return result
    if not os.access(selected, os.R_OK | os.X_OK):
        result.issues.append(ValidationIssue("inaccessible_folder", "The selected folder cannot be accessed.", selected))
        return result
    try:
        for root, directories, filenames in os.walk(selected, topdown=True, followlinks=False):
            directories.sort(key=str.casefold)
            filenames.sort(key=str.casefold)
            for filename in filenames:
                path = Path(root) / filename
                reason = _is_hidden_or_system(path)
                if reason:
                    result.skipped.append(SkippedFile(path, reason))
                elif not _is_modifiable(path):
                    result.skipped.append(SkippedFile(path, "file is not modifiable by the current user"))
                else:
                    result.files.append(path)
    except OSError as error:
        result.issues.append(ValidationIssue("scan_error", f"The folder could not be scanned: {error}", selected))
    result.files.sort(key=_normal_key)
    result.skipped.sort(key=lambda item: _normal_key(item.path))
    return result


def _validate_windows_filename(filename: str) -> str | None:
    if not filename:
        return "the proposed filename is empty"
    if any(character in INVALID_FILENAME_CHARS or ord(character) < 32 for character in filename):
        return "the proposed filename contains invalid Windows filename characters"
    if filename.endswith((" ", ".")):
        return "Windows filenames cannot end with a space or period"
    stem = filename.rsplit(".", 1)[0].upper()
    if stem in WINDOWS_RESERVED_NAMES:
        return "the proposed filename uses a reserved Windows device name"
    return None


def build_preview(folder: str | Path, prefix: str) -> RenamePreview:
    scan = scan_folder(folder)
    selected = scan.folder if scan.folder else None
    preview = RenamePreview(selected, prefix, skipped=scan.skipped, issues=list(scan.issues))
    if not prefix or not prefix.strip():
        preview.issues.append(ValidationIssue("empty_prefix", "Enter a filename prefix before generating a preview."))
    if not scan.files:
        preview.issues.append(ValidationIssue("empty_batch", "No eligible files were found to rename.", selected))
    if any(issue.blocking for issue in scan.issues):
        return preview
    proposed_keys: dict[str, Path] = {}
    for source in scan.files:
        proposed_name = f"{prefix}{source.name}"
        destination = source.with_name(proposed_name)
        item_issues: list[str] = []
        filename_error = _validate_windows_filename(proposed_name)
        if filename_error:
            item_issues.append(filename_error)
            preview.issues.append(ValidationIssue("invalid_filename", filename_error, source))
        if proposed_name == source.name:
            item_issues.append("the proposed name is identical to the original name")
            preview.issues.append(ValidationIssue("unchanged_name", item_issues[-1], source))
        destination_key = _normal_key(destination)
        if destination_key in proposed_keys:
            item_issues.append("duplicate proposed destination in this batch")
            preview.issues.append(ValidationIssue("duplicate_destination", item_issues[-1], destination))
        else:
            proposed_keys[destination_key] = source
        if _destination_exists_windows(destination) and destination_key != _normal_key(source):
            item_issues.append("destination already exists or collides case-insensitively")
            preview.issues.append(ValidationIssue("destination_exists", item_issues[-1], destination))
        status = "Ready" if not item_issues else "Blocked"
        preview.items.append(PreviewItem(source, destination, source.name, proposed_name, status, "; ".join(item_issues)))
    preview.source_paths = tuple(item.source for item in preview.items)
    preview.destination_paths = tuple(item.destination for item in preview.items)
    if not preview.items:
        preview.issues.append(ValidationIssue("empty_batch", "No eligible files were found to rename.", selected))
    return preview


def validate_preview(preview: RenamePreview, folder: str | Path, prefix: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    selected = Path(folder) if folder else Path()
    if preview.folder is None or _normal_key(preview.folder) != _normal_key(selected):
        issues.append(ValidationIssue("stale_folder", "The selected folder changed after the preview was generated.", selected))
    if preview.prefix != prefix:
        issues.append(ValidationIssue("stale_prefix", "The filename prefix changed after the preview was generated."))
    current = scan_folder(selected)
    if current.issues:
        issues.extend(current.issues)
    current_sources = tuple(current.files)
    if tuple(_normal_key(path) for path in current_sources) != tuple(_normal_key(path) for path in preview.source_paths):
        issues.append(ValidationIssue("stale_files", "The eligible file set changed after the preview was generated.", selected))
    current_destinations = {_normal_key(item.destination) for item in preview.items}
    for item in preview.items:
        if not item.source.exists():
            issues.append(ValidationIssue("missing_source", "A previewed source file no longer exists.", item.source))
        elif not _is_modifiable(item.source):
            issues.append(ValidationIssue("source_unmodifiable", "A previewed source file is no longer modifiable.", item.source))
        if _destination_exists_windows(item.destination) and _normal_key(item.destination) != _normal_key(item.source):
            issues.append(ValidationIssue("destination_appeared", "A previewed destination now exists or collides case-insensitively.", item.destination))
        if _normal_key(item.destination) not in current_destinations:
            issues.append(ValidationIssue("destination_changed", "A previewed destination changed.", item.destination))
    return issues


def execute_rename(preview: RenamePreview, folder: str | Path, prefix: str) -> RenameExecutionResult:
    result = RenameExecutionResult(skipped_count=len(preview.skipped), skipped_files=list(preview.skipped))
    if not preview.valid:
        result.validation_issues = list(preview.issues) or [ValidationIssue("invalid_preview", "Generate a valid preview before renaming.")]
        return result
    integrity_issues = validate_preview(preview, folder, prefix)
    if integrity_issues:
        result.validation_issues = integrity_issues
        return result
    for index, item in enumerate(preview.items):
        result.attempted_count += 1
        try:
            item.source.rename(item.destination)
            result.renamed_count += 1
            result.renamed_files.append((item.source, item.destination))
        except OSError as error:
            result.failed_count = 1
            result.failed_file = (item.source, item.destination)
            result.error_details = f"{type(error).__name__}: {error}"
            result.not_processed = [(remaining.source, remaining.destination) for remaining in preview.items[index + 1:]]
            break
    return result
