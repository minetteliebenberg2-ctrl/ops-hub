"""Discoverable native FC Hub File Mover module."""

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class FileMoverModule(BaseModule):
    module_info = ModuleInfo(
        module_id="file_mover",
        name="File Mover",
        description="Preview and safely move files from one folder to another.",
        category="File Management",
        sort_order=40,
        icon="Folder",
        version="1.0",
    )

    def create_window(self, master):
        from modules.file_mover.windows import FileMoverWindow

        return FileMoverWindow(master)
