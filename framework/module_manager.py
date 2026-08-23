"""Automatic, deterministic and failure-isolated module discovery."""

import importlib
import inspect
import logging
from pathlib import Path
import sys
import traceback

from framework.base_module import BaseModule
from framework.module_discovery_report import ModuleDiscoveryFailure, ModuleDiscoveryReport


LOGGER = logging.getLogger(__name__)


class ModuleManager:
    def __init__(self, modules_path=None, package_name="modules"):
        self.modules_path = Path(modules_path) if modules_path else Path(__file__).resolve().parent.parent / "modules"
        self.package_name = package_name
        self._modules = {}
        self._report = ModuleDiscoveryReport()

    @property
    def report(self):
        return self._report

    def discover(self):
        self.clear()
        report = ModuleDiscoveryReport()
        self._refresh_package_import_context()
        LOGGER.info("Starting FC Hub module discovery from %s", self.modules_path)
        if not self.modules_path.is_dir():
            self._failure(report, self.modules_path.name, self.modules_path, "enumeration", FileNotFoundError("Module directory does not exist."))
            self._report = report
            return report
        folders = sorted(
            item for item in self.modules_path.iterdir()
            if item.is_dir() and not item.name.startswith(("_", ".")) and item.name != "__pycache__"
        )
        report.discovered_folders = [item.name for item in folders]
        for folder in folders:
            module_file = folder / "module.py"
            if not module_file.is_file():
                self._failure(report, folder.name, folder, "enumeration", FileNotFoundError("module.py is missing."))
                continue
            import_name = f"{self.package_name}.{folder.name}.module"
            try:
                importlib.invalidate_caches()
                imported = importlib.import_module(import_name)
                report.imported_modules.append(import_name)
                LOGGER.info("Imported module file %s", import_name)
            except Exception as error:
                self._failure(report, folder.name, folder, "import", error)
                continue
            candidates = [
                value for value in vars(imported).values()
                if inspect.isclass(value) and issubclass(value, BaseModule)
                and value is not BaseModule and value.__module__ == imported.__name__
            ]
            if len(candidates) != 1:
                report.invalid_module_classes.append(folder.name)
                error = ValueError(f"Expected exactly one BaseModule subclass; found {len(candidates)}.")
                self._failure(report, folder.name, folder, "inspection", error)
                continue
            module_class = candidates[0]
            info = getattr(module_class, "module_info", None)
            try:
                self._validate_info(info)
            except Exception as error:
                self._failure(report, folder.name, folder, "metadata validation", error)
                continue
            try:
                instance = module_class()
            except Exception as error:
                self._failure(report, folder.name, folder, "instantiation", error)
                continue
            try:
                self.register(instance, report=report)
            except Exception as error:
                self._failure(report, folder.name, folder, "registration", error)
        if not self._modules and not report.failures:
            self._failure(report, self.modules_path.name, self.modules_path, "registration", RuntimeError("No valid FC Hub modules were registered."))
        report.final_order = [module.info.module_id for module in self.list_modules()]
        self._report = report
        LOGGER.info("Completed module discovery: %s module(s), order=%s", len(self._modules), report.final_order)
        return report

    def register(self, module, report=None):
        if not isinstance(module, BaseModule):
            raise TypeError("Registered object must inherit BaseModule.")
        self._validate_info(module.info)
        module_id = module.info.module_id
        name = module.info.name
        if module_id in self._modules:
            if report is not None and module_id not in report.duplicate_ids:
                report.duplicate_ids.append(module_id)
            raise ValueError(f"Duplicate module ID: {module_id}")
        if any(existing.info.name == name for existing in self._modules.values()):
            if report is not None and name not in report.duplicate_names:
                report.duplicate_names.append(name)
            LOGGER.warning("Duplicate module display name detected: %s", name)
        if any(existing is module for existing in self._modules.values()):
            raise ValueError(f"Duplicate module instance: {module_id}")
        self._modules[module_id] = module
        if report is not None:
            report.registered_module_ids.append(module_id)
            report.registered_names.append(name)
            if not module.info.enabled:
                report.disabled_module_ids.append(module_id)
        return module

    def clear(self):
        self._modules.clear()

    def unregister(self, module_id):
        return self._modules.pop(module_id, None)

    def get(self, module_id):
        return self._modules.get(module_id)

    def list_modules(self):
        return sorted(self._modules.values(), key=lambda item: (item.info.category.casefold(), item.info.sort_order, item.info.name.casefold(), item.info.module_id))

    def list_by_category(self, category):
        return [item for item in self.list_modules() if item.info.category == category]

    def _validate_info(self, info):
        if info is None:
            raise ValueError("ModuleInfo metadata is missing.")
        for field in ("module_id", "name", "description", "category"):
            value = getattr(info, field, None)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"ModuleInfo.{field} must be a non-empty string.")
        if not isinstance(info.sort_order, int):
            raise ValueError("ModuleInfo.sort_order must be an integer.")
        if not isinstance(info.enabled, bool) or not isinstance(info.visible, bool):
            raise ValueError("ModuleInfo enabled and visible fields must be booleans.")

    def _failure(self, report, module_name, module_path, stage, error):
        detail = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        failure = ModuleDiscoveryFailure(module_name, str(module_path), stage, type(error).__name__, str(error), detail)
        report.failures.append(failure)
        LOGGER.error("Module discovery failed (%s, %s): %s", module_name, stage, error)

    def _refresh_package_import_context(self):
        """Prevent stale test-only package paths from affecting discovery."""
        package = sys.modules.get(self.package_name)
        if package is None:
            return
        package_paths = [Path(item).resolve() for item in getattr(package, "__path__", [])]
        expected = self.modules_path.resolve()
        if expected not in package_paths:
            for name in list(sys.modules):
                if name == self.package_name or name.startswith(self.package_name + "."):
                    sys.modules.pop(name, None)


module_manager = ModuleManager()
