# ==========================================================
# FC Hub - Main Window (Phase 2 Redesign)
# ----------------------------------------------------------
# Professional desktop CRM interface with:
# - Fixed left sidebar navigation
# - Top navigation bar with breadcrumbs and search
# - Main content area
# - Light theme
#
# Author: Claude (Redesign Phase 2)
# ==========================================================

import customtkinter as ctk

from framework.module_manager import module_manager
from gui.module_host import ModuleHost
from gui.components.sidebar import Sidebar
from gui.components.topbar import TopBar
from gui.design_tokens import COLORS, LAYOUT


class MainWindow:
    """Main window with sidebar + top bar layout."""

    def __init__(self, master, manager=None):

        self.master = master
        self.manager = manager or module_manager

        self.master.title("Ops Hub")
        self.master.geometry("1600x900")
        self.master.minsize(1200, 700)
        self.master.state("zoomed")
        from gui.window_state import maximise_on_launch
        maximise_on_launch(self.master)

        # Configure main window background
        self.master.configure(fg_color=COLORS["surface_primary"])

        # ===== MAIN CONTAINER =====
        main_container = ctk.CTkFrame(
            self.master,
            fg_color="transparent",
        )
        main_container.pack(fill="both", expand=True)

        # ===== LEFT SIDEBAR =====
        self.sidebar = Sidebar(
            main_container,
            on_module_click=self._on_module_click,
        )
        self.sidebar.pack(side="left", fill="y")

        # ===== RIGHT PANEL (Top Bar + Content) =====
        right_panel = ctk.CTkFrame(
            main_container,
            fg_color="transparent",
        )
        right_panel.pack(side="left", fill="both", expand=True)

        # Top bar
        self.top_bar = TopBar(
            right_panel,
            on_home=self._show_dashboard,
            on_search=self._on_search,
        )
        self.top_bar.pack(side="top", fill="x")

        # Content area
        self.content = ModuleHost(right_panel)
        self.content.pack(side="top", fill="both", expand=True)

        self.active_frame = None
        self.active_module = None

        # Build and show
        self._build_sidebar_navigation()
        self._setup_dashboard_callbacks()
        self._show_dashboard()

    # ==================================================
    # Navigation Building
    # ==================================================

    def _build_sidebar_navigation(self):
        """Build sidebar navigation from module registry."""
        modules = self.manager.list_modules()

        # Group modules by category
        sections = {
            "Main": [],
            "Operations": [],
            "Finance": [],
            "Tools": [],
        }

        # Categorize modules
        main_modules = [
            "dashboard",
            "customers",
            "crm",
            "projects",
            "measurements",
            "quotes",
            "jobs",
        ]
        operations_modules = [
            "schedule",
            "site_visit",
            "communications",
            "documents",
            "gallery",
            "proposals",
        ]
        finance_modules = [
            "invoices",
            "expenses",
            "payments",
            "accounting",
            "reports",
        ]
        tools_modules = [
            "settings",
        ]

        # Assign modules to sections
        for module in modules:
            if not module.info.enabled:
                continue

            module_id = module.info.module_id
            label = module.info.name

            if module_id in main_modules:
                sections["Main"].append((module_id, label, module))
            elif module_id in operations_modules:
                sections["Operations"].append((module_id, label, module))
            elif module_id in finance_modules:
                sections["Finance"].append((module_id, label, module))
            else:
                sections["Tools"].append((module_id, label, module))

        # Build sidebar
        for section_name, modules_list in sections.items():
            if modules_list:
                self.sidebar.add_section(section_name)
                for module_id, label, module in modules_list:
                    self.sidebar.add_module(
                        module_id,
                        label,
                        on_click=lambda m=module: self.open_utility(m),
                    )

    # --------------------------------------------------

    def _setup_dashboard_callbacks(self):
        """Set up dashboard navigation callbacks."""
        try:
            from modules.dashboard.dashboard_view import set_main_window_ref

            set_main_window_ref(self)
        except ImportError:
            pass

    # --------------------------------------------------

    def _show_dashboard(self):
        """Load and show dashboard as default view."""
        dashboard = self.manager.get("dashboard")
        if dashboard and dashboard.info.enabled:
            self.active_module = dashboard
            self.sidebar.set_active_module("dashboard")
            self.top_bar.set_page_title("Dashboard")
            self.active_frame = self.content.mount(dashboard.create_window)
        else:
            self.show_home()

    # --------------------------------------------------

    def open_utility(self, utility):
        """Open a module."""
        if not utility.info.enabled:
            return

        self.active_module = utility
        module_id = utility.info.module_id
        self.sidebar.set_active_module(module_id)
        self.top_bar.set_page_title(utility.info.name)
        self.active_frame = self.content.mount(utility.create_window)

    # --------------------------------------------------

    def open_module_by_id(self, module_id):
        """Open a module by ID (used by dashboard quick actions)."""
        module = self.manager.get(module_id)
        if module and module.info.enabled:
            self.open_utility(module)

    # --------------------------------------------------

    def show_home(self):
        """Show default home view (fallback)."""
        self.top_bar.set_page_title("Ops Hub")
        self.active_frame = self.content.show_home()

    # --------------------------------------------------

    def clear_content(self):
        """Clear active content."""
        self.content.clear()
        self.active_frame = None
        self.active_module = None

    # ==================================================
    # Event Handlers
    # ==================================================

    def _on_module_click(self, module_id):
        """Handle sidebar module click."""
        if module_id == "new_project":
            # TODO: Open new project dialog
            self.open_module_by_id("projects")
        else:
            self.open_module_by_id(module_id)

    def _on_search(self, query: str):
        """Handle search (TODO: implement global search)."""
        if not query or not query.strip():
            return

        # TODO: Implement global search across customers, quotes, invoices
        # For now, pass through to prevent errors
        pass
