# ==========================================================
# FC Hub - Gallery Utility
# ----------------------------------------------------------
# Purpose:
# Register the Gallery module with FC Hub.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class GalleryUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="gallery",
        name="Gallery",
        description="Project image galleries with EXIF metadata and phase tracking.",
        category="Media",
        sort_order=40,
        icon="Image",
    )

    def __init__(self):

        super().__init__()

    # --------------------------------------------------

    def create_window(self, master):

        from modules.gallery.windows import GalleryModuleWindow

        return GalleryModuleWindow(master)
