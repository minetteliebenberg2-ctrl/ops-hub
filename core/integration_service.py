# ==========================================================
# FC Hub - Integration Service
# ----------------------------------------------------------
# Purpose:
# Cross-module data integration and synchronization.
# Links CRM → Proposals → Accounting → Calendar → Gallery → SiteVisit
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from typing import Optional, List, Dict


class IntegrationService:
    """Cross-module data integration"""

    def __init__(self):
        # Module references (set by each module on startup)
        self.crm_service = None
        self.proposals_service = None
        self.accounting_service = None
        self.calendar_service = None
        self.gallery_service = None
        self.site_visit_service = None

    # --------------------------------------------------
    # CRM → Proposals Integration
    # --------------------------------------------------

    def get_customer_for_proposal(self, customer_id: str) -> Dict:
        """Get customer data from CRM for proposal"""
        if not self.crm_service:
            return {}

        try:
            customer = self.crm_service.get_customer(customer_id)
            if customer:
                return {
                    "id": customer.customer_id,
                    "name": customer.name,
                    "email": customer.email,
                    "phone": customer.phone,
                    "address": getattr(customer, "address", ""),
                    "contact_person": getattr(customer, "contact_person", ""),
                }
        except Exception:
            pass

        return {}

    # --------------------------------------------------
    # Proposals → Accounting Integration
    # --------------------------------------------------

    def add_proposal_to_accounting(self, proposal_id: str, job_id: str, amount: float):
        """Link proposal to accounting as a revenue item"""
        if not self.accounting_service:
            return False

        try:
            from modules.accounting.services import Transaction

            txn = Transaction(
                date="2026-07-29",  # Current date
                description=f"Proposal {proposal_id} for Job {job_id}",
                amount=amount,
                transaction_type="Income",
                category="Service Revenue",
                reference=proposal_id,
            )
            self.accounting_service.add_transaction(txn)
            return True
        except Exception:
            pass

        return False

    # --------------------------------------------------
    # Calendar → Site Visit Integration
    # --------------------------------------------------

    def create_site_visit_from_job(self, job_id: str, job_title: str, customer_name: str, site_address: str):
        """Create site visit from calendar job"""
        if not self.site_visit_service:
            return None

        try:
            visit = self.site_visit_service.create_site_visit(job_id, customer_name, site_address)

            # Add standard checklist
            for item in self.site_visit_service.get_standard_checklist():
                self.site_visit_service.add_checklist_item(visit.visit_id, item)

            return visit
        except Exception:
            pass

        return None

    # --------------------------------------------------
    # Site Visit → Gallery Integration
    # --------------------------------------------------

    def add_site_visit_photos_to_gallery(self, visit_id: str, project_id: str):
        """Organize site visit photos in gallery by phase"""
        if not self.site_visit_service or not self.gallery_service:
            return False

        try:
            visit = self.site_visit_service.get_visit(visit_id)
            if not visit:
                return False

            for photo_path in visit.photos:
                from modules.gallery.services import ImageMetadata

                metadata = ImageMetadata(
                    filename=photo_path.split("\\")[-1],
                    filepath=photo_path,
                    project_id=project_id,
                    phase=visit.status,  # Map visit status to phase
                    description=f"Site visit {visit_id}",
                )
                self.gallery_service.add_image(metadata)

            return True
        except Exception:
            pass

        return False

    # --------------------------------------------------
    # Calendar → Proposals Integration
    # --------------------------------------------------

    def get_job_details_for_proposal(self, job_id: str) -> Dict:
        """Get job details from calendar for proposal creation"""
        if not self.calendar_service:
            return {}

        try:
            job = self.calendar_service.get_job(job_id)
            if job:
                return {
                    "id": job.job_id,
                    "customer": job.customer_name,
                    "title": job.title,
                    "description": job.description,
                    "quoted_amount": job.quoted_amount,
                    "start_date": job.start_date,
                }
        except Exception:
            pass

        return {}

    # --------------------------------------------------
    # Gallery → Calendar Integration
    # --------------------------------------------------

    def link_gallery_to_job(self, project_id: str, job_id: str):
        """Link gallery images to calendar job"""
        if not self.gallery_service or not self.calendar_service:
            return False

        try:
            job = self.calendar_service.get_job(job_id)
            if job:
                # Get gallery summary and attach to job
                summary = self.gallery_service.get_gallery_summary(project_id)
                job.gallery_phases = {
                    "Before": self.gallery_service.get_images_by_project(project_id, "Before"),
                    "During": self.gallery_service.get_images_by_project(project_id, "During"),
                    "After": self.gallery_service.get_images_by_project(project_id, "After"),
                }
                return True
        except Exception:
            pass

        return False

    # --------------------------------------------------
    # Cross-module Data Summary
    # --------------------------------------------------

    def get_job_summary(self, job_id: str) -> Dict:
        """Get complete job summary across all modules"""
        summary = {
            "job_id": job_id,
            "calendar": {},
            "proposals": [],
            "accounting": {},
            "site_visits": [],
            "gallery": {},
        }

        # Calendar data
        if self.calendar_service:
            try:
                job = self.calendar_service.get_job(job_id)
                if job:
                    summary["calendar"] = {
                        "customer": job.customer_name,
                        "title": job.title,
                        "status": job.status,
                        "start_date": job.start_date,
                        "quoted_amount": job.quoted_amount,
                    }
            except Exception:
                pass

        # Accounting data
        if self.accounting_service:
            try:
                transactions = [t for t in self.accounting_service.transactions if job_id in t.reference]
                if transactions:
                    summary["accounting"] = {
                        "revenue": sum(t.amount for t in transactions if t.transaction_type == "Income"),
                        "costs": sum(t.amount for t in transactions if t.transaction_type == "Expense"),
                        "transaction_count": len(transactions),
                    }
            except Exception:
                pass

        # Site visits
        if self.site_visit_service:
            try:
                visits = self.site_visit_service.get_visits_for_job(job_id)
                summary["site_visits"] = [v.visit_date for v in visits]
            except Exception:
                pass

        return summary

    # --------------------------------------------------
    # Module Registration
    # --------------------------------------------------

    def register_crm(self, service):
        """Register CRM service"""
        self.crm_service = service

    def register_proposals(self, service):
        """Register Proposals service"""
        self.proposals_service = service

    def register_accounting(self, service):
        """Register Accounting service"""
        self.accounting_service = service

    def register_calendar(self, service):
        """Register Calendar service"""
        self.calendar_service = service

    def register_gallery(self, service):
        """Register Gallery service"""
        self.gallery_service = service

    def register_site_visit(self, service):
        """Register Site Visit service"""
        self.site_visit_service = service


# Global integration service instance
integration_service = IntegrationService()
