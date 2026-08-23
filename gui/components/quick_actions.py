# ==========================================================
# FC Hub - Quick Actions Component
# ----------------------------------------------------------
# Purpose:
# Grid of action buttons for common tasks (New Quote,
# Schedule Visit, etc.).
#
# Author: Claude
# ==========================================================

import customtkinter as ctk


class QuickActions(ctk.CTkFrame):
    """Quick action button grid."""

    def __init__(self, master, actions=None, columns=2, **kwargs):
        """
        Args:
            master: Parent widget
            actions: List of dicts {icon, label, command}
            columns: Number of columns in grid
        """
        super().__init__(master, **kwargs)

        self.configure(
            fg_color=("white", "#363636"),
            border_width=1,
            border_color=("gray80", "gray50"),
            corner_radius=8,
        )

        # ===== Header =====
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="Quick Actions",
            font=("Segoe UI", 12, "bold"),
            text_color=("#000000", "#E0E0E0"),
        ).pack(anchor="w")

        # ===== Button Grid =====
        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        if actions:
            for idx, action in enumerate(actions):
                row = idx // columns
                col = idx % columns

                btn = ctk.CTkButton(
                    grid_frame,
                    text=f"{action.get('icon', '')} {action.get('label', 'Action')}",
                    font=("Segoe UI", 10),
                    height=45,
                    fg_color=("#1B7A3D", "#1B7A3D"),
                    hover_color=("#165a30", "#165a30"),
                    text_color="white",
                    command=action.get("command", lambda: None),
                    corner_radius=6,
                )
                btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")

            # Configure column weights
            for col in range(columns):
                grid_frame.grid_columnconfigure(col, weight=1)
