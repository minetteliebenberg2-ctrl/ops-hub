# ==========================================================
# FC Hub - Accounting Utility
# ----------------------------------------------------------
# Purpose:
# Register the Accounting module with FC Hub.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class AccountingUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="accounting",
        name="Accounting",
        description="Financial tracking, transactions, reports, and Excel import.",
        category="Finance",
        sort_order=30,
        icon="BarChart",
    )

    def __init__(self):

        super().__init__()

    # --------------------------------------------------

    def create_window(self, master):

        from modules.accounting.windows import AccountingModuleWindow

        return AccountingModuleWindow(master)
