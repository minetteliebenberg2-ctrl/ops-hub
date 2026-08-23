# ==========================================================
# FC Hub - PDF Customer Extractor
# ----------------------------------------------------------
# Purpose:
# Best-effort extraction of a customer's name, address, contact
# person, email, and VAT number from FacilitiesCo's own legacy
# Estimate/Invoice/Statement PDF template (the "To: ... Attention:
# ... Email:" layout used for years of real quotes, alongside and
# before FC Hub itself). This is NOT a general-purpose PDF parser -
# it is shaped around one specific, real template, mined from ~70 of
# Minette's actual documents (2026-08-05). Never auto-trusted blindly:
# every result carries a list of issues, and CRM import only
# auto-saves a result with no issues - anything else is routed to
# manual review rather than guessed into the database.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import re
from dataclasses import dataclass, field

from core.document_text_reader import DocumentTextReader


# The template prints two columns per line (customer name/address on
# the left, document metadata like "QUOTE:"/"VAT #"/"YOUR REG:" on the
# right) but pypdf's flat text extraction collapses both columns onto
# one line in reading order, so the right-column text has to be
# stripped back off. Matches the metadata labels appearing anywhere in
# a line and removes everything from there to the end of that line.
RIGHT_COLUMN_MARKER = re.compile(
    r"\s*(?:YOUR\s+)?(?:\bQUOTE\b|\bINVOICE\b|\bVAT\s*#|\bSUPPLIER\s*#|\bPO\s*NUMBER\b|\bREG\b|\bFOR\b)\s*#?\s*:?.*$",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# The template prints VAT numbers space-grouped ("VAT # 4 570 123 218"),
# so the value must be captured to the end of the line and reassembled -
# an earlier \S* capture stopped at the first space and imported the VAT
# number as literally "4" (found 2026-08-05, still live until now).
# [^\r\n]* can't cross a newline, so a blank value still can't swallow
# the next line.
VAT_PATTERN = re.compile(r"VAT\s*#[ \t]*([^\r\n]*)", re.IGNORECASE)
# The customer's own company registration number - "YOUR REG" in the
# template, distinct from their VAT number.
REGISTRATION_PATTERN = re.compile(r"YOUR\s+REG\s*:?[ \t]*([^\r\n]*)", re.IGNORECASE)
# Extra contact people are named in the body, below the line items
# ("Contact: Thamsi / Phillimon") rather than in the "Attention:" header.
BODY_CONTACT_LINE = re.compile(r"^\s*Contact\s*:\s*(.+)$", re.IGNORECASE)
CONTACT_SEPARATOR = re.compile(r"\s*[/,&]\s*|\s+and\s+", re.IGNORECASE)
LEFTOVER_METADATA = re.compile(r"\b(QUOTE|INVOICE|VAT|REG|SUPPLIER|FOR)\b", re.IGNORECASE)
# A lowercase letter, digit, or "%" directly followed by an uppercase
# letter and then another lowercase letter usually means two
# column-merge artifacts ran together (e.g. "NettingCnrs Hendrik
# Potgieter", "80%Cnrs Hendrik...") rather than a real address. The
# trailing lowercase requirement matters: without it, a real unit
# suffix like "13A" (digit + single capital, then a space) would be
# mistaken for a merge artifact.
COLUMN_MERGE_ARTIFACT = re.compile(r"[a-z0-9%][A-Z][a-z]")
BLANK_VALUES = {"", "TBA", "N/A", "TBC"}
CITY_POSTAL_CODE = re.compile(r"^(.+?),\s*(\d{4})$")
# Order/PO references appear as whole lines inside the To: block - both
# in the name position ("To: ORDER # N/A") and further down among the
# address lines ("PO # TBC" on its own line, which is how "PO # TBC"
# ended up saved as part of a real customer's address). Matches only
# when the WHOLE line is just this reference (not a real company name
# that happens to mention an order/PO), so it's safe to strip outright.
TO_LINE_REFERENCE = re.compile(
    r"^(?:ORDER|PO|QUOTE|INVOICE|SUPPLIER)\s*#\s*\S*$", re.IGNORECASE,
)


def normalise_reference_number(raw):
    """Cleans a VAT/registration number captured to end-of-line.

    The template space-groups VAT numbers ("4 570 123 218", and in the
    body of the same document "457 012 3218" - both meaning 4570123218),
    so an all-digits-and-spaces value has its spaces squeezed out. A
    value that isn't purely digits (a registration number like
    2024/772013/07, or trailing right-column text) falls back to the
    first whitespace-delimited token, which is the old behaviour."""

    value = (raw or "").strip()
    if not value or value.upper() in BLANK_VALUES:
        return ""

    if re.fullmatch(r"\d[\d \t]*", value):
        return re.sub(r"\s+", "", value)

    token = value.split()[0]
    return "" if token.upper() in BLANK_VALUES else token


@dataclass
class ExtractedContact:

    name: str = ""
    email: str = ""
    phone: str = ""


@dataclass
class ExtractedCustomer:

    source_file: str = ""
    name: str = ""
    address_lines: list = field(default_factory=list)
    contact_name: str = ""
    email: str = ""
    contacts: list = field(default_factory=list)
    vat_number: str = ""
    registration_number: str = ""
    issues: list = field(default_factory=list)

    @property
    def confidence(self):
        return "low" if self.issues else "high"


class PdfCustomerExtractor:

    def __init__(self, document_reader=None):

        self.document_reader = document_reader or DocumentTextReader()

    # --------------------------------------------------

    def extract(self, file_path):

        text = self.document_reader.read(file_path)
        result = ExtractedCustomer(source_file=str(file_path))

        lines = [line.rstrip() for line in text.split("\n")]
        lower_lines = [line.lower() for line in lines]

        to_index = next(
            (i for i, line in enumerate(lower_lines) if line.strip().startswith("to:")), None,
        )
        if to_index is None:
            result.issues.append('No "To:" line found - unrecognized document layout.')
            return result

        attention_index = next(
            (
                i for i in range(to_index, len(lines))
                if lower_lines[i].strip().startswith("attention:")
            ),
            None,
        )
        if attention_index is None:
            result.issues.append('No "Attention:" line found - unrecognized document layout.')
            return result

        block = list(lines[to_index:attention_index])
        block[0] = re.sub(r"^\s*To:\s*", "", block[0], flags=re.IGNORECASE)

        cleaned_lines = []
        for raw_line in block:
            stripped = RIGHT_COLUMN_MARKER.sub("", raw_line).strip()
            stripped = re.sub(r"^Address:\s*", "", stripped, flags=re.IGNORECASE).strip()
            if stripped:
                cleaned_lines.append(stripped)

        if cleaned_lines and TO_LINE_REFERENCE.match(cleaned_lines[0]):
            cleaned_lines = cleaned_lines[1:]
            result.issues.append(
                'An order/PO reference was found where the company name should be - '
                'please verify the name and address below.'
            )

        result.name = cleaned_lines[0] if cleaned_lines else ""
        # Any remaining whole-line order/PO/supplier reference is document
        # metadata sitting among the address lines, not part of the address.
        address_lines = [
            line for line in cleaned_lines[1:] if not TO_LINE_REFERENCE.match(line)
        ]
        # The template sometimes prints the customer's name twice (once
        # inline after "To:", again alone on the next line) - that's a
        # duplicate, not a real address line.
        if address_lines and address_lines[0].strip().lower() == result.name.strip().lower():
            address_lines = address_lines[1:]
        result.address_lines = address_lines

        attention_line = lines[attention_index]
        result.contact_name = re.sub(
            r"^\s*Attention:\s*", "", attention_line, flags=re.IGNORECASE,
        ).strip()

        for i in range(attention_index, min(attention_index + 3, len(lines))):
            if "email:" in lower_lines[i]:
                email_match = EMAIL_PATTERN.search(lines[i])
                if email_match:
                    result.email = email_match.group(0)
                break

        vat_match = VAT_PATTERN.search(text)
        result.vat_number = normalise_reference_number(
            vat_match.group(1) if vat_match else "",
        )

        registration_match = REGISTRATION_PATTERN.search(text)
        result.registration_number = normalise_reference_number(
            registration_match.group(1) if registration_match else "",
        )

        result.contacts = self._collect_contacts(result, lines)

        if not result.name:
            result.issues.append("No customer name found.")
        if not address_lines:
            result.issues.append("No address found.")
        if not result.email:
            result.issues.append("No email address found.")
        if any(LEFTOVER_METADATA.search(x) for x in [result.name, *address_lines]):
            result.issues.append("Leftover document text found in the name/address - likely a parsing artifact.")
        if any(COLUMN_MERGE_ARTIFACT.search(x) for x in address_lines):
            result.issues.append("Possible run-together text in the address (two columns merged) - please check.")

        return result

    # --------------------------------------------------

    def _collect_contacts(self, result, lines):
        """Every contact person named on the document, in document order.

        The "Attention:" name in the header is the primary one and owns
        the "Email:" address directly below it. Some documents name
        further people in a body line ("Contact: Thamsi / Phillimon") -
        those are real contacts too, but the document gives no email or
        phone for them, so they come in with a name only. The template
        never prints a client phone number at all."""

        contacts = []
        seen = set()

        def add(name, email=""):
            name = (name or "").strip()
            if not name or name.lower() in seen:
                return
            seen.add(name.lower())
            contacts.append(ExtractedContact(name=name, email=email))

        add(result.contact_name, result.email)

        for line in lines:
            match = BODY_CONTACT_LINE.match(line)
            if not match:
                continue
            for part in CONTACT_SEPARATOR.split(match.group(1)):
                part = (part or "").strip()
                # Body lines are free text - keep short people-shaped
                # names and drop sentences that happen to start "Contact:".
                if part and len(part) <= 40 and "@" not in part:
                    add(part)

        return contacts


def split_address_lines(address_lines):
    """Maps free-form address lines onto FC Hub's structured Address
    fields (line1/line2/city/postal_code). The source documents don't
    label which line is the city vs. the street, so this only ever
    infers a city/postal code when the last line unambiguously matches
    "City, 1234" - everything else stays in line1/line2 rather than
    being guessed at."""

    if not address_lines:
        return "", "", "", ""

    line1 = address_lines[0]
    remaining = list(address_lines[1:])
    city = ""
    postal_code = ""

    if remaining:
        match = CITY_POSTAL_CODE.match(remaining[-1])
        if match:
            city, postal_code = match.group(1), match.group(2)
            remaining = remaining[:-1]

    line2 = ", ".join(remaining)
    return line1, line2, city, postal_code
