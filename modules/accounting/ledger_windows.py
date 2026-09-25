# ==========================================================
# FC Hub - Accounting Windows
# ----------------------------------------------------------
# Purpose:
# Financial dashboard, transaction ledger, bank statement import, and
# reporting - backed by the real database (core/ledger_service.py),
# personal and business, full financial year.
#
# Author: Minette & James
# Version: 2.0
# ==========================================================

from datetime import date, datetime
import getpass
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from gui.components.date_picker import DateEntry
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.ticker import FuncFormatter

    MATPLOTLIB_AVAILABLE = True
except ImportError:  # pragma: no cover - only hit on an incomplete install
    # Charts are a nicety; the ledger, imports, reports and payments are
    # not. A missing matplotlib used to raise at import time and take the
    # whole Accounting module down with it - every button did nothing.
    Figure = FigureCanvasTkAgg = FuncFormatter = None
    MATPLOTLIB_AVAILABLE = False

from core.app_paths import get_assets_dir
from core.bank_statement_parser import BankStatementParseError
from core.crm_service import CRMService
from core.ledger_service import EXPENSE_CATEGORIES, INCOME_CATEGORIES, LedgerService
from core.merchant_key import merchant_key
from core.ledger_transaction import EXPENSE, INCOME
from core.payment_service import PaymentService
from core.quote_pdf import format_money
from gui.entity_table import build_entity_table


def current_actor():

    try:
        return getpass.getuser()
    except Exception:
        return ""


def parse_amount_minor(text):
    """Parse a Rand amount like '1500.00' or '1,500' into integer cents."""

    cleaned = text.strip().replace(",", "").replace("R", "").strip()
    if not cleaned:
        raise ValueError("Enter an amount.")
    try:
        value = float(cleaned)
    except ValueError:
        raise ValueError("Enter a valid amount.")
    if value <= 0:
        raise ValueError("Amount must be greater than zero.")
    return round(value * 100)


from gui.design_tokens import COLORS

THEME_DARK_GREY = COLORS["surface_primary"]
THEME_SURFACE = COLORS["surface_secondary"]
THEME_SURFACE_LIGHT = COLORS["surface_tertiary"]
THEME_TEXT_PRIMARY = COLORS["text_primary"]
THEME_TEXT_SECONDARY = COLORS["text_secondary"]

GOOD_COLOR = "#00AA00"
NEUTRAL_COLOR = COLORS["accent_primary"]
WARN_COLOR = "#CC6600"

# Same accent green as the document/PDF design system (see
# document_design_system) - the charts here should read as the same
# product as the quotes/invoices, not a different app bolted on.
BRAND_GREEN = COLORS["accent_primary"]


# --------------------------------------------------
# Chart helpers - small, dark-theme-matched matplotlib embeds. No chart
# library existed in this app before; kept deliberately minimal (bar
# charts only) rather than pulling in a whole dashboard framework.
# --------------------------------------------------

def _register_lato():
    """Registers the same Lato family used in the PDF documents (see
    document_design_system) with matplotlib, so charts read as the
    same product as quotes/invoices rather than a generic default
    font. Falls back to matplotlib's default silently if the fonts
    aren't found - cosmetic only, never worth crashing the app over."""

    try:
        from matplotlib import font_manager

        fonts_dir = get_assets_dir() / "fonts"
        for filename in ("Lato-Regular.ttf", "Lato-Bold.ttf", "Lato-Italic.ttf", "Lato-BoldItalic.ttf"):
            path = fonts_dir / filename
            if path.exists():
                font_manager.fontManager.addfont(str(path))
        return "Lato"
    except Exception:
        return "sans-serif"


CHART_FONT = _register_lato()

# A single-transaction month shouldn't render as one giant bar filling
# the whole chart width - reserve room for at least this many month
# slots even when there's less real data than that yet, so early
# months in a young ledger don't look artificially huge.
MIN_MONTH_SLOTS = 6
MIN_CATEGORY_SLOTS = 6


def _style_chart(fig, ax):

    fig.patch.set_facecolor(THEME_SURFACE)
    ax.set_facecolor(THEME_SURFACE)
    ax.tick_params(colors=THEME_TEXT_SECONDARY, labelsize=9)
    ax.title.set_color(THEME_TEXT_PRIMARY)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color=THEME_SURFACE_LIGHT, linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily(CHART_FONT)


def _rand_axis_formatter():
    """Compact axis labels - "R15,000" not "15000.0" - readable at a
    glance instead of raw floats."""

    return FuncFormatter(lambda value, _pos: f"R{value:,.0f}")


def _empty_state(parent, text):

    ctk.CTkLabel(
        parent, text=text, text_color=THEME_TEXT_SECONDARY, wraplength=320, justify="center",
    ).pack(expand=True, pady=40)


def _short_month_label(month_key):
    """"2026-08" -> "Aug '26" - short enough that a year of months
    doesn't need steep rotation to fit."""

    try:
        return datetime.strptime(month_key, "%Y-%m").strftime("%b '%y")
    except ValueError:
        return month_key


def _month_label(month_key):
    """'2026-08' -> 'Aug 2026' for the month filter dropdown."""
    try:
        return datetime.strptime(month_key, "%Y-%m").strftime("%b %Y")
    except ValueError:
        return month_key


def _month_prefix(label):
    """'Aug 2026' -> '2026-08' for transaction date filtering."""
    try:
        return datetime.strptime(label, "%b %Y").strftime("%Y-%m")
    except ValueError:
        return None


DONUT_COLORS = [
    "#2A78D6", "#EB6834", "#1BAF7A", "#EDA100", "#E87BA4",
    "#008300", "#4A3AA7", "#898781",
]


def build_expense_donut_chart(parent, by_category):
    """Donut chart showing expense breakdown by category."""

    expense_items = {}
    for key, amount in by_category.items():
        if key.startswith("Expense/"):
            cat = key.split("/", 1)[1]
            expense_items[cat] = expense_items.get(cat, 0) + amount

    if not expense_items:
        _empty_state(parent, "No expenses yet.")
        return

    ordered = sorted(expense_items.items(), key=lambda x: x[1], reverse=True)
    top = ordered[:7]
    other = sum(v for _, v in ordered[7:])
    if other > 0:
        top.append(("Other", other))

    labels = [l if len(l) <= 22 else l[:20] + "…" for l, _ in top]
    values = [v / 100 for _, v in top]
    colors = DONUT_COLORS[:len(top)]
    total = sum(values)

    if not MATPLOTLIB_AVAILABLE:
        _empty_state(parent, "Charts are unavailable on this install.")
        return

    fig = Figure(figsize=(4, 3.4), dpi=100)
    ax = fig.add_subplot(111)
    wedges, _ = ax.pie(
        values, colors=colors, startangle=90, counterclock=False,
        wedgeprops={"width": 0.45, "edgecolor": THEME_SURFACE, "linewidth": 1.5},
    )
    ax.set_aspect("equal")

    legend_labels = [f"{l}  {v / total * 100:.0f}%" for l, v in zip(labels, values)]
    legend = ax.legend(
        wedges, legend_labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
        fontsize=8, frameon=False, labelspacing=0.8,
    )
    for text in legend.get_texts():
        text.set_color(THEME_TEXT_PRIMARY)
        text.set_fontfamily(CHART_FONT)

    fig.patch.set_facecolor(THEME_SURFACE)
    fig.tight_layout(pad=0.5)

    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


def build_monthly_trend_chart(parent, by_month):
    """Grouped bar chart: Income vs Expenses per month (YYYY-MM keys)."""

    if not by_month:
        _empty_state(parent, "No transactions yet — import a bank statement or add one manually.")
        return

    months = list(by_month.keys())
    income_vals = [by_month[m].get("Income", 0) / 100 for m in months]
    expense_vals = [by_month[m].get("Expense", 0) / 100 for m in months]

    if not MATPLOTLIB_AVAILABLE:
        _empty_state(parent, "Charts are unavailable on this install.")
        return

    fig = Figure(figsize=(5.5, 3.4), dpi=100)
    ax = fig.add_subplot(111)
    positions = range(len(months))
    # A bar width proportional to how many months are actually on
    # screen, capped so a chart with only one or two months doesn't
    # render one enormous block - this is what made the chart look
    # "very wide" with only a little data in it.
    width = min(0.35, 2.2 / max(len(months), MIN_MONTH_SLOTS))
    ax.bar([p - width / 2 for p in positions], income_vals, width, label="Income", color=BRAND_GREEN)
    ax.bar([p + width / 2 for p in positions], expense_vals, width, label="Expenses", color=WARN_COLOR)
    ax.set_xticks(list(positions))
    ax.set_xticklabels([_short_month_label(m) for m in months], rotation=0, ha="center", fontsize=9)
    ax.set_xlim(-0.7, max(len(months), MIN_MONTH_SLOTS) - 0.3)
    ax.yaxis.set_major_formatter(_rand_axis_formatter())
    # Above the plot, not inside it - a tall bar (e.g. one strong
    # income month next to quiet ones) would otherwise sit right
    # behind an in-plot legend and make it unreadable.
    legend = ax.legend(
        fontsize=9, facecolor=THEME_SURFACE, edgecolor=THEME_SURFACE_LIGHT,
        loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2, frameon=False,
    )
    for text in legend.get_texts():
        text.set_color(THEME_TEXT_PRIMARY)
        text.set_fontfamily(CHART_FONT)
    _style_chart(fig, ax)
    fig.tight_layout(pad=1.2)

    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


def build_category_breakdown_chart(parent, totals_minor, title, color):
    """Horizontal bar chart for a category -> amount breakdown."""

    if not totals_minor:
        _empty_state(parent, "No transactions in this category yet.")
        return

    ordered = sorted(totals_minor.items(), key=lambda item: item[1], reverse=True)[:10]
    # Longest category names in her chart of accounts run long
    # ("Personal Expenses through Business Accounts") - truncate the
    # label, not the bar, so the chart doesn't get squeezed to make
    # room for text.
    labels = [label if len(label) <= 28 else label[:26] + "…" for label, _ in ordered]
    values = [amount / 100 for _, amount in ordered]

    if not MATPLOTLIB_AVAILABLE:
        _empty_state(parent, "Charts are unavailable on this install.")
        return

    fig = Figure(figsize=(5.5, 3.8), dpi=100)
    ax = fig.add_subplot(111)
    height = min(0.6, 3.5 / max(len(ordered), MIN_CATEGORY_SLOTS))
    ax.barh(labels, values, height=height, color=color)
    ax.invert_yaxis()
    ax.set_ylim(max(len(ordered), MIN_CATEGORY_SLOTS) - 0.5, -0.5)
    ax.set_title(title, fontsize=11, fontfamily=CHART_FONT, pad=10)
    ax.xaxis.set_major_formatter(_rand_axis_formatter())
    ax.tick_params(axis="y", labelsize=9)
    _style_chart(fig, ax)
    fig.tight_layout(pad=1.2)

    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


class AccountingHub(ctk.CTkToplevel):
    """Dockable hub launcher for Accounting utilities"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Accounting Hub")
        self.minsize(460, 620)
        self.resizable(True, True)
        self.configure(fg_color=THEME_DARK_GREY)

        ctk.CTkLabel(
            self,
            text="Accounting Hub",
            font=("Segoe UI", 24, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(20, 30))

        ctk.CTkLabel(
            self,
            text="Manage financial data, transactions, and generate reports.",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
        ).pack(pady=(0, 30), padx=20)

        button_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        button_frame.pack(pady=20, padx=20, fill="both", expand=True)

        buttons = [
            ("📊 Dashboard", self.open_dashboard),
            ("📋 Transaction Ledger", self.open_ledger),
            ("💳 Payments", self.open_payments),
            ("🧾 Invoices", self.open_invoices),
            ("🏦 Import Bank Statement", self.open_import),
            ("📈 Reports", self.open_reports),
            ("🏷️ Categories", self.open_categories),
            ("🏦 Manage Accounts", self.open_accounts),
            ("⚙️ Settings", self.open_settings),
        ]

        for label, command in buttons:
            ctk.CTkButton(
                button_frame,
                text=label,
                command=command,
                height=40,
                font=("Segoe UI", 12),
                fg_color=NEUTRAL_COLOR,
                hover_color=COLORS["accent_hover"],
            ).pack(pady=5, fill="x")

        ctk.CTkButton(
            self,
            text="Close Hub",
            command=self.destroy,
            width=200,
            fg_color=COLORS["button_secondary"],
            hover_color=COLORS["button_secondary_hover"],
        ).pack(pady=(0, 20))

        # Size to what the content actually needs (capped to the screen)
        # rather than a hardcoded guess - the old fixed 500x420 clipped
        # the Invoices button and the non-resizable window left no way to
        # reach it. Recomputed here so adding a ninth utility later can
        # never silently hide itself again.
        self.update_idletasks()
        needed_height = min(self.winfo_reqheight() + 10, int(self.winfo_screenheight() * 0.9))
        self.geometry(f"500x{needed_height}")

        self.dashboard_window = None
        self.ledger_window = None
        self.payments_window = None
        self.invoices_window = None
        self.import_window = None
        self.reports_window = None
        self.open_windows = set()

    def open_dashboard(self):
        if self.dashboard_window is None or not self.dashboard_window.winfo_exists():
            self.dashboard_window = DashboardWindow(self)
        else:
            self.dashboard_window.lift()
            self.dashboard_window.focus()

    def open_ledger(self):
        if self.ledger_window is None or not self.ledger_window.winfo_exists():
            self.ledger_window = LedgerWindow(self)
        else:
            self.ledger_window.lift()
            self.ledger_window.focus()

    def open_payments(self):
        if self.payments_window is None or not self.payments_window.winfo_exists():
            self.payments_window = PaymentsWindow(self)
        else:
            self.payments_window.lift()
            self.payments_window.focus()

    def open_invoices(self):
        if self.invoices_window is None or not self.invoices_window.winfo_exists():
            self.invoices_window = InvoicesWindow(self)
        else:
            self.invoices_window.lift()
            self.invoices_window.focus()

    def open_import(self):
        if self.import_window is None or not self.import_window.winfo_exists():
            self.import_window = BankImportWindow(self)
        else:
            self.import_window.lift()
            self.import_window.focus()

    def open_reports(self):
        if self.reports_window is None or not self.reports_window.winfo_exists():
            self.reports_window = ReportsWindow(self)
        else:
            self.reports_window.lift()
            self.reports_window.focus()

    def open_categories(self):
        CategoriesWindow(self, LedgerService(), on_change=None)

    def open_accounts(self):
        ManageAccountsWindow(self)

    def open_settings(self):
        messagebox.showinfo("Settings", "Settings (placeholder)")


class ManageAccountsWindow(ctk.CTkToplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Manage Bank Accounts")
        self.geometry("400x500")
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)

        self.service = LedgerService()

        ctk.CTkLabel(
            self, text="Bank Accounts", font=("Segoe UI", 16, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(15, 10))

        add_frame = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        add_frame.pack(fill="x", padx=15, pady=(0, 10))
        ctk.CTkLabel(add_frame, text="New account name:", text_color=THEME_TEXT_SECONDARY).pack(side="left", padx=(10, 5), pady=10)
        self.name_var = tk.StringVar()
        self.name_entry = ctk.CTkEntry(add_frame, textvariable=self.name_var, width=180)
        self.name_entry.pack(side="left", padx=5, pady=10)
        ctk.CTkButton(
            add_frame, text="Add", width=60, command=self._add_account,
            fg_color=BRAND_GREEN, hover_color=COLORS["accent_hover"],
        ).pack(side="left", padx=(5, 10), pady=10)

        list_frame = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.account_list = tk.Listbox(list_frame, font=("Segoe UI", 11), selectmode="single")
        self.account_list.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkButton(
            self, text="Close", command=self.destroy, width=120,
            fg_color=COLORS["button_secondary"], hover_color=COLORS["button_secondary_hover"],
        ).pack(pady=(0, 15))

        self._refresh()

    def _refresh(self):
        self.account_list.delete(0, "end")
        for name in self.service.list_accounts():
            self.account_list.insert("end", name)

    def _add_account(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Add Account", "Enter an account name.", parent=self)
            return
        try:
            self.service.add_account(name)
            self.name_var.set("")
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)


class DashboardWindow(ctk.CTkToplevel):
    """Real financial dashboard - KPI cards, a monthly Income vs
    Expenses chart, and recent transactions, all backed by the
    database (core/ledger_service.py). Personal and business
    transactions live side by side, filtered by account elsewhere
    (Ledger); the dashboard itself shows the combined picture."""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Accounting Dashboard")
        self.geometry("1400x750")
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)

        # Belt-and-braces on top of the site-wide gui/window_focus.py
        # fix - a crash partway through building this window's UI was
        # interrupting that fix's timing and leaving the window stuck
        # behind its parent. The crash is fixed too, but this stays as
        # a safety net.
        self.lift()
        self.focus_force()
        self.after(50, lambda: (self.lift(), self.focus_force()))

        self.service = LedgerService()
        self.metric_cards = {}
        self.chart_frame = None
        self.recent_table = None

        self._build_ui()
        self.refresh()

    def _build_ui(self):

        main_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        header_row = ctk.CTkFrame(main_frame, fg_color=THEME_DARK_GREY)
        header_row.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(
            header_row, text="Financial Dashboard", font=("Segoe UI", 18, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="left")
        ctk.CTkButton(header_row, text="Refresh", command=self.refresh, width=90).pack(side="right", padx=4)
        ctk.CTkButton(
            header_row, text="Import Bank Statement", command=self.import_statement, width=170,
            fg_color=BRAND_GREEN, hover_color=COLORS["accent_hover"], text_color="#FFFFFF",
        ).pack(side="right", padx=4)
        ctk.CTkButton(header_row, text="Add Transaction", command=self.add_transaction, width=140).pack(side="right", padx=4)

        metrics_frame = ctk.CTkFrame(main_frame, fg_color=THEME_DARK_GREY)
        metrics_frame.pack(fill="x", pady=(0, 15))

        self.metric_cards["income"] = self._create_metric_card(metrics_frame, "Total Income", "R 0.00", GOOD_COLOR)
        self.metric_cards["income"].pack(side="left", padx=(0, 10), fill="x", expand=True)

        self.metric_cards["expenses"] = self._create_metric_card(metrics_frame, "Total Expenses", "R 0.00", WARN_COLOR)
        self.metric_cards["expenses"].pack(side="left", padx=10, fill="x", expand=True)

        self.metric_cards["profit"] = self._create_metric_card(metrics_frame, "Net Profit", "R 0.00", GOOD_COLOR)
        self.metric_cards["profit"].pack(side="left", padx=(10, 0), fill="x", expand=True)

        content_row = ctk.CTkFrame(main_frame, fg_color=THEME_DARK_GREY)
        content_row.pack(fill="both", expand=True)
        content_row.grid_columnconfigure(0, weight=2)
        content_row.grid_columnconfigure(1, weight=2)
        content_row.grid_columnconfigure(2, weight=2)
        content_row.grid_rowconfigure(0, weight=1)

        pie_container = ctk.CTkFrame(content_row, fg_color=THEME_SURFACE)
        pie_container.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ctk.CTkLabel(
            pie_container, text="Expense Breakdown", font=("Segoe UI", 12, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(10, 5), padx=10, anchor="w")
        self.pie_frame = ctk.CTkFrame(pie_container, fg_color=THEME_SURFACE)
        self.pie_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        bar_container = ctk.CTkFrame(content_row, fg_color=THEME_SURFACE)
        bar_container.grid(row=0, column=1, sticky="nsew", padx=(5, 5))
        ctk.CTkLabel(
            bar_container, text="Income vs Expenses by Month", font=("Segoe UI", 12, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(10, 5), padx=10, anchor="w")
        self.chart_frame = ctk.CTkFrame(bar_container, fg_color=THEME_SURFACE)
        self.chart_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        recent_container = ctk.CTkFrame(content_row, fg_color=THEME_SURFACE)
        recent_container.grid(row=0, column=2, sticky="nsew")
        ctk.CTkLabel(
            recent_container, text="Recent Transactions", font=("Segoe UI", 12, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(10, 5), padx=10, anchor="w")
        # build_entity_table grids its own children into whatever
        # parent it's given - it must be a frame with nothing already
        # packed into it, or Tkinter raises "cannot use geometry
        # manager grid ... already has slaves managed by pack". Giving
        # it this fresh wrapper (a sibling of the label above, not the
        # same frame) keeps the two geometry managers apart.
        table_wrapper = ctk.CTkFrame(recent_container, fg_color=THEME_SURFACE)
        table_wrapper.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.recent_table = build_entity_table(
            table_wrapper, ("Type", "Category", "Amount"), (), height=14,
        )

        self.stats_label = ctk.CTkLabel(
            main_frame, text="", font=("Segoe UI", 10), text_color=THEME_TEXT_SECONDARY,
        )
        self.stats_label.pack(fill="x", pady=(10, 0))

    def _create_metric_card(self, parent, title, value, color):

        card = ctk.CTkFrame(parent, fg_color=THEME_SURFACE, border_color=color, border_width=2)
        ctk.CTkLabel(card, text=title, font=("Segoe UI", 10), text_color=THEME_TEXT_SECONDARY).pack(pady=(10, 5))
        value_label = ctk.CTkLabel(card, text=value, font=("Segoe UI", 16, "bold"), text_color=color)
        value_label.pack(pady=(0, 10))
        card.value_label = value_label
        return card

    def refresh(self):

        summary = self.service.get_summary()

        self.metric_cards["income"].value_label.configure(text=format_money(summary["total_income_minor"]))
        self.metric_cards["expenses"].value_label.configure(text=format_money(summary["total_expenses_minor"]))

        profit_color = GOOD_COLOR if summary["net_profit_minor"] >= 0 else WARN_COLOR
        self.metric_cards["profit"].value_label.configure(
            text=format_money(summary["net_profit_minor"]), text_color=profit_color,
        )

        accounts = self.service.list_accounts()
        self.stats_label.configure(
            text=f"Transactions: {summary['transaction_count']} | Accounts: {', '.join(accounts) or 'None yet'}"
        )

        for child in self.pie_frame.winfo_children():
            child.destroy()
        build_expense_donut_chart(self.pie_frame, summary["by_category"])

        for child in self.chart_frame.winfo_children():
            child.destroy()
        build_monthly_trend_chart(self.chart_frame, summary["by_month"])

        self.recent_table.delete(*self.recent_table.get_children())
        for transaction in self.service.list_transactions()[:20]:
            self.recent_table.insert(
                "", "end", iid=transaction.id, text=transaction.date,
                values=(
                    transaction.transaction_type,
                    transaction.category or "(Uncategorized)",
                    format_money(transaction.amount_minor),
                ),
            )

    def add_transaction(self):

        AddTransactionDialog(self, self.service, on_saved=self.refresh)

    def import_statement(self):

        BankImportWindow(self, on_saved=self.refresh)


class LedgerWindow(ctk.CTkToplevel):
    """The full transaction ledger - every manually entered and
    bank-imported transaction, filterable by account/type/category,
    with an Excel-like inline-editable grid (click a cell to edit
    Date/Description/Category/Amount directly), Undo, receipt
    attachment, and export to Excel/CSV."""

    # Columns match build_entity_table's `columns` tuple 1:1, so
    # Treeview column id "#1" is "Date", "#2" is "Description", etc.
    # (#0 is the tree column, showing the same date for a quick visual
    # anchor - left alone, not editable).
    COLUMNS = ("Date", "Description", "Type", "Category", "Account", "Amount", "Source")
    EDITABLE_COLUMNS = ("Date", "Description", "Category", "Amount")

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Transaction Ledger")
        self.geometry("1400x900")
        self.configure(fg_color=THEME_DARK_GREY)

        self.service = LedgerService()
        self._all_accounts = ["All Accounts"]
        self._all_categories = ["All Categories"]
        self._all_months = ["All Months"]
        self._transactions_by_id = {}
        self._editor = None  # active inline-edit overlay widget, if any
        self._sort_by_category = False

        self._build_ui()
        self.refresh()

    def _build_ui(self):

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header_row = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        header_row.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        ctk.CTkLabel(
            header_row, text="Transaction Ledger", font=("Segoe UI", 18, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="left")
        self.status_label = ctk.CTkLabel(
            header_row, text="Click any Date, Description, Category, or Amount cell to edit it.",
            text_color=THEME_TEXT_SECONDARY, font=("Segoe UI", 10),
        )
        self.status_label.pack(side="left", padx=20)

        filter_frame = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        filter_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkLabel(filter_frame, text="Filter:", text_color=THEME_TEXT_SECONDARY).pack(side="left", padx=(10, 5), pady=10)

        self.type_var = ctk.StringVar(value="All Types")
        ctk.CTkOptionMenu(
            filter_frame, variable=self.type_var, values=["All Types", INCOME, EXPENSE],
            command=lambda _v: self.refresh(),
        ).pack(side="left", padx=5)

        # ttk.Combobox, not CTkOptionMenu, for Account/Category -
        # CTkOptionMenu's dropdown crashes on mouse-wheel scroll once
        # it has enough items to need scrolling (a real customtkinter
        # bug: its scroll handler receives a Tk widget path string
        # instead of a widget object and blows up on `.master`). With
        # 45 real categories that made most of the list unreachable
        # and looked like categories had gone missing. ttk.Combobox's
        # native dropdown scrolls correctly and needs no workaround.
        self.account_var = ctk.StringVar(value="All Accounts")
        self.account_menu = ttk.Combobox(
            filter_frame, textvariable=self.account_var, values=self._all_accounts,
            state="readonly", width=22,
        )
        self.account_menu.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.account_menu.pack(side="left", padx=5)

        self.category_var = ctk.StringVar(value="All Categories")
        self.category_menu = ttk.Combobox(
            filter_frame, textvariable=self.category_var, values=self._all_categories,
            state="readonly", width=32,
        )
        self.category_menu.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.category_menu.pack(side="left", padx=5)

        self.month_var = ctk.StringVar(value="All Months")
        self.month_menu = ttk.Combobox(
            filter_frame, textvariable=self.month_var, values=self._all_months,
            state="readonly", width=14,
        )
        self.month_menu.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.month_menu.pack(side="left", padx=5)

        self.sort_cat_btn = ctk.CTkButton(
            filter_frame, text="Sort: Date", command=self._toggle_sort, width=110,
        )
        self.sort_cat_btn.pack(side="left", padx=5)

        ctk.CTkButton(
            filter_frame, text="Undo Last Edit", command=self.undo_last_edit, width=130,
            fg_color=NEUTRAL_COLOR, hover_color=COLORS["accent_hover"],
        ).pack(side="right", padx=(5, 10), pady=10)
        ctk.CTkButton(
            filter_frame, text="Manage Categories", command=self.manage_categories, width=140,
        ).pack(side="right", padx=5, pady=10)
        ctk.CTkButton(
            filter_frame, text="Export to Excel", command=self.export_to_excel, width=130,
        ).pack(side="right", padx=5, pady=10)
        ctk.CTkButton(
            filter_frame, text="View Receipt", command=self.view_receipt, width=110,
        ).pack(side="right", padx=5, pady=10)
        ctk.CTkButton(
            filter_frame, text="Attach Receipt", command=self.attach_receipt, width=120,
        ).pack(side="right", padx=5, pady=10)

        table_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.table = build_entity_table(
            table_frame,
            self.COLUMNS,
            (
                ("Refresh", self.refresh),
                ("Add Transaction", self.add_transaction),
                ("Delete", self.delete_transaction),
            ),
        )
        self.table.bind("<Button-1>", self._on_cell_click)
        self.table.bind("<<TreeviewSelect>>", self._on_select_changed, add="+")

        # Reconciliation panel - closing balance only (confirmed scope),
        # picked account, ledger total, statement total, and the
        # difference between them.
        self.recon_frame = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        self.recon_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        ctk.CTkLabel(
            self.recon_frame, text="Reconciliation:", font=("Segoe UI", 11, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="left", padx=(10, 5), pady=8)
        self.recon_account_var = ctk.StringVar(value="All Accounts")
        self.recon_account_menu = ctk.CTkOptionMenu(
            self.recon_frame, variable=self.recon_account_var, values=["All Accounts"],
            command=lambda _v: self._refresh_reconciliation(), width=180,
        )
        self.recon_account_menu.pack(side="left", padx=5)
        self.recon_label = ctk.CTkLabel(self.recon_frame, text="", text_color=THEME_TEXT_SECONDARY)
        self.recon_label.pack(side="left", padx=15)

        self.grid_rowconfigure(3, weight=0)

    # --------------------------------------------------
    # Load / refresh
    # --------------------------------------------------

    def refresh(self):

        self._destroy_editor()

        self._all_accounts = ["All Accounts"] + self.service.list_accounts()
        self._all_categories = ["All Categories"] + self.service.list_categories(active_only=False)
        self.account_menu.configure(values=self._all_accounts)
        self.category_menu.configure(values=self._all_categories)
        self.recon_account_menu.configure(values=self._all_accounts)

        filters = {}
        if self.type_var.get() != "All Types":
            filters["transaction_type"] = self.type_var.get()
        if self.account_var.get() != "All Accounts":
            filters["account"] = self.account_var.get()
        if self.category_var.get() != "All Categories":
            filters["category"] = self.category_var.get()

        transactions = list(self.service.list_transactions(filters))

        # Build month list from all loaded transactions (before month filter)
        months_seen = sorted({t.date[:7] for t in transactions}, reverse=True)
        self._all_months = ["All Months"] + [_month_label(m) for m in months_seen]
        self.month_menu.configure(values=self._all_months)

        # Month filter (applied client-side — date_from/to in filters would
        # need exact boundaries; matching on YYYY-MM prefix is simpler)
        selected_month = self.month_var.get()
        if selected_month != "All Months":
            month_prefix = _month_prefix(selected_month)
            if month_prefix:
                transactions = [t for t in transactions if t.date.startswith(month_prefix)]

        # Sort
        if self._sort_by_category:
            transactions.sort(key=lambda t: (t.category or "").lower())

        self.table.delete(*self.table.get_children())
        self._transactions_by_id = {}
        for transaction in transactions:
            self._transactions_by_id[transaction.id] = transaction
            self.table.insert(
                "", "end", iid=transaction.id, text=transaction.date,
                values=self._row_values(transaction),
            )

        self._refresh_reconciliation()

    def _row_values(self, transaction):

        description = transaction.description
        if transaction.receipt_filename:
            description = f"\U0001F4CE {description}"
        return (
            transaction.date,
            description,
            transaction.transaction_type,
            transaction.category or "(Uncategorized)",
            transaction.account,
            format_money(transaction.amount_minor),
            transaction.source,
        )

    def _refresh_reconciliation(self):

        account = self.recon_account_var.get()
        if account == "All Accounts":
            self.recon_label.configure(text="Pick an account to see its reconciliation.")
            return

        recon = self.service.get_reconciliation(account)
        if recon is None:
            self.recon_label.configure(text=f'No bank import for "{account}" yet - reconciliation unavailable.')
            return

        color = GOOD_COLOR if abs(recon["difference_minor"]) <= 5 else WARN_COLOR
        self.recon_label.configure(
            text=(
                f"Ledger: {format_money(recon['ledger_balance_minor'])}   "
                f"Statement ({recon['statement_date']}): {format_money(recon['statement_balance_minor'])}   "
                f"Difference: {format_money(recon['difference_minor'])}"
            ),
            text_color=color,
        )

    # --------------------------------------------------
    # Selection helpers
    # --------------------------------------------------

    def _selected_id(self):

        selection = self.table.selection()
        if not selection:
            messagebox.showwarning("Ledger", "Select a transaction first.", parent=self)
            return None
        return selection[0]

    def _on_select_changed(self, _event=None):

        self._destroy_editor()

    def add_transaction(self):

        AddTransactionDialog(self, self.service, on_saved=self.refresh)

    def delete_transaction(self):

        transaction_id = self._selected_id()
        if transaction_id is None:
            return
        if not messagebox.askyesno("Delete Transaction", "Delete this transaction permanently?", parent=self):
            return
        self.service.delete_transaction(transaction_id)
        self.refresh()

    def _toggle_sort(self):
        self._sort_by_category = not self._sort_by_category
        self.sort_cat_btn.configure(text="Sort: Category" if self._sort_by_category else "Sort: Date")
        self.refresh()

    def undo_last_edit(self):

        try:
            result = self.service.undo_last_edit(current_actor())
        except ValueError as error:
            self.status_label.configure(text=str(error), text_color=WARN_COLOR)
            return

        self.refresh()
        self.status_label.configure(
            text=f"Undo: reverted {result['field_name']} to \"{result['reverted_to']}\".",
            text_color=GOOD_COLOR,
        )

    # --------------------------------------------------

    def manage_categories(self):
        """Shortcut straight to category management from the Ledger
        itself - the same Add/Rename/Retire/Reactivate CRUD as
        Settings -> Ledger Categories, without leaving Accounting."""

        CategoriesWindow(self, self.service, on_change=self.refresh)

    # --------------------------------------------------
    # Receipts
    # --------------------------------------------------

    def attach_receipt(self):

        transaction_id = self._selected_id()
        if transaction_id is None:
            return
        filename = filedialog.askopenfilename(
            title="Select Receipt", filetypes=[("Documents", "*.pdf *.png *.jpg *.jpeg"), ("All Files", "*.*")],
        )
        if not filename:
            return
        try:
            self.service.attach_receipt(transaction_id, filename, current_actor())
        except (ValueError, FileNotFoundError) as error:
            messagebox.showerror("Attach Receipt", str(error), parent=self)
            return
        self.refresh()

    def view_receipt(self):

        transaction_id = self._selected_id()
        if transaction_id is None:
            return
        path = self.service.get_receipt_path(transaction_id)
        if path is None or not path.exists():
            messagebox.showinfo("View Receipt", "No receipt attached to this transaction.", parent=self)
            return
        try:
            os.startfile(str(path))
        except Exception as error:
            messagebox.showerror("View Receipt", f"Could not open the receipt: {error}", parent=self)

    # --------------------------------------------------
    # Export
    # --------------------------------------------------

    def export_to_excel(self):

        filename = filedialog.asksaveasfilename(
            title="Export Ledger to Excel", defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")], initialfile="ledger_export.xlsx",
        )
        if not filename:
            return

        from core.ledger_export import export_transactions_to_xlsx

        transactions = [
            self._transactions_by_id[row_id] for row_id in self.table.get_children()
            if row_id in self._transactions_by_id
        ]
        export_transactions_to_xlsx(transactions, filename)
        self.status_label.configure(text=f"Exported {len(transactions)} transactions to {filename}", text_color=GOOD_COLOR)

    # --------------------------------------------------
    # Inline "Excel-like" cell editing
    # --------------------------------------------------

    def _on_cell_click(self, event):

        self._destroy_editor()

        row_id = self.table.identify_row(event.y)
        column_id = self.table.identify_column(event.x)
        if not row_id or not column_id or column_id == "#0":
            return

        column_index = int(column_id.replace("#", "")) - 1
        if column_index < 0 or column_index >= len(self.COLUMNS):
            return
        column_name = self.COLUMNS[column_index]
        if column_name not in self.EDITABLE_COLUMNS:
            return

        self._open_editor(row_id, column_id, column_name)

    def _open_editor(self, row_id, column_id, column_name):

        bbox = self.table.bbox(row_id, column_id)
        if not bbox:
            return
        x, y, width, height = bbox

        transaction = self._transactions_by_id.get(row_id)
        if transaction is None:
            return

        current_value = {
            "Date": transaction.date,
            "Description": transaction.description,
            "Category": transaction.category,
            "Amount": f"{transaction.amount_minor / 100:.2f}",
        }[column_name]

        if column_name == "Category":
            categories = self.service.list_categories(category_type=transaction.transaction_type, active_only=True)
            if transaction.category and transaction.category not in categories:
                categories = categories + [transaction.category]
            editor = ttk.Combobox(self.table, values=categories, state="normal")
            editor.set(current_value)
        else:
            # CTkEntry (unlike ttk widgets) rejects width/height passed
            # to .place() - they must go to the constructor instead.
            editor = ctk.CTkEntry(self.table, width=width, height=height)
            editor.insert(0, current_value)

        if isinstance(editor, ttk.Combobox):
            editor.place(x=x, y=y, width=width, height=height)
        else:
            editor.place(x=x, y=y)
        editor.focus_set()
        if isinstance(editor, ctk.CTkEntry):
            editor.select_range(0, "end")

        self._editor = editor
        self._editor_context = (row_id, column_name)

        editor.bind("<Return>", lambda _e: self._commit_editor(move="down"))
        editor.bind("<Tab>", lambda _e: self._commit_editor(move="right"))
        editor.bind("<Escape>", lambda _e: self._destroy_editor())
        editor.bind("<FocusOut>", lambda _e: self._commit_editor(move=None))

    def _destroy_editor(self):

        if self._editor is not None:
            editor = self._editor
            self._editor = None
            self._editor_context = None
            try:
                editor.unbind("<FocusOut>")
                editor.destroy()
            except Exception:
                pass

    def _commit_editor(self, move):

        if self._editor is None:
            return "break"

        editor = self._editor
        row_id, column_name = self._editor_context
        new_value = editor.get().strip() if isinstance(editor, ttk.Combobox) else editor.get().strip()

        # Detach before any refresh/messages so a validation failure or
        # a later exception can't leave a stale overlay behind.
        self._editor = None
        self._editor_context = None
        try:
            editor.unbind("<FocusOut>")
            editor.destroy()
        except Exception:
            pass

        transaction = self._transactions_by_id.get(row_id)
        if transaction is None:
            return "break"

        try:
            self._apply_cell_edit(transaction, column_name, new_value)
        except ValueError as error:
            # Don't interrupt the Excel-like flow with a blocking
            # messagebox - reject silently back to the old value and
            # just say why in the status bar.
            self.status_label.configure(text=f"Not saved: {error}", text_color=WARN_COLOR)
            self.refresh()
            return "break"

        self.refresh()

        if move == "down":
            self._move_editor(row_id, column_name, delta_row=1, delta_col=0)
        elif move == "right":
            self._move_editor(row_id, column_name, delta_row=0, delta_col=1)

        return "break"

    def _apply_cell_edit(self, transaction, column_name, new_value):

        actor = current_actor()

        if column_name == "Date":
            new_date = _normalize_ledger_date(new_value)
            if new_date == transaction.date:
                return
            self.service.record_edit(transaction.id, "date", transaction.date, new_date, actor)
            transaction.date = new_date
            self.service.repository.update(transaction)

        elif column_name == "Description":
            if new_value == transaction.description:
                return
            self.service.record_edit(transaction.id, "description", transaction.description, new_value, actor)
            transaction.description = new_value
            self.service.repository.update(transaction)

        elif column_name == "Category":
            valid = self.service.list_categories(category_type=transaction.transaction_type, active_only=False)
            if new_value not in valid:
                raise ValueError(f'"{new_value}" is not a known {transaction.transaction_type} category.')
            if new_value == transaction.category:
                return
            previous_category = transaction.category or ""
            self.service.update_category(transaction.id, new_value, actor)
            self._offer_bulk_recategorise(transaction, previous_category, new_value, actor)

        elif column_name == "Amount":
            new_amount = parse_amount_minor(new_value)
            if new_amount == transaction.amount_minor:
                return
            self.service.record_edit(transaction.id, "amount_minor", transaction.amount_minor, new_amount, actor)
            transaction.amount_minor = new_amount
            self.service.repository.update(transaction)

    def _offer_bulk_recategorise(self, transaction, previous_category, new_category, actor):
        """After one category change, offer to fix every other transaction
        from the same merchant and to remember the choice for future
        imports - Minette's "Kwikspar = Groceries" ask.

        Only offers rows that still carry the OLD category, so a merchant
        she has deliberately split across categories never gets silently
        flattened back together.
        """

        key = merchant_key(transaction.description)
        if not key:
            return

        # Every other row from this payee, whatever it is categorised as
        # now. Her instruction: offer them all at once - a payee that
        # needs splitting gets split in the KPI view, not here.
        similar = self.service.find_similar_transactions(
            transaction.description,
            exclude_id=transaction.id,
        )

        parent = self.winfo_toplevel()

        if similar:
            # Name the categories being overwritten, so a mixed payee is
            # never flattened without her seeing what she is losing.
            current = {}
            for item in similar:
                label = item.category or "Uncategorized"
                current[label] = current.get(label, 0) + 1
            breakdown = ", ".join(
                f"{count} x {label}" for label, count in sorted(current.items())
            )
            if messagebox.askyesno(
                "Apply to similar transactions?",
                f'{len(similar)} other transaction(s) from "{key}".'
                + "\n\n" + f"Currently: {breakdown}." + "\n\n"
                + f'Change them all to "{new_category}"?',
                parent=parent,
            ):
                updated = self.service.bulk_update_category(
                    [item.id for item in similar], new_category, actor
                )
                self.status_label.configure(
                    text=f"Updated {updated} similar transaction(s).", text_color=GOOD_COLOR
                )

        if self.service.category_for_key(key) != new_category:
            if messagebox.askyesno(
                "Remember this rule?",
                f"Always categorise \"{key}\" as \"{new_category}\" on future imports?",
                parent=parent,
            ):
                self.service.save_category_rule(
                    key, new_category, transaction.transaction_type, actor
                )

    def _move_editor(self, row_id, column_name, delta_row, delta_col):

        if delta_col:
            editable = list(self.EDITABLE_COLUMNS)
            index = editable.index(column_name)
            next_index = index + delta_col
            if 0 <= next_index < len(editable):
                next_column_name = editable[next_index]
                column_id = f"#{self.COLUMNS.index(next_column_name) + 1}"
                self._open_editor(row_id, column_id, next_column_name)
            return

        if delta_row:
            children = self.table.get_children()
            if row_id not in children:
                return
            index = children.index(row_id)
            next_index = index + delta_row
            if 0 <= next_index < len(children):
                next_row_id = children[next_index]
                column_id = f"#{self.COLUMNS.index(column_name) + 1}"
                self.table.selection_set(next_row_id)
                self.table.see(next_row_id)
                self._open_editor(next_row_id, column_id, column_name)


def _normalize_ledger_date(value):
    """Accepts 'YYYY-MM-DD' or 'YYYY/MM/DD' and normalizes to the
    app's 'YYYY-MM-DD'; raises ValueError otherwise."""

    from datetime import datetime as _datetime

    value = value.strip().replace("/", "-")
    try:
        parsed = _datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format.")
    return parsed.strftime("%Y-%m-%d")


class CategoriesWindow(ctk.CTkToplevel):
    """Manage Income/Expense categories directly from the Ledger -
    Add/Rename/Retire/Reactivate, same logic as Settings -> Ledger
    Categories (modules/settings/windows.py). Retiring hides a
    category from new-entry dropdowns without touching transactions
    that already use it."""

    def __init__(self, parent, service, on_change=None):
        super().__init__(parent)

        self.title("Manage Categories")
        self.geometry("600x500")
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)
        self.grab_set()

        self.service = service
        self.on_change = on_change

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text="Ledger Categories", font=("Segoe UI", 18, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        table_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.table = build_entity_table(
            table_frame,
            ("Type", "Status"),
            (
                ("Refresh", self.refresh),
                ("New Category", self.new_category),
                ("Rename", self.rename_category),
                ("Retire", self.retire_category),
                ("Reactivate", self.reactivate_category),
            ),
        )

        ctk.CTkButton(self, text="Close", command=self.destroy, width=100).grid(row=2, column=0, sticky="e", padx=10, pady=(0, 10))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.refresh()

    def refresh(self):

        self.table.delete(*self.table.get_children())
        for category in self.service.category_repository.list_all(active_only=False):
            self.table.insert(
                "", "end", iid=category.id, text=category.name,
                values=(category.category_type, "Active" if category.active else "Retired"),
            )
        if self.on_change:
            self.on_change()

    def _selected_category(self):

        selection = self.table.selection()
        if not selection:
            messagebox.showwarning("Categories", "Select a category first.", parent=self)
            return None
        return self.service.category_repository.get(selection[0])

    def new_category(self):

        from gui.form_dialogs import EntityFormDialog

        fields = [
            {"key": "name", "label": "Category Name", "kind": "text", "initial": ""},
            {"key": "category_type", "label": "Type", "kind": "dropdown", "options": [INCOME, EXPENSE], "initial": EXPENSE},
        ]
        result = EntityFormDialog.ask(self, "New Category", fields)
        if result is None:
            return

        try:
            self.service.add_category(result["name"].strip(), result["category_type"], current_actor())
        except ValueError as error:
            messagebox.showerror("Categories", str(error), parent=self)
            return

        self.refresh()

    def rename_category(self):

        from gui.form_dialogs import EntityFormDialog

        category = self._selected_category()
        if category is None:
            return

        result = EntityFormDialog.ask(
            self, f"Rename Category — {category.name}",
            [{"key": "name", "label": "Category Name", "kind": "text", "initial": category.name}],
        )
        if result is None:
            return

        try:
            self.service.rename_category(category.id, result["name"].strip())
        except ValueError as error:
            messagebox.showerror("Categories", str(error), parent=self)
            return

        self.refresh()

    def retire_category(self):

        category = self._selected_category()
        if category is None:
            return
        self.service.retire_category(category.id)
        self.refresh()

    def reactivate_category(self):

        category = self._selected_category()
        if category is None:
            return
        self.service.reactivate_category(category.id)
        self.refresh()


class AddTransactionDialog(ctk.CTkToplevel):
    """Manually add one ledger transaction - date, description, type,
    category (list changes with type), account, amount, reference,
    notes."""

    def __init__(self, parent, service, on_saved):
        super().__init__(parent)

        self.title("Add Transaction")
        self.geometry("440x640")
        self.minsize(400, 420)
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)
        self.grab_set()

        self.service = service
        self.on_saved = on_saved

        button_row = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        button_row.pack(side="bottom", padx=20, pady=(0, 20), fill="x")
        ctk.CTkButton(button_row, text="Cancel", command=self.destroy, width=100).pack(side="right", padx=5)
        ctk.CTkButton(button_row, text="Save", command=self._save, width=100).pack(side="right", padx=5)

        ctk.CTkLabel(
            self, text="Add Transaction", font=("Segoe UI", 16, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="top", pady=(20, 15), padx=20, anchor="w")

        form_frame = ctk.CTkScrollableFrame(self, fg_color=THEME_DARK_GREY)
        form_frame.pack(side="top", fill="both", expand=True, padx=20)

        ctk.CTkLabel(form_frame, text="Type:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.type_var = ctk.StringVar(value=EXPENSE)
        ctk.CTkOptionMenu(
            form_frame, variable=self.type_var, values=[INCOME, EXPENSE], command=self._on_type_changed,
        ).pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Category:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        initial_categories = self._categories_for(EXPENSE)
        self.category_var = ctk.StringVar(value=initial_categories[0] if initial_categories else "")
        # ttk.Combobox, not CTkOptionMenu - see the matching comment on
        # LedgerWindow's filter dropdown; the Expense list alone runs
        # to ~37 categories, enough to hit the same scroll crash.
        self.category_menu = ttk.Combobox(
            form_frame, textvariable=self.category_var, values=initial_categories or [""], state="readonly",
        )
        self.category_menu.pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Description:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.description_entry = ctk.CTkEntry(form_frame)
        self.description_entry.pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Amount (R):", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.amount_entry = ctk.CTkEntry(form_frame, placeholder_text="0.00")
        self.amount_entry.pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Date:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.date_entry = DateEntry(form_frame, value=date.today().isoformat())
        self.date_entry.pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Account (pick one or type your own):", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        accounts = service.list_accounts() or ["Personal Account", "Gold Business Account"]
        self.account_var = ctk.StringVar(value=accounts[0])
        self.account_entry = ttk.Combobox(form_frame, textvariable=self.account_var, values=accounts)
        self.account_entry.pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Reference:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.reference_entry = ctk.CTkEntry(form_frame)
        self.reference_entry.pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Notes:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.notes_entry = ctk.CTkEntry(form_frame)
        self.notes_entry.pack(pady=(2, 20), fill="x")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self.destroy())

    def _categories_for(self, transaction_type):

        categories = self.service.list_categories(category_type=transaction_type, active_only=True)
        return categories

    def _on_type_changed(self, _value):

        categories = self._categories_for(self.type_var.get())
        self.category_menu.configure(values=categories or [""])
        self.category_var.set(categories[0] if categories else "")

    def _save(self):

        try:
            amount_minor = parse_amount_minor(self.amount_entry.get())
        except ValueError as error:
            messagebox.showerror("Add Transaction", str(error), parent=self)
            return

        description = self.description_entry.get().strip()
        account = self.account_var.get().strip()
        if not account:
            messagebox.showwarning("Add Transaction", "Enter or select an account.", parent=self)
            return

        try:
            self.service.add_transaction(
                self.date_entry.get(),
                description,
                amount_minor,
                self.type_var.get(),
                self.category_var.get(),
                account,
                self.reference_entry.get().strip(),
                self.notes_entry.get().strip(),
                current_actor(),
            )
        except ValueError as error:
            messagebox.showerror("Add Transaction", str(error), parent=self)
            return

        self.on_saved()
        self.destroy()


class PaymentsWindow(ctk.CTkToplevel):
    """Log customer payments and allocate them against Tax Invoices.

    Phase 1: manual entry only. No bank-statement import or
    auto-matching yet - that's a later, separately signed-off phase."""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Payments")
        self.geometry("1200x750")
        self.configure(fg_color=THEME_DARK_GREY)

        self.crm_service = CRMService()
        self.payment_service = PaymentService()
        self._customers_by_id = {}

        self._build_ui()
        self.refresh()

    def _build_ui(self):

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text="Payments", font=("Segoe UI", 18, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))

        table_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        table_frame.grid(row=1, column=0, sticky="nsew")
        self.table = build_entity_table(
            table_frame,
            ("Customer", "Amount", "Date", "Reference", "Status"),
            (
                ("Refresh", self.refresh),
                ("Log Payment", self.log_payment),
                ("Allocate", self.allocate_selected),
            ),
        )
        self.table.bind("<Double-1>", lambda _event: self.allocate_selected())

    def refresh(self):

        self._customers_by_id = {c.id: c for c in self.crm_service.list_customers()}

        self.table.delete(*self.table.get_children())
        for payment in self.payment_service.list_payments():
            customer = self._customers_by_id.get(payment.customer_id)
            self.table.insert(
                "",
                "end",
                iid=payment.id,
                text=payment.date,
                values=(
                    customer.name if customer else "(unknown customer)",
                    format_money(payment.amount_minor),
                    payment.date,
                    payment.reference,
                    payment.status,
                ),
            )

    def _selected_payment_id(self):

        selection = self.table.selection()
        if not selection:
            messagebox.showwarning("Payments", "Select a payment first.", parent=self)
            return None
        return selection[0]

    def log_payment(self):

        customers = self.crm_service.list_customers()
        if not customers:
            messagebox.showwarning("Payments", "Create a customer in CRM first.", parent=self)
            return
        LogPaymentDialog(self, self.crm_service, self.payment_service, customers, on_saved=self.refresh)

    def allocate_selected(self):

        payment_id = self._selected_payment_id()
        if payment_id is None:
            return
        AllocatePaymentDialog(self, self.crm_service, self.payment_service, payment_id, on_saved=self.refresh)


class InvoicesWindow(ctk.CTkToplevel):
    """Every Tax Invoice across every customer, with its real paid/
    balance status computed from logged payment allocations - the
    "show status everywhere" view, not scoped to one customer."""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Invoices")
        self.geometry("1200x750")
        self.configure(fg_color=THEME_DARK_GREY)

        self.crm_service = CRMService()
        self.payment_service = PaymentService()
        self._customers_by_id = {}

        self._build_ui()
        self.refresh()

    def _build_ui(self):

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text="Invoices", font=("Segoe UI", 18, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))

        table_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        table_frame.grid(row=1, column=0, sticky="nsew")
        self.table = build_entity_table(
            table_frame,
            ("Invoice #", "Customer", "Issue Date", "Total", "Balance", "Status"),
            (("Refresh", self.refresh),),
        )

    def refresh(self):

        self._customers_by_id = {c.id: c for c in self.crm_service.list_customers()}

        self.table.delete(*self.table.get_children())
        for entry in self.payment_service.list_invoices_with_status():
            invoice = entry["document"]
            customer = self._customers_by_id.get(invoice.customer_id)
            status = entry["status"]
            if entry["days_overdue"] > 0:
                status = f"{status} — {entry['days_overdue']}d overdue"
            self.table.insert(
                "",
                "end",
                iid=invoice.id,
                text=invoice.document_number,
                values=(
                    invoice.document_number,
                    customer.name if customer else "(unknown customer)",
                    invoice.issue_date,
                    format_money(invoice.total_minor, invoice.currency),
                    format_money(entry["balance_minor"], invoice.currency),
                    status,
                ),
            )


class LogPaymentDialog(ctk.CTkToplevel):
    """Record a customer payment - amount, date, reference, notes. Not
    allocated to an invoice yet; that happens separately."""

    def __init__(self, parent, crm_service, payment_service, customers, on_saved):
        super().__init__(parent)

        self.title("Log Payment")
        self.geometry("440x560")
        self.minsize(400, 380)
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)
        self.grab_set()

        self.parent = parent
        self.crm_service = crm_service
        self.payment_service = payment_service
        self.on_saved = on_saved

        self._customer_by_label = {f"{c.customer_number} — {c.name}": c for c in customers}
        labels = list(self._customer_by_label.keys())
        self._invoice_by_label = {}
        self.NO_INVOICE_LABEL = "(no specific invoice / general payment)"

        # Cancel/Save (side="bottom") packed FIRST, before the
        # scrollable form body - same fix as AllocatePaymentDialog: it
        # guarantees the buttons always have room and stay reachable
        # regardless of how many fields the form grows to, instead of
        # the form pushing them below the visible window.
        button_row = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        button_row.pack(side="bottom", padx=20, pady=(0, 20), fill="x")
        ctk.CTkButton(button_row, text="Cancel", command=self.destroy, width=100).pack(side="right", padx=5)
        ctk.CTkButton(button_row, text="Save", command=self._save, width=100).pack(side="right", padx=5)

        ctk.CTkLabel(
            self, text="Log Payment", font=("Segoe UI", 16, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="top", pady=(20, 15), padx=20, anchor="w")

        form_frame = ctk.CTkScrollableFrame(self, fg_color=THEME_DARK_GREY)
        form_frame.pack(side="top", fill="both", expand=True, padx=20)

        ctk.CTkLabel(form_frame, text="Customer:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.customer_var = ctk.StringVar(value=labels[0] if labels else "")
        ctk.CTkOptionMenu(
            form_frame, variable=self.customer_var, values=labels or ["(no customers)"],
            command=self._on_customer_changed,
        ).pack(pady=(2, 12), fill="x")

        # Auto-populates with the selected customer's open invoices as
        # soon as a customer is picked - Minette's ask was that the
        # invoice should "come up automatically under the customer
        # name" instead of a separate lookup step later in Allocate.
        ctk.CTkLabel(form_frame, text="Invoice (optional):", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.invoice_var = ctk.StringVar(value=self.NO_INVOICE_LABEL)
        self.invoice_menu = ctk.CTkOptionMenu(form_frame, variable=self.invoice_var, values=[self.NO_INVOICE_LABEL])
        self.invoice_menu.pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Amount (R):", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.amount_entry = ctk.CTkEntry(form_frame, placeholder_text="0.00")
        self.amount_entry.pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Date:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.date_entry = DateEntry(form_frame, value=date.today().isoformat())
        self.date_entry.pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Reference:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.reference_entry = ctk.CTkEntry(form_frame, placeholder_text="e.g. bank reference or EFT description")
        self.reference_entry.pack(pady=(2, 12), fill="x")

        ctk.CTkLabel(form_frame, text="Notes:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.notes_entry = ctk.CTkEntry(form_frame)
        self.notes_entry.pack(pady=(2, 20), fill="x")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self.destroy())

        if labels:
            self._on_customer_changed(labels[0])

    def _on_customer_changed(self, _value=None):
        """Refresh the invoice dropdown to that customer's open
        invoices, and prefill the amount with the top invoice's balance
        if the amount field is still empty (never overwrites something
        the user already typed)."""

        customer = self._customer_by_label.get(self.customer_var.get())
        self._invoice_by_label = {}
        if customer is None:
            self.invoice_menu.configure(values=[self.NO_INVOICE_LABEL])
            self.invoice_var.set(self.NO_INVOICE_LABEL)
            return

        open_invoices = self.payment_service.get_open_invoices(customer.id)
        for entry in open_invoices:
            invoice = entry["document"]
            label = f"{invoice.document_number} — Balance {format_money(entry['balance_minor'])}"
            self._invoice_by_label[label] = (invoice, entry["balance_minor"])

        labels = [self.NO_INVOICE_LABEL] + list(self._invoice_by_label.keys())
        self.invoice_menu.configure(values=labels)
        self.invoice_var.set(labels[0])

        if open_invoices and not self.amount_entry.get().strip():
            self.amount_entry.insert(0, f"{open_invoices[0]['balance_minor'] / 100:.2f}")

    def _save(self):

        customer = self._customer_by_label.get(self.customer_var.get())
        if customer is None:
            messagebox.showwarning("Log Payment", "Select a customer.", parent=self)
            return

        try:
            amount_minor = parse_amount_minor(self.amount_entry.get())
        except ValueError as error:
            messagebox.showerror("Log Payment", str(error), parent=self)
            return

        payment_date = self.date_entry.get()
        reference = self.reference_entry.get().strip()
        notes = self.notes_entry.get().strip()

        try:
            payment = self.payment_service.log_payment(
                customer.id, amount_minor, payment_date, reference, notes, current_actor(),
            )
        except ValueError as error:
            messagebox.showerror("Log Payment", str(error), parent=self)
            return

        selected_invoice = self._invoice_by_label.get(self.invoice_var.get())
        preselect_invoice_id = selected_invoice[0].id if selected_invoice else None

        self.on_saved()
        self.destroy()

        # Straight into Allocate rather than leaving her to find the
        # payment in the list and click Allocate again - this was the
        # extra manual step that made the payment feel like it hadn't
        # gone anywhere.
        AllocatePaymentDialog(
            self.parent, self.crm_service, self.payment_service, payment.id,
            on_saved=self.on_saved, preselect_invoice_id=preselect_invoice_id,
        )


class AllocatePaymentDialog(ctk.CTkToplevel):
    """Allocate a logged payment against the customer's open Tax
    Invoices - split across several invoices, partial amounts, and
    reversible one allocation at a time."""

    def __init__(self, parent, crm_service, payment_service, payment_id, on_saved, preselect_invoice_id=None):
        super().__init__(parent)

        self.title("Allocate Payment")
        self.geometry("720x600")
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)
        self.grab_set()

        self.crm_service = crm_service
        self.payment_service = payment_service
        self.payment_id = payment_id
        self.on_saved = on_saved
        self.amount_entries = {}
        # Consumed on the first _refresh() only (then cleared) so it
        # prefills the amount box once instead of clobbering whatever
        # the user is typing on every later redraw.
        self._preselect_invoice_id = preselect_invoice_id

        self.scroll = None
        self._build_ui()
        self._refresh()

    def _build_ui(self):

        self.minsize(600, 420)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # Pack the Close button (side="bottom") and header (side="top")
        # FIRST, before the scrollable content below - Tkinter's pack
        # manager reserves space for widgets in the order they're
        # packed, so this guarantees the button always has room and
        # stays reachable, however many invoices/allocations there are
        # to list. Packing the scrollable content last (with
        # expand=True) means it's the one that shrinks to fit whatever
        # space is left, instead of pushing Close off the bottom of a
        # fixed-size, modal window that the user can't otherwise get
        # past.
        button_row = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        button_row.pack(side="bottom", fill="x", padx=20, pady=(10, 20))
        ctk.CTkButton(button_row, text="Close", command=self.destroy, width=100).pack(side="right")

        self.header_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 16, "bold"), text_color=THEME_TEXT_PRIMARY, justify="left",
        )
        self.header_label.pack(side="top", pady=(20, 5), padx=20, anchor="w")

        self.remaining_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 12, "bold"), text_color=NEUTRAL_COLOR,
        )
        self.remaining_label.pack(side="top", pady=(0, 15), padx=20, anchor="w")

        ctk.CTkLabel(
            self, text="Open Invoices", font=("Segoe UI", 12, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="top", padx=20, anchor="w")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=THEME_SURFACE)
        self.scroll.pack(side="top", padx=20, pady=(5, 10), fill="both", expand=True)

        ctk.CTkLabel(
            self, text="Allocation History", font=("Segoe UI", 12, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="top", padx=20, anchor="w")

        self.history_scroll = ctk.CTkScrollableFrame(self, fg_color=THEME_SURFACE, height=140)
        self.history_scroll.pack(side="top", padx=20, pady=(5, 10), fill="x")

    def _refresh(self):

        payment = self.payment_service.get_payment(self.payment_id)
        if payment is None:
            messagebox.showerror("Allocate Payment", "This payment no longer exists.", parent=self)
            self.destroy()
            return

        customer = self.crm_service.customers.get(payment.customer_id)
        remaining = self.payment_service.get_payment_remaining(self.payment_id)

        self.header_label.configure(
            text=f"{customer.name if customer else '(unknown customer)'} — "
                 f"Payment of {format_money(payment.amount_minor)} on {payment.date}\n"
                 f"Reference: {payment.reference or '(none)'} — Status: {payment.status}"
        )
        self.remaining_label.configure(text=f"Unallocated balance: {format_money(remaining)}")

        for child in self.scroll.winfo_children():
            child.destroy()
        self.amount_entries = {}

        open_invoices = self.payment_service.get_open_invoices(payment.customer_id)
        if not open_invoices:
            ctk.CTkLabel(
                self.scroll, text="No open Tax Invoices for this customer.", text_color=THEME_TEXT_SECONDARY,
            ).pack(pady=10)
        for entry in open_invoices:
            invoice = entry["document"]
            row = ctk.CTkFrame(self.scroll, fg_color=THEME_SURFACE_LIGHT)
            row.pack(fill="x", pady=4, padx=4)

            ctk.CTkLabel(
                row,
                text=f"{invoice.document_number} — Total {format_money(invoice.total_minor)} — "
                     f"Balance {format_money(entry['balance_minor'])} — {entry['status']}",
                text_color=THEME_TEXT_PRIMARY,
                anchor="w",
            ).pack(side="left", padx=10, pady=8, fill="x", expand=True)

            amount_entry = ctk.CTkEntry(row, width=100, placeholder_text="0.00")
            if invoice.id == self._preselect_invoice_id:
                prefill_minor = min(remaining, entry["balance_minor"])
                if prefill_minor > 0:
                    amount_entry.insert(0, f"{prefill_minor / 100:.2f}")
            amount_entry.pack(side="left", padx=5)
            self.amount_entries[invoice.id] = amount_entry

            ctk.CTkButton(
                row, text="Allocate", width=90,
                command=lambda inv=invoice, entry_widget=amount_entry: self._allocate(inv, entry_widget),
            ).pack(side="left", padx=(5, 10))

        self._preselect_invoice_id = None

        for child in self.history_scroll.winfo_children():
            child.destroy()

        allocations = self.payment_service.list_allocations_for_payment(self.payment_id)
        if not allocations:
            ctk.CTkLabel(
                self.history_scroll, text="No allocations yet.", text_color=THEME_TEXT_SECONDARY,
            ).pack(pady=10)
        for allocation in allocations:
            invoice = self.payment_service.documents.get(allocation.quote_document_id)
            row = ctk.CTkFrame(self.history_scroll, fg_color=THEME_SURFACE_LIGHT)
            row.pack(fill="x", pady=2, padx=4)

            label = f"{invoice.document_number if invoice else '(deleted invoice)'} — {format_money(allocation.amount_minor)} on {allocation.created_at[:10]}"
            color = GOOD_COLOR if allocation.amount_minor >= 0 else WARN_COLOR
            ctk.CTkLabel(row, text=label, text_color=color, anchor="w").pack(side="left", padx=10, pady=6, fill="x", expand=True)

            if allocation.amount_minor > 0:
                ctk.CTkButton(
                    row, text="Unallocate", width=90,
                    command=lambda alloc=allocation: self._unallocate(alloc),
                ).pack(side="left", padx=10)

    def _allocate(self, invoice, amount_entry):

        try:
            amount_minor = parse_amount_minor(amount_entry.get())
        except ValueError as error:
            messagebox.showerror("Allocate Payment", str(error), parent=self)
            return

        try:
            self.payment_service.allocate(self.payment_id, invoice.id, amount_minor, current_actor())
        except ValueError as error:
            messagebox.showerror("Allocate Payment", str(error), parent=self)
            return

        self._refresh()
        self.on_saved()

    def _unallocate(self, allocation):

        if not messagebox.askyesno(
            "Unallocate", "Reverse this allocation? This keeps a record but frees up both the payment and the invoice balance.", parent=self,
        ):
            return

        try:
            self.payment_service.unallocate(allocation.id, current_actor())
        except ValueError as error:
            messagebox.showerror("Allocate Payment", str(error), parent=self)
            return

        self._refresh()
        self.on_saved()


class BankImportWindow(ctk.CTkToplevel):
    """One-click FNB bank statement (CSV) import - no Excel step. Parses
    the real "Account Transaction History" export format, previews it,
    then imports straight into the database ledger. Re-importing an
    overlapping month is safe (see LedgerService.import_bank_statement's
    dedupe logic) so this can just be re-run monthly."""

    def __init__(self, parent, on_saved=None):
        super().__init__(parent)

        self.title("Import Bank Statement")
        self.geometry("1200x750")
        self.configure(fg_color=THEME_DARK_GREY)

        # This window is unusual in the Accounting module: it can be
        # opened from an already-open content window (Dashboard's
        # "Import Bank Statement" button), not just from the Hub
        # launcher like every other Accounting window. The site-wide
        # gui/window_focus.py fix (delayed lift/focus/topmost) did not
        # reliably win that specific nested-window race even with an
        # extra manual lift()/focus_force() added directly here.
        # Modal windows (transient + grab_set, like LogPaymentDialog)
        # have not had this problem at all - matching that proven
        # pattern instead of layering on more non-modal workarounds.
        self.transient(parent)
        self.grab_set()

        self.service = LedgerService()
        self.on_saved = on_saved
        self._filepath = ""
        self._parsed_account = ""
        self._parsed_count = 0
        self._detected_format = None

        self._build_ui()

    def _build_ui(self):

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        main_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Import/Close pinned to the bottom FIRST, before the rest of
        # the form - same reasoning as LogPaymentDialog/
        # AllocatePaymentDialog: guarantees they're always reachable
        # regardless of how tall the preview content grows, instead of
        # relying on this window always being tall enough.
        button_frame = ctk.CTkFrame(main_frame, fg_color=THEME_DARK_GREY)
        button_frame.pack(side="bottom", fill="x", pady=(10, 0))
        self.import_button = ctk.CTkButton(
            button_frame, text="Import", command=self._import, fg_color=GOOD_COLOR, hover_color="#008800", state="disabled",
        )
        self.import_button.pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Close", command=self.destroy).pack(side="left", padx=5)

        ctk.CTkLabel(
            main_frame, text="Import Bank Statement", font=("Segoe UI", 18, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="top", pady=(0, 5), anchor="w")

        ctk.CTkLabel(
            main_frame,
            text="Select a CSV file - either your FNB \"Account Transaction History\" export, or your "
                 "bookkeeping software's \"Transaction Analysis\" ledger export (the format is detected "
                 "automatically). One click, no Excel step - already-imported rows are skipped "
                 "automatically, so it's safe to re-run monthly.",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
            wraplength=900,
            justify="left",
        ).pack(pady=(0, 20), anchor="w")

        file_frame = ctk.CTkFrame(main_frame, fg_color=THEME_SURFACE)
        file_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(file_frame, text="File:", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=10, pady=10)
        self.file_label = ctk.CTkLabel(file_frame, text="No file selected", text_color=THEME_TEXT_SECONDARY)
        self.file_label.pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(file_frame, text="Browse", command=self._browse_file, width=100).pack(side="left", padx=10)

        account_frame = ctk.CTkFrame(main_frame, fg_color=THEME_SURFACE)
        account_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(account_frame, text="Account name:", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=10, pady=10)
        self.account_var = ctk.StringVar(value="")
        existing_accounts = self.service.list_accounts()
        self.account_combo = ttk.Combobox(
            account_frame, textvariable=self.account_var,
            values=existing_accounts,
        )
        self.account_combo.pack(side="left", padx=5, expand=True, fill="x")

        preview_frame = ctk.CTkFrame(main_frame, fg_color=THEME_SURFACE)
        preview_frame.pack(fill="both", expand=True, pady=(0, 15))
        ctk.CTkLabel(
            preview_frame, text="Preview", font=("Segoe UI", 12, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(10, 5), padx=10, anchor="w")
        self.preview_label = ctk.CTkLabel(
            preview_frame, text="Select a file to preview it.", text_color=THEME_TEXT_SECONDARY, justify="left", anchor="nw",
        )
        self.preview_label.pack(pady=10, padx=10, fill="both", expand=True, anchor="w")

    def _browse_file(self):

        filename = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if not filename:
            return
        self._filepath = filename
        self.file_label.configure(text=filename)
        self._preview_file(filename)

    def _preview_file(self, filename):
        """Tries the FNB bank statement format first, then falls back
        to the bookkeeping ledger audit export format - Minette has
        both, and there's no need to make her choose which one she's
        pointing at when the file content already says so."""

        from core.bank_statement_parser import parse_fnb_statement
        from core.ledger_audit_parser import LedgerAuditParseError, parse_ledger_audit

        account_label = ""
        rows = []
        detected_format = None
        errors = []

        try:
            # parse_fnb_statement returns four values (the closing balance
            # and statement date feed reconciliation). Unpacking only two
            # here used to raise an uncaught ValueError that killed the
            # whole preview - the file appeared to do nothing at all.
            account_label, fnb_rows, _closing_balance_minor, _statement_date = parse_fnb_statement(filename)
            rows = fnb_rows
            detected_format = "fnb"
        except BankStatementParseError as error:
            errors.append(str(error))
        except Exception as error:
            errors.append(f"Unexpected error reading as FNB statement: {error}")

        if detected_format is None:
            try:
                ledger_rows = parse_ledger_audit(filename)
                rows = ledger_rows
                account_label = ledger_rows[0].account if ledger_rows else ""
                detected_format = "ledger_audit"
            except LedgerAuditParseError as error:
                errors.append(str(error))
            except Exception as error:
                errors.append(f"Unexpected error reading as ledger export: {error}")

        if detected_format is None:
            try:
                from core.pl_report_parser import PLReportParseError, parse_pl_report
                pl_rows = parse_pl_report(filename)
                rows = pl_rows
                account_label = ""
                detected_format = "pl_report"
            except PLReportParseError as error:
                errors.append(str(error))
            except Exception as error:
                errors.append(f"Unexpected error reading as P&L report: {error}")

        if detected_format is None:
            self.preview_label.configure(
                text="This doesn't look like a supported format:\n"
                     "- FNB \"Account Transaction History\" CSV\n"
                     "- Bookkeeping \"Transaction Analysis\" ledger audit CSV\n"
                     "- Bookkeeping \"Income & Expenses YTD\" P&L category export\n\n"
                     + "\n".join(errors)
            )
            self.import_button.configure(state="disabled")
            self._detected_format = None
            return

        self._detected_format = detected_format
        self._parsed_account = account_label
        self._parsed_count = len(rows)
        if account_label and not self.account_var.get().strip():
            self.account_var.set(account_label)

        if not rows:
            self.preview_label.configure(text="No transactions found in this file.")
            self.import_button.configure(state="disabled")
            return

        income_count = sum(1 for row in rows if row.transaction_type == INCOME)
        expense_count = len(rows) - income_count
        format_labels = {
            "fnb": "FNB bank statement",
            "ledger_audit": "Bookkeeping ledger export (pre-categorized)",
            "pl_report": "Bookkeeping P&L category export (pre-categorized)",
        }
        format_label = format_labels.get(detected_format, detected_format)
        sample_lines = "\n".join(
            f"  {row.date}  {row.transaction_type:7}  {format_money(row.amount_minor)}"
            f"{'  ' + row.category if detected_format in ('ledger_audit', 'pl_report') else ''}  {row.description[:50]}"
            for row in rows[:8]
        )
        self.preview_label.configure(
            text=(
                f"Format detected: {format_label}\n"
                f"Account: {account_label or '(not stated in file)'}\n"
                f"{len(rows)} transactions found  ({income_count} income, {expense_count} expense)\n\n"
                f"First rows:\n{sample_lines}"
            )
        )
        self.import_button.configure(state="normal")

    def _import(self):

        if not self._filepath or not self._detected_format:
            return
        account_override = self.account_var.get().strip()

        try:
            if self._detected_format == "fnb":
                result = self.service.import_bank_statement(self._filepath, current_actor(), account_override=account_override)
            elif self._detected_format == "pl_report":
                result = self.service.import_pl_report(self._filepath, current_actor(), account_override=account_override)
            else:
                result = self.service.import_ledger_audit(self._filepath, current_actor(), account_override=account_override)
        except BankStatementParseError as error:
            messagebox.showerror("Import Bank Statement", str(error), parent=self)
            return
        except Exception as error:
            messagebox.showerror("Import Bank Statement", f"Import failed: {error}", parent=self)
            return

        messagebox.showinfo(
            "Import Bank Statement",
            f"Imported {result['imported']} new transaction(s) into \"{result['account']}\".\n"
            f"{result['skipped_duplicates']} already-imported row(s) were skipped.",
            parent=self,
        )
        if self.on_saved:
            self.on_saved()


class ReportsWindow(ctk.CTkToplevel):
    """Financial reports - Income Statement, Expense Breakdown, Monthly
    Summary, Category Analysis - all computed live from the ledger."""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Financial Reports")
        self.geometry("1020x660")
        self.minsize(880, 560)
        self.configure(fg_color=THEME_DARK_GREY)

        self.service = LedgerService()

        self._build_ui()
        self.refresh()

    def _build_ui(self):

        main_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        header_row = ctk.CTkFrame(main_frame, fg_color=THEME_DARK_GREY)
        header_row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            header_row, text="Financial Reports", font=("Segoe UI", 15, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="left")
        ctk.CTkButton(
            header_row, text="Refresh", command=self.refresh, width=80, height=28,
            fg_color=BRAND_GREEN, hover_color=COLORS["accent_hover"],
        ).pack(side="right")

        self.tabs = ctk.CTkTabview(main_frame, fg_color=THEME_SURFACE)
        self.tabs.pack(fill="both", expand=True)

        self.income_statement_tab = self.tabs.add("Income Statement")
        self.expense_tab = self.tabs.add("Expense Breakdown")
        self.monthly_tab = self.tabs.add("Monthly Summary")
        self.category_tab = self.tabs.add("Category Analysis")

    def refresh(self):

        summary = self.service.get_summary()
        self._build_income_statement(summary)
        self._build_expense_breakdown(summary)
        self._build_monthly_summary(summary)
        self._build_category_analysis(summary)

    def _clear(self, tab):

        for child in tab.winfo_children():
            child.destroy()

    def export_income_statement_pdf(self):

        date_range = DateRangeDialog.ask(self)
        if date_range is None:
            return
        date_from, date_to = date_range

        filename = filedialog.asksaveasfilename(
            title="Export Income Statement", defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")], initialfile="income_statement.pdf",
        )
        if not filename:
            return

        from core.business_settings_service import BusinessSettingsService
        from core.ledger_report_pdf import generate_income_statement_pdf

        summary = self.service.get_summary(date_from=date_from or None, date_to=date_to or None)
        business_settings = BusinessSettingsService().get_settings()

        try:
            generate_income_statement_pdf(summary, business_settings, date_from, date_to, filename)
        except Exception as error:
            messagebox.showerror("Export PDF", f"Could not generate the PDF: {error}", parent=self)
            return

        messagebox.showinfo("Export PDF", f"Income Statement exported to:\n{filename}", parent=self)

    def _build_income_statement(self, summary):

        tab = self.income_statement_tab
        self._clear(tab)

        ctk.CTkButton(
            tab, text="Export PDF", command=self.export_income_statement_pdf,
            width=110, height=28, fg_color=BRAND_GREEN, hover_color=COLORS["accent_hover"],
        ).pack(anchor="e", padx=16, pady=(10, 0))

        # Three compact side-by-side cards, matching the Dashboard's
        # existing metric-card pattern, rather than three full-width
        # stacked rows - same information, far less vertical bulk.
        cards_row = ctk.CTkFrame(tab, fg_color=THEME_DARK_GREY)
        cards_row.pack(fill="x", padx=16, pady=(12, 0))

        cards = [
            ("Total Income", format_money(summary["total_income_minor"]), GOOD_COLOR),
            ("Total Expenses", format_money(summary["total_expenses_minor"]), WARN_COLOR),
            ("Net Profit", format_money(summary["net_profit_minor"]),
             GOOD_COLOR if summary["net_profit_minor"] >= 0 else WARN_COLOR),
        ]
        for index, (label, value, color) in enumerate(cards):
            card = ctk.CTkFrame(cards_row, fg_color=THEME_SURFACE, border_color=color, border_width=1)
            left = 0 if index == 0 else 8
            right = 0 if index == len(cards) - 1 else 8
            card.pack(side="left", padx=(left, right), fill="x", expand=True)
            ctk.CTkLabel(
                card, text=label, font=("Segoe UI", 10), text_color=THEME_TEXT_SECONDARY,
            ).pack(pady=(10, 2))
            ctk.CTkLabel(
                card, text=value, font=("Segoe UI", 17, "bold"), text_color=color,
            ).pack(pady=(0, 10))

        ctk.CTkLabel(
            tab, text=f"Based on {summary['transaction_count']} transactions.",
            text_color=THEME_TEXT_SECONDARY, font=("Segoe UI", 10),
        ).pack(padx=16, pady=(10, 0), anchor="w")

    def _build_expense_breakdown(self, summary):

        tab = self.expense_tab
        self._clear(tab)

        expense_totals = {
            key.split("/", 1)[1]: value
            for key, value in summary["by_category"].items()
            if key.startswith(f"{EXPENSE}/")
        }
        build_category_breakdown_chart(tab, expense_totals, "Expenses by Category", WARN_COLOR)

    def _build_monthly_summary(self, summary):

        tab = self.monthly_tab
        self._clear(tab)

        build_monthly_trend_chart(tab, summary["by_month"])

    def _build_category_analysis(self, summary):

        tab = self.category_tab
        self._clear(tab)

        income_totals = {
            key.split("/", 1)[1]: value
            for key, value in summary["by_category"].items()
            if key.startswith(f"{INCOME}/")
        }
        build_category_breakdown_chart(tab, income_totals, "Income by Category", BRAND_GREEN)


class DateRangeDialog(ctk.CTkToplevel):
    """Small modal date-range picker (reuses the tkcalendar DateEntry
    pattern already used elsewhere, e.g. modules/quotes/windows.py's
    StatementWindow) - used for the Income Statement PDF export."""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Select Date Range")
        self.geometry("340x220")
        self.resizable(False, False)
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)
        self.grab_set()

        self.result = None

        ctk.CTkLabel(
            self, text="Income Statement Date Range", font=("Segoe UI", 13, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(15, 10))

        today = date.today()

        ctk.CTkLabel(self, text="From:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w", padx=20)
        self.from_entry = DateEntry(self, value=f"{today.year}-01-01")
        self.from_entry.pack(fill="x", padx=20, pady=(2, 10))

        ctk.CTkLabel(self, text="To:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w", padx=20)
        self.to_entry = DateEntry(self, value=today.isoformat())
        self.to_entry.pack(fill="x", padx=20, pady=(2, 10))

        button_row = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        button_row.pack(fill="x", padx=20, pady=(10, 15))
        ctk.CTkButton(button_row, text="Cancel", command=self.destroy, width=90).pack(side="right", padx=5)
        ctk.CTkButton(button_row, text="OK", command=self._ok, width=90).pack(side="right", padx=5)

        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _ok(self):

        self.result = (
            self.from_entry.get(),
            self.to_entry.get(),
        )
        self.destroy()

    @staticmethod
    def ask(parent):
        dialog = DateRangeDialog(parent)
        parent.wait_window(dialog)
        return dialog.result


class AccountingModuleWindow(ctk.CTkFrame):
    """Module frame - launches hub with quick access"""

    def __init__(self, master):
        super().__init__(master)

        self.configure(fg_color=THEME_DARK_GREY)
        self.hub = None

        ctk.CTkLabel(
            self,
            text="Accounting Hub",
            font=("Segoe UI", 22, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(20, 30))

        info_frame = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        info_frame.pack(pady=20, padx=40, fill="both", expand=True)

        ctk.CTkLabel(
            info_frame,
            text="Manage your finances with a complete accounting system.\n\nTrack transactions, import bank statements, and generate reports.",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
            justify="center",
        ).pack(pady=20, padx=20)

        button_frame = ctk.CTkFrame(info_frame, fg_color=THEME_SURFACE)
        button_frame.pack(pady=20, padx=20, fill="x")

        buttons = [
            ("📊 Dashboard", self._open_dashboard),
            ("📋 Ledger", self._open_ledger),
            ("💳 Payments", self._open_payments),
            ("🧾 Invoices", self._open_invoices),
            ("🏦 Import Bank Statement", self._open_import),
            ("📈 Reports", self._open_reports),
        ]

        for label, command in buttons:
            ctk.CTkButton(
                button_frame,
                text=label,
                command=command,
                height=40,
                font=("Segoe UI", 11),
            ).pack(pady=5, fill="x")

    def _ensure_hub(self):
        if self.hub is None or not self.hub.winfo_exists():
            self.hub = AccountingHub(self.winfo_toplevel())
        return self.hub

    def _open_dashboard(self):
        hub = self._ensure_hub()
        hub.open_dashboard()

    def _open_ledger(self):
        hub = self._ensure_hub()
        hub.open_ledger()

    def _open_payments(self):
        hub = self._ensure_hub()
        hub.open_payments()

    def _open_invoices(self):
        hub = self._ensure_hub()
        hub.open_invoices()

    def _open_import(self):
        hub = self._ensure_hub()
        hub.open_import()

    def _open_reports(self):
        hub = self._ensure_hub()
        hub.open_reports()
