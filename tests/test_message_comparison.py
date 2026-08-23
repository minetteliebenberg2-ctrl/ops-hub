"""Regression tests for MessageComparison, covering the false-positive
duplicate-detection bug reported by Minette: recurring template emails
from the same sender (e.g. monthly FNB banking notifications) with the
same subject and similar size were being flagged as duplicates of each
other purely because sender+recipient+subject+size already met the
threshold, without date ever needing to match."""

from types import SimpleNamespace

import pytest

from core.message_comparison import MessageComparison


def message(sender="alerts@fnb.co.za", recipient="minette@facilitiesco.com",
            subject="Your monthly statement is ready", date="Mon, 1 Jun 2026 09:00:00 +0200",
            message_size=15000):
    return SimpleNamespace(sender=sender, recipient=recipient, subject=subject, date=date, message_size=message_size)


@pytest.fixture
def comparison():
    return MessageComparison()


def test_recurring_emails_on_different_dates_are_not_duplicates(comparison):
    june = message(date="Mon, 1 Jun 2026 09:00:00 +0200")
    july = message(date="Wed, 1 Jul 2026 09:00:00 +0200")

    assert comparison.is_probable_duplicate(june, july) is False


def test_same_sender_subject_size_score_meets_threshold_without_date(comparison):
    # Confirms the actual root cause: these four fields alone hit the
    # threshold, which is exactly why date must be a mandatory gate.
    june = message(date="Mon, 1 Jun 2026 09:00:00 +0200")
    july = message(date="Wed, 1 Jul 2026 09:00:00 +0200")

    assert comparison.compare(june, july) >= comparison.threshold


def test_true_duplicates_on_the_same_date_are_still_caught(comparison):
    first = message()
    second = message()

    assert comparison.is_probable_duplicate(first, second) is True


def test_messages_without_a_parsable_date_are_never_flagged_as_duplicate(comparison):
    first = message(date="")
    second = message(date="")

    assert comparison.is_probable_duplicate(first, second) is False
