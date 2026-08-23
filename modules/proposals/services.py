# ==========================================================
# FC Hub - Proposals Services
# ----------------------------------------------------------
# Purpose:
# Proposal generation, client data integration, and export.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json

from core.app_paths import get_project_root
import sqlite3


@dataclass
class ClientData:
    """Client information for proposal"""

    customer_id: str = ""
    company_name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    contact_person: str = ""
    contact_email: str = ""


@dataclass
class ProposalData:
    """Proposal template data"""

    proposal_id: str = ""
    proposal_date: str = ""
    client: ClientData = None
    title: str = "Quote"
    description: str = ""
    line_items: list = None
    total_amount: float = 0.0
    notes: str = ""
    terms: str = ""
    gallery_images: list = None
    accounting_data: dict = None

    # -- Proposal document form fields (FacilitiesCo_Proposal_Template_A4) --
    attention: str = ""
    site: str = ""
    site_area: str = ""
    structure_colour: str = ""
    netting_colour: str = ""
    netting_size: str = ""
    dimensions: str = ""
    timeline_durations: list = None  # 6 strings, one per template phase
    site_photos: list = None  # up to 8 image file paths
    net_double_qty: str = ""
    net_triple_qty: str = ""
    painting_light: str = ""
    painting_medium: str = ""
    painting_full: str = ""
    client_logo_path: str = ""

    def __post_init__(self):
        if self.client is None:
            self.client = ClientData()
        if self.line_items is None:
            self.line_items = []
        if self.gallery_images is None:
            self.gallery_images = []
        if self.accounting_data is None:
            self.accounting_data = {}
        if self.timeline_durations is None:
            self.timeline_durations = [""] * 6
        if self.site_photos is None:
            self.site_photos = []


class ProposalService:
    """Service for managing proposals — backed by the proposals DB table."""

    def __init__(self):
        self._db = get_project_root() / "database" / "fc_hub.db"

    def _conn(self):
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        return conn

    def _now(self):
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # --------------------------------------------------
    # Numbering
    # --------------------------------------------------

    def _next_number(self, conn):
        row = conn.execute("SELECT COUNT(*) FROM proposals").fetchone()
        return row[0] + 1

    # --------------------------------------------------
    # CRUD
    # --------------------------------------------------

    def create_proposal(self, proposal_type="Proposal"):
        now = self._now()
        with self._conn() as conn:
            n = self._next_number(conn)
            proposal_id = f"PROP-{n:04d}"
            proposal = ProposalData(
                proposal_id=proposal_id,
                proposal_date=now[:10],
                title=proposal_type,
            )
            conn.execute(
                "INSERT INTO proposals (id, proposal_date, customer_id, title, data_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (proposal_id, proposal.proposal_date,
                 proposal.client.customer_id or None,
                 proposal_type, self._serialize(proposal), now, now),
            )
        return proposal

    def save_proposal(self, proposal):
        """Persist current state of a ProposalData object."""
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                "UPDATE proposals SET customer_id=?, title=?, data_json=?, updated_at=? WHERE id=?",
                (proposal.client.customer_id or None,
                 proposal.title,
                 self._serialize(proposal),
                 now, proposal.proposal_id),
            )

    def get_proposal(self, proposal_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        return self._deserialize(row) if row else None

    def list_proposals(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM proposals ORDER BY proposal_date DESC, id DESC"
            ).fetchall()
        return [self._deserialize(r) for r in rows]

    def delete_proposal(self, proposal_id):
        with self._conn() as conn:
            conn.execute("DELETE FROM proposals WHERE id=?", (proposal_id,))

    # --------------------------------------------------
    # Serialization helpers
    # --------------------------------------------------

    def _serialize(self, proposal):
        d = asdict(proposal)
        return json.dumps(d, ensure_ascii=False)

    def _deserialize(self, row):
        d = json.loads(row["data_json"])
        client_d = d.pop("client", {})
        client = ClientData(**{k: v for k, v in client_d.items() if k in ClientData.__dataclass_fields__})
        proposal = ProposalData(
            proposal_id=row["id"],
            proposal_date=row["proposal_date"],
            title=row["title"],
            client=client,
            **{k: v for k, v in d.items()
               if k not in ("proposal_id", "proposal_date", "title", "client")
               and k in ProposalData.__dataclass_fields__},
        )
        return proposal

    # --------------------------------------------------
    # Legacy helpers (kept for callers that use them)
    # --------------------------------------------------

    def add_line_item(self, proposal_id, description, quantity, unit_price):
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return
        proposal.line_items.append({
            "description": description,
            "quantity": quantity,
            "unit_price": unit_price,
            "total": quantity * unit_price,
        })
        proposal.total_amount = sum(i["total"] for i in proposal.line_items)
        self.save_proposal(proposal)

    def add_gallery_image(self, proposal_id, image_path, caption=""):
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return
        proposal.gallery_images.append({
            "path": str(image_path),
            "caption": caption,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.save_proposal(proposal)

    def import_accounting_data(self, proposal_id, accounting_data):
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return
        proposal.accounting_data = accounting_data
        self.save_proposal(proposal)


class AccountingImportService:
    """Service for importing accounting data from various sources"""

    def __init__(self):
        pass

    # --------------------------------------------------

    def import_from_pdf(self, pdf_path):
        """Extract accounting data from PDF (placeholder for now)"""

        # Placeholder: will be enhanced to parse PDF bank statements
        return {
            "source": "PDF",
            "file": str(pdf_path),
            "status": "ready_for_import",
            "data": {
                "transactions": [],
                "totals": {
                    "income": 0.0,
                    "expenses": 0.0,
                    "net": 0.0,
                },
            },
        }

    # --------------------------------------------------

    def import_from_excel(self, excel_path):
        """Extract accounting data from Excel spreadsheet (placeholder)"""

        # Placeholder: will be enhanced to parse Excel financial data
        return {
            "source": "Excel",
            "file": str(excel_path),
            "status": "ready_for_import",
            "data": {
                "categories": [],
                "totals": {
                    "revenue": 0.0,
                    "costs": 0.0,
                    "profit": 0.0,
                },
            },
        }

    # --------------------------------------------------

    def import_from_bank_statement(self, statement_path):
        """Extract transactions from bank statement (placeholder)"""

        return {
            "source": "Bank Statement",
            "file": str(statement_path),
            "status": "ready_for_import",
            "data": {
                "account": "",
                "transactions": [],
                "opening_balance": 0.0,
                "closing_balance": 0.0,
            },
        }
