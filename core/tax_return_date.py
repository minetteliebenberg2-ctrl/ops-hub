"""Bi-annual provisional tax return dates.

Provisional tax (IRP6) has two periods in every tax year: the first
falls due at the end of August, the second at the end of February. The
annual ITR14 is carried here too, because she thinks of all three as
"the tax returns" and wants them in one list.

Internal only - nothing in this module reaches a quote, invoice or job
card.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
import uuid

from core.database import database

PERIODS = ("Provisional 1 (Aug)", "Provisional 2 (Feb)", "Annual (ITR14)")

# How many days before the due date the list starts warning.
DUE_SOON_DAYS = 30


def default_due_date(tax_year, period):
    """The statutory due date for a period, given a tax year like '2027'.

    SARS tax years end on the last day of February, so FY2027 runs
    1 March 2026 to 28 February 2027: period 1 falls due 31 August 2026
    and period 2 on the last day of February 2027.
    """

    try:
        year = int(str(tax_year).strip()[-4:])
    except (TypeError, ValueError):
        return ""
    if period == PERIODS[0]:
        return f"{year - 1}-08-31"
    if period == PERIODS[1]:
        last = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
        return f"{year}-02-{last}"
    if period == PERIODS[2]:
        # ITR14 is due 12 months after year end.
        return f"{year + 1}-02-28"
    return ""


def parse_amount(raw):
    """Read an amount typed the South African way, or raise ValueError.

    She types "R 12 500,00" as often as "12500.00", and a naive
    strip-the-commas read turns the first into 1 250 000. So: drop the
    currency symbol and every kind of space, then decide which of
    , and . is the decimal separator - the last one, when both appear,
    and a lone comma followed by one or two digits.
    """

    text = str(raw or "")
    for junk in ("R", "r", " ", " ", " "):
        text = text.replace(junk, "")
    if not text:
        return 0.0

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        tail = text.rsplit(",", 1)[1]
        if text.count(",") == 1 and 1 <= len(tail) <= 2:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")

    return float(text)


@dataclass
class TaxReturnDate:
    id: str = ""
    tax_year: str = ""
    period: str = PERIODS[0]
    due_date: str = ""
    submitted_date: str = ""
    amount: float = 0.0
    paid: bool = False
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def status(self):
        """SUBMITTED / OVERDUE / DUE SOON / UPCOMING / NO DATE."""

        if self.submitted_date:
            return "SUBMITTED"
        if not self.due_date:
            return "NO DATE"
        try:
            due = date.fromisoformat(self.due_date)
        except ValueError:
            return "NO DATE"
        days = (due - date.today()).days
        if days < 0:
            return "OVERDUE"
        if days <= DUE_SOON_DAYS:
            return "DUE SOON"
        return "UPCOMING"


class TaxReturnDateRepository:

    def __init__(self, db=None):
        self.db = db or database

    def list_all(self):
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tax_return_dates ORDER BY tax_year DESC, due_date"
            ).fetchall()
        return [self._to_item(r) for r in rows]

    def get(self, item_id):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM tax_return_dates WHERE id=?", (item_id,)
            ).fetchone()
        return self._to_item(row) if row else None

    def save(self, item):
        now = datetime.now(timezone.utc).isoformat()
        item.updated_at = now
        if not item.id:
            item.id = str(uuid.uuid4())
            item.created_at = now
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO tax_return_dates "
                "(id, tax_year, period, due_date, submitted_date, amount, paid, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET tax_year=?, period=?, due_date=?, "
                "submitted_date=?, amount=?, paid=?, notes=?, updated_at=?",
                (item.id, item.tax_year, item.period, item.due_date, item.submitted_date,
                 item.amount, int(item.paid), item.notes, item.created_at, item.updated_at,
                 item.tax_year, item.period, item.due_date, item.submitted_date,
                 item.amount, int(item.paid), item.notes, item.updated_at),
            )
        return item

    def delete(self, item_id):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM tax_return_dates WHERE id=?", (item_id,))

    @staticmethod
    def _to_item(row):
        keys = row.keys()
        return TaxReturnDate(
            id=row["id"],
            tax_year=row["tax_year"] or "",
            period=row["period"] or "",
            due_date=row["due_date"] or "",
            submitted_date=row["submitted_date"] or "",
            amount=row["amount"] or 0.0,
            paid=bool(row["paid"]),
            notes=row["notes"] or "",
            created_at=row["created_at"] if "created_at" in keys else "",
            updated_at=row["updated_at"] if "updated_at" in keys else "",
        )
