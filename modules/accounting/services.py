# ==========================================================
# FC Hub - Accounting Services
# ----------------------------------------------------------
# Purpose:
# Financial data management, import, categorization, and reporting.
#
# Author: Minette & James
# Version: 1.1 (Enhanced with Excel parsing)
# ==========================================================

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import json
import openpyxl


@dataclass
class Transaction:
    """Single financial transaction"""

    date: str
    description: str
    amount: float
    transaction_type: str  # "Income" or "Expense"
    category: str = ""
    reference: str = ""
    account: str = ""
    notes: str = ""

    def to_dict(self):
        return {
            "date": self.date,
            "description": self.description,
            "amount": self.amount,
            "type": self.transaction_type,
            "category": self.category,
            "reference": self.reference,
            "account": self.account,
            "notes": self.notes,
        }


@dataclass
class FinancialSummary:
    """Summary of financial data"""

    period: str = ""
    total_income: float = 0.0
    total_expenses: float = 0.0
    net_profit: float = 0.0
    transaction_count: int = 0
    transactions_by_category: Dict[str, float] = field(default_factory=dict)
    accounts: List[str] = field(default_factory=list)


class AccountingService:
    """Service for managing accounting data"""

    def __init__(self):
        self.transactions: List[Transaction] = []
        self.categories: Dict[str, str] = self._default_categories()
        self.accounts: List[str] = ["Operating", "Savings", "Credit Card"]

    # --------------------------------------------------

    def _default_categories(self) -> Dict[str, str]:
        """Get default expense and income categories"""
        return {
            "Income": [
                "Service Revenue",
                "Product Sales",
                "Consulting",
                "Maintenance Contracts",
                "Sales Income",
                "Other Income",
            ],
            "Expense": [
                "Salaries & Wages",
                "Materials & Supplies",
                "Vehicle Expenses",
                "Equipment & Tools",
                "Fuel & Transport",
                "Utilities",
                "Rent & Premises",
                "Insurance",
                "Professional Services",
                "Marketing",
                "Office Expenses",
                "Repairs & Maintenance",
                "Interest & Fees",
                "Taxes",
                "Groceries",
                "Pharmacy",
                "Admin Costs",
                "Business Insurance",
                "Payroll Expense",
                "Inter Account Transfer",
                "Miscellaneous",
            ],
        }

    # --------------------------------------------------

    def add_transaction(self, transaction: Transaction):
        """Add a transaction to the ledger"""
        self.transactions.append(transaction)
        self.transactions.sort(key=lambda t: t.date, reverse=True)

    # --------------------------------------------------

    def add_transactions_bulk(self, transactions: List[Transaction]):
        """Import multiple transactions"""
        self.transactions.extend(transactions)
        self.transactions.sort(key=lambda t: t.date, reverse=True)

    # --------------------------------------------------

    def get_transactions(self, filters=None) -> List[Transaction]:
        """Get transactions with optional filters"""
        results = self.transactions

        if not filters:
            return results

        if filters.get("type"):
            results = [t for t in results if t.transaction_type == filters["type"]]

        if filters.get("category"):
            results = [t for t in results if t.category == filters["category"]]

        if filters.get("account"):
            results = [t for t in results if t.account == filters["account"]]

        if filters.get("date_from"):
            results = [t for t in results if t.date >= filters["date_from"]]

        if filters.get("date_to"):
            results = [t for t in results if t.date <= filters["date_to"]]

        return results

    # --------------------------------------------------

    def get_summary(self, date_from=None, date_to=None) -> FinancialSummary:
        """Generate financial summary for period"""
        filtered = self.get_transactions({
            "date_from": date_from,
            "date_to": date_to,
        })

        summary = FinancialSummary(
            period=f"{date_from or 'All'} to {date_to or 'Now'}",
            transaction_count=len(filtered),
        )

        categories_breakdown = {}

        for txn in filtered:
            if txn.transaction_type == "Income":
                summary.total_income += txn.amount
            else:
                summary.total_expenses += txn.amount

            category_key = f"{txn.transaction_type}/{txn.category}"
            categories_breakdown[category_key] = categories_breakdown.get(category_key, 0) + txn.amount

            if txn.account not in summary.accounts:
                summary.accounts.append(txn.account)

        summary.net_profit = summary.total_income - summary.total_expenses
        summary.transactions_by_category = categories_breakdown

        return summary

    # --------------------------------------------------

    def export_transactions(self, filepath, transactions=None):
        """Export transactions to JSON"""
        data = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "transaction_count": len(transactions or self.transactions),
            "transactions": [
                t.to_dict() for t in (transactions or self.transactions)
            ],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # --------------------------------------------------

    def import_transactions(self, filepath):
        """Import transactions from JSON"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            transactions = []
            for item in data.get("transactions", []):
                txn = Transaction(
                    date=item.get("date", ""),
                    description=item.get("description", ""),
                    amount=float(item.get("amount", 0)),
                    transaction_type=item.get("type", "Expense"),
                    category=item.get("category", ""),
                    reference=item.get("reference", ""),
                    account=item.get("account", ""),
                    notes=item.get("notes", ""),
                )
                transactions.append(txn)

            self.add_transactions_bulk(transactions)
            return len(transactions)

        except Exception as e:
            raise ValueError(f"Failed to import transactions: {str(e)}")


class ExcelImportService:
    """Service for importing data from Excel files"""

    def __init__(self):
        pass

    # --------------------------------------------------

    def import_excel_file(self, filepath) -> List[Transaction]:
        """Import transactions from Excel file with auto-detection"""
        try:
            wb = openpyxl.load_workbook(filepath, data_only=True)
            ws = wb.active

            transactions = []

            # Detect columns from first row
            headers = {}
            first_row = list(ws.iter_rows(max_row=1, values_only=True))[0]

            for idx, header in enumerate(first_row):
                if header:
                    header_lower = str(header).lower().strip()
                    if "date" in header_lower:
                        headers["date"] = idx
                    elif "description" in header_lower or "desc" in header_lower:
                        headers["description"] = idx
                    elif "category" in header_lower:
                        headers["category"] = idx
                    elif "account" in header_lower:
                        headers["account"] = idx
                    elif "income" in header_lower:
                        headers["income"] = idx
                    elif "expense" in header_lower:
                        headers["expense"] = idx

            # Extract transactions from data rows
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if not any(cell is not None for cell in row):
                    continue

                try:
                    date_val = row[headers.get("date", 0)] if "date" in headers else None
                    description = str(row[headers.get("description", 1)] or "").strip() if "description" in headers else ""
                    category = str(row[headers.get("category", 2)] or "").strip() if "category" in headers else ""
                    account = str(row[headers.get("account", 3)] or "").strip() if "account" in headers else ""

                    income = row[headers.get("income", 4)] if "income" in headers else None
                    expense = row[headers.get("expense", 5)] if "expense" in headers else None

                    # Skip if no amount
                    if not income and not expense:
                        continue

                    # Determine transaction type and amount
                    if income and (not expense or float(income or 0) > 0):
                        amount = float(income)
                        txn_type = "Income"
                    else:
                        amount = float(expense or 0)
                        txn_type = "Expense"

                    if amount == 0:
                        continue

                    # Format date
                    if date_val:
                        if isinstance(date_val, str):
                            date_str = date_val
                        else:
                            date_str = str(date_val)
                    else:
                        date_str = datetime.now().isoformat(timespec="seconds")

                    txn = Transaction(
                        date=date_str,
                        description=description,
                        amount=abs(amount),
                        transaction_type=txn_type,
                        category=category,
                        account=account,
                    )
                    transactions.append(txn)

                except (ValueError, TypeError):
                    continue

            return transactions

        except Exception as e:
            raise ValueError(f"Failed to import Excel file: {str(e)}")

    # --------------------------------------------------

    def detect_excel_structure(self, filepath) -> Dict:
        """Detect column structure and data format in Excel file"""
        try:
            wb = openpyxl.load_workbook(filepath, data_only=True)
            ws = wb.active

            first_row = list(ws.iter_rows(max_row=1, values_only=True))[0]

            structure = {
                "file": str(filepath),
                "sheets": wb.sheetnames,
                "active_sheet": ws.title,
                "headers": [str(h) for h in first_row if h],
                "row_count": ws.max_row - 1,
            }

            return structure

        except Exception as e:
            return {
                "file": str(filepath),
                "error": str(e),
            }
