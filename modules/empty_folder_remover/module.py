"""Discoverable native FC Hub Empty Folder Remover module."""

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class EmptyFolderRemoverModule(BaseModule):
    module_info = ModuleInfo(
        module_id="empty_folder_remover",
        name="Empty Folder Remover",
        description="Find empty folders and safely move selected folders to the Recycle Bin.",
        category="File Management",
        sort_order=50,
        icon="Folder",
        version="1.0",
    )

    def create_window(self, master):
        from modules.empty_folder_remover.windows import EmptyFolderRemoverWindow

        return EmptyFolderRemoverWindow(master)
