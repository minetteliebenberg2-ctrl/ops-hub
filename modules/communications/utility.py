# ==========================================================
# FC Hub - Communications Utility
# ----------------------------------------------------------
# Purpose:
# Register the Communications module with FC Hub.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class CommunicationsUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="communications",
        name="Communications",
        description="Mailbox intelligence, contact collection and CRM handoff.",
        category="Communications",
        sort_order=20,
        icon="Communications",
    )

    def __init__(self):

        super().__init__()

    # --------------------------------------------------

    def create_window(self, master):

        from modules.communications.windows import CommunicationsModuleWindow

        return CommunicationsModuleWindow(master)
