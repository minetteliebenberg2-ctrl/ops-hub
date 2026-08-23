# ==========================================================
# FC Hub - Site
# ----------------------------------------------------------
# Purpose:
# Site model for CRM. A site is a customer-owned operational
# location referencing a structured address.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass
from datetime import date, datetime

WARRANTY_YEARS = 3


@dataclass
class Site:

    id: str = ""
    customer_id: str = ""
    address_id: str = ""
    name: str = ""
    site_type: str = ""
    notes: str = ""
    warranty_installed_date: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    updated_by: str = ""
    archived_at: str = ""
    archived_by: str = ""
    archive_reason: str = ""
    deleted_at: str = ""
    deleted_by: str = ""

    @property
    def warranty_expiry_date(self):
        """3 years from installation, per her terms and conditions -
        computed, not stored, so it can never drift from
        warranty_installed_date."""

        if not self.warranty_installed_date:
            return None
        try:
            installed = datetime.strptime(self.warranty_installed_date, "%Y-%m-%d").date()
        except ValueError:
            return None
        try:
            return installed.replace(year=installed.year + WARRANTY_YEARS)
        except ValueError:
            # 29 Feb installed, +3 years lands on a non-leap year.
            return installed.replace(month=2, day=28, year=installed.year + WARRANTY_YEARS)

    @property
    def warranty_days_remaining(self):
        """Negative once expired. None when there's no installation
        date on file at all."""

        expiry = self.warranty_expiry_date
        if expiry is None:
            return None
        return (expiry - date.today()).days


def warranty_status_label(site):
    """Short display string for the Sites table - matches the
    Overdue Invoices / Stale Quotes panels' "Nd" style rather than a
    full date, so it reads at a glance."""

    days = site.warranty_days_remaining
    if days is None:
        return "—"
    if days < 0:
        return f"Expired {-days}d ago"
    return f"{days}d remaining"
