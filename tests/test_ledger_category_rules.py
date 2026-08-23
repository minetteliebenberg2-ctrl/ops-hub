import os
import tempfile

import pytest

from core.database import Database
from core.ledger_repository import LedgerTransactionRepository
from core.ledger_service import LedgerService
from core.ledger_transaction import EXPENSE
from core.merchant_key import merchant_key


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


def _add(service, description, category=""):
    return service.add_transaction(
        "2026-06-28", description, 15000, EXPENSE, category, "Gold Business Account", "", "", "minette",
    )


def test_merchant_key_groups_dated_card_variants():
    a = merchant_key("KWIKSPAR HOMESTEAD  485442*7275  28 JUN")
    b = merchant_key("KWIKSPAR HOMESTEAD  485442*7275  24 JUN")
    assert a == b == "KWIKSPAR HOMESTEAD"


def test_find_similar_matches_same_merchant_only(ledger_service):
    t = _add(ledger_service, "KWIKSPAR HOMESTEAD  485442*7275  28 JUN")
    _add(ledger_service, "KWIKSPAR HOMESTEAD  485442*7275  24 JUN")
    _add(ledger_service, "SASOL DALPARK       485442*7275  30 MAR")
    similar = ledger_service.find_similar_transactions(t.description, exclude_id=t.id)
    assert len(similar) == 1


def test_find_similar_respects_same_category_only(ledger_service):
    t = _add(ledger_service, "KWIKSPAR A 111*2222 28 JUN", category="Groceries")
    _add(ledger_service, "KWIKSPAR A 111*2222 24 JUN", category="Uncategorized")
    _add(ledger_service, "KWIKSPAR A 111*2222 20 JUN", category="Fuel")
    similar = ledger_service.find_similar_transactions(
        t.description, exclude_id=t.id, same_category_only="Uncategorized"
    )
    assert len(similar) == 1
    assert similar[0].category == "Uncategorized"


def test_empty_key_never_sweeps_rows(ledger_service):
    _add(ledger_service, "12345 *")
    assert ledger_service.find_similar_transactions("999 *") == []


def test_bulk_update_audits_each_row(ledger_service):
    a = _add(ledger_service, "KWIKSPAR X 1*2 28 JUN", category="Uncategorized")
    b = _add(ledger_service, "KWIKSPAR X 1*2 24 JUN", category="Uncategorized")
    updated = ledger_service.bulk_update_category([a.id, b.id], "Groceries", "minette")
    assert updated == 2
    assert ledger_service.repository.get(a.id).category == "Groceries"


def test_save_rule_then_auto_category_applies_on_import(ledger_service):
    ledger_service.save_category_rule("KWIKSPAR HOMESTEAD", "Groceries", EXPENSE, "minette")
    assert ledger_service._auto_category("KWIKSPAR HOMESTEAD 485442*7275 01 JUL") == "Groceries"


def test_resaving_rule_updates_not_duplicates(ledger_service):
    ledger_service.save_category_rule("WOOLWORTHS", "Groceries", EXPENSE, "minette")
    ledger_service.save_category_rule("WOOLWORTHS", "Clothing", EXPENSE, "minette")
    rules = [r for r in ledger_service.list_category_rules() if r["match_key"] == "WOOLWORTHS"]
    assert len(rules) == 1
    assert rules[0]["category"] == "Clothing"
