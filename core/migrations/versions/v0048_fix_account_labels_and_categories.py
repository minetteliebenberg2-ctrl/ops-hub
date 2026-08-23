from core.migrations.runner import Migration, migration_checksum

PAYLOAD = """
-- 1. Fix 16 transactions from 631 CSV that leaked into Personal Account
UPDATE ledger_transactions SET account = 'Gold Business Account'
    WHERE account = 'Personal Account' AND import_batch = '63130416414.csv';

-- 2. Merge Bookkeeping Import into Gold Business Account (all from 631)
UPDATE ledger_transactions SET account = 'Gold Business Account'
    WHERE account = 'Bookkeeping Import';

-- 3. Rename old category names to v21 equivalents (all accounts)
UPDATE ledger_transactions SET category = 'Bank Fees'
    WHERE category = 'Bank Charges';
UPDATE ledger_transactions SET category = 'Credit Card Payment'
    WHERE category = 'Credit Card Expenses';
UPDATE ledger_transactions SET category = 'Cell Phone/Communication'
    WHERE category = 'Telephone / Fax / Internet';
UPDATE ledger_transactions SET category = 'Business Meals'
    WHERE category = 'Entertainment & Meals';

-- 4. Fix specific merchant categorisations
UPDATE ledger_transactions SET category = 'Subcontractor Wages'
    WHERE UPPER(description) LIKE '%GEORGE LOBISI%' AND (category IS NULL OR category = '');
UPDATE ledger_transactions SET category = 'Subcontractor Wages'
    WHERE UPPER(description) LIKE '%GEORGE GEORGE%' AND (category IS NULL OR category = '');
UPDATE ledger_transactions SET category = 'Hardware'
    WHERE UPPER(description) LIKE '%ALSTAN INDUSTRIAL%' AND (category IS NULL OR category = '');

-- 5. Add missing categories to the dropdown
INSERT OR IGNORE INTO ledger_categories (id, name, category_type, active, created_at, updated_at)
    VALUES ('cat_catering', 'Catering', 'Expense', 1, datetime('now'), datetime('now'));
INSERT OR IGNORE INTO ledger_categories (id, name, category_type, active, created_at, updated_at)
    VALUES ('cat_fee_consulting', 'Fee / Consulting Income', 'Income', 1, datetime('now'), datetime('now'));
INSERT OR IGNORE INTO ledger_categories (id, name, category_type, active, created_at, updated_at)
    VALUES ('cat_workmans_comp', 'Workman''s Comp / COIDA', 'Expense', 1, datetime('now'), datetime('now'));
INSERT OR IGNORE INTO ledger_categories (id, name, category_type, active, created_at, updated_at)
    VALUES ('cat_hardware', 'Hardware', 'Expense', 1, datetime('now'), datetime('now'));

-- 6. Fix WormkmansComp typo
UPDATE ledger_transactions SET category = 'Workman''s Comp / COIDA'
    WHERE category = 'WormkmansComp';
"""


def _auto_categorize(connection):
    """Run auto-category rules over uncategorized bank-import transactions."""
    from core.ledger_service import AUTO_CATEGORY_RULES

    rows = connection.execute(
        """
        SELECT id, description FROM ledger_transactions
        WHERE (category IS NULL OR category = '')
          AND account IN ('Gold Business Account', 'Personal Account')
        """
    ).fetchall()

    for row in rows:
        txn_id = row[0]
        desc_upper = row[1].upper()
        for keyword, category in AUTO_CATEGORY_RULES:
            if keyword in desc_upper:
                connection.execute(
                    "UPDATE ledger_transactions SET category = ? WHERE id = ?",
                    (category, txn_id),
                )
                break


def apply(connection):
    for statement in PAYLOAD.strip().split(";"):
        lines = [ln for ln in statement.strip().splitlines()
                 if ln.strip() and not ln.strip().startswith("--")]
        sql = "\n".join(lines).strip()
        if sql:
            connection.execute(sql)
    _auto_categorize(connection)


def verify(connection):
    # No Bookkeeping Import account should remain
    row = connection.execute(
        "SELECT COUNT(*) FROM ledger_transactions WHERE account = 'Bookkeeping Import'"
    ).fetchone()
    assert row[0] == 0, "Bookkeeping Import transactions still present"

    # No 631 CSV transactions in Personal Account
    row = connection.execute(
        "SELECT COUNT(*) FROM ledger_transactions "
        "WHERE account = 'Personal Account' AND import_batch = '63130416414.csv'"
    ).fetchone()
    assert row[0] == 0, "631 CSV transactions still in Personal Account"

    # No old category names
    for old_name in ("Bank Charges", "Credit Card Expenses",
                     "Telephone / Fax / Internet", "Entertainment & Meals",
                     "WormkmansComp"):
        row = connection.execute(
            "SELECT COUNT(*) FROM ledger_transactions WHERE category = ?",
            (old_name,),
        ).fetchone()
        assert row[0] == 0, f"Old category name still present: {old_name}"


MIGRATION = Migration(
    version=48,
    name="fix_account_labels_and_categories",
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
