"""Discoverable Batch Renamer module entry point."""

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class BatchRenamerModule(BaseModule):
    module_info = ModuleInfo(
        module_id="batch_renamer",
        name="Batch Renamer",
        description="Preview and safely prefix filenames in a folder tree.",
        category="File Management",
        sort_order=10,
        icon="Files",
    )

    def create_window(self, master):
        from modules.batch_renamer.windows import BatchRenamerWindow

        return BatchRenamerWindow(master)
