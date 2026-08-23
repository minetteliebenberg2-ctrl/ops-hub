"""Build the standalone Excel accounting workbook.

This is NOT an export of the FC Hub ledger - it is a self-contained working
set of books you keep in Excel. Everything downstream of the Ledger sheet is
live formulas, so capturing a transaction updates the trial balance, income
statement, balance sheet, cash flow and bank reconciliation at once.

The only thing read from FC Hub is the income/expense category list, so the
chart of accounts matches the wording already used in the app rather than
inventing a second vocabulary. Balance-sheet accounts have no equivalent in
the app's ledger, so a standard small-company set is seeded here and is meant
to be edited.

Financial year runs March to February (SA tax year); set the year on Setup.

Usage:  python tools/build_accounting_workbook.py [output.xlsx] [fy_start_year]
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

BRAND_GREEN = "1B7A3D"
LIGHT_GREEN = "E8F3EC"
GREY = "F2F2F2"
FONT = "Arial"

MONEY = '#,##0.00;[Red]-#,##0.00'
DATE_FMT = "yyyy-mm-dd"

# Rows of Ledger available for capture. Formulas on the summary sheets span
# the whole block, so blank rows cost nothing but let you keep typing.
LEDGER_ROWS = 2000
LEDGER_FIRST = 2
LEDGER_LAST = LEDGER_FIRST + LEDGER_ROWS - 1

MONTHS = ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb"]

THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# Balance-sheet accounts. The app's ledger only classifies Income/Expense, so
# these are seeded rather than read; edit freely, every sheet follows the
# Chart of Accounts.
BALANCE_SHEET_ACCOUNTS = [
    ("1000", "Bank - Current Account", "Asset", "Current Assets"),
    ("1010", "Bank - Savings Account", "Asset", "Current Assets"),
    ("1020", "Petty Cash", "Asset", "Current Assets"),
    ("1100", "Trade Debtors (Accounts Receivable)", "Asset", "Current Assets"),
    ("1200", "Stock on Hand", "Asset", "Current Assets"),
    ("1500", "Plant & Equipment", "Asset", "Non-Current Assets"),
    ("1510", "Motor Vehicles", "Asset", "Non-Current Assets"),
    ("1520", "Office Equipment & Computers", "Asset", "Non-Current Assets"),
    ("1590", "Accumulated Depreciation", "Asset", "Non-Current Assets"),
    ("2000", "Trade Creditors (Accounts Payable)", "Liability", "Current Liabilities"),
    ("2100", "Credit Card", "Liability", "Current Liabilities"),
    ("2200", "SARS - PAYE/UIF/SDL", "Liability", "Current Liabilities"),
    ("2210", "SARS - Income Tax Payable", "Liability", "Current Liabilities"),
    ("2300", "Customer Deposits Held", "Liability", "Current Liabilities"),
    ("2500", "Long Term Loans", "Liability", "Non-Current Liabilities"),
    ("2600", "Directors Loan Account", "Liability", "Non-Current Liabilities"),
    ("3000", "Share Capital", "Equity", "Equity"),
    ("3100", "Retained Earnings", "Equity", "Equity"),
]

# Accounts the Cash Flow sheet treats as cash. Must match the names above
# exactly; if you rename a bank account in the Chart of Accounts, rename it
# here too and regenerate.
CASH_ACCOUNTS = [
    "Bank - Current Account",
    "Bank - Savings Account",
    "Petty Cash",
]


def _load_app_categories():
    """Income and expense categories as worded in FC Hub's Accounting module."""

    db = Path(__file__).resolve().parent.parent / "database" / "fc_hub.db"
    if not db.exists():
        return [], []

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "select category_type, name from ledger_categories "
            "where active = 1 order by category_type, name"
        ).fetchall()
    finally:
        conn.close()

    income = [name for kind, name in rows if kind == "Income"]
    expense = [name for kind, name in rows if kind == "Expense"]
    return income, expense


def _load_supplier_prices():
    """Live supplier price list. Read from supplier_price_items (the table she
    edits in Settings -> Supplier Pricing), never from a second copy kept by
    hand - a stale price in the books is worse than no price."""

    db = Path(__file__).resolve().parent.parent / "database" / "fc_hub.db"
    if not db.exists():
        return []

    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            "select category, item_name, supplier_name, spec, unit, "
            "cost_minor, vat_inclusive from supplier_price_items "
            "where is_active = 1 order by category, sort_order, item_name"
        ).fetchall()
    finally:
        conn.close()


def _header(sheet, headers, row=1, fill=BRAND_GREEN):
    for column, title in enumerate(headers, start=1):
        cell = sheet.cell(row=row, column=column, value=title)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    sheet.row_dimensions[row].height = 22


def _widths(sheet, widths):
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width


def _title(sheet, text, subtitle=None):
    cell = sheet.cell(row=1, column=1, value=text)
    cell.font = Font(name=FONT, bold=True, size=14, color=BRAND_GREEN)
    if subtitle:
        note = sheet.cell(row=2, column=1, value=subtitle)
        note.font = Font(name=FONT, size=9, italic=True, color="666666")


def _cell(sheet, row, column, value, bold=False, fmt=None, fill=None, size=10):
    cell = sheet.cell(row=row, column=column, value=value)
    cell.font = Font(name=FONT, bold=bold, size=size)
    if fmt:
        cell.number_format = fmt
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)
    return cell


# ----------------------------------------------------------------------
# Sheets
# ----------------------------------------------------------------------

def build_setup(sheet, fy_start_year):
    _title(sheet, "Setup", "Everything else in this workbook keys off these values.")
    _widths(sheet, [34, 40])

    rows = [
        ("Business name", "FacilitiesCo"),
        ("Registration number", "2024/772013/07"),
        ("VAT registered", "No"),
        ("Financial year starts (1 March)", f"{fy_start_year}-03-01"),
        ("Financial year ends (28/29 February)", f"{fy_start_year + 1}-02-28"),
        ("Reporting currency", "ZAR"),
    ]
    row = 4
    for label, value in rows:
        _cell(sheet, row, 1, label, bold=True)
        _cell(sheet, row, 2, value).fill = PatternFill("solid", fgColor=LIGHT_GREEN)
        row += 1

    row += 1
    _cell(sheet, row, 1, "How to use", bold=True, size=11)
    row += 1
    for line in [
        "1. Chart of Accounts - add or rename accounts. Every other sheet reads this list.",
        "2. Ledger - capture each transaction on one row: date, account, then Debit or Credit.",
        "3. Trial Balance, Income Statement, Balance Sheet, Cash Flow and Bank Rec are all",
        "   formulas - never type into their figure columns.",
        "4. Opening Balances on the Balance Sheet are the only balance-sheet figures you type.",
        "5. Bank Rec: enter the closing balance off the bank statement; the difference must be nil.",
    ]:
        _cell(sheet, row, 1, line, size=9)
        row += 1

    sheet.freeze_panes = "A4"


def build_chart(sheet, income, expense):
    _title(sheet, "Chart of Accounts", "Add rows freely - the summary sheets read this list.")
    _header(sheet, ["Code", "Account", "Type", "Statement Group"], row=3)
    _widths(sheet, [10, 46, 14, 26])

    entries = []
    for index, name in enumerate(income):
        entries.append((f"4{index:03d}", name, "Income", "Revenue"))
    for index, name in enumerate(expense):
        entries.append((f"5{index:03d}", name, "Expense", "Operating Expenses"))
    entries.extend(BALANCE_SHEET_ACCOUNTS)

    row = 4
    for code, name, kind, group in entries:
        _cell(sheet, row, 1, code)
        _cell(sheet, row, 2, name)
        _cell(sheet, row, 3, kind)
        _cell(sheet, row, 4, group)
        for column in range(1, 5):
            sheet.cell(row=row, column=column).border = BOX
        row += 1

    last = row - 1
    sheet.freeze_panes = "A4"
    return last, entries


def build_ledger(sheet, chart_last):
    _title(sheet, "Ledger", "One row per transaction. Debit increases assets/expenses; Credit increases income/liabilities.")
    _header(
        sheet,
        ["Date", "Reference", "Description", "Account", "Debit", "Credit", "Bank / Source", "Notes"],
        row=3,
    )
    _widths(sheet, [12, 14, 44, 34, 14, 14, 22, 30])

    first = 4
    last = first + LEDGER_ROWS - 1

    validation = DataValidation(
        type="list",
        formula1=f"='Chart of Accounts'!$B$4:$B${chart_last}",
        allow_blank=True,
        showDropDown=False,
    )
    validation.error = "Pick an account from the Chart of Accounts."
    sheet.add_data_validation(validation)
    validation.add(f"D{first}:D{last}")

    for row in range(first, last + 1):
        sheet.cell(row=row, column=1).number_format = DATE_FMT
        for column in (5, 6):
            sheet.cell(row=row, column=column).number_format = MONEY
        for column in range(1, 9):
            cell = sheet.cell(row=row, column=column)
            cell.font = Font(name=FONT, size=10)
            cell.border = BOX

    # Running totals sit above the data so they stay visible with the panes
    # frozen, rather than at row 2003 where nobody will scroll to them.
    _cell(sheet, 2, 4, "Totals", bold=True)
    _cell(sheet, 2, 5, f"=SUM(E{first}:E{last})", bold=True, fmt=MONEY, fill=LIGHT_GREEN)
    _cell(sheet, 2, 6, f"=SUM(F{first}:F{last})", bold=True, fmt=MONEY, fill=LIGHT_GREEN)
    # ROUND, not TEXT: TEXT's format codes are locale-dependent and rendered
    # as "-7500,0.00" on this machine's regional settings.
    _cell(sheet, 2, 7, '=IF(ROUND(E2-F2,2)=0,"Balanced","OUT BY "&ROUND(E2-F2,2))', bold=True)

    sheet.freeze_panes = "A4"
    return first, last


def build_trial_balance(sheet, chart_last, ledger_first, ledger_last):
    _title(sheet, "Trial Balance", "Formulas only - capture on the Ledger.")
    _header(sheet, ["Code", "Account", "Type", "Debit", "Credit", "Balance"], row=3)
    _widths(sheet, [10, 46, 14, 16, 16, 16])

    first = 4
    last = first + (chart_last - 4)
    for offset, row in enumerate(range(first, last + 1)):
        source = 4 + offset
        _cell(sheet, row, 1, f"='Chart of Accounts'!A{source}")
        _cell(sheet, row, 2, f"='Chart of Accounts'!B{source}")
        _cell(sheet, row, 3, f"='Chart of Accounts'!C{source}")
        _cell(
            sheet, row, 4,
            f"=SUMIF(Ledger!$D${ledger_first}:$D${ledger_last},$B{row},"
            f"Ledger!$E${ledger_first}:$E${ledger_last})",
            fmt=MONEY,
        )
        _cell(
            sheet, row, 5,
            f"=SUMIF(Ledger!$D${ledger_first}:$D${ledger_last},$B{row},"
            f"Ledger!$F${ledger_first}:$F${ledger_last})",
            fmt=MONEY,
        )
        _cell(sheet, row, 6, f"=D{row}-E{row}", fmt=MONEY)
        for column in range(1, 7):
            sheet.cell(row=row, column=column).border = BOX

    total = last + 1
    _cell(sheet, total, 2, "TOTAL", bold=True, fill=LIGHT_GREEN)
    _cell(sheet, total, 4, f"=SUM(D{first}:D{last})", bold=True, fmt=MONEY, fill=LIGHT_GREEN)
    _cell(sheet, total, 5, f"=SUM(E{first}:E{last})", bold=True, fmt=MONEY, fill=LIGHT_GREEN)
    _cell(
        sheet, total, 6,
        f'=IF(ROUND(D{total}-E{total},2)=0,"Balanced","OUT BY "&ROUND(D{total}-E{total},2))',
        bold=True, fill=LIGHT_GREEN,
    )

    sheet.freeze_panes = "A4"
    return first, last


def _month_columns(sheet, header_row, fy_start_year):
    """Write Mar..Feb headers with the real month-start date underneath, so
    SUMIFS can bracket a month without any date arithmetic in every cell."""

    for index, month in enumerate(MONTHS):
        column = 2 + index
        year = fy_start_year if index < 10 else fy_start_year + 1
        month_number = 3 + index if index < 10 else index - 9
        cell = sheet.cell(row=header_row, column=column, value=f"{month} {str(year)[-2:]}")
        cell.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor=BRAND_GREEN)
        cell.alignment = Alignment(horizontal="center")
        # Hidden helper row: first day of that month.
        helper = sheet.cell(row=header_row + 1, column=column, value=f"{year}-{month_number:02d}-01")
        helper.number_format = DATE_FMT
        helper.font = Font(name=FONT, size=8, color="AAAAAA")

    total = 2 + len(MONTHS)
    cell = sheet.cell(row=header_row, column=total, value="Year Total")
    cell.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
    cell.fill = PatternFill("solid", fgColor="155E2E")
    cell.alignment = Alignment(horizontal="center")
    sheet.row_dimensions[header_row + 1].height = 10
    return total


def _month_sumif(row, column, ledger_first, ledger_last, amount_column, header_row):
    """SUMIFS for one account row x one month column."""

    letter = get_column_letter(column)
    return (
        f"=SUMIFS(Ledger!${amount_column}${ledger_first}:${amount_column}${ledger_last},"
        f"Ledger!$D${ledger_first}:$D${ledger_last},$A{row},"
        f"Ledger!$A${ledger_first}:$A${ledger_last},\">=\"&{letter}${header_row + 1},"
        f"Ledger!$A${ledger_first}:$A${ledger_last},\"<=\"&EOMONTH({letter}${header_row + 1},0))"
    )


def build_income_statement(sheet, entries, ledger_first, ledger_last, fy_start_year):
    _title(sheet, "Income Statement", "March to February, per month. Formulas only.")
    header_row = 4
    _cell(sheet, header_row, 1, "Account", bold=True).fill = PatternFill("solid", fgColor=BRAND_GREEN)
    sheet.cell(row=header_row, column=1).font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
    total_column = _month_columns(sheet, header_row, fy_start_year)
    _widths(sheet, [42] + [13] * 12 + [15])

    income = [name for _, name, kind, _ in entries if kind == "Income"]
    expense = [name for _, name, kind, _ in entries if kind == "Expense"]

    row = header_row + 2

    def section(heading, names, amount_column):
        nonlocal row
        _cell(sheet, row, 1, heading, bold=True, size=11, fill=LIGHT_GREEN)
        for column in range(2, total_column + 1):
            sheet.cell(row=row, column=column).fill = PatternFill("solid", fgColor=LIGHT_GREEN)
        row += 1
        first = row
        for name in names:
            _cell(sheet, row, 1, name)
            for column in range(2, total_column):
                _cell(
                    sheet, row, column,
                    _month_sumif(row, column, ledger_first, ledger_last, amount_column, header_row),
                    fmt=MONEY,
                )
            _cell(sheet, row, total_column,
                  f"=SUM(B{row}:{get_column_letter(total_column - 1)}{row})", fmt=MONEY, bold=True)
            row += 1
        last = row - 1
        _cell(sheet, row, 1, f"Total {heading}", bold=True)
        for column in range(2, total_column + 1):
            letter = get_column_letter(column)
            _cell(sheet, row, column, f"=SUM({letter}{first}:{letter}{last})", bold=True, fmt=MONEY)
        subtotal = row
        row += 2
        return subtotal

    # Income lands in the Credit column, expenses in the Debit column - that
    # is the whole reason each section names its own amount column.
    income_total = section("Income", income, "F")
    expense_total = section("Expenses", expense, "E")

    _cell(sheet, row, 1, "NET PROFIT / (LOSS)", bold=True, size=11, fill=LIGHT_GREEN)
    for column in range(2, total_column + 1):
        letter = get_column_letter(column)
        _cell(sheet, row, column, f"={letter}{income_total}-{letter}{expense_total}",
              bold=True, fmt=MONEY, fill=LIGHT_GREEN)

    sheet.freeze_panes = "B6"
    return row, income_total, expense_total


def build_balance_sheet(sheet, entries, tb_first, tb_last, net_profit_row, total_column):
    _title(sheet, "Balance Sheet", "Opening Balance is the only column you type into.")
    _header(sheet, ["Code", "Account", "Opening Balance", "Movement (Ledger)", "Closing Balance"], row=4)
    _widths(sheet, [10, 46, 18, 20, 18])

    codes = {name: (code, group) for code, name, kind, group in entries
             if kind in ("Asset", "Liability", "Equity")}
    by_group = {}
    for code, name, kind, group in entries:
        if kind in ("Asset", "Liability", "Equity"):
            by_group.setdefault((kind, group), []).append((code, name))

    row = 6
    group_totals = {"Asset": [], "Liability": [], "Equity": []}

    for (kind, group), accounts in by_group.items():
        _cell(sheet, row, 1, group, bold=True, size=11, fill=LIGHT_GREEN)
        for column in range(2, 6):
            sheet.cell(row=row, column=column).fill = PatternFill("solid", fgColor=LIGHT_GREEN)
        row += 1
        first = row
        for code, name in accounts:
            _cell(sheet, row, 1, code)
            _cell(sheet, row, 2, name)
            _cell(sheet, row, 3, 0, fmt=MONEY).fill = PatternFill("solid", fgColor="FFFDE7")
            # Assets are debit-positive, liabilities and equity credit-positive.
            sign = "" if kind == "Asset" else "-"
            _cell(
                sheet, row, 4,
                f"={sign}SUMIF('Trial Balance'!$B${tb_first}:$B${tb_last},$B{row},"
                f"'Trial Balance'!$F${tb_first}:$F${tb_last})",
                fmt=MONEY,
            )
            _cell(sheet, row, 5, f"=C{row}+D{row}", fmt=MONEY)
            for column in range(1, 6):
                sheet.cell(row=row, column=column).border = BOX
            row += 1
        _cell(sheet, row, 2, f"Total {group}", bold=True)
        for column in (3, 4, 5):
            letter = get_column_letter(column)
            _cell(sheet, row, column, f"=SUM({letter}{first}:{letter}{row - 1})", bold=True, fmt=MONEY)
        group_totals[kind].append(row)
        row += 2

    profit_row = row
    _cell(sheet, row, 2, "Profit / (Loss) for the year", bold=True)
    _cell(sheet, row, 5,
          f"='Income Statement'!{get_column_letter(total_column)}{net_profit_row}",
          bold=True, fmt=MONEY)
    row += 2

    assets = "+".join(f"E{r}" for r in group_totals["Asset"]) or "0"
    liabilities = "+".join(f"E{r}" for r in group_totals["Liability"]) or "0"
    equity = "+".join(f"E{r}" for r in group_totals["Equity"]) or "0"

    _cell(sheet, row, 2, "TOTAL ASSETS", bold=True, fill=LIGHT_GREEN)
    _cell(sheet, row, 5, f"={assets}", bold=True, fmt=MONEY, fill=LIGHT_GREEN)
    row += 1
    _cell(sheet, row, 2, "TOTAL LIABILITIES & EQUITY", bold=True, fill=LIGHT_GREEN)
    _cell(sheet, row, 5, f"={liabilities}+{equity}+E{profit_row}", bold=True, fmt=MONEY, fill=LIGHT_GREEN)
    row += 1
    _cell(sheet, row, 2, "Difference (must be nil)", bold=True)
    _cell(sheet, row, 5,
          f'=IF(ROUND(E{row - 2}-E{row - 1},2)=0,"Balanced","OUT BY "&ROUND(E{row - 2}-E{row - 1},2))',
          bold=True)

    sheet.freeze_panes = "A6"


def build_cash_flow(sheet, ledger_first, ledger_last, fy_start_year):
    _title(sheet, "Cash Flow", "Money in and out per month, with a running balance.")
    header_row = 4
    _cell(sheet, header_row, 1, "", bold=True)
    total_column = _month_columns(sheet, header_row, fy_start_year)
    _widths(sheet, [30] + [13] * 12 + [15])

    row = header_row + 2
    _cell(sheet, row, 1, "Opening bank balance", bold=True)
    _cell(sheet, row, 2, 0, fmt=MONEY).fill = PatternFill("solid", fgColor="FFFDE7")
    for column in range(3, total_column):
        _cell(sheet, row, column, f"={get_column_letter(column - 1)}{row + 3}", fmt=MONEY)
    opening = row

    row += 1
    _cell(sheet, row, 1, "Receipts", bold=True)
    receipts = row
    row += 1
    _cell(sheet, row, 1, "Payments", bold=True)
    payments = row
    row += 1
    _cell(sheet, row, 1, "Closing bank balance", bold=True, fill=LIGHT_GREEN)
    closing = row

    # Only the cash accounts count here. Summing every credit as a receipt
    # double-counts a normal entry - Dr Bank / Cr Sales Income would show as
    # both a receipt and a payment and net to nil. Cash in is a DEBIT to a
    # cash account; cash out is a CREDIT to one.
    for column in range(2, total_column):
        letter = get_column_letter(column)
        start = f"{letter}${header_row + 1}"

        def cash_sum(amount_column):
            parts = [
                f"SUMIFS(Ledger!${amount_column}${ledger_first}:${amount_column}${ledger_last},"
                f"Ledger!$D${ledger_first}:$D${ledger_last},\"{account}\","
                f"Ledger!$A${ledger_first}:$A${ledger_last},\">=\"&{start},"
                f"Ledger!$A${ledger_first}:$A${ledger_last},\"<=\"&EOMONTH({start},0))"
                for account in CASH_ACCOUNTS
            ]
            return "=" + "+".join(parts)

        _cell(sheet, receipts, column, cash_sum("E"), fmt=MONEY)
        _cell(sheet, payments, column, cash_sum("F"), fmt=MONEY)
        _cell(sheet, closing, column,
              f"={letter}{opening}+{letter}{receipts}-{letter}{payments}",
              bold=True, fmt=MONEY, fill=LIGHT_GREEN)

    last_month = get_column_letter(total_column - 1)
    _cell(sheet, receipts, total_column, f"=SUM(B{receipts}:{last_month}{receipts})", bold=True, fmt=MONEY)
    _cell(sheet, payments, total_column, f"=SUM(B{payments}:{last_month}{payments})", bold=True, fmt=MONEY)
    _cell(sheet, closing, total_column, f"={last_month}{closing}", bold=True, fmt=MONEY, fill=LIGHT_GREEN)

    sheet.freeze_panes = "B6"
    return closing


def build_bank_rec(sheet, cash_closing_row, total_column):
    _title(sheet, "Bank Reconciliation", "Type the statement balance and any timing differences.")
    _widths(sheet, [46, 20, 40])

    row = 4
    _cell(sheet, row, 1, "Closing balance per bank statement", bold=True)
    _cell(sheet, row, 2, 0, fmt=MONEY).fill = PatternFill("solid", fgColor="FFFDE7")
    statement = row

    row += 2
    _cell(sheet, row, 1, "Add: deposits not yet on statement", bold=True)
    row += 1
    deposits_first = row
    for _ in range(5):
        _cell(sheet, row, 1, "")
        _cell(sheet, row, 2, None, fmt=MONEY).fill = PatternFill("solid", fgColor="FFFDE7")
        _cell(sheet, row, 3, "")
        for column in range(1, 4):
            sheet.cell(row=row, column=column).border = BOX
        row += 1
    deposits_last = row - 1

    row += 1
    _cell(sheet, row, 1, "Less: payments not yet on statement", bold=True)
    row += 1
    payments_first = row
    for _ in range(5):
        _cell(sheet, row, 1, "")
        _cell(sheet, row, 2, None, fmt=MONEY).fill = PatternFill("solid", fgColor="FFFDE7")
        _cell(sheet, row, 3, "")
        for column in range(1, 4):
            sheet.cell(row=row, column=column).border = BOX
        row += 1
    payments_last = row - 1

    row += 1
    _cell(sheet, row, 1, "Adjusted bank balance", bold=True, fill=LIGHT_GREEN)
    _cell(sheet, row, 2,
          f"=B{statement}+SUM(B{deposits_first}:B{deposits_last})-SUM(B{payments_first}:B{payments_last})",
          bold=True, fmt=MONEY, fill=LIGHT_GREEN)
    adjusted = row

    row += 1
    _cell(sheet, row, 1, "Closing balance per Cash Flow", bold=True)
    _cell(sheet, row, 2,
          f"='Cash Flow'!{get_column_letter(total_column)}{cash_closing_row}", fmt=MONEY)
    per_books = row

    row += 1
    _cell(sheet, row, 1, "Difference (must be nil)", bold=True)
    _cell(sheet, row, 2,
          f'=IF(ROUND(B{adjusted}-B{per_books},2)=0,"Reconciled",'
          f'"OUT BY "&ROUND(B{adjusted}-B{per_books},2))',
          bold=True)


def build_suppliers(sheet, prices):
    """Supplier contact list, one row per supplier appearing in the price list.
    Contact details are not held in the app, so those columns are blank for
    her to fill - the point is that the supplier names match the price list."""

    _title(sheet, "Suppliers", "Names come from the live price list; fill in the contact details.")
    _header(sheet, ["Supplier", "Contact Person", "Phone", "Email", "Account No.",
                    "Payment Terms", "Notes"], row=3)
    _widths(sheet, [26, 22, 18, 30, 16, 18, 34])

    seen = []
    for _, _, supplier, _, _, _, _ in prices:
        if supplier and supplier not in seen:
            seen.append(supplier)

    row = 4
    for supplier in sorted(seen):
        _cell(sheet, row, 1, supplier, bold=True)
        for column in range(2, 8):
            _cell(sheet, row, column, "")
        for column in range(1, 8):
            sheet.cell(row=row, column=column).border = BOX
        row += 1

    sheet.freeze_panes = "A4"


def build_price_list(sheet, prices):
    _title(
        sheet,
        "Supplier Price List",
        "Live from FC Hub (Settings -> Supplier Pricing). All costs INCLUDE VAT - "
        "not VAT registered, so input VAT is real cost. Regenerate after a price increase.",
    )
    _header(sheet, ["Category", "Item", "Supplier", "Spec", "Unit", "Cost (incl VAT)"], row=4)
    _widths(sheet, [16, 34, 18, 34, 14, 16])

    row = 5
    current_category = None
    for category, item, supplier, spec, unit, cost_minor, vat_inclusive in prices:
        if category != current_category:
            current_category = category
            _cell(sheet, row, 1, category, bold=True, size=11, fill=LIGHT_GREEN)
            for column in range(2, 7):
                sheet.cell(row=row, column=column).fill = PatternFill("solid", fgColor=LIGHT_GREEN)
            row += 1
        _cell(sheet, row, 1, "")
        _cell(sheet, row, 2, item)
        _cell(sheet, row, 3, supplier or "")
        _cell(sheet, row, 4, spec or "")
        _cell(sheet, row, 5, unit or "")
        _cell(sheet, row, 6, (cost_minor or 0) / 100.0, fmt=MONEY)
        if not vat_inclusive:
            _cell(sheet, row, 5, f"{unit or ''} (excl VAT)")
        for column in range(1, 7):
            sheet.cell(row=row, column=column).border = BOX
        row += 1

    sheet.freeze_panes = "A5"


def build(output_path, fy_start_year):
    income, expense = _load_app_categories()
    if not income and not expense:
        print("WARNING: no categories read from the app database - chart of accounts "
              "will only contain balance-sheet accounts.")

    book = openpyxl.Workbook()
    setup = book.active
    setup.title = "Setup"
    build_setup(setup, fy_start_year)

    chart = book.create_sheet("Chart of Accounts")
    chart_last, entries = build_chart(chart, income, expense)

    ledger = book.create_sheet("Ledger")
    ledger_first, ledger_last = build_ledger(ledger, chart_last)

    trial = book.create_sheet("Trial Balance")
    tb_first, tb_last = build_trial_balance(trial, chart_last, ledger_first, ledger_last)

    statement = book.create_sheet("Income Statement")
    net_row, _, _ = build_income_statement(
        statement, entries, ledger_first, ledger_last, fy_start_year
    )
    total_column = 2 + len(MONTHS)

    balance = book.create_sheet("Balance Sheet")
    build_balance_sheet(balance, entries, tb_first, tb_last, net_row, total_column)

    cash = book.create_sheet("Cash Flow")
    closing_row = build_cash_flow(cash, ledger_first, ledger_last, fy_start_year)

    rec = book.create_sheet("Bank Reconciliation")
    build_bank_rec(rec, closing_row, total_column)

    prices = _load_supplier_prices()
    if not prices:
        print("WARNING: no supplier prices read from the app database.")
    build_suppliers(book.create_sheet("Suppliers"), prices)
    build_price_list(book.create_sheet("Supplier Price List"), prices)

    book.save(output_path)
    return output_path


def main():
    args = sys.argv[1:]
    output = args[0] if args else None
    fy_start_year = int(args[1]) if len(args) > 1 else 2026

    if output is None:
        exports = Path(__file__).resolve().parent.parent / "exports"
        exports.mkdir(exist_ok=True)
        output = exports / f"FacilitiesCo_Accounts_FY{fy_start_year}-{str(fy_start_year + 1)[-2:]}.xlsx"

    path = build(str(output), fy_start_year)
    print(f"Written: {path}")


if __name__ == "__main__":
    main()
