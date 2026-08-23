# ==========================================================
# FC Hub - Top Navigation Bar (Redesigned)
# ----------------------------------------------------------
# Professional Claude-like top navigation with:
# - Logo and branding
# - Search bar
# - Real dropdown menus
#
# Author: Claude
# ==========================================================

import customtkinter as ctk
from tkinter import Menu
from gui.styles import COLORS, FONTS, SPACING


class TopNav(ctk.CTkFrame):
    """Professional top navigation bar."""

    def __init__(
        self,
        master,
        on_tools_menu=None,
        on_search=None,
        on_home=None,
        **kwargs
    ):
        """
        Args:
            master: Parent widget
            on_tools_menu: Callback for tools menu
            on_search: Callback for search
            on_home: Callback for home/logo click
        """
        super().__init__(master, height=60, **kwargs)
        self.pack_propagate(False)

        self.on_tools_menu = on_tools_menu or (lambda: None)
        self.on_search = on_search or (lambda x: None)
        self.on_home = on_home or (lambda: None)

        # Configure styling
        self.configure(fg_color=COLORS["bg_secondary"], border_width=0)

        # ===== LEFT: Logo =====
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.pack(side="left", fill="y", padx=(20, 30), pady=0)

        home_btn = ctk.CTkButton(
            left_frame,
            text="← Dashboard",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            command=self.on_home,
            corner_radius=6,
            border_width=0,
        )
        home_btn.pack(side="left", padx=(0, 12))

        logo_btn = ctk.CTkButton(
            left_frame,
            text="FC Hub",
            font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            command=self.on_home,
            corner_radius=0,
            border_width=0,
        )
        logo_btn.pack(side="left")

        # ===== CENTER: Search =====
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(side="left", fill="both", expand=True, padx=(0, 20))

        search_container = ctk.CTkFrame(
            search_frame,
            fg_color=COLORS["bg_tertiary"],
            border_width=1,
            border_color=COLORS["border_dark"],
            corner_radius=6,
            height=36,
        )
        search_container.pack(fill="x", expand=True, pady=12)
        search_container.pack_propagate(False)

        search_icon = ctk.CTkLabel(
            search_container,
            text="🔍",
            font=("Segoe UI", 12),
            text_color=COLORS["text_tertiary"],
        )
        search_icon.pack(side="left", padx=(10, 5))

        self.search_entry = ctk.CTkEntry(
            search_container,
            placeholder_text="Search customers, quotes, activities...",
            fg_color="transparent",
            border_width=0,
            font=FONTS["body_md"],
            text_color=COLORS["text_primary"],
            placeholder_text_color=COLORS["text_tertiary"],
        )
        self.search_entry.pack(side="left", fill="both", expand=True, padx=5)
        self.search_entry.bind("<Return>", self._on_search_enter)

        # ===== RIGHT: Actions =====
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.pack(side="right", fill="y", padx=(0, 20))

        # Notifications
        notif_btn = ctk.CTkButton(
            right_frame,
            text="🔔",
            width=36,
            height=36,
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            border_width=0,
            command=self._on_notifications_click,
            font=("Segoe UI", 14),
        )
        notif_btn.pack(side="left", padx=4)

        # User Avatar (with dropdown)
        avatar_btn = ctk.CTkButton(
            right_frame,
            text="👤",
            width=36,
            height=36,
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            border_width=0,
            command=self._on_user_menu_click,
            font=("Segoe UI", 14),
            corner_radius=6,
        )
        avatar_btn.pack(side="left", padx=4)

        # Tools Menu (with dropdown)
        tools_btn = ctk.CTkButton(
            right_frame,
            text="⋮",
            width=36,
            height=36,
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            border_width=0,
            command=self._on_tools_click,
            font=("Segoe UI", 16),
        )
        tools_btn.pack(side="left", padx=4)

    # --------------------------------------------------
    # Menu implementations
    # --------------------------------------------------

    def _on_search_enter(self, event):
        """Handle Enter in search box."""
        term = self.search_entry.get().strip()
        if term:
            self.on_search(term)
            self.search_entry.delete(0, "end")

    # --------------------------------------------------

    def _on_notifications_click(self):
        """Show notifications dropdown."""
        menu = Menu(self.master, tearoff=0)
        menu.add_command(label="No new notifications")
        menu.add_separator()
        menu.add_command(label="Notification settings")

        # Get button position for menu placement
        x = self.winfo_rootx() + self.winfo_width() - 150
        y = self.winfo_rooty() + self.winfo_height()
        menu.tk_popup(x, y)

    # --------------------------------------------------

    def _on_user_menu_click(self):
        """Show user menu dropdown."""
        menu = Menu(self.master, tearoff=0)
        menu.add_command(label="👤 Profile")
        menu.add_command(label="⚙️  Settings")
        menu.add_command(label="🔐 Security")
        menu.add_separator()
        menu.add_command(label="📖 Help & Support")
        menu.add_command(label="ℹ️  About")
        menu.add_separator()
        menu.add_command(label="🚪 Sign Out")

        x = self.winfo_rootx() + self.winfo_width() - 180
        y = self.winfo_rooty() + self.winfo_height()
        menu.tk_popup(x, y)

    # --------------------------------------------------

    def _on_tools_click(self):
        """Show tools menu dropdown."""
        self.on_tools_menu()

    # --------------------------------------------------

    def clear_search(self):
        """Clear search field."""
        self.search_entry.delete(0, "end")

    def set_search_focus(self):
        """Focus search field."""
        self.search_entry.focus()
