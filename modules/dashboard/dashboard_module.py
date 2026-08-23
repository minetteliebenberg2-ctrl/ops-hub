# ==========================================================
# FC Hub - Dashboard Module
# ----------------------------------------------------------
# Purpose:
# Dashboard module implementing BaseModule interface.
# Provides business overview with KPIs and activities.
#
# Author: Claude
# ==========================================================

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class DashboardModule(BaseModule):
    """Dashboard module showing KPIs, activities, and quick actions."""

    module_info = ModuleInfo(
        module_id="dashboard",
        name="Dashboard",
        description="Business overview with KPIs, activities, and quick actions.",
        category="Home",  # Top-level category (appears first)
        sort_order=0,  # Always first in its category
        enabled=True,
        visible=True,
        icon="🏠",
    )

    def __init__(self):
        super().__init__()

    # --------------------------------------------------

    def create_window(self, master):
        """
        Create and return the dashboard view.

        Args:
            master: Parent widget (typically ModuleHost)

        Returns:
            DashboardView widget
        """
        from modules.dashboard.dashboard_view import DashboardView

        return DashboardView(master)
