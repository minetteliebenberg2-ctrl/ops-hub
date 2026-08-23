# ==========================================================
# FC Hub - Financial Statements Windows
# ----------------------------------------------------------
# Purpose:
# Income statement, cash flow, balance sheet and bank
# reconciliation for a financial year, plus the screen where the
# balance-sheet accounts and their opening balances are kept.
#
# The layout deliberately mirrors the standalone Excel workbook
# (tools/build_accounting_workbook.py) - same statements, same
# March-to-February columns - so the two read the same way.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import getpass
from tkinter import messagebox, ttk

import customtkinter as ctk

from core.financial_statements import (
    FinancialStatementsService,
    current_financial_year,
    financial_year_label,
)
from core.balance_sheet_repository import ACCOUNT_TYPES
from gui.design_tokens import COLORS, FONTS, SPACING
from gui.flow_layout import reflow_widgets


def current_actor():
    try:
        return getpass.getuser()
    except Exception:
        return ""


def money(amount_minor):
    """Rands with a thousands separator; negatives in brackets, the way
    every accountant expects to read them."""

    if amount_minor is None:
        return ""
    value = amount_minor / 100.0
    if value < 0:
        return f"({abs(value):,.2f})"
    return f"{value:,.2f}"


def parse_money_minor(text):
    """Accepts '1500', '1,500.00', 'R1 500', '(250)' for negative, and an
    empty string for nil. Opening balances can legitimately be negative -
    an overdrawn account or a credit balance - so unlike the ledger's
    amount parser this one does not reject them."""

    cleaned = (text or "").strip().replace(",", "").replace("R", "").replace(" ", "")
    if not cleaned:
        return 0
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1]
    try:
        value = float(cleaned)
    except ValueError:
        raise ValueError(f"'{text}' is not a valid amount.")
    if negative:
        value = -value
    return round(value * 100)


class StatementsWindow(ctk.CTkToplevel):
    """Tabbed view of the four statements for one financial year."""

    def __init__(self, parent, statements_service=None):
        super().__init__(parent)

        self.service = statements_service or FinancialStatementsService()
        self.financial_year = current_financial_year()

        self.title("Financial Statements")
        self.minsize(1100, 640)
        self.configure(fg_color=COLORS["surface_primary"])

        self._build_header()

        self.tabs = ctk.CTkTabview(self, fg_color=COLORS["surface_primary"])
        self.tabs.pack(fill="both", expand=True, padx=SPACING["lg"], pady=(0, SPACING["lg"]))
        for name in ("Income Statement", "Cash Flow", "Balance Sheet", "Bank Reconciliation"):
            self.tabs.add(name)

        self.income_table = self._build_month_table(self.tabs.tab("Income Statement"))
        self.cash_table = self._build_month_table(self.tabs.tab("Cash Flow"))
        self.balance_table = self._build_balance_table(self.tabs.tab("Balance Sheet"))
        self.reconciliation_table = self._build_reconciliation_table(
            self.tabs.tab("Bank Reconciliation")
        )

        self.refresh()

    # --------------------------------------------------

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACING["lg"], pady=SPACING["lg"])

        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            titles,
            text="Financial Statements",
            font=FONTS["title_lg"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        self.subtitle = ctk.CTkLabel(
            titles,
            text="",
            font=FONTS["body_md"],
            text_color=COLORS["text_secondary"],
        )
        self.subtitle.pack(anchor="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right")

        ctk.CTkLabel(
            controls,
            text="Financial year",
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(0, SPACING["sm"]))

        years = self.service.available_financial_years()
        self.year_menu = ctk.CTkOptionMenu(
            controls,
            values=[financial_year_label(year) for year in years],
            command=self._on_year_changed,
            width=140,
        )
        self.year_menu.set(financial_year_label(self.financial_year))
        self.year_menu.pack(side="left", padx=(0, SPACING["md"]))
        self._years_by_label = {financial_year_label(year): year for year in years}

        ctk.CTkButton(
            controls,
            text="Balance Sheet Accounts",
            command=self.open_accounts,
            fg_color=COLORS["surface_secondary"],
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border_default"],
        ).pack(side="left", padx=(0, SPACING["sm"]))

        ctk.CTkButton(controls, text="Refresh", command=self.refresh).pack(side="left")

    def _build_month_table(self, parent):
        """Treeview with a label column plus the twelve months and a total."""

        columns = ("total",) + tuple(f"m{index}" for index in range(12))
        table = ttk.Treeview(parent, columns=columns, show="tree headings", height=22)
        table.heading("#0", text="")
        table.column("#0", width=250, stretch=True, anchor="w")
        table.heading("total", text="Year Total")
        table.column("total", width=110, anchor="e", stretch=False)
        for index in range(12):
            table.column(f"m{index}", width=92, anchor="e", stretch=False)

        scroll = ttk.Scrollbar(parent, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(parent, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)

        table.pack(side="top", fill="both", expand=True)
        horizontal.pack(side="bottom", fill="x")
        scroll.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")

        table.tag_configure("section", font=("Segoe UI", 10, "bold"))
        table.tag_configure("total", font=("Segoe UI", 10, "bold"))
        return table

    def _build_balance_table(self, parent):
        columns = ("opening", "movement", "closing", "source")
        table = ttk.Treeview(parent, columns=columns, show="tree headings", height=22)
        table.heading("#0", text="Account")
        table.column("#0", width=320, stretch=True, anchor="w")
        for column, title, width in (
            ("opening", "Opening", 130),
            ("movement", "Movement", 130),
            ("closing", "Closing", 130),
            ("source", "Movement from", 160),
        ):
            table.heading(column, text=title)
            table.column(column, width=width, anchor="e" if column != "source" else "w")

        table.pack(fill="both", expand=True)
        table.tag_configure("section", font=("Segoe UI", 10, "bold"))
        table.tag_configure("total", font=("Segoe UI", 10, "bold"))
        return table

    def _build_reconciliation_table(self, parent):
        columns = ("ledger", "statement", "difference", "status", "as_at")
        table = ttk.Treeview(parent, columns=columns, show="tree headings", height=12)
        table.heading("#0", text="Account")
        table.column("#0", width=280, stretch=True, anchor="w")
        for column, title, width, anchor in (
            ("ledger", "Ledger Balance", 140, "e"),
            ("statement", "Statement Balance", 150, "e"),
            ("difference", "Difference", 130, "e"),
            ("status", "Status", 130, "w"),
            ("as_at", "Statement Date", 130, "w"),
        ):
            table.heading(column, text=title)
            table.column(column, width=width, anchor=anchor)

        table.pack(fill="both", expand=True, padx=SPACING["md"], pady=SPACING["md"])

        ctk.CTkLabel(
            parent,
            text=(
                "The ledger balance covers every transaction ever recorded for the account, "
                "not just this financial year. A difference can mean a missing import - or "
                "simply that the ledger does not go back as far as the account does."
            ),
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=SPACING["md"], pady=(0, SPACING["md"]))
        return table

    # --------------------------------------------------

    def _on_year_changed(self, label):
        self.financial_year = self._years_by_label.get(label, self.financial_year)
        self.refresh()

    def refresh(self):
        self.subtitle.configure(
            text=f"{financial_year_label(self.financial_year)} — 1 March to 28/29 February"
        )
        self._refresh_income()
        self._refresh_cash_flow()
        self._refresh_balance_sheet()
        self._refresh_reconciliation()

    def _refresh_income(self):
        table = self.income_table
        table.delete(*table.get_children())

        result = self.service.income_statement(self.financial_year)
        for index, label in enumerate(result["months"]):
            table.heading(f"m{index}", text=label)

        def add_section(heading, lines, totals, total_minor):
            table.insert("", "end", text=heading, values=("",) * 13, tags=("section",))
            for line in lines:
                table.insert(
                    "", "end", text=f"   {line['name']}",
                    values=(money(line["total_minor"]),)
                           + tuple(money(value) for value in line["monthly_minor"]),
                )
            table.insert(
                "", "end", text=f"Total {heading}",
                values=(money(total_minor),) + tuple(money(value) for value in totals),
                tags=("total",),
            )
            table.insert("", "end", text="", values=("",) * 13)

        add_section("Income", result["income"],
                    result["income_total_monthly_minor"], result["income_total_minor"])
        add_section("Expenses", result["expenses"],
                    result["expense_total_monthly_minor"], result["expense_total_minor"])

        table.insert(
            "", "end", text="NET PROFIT / (LOSS)",
            values=(money(result["net_profit_minor"]),)
                   + tuple(money(value) for value in result["net_profit_monthly_minor"]),
            tags=("total",),
        )

    def _refresh_cash_flow(self):
        table = self.cash_table
        table.delete(*table.get_children())

        result = self.service.cash_flow(self.financial_year)
        for index, label in enumerate(result["months"]):
            table.heading(f"m{index}", text=label)

        rows = (
            ("Opening bank balance", result["opening_monthly_minor"], result["opening_minor"], ()),
            ("Receipts", result["receipts_monthly_minor"], result["receipts_minor"], ()),
            ("Payments", result["payments_monthly_minor"], result["payments_minor"], ()),
            ("Closing bank balance", result["closing_monthly_minor"], result["closing_minor"], ("total",)),
        )
        for label, monthly, total, tags in rows:
            table.insert(
                "", "end", text=label,
                values=(money(total),) + tuple(money(value) for value in monthly),
                tags=tags,
            )

        table.insert("", "end", text="", values=("",) * 13)
        table.insert(
            "", "end",
            text="Opening balance comes from the cash accounts on Balance Sheet Accounts.",
            values=("",) * 13,
        )

    def _refresh_balance_sheet(self):
        table = self.balance_table
        table.delete(*table.get_children())

        result = self.service.balance_sheet(self.financial_year)
        for group in result["groups"]:
            table.insert("", "end", text=group["group"], values=("", "", "", ""), tags=("section",))
            for line in group["lines"]:
                table.insert(
                    "", "end",
                    text=f"   {line['code']}  {line['name']}",
                    values=(
                        money(line["opening_minor"]),
                        money(line["movement_minor"]),
                        money(line["closing_minor"]),
                        "Ledger" if line["derived"] else "Entered",
                    ),
                )

        table.insert("", "end", text="", values=("", "", "", ""))
        table.insert(
            "", "end", text="Profit / (Loss) for the year",
            values=("", "", money(result["profit_for_year_minor"]), "Income Statement"),
            tags=("total",),
        )
        table.insert(
            "", "end", text="TOTAL ASSETS",
            values=("", "", money(result["total_assets_minor"]), ""), tags=("total",),
        )
        table.insert(
            "", "end", text="TOTAL LIABILITIES & EQUITY",
            values=("", "", money(result["total_equity_and_liabilities_minor"]), ""),
            tags=("total",),
        )
        table.insert(
            "", "end", text="Difference (should be nil)",
            values=(
                "", "",
                "Balanced" if result["balanced"] else money(result["difference_minor"]),
                "",
            ),
            tags=("total",),
        )

    def _refresh_reconciliation(self):
        table = self.reconciliation_table
        table.delete(*table.get_children())

        reconciliations = self.service.bank_reconciliations()
        if not reconciliations:
            table.insert(
                "", "end",
                text="No bank statement has been imported yet.",
                values=("", "", "", "", ""),
            )
            return

        for row in reconciliations:
            table.insert(
                "", "end", text=row["account"],
                values=(
                    money(row["ledger_balance_minor"]),
                    money(row["statement_balance_minor"]),
                    money(row["difference_minor"]),
                    "Reconciled" if row["reconciled"] else "Check",
                    row["statement_date"] or "",
                ),
            )

    # --------------------------------------------------

    def open_accounts(self):
        window = BalanceSheetAccountsWindow(
            self, self.service, self.financial_year, on_change=self.refresh
        )
        window.grab_set()


class BalanceSheetAccountsWindow(ctk.CTkToplevel):
    """The balance-sheet chart of accounts and this year's opening
    balances - the figures the ledger cannot supply on its own."""

    def __init__(self, parent, statements_service, financial_year, on_change=None):
        super().__init__(parent)

        self.service = statements_service
        self.repository = statements_service.balance_sheet_repository
        self.financial_year = financial_year
        self.on_change = on_change

        self.title(f"Balance Sheet Accounts — {financial_year_label(financial_year)}")
        self.minsize(980, 560)
        self.configure(fg_color=COLORS["surface_primary"])

        ctk.CTkLabel(
            self,
            text="Balance Sheet Accounts",
            font=FONTS["title_lg"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", padx=SPACING["lg"], pady=(SPACING["lg"], 0))

        ctk.CTkLabel(
            self,
            text=(
                "Opening balances are entered once at the start of the financial year. "
                "Link a cash account to a ledger account and its movement is worked out "
                "from the transactions; everything else stays as entered."
            ),
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"],
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["md"]))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=SPACING["lg"], pady=(0, SPACING["md"]))
        reflow_widgets(actions, [
            ctk.CTkButton(actions, text="New Account", command=self.new_account),
            ctk.CTkButton(actions, text="Edit Selected", command=self.edit_selected),
            ctk.CTkButton(actions, text="Set Opening Balance", command=self.set_opening_balance),
            ctk.CTkButton(actions, text="Retire Selected", command=self.retire_selected),
            ctk.CTkButton(actions, text="Close", command=self.destroy),
        ])

        columns = ("type", "group", "ledger_account", "cash", "opening")
        self.table = ttk.Treeview(self, columns=columns, show="tree headings", height=18)
        self.table.heading("#0", text="Code / Account")
        self.table.column("#0", width=320, stretch=True, anchor="w")
        for column, title, width, anchor in (
            ("type", "Type", 100, "w"),
            ("group", "Group", 180, "w"),
            ("ledger_account", "Ledger Account", 190, "w"),
            ("cash", "Cash", 60, "center"),
            ("opening", "Opening Balance", 140, "e"),
        ):
            self.table.heading(column, text=title)
            self.table.column(column, width=width, anchor=anchor)

        self.table.pack(fill="both", expand=True, padx=SPACING["lg"], pady=(0, SPACING["lg"]))
        self.table.bind("<Double-1>", lambda _event: self.set_opening_balance())

        self.refresh()

    # --------------------------------------------------

    def refresh(self):
        self.table.delete(*self.table.get_children())
        for account in self.repository.list_accounts(active_only=True):
            opening = self.repository.opening_balance_minor(account.id, self.financial_year)
            self.table.insert(
                "", "end", iid=account.id,
                text=f"{account.code}  {account.name}",
                values=(
                    account.account_type,
                    account.statement_group,
                    account.ledger_account or "—",
                    "Yes" if account.is_cash else "",
                    money(opening),
                ),
            )
        if self.on_change:
            self.on_change()

    def _selected(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showinfo("Select an account", "Select an account first.", parent=self)
            return None
        return self.repository.get_account(selection[0])

    def new_account(self):
        AccountDialog(self, self.repository, self.service, None, self.refresh).grab_set()

    def edit_selected(self):
        account = self._selected()
        if account:
            AccountDialog(self, self.repository, self.service, account, self.refresh).grab_set()

    def retire_selected(self):
        account = self._selected()
        if not account:
            return
        confirm = messagebox.askyesno(
            "Retire account",
            f"Retire '{account.name}'?\n\nIt stays on statements already produced, "
            "but stops appearing on new ones.",
            parent=self,
        )
        if confirm:
            self.repository.retire_account(account.id, current_actor())
            self.refresh()

    def set_opening_balance(self):
        account = self._selected()
        if not account:
            return

        current = self.repository.opening_balance_minor(account.id, self.financial_year)
        dialog = ctk.CTkInputDialog(
            title=f"Opening balance — {financial_year_label(self.financial_year)}",
            text=f"{account.name}\n\nOpening balance in Rands (brackets for negative):",
        )
        # CTkInputDialog has no way to pre-fill, so show the current value
        # in the prompt rather than silently losing it.
        value = dialog.get_input()
        if value is None:
            return
        try:
            amount_minor = parse_money_minor(value)
        except ValueError as error:
            messagebox.showerror("Opening balance", str(error), parent=self)
            return

        self.repository.set_opening_balance(
            account.id, self.financial_year, amount_minor, current_actor()
        )
        self.refresh()


class AccountDialog(ctk.CTkToplevel):
    """Create or edit one balance-sheet account."""

    def __init__(self, parent, repository, statements_service, account, on_saved):
        super().__init__(parent)

        self.repository = repository
        self.service = statements_service
        self.account = account
        self.on_saved = on_saved

        self.title("New Account" if account is None else "Edit Account")
        self.minsize(460, 420)
        self.configure(fg_color=COLORS["surface_primary"])

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=SPACING["lg"], pady=SPACING["lg"])

        self.code = self._field(body, "Code", account.code if account else "")
        self.name = self._field(body, "Account name", account.name if account else "")

        ctk.CTkLabel(body, text="Type", font=FONTS["body_sm"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.account_type = ctk.CTkOptionMenu(body, values=list(ACCOUNT_TYPES))
        self.account_type.set(account.account_type if account else ACCOUNT_TYPES[0])
        self.account_type.pack(fill="x", pady=(0, SPACING["md"]))

        self.group = self._field(
            body, "Statement group (e.g. Current Assets)",
            account.statement_group if account else "",
        )

        ctk.CTkLabel(body, text="Ledger account (cash accounts only)", font=FONTS["body_sm"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w")
        ledger_accounts = ["—"] + list(self.service.ledger_service.list_accounts())
        self.ledger_account = ctk.CTkOptionMenu(body, values=ledger_accounts)
        self.ledger_account.set(
            account.ledger_account if account and account.ledger_account else "—"
        )
        self.ledger_account.pack(fill="x", pady=(0, SPACING["md"]))

        self.is_cash = ctk.CTkCheckBox(body, text="This is a cash / bank account")
        if account and account.is_cash:
            self.is_cash.select()
        self.is_cash.pack(anchor="w", pady=(0, SPACING["lg"]))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x")
        ctk.CTkButton(buttons, text="Save", command=self.save).pack(side="left")
        ctk.CTkButton(
            buttons, text="Cancel", command=self.destroy,
            fg_color=COLORS["surface_secondary"], text_color=COLORS["text_primary"],
            border_width=1, border_color=COLORS["border_default"],
        ).pack(side="left", padx=SPACING["sm"])

    def _field(self, parent, label, value):
        ctk.CTkLabel(parent, text=label, font=FONTS["body_sm"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w")
        entry = ctk.CTkEntry(parent)
        entry.insert(0, value or "")
        entry.pack(fill="x", pady=(0, SPACING["md"]))
        return entry

    def save(self):
        name = self.name.get().strip()
        if not name:
            messagebox.showerror("Account", "Enter an account name.", parent=self)
            return

        from core.balance_sheet_repository import BalanceSheetAccount

        account = self.account or BalanceSheetAccount()
        account.code = self.code.get().strip()
        account.name = name
        account.account_type = self.account_type.get()
        account.statement_group = self.group.get().strip() or account.account_type
        ledger_account = self.ledger_account.get()
        account.ledger_account = "" if ledger_account == "—" else ledger_account
        account.is_cash = 1 if self.is_cash.get() else 0

        self.repository.save_account(account, current_actor())
        if self.on_saved:
            self.on_saved()
        self.destroy()
