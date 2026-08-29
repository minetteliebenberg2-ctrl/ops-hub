# ==========================================================
# FC Hub - Dashboard Data Aggregation
# ----------------------------------------------------------
# Purpose:
# Gather KPI data and activities from core services.
# Supports async loading with callbacks.
#
# Author: Claude
# ==========================================================

import threading
from datetime import date, datetime

from core.crm_service import CRMService
from core.job_card_service import JobCardService
from core.payment_service import PaymentService
from core.quote import format_quote_number
from core.quote_service import QuoteService
from core.site_visit import SCHEDULED
from core.site_visit_service import SiteVisitService

# A quote's default validity is 7 days (QuoteService.DEFAULT_VALIDITY_DAYS) -
# start flagging it this many days before expiry so there's time to
# actually follow up, not just a same-day surprise.
STALE_QUOTE_WARNING_DAYS = 3

# A warranty runs 3 years, so a short warning window would be a
# same-day surprise the same way STALE_QUOTE_WARNING_DAYS avoids for
# quotes - a month's notice is more realistic to actually act on.
WARRANTY_WARNING_DAYS = 30


class DashboardData:
    """Aggregate data from core services for dashboard display."""

    def __init__(self, crm_service=None, quote_service=None, payment_service=None, site_visit_service=None, job_card_service=None):
        self.crm_service = crm_service or CRMService()
        self.quote_service = quote_service or QuoteService()
        self.payment_service = payment_service or PaymentService()
        self.site_visit_service = site_visit_service or SiteVisitService()
        self.job_card_service = job_card_service or JobCardService()

    # ==================================================
    # KPI Methods
    # ==================================================

    def get_outstanding_invoices_count(self):
        """Count of Tax Invoices with a positive balance still owed,
        computed from real payment allocations (PaymentService)."""
        try:
            invoices = self.payment_service.list_invoices_with_status()
            return len([entry for entry in invoices if entry["balance_minor"] > 0])
        except Exception as e:
            print(f"Error getting outstanding invoices: {e}")
            return None

    # --------------------------------------------------

    def get_active_quotes_count(self):
        """Get count of active (issued) quotes."""
        try:
            quotes = self.quote_service.list_quotes()
            if not quotes:
                return 0
            active = [q for q in quotes if q.status in ["Issued", "Draft"]]
            return len(active)
        except Exception as e:
            print(f"Error getting quotes: {e}")
            return 0

    # --------------------------------------------------

    def get_upcoming_site_visits_count(self):
        """Real count of Scheduled site visits from today onward
        (core.site_visit_service - given real persistence 2026-08-06,
        unlike modules.site_visit's still-deferred measurements/
        checklist/photos)."""

        try:
            today = date.today().isoformat()
            return len([
                visit for visit in self.site_visit_service.list_visits()
                if visit.status == SCHEDULED and not visit.archived_at and visit.visit_date >= today
            ])
        except Exception as e:
            print(f"Error getting upcoming site visits: {e}")
            return None

    # --------------------------------------------------

    def get_total_contacts_count(self):
        """Get total contact count."""
        try:
            contacts = self.crm_service.list_all_contacts()
            return len(contacts) if contacts else 0
        except Exception as e:
            print(f"Error getting contacts: {e}")
            return 0

    # ==================================================
    # Activity Feed Methods
    # ==================================================

    def get_recent_activities(self, limit=8):
        """
        Get recent activities across modules.

        Args:
            limit: Max activities to return

        Returns:
            List of dicts {icon, description, entity, timestamp}
        """
        activities = []

        # Get recent quotes
        try:
            quotes = self.quote_service.list_quotes()
            if quotes:
                sorted_quotes = sorted(
                    quotes,
                    key=lambda q: q.created_at or datetime.min,
                    reverse=True,
                )
                for quote in sorted_quotes[:3]:
                    customer = self.crm_service.get_customer(quote.customer_id)
                    customer_name = customer.name if customer else "Unknown"
                    quote_num = quote.quote_number or quote.id[:8]

                    activities.append(
                        {
                            "icon": "📄",
                            "description": f"Quote {quote.status}",
                            "entity": f"{customer_name} — Quote #{quote_num}",
                            "timestamp": quote.created_at or quote.updated_at,
                        }
                    )
        except Exception as e:
            print(f"Error getting quotes: {e}")

        # Get recent contacts
        try:
            contacts = self.crm_service.list_all_contacts()
            if contacts:
                sorted_contacts = sorted(
                    contacts,
                    key=lambda c: c.created_at or datetime.min,
                    reverse=True,
                )
                for contact in sorted_contacts[:3]:
                    customer = self.crm_service.get_customer(contact.customer_id)
                    customer_name = customer.name if customer else "Unknown"

                    activities.append(
                        {
                            "icon": "👥",
                            "description": "New contact",
                            "entity": f"{customer_name} — {contact.name}",
                            "timestamp": contact.created_at,
                        }
                    )
        except Exception as e:
            print(f"Error getting contacts: {e}")

        # Get recent job cards
        try:
            customers_by_id = {c.id: c for c in self.crm_service.list_customers()}
            job_cards = self.job_card_service.job_cards.list_recent(3)
            for jc in job_cards:
                customer = customers_by_id.get(jc.customer_id)
                customer_name = customer.name if customer else "Unknown"
                activities.append(
                    {
                        "icon": "📋",
                        "description": f"Job card {jc.status}",
                        "entity": f"{customer_name} — {jc.job_card_number or jc.id[:8]}",
                        "timestamp": jc.created_at,
                    }
                )
        except Exception as e:
            print(f"Error getting job cards for activity: {e}")

        # Sort all by timestamp (newest first)
        activities.sort(key=lambda a: a["timestamp"] or datetime.min, reverse=True)

        return activities[:limit]

    # ==================================================
    # Right Sidebar Data
    # ==================================================

    def get_upcoming_site_visits(self, limit=5):
        """
        Real Scheduled site visits from today onward, soonest first
        (core.site_visit_service - given real persistence 2026-08-06).

        Returns:
            List of dicts {site_name, customer, date, time}
        """
        try:
            today = date.today().isoformat()
            customers_by_id = {c.id: c for c in self.crm_service.list_customers()}
            sites_by_id = {s.id: s for s in self.crm_service.sites.list_all()}

            upcoming = [
                visit for visit in self.site_visit_service.list_visits()
                if visit.status == SCHEDULED and not visit.archived_at and visit.visit_date >= today
            ]
            upcoming.sort(key=lambda visit: (visit.visit_date, visit.visit_time))

            results = []
            for visit in upcoming[:limit]:
                customer = customers_by_id.get(visit.customer_id)
                site = sites_by_id.get(visit.site_id) if visit.site_id else None
                results.append({
                    "site_name": site.name if site else "(no site)",
                    "customer": customer.name if customer else "Unknown",
                    "date": visit.visit_date,
                    "time": visit.visit_time,
                })
            return results
        except Exception as e:
            print(f"Error getting upcoming site visits: {e}")
            return []

    # --------------------------------------------------

    def get_overdue_invoices(self, limit=5):
        """
        Real Tax Invoices past their due date with a positive balance
        still owed, worst-overdue first.

        Returns:
            List of dicts {invoice_number, customer, amount, days_overdue}
        """
        try:
            customers_by_id = {c.id: c for c in self.crm_service.list_customers()}
            overdue = []
            for entry in self.payment_service.list_invoices_with_status():
                if entry["days_overdue"] <= 0:
                    continue
                invoice = entry["document"]
                customer = customers_by_id.get(invoice.customer_id)
                overdue.append(
                    {
                        "invoice_number": invoice.document_number,
                        "customer": customer.name if customer else "Unknown",
                        "amount": f"R {entry['balance_minor'] / 100:,.2f}",
                        "days_overdue": entry["days_overdue"],
                    }
                )
            overdue.sort(key=lambda row: row["days_overdue"], reverse=True)
            return overdue[:limit]
        except Exception as e:
            print(f"Error getting overdue invoices: {e}")
            return []

    # --------------------------------------------------

    def get_stale_quotes(self, limit=5):
        """Issued quotes that are expiring soon or already past their
        expiry date, with no decision recorded yet (still "Issued", not
        Accepted/Rejected) - the "forgotten follow-up" the audit
        flagged. Deliberately reuses the existing status/expiry_date
        fields rather than a new reminder/task system - simplest thing
        that actually surfaces the risk.

        Returns:
            List of dicts {quote_number, customer, status_label, days}
            where days is negative if already expired, worst first.
        """
        try:
            customers_by_id = {c.id: c for c in self.crm_service.list_customers()}
            today = date.today()
            stale = []
            for quote in self.quote_service.list_quotes():
                if quote.status != "Issued" or quote.archived_at or not quote.expiry_date:
                    continue
                try:
                    expiry = datetime.strptime(quote.expiry_date, "%Y-%m-%d").date()
                except ValueError:
                    continue
                days = (expiry - today).days
                if days > STALE_QUOTE_WARNING_DAYS:
                    continue
                customer = customers_by_id.get(quote.customer_id)
                status_label = f"Expired {-days}d ago" if days < 0 else (
                    "Expires today" if days == 0 else f"Expires in {days}d"
                )
                stale.append(
                    {
                        "quote_number": format_quote_number(quote),
                        "customer": customer.name if customer else "Unknown",
                        "status_label": status_label,
                        "days": days,
                    }
                )
            stale.sort(key=lambda row: row["days"])
            return stale[:limit]
        except Exception as e:
            print(f"Error getting stale quotes: {e}")
            return []

    # ==================================================
    # Async Loading
    # ==================================================

    def get_documents_expiring_count(self):
        """Compliance documents already expired or lapsing within the warning
        window. This is the number that matters: a Tax Compliance PIN or COIDA
        letter that has quietly expired is only discovered when a client asks
        for it mid-tender."""

        try:
            from modules.documents.services import DocumentsRepository

            return len(DocumentsRepository().expiring_documents())
        except Exception:
            # Documents module or its table not available (pre-v0017 database) -
            # show "-" rather than a fabricated zero.
            return None

    # --------------------------------------------------

    def get_warranties_expiring_count(self):
        """Sites whose 3-year warranty (from warranty_installed_date)
        has already lapsed or lapses within the warning window - same
        "don't discover it when a client asks" reasoning as
        documents expiring."""

        try:
            count = 0
            for site in self.crm_service.sites.list_all():
                if site.archived_at:
                    continue
                days = site.warranty_days_remaining
                if days is not None and days <= WARRANTY_WARNING_DAYS:
                    count += 1
            return count
        except Exception as e:
            print(f"Error getting warranties expiring: {e}")
            return None

    def load_kpis_async(self, callback):
        """
        Load KPI data asynchronously.

        Args:
            callback: Function to call with (data_dict) when ready
        """

        def _load():
            data = {
                "outstanding_invoices": self.get_outstanding_invoices_count(),
                "active_quotes": self.get_active_quotes_count(),
                "upcoming_visits": self.get_upcoming_site_visits_count(),
                "total_contacts": self.get_total_contacts_count(),
                "documents_expiring": self.get_documents_expiring_count(),
                "warranties_expiring": self.get_warranties_expiring_count(),
            }
            callback(data)

        thread = threading.Thread(target=_load, daemon=True)
        thread.start()

    # --------------------------------------------------

    def load_activities_async(self, callback):
        """
        Load recent activities asynchronously.

        Args:
            callback: Function to call with (activities_list) when ready
        """

        def _load():
            activities = self.get_recent_activities()
            callback(activities)

        thread = threading.Thread(target=_load, daemon=True)
        thread.start()

    # --------------------------------------------------

    def load_sidebar_widgets_async(self, callback):
        """
        Load right sidebar widgets asynchronously.

        Args:
            callback: Function to call with ({visits, invoices}) when ready
        """

        def _load():
            data = {
                "upcoming_visits": self.get_upcoming_site_visits(),
                "overdue_invoices": self.get_overdue_invoices(),
                "stale_quotes": self.get_stale_quotes(),
            }
            callback(data)

        thread = threading.Thread(target=_load, daemon=True)
        thread.start()
