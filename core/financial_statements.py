# ==========================================================
# FC Hub - Financial Statements
# ----------------------------------------------------------
# Purpose:
# Income statement, cash flow, balance sheet and bank
# reconciliation for a financial year, built from the existing
# single-entry ledger.
#
# The shape of every statement here matches the standalone Excel
# workbook (tools/build_accounting_workbook.py) on purpose - it is
# the same set of books, one produced by the app and one by hand.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from calendar import monthrange
from datetime import date

from core.balance_sheet_repository import BalanceSheetRepository
from core.ledger_service import TRANSFER_LIKE_CATEGORIES, LedgerService
from core.ledger_transaction import EXPENSE, INCOME

# South African tax year: 1 March to the end of February.
FINANCIAL_YEAR_START_MONTH = 3

MONTH_LABELS = (
    "Mar", "Apr", "May", "Jun", "Jul", "Aug",
    "Sep", "Oct", "Nov", "Dec", "Jan", "Feb",
)


def financial_year_for(day):
    """The financial year a date falls in, named by the calendar year its
    March start falls in. 2027-01-15 belongs to FY2026 (Mar 26 - Feb 27)."""

    if isinstance(day, str):
        day = date.fromisoformat(day[:10])
    return day.year if day.month >= FINANCIAL_YEAR_START_MONTH else day.year - 1


def current_financial_year():
    return financial_year_for(date.today())


def financial_year_months(financial_year):
    """The twelve months of a financial year as
    (label, first_day, last_day) with ISO date strings."""

    months = []
    for offset in range(12):
        month_number = FINANCIAL_YEAR_START_MONTH + offset
        year = financial_year + (month_number - 1) // 12
        month_number = (month_number - 1) % 12 + 1
        last_day = monthrange(year, month_number)[1]
        months.append((
            f"{MONTH_LABELS[offset]} {str(year)[-2:]}",
            f"{year}-{month_number:02d}-01",
            f"{year}-{month_number:02d}-{last_day:02d}",
        ))
    return months


def financial_year_bounds(financial_year):
    months = financial_year_months(financial_year)
    return months[0][1], months[-1][2]


def financial_year_label(financial_year):
    return f"FY{financial_year}/{str(financial_year + 1)[-2:]}"


class FinancialStatementsService:
    """Reads the ledger; never writes to it. Every figure is derived, so
    a statement can always be regenerated from the transactions."""

    def __init__(self, ledger_service=None, balance_sheet_repository=None):
        self.ledger_service = ledger_service or LedgerService()
        self.balance_sheet_repository = balance_sheet_repository or BalanceSheetRepository(
            db=self.ledger_service.repository.db
        )

    # --------------------------------------------------
    # Shared
    # --------------------------------------------------

    def _transactions_for_year(self, financial_year):
        start, end = financial_year_bounds(financial_year)
        return self.ledger_service.list_transactions({"date_from": start, "date_to": end})

    @staticmethod
    def _month_index(transactions_date, months):
        """Which of the twelve month buckets a transaction date falls in,
        or None if it somehow sits outside the year."""

        for index, (_, first, last) in enumerate(months):
            if first <= transactions_date[:10] <= last:
                return index
        return None

    # --------------------------------------------------
    # Income statement
    # --------------------------------------------------

    def income_statement(self, financial_year):
        """Income and expenses by category, one column per month.

        Transfer-like categories are excluded exactly as get_summary
        excludes them - moving money between her own accounts is not
        income, and counting it would overstate every month."""

        months = financial_year_months(financial_year)
        income_rows = {}
        expense_rows = {}

        for transaction in self._transactions_for_year(financial_year):
            if transaction.category in TRANSFER_LIKE_CATEGORIES:
                continue
            index = self._month_index(transaction.date, months)
            if index is None:
                continue

            rows = income_rows if transaction.transaction_type == INCOME else expense_rows
            category = transaction.category or "(Uncategorised)"
            bucket = rows.setdefault(category, [0] * 12)
            bucket[index] += transaction.amount_minor

        def as_lines(rows):
            lines = []
            for name in sorted(rows):
                monthly = rows[name]
                lines.append({
                    "name": name,
                    "monthly_minor": monthly,
                    "total_minor": sum(monthly),
                })
            return lines

        income = as_lines(income_rows)
        expenses = as_lines(expense_rows)

        income_totals = [sum(line["monthly_minor"][i] for line in income) for i in range(12)]
        expense_totals = [sum(line["monthly_minor"][i] for line in expenses) for i in range(12)]
        net = [income_totals[i] - expense_totals[i] for i in range(12)]

        return {
            "financial_year": financial_year,
            "label": financial_year_label(financial_year),
            "months": [label for label, _, _ in months],
            "income": income,
            "expenses": expenses,
            "income_total_monthly_minor": income_totals,
            "expense_total_monthly_minor": expense_totals,
            "net_profit_monthly_minor": net,
            "income_total_minor": sum(income_totals),
            "expense_total_minor": sum(expense_totals),
            "net_profit_minor": sum(net),
        }

    # --------------------------------------------------
    # Cash flow
    # --------------------------------------------------

    def cash_flow(self, financial_year, account=None):
        """Money in and out per month with a running bank balance.

        Unlike the income statement this counts transfers, because a
        transfer really does move cash in or out of an account. Pass an
        account to see one bank account on its own; leave it off for all
        of them combined."""

        months = financial_year_months(financial_year)
        filters = {"date_from": months[0][1], "date_to": months[-1][2]}
        if account:
            filters["account"] = account

        receipts = [0] * 12
        payments = [0] * 12
        for transaction in self.ledger_service.list_transactions(filters):
            index = self._month_index(transaction.date, months)
            if index is None:
                continue
            if transaction.transaction_type == INCOME:
                receipts[index] += transaction.amount_minor
            else:
                payments[index] += transaction.amount_minor

        opening = self.opening_cash_minor(financial_year, account)
        opening_balances = []
        closing_balances = []
        running = opening
        for index in range(12):
            opening_balances.append(running)
            running = running + receipts[index] - payments[index]
            closing_balances.append(running)

        return {
            "financial_year": financial_year,
            "label": financial_year_label(financial_year),
            "account": account or "All accounts",
            "months": [label for label, _, _ in months],
            "opening_monthly_minor": opening_balances,
            "receipts_monthly_minor": receipts,
            "payments_monthly_minor": payments,
            "closing_monthly_minor": closing_balances,
            "opening_minor": opening,
            "receipts_minor": sum(receipts),
            "payments_minor": sum(payments),
            "closing_minor": closing_balances[-1],
        }

    def opening_cash_minor(self, financial_year, account=None):
        """Opening bank balance for the year, from the balance-sheet
        accounts she maintains. One account when asked for, otherwise
        every cash account added together."""

        opening = 0
        for row in self.balance_sheet_repository.list_accounts(active_only=True):
            if not row.is_cash:
                continue
            if account and row.ledger_account != account:
                continue
            opening += self.balance_sheet_repository.opening_balance_minor(row.id, financial_year)
        return opening

    # --------------------------------------------------
    # Balance sheet
    # --------------------------------------------------

    def balance_sheet(self, financial_year):
        """Assets, liabilities and equity at the end of the financial year.

        Opening balances are hers to maintain. Movement is only derivable
        for cash accounts tied to a ledger account - everything else shows
        its opening balance and is flagged so it is obvious which figures
        the app worked out and which it was told."""

        months = financial_year_months(financial_year)
        year_start, year_end = months[0][1], months[-1][2]

        groups = {}
        totals = {"Asset": 0, "Liability": 0, "Equity": 0}

        for row in self.balance_sheet_repository.list_accounts(active_only=True):
            opening = self.balance_sheet_repository.opening_balance_minor(row.id, financial_year)

            movement = 0
            derived = False
            if row.is_cash and row.ledger_account:
                transactions = self.ledger_service.list_transactions({
                    "date_from": year_start,
                    "date_to": year_end,
                    "account": row.ledger_account,
                })
                income = sum(t.amount_minor for t in transactions if t.transaction_type == INCOME)
                expense = sum(t.amount_minor for t in transactions if t.transaction_type == EXPENSE)
                movement = income - expense
                derived = True

            closing = opening + movement
            totals[row.account_type] = totals.get(row.account_type, 0) + closing

            groups.setdefault(row.statement_group, {
                "group": row.statement_group,
                "account_type": row.account_type,
                "lines": [],
            })["lines"].append({
                "account_id": row.id,
                "code": row.code,
                "name": row.name,
                "opening_minor": opening,
                "movement_minor": movement,
                "closing_minor": closing,
                "derived": derived,
            })

        profit = self.income_statement(financial_year)["net_profit_minor"]

        total_assets = totals.get("Asset", 0)
        total_equity_and_liabilities = totals.get("Liability", 0) + totals.get("Equity", 0) + profit

        return {
            "financial_year": financial_year,
            "label": financial_year_label(financial_year),
            "as_at": year_end,
            "groups": list(groups.values()),
            "total_assets_minor": total_assets,
            "total_liabilities_minor": totals.get("Liability", 0),
            "total_equity_minor": totals.get("Equity", 0),
            "profit_for_year_minor": profit,
            "total_equity_and_liabilities_minor": total_equity_and_liabilities,
            "difference_minor": total_assets - total_equity_and_liabilities,
            "balanced": total_assets == total_equity_and_liabilities,
        }

    # --------------------------------------------------
    # Bank reconciliation
    # --------------------------------------------------

    def bank_reconciliation(self, account):
        """Ledger balance against the last imported statement balance.

        Thin wrapper over LedgerService.get_reconciliation - the caveat
        there applies here too: the ledger balance is all-time, so a
        difference may only mean the ledger does not go back as far as
        the account does."""

        reconciliation = self.ledger_service.get_reconciliation(account)
        if reconciliation is None:
            return None

        reconciliation = dict(reconciliation)
        reconciliation["account"] = account
        reconciliation["reconciled"] = reconciliation["difference_minor"] == 0
        return reconciliation

    def bank_reconciliations(self):
        results = []
        for account in self.ledger_service.list_accounts():
            reconciliation = self.bank_reconciliation(account)
            if reconciliation is not None:
                results.append(reconciliation)
        return results

    # --------------------------------------------------

    def available_financial_years(self):
        """Years the ledger actually has transactions in, newest first,
        always including the current one so a fresh install has
        something to show."""

        years = {current_financial_year()}
        for transaction in self.ledger_service.list_transactions():
            if transaction.date:
                years.add(financial_year_for(transaction.date))
        return sorted(years, reverse=True)
