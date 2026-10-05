"""Money Owing: ageing of unpaid Tax Invoices and bank-credit matching.

Read-only over quotes, site visits and job cards. The only writes are
payments and payment allocations, made through PaymentService.
"""

from datetime import date, datetime

from core.database import database

LEDGER_REF = "LEDGER:"
START_DATE = "2026-08-01"
BUCKETS = ("Current", "1-30", "31-60", "61-90", "90+")


def bucket_for(days_overdue):
    if days_overdue <= 0:
        return 0
    if days_overdue <= 30:
        return 1
    if days_overdue <= 60:
        return 2
    if days_overdue <= 90:
        return 3
    return 4


class MoneyOwingService:

    def __init__(self, payment_service=None, crm_service=None, db=None):
        from core.payment_service import PaymentService
        from core.crm_service import CRMService
        self.db = db or database
        self.payments = payment_service or PaymentService()
        self.crm = crm_service or CRMService()

    def _customer_names(self):
        return {c.id: c.name for c in self.crm.list_customers()}

    def open_invoices(self):
        names = self._customer_names()
        rows = []
        for item in self.payments.list_invoices_with_status():
            if item["balance_minor"] <= 0:
                continue
            doc = item["document"]
            rows.append({
                "customer_id": doc.customer_id,
                "customer": names.get(doc.customer_id, "Unknown"),
                "document_id": doc.id,
                "number": doc.document_number,
                "issue_date": doc.issue_date,
                "due_date": doc.due_date,
                "total_minor": doc.total_minor,
                "paid_minor": item["allocated_minor"],
                "balance_minor": item["balance_minor"],
                "days_overdue": item["days_overdue"],
            })
        return rows

    def ageing_by_customer(self):
        result = {}
        for row in self.open_invoices():
            entry = result.setdefault(row["customer_id"], {
                "customer_id": row["customer_id"], "customer": row["customer"],
                "buckets": [0] * 5, "total": 0,
            })
            entry["buckets"][bucket_for(row["days_overdue"])] += row["balance_minor"]
            entry["total"] += row["balance_minor"]
        return sorted(result.values(), key=lambda e: -e["total"])

    def invoices_for(self, customer_id):
        return [r for r in self.open_invoices() if r["customer_id"] == customer_id]

    def unmatched_credits(self):
        """Gold Business income since START_DATE not yet logged as a payment."""
        used = {p.reference for p in self.payments.list_payments()
                if (p.reference or "").startswith(LEDGER_REF)}
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, date, description, amount_minor FROM ledger_transactions "
                "WHERE transaction_type = 'Income' AND date >= ? "
                "AND lower(account) LIKE '%business%' "
                "AND category = 'Sales Income' ORDER BY date DESC", (START_DATE,)
            ).fetchall()
        return [dict(r) for r in rows if LEDGER_REF + r["id"] not in used]

    def suggest(self, credit):
        """Best open invoice for a credit: exact balance, else name hit."""
        invoices = self.open_invoices()
        exact = [i for i in invoices if i["balance_minor"] == credit["amount_minor"]]
        if exact:
            return exact[0]
        text = (credit["description"] or "").lower()
        for i in invoices:
            if any(w in text for w in i["customer"].lower().split() if len(w) > 3):
                return i
        return None

    def match(self, credit, customer_id, splits, actor="Money Owing"):
        """splits: [(document_id, amount_minor)]. Logs the payment, allocates."""
        total = sum(a for _, a in splits)
        if total > credit["amount_minor"]:
            raise ValueError("Allocations exceed the bank credit.")
        payment = self.payments.log_payment(
            customer_id, credit["amount_minor"], credit["date"],
            LEDGER_REF + credit["id"], credit["description"], actor)
        for doc_id, amount in splits:
            self.payments.allocate(payment.id, doc_id, amount, actor)
        return payment

    def unmatch(self, payment_id, actor="Money Owing"):
        for alloc in self.payments.list_allocations_for_payment(payment_id):
            if alloc.amount_minor > 0:
                self.payments.unallocate(alloc.id, actor)
        self.payments.payments.delete(payment_id)
