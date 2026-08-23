"""Financial statements built off the single-entry ledger.

The figures matter more than usual here - a wrong month bucket or a
double-counted transfer is the kind of error that looks plausible on
screen and is only caught by arithmetic.
"""

import os
import tempfile

import pytest

from core.balance_sheet_repository import BalanceSheetRepository
from core.database import Database
from core.financial_statements import (
    FinancialStatementsService,
    financial_year_bounds,
    financial_year_for,
    financial_year_months,
)
from core.ledger_repository import LedgerTransactionRepository
from core.ledger_service import LedgerService
from core.ledger_transaction import EXPENSE, INCOME

ACCOUNT = "Gold Business Account"


@pytest.fixture
def test_db():
    db_path = tempfile.mktemp(suffix=".db")
    database = Database(db_path)
    yield database
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def statements(test_db):
    ledger = LedgerService(repository=LedgerTransactionRepository(db=test_db))
    return FinancialStatementsService(
        ledger_service=ledger,
        balance_sheet_repository=BalanceSheetRepository(db=test_db),
    )


def post(statements, day, amount_minor, kind, category, account=ACCOUNT):
    return statements.ledger_service.add_transaction(
        day, f"{category} {day}", amount_minor, kind, category, account, "", "", "test",
    )


# --------------------------------------------------
# Financial year arithmetic
# --------------------------------------------------

def test_financial_year_runs_march_to_february():
    start, end = financial_year_bounds(2026)
    assert start == "2026-03-01"
    assert end == "2027-02-28"


def test_february_belongs_to_the_previous_financial_year():
    assert financial_year_for("2027-02-15") == 2026
    assert financial_year_for("2027-03-01") == 2027


def test_leap_february_end_date():
    _, end = financial_year_bounds(2027)
    assert end == "2028-02-29"


def test_twelve_months_starting_at_march():
    months = financial_year_months(2026)
    assert len(months) == 12
    assert months[0][0] == "Mar 26"
    assert months[-1][0] == "Feb 27"


# --------------------------------------------------
# Income statement
# --------------------------------------------------

def test_income_statement_buckets_by_month(statements):
    post(statements, "2026-03-15", 100000, INCOME, "Sales Income")
    post(statements, "2026-05-20", 50000, INCOME, "Sales Income")
    post(statements, "2026-05-25", 20000, EXPENSE, "Accounting")

    result = statements.income_statement(2026)

    sales = next(line for line in result["income"] if line["name"] == "Sales Income")
    assert sales["monthly_minor"][0] == 100000    # March
    assert sales["monthly_minor"][2] == 50000     # May
    assert sales["total_minor"] == 150000

    assert result["expense_total_minor"] == 20000
    assert result["net_profit_minor"] == 130000
    assert result["net_profit_monthly_minor"][2] == 30000


def test_income_statement_excludes_transfers(statements):
    post(statements, "2026-04-01", 100000, INCOME, "Sales Income")
    post(statements, "2026-04-02", 500000, INCOME, "Bank:  Inter-account Transfers")

    result = statements.income_statement(2026)

    assert result["income_total_minor"] == 100000
    assert all(line["name"] != "Bank:  Inter-account Transfers" for line in result["income"])


def test_income_statement_ignores_other_financial_years(statements):
    post(statements, "2026-02-28", 999900, INCOME, "Sales Income")   # FY2025
    post(statements, "2026-03-01", 100000, INCOME, "Sales Income")   # FY2026

    assert statements.income_statement(2026)["income_total_minor"] == 100000


def test_uncategorised_lines_are_still_reported(statements):
    post(statements, "2026-06-01", 30000, EXPENSE, "")

    result = statements.income_statement(2026)
    assert result["expenses"][0]["name"] == "(Uncategorised)"
    assert result["expense_total_minor"] == 30000


# --------------------------------------------------
# Cash flow
# --------------------------------------------------

def test_cash_flow_runs_a_balance_across_the_year(statements):
    post(statements, "2026-03-10", 100000, INCOME, "Sales Income")
    post(statements, "2026-04-10", 40000, EXPENSE, "Accounting")

    result = statements.cash_flow(2026)

    assert result["receipts_monthly_minor"][0] == 100000
    assert result["payments_monthly_minor"][1] == 40000
    assert result["closing_monthly_minor"][0] == 100000
    assert result["closing_monthly_minor"][1] == 60000
    assert result["closing_minor"] == 60000


def test_cash_flow_counts_transfers(statements):
    """A transfer is not income, but it genuinely moves cash - the income
    statement must exclude it and the cash flow must not."""

    post(statements, "2026-03-10", 100000, INCOME, "Bank:  Inter-account Transfers")

    assert statements.income_statement(2026)["income_total_minor"] == 0
    assert statements.cash_flow(2026)["receipts_minor"] == 100000


def test_cash_flow_starts_from_the_opening_balance(statements):
    account = next(
        row for row in statements.balance_sheet_repository.list_accounts()
        if row.is_cash
    )
    account.ledger_account = ACCOUNT
    statements.balance_sheet_repository.save_account(account, "test")
    statements.balance_sheet_repository.set_opening_balance(account.id, 2026, 250000, "test")

    post(statements, "2026-03-10", 100000, INCOME, "Sales Income")

    result = statements.cash_flow(2026, account=ACCOUNT)
    assert result["opening_minor"] == 250000
    assert result["closing_minor"] == 350000


# --------------------------------------------------
# Balance sheet
# --------------------------------------------------

def test_balance_sheet_derives_movement_for_linked_cash_accounts(statements):
    repository = statements.balance_sheet_repository
    bank = next(row for row in repository.list_accounts() if row.is_cash)
    bank.ledger_account = ACCOUNT
    repository.save_account(bank, "test")
    repository.set_opening_balance(bank.id, 2026, 100000, "test")

    post(statements, "2026-05-01", 60000, INCOME, "Sales Income")
    post(statements, "2026-05-02", 10000, EXPENSE, "Accounting")

    result = statements.balance_sheet(2026)
    line = next(
        line
        for group in result["groups"]
        for line in group["lines"]
        if line["account_id"] == bank.id
    )

    assert line["opening_minor"] == 100000
    assert line["movement_minor"] == 50000
    assert line["closing_minor"] == 150000
    assert line["derived"] is True


def test_balance_sheet_flags_accounts_it_cannot_derive(statements):
    repository = statements.balance_sheet_repository
    creditors = next(row for row in repository.list_accounts() if row.name.startswith("Trade Creditors"))
    repository.set_opening_balance(creditors.id, 2026, 80000, "test")

    result = statements.balance_sheet(2026)
    line = next(
        line
        for group in result["groups"]
        for line in group["lines"]
        if line["account_id"] == creditors.id
    )

    assert line["derived"] is False
    assert line["closing_minor"] == 80000


def test_balance_sheet_reports_the_profit_for_the_year(statements):
    post(statements, "2026-07-01", 200000, INCOME, "Sales Income")
    post(statements, "2026-07-02", 50000, EXPENSE, "Accounting")

    assert statements.balance_sheet(2026)["profit_for_year_minor"] == 150000


def test_balance_sheet_balances_when_the_two_sides_agree(statements):
    """Assets = liabilities + equity + profit. Post the profit as cash and
    put the matching credit in equity, and it must come out nil."""

    repository = statements.balance_sheet_repository
    bank = next(row for row in repository.list_accounts() if row.is_cash)
    bank.ledger_account = ACCOUNT
    repository.save_account(bank, "test")

    post(statements, "2026-07-01", 200000, INCOME, "Sales Income")

    result = statements.balance_sheet(2026)
    assert result["total_assets_minor"] == 200000
    assert result["profit_for_year_minor"] == 200000
    assert result["difference_minor"] == 0
    assert result["balanced"] is True


# --------------------------------------------------
# Years available
# --------------------------------------------------

def test_available_years_come_from_the_transactions(statements):
    post(statements, "2025-06-01", 10000, INCOME, "Sales Income")
    post(statements, "2026-06-01", 10000, INCOME, "Sales Income")

    years = statements.available_financial_years()
    assert 2025 in years
    assert 2026 in years
    assert years == sorted(years, reverse=True)
