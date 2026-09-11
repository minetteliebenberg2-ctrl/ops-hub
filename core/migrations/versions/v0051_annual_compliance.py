from core.migrations.runner import Migration, migration_checksum

PAYLOAD = """
CREATE TABLE IF NOT EXISTS coida_annual_returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    financial_year TEXT NOT NULL UNIQUE,
    year_end TEXT NOT NULL,
    revenue REAL NOT NULL DEFAULT 0,
    advertising REAL NOT NULL DEFAULT 0,
    cogs REAL NOT NULL DEFAULT 0,
    insurance REAL NOT NULL DEFAULT 0,
    interest_expense REAL NOT NULL DEFAULT 0,
    office_supplies REAL NOT NULL DEFAULT 0,
    sub_contractors REAL NOT NULL DEFAULT 0,
    other_expenses REAL NOT NULL DEFAULT 0,
    monthly_salary REAL NOT NULL DEFAULT 0,
    director_total_earnings REAL NOT NULL DEFAULT 0,
    roe_submitted INTEGER NOT NULL DEFAULT 0,
    roe_submitted_date TEXT,
    logs_expiry TEXT,
    logs_certificate_no TEXT,
    assessment_amount REAL NOT NULL DEFAULT 0,
    assessment_paid INTEGER NOT NULL DEFAULT 0,
    coida_credit REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payslips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL,
    employee_name TEXT NOT NULL DEFAULT 'Minette Liebenberg',
    gross_salary REAL NOT NULL DEFAULT 0,
    uif_employee REAL NOT NULL DEFAULT 0,
    uif_employer REAL NOT NULL DEFAULT 0,
    net_salary REAL NOT NULL DEFAULT 0,
    pdf_path TEXT,
    generated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO coida_annual_returns
    (financial_year, year_end, revenue, advertising, cogs, insurance,
     interest_expense, office_supplies, sub_contractors, other_expenses,
     monthly_salary, director_total_earnings,
     roe_submitted, roe_submitted_date,
     logs_expiry, logs_certificate_no,
     assessment_amount, assessment_paid, coida_credit, notes)
VALUES
    ('FY2025', '2025-02-28', 78480.00, 200.00, 15479.60, 1091.00,
     1450.00, 431.20, 54577.00, 0.00,
     900.00, 10800.00,
     1, '2025-05-01',
     NULL, NULL,
     3304.00, 1, 0.00,
     'First year of trading. ROE submitted May 2025. Assessment paid in full Nov 2025.'),
    ('FY2026', '2026-02-28', 73800.00, 200.00, 12000.00, 1091.00,
     1500.00, 600.00, 42000.00, 0.00,
     1000.00, 12000.00,
     0, NULL,
     '2026-04-30', '2024166585',
     0.00, 0, 1700.00,
     'LOGS expired 30 Apr 2026. R1,700 credit on COIDA account. ROE not yet submitted. Dispute letter sent re min assessment FY2024.');
"""


def apply(connection):
    for statement in PAYLOAD.strip().split(";"):
        sql = statement.strip()
        if sql:
            connection.execute(sql)


def verify(connection):
    r1 = connection.execute("SELECT COUNT(*) FROM coida_annual_returns").fetchone()
    r2 = connection.execute("SELECT COUNT(*) FROM payslips").fetchone()
    assert r1[0] >= 2, "coida_annual_returns not seeded"
    assert r2[0] >= 0, "payslips table not created"


MIGRATION = Migration(
    version=51,
    name="annual_compliance",
    checksum="f22c75053a59e96c93d64360655acaa60ef0e14c10129e0677d5993d54bdb7be",
    apply=apply,
    verify=verify,
)
