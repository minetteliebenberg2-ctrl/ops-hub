"""Split deposit / balance Tax Invoices (2026-09-22)."""

from datetime import datetime

import pytest
from pypdf import PdfReader

from core.business_document_pdf import generate_invoice_pdf
from tests.test_statements import (  # noqa: F401 - fixtures
    crm_service, make_customer, quote_document_service, quote_service,
    statement_service, test_db,
)


def make_split_quote(quote_service, customer_id, unit_price_minor=1234567):
    quote = quote_service.save_quote(quote_service.new_quote(customer_id), "minette")
    item = quote_service.new_line_item(quote.id)
    item.structure_type = "Cantilever"
    item.quantity = 1
    item.unit_price_minor = unit_price_minor
    quote_service.save_line_item(item)
    quote_service.issue_quote(quote.id, "minette")
    quote = quote_service.get_quote(quote.id)
    quote.split_invoice = True
    quote_service.save_quote(quote, "minette")
    return quote_service.get_quote(quote.id)


def test_split_flag_persists(crm_service, quote_service):
    quote = make_split_quote(quote_service, make_customer(crm_service).id)
    assert quote.split_invoice is True


def test_deposit_and_balance_sum_to_total(crm_service, quote_service, quote_document_service):
    quote = make_split_quote(quote_service, make_customer(crm_service).id)
    deposit = quote_document_service.generate_deposit_invoice(quote.id, "minette")
    balance = quote_document_service.generate_balance_invoice(quote.id, "minette")

    assert deposit.invoice_part == "deposit" and balance.invoice_part == "balance"
    assert deposit.total_minor == round(quote.total_minor * 0.65)
    assert deposit.total_minor + balance.total_minor == quote.total_minor
    assert "I_" in deposit.document_number and deposit.document_number != balance.document_number
    stored = {d.id: d for d in quote_document_service.list_for_quote(quote.id)}
    assert stored[deposit.id].total_minor == deposit.total_minor
    assert stored[balance.id].invoice_part == "balance"


def test_balance_blocked_without_deposit(crm_service, quote_service, quote_document_service):
    quote = make_split_quote(quote_service, make_customer(crm_service).id)
    with pytest.raises(ValueError):
        quote_document_service.generate_balance_invoice(quote.id, "minette")


def test_statement_lines_include_both_parts(crm_service, quote_service, quote_document_service, statement_service):
    customer = make_customer(crm_service)
    quote = make_split_quote(quote_service, customer.id)
    deposit = quote_document_service.generate_deposit_invoice(quote.id, "minette")
    balance = quote_document_service.generate_balance_invoice(quote.id, "minette")

    today = datetime.now().strftime("%Y-%m-%d")
    lines = statement_service.build_lines(customer.id, today, today, quote_service=quote_service)
    refs = {line["ref"]: line["amount_minor"] for line in lines}
    assert refs == {deposit.document_number: deposit.total_minor, balance.document_number: balance.total_minor}
    assert sum(refs.values()) == quote.total_minor


def test_split_pdfs_render(tmp_path, crm_service, quote_service, quote_document_service):
    customer = make_customer(crm_service)
    quote = make_split_quote(quote_service, customer.id)
    items = quote_service.list_line_items(quote.id)
    deposit = quote_document_service.generate_deposit_invoice(quote.id, "minette")
    balance = quote_document_service.generate_balance_invoice(quote.id, "minette")

    class Settings:
        def __getattr__(self, _name):
            return ""

    for doc, extra in ((deposit, {}), (balance, {"deposit_document": deposit})):
        out = tmp_path / f"{doc.invoice_part}.pdf"
        generate_invoice_pdf(doc, quote, items, customer, None, Settings(), out, **extra)
        text = PdfReader(str(out)).pages[0].extract_text()
        if doc is deposit:
            assert "65% deposit on" in text
        else:
            assert "Less deposit invoiced" in text and deposit.document_number in text
            assert "Balance due" in text
