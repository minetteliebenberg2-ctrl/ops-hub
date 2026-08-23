# ==========================================================
# FC Hub - Stale Quotes Panel Component
# ----------------------------------------------------------
# Purpose:
# Dashboard sidebar widget listing issued quotes that are
# expiring soon or already past their expiry date with no
# decision recorded yet (see DashboardData.get_stale_quotes) -
# the "forgotten follow-up" workflow-audit finding.
#
# Author: Claude
# ==========================================================

import customtkinter as ctk


class StaleQuotesPanel(ctk.CTkFrame):
    """Compact list of quotes needing follow-up, styled to match
    ActivityTable/OverdueInvoicesPanel."""

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
            text="Quotes Needing Follow-up",
            font=("Segoe UI", 12, "bold"),
            text_color=("#000000", "#E0E0E0"),
        ).pack(anchor="w")

        self.list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=(15, 15), pady=(0, 15))

        self.quotes = []
        self._render()

    # --------------------------------------------------

    def set_quotes(self, quotes):
        """Replace the displayed quotes.

        Args:
            quotes: list of dicts {quote_number, customer,
                status_label, days}, worst (most expired) first.
        """
        self.quotes = quotes
        self._render()

    # --------------------------------------------------

    def _render(self):

        for widget in self.list_frame.winfo_children():
            widget.destroy()

        if not self.quotes:
            ctk.CTkLabel(
                self.list_frame,
                text="No quotes need follow-up",
                font=("Segoe UI", 10),
                text_color=("#999999", "#666666"),
            ).pack(pady=20)
            return

        for quote in self.quotes:
            self._create_row(quote)

    # --------------------------------------------------

    def _create_row(self, quote):

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
            text=f"{quote['quote_number']} — {quote['customer']}",
            font=("Segoe UI", 10),
            text_color=("#000000", "#E0E0E0"),
            anchor="w",
        ).pack(fill="x", anchor="w")

        color = "#ef4444" if quote["days"] < 0 else "#f59e0b"
        ctk.CTkLabel(
            row,
            text=quote["status_label"],
            font=("Segoe UI", 9, "bold"),
            text_color=color,
        ).pack(side="right", padx=10, pady=8)
