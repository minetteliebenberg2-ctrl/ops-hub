# ==========================================================
# FC Hub - Site Visit Utility
# ----------------------------------------------------------
# Purpose:
# Register the Site Visit module with FC Hub.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class SiteVisitUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="site_visit",
        name="Site Visit",
        description="Job cards, measurement forms, site inspection checklists.",
        category="Operations",
        sort_order=45,
        icon="Clipboard",
    )

    def __init__(self):

        super().__init__()

    # --------------------------------------------------

    def create_window(self, master):

        from modules.site_visit.windows import SiteVisitModuleWindow

        return SiteVisitModuleWindow(master)
