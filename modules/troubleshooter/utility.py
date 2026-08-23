"""Register the Troubleshooter with FC Hub."""

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class TroubleshooterUtility(BaseModule):
    module_info = ModuleInfo(
        module_id="troubleshooter",
        name="Troubleshooter",
        description="Check FC Hub system health and diagnose common problems.",
        category="System",
        sort_order=90,
        icon="Health",
    )

    def __init__(self):
        super().__init__()

    def create_window(self, master):
        from modules.troubleshooter.windows import TroubleshooterWindow

        return TroubleshooterWindow(master)
