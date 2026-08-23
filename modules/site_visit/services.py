# ==========================================================
# FC Hub - Site Visit Services
# ----------------------------------------------------------
# Purpose:
# Job cards, measurement forms, site inspection checklists.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict
import json


@dataclass
class Measurement:
    """Single measurement"""

    description: str
    value: float
    unit: str  # m, mm, cm, etc.
    notes: str = ""
    section: str = ""  # Foundation, Height, Width, etc.


@dataclass
class ChecklistItem:
    """Inspection checklist item"""

    item_id: str
    description: str
    completed: bool = False
    notes: str = ""
    priority: str = "Normal"  # Low, Normal, High, Critical
    section: str = ""


@dataclass
class SiteVisit:
    """Site visit/inspection record"""

    visit_id: str
    job_id: str = ""
    customer_name: str = ""
    site_address: str = ""
    visit_date: str = ""
    visit_time: str = ""
    completed_by: str = ""

    # Measurements
    measurements: List[Measurement] = field(default_factory=list)

    # Inspection
    checklist: List[ChecklistItem] = field(default_factory=list)
    checklist_completed: int = 0

    # Notes
    site_conditions: str = ""
    access_notes: str = ""
    safety_notes: str = ""
    special_requirements: str = ""
    general_notes: str = ""

    # Gallery
    photos: List[str] = field(default_factory=list)

    # Status
    status: str = "Scheduled"  # Scheduled, In Progress, Completed, Review
    sign_off_by: str = ""
    sign_off_date: str = ""

    def to_dict(self):
        return {
            "visit_id": self.visit_id,
            "job_id": self.job_id,
            "customer_name": self.customer_name,
            "site_address": self.site_address,
            "visit_date": self.visit_date,
            "visit_time": self.visit_time,
            "completed_by": self.completed_by,
            "measurements": [{"description": m.description, "value": m.value, "unit": m.unit} for m in self.measurements],
            "checklist": [{"description": c.description, "completed": c.completed} for c in self.checklist],
            "site_conditions": self.site_conditions,
            "access_notes": self.access_notes,
            "safety_notes": self.safety_notes,
            "photos_count": len(self.photos),
            "status": self.status,
        }


class SiteVisitService:
    """Service for managing site visits and inspections"""

    def __init__(self):
        self.visits: Dict[str, SiteVisit] = {}
        self.next_visit_id = 1

    # --------------------------------------------------

    def create_site_visit(self, job_id: str, customer_name: str, site_address: str) -> SiteVisit:
        """Create a new site visit"""
        visit_id = f"VISIT-{self.next_visit_id:04d}"
        self.next_visit_id += 1

        visit = SiteVisit(
            visit_id=visit_id,
            job_id=job_id,
            customer_name=customer_name,
            site_address=site_address,
            visit_date=datetime.now().strftime("%Y-%m-%d"),
            visit_time=datetime.now().strftime("%H:%M"),
        )

        self.visits[visit_id] = visit
        return visit

    # --------------------------------------------------

    def get_visit(self, visit_id: str) -> SiteVisit:
        """Retrieve a site visit"""
        return self.visits.get(visit_id)

    # --------------------------------------------------

    def add_measurement(self, visit_id: str, measurement: Measurement):
        """Add measurement to visit"""
        visit = self.get_visit(visit_id)
        if visit:
            visit.measurements.append(measurement)

    # --------------------------------------------------

    def add_checklist_item(self, visit_id: str, item: ChecklistItem):
        """Add checklist item to visit"""
        visit = self.get_visit(visit_id)
        if visit:
            visit.checklist.append(item)

    # --------------------------------------------------

    def mark_checklist_item_complete(self, visit_id: str, item_id: str):
        """Mark a checklist item as complete"""
        visit = self.get_visit(visit_id)
        if visit:
            for item in visit.checklist:
                if item.item_id == item_id:
                    item.completed = True
            visit.checklist_completed = sum(1 for i in visit.checklist if i.completed)

    # --------------------------------------------------

    def add_photo(self, visit_id: str, photo_path: str):
        """Add photo to visit"""
        visit = self.get_visit(visit_id)
        if visit:
            visit.photos.append(photo_path)

    # --------------------------------------------------

    def complete_visit(self, visit_id: str, sign_off_by: str = ""):
        """Mark visit as completed"""
        visit = self.get_visit(visit_id)
        if visit:
            visit.status = "Completed"
            visit.sign_off_by = sign_off_by
            visit.sign_off_date = datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def get_visits_for_job(self, job_id: str) -> List[SiteVisit]:
        """Get all visits for a job"""
        return [v for v in self.visits.values() if v.job_id == job_id]

    # --------------------------------------------------

    def export_visit(self, visit_id: str, filepath: str):
        """Export visit report to JSON"""
        visit = self.get_visit(visit_id)
        if not visit:
            return False

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(visit.to_dict(), f, indent=2)

        return True

    # --------------------------------------------------

    def get_standard_checklist(self) -> List[ChecklistItem]:
        """Get standard site visit checklist"""
        return [
            ChecklistItem("1", "Site access verified", section="Access"),
            ChecklistItem("2", "Safety zone established", section="Safety"),
            ChecklistItem("3", "Existing structures assessed", section="Assessment"),
            ChecklistItem("4", "Ground conditions checked", section="Assessment"),
            ChecklistItem("5", "Drainage verified", section="Assessment"),
            ChecklistItem("6", "Utilities located", section="Safety"),
            ChecklistItem("7", "Photos taken - Before", section="Documentation"),
            ChecklistItem("8", "Measurements recorded", section="Documentation"),
            ChecklistItem("9", "Quotes prepared", section="Quote"),
            ChecklistItem("10", "Customer confirmed", section="Approval"),
        ]
