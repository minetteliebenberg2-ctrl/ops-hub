"""Regression tests for core/pdf_customer_extractor.py, built from the
real layouts found in Minette's actual Estimate/Invoice/Statement PDFs
(2026-08-05) - see core/pdf_customer_extractor.py for the "why"."""

from core.pdf_customer_extractor import PdfCustomerExtractor, split_address_lines


class StubReader:

    def __init__(self, text):
        self.text = text

    def read(self, _file_path):
        return self.text


def extract(text):
    return PdfCustomerExtractor(document_reader=StubReader(text)).extract("dummy.pdf")


def test_clean_variant_one_layout_is_high_confidence():
    text = (
        " Homestead\n"
        "DATE: 2026/06/04\n"
        "To: QUOTE: BEN_002\n"
        "Ben FOR: Repairs\n"
        "Golden Crest Country Estate VAT # TBA\n"
        "13A Crystal Crescent YOUR REG: TBA\n"
        "Parkrand SUPPLIER # N/A\n"
        "Attention: Ben\n"
        "Email: ben@flashex.co.za\n"
    )
    result = extract(text)

    assert result.name == "Ben"
    assert result.address_lines == ["Golden Crest Country Estate", "13A Crystal Crescent", "Parkrand"]
    assert result.contact_name == "Ben"
    assert result.email == "ben@flashex.co.za"
    assert result.vat_number == ""
    assert result.registration_number == ""
    assert result.confidence == "high"
    assert result.issues == []


def test_real_registration_number_is_captured():
    text = (
        "Homestead\n"
        "DATE: 2025/11/24\n"
        "To: INVOICE: CMH_006\n"
        "CMH Multifranchise Westrand\n"
        "Roodepoort, 1735 VAT # 4430111916\n"
        "Little Falls YOUR REG: 1926/900691/07\n"
        "Attention: Scott Headrick\n"
        "Email: scotth@cmh.co.za\n"
    )
    result = extract(text)

    assert result.registration_number == "1926/900691/07"
    assert result.vat_number == "4430111916"


def test_placeholder_registration_values_are_treated_as_blank():
    for placeholder in ("TBA", "N/A", "TBC"):
        text = (
            "To: QUOTE: X\n"
            "Someone\n"
            f"1 Main Road YOUR REG: {placeholder}\n"
            "Attention: Someone\n"
            "Email: someone@example.com\n"
        )
        assert extract(text).registration_number == ""


def test_clean_variant_two_layout_is_high_confidence():
    text = (
        "ESTIMATE\n"
        " DATE: 2025/09/10\n"
        "Homestead INVOICE: DFU_001\n"
        "Germiston FOR: Top Net\n"
        "Email: minette@facilitiesco.com VAT # TBA\n"
        "Contact: 0833785122 / 010 015 0532 YOUR REG: TBA\n"
        "To: SUPPLIER # N/A\n"
        "Dominique Fuchsloch\n"
        "2 Skypass Road\n"
        "Solheim\n"
        "Germiston\n"
        "Attention: Dominique\n"
        "Email: spiritual@iburst.co.za  |  0827737267\n"
    )
    result = extract(text)

    assert result.name == "Dominique Fuchsloch"
    assert result.address_lines == ["2 Skypass Road", "Solheim", "Germiston"]
    assert result.contact_name == "Dominique"
    assert result.email == "spiritual@iburst.co.za"
    assert result.confidence == "high"


def test_real_vat_number_is_captured():
    text = (
        "Homestead\n"
        "DATE: 2025/11/24\n"
        "To: INVOICE: CMH_006\n"
        "CMH Multifranchise Westrand\n"
        "Roodepoort, 1735 VAT # 4430111916\n"
        "Attention: Scott Headrick\n"
        "Email: scotth@cmh.co.za\n"
    )
    result = extract(text)

    assert result.vat_number == "4430111916"


def test_placeholder_vat_values_are_treated_as_blank():
    for placeholder in ("TBA", "N/A", "TBC"):
        text = (
            "To: QUOTE: X\n"
            "Someone\n"
            f"1 Main Road VAT # {placeholder}\n"
            "Attention: Someone\n"
            "Email: someone@example.com\n"
        )
        assert extract(text).vat_number == ""


def test_duplicated_name_line_is_not_treated_as_an_address_line():
    # The template sometimes prints the name twice: once inline after
    # "To:", again alone on the next line.
    text = (
        "Homestead\n"
        "DATE: 2026/01/06\n"
        "To: Chris QUOTE: CHR_001\n"
        "Chris\n"
        "FOR: Repairs\n"
        "Address: 9 Zenith Avenue, Solheim VAT # TBA\n"
        "Germiston YOUR REG: TBA\n"
        "SUPPLIER # N/A\n"
        "Attention: Chris\n"
        "Email: vreenecf@gmail.com\n"
    )
    result = extract(text)

    assert result.name == "Chris"
    assert result.address_lines == ["9 Zenith Avenue, Solheim", "Germiston"]
    assert result.confidence == "high"


def test_column_merge_artifact_is_flagged_low_confidence_not_guessed():
    # "NettingCnrs..." is "Netting" (end of the FOR: value, wrapped
    # onto the next line) run together with the real address line -
    # a genuine two-column extraction artifact that must be flagged,
    # not silently kept.
    text = (
        "To: INVOICE: CMH_006\n"
        "CMH Multifranchise Westrand\n"
        "FOR: Replacement \n"
        "NettingCnrs Hendrik Potgieter and Cascades Roads VAT # 4430111916\n"
        "Little Falls YOUR REG: 1926/900691/07\n"
        "Attention: Scott Headrick\n"
        "Email: scotth@cmh.co.za\n"
    )
    result = extract(text)

    assert result.confidence == "low"
    assert any("run-together" in issue for issue in result.issues)


def test_percent_sign_merge_artifact_is_flagged_low_confidence():
    # Real bug found on live import: "Netting - 80%Cnrs Hendrik..." -
    # digit/percent-to-uppercase transitions are merge artifacts too,
    # not just lowercase-to-uppercase ones.
    text = (
        "To: QUOTE: CMH_006(2)\n"
        "GWM CHM Little Falls FOR: Replacement \n"
        "Netting - 80%Cnrs Hendrik Potgieter and Cascades Roads VAT # TBA\n"
        "Little Falls YOUR REG: TBA\n"
        "Attention: Scott Headrick\n"
        "Email: scotth@cmh.co.za\n"
    )
    result = extract(text)

    assert result.confidence == "low"
    assert any("run-together" in issue for issue in result.issues)


def test_missing_email_is_flagged_for_review():
    text = (
        "To: SUPPLIER # N/A\n"
        "ATM Solutions\n"
        "7 Delphi Street\n"
        "Sandton\n"
        "Attention: Cynthia\n"
        "Email: \n"
    )
    result = extract(text)

    assert result.email == ""
    assert result.confidence == "low"
    assert any("email" in issue.lower() for issue in result.issues)


def test_unrecognized_layout_without_to_line_is_reported_not_guessed():
    text = (
        "Homestead\n"
        "DATE: 2026/05/13\n"
        "Fireplace Primrose CC QUOTE: Repairs\n"
        "67 Acacia Street FOR: Wind Damage\n"
        "Attention: Antonio SUPPLIER # N/A\n"
        "Email:fireplaceprimrose@gmail.com\n"
    )
    result = extract(text)

    assert result.name == ""
    assert result.confidence == "low"
    assert "To:" in result.issues[0]


def test_split_address_lines_infers_city_and_postal_code_only_when_unambiguous():
    line1, line2, city, postal_code = split_address_lines(
        ["96 Loper Avenue", "Spartan, Kempton Park", "Roodepoort, 1735"]
    )
    assert line1 == "96 Loper Avenue"
    assert line2 == "Spartan, Kempton Park"
    assert city == "Roodepoort"
    assert postal_code == "1735"


def test_split_address_lines_never_guesses_city_when_no_postal_code_present():
    line1, line2, city, postal_code = split_address_lines(["13A Crystal Crescent", "Parkrand"])
    assert line1 == "13A Crystal Crescent"
    assert line2 == "Parkrand"
    assert city == ""
    assert postal_code == ""


def test_split_address_lines_handles_single_line():
    line1, line2, city, postal_code = split_address_lines(["to be confirmed"])
    assert line1 == "to be confirmed"
    assert line2 == ""
    assert city == ""
    assert postal_code == ""


def test_split_address_lines_handles_empty_input():
    assert split_address_lines([]) == ("", "", "", "")


def test_space_grouped_vat_number_is_reassembled_not_truncated():
    # The template prints the VAT number space-grouped. The old pattern
    # stopped at the first space and imported "4" as a real customer's
    # VAT number (found on The Cavaleros Group, 2026-08-05).
    text = (
        "To: QUOTE: CAV_006\n"
        "The Cavaleros Group\n"
        "Block B, Eastgate Office Park VAT # 4 570 123 218\n"
        "Attention: Phillimon\n"
        "Email: phillimon@cavaleros.co.za\n"
    )

    assert extract(text).vat_number == "4570123218"


def test_a_standalone_po_reference_never_lands_in_the_address():
    # "PO # TBC" sits on its own line inside the To: block and was being
    # saved as address line 2 on the real Cavaleros record.
    text = (
        "To: QUOTE: CAV_006\n"
        "The Cavaleros Group\n"
        "PO # TBC\n"
        "Block B, Eastgate Office Park\n"
        "Attention: Phillimon\n"
        "Email: phillimon@cavaleros.co.za\n"
    )
    result = extract(text)

    assert result.name == "The Cavaleros Group"
    assert result.address_lines == ["Block B, Eastgate Office Park"]


def test_body_contact_line_adds_the_extra_people_named_on_the_document():
    text = (
        "To: QUOTE: CAV_006\n"
        "The Cavaleros Group\n"
        "Block B, Eastgate Office Park\n"
        "Attention: Phillimon\n"
        "Email: phillimon@cavaleros.co.za\n"
        "Refit netting to Block B\n"
        "Contact: Thamsi / Phillimon\n"
    )
    result = extract(text)

    # Phillimon owns the document's email and isn't listed twice just
    # because the body names him again.
    assert [(c.name, c.email) for c in result.contacts] == [
        ("Phillimon", "phillimon@cavaleros.co.za"),
        ("Thamsi", ""),
    ]


def test_a_document_with_no_body_contact_line_still_yields_the_header_person():
    text = (
        "To: QUOTE: X\n"
        "Someone Ltd\n"
        "1 Main Road\n"
        "Attention: Dominique\n"
        "Email: dominique@example.com\n"
    )
    result = extract(text)

    assert [(c.name, c.email) for c in result.contacts] == [
        ("Dominique", "dominique@example.com"),
    ]
