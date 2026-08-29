"""Register the Accounting Workbook module with Ops Hub."""

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class AccountingWorkbookUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="accounting_workbook",
        name="Accounting Workbook",
        description="Generate the annual Excel accounting workbook (ledger, P&L, balance sheet, cash flow).",
        category="Financial Year",
        sort_order=20,
        icon="BookOpen",
    )

    def __init__(self):
        super().__init__()

    def create_window(self, master):
        from modules.accounting_workbook.windows import AccountingWorkbookWindow
        return AccountingWorkbookWindow(master)
