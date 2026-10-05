from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class MoneyOwingUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="money_owing",
        name="Money Owing",
        description="Customer ageing, open invoices, and bank payment matching.",
        category="Finance",
        sort_order=33,
        icon="Wallet",
    )

    def __init__(self):
        super().__init__()

    def create_window(self, master):
        from modules.money_owing.windows import MoneyOwingModuleWindow
        return MoneyOwingModuleWindow(master)
