"""Discoverable native Duplicate Finder module."""

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class DuplicateFinderModule(BaseModule):
    module_info = ModuleInfo(
        module_id="duplicate_finder",
        name="Duplicate Finder",
        description="Find content-identical files and safely move selected copies to the Recycle Bin.",
        category="File Management",
        sort_order=30,
        icon="Duplicates",
        version="1.0",
    )

    def create_window(self, master):
        from modules.duplicate_finder.windows import DuplicateFinderWindow

        return DuplicateFinderWindow(master)
