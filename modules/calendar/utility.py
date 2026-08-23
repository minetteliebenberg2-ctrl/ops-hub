# ==========================================================
# FC Hub - Calendar Utility
# ----------------------------------------------------------
# Purpose:
# Register the Calendar module with FC Hub.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class CalendarUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="calendar",
        name="Calendar",
        description="Job scheduling, project timeline, team coordination.",
        category="Operations",
        sort_order=35,
        icon="Calendar",
    )

    def __init__(self):

        super().__init__()

    # --------------------------------------------------

    def create_window(self, master):

        from modules.calendar.windows import CalendarModuleWindow

        return CalendarModuleWindow(master)
