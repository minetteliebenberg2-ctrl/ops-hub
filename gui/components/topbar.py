# ==========================================================
# FC Hub - Top Navigation Bar
# ----------------------------------------------------------
# Page title, breadcrumbs, search, and user controls
#
# Author: Claude (Redesign Phase 2)
# ==========================================================

import customtkinter as ctk
from gui.design_tokens import COLORS, FONTS, SPACING, LAYOUT


class TopBar(ctk.CTkFrame):
    """Top navigation bar with page title, breadcrumbs, and controls."""

    def __init__(self, master, on_home=None, on_search=None, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["surface_secondary"],
            height=LAYOUT["topbar_height"],
            **kwargs
        )

        self.on_home = on_home
        self.on_search = on_search

        # Prevent height from changing
        self.pack_propagate(False)

        # Main container
        container = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        container.pack(fill="both", expand=True, padx=SPACING["lg"])

        # Left side: breadcrumbs
        self.left_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.left_frame.pack(side="left", fill="both", expand=True)

        # Home button + breadcrumbs
        self.breadcrumb_frame = ctk.CTkFrame(
            self.left_frame,
            fg_color="transparent",
        )
        self.breadcrumb_frame.pack(side="left", fill="x")

        # Home icon button
        self.home_btn = ctk.CTkButton(
            self.breadcrumb_frame,
            text="🏠",
            font=("Arial", 14),
            fg_color="transparent",
            text_color=COLORS["accent_primary"],
            hover_color=COLORS["surface_tertiary"],
            width=32,
            height=32,
            border_width=0,
            command=self._on_home,
        )
        self.home_btn.pack(side="left", padx=(0, SPACING["sm"]))

        # Breadcrumb path
        self.breadcrumb_label = ctk.CTkLabel(
            self.breadcrumb_frame,
            text="",
            font=FONTS["body_md"],
            text_color=COLORS["text_secondary"],
        )
        self.breadcrumb_label.pack(side="left", fill="x", expand=True)

        # Right side: search + user controls
        self.right_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.right_frame.pack(side="right", fill="y")

        # Maximise (every page) - fallback for PCs where launch zoom fails
        self.max_btn = ctk.CTkButton(
            self.right_frame,
            text="⛶  Full screen",
            font=FONTS["body_md"],
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["surface_tertiary"],
            width=110,
            height=32,
            border_width=0,
            command=self._on_maximise,
        )
        self.max_btn.pack(side="left", padx=(0, SPACING["md"]))

        # Search box
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            self.right_frame,
            placeholder_text="Search...",
            textvariable=self.search_var,
            font=FONTS["body_md"],
            fg_color=COLORS["surface_primary"],
            border_color=COLORS["border_default"],
            border_width=1,
            corner_radius=6,
            height=32,
            width=200,
        )
        self.search_entry.pack(side="left", padx=(0, SPACING["lg"]))

        # Notifications placeholder
        self.notif_btn = ctk.CTkButton(
            self.right_frame,
            text="🔔",
            font=("Arial", 14),
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["surface_tertiary"],
            width=32,
            height=32,
            border_width=0,
            command=lambda: None,
        )
        self.notif_btn.pack(side="left", padx=(0, SPACING["md"]))

        # User menu placeholder
        self.user_btn = ctk.CTkButton(
            self.right_frame,
            text="👤",
            font=("Arial", 14),
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["surface_tertiary"],
            width=32,
            height=32,
            border_width=0,
            command=lambda: None,
        )
        self.user_btn.pack(side="left")

    def set_breadcrumb(self, path: str):
        """Set breadcrumb path (e.g., 'Dashboard > Overview')."""
        self.breadcrumb_label.configure(text=path)

    def set_page_title(self, title: str):
        """Set the page title in breadcrumbs."""
        self.breadcrumb_label.configure(text=title)

    def get_search_text(self) -> str:
        """Get current search text."""
        return self.search_var.get()

    def clear_search(self):
        """Clear search box."""
        self.search_var.set("")

    def _on_home(self):
        """Handle home button click."""
        if self.on_home:
            self.on_home()

    def _on_maximise(self):
        from gui.window_state import maximise
        maximise(self.winfo_toplevel())
