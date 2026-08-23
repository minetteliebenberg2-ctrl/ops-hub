# ==========================================================
# FC Hub - Merchant Key
# ----------------------------------------------------------
# Purpose:
# Reduces a bank-statement description down to the merchant
# it came from, so "KWIKSPAR HOMESTEAD  485442*7275  28 JUN"
# and "KWIKSPAR HOMESTEAD  485442*7275  24 JUN" are recognised
# as the same payee and can be categorised together.
#
# Author: Minette & Claude
# Version: 1.0
# ==========================================================

import re


# The card mask FNB prints on card purchases ("485442*7275"). Everything
# from there on is card number + transaction date, never merchant name.
CARD_MASK = re.compile(r"\d{4,6}\s*\*\s*\d{3,4}.*$")

# A trailing "28 JUN" / "01 JULY" style date, and FNB's "AUG 260801"
# statement-period stamp - both vary per transaction for one merchant.
TRAILING_DATE = re.compile(
    r"\s+\d{1,2}\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*$"
)
TRAILING_PERIOD = re.compile(
    r"\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{4,8}\s*$"
)

# Long digit runs left over mid-string (reference/account numbers).
LONG_DIGITS = re.compile(r"\s+\d{5,}\s*")


def merchant_key(description):
    """A normalised merchant identity for a statement description.

    Returns "" when nothing meaningful survives - callers must treat an
    empty key as "cannot group this one", never as a wildcard that
    matches every uncategorised row.
    """

    if not description:
        return ""

    text = " ".join(str(description).split()).upper()

    text = CARD_MASK.sub("", text)
    text = TRAILING_PERIOD.sub("", text)
    text = TRAILING_DATE.sub("", text)
    text = LONG_DIGITS.sub(" ", text)

    text = " ".join(text.split()).strip(" -*.,/")

    # A key that is only digits/punctuation identifies nothing.
    if not any(character.isalpha() for character in text):
        return ""

    return text


def matches_key(description, key):
    """True when a description belongs to the merchant named by `key`."""

    if not key:
        return False
    return merchant_key(description) == key.strip().upper()


__all__ = ["merchant_key", "matches_key"]
