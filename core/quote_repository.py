# ==========================================================
# FC Hub - Quote Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for quotes and quote line items.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime
from uuid import uuid4

from core.database import database
from core.numbering_service import NumberingError, NumberingService
from core.quote import Quote
from core.quote_line_item import QuoteLineItem


class QuoteRepository:

    def __init__(self, db=None, numbering_service=None):

        self.db = db or database
        self.db.initialize()
        self.numbering = numbering_service or NumberingService()

    # --------------------------------------------------

    def save(self, quote):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO quotes (
                    id, quote_number, customer_id, site_id, status,
                    issue_date, expiry_date, currency, payment_terms_snapshot,
                    deposit_percentage, balance_percentage, subtotal_minor,
                    vat_minor, total_minor, po_number, vat_number,
                    registration_number, bill_to_name, notes,
                    revision_of_quote_id, revision_number,
                    created_at, updated_at, created_by, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    site_id = excluded.site_id,
                    expiry_date = excluded.expiry_date,
                    payment_terms_snapshot = excluded.payment_terms_snapshot,
                    deposit_percentage = excluded.deposit_percentage,
                    balance_percentage = excluded.balance_percentage,
                    subtotal_minor = excluded.subtotal_minor,
                    vat_minor = excluded.vat_minor,
                    total_minor = excluded.total_minor,
                    po_number = excluded.po_number,
                    vat_number = excluded.vat_number,
                    registration_number = excluded.registration_number,
                    bill_to_name = excluded.bill_to_name,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    quote.id,
                    quote.quote_number or None,
                    quote.customer_id,
                    quote.site_id or None,
                    quote.status,
                    quote.issue_date,
                    quote.expiry_date,
                    quote.currency,
                    quote.payment_terms_snapshot,
                    quote.deposit_percentage,
                    quote.balance_percentage,
                    quote.subtotal_minor,
                    quote.vat_minor,
                    quote.total_minor,
                    quote.po_number,
                    quote.vat_number,
                    quote.registration_number,
                    quote.bill_to_name,
                    quote.notes,
                    quote.revision_of_quote_id or None,
                    quote.revision_number,
                    quote.created_at,
                    quote.updated_at,
                    quote.created_by,
                    quote.updated_by,
                ),
            )

        return quote

    # --------------------------------------------------

    def get(self, quote_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM quotes WHERE id = ?",
                (quote_id,),
            ).fetchone()

        return self._to_quote(row) if row else None

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM quotes WHERE customer_id = ? ORDER BY created_at DESC",
                (customer_id,),
            ).fetchall()

        return [self._to_quote(row) for row in rows]

    # --------------------------------------------------

    def list_all(self):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM quotes ORDER BY created_at DESC"
            ).fetchall()

        return [self._to_quote(row) for row in rows]

    # --------------------------------------------------

    def issue(self, quote_id, issue_date, expiry_date, actor):
        """Assign the quote's immutable number (scoped to its customer) and
        mark it Issued, inside one transaction. Never renumbers an already
        issued *original* quote - but a revision (revision_number > 0)
        already carries its original's quote_number from create_revision(),
        so issuing one just finalises status/dates without drawing a new
        number, keeping every revision under the same quote number."""

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT customer_id, quote_number, revision_number FROM quotes WHERE id = ?",
                (quote_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Quote not found.")

            is_revision = row["revision_number"] > 0
            if row["quote_number"] and not is_revision:
                raise ValueError("This quote already has a number.")

            if is_revision:
                quote_number = row["quote_number"]
            else:
                customer = connection.execute(
                    "SELECT customer_number FROM customers WHERE id = ?",
                    (row["customer_id"],),
                ).fetchone()
                if customer is None or not customer["customer_number"]:
                    raise NumberingError("The customer does not have a customer number yet.")

                quote_number = self.numbering.allocate_yearly(
                    connection,
                    "quote",
                    scope_id=row["customer_id"],
                    prefix="Q",
                    padding=3,
                )

            now = self._timestamp()
            connection.execute(
                """
                UPDATE quotes
                SET quote_number = ?, status = 'Issued', issue_date = ?,
                    expiry_date = ?, updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (quote_number, issue_date, expiry_date, now, actor, quote_id),
            )

        return quote_number

    # --------------------------------------------------

    def create_revision(self, quote_id, actor):
        """Create a new, editable Draft quote that reuses the original's
        quote_number (same document, next version) instead of drawing a
        fresh number. Copies the current line items as the revision's
        starting point - editing them here never touches the original
        row, which stays exactly as issued."""

        with self.db.connect() as connection:
            original = connection.execute(
                "SELECT * FROM quotes WHERE id = ?", (quote_id,),
            ).fetchone()
            if original is None:
                raise ValueError("Quote not found.")
            if not original["quote_number"]:
                raise ValueError("Only an issued quote can be revised.")

            next_revision = connection.execute(
                """
                SELECT COALESCE(MAX(revision_number), 0) + 1
                FROM quotes
                WHERE customer_id = ? AND quote_number = ?
                """,
                (original["customer_id"], original["quote_number"]),
            ).fetchone()[0]

            now = self._timestamp()
            new_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO quotes (
                    id, quote_number, customer_id, site_id, status,
                    issue_date, expiry_date, currency, payment_terms_snapshot,
                    deposit_percentage, balance_percentage, subtotal_minor,
                    vat_minor, total_minor, po_number, vat_number,
                    registration_number, bill_to_name, notes,
                    revision_of_quote_id, revision_number,
                    created_at, updated_at, created_by, updated_by
                )
                VALUES (?, ?, ?, ?, 'Draft', '', '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id, original["quote_number"], original["customer_id"], original["site_id"],
                    original["currency"], original["payment_terms_snapshot"],
                    original["deposit_percentage"], original["balance_percentage"],
                    original["subtotal_minor"], original["vat_minor"], original["total_minor"],
                    original["po_number"], original["vat_number"], original["registration_number"],
                    original["bill_to_name"], original["notes"],
                    original["id"], next_revision,
                    now, now, actor, actor,
                ),
            )

            for item in connection.execute(
                "SELECT * FROM quote_line_items WHERE quote_id = ?", (quote_id,),
            ).fetchall():
                connection.execute(
                    """
                    INSERT INTO quote_line_items (
                        id, quote_id, sort_order, structure_type, car_bays, shape,
                        width_m, projection_m, height_m, description, quantity,
                        unit_price_minor, amount_minor, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()), new_id, item["sort_order"], item["structure_type"],
                        item["car_bays"], item["shape"], item["width_m"], item["projection_m"],
                        item["height_m"], item["description"], item["quantity"],
                        item["unit_price_minor"], item["amount_minor"], now, now,
                    ),
                )

        return self.get(new_id)

    # --------------------------------------------------

    def set_status(self, quote_id, status, actor):

        now = self._timestamp()
        with self.db.connect() as connection:
            if status == "Accepted":
                connection.execute(
                    "UPDATE quotes SET status = ?, accepted_date = ?, updated_at = ?, updated_by = ? WHERE id = ?",
                    (status, now[:10], now, actor, quote_id),
                )
            else:
                connection.execute(
                    "UPDATE quotes SET status = ?, updated_at = ?, updated_by = ? WHERE id = ?",
                    (status, now, actor, quote_id),
                )

    # --------------------------------------------------

    def archive(self, quote_id, actor, reason):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE quotes
                SET archived_at = ?, archived_by = ?, archive_reason = ?,
                    updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, reason, self._timestamp(), actor, quote_id),
            )

    # --------------------------------------------------

    def delete(self, quote_id):
        """Hard delete of the quotes row, cascading to its line items
        and any quote_documents (see core/quote_service.py: called by
        delete_draft_quote for never-issued Drafts, and by
        delete_quote for any status - the payment-allocation guard
        lives in the service layer, not here)."""

        with self.db.connect() as connection:
            connection.execute("DELETE FROM quotes WHERE id = ?", (quote_id,))

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def _to_quote(self, row):

        return Quote(
            id=row["id"],
            quote_number=row["quote_number"] or "",
            customer_id=row["customer_id"],
            site_id=row["site_id"] or "",
            status=row["status"],
            issue_date=row["issue_date"],
            expiry_date=row["expiry_date"],
            currency=row["currency"],
            payment_terms_snapshot=row["payment_terms_snapshot"],
            deposit_percentage=row["deposit_percentage"],
            balance_percentage=row["balance_percentage"],
            subtotal_minor=row["subtotal_minor"],
            vat_minor=row["vat_minor"],
            total_minor=row["total_minor"],
            po_number=row["po_number"] or "",
            vat_number=row["vat_number"] or "",
            registration_number=row["registration_number"] or "",
            bill_to_name=row["bill_to_name"] or "",
            notes=row["notes"],
            revision_of_quote_id=row["revision_of_quote_id"] or "",
            revision_number=row["revision_number"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            updated_by=row["updated_by"],
            archived_at=row["archived_at"] or "",
            archived_by=row["archived_by"] or "",
            archive_reason=row["archive_reason"],
            accepted_date=row["accepted_date"] or "" if "accepted_date" in row.keys() else "",
        )


class QuoteLineItemRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def list_for_quote(self, quote_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM quote_line_items WHERE quote_id = ? ORDER BY sort_order",
                (quote_id,),
            ).fetchall()

        return [self._to_line_item(row) for row in rows]

    # --------------------------------------------------

    def save(self, line_item):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO quote_line_items (
                    id, quote_id, sort_order, structure_type, car_bays,
                    shape, width_m, projection_m, height_m, colour, description,
                    quantity, unit_price_minor, amount_minor, created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    sort_order = excluded.sort_order,
                    structure_type = excluded.structure_type,
                    car_bays = excluded.car_bays,
                    shape = excluded.shape,
                    width_m = excluded.width_m,
                    projection_m = excluded.projection_m,
                    height_m = excluded.height_m,
                    colour = excluded.colour,
                    description = excluded.description,
                    quantity = excluded.quantity,
                    unit_price_minor = excluded.unit_price_minor,
                    amount_minor = excluded.amount_minor,
                    updated_at = excluded.updated_at
                """,
                (
                    line_item.id,
                    line_item.quote_id,
                    line_item.sort_order,
                    line_item.structure_type,
                    line_item.car_bays,
                    line_item.shape,
                    line_item.width_m,
                    line_item.projection_m,
                    line_item.height_m,
                    line_item.colour,
                    line_item.description,
                    line_item.quantity,
                    line_item.unit_price_minor,
                    line_item.amount_minor,
                    line_item.created_at,
                    line_item.updated_at,
                ),
            )

        return line_item

    # --------------------------------------------------

    def delete(self, line_item_id):

        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM quote_line_items WHERE id = ?",
                (line_item_id,),
            )

    # --------------------------------------------------

    def _to_line_item(self, row):

        return QuoteLineItem(
            id=row["id"],
            quote_id=row["quote_id"],
            sort_order=row["sort_order"],
            structure_type=row["structure_type"],
            car_bays=row["car_bays"],
            shape=row["shape"],
            width_m=row["width_m"],
            projection_m=row["projection_m"],
            height_m=row["height_m"],
            colour=row["colour"] or "",
            description=row["description"],
            quantity=row["quantity"],
            unit_price_minor=row["unit_price_minor"],
            amount_minor=row["amount_minor"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
