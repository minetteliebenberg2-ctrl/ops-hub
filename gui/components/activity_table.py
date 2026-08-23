# ==========================================================
# FC Hub - Activity Table Component
# ----------------------------------------------------------
# Purpose:
# Scrollable activity feed showing recent events (quotes,
# invoices, contacts, etc.).
#
# Author: Claude
# ==========================================================

import customtkinter as ctk
from tkinter import ttk
from datetime import datetime


class ActivityTable(ctk.CTkFrame):
    """Scrollable activity feed."""

    def __init__(self, master, max_height=300, **kwargs):
        """
        Args:
            master: Parent widget
            max_height: Maximum height before scrolling
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
            text="Recent Activity",
            font=("Segoe UI", 12, "bold"),
            text_color=("#000000", "#E0E0E0"),
        ).pack(anchor="w")

        # ===== Scrollable Activity List =====
        canvas = ctk.CTkCanvas(
            self,
            highlightthickness=0,
            bg="#363636",
            highlightbackground="#363636",
            height=max_height,
        )
        scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=(0, 15))
        scrollbar.pack(side="right", fill="y", padx=(0, 15), pady=(0, 15))

        self.activity_frame = ctk.CTkFrame(canvas, fg_color="transparent")
        self.activity_window = canvas.create_window(
            (0, 0),
            window=self.activity_frame,
            anchor="nw",
        )

        def _on_mousewheel(event):
            # Widget teardown doesn't reliably fire <Leave> first, which
            # used to leave this bind_all callback armed and crash the
            # next scroll anywhere in the app on this dead canvas.
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        canvas.bind("<Destroy>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        # Bind updates to canvas
        self.activity_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(self.activity_window, width=e.width - 20),
        )

        self.activities = []

    # --------------------------------------------------

    def add_activity(
        self, icon, description, entity, timestamp=None
    ):
        """
        Add an activity row.

        Args:
            icon: Emoji icon
            description: What happened (e.g., "Quote issued")
            entity: Related entity (e.g., "ABC Corp - Quote #001")
            timestamp: datetime object (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        self.activities.append(
            {
                "icon": icon,
                "description": description,
                "entity": entity,
                "timestamp": timestamp,
            }
        )

        # Keep last 10 activities
        if len(self.activities) > 10:
            self.activities.pop(0)

        self._render_activities()

    # --------------------------------------------------

    def _render_activities(self):
        """Re-render all activities."""
        # Clear existing
        for widget in self.activity_frame.winfo_children():
            widget.destroy()

        if not self.activities:
            ctk.CTkLabel(
                self.activity_frame,
                text="No activities yet",
                font=("Segoe UI", 10),
                text_color=("#999999", "#666666"),
            ).pack(pady=20)
            return

        # Render newest first
        for activity in reversed(self.activities):
            self._create_activity_row(activity)

    # --------------------------------------------------

    def _create_activity_row(self, activity):
        """Create a single activity row."""
        row = ctk.CTkFrame(
            self.activity_frame,
            fg_color=("white", "#404040"),
            border_width=1,
            border_color=("gray90", "gray60"),
            corner_radius=6,
        )
        row.pack(fill="x", pady=4, padx=5)

        # Left: Icon
        icon_label = ctk.CTkLabel(
            row,
            text=activity["icon"],
            font=("Segoe UI", 12),
            width=30,
        )
        icon_label.pack(side="left", padx=(10, 5), pady=8)

        # Middle: Text (description + entity)
        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, pady=8, padx=5)

        desc_label = ctk.CTkLabel(
            text_frame,
            text=activity["description"],
            font=("Segoe UI", 10),
            text_color=("#000000", "#E0E0E0"),
            anchor="w",
        )
        desc_label.pack(fill="x", anchor="w")

        entity_label = ctk.CTkLabel(
            text_frame,
            text=activity["entity"],
            font=("Segoe UI", 9),
            text_color=("#666666", "#999999"),
            anchor="w",
        )
        entity_label.pack(fill="x", anchor="w")

        # Right: Timestamp
        time_str = self._format_time(activity["timestamp"])
        time_label = ctk.CTkLabel(
            row,
            text=time_str,
            font=("Segoe UI", 8),
            text_color=("#999999", "#666666"),
        )
        time_label.pack(side="right", padx=10, pady=8)

    # --------------------------------------------------

    @staticmethod
    def _format_time(timestamp):
        """Format timestamp as relative time."""
        if isinstance(timestamp, str):
            return timestamp

        now = datetime.now()
        diff = now - timestamp

        if diff.total_seconds() < 60:
            return "now"
        elif diff.total_seconds() < 3600:
            return f"{int(diff.total_seconds() / 60)}m ago"
        elif diff.total_seconds() < 86400:
            return f"{int(diff.total_seconds() / 3600)}h ago"
        else:
            return f"{int(diff.total_seconds() / 86400)}d ago"

    # --------------------------------------------------

    def clear(self):
        """Clear all activities."""
        self.activities.clear()
        self._render_activities()
