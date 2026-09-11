"""Annual Compliance — data layer (repositories + dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from core.database import database


# ── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass
class AnnualReturn:
    id: Optional[int]
    financial_year: str          # e.g. "FY2026"
    year_end: str                # ISO date "2026-02-28"
    revenue: float = 0.0
    advertising: float = 0.0
    cogs: float = 0.0
    insurance: float = 0.0
    interest_expense: float = 0.0
    office_supplies: float = 0.0
    sub_contractors: float = 0.0
    other_expenses: float = 0.0
    monthly_salary: float = 0.0
    director_total_earnings: float = 0.0
    roe_submitted: bool = False
    roe_submitted_date: Optional[str] = None
    logs_expiry: Optional[str] = None
    logs_certificate_no: Optional[str] = None
    assessment_amount: float = 0.0
    assessment_paid: bool = False
    coida_credit: float = 0.0
    notes: str = ""

    @property
    def total_expenses(self) -> float:
        return (self.advertising + self.cogs + self.insurance +
                self.interest_expense + self.office_supplies +
                self.sub_contractors + self.other_expenses)

    @property
    def net_income_before_tax(self) -> float:
        return self.revenue - self.total_expenses

    @property
    def tax_provision(self) -> float:
        return round(max(0.0, self.net_income_before_tax) * 0.20, 2)

    @property
    def net_income(self) -> float:
        return round(self.net_income_before_tax - self.tax_provision, 2)

    @property
    def logs_status(self) -> str:
        """'OK' / 'EXPIRING' (within 60 days) / 'EXPIRED' / 'NONE'."""
        if not self.logs_expiry:
            return "NONE"
        try:
            exp = date.fromisoformat(self.logs_expiry)
        except ValueError:
            return "NONE"
        today = date.today()
        if exp < today:
            return "EXPIRED"
        if (exp - today).days <= 60:
            return "EXPIRING"
        return "OK"

    @property
    def roe_status(self) -> str:
        return "Submitted" if self.roe_submitted else "Pending"


@dataclass
class Payslip:
    id: Optional[int]
    period: str                  # "YYYY-MM"
    employee_name: str = ""
    gross_salary: float = 0.0
    uif_employee: float = 0.0
    uif_employer: float = 0.0
    net_salary: float = 0.0
    pdf_path: Optional[str] = None
    generated_at: Optional[str] = None

    @property
    def period_label(self) -> str:
        try:
            d = datetime.strptime(self.period, "%Y-%m")
            return d.strftime("%B %Y")
        except ValueError:
            return self.period


# ── Repositories ─────────────────────────────────────────────────────────────

class AnnualReturnRepository:

    _COLS = (
        "financial_year", "year_end", "revenue", "advertising", "cogs",
        "insurance", "interest_expense", "office_supplies", "sub_contractors",
        "other_expenses", "monthly_salary", "director_total_earnings",
        "roe_submitted", "roe_submitted_date", "logs_expiry",
        "logs_certificate_no", "assessment_amount", "assessment_paid",
        "coida_credit", "notes",
    )

    def _row_to_obj(self, row) -> AnnualReturn:
        return AnnualReturn(
            id=row["id"],
            financial_year=row["financial_year"],
            year_end=row["year_end"],
            revenue=row["revenue"] or 0.0,
            advertising=row["advertising"] or 0.0,
            cogs=row["cogs"] or 0.0,
            insurance=row["insurance"] or 0.0,
            interest_expense=row["interest_expense"] or 0.0,
            office_supplies=row["office_supplies"] or 0.0,
            sub_contractors=row["sub_contractors"] or 0.0,
            other_expenses=row["other_expenses"] or 0.0,
            monthly_salary=row["monthly_salary"] or 0.0,
            director_total_earnings=row["director_total_earnings"] or 0.0,
            roe_submitted=bool(row["roe_submitted"]),
            roe_submitted_date=row["roe_submitted_date"],
            logs_expiry=row["logs_expiry"],
            logs_certificate_no=row["logs_certificate_no"],
            assessment_amount=row["assessment_amount"] or 0.0,
            assessment_paid=bool(row["assessment_paid"]),
            coida_credit=row["coida_credit"] or 0.0,
            notes=row["notes"] or "",
        )

    def list_all(self) -> list[AnnualReturn]:
        with database.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM coida_annual_returns ORDER BY year_end DESC"
            ).fetchall()
        return [self._row_to_obj(r) for r in rows]

    def get(self, annual_return_id: int) -> Optional[AnnualReturn]:
        with database.connect() as conn:
            row = conn.execute(
                "SELECT * FROM coida_annual_returns WHERE id = ?",
                (annual_return_id,)
            ).fetchone()
        return self._row_to_obj(row) if row else None

    def save(self, ar: AnnualReturn) -> AnnualReturn:
        vals = (
            ar.financial_year, ar.year_end, ar.revenue, ar.advertising,
            ar.cogs, ar.insurance, ar.interest_expense, ar.office_supplies,
            ar.sub_contractors, ar.other_expenses, ar.monthly_salary,
            ar.director_total_earnings, int(ar.roe_submitted),
            ar.roe_submitted_date, ar.logs_expiry, ar.logs_certificate_no,
            ar.assessment_amount, int(ar.assessment_paid),
            ar.coida_credit, ar.notes,
        )
        with database.connect() as conn:
            if ar.id is None:
                placeholders = ", ".join(["?"] * len(self._COLS))
                col_list = ", ".join(self._COLS)
                cur = conn.execute(
                    f"INSERT INTO coida_annual_returns ({col_list}) VALUES ({placeholders})",
                    vals,
                )
                ar.id = cur.lastrowid
            else:
                set_clause = ", ".join(f"{c} = ?" for c in self._COLS)
                conn.execute(
                    f"UPDATE coida_annual_returns SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                    (*vals, ar.id),
                )
        return ar

    def delete(self, annual_return_id: int):
        with database.connect() as conn:
            conn.execute(
                "DELETE FROM coida_annual_returns WHERE id = ?",
                (annual_return_id,)
            )


class PayslipRepository:

    def _row_to_obj(self, row) -> Payslip:
        return Payslip(
            id=row["id"],
            period=row["period"],
            employee_name=row["employee_name"],
            gross_salary=row["gross_salary"] or 0.0,
            uif_employee=row["uif_employee"] or 0.0,
            uif_employer=row["uif_employer"] or 0.0,
            net_salary=row["net_salary"] or 0.0,
            pdf_path=row["pdf_path"],
            generated_at=row["generated_at"],
        )

    def list_all(self) -> list[Payslip]:
        with database.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM payslips ORDER BY period DESC"
            ).fetchall()
        return [self._row_to_obj(r) for r in rows]

    def save(self, slip: Payslip) -> Payslip:
        with database.connect() as conn:
            if slip.id is None:
                cur = conn.execute(
                    """INSERT INTO payslips
                       (period, employee_name, gross_salary,
                        uif_employee, uif_employer, net_salary, pdf_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (slip.period, slip.employee_name, slip.gross_salary,
                     slip.uif_employee, slip.uif_employer,
                     slip.net_salary, slip.pdf_path),
                )
                slip.id = cur.lastrowid
            else:
                conn.execute(
                    """UPDATE payslips SET period=?, employee_name=?,
                       gross_salary=?, uif_employee=?, uif_employer=?,
                       net_salary=?, pdf_path=?
                       WHERE id=?""",
                    (slip.period, slip.employee_name, slip.gross_salary,
                     slip.uif_employee, slip.uif_employer,
                     slip.net_salary, slip.pdf_path, slip.id),
                )
        return slip

    def delete(self, payslip_id: int):
        with database.connect() as conn:
            conn.execute("DELETE FROM payslips WHERE id = ?", (payslip_id,))
