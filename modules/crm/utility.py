# ==========================================================
# FC Hub - CRM Utility
# ----------------------------------------------------------
# Purpose:
# Register the CRM module with FC Hub.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo
from modules.crm.windows import CRMWindow


class CRMUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="crm",
        name="CRM",
        description="Customer, contact, site and activity records.",
        category="CRM",
        sort_order=30,
    )

    def __init__(self):

        super().__init__()

    # --------------------------------------------------

    def create_window(self, master):
        import traceback, pathlib
        try:
            return CRMWindow(master)
        except Exception:
            log = pathlib.Path(__file__).parent.parent.parent / "module_error.log"
            with open(log, "a") as f:
                traceback.print_exc(file=f)
            raise
