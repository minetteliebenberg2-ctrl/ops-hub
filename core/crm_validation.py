# ==========================================================
# FC Utilities - CRM Validation
# ----------------------------------------------------------
# Purpose:
# Validation for CRM models.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import re


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(Exception):

    """Raised when CRM validation fails."""


class CRMValidation:

    def validate_customer(self, customer):

        errors = []

        if not customer.name.strip():
            errors.append("Customer name is required.")

        if customer.email.strip() and not EMAIL_PATTERN.match(customer.email.strip()):
            errors.append("Customer email is invalid.")

        self.raise_for_errors(errors)

    # --------------------------------------------------

    def validate_contact(self, contact):

        errors = []

        if not contact.customer_id.strip():
            errors.append("Customer is required.")

        if not contact.name.strip():
            errors.append("Contact name is required.")

        if contact.email.strip() and not EMAIL_PATTERN.match(contact.email.strip()):
            errors.append("Contact email is invalid.")

        self.raise_for_errors(errors)

    # --------------------------------------------------

    def validate_address(self, address):

        errors = []

        if not address.customer_id.strip():
            errors.append("Customer is required.")

        if not address.line1.strip():
            errors.append("Address line 1 is required.")

        self.raise_for_errors(errors)

    # --------------------------------------------------

    def validate_site(self, site):

        errors = []

        if not site.customer_id.strip():
            errors.append("Customer is required.")

        if not site.name.strip():
            errors.append("Site name is required.")

        self.raise_for_errors(errors)

    # --------------------------------------------------

    def validate_activity(self, activity):

        errors = []

        if not activity.customer_id.strip():
            errors.append("Customer is required.")

        if not activity.subject.strip():
            errors.append("Activity subject is required.")

        self.raise_for_errors(errors)

    # --------------------------------------------------

    def raise_for_errors(self, errors):

        if errors:
            raise ValidationError("\n".join(errors))
