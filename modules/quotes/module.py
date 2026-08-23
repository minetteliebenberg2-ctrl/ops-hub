# ==========================================================
# FC Hub - Quotes Module
# ----------------------------------------------------------
# Purpose:
# Register the Quotes module with FC Hub. Owns quote creation,
# line items, numbering, issuing, and PDF generation.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class QuotesModule(BaseModule):

    module_info = ModuleInfo(
        module_id="quotes",
        name="Quotes",
        description="Create, issue, and generate PDF quotes for customers.",
        category="Sales",
        sort_order=35,
        icon="Quotes",
        version="1.0",
    )

    def create_window(self, master):

        from modules.quotes.windows import QuotesWindow

        return QuotesWindow(master)
