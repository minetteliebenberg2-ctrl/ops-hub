"""Tests for Site warranty tracking - "3 years from installation" per
Minette's terms and conditions, mapped out 2026-08-07 as the
foundation for Site Visit warranty flagging."""

from datetime import date, timedelta

from core.site import Site, warranty_status_label


def _iso(d):
    return d.strftime("%Y-%m-%d")


def test_no_installed_date_means_no_warranty_tracked():
    site = Site(warranty_installed_date="")
    assert site.warranty_expiry_date is None
    assert site.warranty_days_remaining is None
    assert warranty_status_label(site) == "—"


def test_expiry_is_exactly_three_years_after_installation():
    site = Site(warranty_installed_date="2023-08-07")
    assert site.warranty_expiry_date == date(2026, 8, 7)


def test_leap_day_installation_does_not_crash():
    site = Site(warranty_installed_date="2024-02-29")
    assert site.warranty_expiry_date == date(2027, 2, 28)


def test_malformed_date_is_treated_as_not_tracked_not_a_crash():
    site = Site(warranty_installed_date="not-a-date")
    assert site.warranty_expiry_date is None
    assert warranty_status_label(site) == "—"


def test_warranty_days_remaining_positive_before_expiry():
    installed = date.today() - timedelta(days=10)
    site = Site(warranty_installed_date=_iso(installed))
    expected_days = ((installed.replace(year=installed.year + 3)) - date.today()).days
    assert site.warranty_days_remaining == expected_days
    assert site.warranty_days_remaining > 0
    assert "remaining" in warranty_status_label(site)


def test_warranty_days_remaining_negative_after_expiry():
    installed = date.today() - timedelta(days=365 * 4)
    site = Site(warranty_installed_date=_iso(installed))
    assert site.warranty_days_remaining < 0
    assert "Expired" in warranty_status_label(site)
