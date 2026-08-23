"""Regression tests for the Contact Review Queue's filtering logic.

2026-08-07: Minette reported the "Hide archived/rejected" checkbox not
hiding rejected/invalid emails. Root cause: the checkbox only took
effect when the status dropdown was on "All"
(`hide_archived and status == "All"`), so switching the dropdown to
any other status silently disabled it. Also, invalid-classified
addresses weren't excluded by classification directly - only by
review_status, which is a weaker guarantee.
"""

from modules.communications.services import (
    AddressClassification,
    ContactCandidate,
    REVIEW_IGNORED,
    REVIEW_NEEDS_ATTENTION,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    filter_review_queue,
)


def make_candidate(email, review_status=REVIEW_PENDING, classification=AddressClassification.NEW, display_name=""):
    return ContactCandidate(
        normalized_email=email, display_name=display_name,
        review_status=review_status, classification=classification,
    )


def test_hide_archived_excludes_rejected_and_ignored_with_status_all():
    candidates = [
        make_candidate("a@x.com", review_status=REVIEW_PENDING),
        make_candidate("b@x.com", review_status=REVIEW_REJECTED),
        make_candidate("c@x.com", review_status=REVIEW_IGNORED),
    ]

    visible = filter_review_queue(candidates, "All", hide_archived=True)

    assert [c.normalized_email for c in visible] == ["a@x.com"]


def test_hide_archived_still_applies_when_status_is_not_all():
    """The actual bug: previously picking any status other than "All"
    silently disabled the hide-checkbox entirely."""
    candidates = [
        make_candidate("a@x.com", review_status=REVIEW_PENDING),
        make_candidate("b@x.com", review_status=REVIEW_REJECTED),
        make_candidate("c@x.com", review_status=REVIEW_NEEDS_ATTENTION),
    ]

    visible = filter_review_queue(candidates, REVIEW_NEEDS_ATTENTION, hide_archived=True)

    assert [c.normalized_email for c in visible] == ["c@x.com"]


def test_selecting_rejected_status_explicitly_still_shows_rejected():
    """Picking "Rejected" from the dropdown itself must still work even
    with the hide-checkbox on - she's explicitly asking to see them."""
    candidates = [
        make_candidate("a@x.com", review_status=REVIEW_PENDING),
        make_candidate("b@x.com", review_status=REVIEW_REJECTED),
    ]

    visible = filter_review_queue(candidates, REVIEW_REJECTED, hide_archived=True)

    assert [c.normalized_email for c in visible] == ["b@x.com"]


def test_hide_archived_excludes_invalid_classification_regardless_of_status():
    candidates = [
        make_candidate("a@x.com", review_status=REVIEW_PENDING, classification=AddressClassification.NEW),
        make_candidate(
            "invalid@x.com", review_status=REVIEW_NEEDS_ATTENTION, classification=AddressClassification.INVALID,
        ),
    ]

    visible = filter_review_queue(candidates, "All", hide_archived=True)

    assert [c.normalized_email for c in visible] == ["a@x.com"]


def test_hide_archived_off_shows_everything():
    candidates = [
        make_candidate("a@x.com", review_status=REVIEW_PENDING),
        make_candidate("b@x.com", review_status=REVIEW_REJECTED),
        make_candidate("c@x.com", review_status=REVIEW_IGNORED),
    ]

    visible = filter_review_queue(candidates, "All", hide_archived=False)

    assert len(visible) == 3


def test_search_matches_email_or_display_name():
    candidates = [
        make_candidate("phillimon@cavaleros.co.za", display_name="Phillimon"),
        make_candidate("other@example.com", display_name="Someone Else"),
    ]

    visible = filter_review_queue(candidates, "All", hide_archived=False, search="cavaleros")

    assert [c.normalized_email for c in visible] == ["phillimon@cavaleros.co.za"]
