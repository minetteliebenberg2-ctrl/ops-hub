import os
import tempfile

import pytest

from core.database import Database
from core.ledger_repository import LedgerTransactionRepository
from core.ledger_service import LedgerService
from core.ledger_transaction import INCOME, SOURCE_LEDGER_IMPORT


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


LEDGER_AUDIT_SAMPLE = (
    "Transaction Analysis - with ledger posting details;;;;;;;;;\r\n"
    "31 August 2026;;;;;;;;;\r\n"
    ";;;;;;;;;\r\n"
    "Posting Date;Transaction Date;Description;Amount;Tax;Category Name;Detail Description;Transaction Type;DR Amount;CR Amount\r\n"
    "2025/09/01;2025/09/01;FFW LI    750000845 SEP 250901;285,94;N;Insurance / Security;;Payment (Auto);285,94;0,00\r\n"
    ";;;;;Gold Business Account;;Payment (Auto);0,00;285,94\r\n"
    "2025/09/02;2025/09/02;FNB APP TRANSFER FROM ML;345,00;N;Gold Business Account;;Receipt (Auto);345,00;0,00\r\n"
    ";;;;;Bank:  Inter-account Transfers;;Receipt (Auto);0,00;345,00\r\n"
    "2025/09/03;2025/09/03;FUEL  AE MARLANDS         4854422149347275 7492;212,10;N;Gold Business Account;;Payment (Auto);0,00;212,10\r\n"
    ";;;;;Motor V: Fuel & Oil;;Payment (Auto);212,10;0,00\r\n"
    "2025/09/03;2025/09/03;ABSA BANK Dominique Fuchsloch;4 000,00;N;Gold Business Account;;Receipt (Auto);4 000,00;0,00\r\n"
    ";;;;;Sales Income;;Receipt (Auto);0,00;4 000,00\r\n"
)


def write_sample(tmp_path, content=LEDGER_AUDIT_SAMPLE, name="ledger_audit.csv"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8-sig")
    return str(path)


def test_import_parses_categories_and_account(ledger_service, tmp_path):
    filepath = write_sample(tmp_path)

    result = ledger_service.import_ledger_audit(filepath, "minette")

    assert result["account"] == "Gold Business Account"
    assert result["imported"] == 4
    assert result["skipped_duplicates"] == 0

    transactions = ledger_service.list_transactions()
    assert len(transactions) == 4
    assert all(t.source == SOURCE_LEDGER_IMPORT for t in transactions)

    fuel = next(t for t in transactions if "FUEL" in t.description)
    assert fuel.category == "Motor V: Fuel & Oil"
    assert fuel.amount_minor == 21210

    transfer = next(t for t in transactions if "TRANSFER FROM ML" in t.description)
    assert transfer.category == "Bank:  Inter-account Transfers"
    assert transfer.transaction_type == INCOME

    sales = next(t for t in transactions if "ABSA BANK" in t.description)
    assert sales.category == "Sales Income"
    assert sales.amount_minor == 400000


def test_reimport_skips_all_as_duplicates(ledger_service, tmp_path):
    filepath = write_sample(tmp_path)
    ledger_service.import_ledger_audit(filepath, "minette")

    result = ledger_service.import_ledger_audit(filepath, "minette")

    assert result["imported"] == 0
    assert result["skipped_duplicates"] == 4


def test_bank_statement_and_ledger_audit_dedupe_against_each_other(ledger_service, tmp_path):
    """Importing the same account from both a bank statement export and
    a ledger audit export shouldn't create duplicates for rows that
    are genuinely the same transaction."""

    fnb_sample = (
        "ACCOUNT TRANSACTION HISTORY\n\n"
        "Name:, Minette, Liebenberg\n"
        "Account:, 63130416414, [Gold Business Account]\n"
        "Balance:, 1796.48, 764.27\n\n"
        "Date, Amount, Balance, Description\n"
        "2025/09/01, -285.94, 1796.48, FFW LI    750000845 SEP 250901\n"
    )
    fnb_path = tmp_path / "fnb.csv"
    fnb_path.write_text(fnb_sample, encoding="utf-8")

    ledger_service.import_bank_statement(str(fnb_path), "minette")
    assert len(ledger_service.list_transactions()) == 1

    audit_path = write_sample(tmp_path)
    result = ledger_service.import_ledger_audit(audit_path, "minette")

    # The FFW LI row already exists (from the bank import) so only the
    # other 3 rows in the audit sample should import.
    assert result["imported"] == 3
    assert result["skipped_duplicates"] == 1
    assert len(ledger_service.list_transactions()) == 4
