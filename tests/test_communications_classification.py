"""Regression tests for email address classification and ignore list."""

import os
import tempfile

import pytest

from core.database import Database
from modules.communications.services import (
    AddressClassification,
    AutomatedAddressClassifier,
    EmailAddressNormalizer,
    EmailAddressValidator,
    IgnoreListService,
)

# --------------------------------------------------------
# EmailAddressNormalizer
# --------------------------------------------------------


def test_normalizer_lowercases_email_and_keeps_display_name():
    result = EmailAddressNormalizer().normalize("Sarah Jones <SARAH@Example.com>")
    assert result["email"] == "sarah@example.com"
    assert result["display_name"] == "Sarah Jones"


def test_normalizer_handles_blank_input():
    result = EmailAddressNormalizer().normalize("")
    assert result["email"] == ""
    assert result["display_name"] == ""


# --------------------------------------------------------
# EmailAddressValidator
# --------------------------------------------------------


def test_validator_flags_blank_email():
    assert EmailAddressValidator().validate("") == AddressClassification.BLANK


def test_validator_flags_invalid_email():
    assert (
        EmailAddressValidator().validate("not-an-email")
        == AddressClassification.INVALID
    )


def test_validator_accepts_valid_email():
    assert (
        EmailAddressValidator().validate("sarah@example.com")
        == AddressClassification.VALID
    )


# --------------------------------------------------------
# AutomatedAddressClassifier
# --------------------------------------------------------


def test_classifier_flags_noreply_addresses():
    classifier = AutomatedAddressClassifier()
    assert classifier.classify("noreply@example.com") == "No-reply sender"


def test_classifier_flags_postmaster():
    classifier = AutomatedAddressClassifier()
    assert classifier.classify("postmaster@example.com") == "Postmaster"


def test_classifier_flags_auto_submitted_header():
    classifier = AutomatedAddressClassifier()
    result = classifier.classify(
        "sarah@example.com",
        headers={"Auto-Submitted": "auto-generated"},
    )
    assert result == "Auto-Submitted header"


def test_classifier_leaves_real_addresses_alone():
    classifier = AutomatedAddressClassifier()
    assert classifier.classify("sarah@example.com") == ""


# --------------------------------------------------------
# IgnoreListService
# --------------------------------------------------------


@pytest.fixture
def ignore_list():
    db_path = tempfile.mktemp(suffix=".db")
    test_db = Database(path=db_path)
    test_db.initialize()
    service = IgnoreListService(test_db)
    yield service
    if os.path.exists(db_path):
        os.remove(db_path)


def test_ignored_email_is_detected(ignore_list):
    ignore_list.add_email("spam@example.com", reason="Known spammer")
    assert ignore_list.is_ignored("spam@example.com") is True


def test_ignored_domain_blocks_all_addresses_on_it(ignore_list):
    ignore_list.add_domain("spamdomain.com", reason="Bulk sender")
    assert ignore_list.is_ignored("anyone@spamdomain.com") is True


def test_unlisted_email_is_not_ignored(ignore_list):
    assert ignore_list.is_ignored("sarah@example.com") is False
