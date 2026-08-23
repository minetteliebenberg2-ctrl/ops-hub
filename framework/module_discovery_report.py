"""Structured results from one module discovery pass."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModuleDiscoveryFailure:
    module_name: str
    module_path: str
    stage: str
    exception_type: str
    message: str
    detail: str = ""


@dataclass
class ModuleDiscoveryReport:
    discovered_folders: list[str] = field(default_factory=list)
    imported_modules: list[str] = field(default_factory=list)
    registered_module_ids: list[str] = field(default_factory=list)
    registered_names: list[str] = field(default_factory=list)
    disabled_module_ids: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    duplicate_names: list[str] = field(default_factory=list)
    invalid_module_classes: list[str] = field(default_factory=list)
    failures: list[ModuleDiscoveryFailure] = field(default_factory=list)
    final_order: list[str] = field(default_factory=list)

    @property
    def has_failures(self):
        return bool(self.failures or self.duplicate_ids or self.duplicate_names or self.invalid_module_classes)

