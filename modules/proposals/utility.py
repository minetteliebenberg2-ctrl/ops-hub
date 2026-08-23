# ==========================================================
# FC Hub - Proposals Utility
# ----------------------------------------------------------
# Purpose:
# Register the Proposals module with FC Hub.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class ProposalsUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="proposals",
        name="Proposals",
        description="Create and manage client proposals, quotes, and invoices.",
        category="Business",
        sort_order=25,
        icon="FileText",
    )

    def __init__(self):

        super().__init__()

    # --------------------------------------------------

    def create_window(self, master):

        from modules.proposals.windows import ProposalsModuleWindow

        return ProposalsModuleWindow(master)
