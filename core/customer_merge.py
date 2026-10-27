"""Merge two customer records into one.

Moves all child records from source → target, renumbers documents
with the target customer's prefix, then soft-deletes the source.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone


# Every table with a customer_id FK that should be reassigned.
_CHILD_TABLES = [
    "customer_contacts",
    "customer_addresses",
    "customer_sites",
    "customer_activities",
    "quotes",
    "quote_documents",
    "statements",
    "payments",
    "proposals",
    "job_cards",
    "site_visits",
    "site_images",
    "site_plans",
    "scheduled_jobs",
    "shade_sails",
    "job_cost_allocations",
]

# Tables whose rows carry a number with the customer prefix.
_NUMBERED_TABLES = {
    "quotes": "quote_number",
    "quote_documents": "document_number",
    "job_cards": "job_card_number",
    "statements": "document_number",
}


def _prefix_from(customer_number: str) -> str:
    """'GHH-001' → 'GHH'."""
    return customer_number.split("-")[0] if customer_number else ""


def _renumber(value: str, old_prefix: str, new_prefix: str) -> str:
    """Replace the customer prefix in a document number."""
    if not value or not old_prefix:
        return value
    return re.sub(rf"^{re.escape(old_prefix)}-", f"{new_prefix}-", value)


def _safe_renumber(cursor, table: str, col: str, row_id: str,
                   old_val: str, new_val: str) -> str:
    """Renumber, appending a letter suffix if the new number already exists."""
    candidate = new_val
    for suffix in ["", "b", "c", "d", "e"]:
        test = candidate if not suffix else f"{new_val}{suffix}"
        existing = cursor.execute(
            f"SELECT 1 FROM {table} WHERE {col} = ? AND id != ?",
            (test, row_id),
        ).fetchone()
        if not existing:
            return test
    return old_val


def merge_customers(db, source_id: str, target_id: str, actor: str) -> dict:
    """Merge source customer into target.

    Returns a summary dict with counts of moved records.
    """
    with db.connect() as conn:
        cursor = conn.cursor()

        source = cursor.execute(
            "SELECT id, name, customer_number FROM customers WHERE id = ?",
            (source_id,),
        ).fetchone()
        target = cursor.execute(
            "SELECT id, name, customer_number FROM customers WHERE id = ?",
            (target_id,),
        ).fetchone()

        if not source or not target:
            raise ValueError("Source or target customer not found.")
        if source["id"] == target["id"]:
            raise ValueError("Cannot merge a customer into itself.")

        old_prefix = _prefix_from(source["customer_number"])
        new_prefix = _prefix_from(target["customer_number"])
        now = datetime.now(timezone.utc).isoformat()
        summary = {}

        for table in _CHILD_TABLES:
            try:
                result = cursor.execute(
                    f"UPDATE {table} SET customer_id = ? WHERE customer_id = ?",
                    (target_id, source_id),
                )
                if result.rowcount:
                    summary[table] = result.rowcount
            except Exception:
                pass

        if old_prefix and new_prefix and old_prefix != new_prefix:
            for table, col in _NUMBERED_TABLES.items():
                try:
                    rows = cursor.execute(
                        f"SELECT id, {col} FROM {table} WHERE customer_id = ? AND {col} LIKE ?",
                        (target_id, f"{old_prefix}-%"),
                    ).fetchall()
                    for row in rows:
                        new_val = _renumber(row[col], old_prefix, new_prefix)
                        if new_val != row[col]:
                            final = _safe_renumber(
                                cursor, table, col, row["id"], row[col], new_val,
                            )
                            if final != row[col]:
                                cursor.execute(
                                    f"UPDATE {table} SET {col} = ? WHERE id = ?",
                                    (final, row["id"]),
                                )
                except Exception:
                    pass

            try:
                cursor.execute(
                    "UPDATE quote_documents SET bill_to_name = ? "
                    "WHERE customer_id = ? AND bill_to_name = ?",
                    (target["name"], target_id, source["name"]),
                )
            except Exception:
                pass

        cursor.execute(
            "UPDATE customers SET deleted_at = ?, deleted_by = ?, "
            "notes = COALESCE(notes, '') || ? WHERE id = ?",
            (now, actor,
             f"\n[Merged into {target['name']} ({target['customer_number']}) on {now[:10]}]",
             source_id),
        )

    return summary
