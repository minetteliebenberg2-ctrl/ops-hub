"""Discoverable FC Hub Backup module."""

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class BackupModule(BaseModule):
    module_info = ModuleInfo(
        module_id="backup",
        name="Backup",
        description="Create, verify, and safely prepare recovery backups.",
        category="System",
        sort_order=20,
        icon="Backup",
        version="1.0",
    )

    def create_window(self, master):
        from modules.backup.windows import BackupWindow

        return BackupWindow(master)
