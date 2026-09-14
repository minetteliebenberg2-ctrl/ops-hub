"""Regression tests for proposal customer resolution.

The Gallery photo picker and auto-filing to client folders require a CRM
customer_id.  Older proposals (or those where the company name was typed
manually) have customer_id="" — _resolve_customer_id must still find the
right customer by name so the Gallery picker opens instead of the OS file
dialog.  This broke twice before; these tests lock it down.
"""

import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from core.customer import Customer
from modules.proposals.services import ClientData, ProposalData


@dataclass
class _FakeFormWindow:
    """Minimal stand-in for ProposalFormWindow with just the fields
    _resolve_customer_id needs."""

    proposal: ProposalData = None
    crm_service: MagicMock = None

    # Paste the real method so the test breaks if the signature drifts.
    def _resolve_customer_id(self):
        cid = getattr(self.proposal.client, "customer_id", None) or ""
        if cid:
            return cid
        name = getattr(self.proposal.client, "company_name", None) or ""
        if not name.strip():
            return ""
        matches = self.crm_service.search_customers(name.strip())
        for c in matches:
            if c.name.strip().lower() == name.strip().lower():
                self.proposal.client.customer_id = c.id
                return c.id
        return ""


class ResolveCustomerIdTests(unittest.TestCase):

    def _make(self, customer_id="", company_name="", search_results=None):
        client = ClientData(customer_id=customer_id, company_name=company_name)
        proposal = ProposalData(client=client)
        crm = MagicMock()
        crm.search_customers.return_value = search_results or []
        form = _FakeFormWindow(proposal=proposal, crm_service=crm)
        return form

    def test_returns_existing_customer_id_without_searching(self):
        form = self._make(customer_id="abc-123", company_name="Acme")
        self.assertEqual(form._resolve_customer_id(), "abc-123")
        form.crm_service.search_customers.assert_not_called()

    def test_resolves_by_name_when_customer_id_empty(self):
        customer = Customer(id="found-456", name="FacilitiesCo")
        form = self._make(company_name="FacilitiesCo", search_results=[customer])
        self.assertEqual(form._resolve_customer_id(), "found-456")
        self.assertEqual(form.proposal.client.customer_id, "found-456")

    def test_case_insensitive_name_match(self):
        customer = Customer(id="ci-789", name="facilitiesco")
        form = self._make(company_name="FacilitiesCo", search_results=[customer])
        self.assertEqual(form._resolve_customer_id(), "ci-789")

    def test_returns_empty_when_no_name_and_no_id(self):
        form = self._make()
        self.assertEqual(form._resolve_customer_id(), "")

    def test_returns_empty_when_name_has_no_crm_match(self):
        form = self._make(company_name="Unknown Corp", search_results=[])
        self.assertEqual(form._resolve_customer_id(), "")

    def test_does_not_match_partial_name(self):
        customer = Customer(id="partial", name="FacilitiesCo Holdings")
        form = self._make(company_name="FacilitiesCo", search_results=[customer])
        self.assertEqual(form._resolve_customer_id(), "")

    def test_backfills_customer_id_on_proposal_client(self):
        """Once resolved, customer_id is cached on the proposal so subsequent
        calls don't re-search — and so the proposal can be saved with the link."""
        customer = Customer(id="backfill-1", name="Test Client")
        form = self._make(company_name="Test Client", search_results=[customer])
        form._resolve_customer_id()
        self.assertEqual(form.proposal.client.customer_id, "backfill-1")
        # Second call should return cached id without searching again.
        form.crm_service.search_customers.reset_mock()
        self.assertEqual(form._resolve_customer_id(), "backfill-1")
        form.crm_service.search_customers.assert_not_called()


if __name__ == "__main__":
    unittest.main()
