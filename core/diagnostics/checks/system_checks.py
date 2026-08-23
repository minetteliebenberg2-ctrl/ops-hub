"""Safe checks for the FC Hub installation and its services."""

import importlib
import importlib.metadata
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from contextlib import closing

from core.app_paths import get_project_root
from core.diagnostics.models import DiagnosticResult, DiagnosticStatus
from core.diagnostics.registry import DiagnosticRegistry
from core.migrations.runner import MigrationRunner
from framework.module_manager import module_manager
from modules.backup.services import BackupService


PROJECT_ROOT = get_project_root()
FROZEN = getattr(sys, "frozen", False)


class Check:
    description = ""

    def result(self, status, summary, details="", recommendation="No action required.", blocking=False):
        return DiagnosticResult(
            self.check_id, self.category, self.name, status, summary,
            details or summary, recommendation, blocking,
        )


class ProjectStructureCheck(Check):
    check_id = "project.structure"
    category = "Project"
    name = "Project structure"

    def __init__(self, root=PROJECT_ROOT):
        self.root = Path(root)

    def run(self):
        if FROZEN:
            # launcher.py, core, framework, gui, and modules are bundled
            # inside the frozen executable, not present as loose files next
            # to it; only genuine runtime data folders are expected here.
            critical = ["database"]
            optional = ["assets", "exports", "backups"]
        else:
            critical = ["launcher.py", "core", "framework", "gui", "modules", "database"]
            optional = ["assets", "tests", "utilities", "exports", "backups"]
        missing_critical = [item for item in critical if not (self.root / item).exists()]
        missing_optional = [item for item in optional if not (self.root / item).exists()]
        details = f"Project root: {self.root}\nCritical items present: {len(critical) - len(missing_critical)}/{len(critical)}"
        if FROZEN:
            details += "\nRunning from a frozen build; source folders are bundled inside the executable."
        if missing_critical:
            return self.result(DiagnosticStatus.FAIL, "Critical project items are missing.", details + "\nMissing: " + ", ".join(missing_critical), "Restore the missing items from the verified Sprint 18 baseline.", True)
        if missing_optional:
            return self.result(DiagnosticStatus.WARNING, "Core structure is valid; optional folders are missing.", details + "\nOptional missing: " + ", ".join(missing_optional), "Create an optional folder only when its feature requires it.")
        return self.result(DiagnosticStatus.PASS, "Required project files and folders are present.", details)


class PythonEnvironmentCheck(Check):
    check_id = "environment.python"
    category = "Environment"
    name = "Python environment"

    def run(self):
        version = sys.version_info
        supported = version >= (3, 10)
        in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix) or bool(os.environ.get("VIRTUAL_ENV"))
        details = f"Python: {sys.version.split()[0]}\nExecutable: {sys.executable}\nVirtual environment: {'Yes' if in_venv else 'No'}"
        if not supported:
            return self.result(DiagnosticStatus.FAIL, "Python 3.10 or newer is required.", details, "Run FC Hub with a supported Python interpreter.", True)
        status = DiagnosticStatus.PASS if in_venv else DiagnosticStatus.INFO
        summary = "Python is supported." if in_venv else "Python is supported; no virtual environment was detected."
        return self.result(status, summary, details, "Use a virtual environment for an isolated installation." if not in_venv else "No action required.")


class DependencyCheck(Check):
    check_id = "environment.dependencies"
    category = "Environment"
    name = "Required dependencies"

    def __init__(self, root=PROJECT_ROOT):
        self.root = Path(root)

    def run(self):
        if FROZEN:
            return self.result(
                DiagnosticStatus.INFO,
                "Running from a frozen build; dependencies are bundled with the executable.",
                f"Executable: {sys.executable}",
                "No action required.",
            )
        requirements_path = self.root / "requirements.txt"
        if not requirements_path.exists():
            return self.result(
                DiagnosticStatus.FAIL,
                "requirements.txt was not found.",
                f"Expected: {requirements_path}",
                "Restore requirements.txt from the verified baseline.",
                True,
            )
        requirements = []
        for line in requirements_path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                requirements.append(value.split("=")[0].split(">=")[0].strip())
        missing, versions = [], []
        for package in requirements:
            try:
                versions.append(f"{package} {importlib.metadata.version(package)}")
            except importlib.metadata.PackageNotFoundError:
                missing.append(package)
        if missing:
            return self.result(DiagnosticStatus.FAIL, "Required Python dependencies are missing.", "Missing: " + ", ".join(missing), "Install the packages listed in requirements.txt.", True)
        return self.result(DiagnosticStatus.PASS, "Required Python dependencies are available.", "\n".join(versions) or "No third-party requirements are listed.")


class ImportHealthCheck(Check):
    check_id = "application.imports"
    category = "Application"
    name = "Import health"

    def run(self):
        modules = ["framework.module_manager", "core.database", "modules.backup.module", "modules.communications.module", "modules.crm.module", "modules.troubleshooter.module"]
        if not FROZEN:
            # launcher.py is only importable by this bare module name from a
            # source checkout; a frozen build's entry point is not a
            # separately importable "launcher" module.
            modules.append("launcher")
        failures = []
        for module in modules:
            try:
                importlib.import_module(module)
            except Exception as error:
                failures.append(f"{module}: {type(error).__name__}: {error}")
        if failures:
            return self.result(DiagnosticStatus.FAIL, "One or more FC Hub components could not be imported.", "\n".join(failures), "Restore or repair the listed module or its dependency.", True)
        return self.result(DiagnosticStatus.PASS, "Core and feature modules import successfully.", "Checked: " + ", ".join(modules))


class ModuleRegistrationCheck(Check):
    check_id = "application.modules"
    category = "Application"
    name = "Module registration"

    def run(self):
        modules = module_manager.list_modules()
        names = [module.info.name for module in modules]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        invalid = [name or "<unnamed>" for name, module in zip(names, modules) if not name or not callable(getattr(module, "create_window", None))]
        expected = ["communications", "crm", "troubleshooter", "backup"]
        ids = [module.info.module_id for module in modules]
        missing = [module_id for module_id in expected if module_id not in ids]
        details = "Registered: " + (", ".join(f"{module.info.module_id} ({module.info.name})" for module in modules) or "none")
        if duplicates or invalid or missing:
            extra = f"\nMissing: {missing}\nDuplicates: {duplicates}\nInvalid: {invalid}"
            return self.result(DiagnosticStatus.FAIL, "Module registration has errors.", details + extra, "Review module metadata and discovery registration.", True)
        return self.result(DiagnosticStatus.PASS, "All current FC Hub modules are registered once.", details)


class ModuleDiscoveryCheck(Check):
    check_id = "application.module_discovery"
    category = "Application"
    name = "Module discovery report"

    def run(self):
        report = module_manager.report
        details = (
            f"Folders: {', '.join(report.discovered_folders) or 'none'}\n"
            f"Imported: {', '.join(report.imported_modules) or 'none'}\n"
            f"Registered IDs: {', '.join(report.registered_module_ids) or 'none'}\n"
            f"Registered names: {', '.join(report.registered_names) or 'none'}\n"
            f"Disabled IDs: {', '.join(report.disabled_module_ids) or 'none'}\n"
            f"Duplicate IDs: {', '.join(report.duplicate_ids) or 'none'}\n"
            f"Duplicate names: {', '.join(report.duplicate_names) or 'none'}\n"
            f"Invalid classes: {', '.join(report.invalid_module_classes) or 'none'}\n"
            f"Final order: {', '.join(report.final_order) or 'none'}"
        )
        if report.failures:
            failures = "\n".join(
                f"{failure.module_name} [{failure.stage}] {failure.exception_type}: {failure.message}"
                for failure in report.failures
            )
            details += "\nFailures:\n" + failures
            return self.result(DiagnosticStatus.WARNING, "Module discovery completed with failures.", details, "Review the discovery failure details and repair only the affected module.")
        if not report.registered_module_ids:
            return self.result(DiagnosticStatus.FAIL, "No FC Hub modules were discovered.", details, "Verify the modules directory and module.py contracts.", True)
        return self.result(DiagnosticStatus.PASS, "Module discovery completed successfully.", details)


class FilesystemAccessCheck(Check):
    check_id = "filesystem.access"
    category = "Filesystem"
    name = "Application folder access"

    def __init__(self, paths=None):
        self.paths = [Path(item) for item in (paths or [PROJECT_ROOT / "database"])]

    def run(self):
        failures = []
        for path in self.paths:
            if not path.is_dir():
                failures.append(f"Missing directory: {path}")
                continue
            probe = None
            try:
                descriptor, probe_name = tempfile.mkstemp(prefix=".fc_hub_health_", dir=path)
                os.close(descriptor)
                probe = Path(probe_name)
                probe.write_text("FC Hub write-access probe", encoding="utf-8")
                probe.read_text(encoding="utf-8")
            except OSError as error:
                failures.append(f"{path}: {error}")
            finally:
                if probe and probe.exists():
                    probe.unlink()
        if failures:
            return self.result(DiagnosticStatus.FAIL, "An application-controlled folder is not writable.", "\n".join(failures), "Correct folder permissions or restore the missing folder.", True)
        return self.result(DiagnosticStatus.PASS, "Application-controlled folders are readable and writable.", "Checked with temporary files that were removed:\n" + "\n".join(map(str, self.paths)))


class DatabaseHealthCheck(Check):
    check_id = "database.health"
    category = "Database"
    name = "Database health"
    expected_tables = {
        "customers",
        "customer_contacts",
        "customer_addresses",
        "customer_sites",
        "customer_activities",
        "communication_candidates",
        "communication_occurrences",
        "communication_ignore_list",
        "communication_import_history",
    }

    def __init__(self, path=None):
        self.path = Path(path) if path else PROJECT_ROOT / "database" / "fc_hub.db"

    def run(self):
        if not self.path.exists():
            return self.result(DiagnosticStatus.WARNING, "The database does not exist yet.", str(self.path), "Start FC Hub normally to initialize a new database.")
        uri = f"file:{self.path.resolve().as_posix()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            connection.execute("PRAGMA foreign_keys = ON")
            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        migration_state = MigrationRunner(
            _DatabasePath(self.path),
        ).inspect()
        missing = sorted(self.expected_tables - tables)
        details = (
            f"Path: {self.path}\n"
            f"Integrity: {integrity}\n"
            f"Foreign keys: {'enabled' if foreign_keys else 'disabled'}\n"
            f"Foreign-key violations: "
            f"{len(migration_state.foreign_key_violations)}\n"
            f"Schema version: {migration_state.current_version}\n"
            f"Latest migration: {migration_state.latest_version}\n"
            f"Pending migrations: "
            f"{', '.join(map(str, migration_state.pending_versions)) or 'none'}\n"
            f"Checksum: {migration_state.checksum_status}\n"
            f"Schema status: {migration_state.schema_status}\n"
            f"Tables: {', '.join(sorted(tables))}"
        )
        if integrity != "ok":
            return self.result(DiagnosticStatus.FAIL, "SQLite integrity check failed.", details, "Stop using the database and restore a verified backup after preserving the current file.", True)
        if missing:
            return self.result(DiagnosticStatus.FAIL, "Expected database tables are missing.", details + "\nMissing: " + ", ".join(missing), "Run the controlled application initialization or migration process; do not replace the live database.", True)
        if not migration_state.supported:
            return self.result(DiagnosticStatus.FAIL, "The database schema is unsupported or a migration checksum changed.", details, "Stop and review the database schema before applying any migration.", True)
        if migration_state.foreign_key_violations:
            return self.result(DiagnosticStatus.FAIL, "Foreign-key violations were detected.", details, "Preserve the database and resolve relationship integrity through an approved migration.", True)
        if migration_state.pending_versions:
            return self.result(DiagnosticStatus.WARNING, "The database is healthy and has pending migrations.", details, "Create and verify a backup before explicitly applying pending migrations.")
        return self.result(DiagnosticStatus.PASS, "The database is readable and structurally healthy.", details)


class _DatabasePath:
    def __init__(self, path):
        self.path = Path(path)


class BackupHealthCheck(Check):
    check_id = "backup.health"
    category = "Backup"
    name = "Backup services"

    def __init__(self, root=PROJECT_ROOT):
        self.root = Path(root)

    def run(self):
        backup_dir = self.root / "backups"
        service = BackupService(source_root=self.root, default_destination=backup_dir)
        storage = service.inspect_destination(backup_dir)
        summaries = service.list_backups(backup_dir)
        verified = [item for item in summaries if item.status == "verified" and item.verification_status == "verified"]
        details = f"Service: {service.__class__.__module__}.{service.__class__.__name__}\nDirectory: {backup_dir}\nBackups: {len(summaries)}\nVerified: {len(verified)}"
        if not storage.available:
            return self.result(DiagnosticStatus.WARNING, "Backup destination is not currently available.", details + f"\nReason: {storage.error}", "Choose or create a writable backup destination.")
        if not summaries:
            return self.result(DiagnosticStatus.INFO, "Backup service is available, but no backups exist yet.", details, "Create and verify a backup with the Backup module.")
        invalid = [item.path.name for item in summaries if item.status != "verified" or item.verification_status != "verified"]
        if invalid:
            return self.result(DiagnosticStatus.WARNING, "Backup history contains incomplete or unverified backups.", details + "\nReview: " + ", ".join(invalid), "Verify valid backups and preserve at least one verified backup.")
        return self.result(DiagnosticStatus.PASS, "Backup service and verified backups are available.", details)


class ResourceAndPathCheck(Check):
    check_id = "configuration.resources"
    category = "Configuration"
    name = "Paths and resources"

    def run(self):
        database = PROJECT_ROOT / "database" / "fc_hub.db"
        issues = []
        if not PROJECT_ROOT.is_absolute():
            issues.append("Project root is not absolute.")
        if database.parent != PROJECT_ROOT / "database":
            issues.append("Database path conflicts with the project database folder.")
        assets = PROJECT_ROOT / "assets"
        details = f"Project root: {PROJECT_ROOT}\nDatabase: {database}\nAssets: {assets}"
        if issues:
            return self.result(DiagnosticStatus.FAIL, "Configured application paths conflict.", details + "\n" + "\n".join(issues), "Correct path configuration without moving or replacing client data.", True)
        if not assets.is_dir() or not any(assets.iterdir()):
            return self.result(DiagnosticStatus.INFO, "Core paths are valid; no required external resources are configured.", details, "No action is needed unless a utility requires assets.")
        return self.result(DiagnosticStatus.PASS, "Application paths and resources are available.", details)


class BasicApplicationHealthCheck(Check):
    check_id = "application.overall"
    category = "Application"
    name = "Basic application health"

    def run(self):
        required = {"communications", "crm", "troubleshooter"}
        registered = {module.info.module_id for module in module_manager.list_modules()}
        missing = sorted(required - registered)
        if missing:
            return self.result(DiagnosticStatus.FAIL, "FC Hub core loads, but major utilities are missing.", "Missing: " + ", ".join(missing), "Review launcher utility registration.", True)
        return self.result(DiagnosticStatus.PASS, "FC Hub core services and major modules respond.", "Launcher imports without starting a mainloop; ModuleManager and database modules are available.")


def build_default_registry():
    registry = DiagnosticRegistry()
    for check_type in (ProjectStructureCheck, PythonEnvironmentCheck, DependencyCheck, ImportHealthCheck, ModuleRegistrationCheck, ModuleDiscoveryCheck, FilesystemAccessCheck, DatabaseHealthCheck, BackupHealthCheck, ResourceAndPathCheck, BasicApplicationHealthCheck):
        registry.register(check_type())
    return registry
