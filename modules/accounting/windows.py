# ==========================================================
# FC Hub - Accounting Module (Light Theme Hub)
# ----------------------------------------------------------
# Purpose:
# The landing screen for Accounting: this financial year's key
# figures at a glance, the most recent transactions, and the way
# in to every accounting tool.
#
# The tools themselves live in ledger_windows.py (ledger, bank
# import, payments, invoices, categories, reports) and
# statements_windows.py (income statement, cash flow, balance
# sheet, bank reconciliation). This file only presents them - it
# holds no accounting logic of its own.
#
# Author: Minette & James
# Version: 2.0
# ==========================================================

import getpass
from tkinter import messagebox

import customtkinter as ctk

from core.financial_statements import (
    FinancialStatementsService,
    current_financial_year,
    financial_year_bounds,
    financial_year_label,
)
from core.ledger_service import LedgerService
from core.quote_pdf import format_money
from gui.design_tokens import COLORS, FONTS, SPACING
from gui.entity_table import build_entity_table
from gui.flow_layout import reflow_widgets


def current_actor():
    try:
        return getpass.getuser()
    except Exception:
        return ""


class AccountingModuleWindow(ctk.CTkFrame):
    """Accounting landing screen."""

    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["surface_primary"])

        self.service = LedgerService()
        self.statements = FinancialStatementsService(ledger_service=self.service)
        self.financial_year = current_financial_year()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["surface_primary"])
        scroll.grid(row=1, column=0, sticky="nsew")

        self._build_kpi_cards(scroll)
        self._build_tools(scroll)
        self._build_transaction_list(scroll)

        self.refresh()

    # --------------------------------------------------
    # Layout
    # --------------------------------------------------

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(
            row=0, column=0, sticky="ew",
            padx=SPACING["xxl"], pady=(SPACING["xxl"], SPACING["lg"]),
        )

        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            titles, text="Accounting",
            font=FONTS["title_lg"], text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        self.subtitle = ctk.CTkLabel(
            titles, text="",
            font=FONTS["body_md"], text_color=COLORS["text_secondary"],
        )
        self.subtitle.pack(anchor="w", pady=(SPACING["sm"], 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        ctk.CTkButton(
            actions, text="Open Ledger",
            font=FONTS["body_sm"],
            fg_color=COLORS["accent_primary"],
            text_color=COLORS["text_inverse"],
            hover_color=COLORS["accent_hover"],
            command=self.open_ledger,
        ).pack(side="left", padx=(0, SPACING["md"]))

        ctk.CTkButton(
            actions, text="Financial Statements",
            font=FONTS["body_sm"],
            fg_color=COLORS["surface_secondary"],
            text_color=COLORS["text_primary"],
            border_width=1, border_color=COLORS["border_default"],
            command=self.open_statements,
        ).pack(side="left")

    def _build_kpi_cards(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=SPACING["xxl"], pady=(0, SPACING["lg"]))

        self.kpi_values = {}
        for key, label in (
            ("income", "Income this financial year"),
            ("expenses", "Expenses this financial year"),
            ("profit", "Net profit / (loss)"),
            ("cash", "Closing bank balance"),
        ):
            self.kpi_values[key] = self._build_kpi_card(frame, label)

    def _build_kpi_card(self, parent, label):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["surface_secondary"],
            border_width=1, border_color=COLORS["border_default"],
            corner_radius=8,
        )
        card.pack(side="left", fill="both", expand=True, padx=(0, SPACING["md"]))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=SPACING["lg"], pady=SPACING["lg"])

        ctk.CTkLabel(
            inner, text=label,
            font=FONTS["body_sm"], text_color=COLORS["text_secondary"],
            wraplength=180, justify="left",
        ).pack(anchor="w", pady=(0, SPACING["sm"]))

        value = ctk.CTkLabel(
            inner, text="—",
            font=FONTS["heading_md"], text_color=COLORS["accent_primary"],
        )
        value.pack(anchor="w")
        return value

    def _build_tools(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=SPACING["xxl"], pady=(0, SPACING["lg"]))

        ctk.CTkLabel(
            frame, text="Tools",
            font=FONTS["heading_sm"], text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, SPACING["md"]))

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.pack(fill="x")

        # reflow_widgets wraps the row instead of letting the last buttons
        # fall off the edge on a narrow window - the bug fixed in
        # gui/flow_layout.py.
        reflow_widgets(buttons, [
            self._tool_button(buttons, "Ledger", self.open_ledger),
            self._tool_button(buttons, "Statements", self.open_statements),
            self._tool_button(buttons, "Dashboard", self.open_dashboard),
            self._tool_button(buttons, "Import Bank Statement", self.open_bank_import),
            self._tool_button(buttons, "Payments", self.open_payments),
            self._tool_button(buttons, "Invoices", self.open_invoices),
            self._tool_button(buttons, "Categories", self.open_categories),
            self._tool_button(buttons, "Reports", self.open_reports),
        ])

    def _tool_button(self, parent, text, command):
        return ctk.CTkButton(
            parent, text=text, command=command,
            font=FONTS["body_sm"],
            fg_color=COLORS["surface_secondary"],
            text_color=COLORS["text_primary"],
            hover_color=COLORS["border_default"],
            border_width=1, border_color=COLORS["border_default"],
            width=180,
        )

    def _build_transaction_list(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=SPACING["xxl"], pady=(0, SPACING["xxl"]))

        ctk.CTkLabel(
            frame, text="Recent Transactions",
            font=FONTS["heading_sm"], text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, SPACING["md"]))

        table_frame = ctk.CTkFrame(frame, fg_color="transparent")
        table_frame.pack(fill="both", expand=True)

        self.table = build_entity_table(
            table_frame,
            ("Date", "Description", "Category", "Account", "Type", "Amount"),
            (("Refresh", self.refresh),),
        )

    # --------------------------------------------------
    # Data
    # --------------------------------------------------

    def refresh(self):
        label = financial_year_label(self.financial_year)
        self.subtitle.configure(text=f"{label} — 1 March to end February")

        start, end = financial_year_bounds(self.financial_year)
        summary = self.service.get_summary(date_from=start, date_to=end)
        cash = self.statements.cash_flow(self.financial_year)

        self.kpi_values["income"].configure(
            text=format_money(summary["total_income_minor"]))
        self.kpi_values["expenses"].configure(
            text=format_money(summary["total_expenses_minor"]))
        self.kpi_values["profit"].configure(
            text=format_money(summary["net_profit_minor"]))
        self.kpi_values["cash"].configure(
            text=format_money(cash["closing_minor"]))

        self.table.delete(*self.table.get_children())
        transactions = self.service.list_transactions({"date_from": start, "date_to": end})
        for transaction in sorted(transactions, key=lambda t: t.date, reverse=True)[:15]:
            self.table.insert(
                "", "end", iid=transaction.id, text=transaction.date,
                values=(
                    transaction.date,
                    transaction.description or "—",
                    transaction.category or "—",
                    transaction.account or "—",
                    transaction.transaction_type,
                    format_money(transaction.amount_minor),
                ),
            )

    # --------------------------------------------------
    # Tools
    # --------------------------------------------------

    def _open(self, factory):
        """Opens a tool window and refreshes this screen when it closes,
        so a transaction added in the ledger shows up here straight away."""

        try:
            window = factory(self.winfo_toplevel())
        except Exception as error:
            messagebox.showerror("Accounting", str(error))
            return None
        def on_closed(event):
            # Only the tool window's own destruction counts, and only if
            # this screen is still alive - closing the whole app tears both
            # down and refreshing dead widgets raises a TclError.
            if event.widget is window and self.winfo_exists():
                self.refresh()

        window.bind("<Destroy>", on_closed)
        return window

    def open_ledger(self):
        from modules.accounting.ledger_windows import LedgerWindow
        return self._open(LedgerWindow)

    def open_dashboard(self):
        from modules.accounting.ledger_windows import DashboardWindow
        return self._open(DashboardWindow)

    def open_bank_import(self):
        from modules.accounting.ledger_windows import BankImportWindow
        return self._open(BankImportWindow)

    def open_payments(self):
        from modules.accounting.ledger_windows import PaymentsWindow
        return self._open(PaymentsWindow)

    def open_invoices(self):
        from modules.accounting.ledger_windows import InvoicesWindow
        return self._open(InvoicesWindow)

    def open_categories(self):
        from modules.accounting.ledger_windows import CategoriesWindow
        return self._open(
            lambda parent: CategoriesWindow(parent, self.service, on_change=self.refresh)
        )

    def open_reports(self):
        from modules.accounting.ledger_windows import ReportsWindow
        return self._open(ReportsWindow)

    def open_statements(self):
        from modules.accounting.statements_windows import StatementsWindow
        return self._open(
            lambda parent: StatementsWindow(parent, statements_service=self.statements)
        )
