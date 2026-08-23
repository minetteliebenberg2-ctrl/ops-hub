"""Regression tests for signature-field extraction wired into the
automatic email address collection pipeline."""

import mailbox

from core.mailbox import Mailbox
from modules.communications.services import AutomaticEmailAddressCollector


SIGNATURE_BODY = (
    "Hi there,\n\n"
    "Thanks for reaching out about the quote.\n\n"
    "Kind regards,\n"
    "Sarah Jones\n\n"
    "Acme Solutions (Pty) Ltd\n"
    "Tel: 011 234 5678\n"
    "Website: www.acmesolutions.co.za\n"
    "VAT Reg No: 4123456789\n"
)


def _build_signature_mailbox(tmp_path):

    mbox_path = str(tmp_path / "Inbox")

    mbox = mailbox.mbox(mbox_path)
    mbox.lock()

    message = mailbox.mboxMessage()
    message["From"] = "Sarah Jones <sarahjones88@gmail.com>"
    message["To"] = "someone@example.com"
    message["Subject"] = "Quote Request"
    message["Message-ID"] = "<signature-test@example.com>"
    message.set_payload(SIGNATURE_BODY)

    mbox.add(message)

    mbox.flush()
    mbox.unlock()
    mbox.close()

    return Mailbox(
        id=mbox_path,
        name="Inbox",
        source="Thunderbird",
        relative_path="Inbox",
        full_path=mbox_path,
    )


def _collect_candidates(tmp_path):

    mailbox_item = _build_signature_mailbox(tmp_path)

    collector = AutomaticEmailAddressCollector(
        database_path=str(tmp_path / "test.db"),
    )

    result = collector.collect([mailbox_item])

    return {
        candidate.normalized_email: candidate
        for candidate in result["candidates"]
    }


def test_sender_candidate_gets_extracted_signature_fields(tmp_path):

    candidates = _collect_candidates(tmp_path)

    sender = candidates["sarahjones88@gmail.com"]

    assert sender.extracted_phone == "011 234 5678"
    assert sender.extracted_website == "www.acmesolutions.co.za"
    assert sender.extracted_vat_number == "4123456789"
    assert sender.extracted_company_name == "Acme Solutions (Pty) Ltd"


def test_recipient_candidate_does_not_inherit_sender_signature(tmp_path):

    candidates = _collect_candidates(tmp_path)

    recipient = candidates["someone@example.com"]

    assert recipient.extracted_phone == ""
    assert recipient.extracted_website == ""
    assert recipient.extracted_vat_number == ""
    assert recipient.extracted_company_name == ""


def test_extracted_signature_fields_round_trip_through_database(tmp_path):

    mailbox_item = _build_signature_mailbox(tmp_path)

    collector = AutomaticEmailAddressCollector(
        database_path=str(tmp_path / "test.db"),
    )

    collector.collect([mailbox_item])

    reloaded = {
        candidate.normalized_email: candidate
        for candidate in collector.repository.get_candidates()
    }
    sender = reloaded["sarahjones88@gmail.com"]

    assert sender.extracted_phone == "011 234 5678"
    assert sender.extracted_website == "www.acmesolutions.co.za"
    assert sender.extracted_vat_number == "4123456789"
    assert sender.extracted_company_name == "Acme Solutions (Pty) Ltd"
