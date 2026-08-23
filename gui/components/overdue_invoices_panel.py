# ==========================================================
# FC Hub - Overdue Invoices Panel Component
# ----------------------------------------------------------
# Purpose:
# Dashboard sidebar widget listing real overdue Tax Invoices
# (see DashboardData.get_overdue_invoices) - lets Minette spot a
# late payment without leaving the Dashboard.
#
# Author: Claude
# ==========================================================

import customtkinter as ctk


class OverdueInvoicesPanel(ctk.CTkFrame):
    """Compact list of overdue invoices, styled to match ActivityTable."""

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
            text="Overdue Invoices",
            font=("Segoe UI", 12, "bold"),
            text_color=("#000000", "#E0E0E0"),
        ).pack(anchor="w")

        self.list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=(15, 15), pady=(0, 15))

        self.invoices = []
        self._render()

    # --------------------------------------------------

    def set_invoices(self, invoices):
        """Replace the displayed invoices.

        Args:
            invoices: list of dicts {invoice_number, customer, amount,
                days_overdue}, worst-overdue first.
        """
        self.invoices = invoices
        self._render()

    # --------------------------------------------------

    def _render(self):

        for widget in self.list_frame.winfo_children():
            widget.destroy()

        if not self.invoices:
            ctk.CTkLabel(
                self.list_frame,
                text="No overdue invoices",
                font=("Segoe UI", 10),
                text_color=("#999999", "#666666"),
            ).pack(pady=20)
            return

        for invoice in self.invoices:
            self._create_row(invoice)

    # --------------------------------------------------

    def _create_row(self, invoice):

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
            text=f"{invoice['invoice_number']} — {invoice['customer']}",
            font=("Segoe UI", 10),
            text_color=("#000000", "#E0E0E0"),
            anchor="w",
        ).pack(fill="x", anchor="w")

        ctk.CTkLabel(
            text_frame,
            text=invoice["amount"],
            font=("Segoe UI", 9),
            text_color=("#666666", "#999999"),
            anchor="w",
        ).pack(fill="x", anchor="w")

        ctk.CTkLabel(
            row,
            text=f"{invoice['days_overdue']}d overdue",
            font=("Segoe UI", 9, "bold"),
            text_color="#ef4444",
        ).pack(side="right", padx=10, pady=8)
