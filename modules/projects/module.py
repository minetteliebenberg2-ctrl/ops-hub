# ==========================================================
# FC Hub - Projects Module
# ----------------------------------------------------------
# Purpose:
# Project management and tracking with status,
# customer association, and installation timeline.
#
# Author: Claude (Redesign Phase 3)
# Version: 1.0
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class ProjectsModule(BaseModule):

    module_info = ModuleInfo(
        module_id="projects",
        name="Projects",
        description="Manage projects and track installation progress.",
        category="Operations",
        sort_order=40,
        icon="Projects",
        version="1.0",
    )

    def create_window(self, master):

        from modules.projects.windows import ProjectsView

        return ProjectsView(master)
