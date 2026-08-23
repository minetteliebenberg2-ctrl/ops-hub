# ==========================================================
# FC Hub - Ledger Excel Export
# ----------------------------------------------------------
# Purpose:
# Export a list of ledger transactions to an .xlsx workbook for the
# accountant - respects whatever filters were active in the Ledger
# window since it's just handed the already-filtered list.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from openpyxl import Workbook

HEADERS = ["Date", "Description", "Category", "Account", "Type", "Amount", "Reference", "Notes", "Source"]


def export_transactions_to_xlsx(transactions, filepath):

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ledger"
    sheet.append(HEADERS)

    for transaction in transactions:
        sheet.append([
            transaction.date,
            transaction.description,
            transaction.category,
            transaction.account,
            transaction.transaction_type,
            transaction.amount_minor / 100,
            transaction.reference,
            transaction.notes,
            transaction.source,
        ])

    workbook.save(filepath)
    return filepath
