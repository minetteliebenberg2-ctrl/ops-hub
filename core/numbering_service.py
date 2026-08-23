# ==========================================================
# FC Hub - Numbering Service
# ----------------------------------------------------------
# Purpose:
# Allocate human-readable document numbers (customer_number,
# and future quote/job/pro-forma/invoice numbers) from the
# numbering_sequences table. Allocation happens on a connection
# supplied by the caller so it commits or rolls back atomically
# with the record being numbered.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime, timezone
from uuid import uuid4


class NumberingError(RuntimeError):

    """Raised when a number cannot be allocated."""


class NumberingService:

    def allocate(
        self,
        connection,
        document_type,
        *,
        scope="global",
        scope_id="",
        prefix=None,
        padding=None,
    ):
        row = connection.execute(
            """
            SELECT prefix, padding, next_value
            FROM numbering_sequences
            WHERE document_type = ? AND scope = ? AND scope_id = ?
            """,
            (document_type, scope, scope_id),
        ).fetchone()

        now = self._timestamp()

        if row is None:
            if prefix is None or padding is None:
                raise NumberingError(
                    f"No numbering sequence exists for document_type={document_type!r}, "
                    f"scope={scope!r}, scope_id={scope_id!r}, and no prefix/padding was "
                    "supplied to create one."
                )
            next_value = 1
            connection.execute(
                """
                INSERT INTO numbering_sequences (
                    id, document_type, scope, scope_id, prefix, padding,
                    next_value, yearly_reset, last_reset_year, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
                """,
                (str(uuid4()), document_type, scope, scope_id, prefix, padding, next_value + 1, now, now),
            )
        else:
            next_value = row["next_value"]
            prefix = row["prefix"]
            padding = row["padding"]
            connection.execute(
                """
                UPDATE numbering_sequences
                SET next_value = ?, updated_at = ?
                WHERE document_type = ? AND scope = ? AND scope_id = ?
                """,
                (next_value + 1, now, document_type, scope, scope_id),
            )

        return f"{prefix}-{next_value:0{padding}d}"

    # --------------------------------------------------

    def allocate_yearly(
        self,
        connection,
        document_type,
        *,
        scope_id,
        prefix,
        padding=3,
        year=None,
    ):
        """Allocate a number in the ``{PREFIX}_{YY}/{NNN}`` form (e.g.
        ``Q_26/001``), scoped per customer (scope_id) and reset to 001
        every calendar year. Used for the Quote/Pro-Forma/Invoice/
        Statement numbering scheme confirmed 2026-08-03, replacing the
        older flat ``FAC-001-Q-001`` style for those document types."""

        year = year or datetime.now().year
        scope = "customer_yearly"

        row = connection.execute(
            """
            SELECT next_value, last_reset_year
            FROM numbering_sequences
            WHERE document_type = ? AND scope = ? AND scope_id = ?
            """,
            (document_type, scope, scope_id),
        ).fetchone()

        now = self._timestamp()

        if row is None:
            next_value = 1
            connection.execute(
                """
                INSERT INTO numbering_sequences (
                    id, document_type, scope, scope_id, prefix, padding,
                    next_value, yearly_reset, last_reset_year, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (str(uuid4()), document_type, scope, scope_id, prefix, padding, next_value + 1, year, now, now),
            )
        else:
            if row["last_reset_year"] != year:
                next_value = 1
            else:
                next_value = row["next_value"]
            connection.execute(
                """
                UPDATE numbering_sequences
                SET next_value = ?, last_reset_year = ?, prefix = ?, padding = ?, updated_at = ?
                WHERE document_type = ? AND scope = ? AND scope_id = ?
                """,
                (next_value + 1, year, prefix, padding, now, document_type, scope, scope_id),
            )

        yy = f"{year % 100:02d}"
        return f"{prefix}_{yy}/{next_value:0{padding}d}"

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
