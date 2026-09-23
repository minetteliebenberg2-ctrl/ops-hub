import os
import tempfile

import pytest

from core.database import Database
from core.ledger_repository import LedgerTransactionRepository
from core.ledger_service import LedgerService
from core.ledger_transaction import EXPENSE, INCOME, SOURCE_BANK_IMPORT, SOURCE_MANUAL


@pytest.fixture
def test_db():
    db_path = tempfile.mktemp(suffix=".db")
    database = Database(db_path)
    yield database
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def ledger_service(test_db):
    return LedgerService(repository=LedgerTransactionRepository(db=test_db))


FNB_SAMPLE = """ACCOUNT TRANSACTION HISTORY

Name:, Minette, Liebenberg
Account:, 63130416414, [Gold Business Account]
Balance:, 1796.48, 764.27

Date, Amount, Balance, Description
2026/04/02, -1000.00, 1796.48, ML
2026/04/02, -2450.00, 2796.48, MNV PROJECTS
2026/04/01, -391.63, 5246.48, LILY PHARMACY       485442*7275  30 MAR
2026/04/01, -29.90, 5638.11, SASOL DALPARK       485442*7275  30 MAR
2026/03/31, -55.36, 6594.42, #SERVICE FEES
2026/03/31, 15000.00, 6649.78, CLIENT PAYMENT RECEIVED
"""


def write_sample_csv(tmp_path, content=FNB_SAMPLE, name="statement.csv"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_add_transaction_manual(ledger_service):
    transaction = ledger_service.add_transaction(
        "2026-08-04", "Cash deposit", 50000, INCOME, "Sales Income", "Gold Business Account", "", "", "minette",
    )
    assert transaction.source == SOURCE_MANUAL
    assert transaction.amount_minor == 50000


def test_add_transaction_rejects_zero_amount(ledger_service):
    with pytest.raises(ValueError):
        ledger_service.add_transaction(
            "2026-08-04", "Bad", 0, EXPENSE, "", "Personal Account", "", "", "minette",
        )


def test_import_bank_statement_parses_and_categorizes(ledger_service, tmp_path):
    filepath = write_sample_csv(tmp_path)

    result = ledger_service.import_bank_statement(filepath, "minette")

    assert result["account"] == "Gold Business Account"
    assert result["imported"] == 6
    assert result["skipped_duplicates"] == 0

    transactions = ledger_service.list_transactions()
    assert len(transactions) == 6
    assert all(t.source == SOURCE_BANK_IMPORT for t in transactions)

    # Ops Hub went generic on 2026-09-23: the payee/merchant-name rules
    # were stripped from AUTO_CATEGORY_RULES, so anything that isn't a
    # bank-generated description imports UNCATEGORISED and is tagged by
    # hand or through bulk recategorise.
    pharmacy = next(t for t in transactions if "PHARMACY" in t.description)
    assert pharmacy.category == ""
    assert pharmacy.transaction_type == EXPENSE
    assert pharmacy.amount_minor == 39163

    income_row = next(t for t in transactions if t.transaction_type == INCOME)
    assert income_row.amount_minor == 1500000

    # The neutral rules that survive: bank-generated descriptions only.
    fees = next(t for t in transactions if "SERVICE FEES" in t.description)
    assert fees.category == "Bank Fees"

    fuel = next(t for t in transactions if "SASOL" in t.description)
    assert fuel.category == ""


def test_reimporting_same_statement_skips_all_as_duplicates(ledger_service, tmp_path):
    filepath = write_sample_csv(tmp_path)
    ledger_service.import_bank_statement(filepath, "minette")

    result = ledger_service.import_bank_statement(filepath, "minette")

    assert result["imported"] == 0
    assert result["skipped_duplicates"] == 6
    assert len(ledger_service.list_transactions()) == 6


def test_reimport_with_one_new_row_only_imports_the_new_one(ledger_service, tmp_path):
    filepath = write_sample_csv(tmp_path)
    ledger_service.import_bank_statement(filepath, "minette")

    extended = FNB_SAMPLE + "2026/04/03, -100.00, 696.48, NEW TRANSACTION\n"
    filepath2 = write_sample_csv(tmp_path, extended, "statement2.csv")

    result = ledger_service.import_bank_statement(filepath2, "minette")

    assert result["imported"] == 1
    assert result["skipped_duplicates"] == 6
    assert len(ledger_service.list_transactions()) == 7


def test_genuinely_repeated_same_day_transaction_is_not_wrongly_deduped(ledger_service, tmp_path):
    content = FNB_SAMPLE + "2026/04/02, -1000.00, 796.48, ML\n"
    filepath = write_sample_csv(tmp_path, content)

    result = ledger_service.import_bank_statement(filepath, "minette")

    # Two identical "ML" -1000.00 rows on the same date both get imported
    assert result["imported"] == 7
    assert result["skipped_duplicates"] == 0


def test_account_override_takes_precedence_over_parsed_label(ledger_service, tmp_path):
    filepath = write_sample_csv(tmp_path)

    result = ledger_service.import_bank_statement(filepath, "minette", account_override="Personal Account")

    assert result["account"] == "Personal Account"


def test_get_summary_totals_income_and_expenses(ledger_service, tmp_path):
    filepath = write_sample_csv(tmp_path)
    ledger_service.import_bank_statement(filepath, "minette")

    summary = ledger_service.get_summary()

    assert summary["transaction_count"] == 6
    assert summary["total_income_minor"] == 1500000
    # Every expense row counts now: with the payee-name rules gone the
    # pharmacy row (39163) imports uncategorised instead of landing in
    # "Pharmacy", which is one of the TRANSFER_LIKE_CATEGORIES that get
    # excluded from expense totals.
    assert summary["total_expenses_minor"] == 1000 * 100 + 2450 * 100 + 39163 + 2990 + 5536
    assert summary["net_profit_minor"] == summary["total_income_minor"] - summary["total_expenses_minor"]
    assert "2026-04" in summary["by_month"]
    assert "2026-03" in summary["by_month"]


def test_transfer_like_categories_excluded_from_totals_not_from_ledger(ledger_service):
    """Confirmed with Minette 2026-08-04: personal funds moved into the
    business and unassigned/family receipts are real money movements
    (stay visible in the ledger and category breakdown) but must not
    inflate Total Income - she uses her own money to fund the business
    and doesn't want that counted as revenue."""

    ledger_service.add_transaction(
        "2026-08-01", "Sale to client", 100000, INCOME, "Sales Income", "Gold Business Account", "", "", "minette",
    )
    ledger_service.add_transaction(
        "2026-08-02", "FNB APP TRANSFER FROM ML", 50000, INCOME, "Bank:  Inter-account Transfers",
        "Gold Business Account", "", "", "minette",
    )
    ledger_service.add_transaction(
        "2026-08-03", "Payment from Janene", 20000, INCOME, "Unassigned Receipts",
        "Gold Business Account", "", "", "minette",
    )

    summary = ledger_service.get_summary()

    # Only the real sale counts toward Total Income
    assert summary["total_income_minor"] == 100000
    # But all three transactions are still visible in the ledger itself
    assert len(ledger_service.list_transactions()) == 3
    # And still show up in the category breakdown for audit purposes
    assert "Income/Bank:  Inter-account Transfers" in summary["by_category"]
    assert "Income/Unassigned Receipts" in summary["by_category"]
    # But not in the monthly trend chart data (also a "totals" view)
    assert summary["by_month"]["2026-08"]["Income"] == 100000


def test_update_category(ledger_service, tmp_path):
    filepath = write_sample_csv(tmp_path)
    ledger_service.import_bank_statement(filepath, "minette")
    transaction = ledger_service.list_transactions()[0]

    ledger_service.update_category(transaction.id, "Materials & Supplies")

    updated = ledger_service.repository.get(transaction.id)
    assert updated.category == "Materials & Supplies"


def test_delete_transaction(ledger_service, tmp_path):
    filepath = write_sample_csv(tmp_path)
    ledger_service.import_bank_statement(filepath, "minette")
    transaction = ledger_service.list_transactions()[0]

    ledger_service.delete_transaction(transaction.id)

    assert ledger_service.repository.get(transaction.id) is None
    assert len(ledger_service.list_transactions()) == 5
