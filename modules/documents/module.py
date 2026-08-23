"""Discoverable FC Hub Documents module."""

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class DocumentsModule(BaseModule):
    module_info = ModuleInfo(
        module_id="documents",
        name="Documents",
        description="Letterhead and spreadsheet templates, plus stored compliance documents.",
        category="Business",
        sort_order=6,
        icon="📄",
        version="1.0",
    )

    def create_window(self, master):
        from modules.documents.windows import DocumentsWindow

        return DocumentsWindow(master)
