# ==========================================================
# FC Hub - Module Navigation (Horizontal Tabs)
# ----------------------------------------------------------
# Horizontal module navigation bar with main tabs and
# utilities dropdown
#
# Author: Claude
# ==========================================================

import customtkinter as ctk
from tkinter import Menu
from gui.styles import COLORS, FONTS


class ModuleNav(ctk.CTkFrame):
    """Horizontal module navigation tabs."""

    # Main modules (shown as tabs in order)
    MAIN_MODULES = [
        "dashboard",
        "crm",
        "quotes",
        "accounting",
        "communications",
        "documents",
    ]

    # Utility modules (grouped in Utilities dropdown)
    UTILITY_MODULES = {
        "backup",
        "settings",
        "troubleshooter",
        "batch_renamer",
        "duplicate_finder",
        "file_mover",
        "empty_folder_remover",
        "calendar",
    }

    # Proposals and Gallery are reached through the Quotes tab's own hub
    # page (QuotesModuleWindow), the same way Communications' sub-features
    # are reached through its hub page - neither has a separate top-level
    # tab or Utilities-dropdown entry.

    # module_info.icon on every existing module is a text/library icon
    # name (e.g. "BarChart", "Communications"), not an emoji - it was
    # never wired up to a real icon font. Map the known names to emoji
    # for display; anything not in this map is assumed to already be a
    # literal emoji (e.g. the Dashboard module's "🏠").
    ICON_MAP = {
        "BarChart": "📊",
        "Calendar": "📅",
        "Image": "🖼️",
        "Files": "📁",
        "Quotes": "📄",
        "Health": "🔧",
        "Backup": "💾",
        "Communications": "📧",
        "Folder": "📂",
        "FileText": "📋",
        "Clipboard": "📍",
        "Duplicates": "🔍",
        "Settings": "⚙️",
    }

    # Fallback icons for modules that don't set module_info.icon at all
    FALLBACK_ICON_BY_MODULE_ID = {
        "crm": "👥",
    }

    def __init__(self, master, modules=None, on_module_click=None, on_theme_change=None, **kwargs):
        """
        Args:
            master: Parent widget
            modules: List of module objects
            on_module_click: Callback when module tab clicked
            on_theme_change: Callback for theme toggle
        """
        super().__init__(master, height=50, **kwargs)
        self.pack_propagate(False)

        self.modules = modules or []
        self.on_module_click = on_module_click or (lambda m: None)
        self.on_theme_change = on_theme_change or (lambda t: None)
        self.tab_buttons = {}
        self.active_module_id = None
        self.utility_modules = []

        # Configure styling
        self.configure(
            fg_color=COLORS["bg_primary"],
            border_width=1,
            border_color=COLORS["border_dark"],
        )

        # Create tab container
        self.tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_frame.pack(side="left", fill="both", expand=True, padx=10, pady=0)

    # --------------------------------------------------

    def add_module_tabs(self, modules):
        """Add module tabs in proper order."""
        self.modules = modules

        # A module with visible=False must not get a tab at all. The old
        # sidebar honoured this; the top-tab redesign dropped the check, so
        # hidden modules were still being rendered.
        modules = [m for m in modules if m.info.visible]

        # Build lookup dict for easy access
        module_dict = {m.info.module_id: m for m in modules}

        # Add main modules in order
        for module_id in self.MAIN_MODULES:
            if module_id in module_dict:
                self._add_tab(module_dict[module_id])

        # Collect utility modules
        self.utility_modules = [m for m in modules if m.info.module_id in self.UTILITY_MODULES]

        # Add Utilities tab (opens dropdown)
        if self.utility_modules:
            self._add_utilities_tab()

    # --------------------------------------------------

    def _add_tab(self, module):
        """Add a single module tab."""
        tab_text = self._display_label(module)

        btn = ctk.CTkButton(
            self.tab_frame,
            text=tab_text,
            font=FONTS["body_sm"],
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            height=32,
            corner_radius=4,
            border_width=0,
            state="normal" if module.info.enabled else "disabled",
            command=lambda m=module: self._on_tab_click(m),
        )
        btn.pack(side="left", padx=4, pady=8)

        self.tab_buttons[module.info.module_id] = btn

    # --------------------------------------------------

    def _add_utilities_tab(self):
        """Add Utilities tab that opens dropdown."""
        btn = ctk.CTkButton(
            self.tab_frame,
            text="⚙️ Utilities ▼",
            font=FONTS["body_sm"],
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            height=32,
            corner_radius=4,
            border_width=0,
            command=self._show_utilities_menu,
        )
        btn.pack(side="left", padx=4, pady=8)

        self.utilities_btn = btn
        self.tab_buttons["utilities"] = btn

    # --------------------------------------------------

    def _on_tab_click(self, module):
        """Handle module tab click."""
        self.highlight_module(module.info.module_id)
        self.on_module_click(module)

    # --------------------------------------------------

    def highlight_module(self, module_id):
        """Highlight active module tab."""
        # Clear all highlights
        for btn in self.tab_buttons.values():
            btn.configure(
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
            )

        # Highlight active
        if module_id in self.tab_buttons:
            btn = self.tab_buttons[module_id]
            btn.configure(
                fg_color=COLORS["bg_tertiary"],
                text_color=COLORS["accent_primary"],
            )
        self.active_module_id = module_id

    # --------------------------------------------------

    def _show_utilities_menu(self):
        """Show utilities dropdown menu."""
        menu = Menu(self.master, tearoff=0)

        # Add utility modules
        for module in self.utility_modules:
            menu.add_command(
                label=self._display_label(module),
                command=lambda m=module: self._on_tab_click(m),
            )

        # Add separator
        menu.add_separator()

        # Add theme toggle
        menu.add_command(label="🌙 Dark Mode", command=lambda: self._set_theme("dark"))
        menu.add_command(label="☀️  Light Mode", command=lambda: self._set_theme("light"))

        x = self.utilities_btn.winfo_rootx()
        y = self.utilities_btn.winfo_rooty() + self.utilities_btn.winfo_height()
        menu.tk_popup(x, y)

    # --------------------------------------------------

    def _set_theme(self, theme):
        """Handle theme change."""
        self.on_theme_change(theme)

    # --------------------------------------------------

    @classmethod
    def _display_label(cls, module):
        """Build 'icon name' label, mapping text icon names to emoji."""
        raw_icon = getattr(module.info, "icon", "") or ""

        if raw_icon in cls.ICON_MAP:
            icon = cls.ICON_MAP[raw_icon]
        elif raw_icon:
            # Not a known text icon name - assume it's already an emoji
            # (e.g. Dashboard's "🏠") and use it as-is.
            icon = raw_icon
        else:
            icon = cls.FALLBACK_ICON_BY_MODULE_ID.get(module.info.module_id, "")

        name = module.info.name
        return f"{icon} {name}" if icon else name
