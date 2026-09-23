from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

from core.database import database

COST_BUCKETS = ("labour", "materials", "transport", "other")


@dataclass
class JobCostItem:
    id: str = ""
    name: str = ""
    cost_bucket: str = "labour"
    unit_price: float = 0.0
    gp_percent: float = 45.0
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""


class JobCostItemRepository:

    def __init__(self, db=None):
        self.db = db or database

    def list_all(self, include_inactive=False):
        with self.db.connect() as conn:
            if include_inactive:
                rows = conn.execute("SELECT * FROM job_cost_items ORDER BY name").fetchall()
            else:
                rows = conn.execute("SELECT * FROM job_cost_items WHERE is_active=1 ORDER BY name").fetchall()
            return [self._to_item(r) for r in rows]

    def get(self, item_id):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM job_cost_items WHERE id=?", (item_id,)).fetchone()
            return self._to_item(row) if row else None

    def save(self, item):
        now = datetime.now(timezone.utc).isoformat()
        item.updated_at = now
        if not item.id:
            item.id = str(uuid.uuid4())
            item.created_at = now
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO job_cost_items (id, name, cost_bucket, unit_price, gp_percent, is_active, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=?, cost_bucket=?, unit_price=?, gp_percent=?, is_active=?, updated_at=?",
                (item.id, item.name, item.cost_bucket, item.unit_price, item.gp_percent, int(item.is_active), item.created_at, item.updated_at,
                 item.name, item.cost_bucket, item.unit_price, item.gp_percent, int(item.is_active), item.updated_at),
            )
        return item

    def delete(self, item_id):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM job_cost_items WHERE id=?", (item_id,))

    def cost_map(self):
        items = self.list_all()
        return {item.name: (item.cost_bucket, item.gp_percent / 100) for item in items}

    @staticmethod
    def _to_item(row):
        return JobCostItem(
            id=row["id"],
            name=row["name"],
            cost_bucket=row["cost_bucket"],
            unit_price=row["unit_price"] if "unit_price" in row.keys() else 0.0,
            gp_percent=row["gp_percent"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
