# ==========================================================
# FC Hub - Sidebar Navigation
# ----------------------------------------------------------
# Fixed left sidebar with module navigation, active states,
# and quick action buttons
#
# Author: Claude (Redesign Phase 2)
# ==========================================================

import customtkinter as ctk
from gui.design_tokens import COLORS, FONTS, SPACING, LAYOUT

ICON_MAP = {
    "dashboard": "📊",
    "customers": "👥",
    "crm": "👥",
    "projects": "📋",
    "measurements": "📐",
    "quotes": "💬",
    "jobs": "🔨",
    "site_visit": "🏗️",
    "schedule": "📅",
    "communications": "✉️",
    "documents": "📄",
    "gallery": "🖼️",
    "invoices": "💳",
    "expenses": "💸",
    "payments": "💰",
    "accounting": "📊",
    "proposals": "📝",
    "reports": "📈",
    "settings": "⚙️",
    "calendar": "📅",
    "shade_sails": "⛵",
    "batch_renamer": "🏷️",
    "backup": "💾",
    "duplicate_finder": "🔍",
    "file_mover": "📁",
    "empty_folder_remover": "🗑️",
    "troubleshooter": "🛠️",
}


class SidebarItem(ctk.CTkFrame):
    """A single sidebar navigation item."""

    def __init__(
        self,
        master,
        icon: str,
        label: str,
        on_click=None,
        is_active: bool = False,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self.on_click = on_click
        self.is_active = is_active
        _text_color = COLORS["sidebar_active_text"] if is_active else COLORS["sidebar_text"]

        # Container for the item — fixed height, no nested content frame so
        # vertical alignment is consistent across all items.
        self.container = ctk.CTkFrame(
            self,
            fg_color=COLORS["sidebar_active_bg"] if is_active else "transparent",
            corner_radius=6,
            height=32,
        )
        self.container.pack(fill="x", pady=1)
        self.container.pack_propagate(False)
        self.container.bind("<Button-1>", self._on_click)

        # Icon and label are placed at FIXED x-positions (not packed side by
        # side) so the text column stays aligned no matter how wide the emoji
        # glyph renders — some icons (✉ 🖼) are wider and would otherwise shove
        # the label right. Both are vertically centred via rely=0.5.
        icon_label = ctk.CTkLabel(
            self.container,
            text=icon,
            font=("Arial", 13),
            text_color=_text_color,
            anchor="center",
        )
        icon_label.place(x=12, rely=0.5, anchor="w")
        icon_label.bind("<Button-1>", self._on_click)

        label_widget = ctk.CTkLabel(
            self.container,
            text=label,
            font=FONTS["body_md"],
            text_color=_text_color,
            anchor="w",
        )
        label_widget.place(x=38, rely=0.5, anchor="w")
        label_widget.bind("<Button-1>", self._on_click)

    def _on_click(self, event=None):
        if self.on_click:
            self.on_click()

    def set_active(self, is_active: bool):
        """Update active state."""
        self.is_active = is_active
        self.container.configure(
            fg_color=(
                COLORS["sidebar_active_bg"]
                if is_active
                else "transparent"
            )
        )


class Sidebar(ctk.CTkFrame):
    """Fixed left sidebar for module navigation."""

    def __init__(self, master, on_module_click=None, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["sidebar_bg"],
            width=LAYOUT["sidebar_width"],
            **kwargs
        )

        self.on_module_click = on_module_click
        self.active_module = None
        self.module_items = {}

        # Prevent width from changing
        self.pack_propagate(False)

        # Logo area
        logo_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
            height=60,
        )
        logo_frame.pack(fill="x", padx=SPACING["lg"], pady=SPACING["lg"])
        logo_frame.pack_propagate(False)

        logo_text = ctk.CTkLabel(
            logo_frame,
            text="Ops Hub",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["sidebar_text"],
        )
        logo_text.pack(anchor="w")

        # Quick action button
        self.new_project_btn = ctk.CTkButton(
            self,
            text="+ New Project",
            font=FONTS["label"],
            fg_color=COLORS["accent_primary"],
            text_color=COLORS["text_inverse"],
            height=36,
            border_width=0,
            corner_radius=6,
            command=self._on_new_project,
        )
        self.new_project_btn.pack(
            fill="x",
            padx=SPACING["lg"],
            pady=(0, SPACING["lg"]),
        )

        # Scrollable navigation area
        self.nav_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            label_text=None,
        )
        self.nav_frame.pack(fill="both", expand=True, padx=SPACING["md"])

        # Section spacer helper
        self._last_section = None

    def add_section(self, title: str):
        """Add a section header."""
        if self._last_section is not None:
            # Add spacing before new section
            spacer = ctk.CTkFrame(
                self.nav_frame,
                fg_color="transparent",
                height=SPACING["md"],
            )
            spacer.pack(fill="x")
            spacer.pack_propagate(False)

        # Section label
        section_label = ctk.CTkLabel(
            self.nav_frame,
            text=title.upper(),
            font=("Segoe UI", 9, "bold"),
            text_color=COLORS["text_tertiary"],
        )
        section_label.pack(
            anchor="w",
            padx=(SPACING["md"], 0),
            pady=(SPACING["md"], SPACING["sm"]),
        )

        self._last_section = section_label

    def add_module(
        self,
        module_id: str,
        label: str,
        on_click=None,
    ):
        """Add a module navigation item."""
        icon = ICON_MAP.get(module_id, "▪")

        item = SidebarItem(
            self.nav_frame,
            icon=icon,
            label=label,
            on_click=lambda: self._on_module_click(module_id, on_click),
            is_active=(module_id == self.active_module),
        )
        item.pack(fill="x", pady=0)

        self.module_items[module_id] = item

    def set_active_module(self, module_id: str):
        """Set the active module."""
        # Deactivate previous
        if self.active_module and self.active_module in self.module_items:
            self.module_items[self.active_module].set_active(False)

        # Activate new
        self.active_module = module_id
        if module_id in self.module_items:
            self.module_items[module_id].set_active(True)

    def _on_module_click(self, module_id: str, callback=None):
        """Handle module click."""
        self.set_active_module(module_id)
        if callback:
            callback()
        if self.on_module_click:
            self.on_module_click(module_id)

    def _on_new_project(self):
        """Handle New Project button click."""
        if self.on_module_click:
            self.on_module_click("new_project")
