# ==========================================================
# FC Hub - Upcoming Visits Panel Component
# ----------------------------------------------------------
# Purpose:
# Dashboard sidebar widget listing real scheduled Site Visits
# (see DashboardData.get_upcoming_site_visits) - was always empty
# until Site Visit got real persistence (2026-08-06).
#
# Author: Claude
# ==========================================================

import customtkinter as ctk


class UpcomingVisitsPanel(ctk.CTkFrame):
    """Compact list of upcoming site visits, styled to match
    ActivityTable/OverdueInvoicesPanel/StaleQuotesPanel."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.configure(
            fg_color=("white", "#363636"),
            border_width=1,
            border_color=("gray80", "gray50"),
            corner_radius=8,
        )

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="Upcoming Visits",
            font=("Segoe UI", 12, "bold"),
            text_color=("#000000", "#E0E0E0"),
        ).pack(anchor="w")

        self.list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=(15, 15), pady=(0, 15))

        self.visits = []
        self._render()

    # --------------------------------------------------

    def set_visits(self, visits):
        """Replace the displayed visits.

        Args:
            visits: list of dicts {site_name, customer, date, time},
                soonest first.
        """
        self.visits = visits
        self._render()

    # --------------------------------------------------

    def _render(self):

        for widget in self.list_frame.winfo_children():
            widget.destroy()

        if not self.visits:
            ctk.CTkLabel(
                self.list_frame,
                text="No upcoming visits scheduled",
                font=("Segoe UI", 10),
                text_color=("#999999", "#666666"),
            ).pack(pady=20)
            return

        for visit in self.visits:
            self._create_row(visit)

    # --------------------------------------------------

    def _create_row(self, visit):

        row = ctk.CTkFrame(
            self.list_frame,
            fg_color=("white", "#404040"),
            border_width=1,
            border_color=("gray90", "gray60"),
            corner_radius=6,
        )
        row.pack(fill="x", pady=4)

        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, padx=(10, 5), pady=8)

        ctk.CTkLabel(
            text_frame,
            text=f"{visit['customer']} — {visit['site_name']}",
            font=("Segoe UI", 10),
            text_color=("#000000", "#E0E0E0"),
            anchor="w",
        ).pack(fill="x", anchor="w")

        when = f"{visit['date']} {visit['time']}".strip()
        ctk.CTkLabel(
            row,
            text=when,
            font=("Segoe UI", 9, "bold"),
            text_color="#10b981",
        ).pack(side="right", padx=10, pady=8)
