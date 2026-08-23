# ==========================================================
# FC Hub - Signature Field Extractor
# ----------------------------------------------------------
# Purpose:
# Best-effort extraction of company name, phone, website,
# and VAT number from free text (email bodies, Word/PDF
# documents). Every result is a guess for human review -
# never auto-trusted, never auto-imported.
# ==========================================================

import re

PHONE_PATTERN = re.compile(
    r"(?:\+27\s?\d{2}|\(0\d{2}\)|0\d{2})[\s.-]?\d{3}[\s.-]?\d{4}"
)

WEBSITE_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}(?:/\S*)?",
)

VAT_PATTERN = re.compile(
    r"VAT\s*(?:Reg(?:istration)?)?\s*(?:No\.?|Number)?\s*[:#]?\s*(\d{10})",
    re.IGNORECASE,
)

COMPANY_SUFFIX_PATTERN = re.compile(
    r"^.*\b(?:\(Pty\)\s*Ltd|Pty\s*Ltd|CC|Inc\.?|Ltd\.?|LLC)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class SignatureFieldExtractor:
    """Extracts likely contact fields from free text.

    Every field returned is a best-effort guess and must be
    confirmed by a human before it is written to the CRM.
    """

    def extract(self, text):

        text = text or ""

        return {
            "phone": self._extract_phone(text),
            "website": self._extract_website(text),
            "vat_number": self._extract_vat_number(text),
            "company_name": self._extract_company_name(text),
        }

    # --------------------------------------------------

    def _extract_phone(self, text):

        match = PHONE_PATTERN.search(text)

        if not match:
            return ""

        return match.group(0).strip()

    # --------------------------------------------------

    def _extract_website(self, text):

        masked_text = EMAIL_PATTERN.sub(" ", text)

        match = WEBSITE_PATTERN.search(masked_text)

        if not match:
            return ""

        return match.group(0).strip().rstrip(".,")

    # --------------------------------------------------

    def _extract_vat_number(self, text):

        match = VAT_PATTERN.search(text)

        if not match:
            return ""

        return match.group(1)

    # --------------------------------------------------

    def _extract_company_name(self, text):

        match = COMPANY_SUFFIX_PATTERN.search(text)

        if not match:
            return ""

        return match.group(0).strip().strip(",;")
