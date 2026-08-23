"""Regression tests for the signature field extractor."""

from core.signature_field_extractor import SignatureFieldExtractor


def test_extracts_all_fields_from_a_full_signature():
    text = """
    Kind regards,

    Sarah Jones
    Sales Manager
    Bright Facilities (Pty) Ltd
    011 234 5678
    www.brightfacilities.co.za
    VAT Reg No: 4123456789
    """

    result = SignatureFieldExtractor().extract(text)

    assert result["phone"] == "011 234 5678"
    assert result["website"] == "www.brightfacilities.co.za"
    assert result["vat_number"] == "4123456789"
    assert result["company_name"] == "Bright Facilities (Pty) Ltd"


def test_extracts_mobile_number_and_cc_company():
    text = """
    Thanks,
    Mike
    Acme Cleaning CC
    +27 82 555 1234
    acmecleaning.co.za
    """

    result = SignatureFieldExtractor().extract(text)

    assert result["phone"] == "+27 82 555 1234"
    assert result["website"] == "acmecleaning.co.za"
    assert result["company_name"] == "Acme Cleaning CC"


def test_plain_message_with_no_signature_returns_blanks():
    text = "Hey, can we reschedule tomorrow? Thanks, John"

    result = SignatureFieldExtractor().extract(text)

    assert result["phone"] == ""
    assert result["website"] == ""
    assert result["vat_number"] == ""
    assert result["company_name"] == ""


def test_website_does_not_capture_email_domain():
    text = "Contact us: sarah@example.com or call 0821234567"

    result = SignatureFieldExtractor().extract(text)

    assert result["phone"] == "0821234567"
    assert result["website"] == ""
