# ==========================================================
# FC Hub - Settings Module
# ----------------------------------------------------------
# Purpose:
# Register the Settings module with FC Hub. Owns
# FacilitiesCo's own business details and addresses (master
# spec 7.17) - distinct from CRM customer data.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class SettingsModule(BaseModule):

    module_info = ModuleInfo(
        module_id="settings",
        name="Settings",
        description="Business details, banking, and business addresses.",
        category="System",
        sort_order=25,
        icon="Settings",
        version="1.0",
    )

    def create_window(self, master):

        from modules.settings.windows import SettingsWindow

        return SettingsWindow(master)
