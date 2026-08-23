# ==========================================================
# FC Hub - KPI Card Component (Redesigned)
# ----------------------------------------------------------
# Professional HubSpot-style KPI card with better styling
#
# Author: Claude
# ==========================================================

import customtkinter as ctk
from gui.styles import COLORS, FONTS


class KPICard(ctk.CTkFrame):
    """Professional KPI metric card."""

    def __init__(
        self,
        master,
        title="Metric",
        value="—",
        icon="📊",
        color="#1B7A3D",
        **kwargs
    ):
        """
        Args:
            master: Parent widget
            title: Card title
            value: Metric value
            icon: Icon emoji
            color: Accent color (hex)
        """
        super().__init__(master, **kwargs)

        self.color = color
        self.title = title
        self.value_ref = None

        # Configure styling
        self.configure(
            fg_color=COLORS["bg_secondary"],
            border_width=1,
            border_color=COLORS["border_dark"],
            corner_radius=8,
        )

        # Icon
        icon_label = ctk.CTkLabel(
            self,
            text=icon,
            font=("Segoe UI", 28),
        )
        icon_label.pack(anchor="w", padx=16, pady=(16, 8))

        # Title
        title_label = ctk.CTkLabel(
            self,
            text=title,
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
        )
        title_label.pack(anchor="w", padx=16, pady=(0, 8))

        # Value
        self.value_ref = ctk.CTkLabel(
            self,
            text=str(value),
            font=("Segoe UI", 24, "bold"),
            text_color=(color, color),
        )
        self.value_ref.pack(anchor="w", padx=16, pady=(0, 16))

    # --------------------------------------------------

    def set_value(self, value):
        """Update the value."""
        if self.value_ref:
            self.value_ref.configure(text=str(value))
