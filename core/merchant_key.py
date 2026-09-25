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


# Words the bank puts in front of, or behind, a real merchant name. A key
# made of nothing but these identifies nobody and must never group rows.
GENERIC_WORDS = {
    "SEND", "PURCH", "PAYMENT", "PMT", "TRANSFER", "TRF", "EFT", "FNB",
    "APP", "INTERNET", "FROM", "TO", "CR", "DR", "DEBIT", "CREDIT", "CARD",
}

# A one-word merchant must be this long before it is allowed to match
# longer keys - "ML" should never sweep up everything starting with ML.
MIN_SINGLE_WORD = 4


def merchant_matches(first, second):
    """True when two merchant keys name the same payee.

    Exact equality is too strict for real statements: FNB appends a
    different trailing word to almost every payment, so one merchant
    arrives as "SEND JAMES WELDING", "SEND JAMES WELDING WELDING" and
    "SEND JAMES WELDING NEW NUMBER". Those are one payee.

    The rule is deliberately conservative - one key must be a whole-word
    prefix of the other. "SPAR HOMESTEAD" and "SPAR THE PALMS" diverge at
    the second word and stay apart, which is what she wants: those are
    different shops.
    """

    if not first or not second:
        return False
    if first == second:
        return True

    short, long_ = sorted((first.split(), second.split()), key=len)
    if long_[: len(short)] != short:
        return False

    # The shared part has to identify someone on its own.
    if all(word in GENERIC_WORDS for word in short):
        return False
    if len(short) == 1 and len(short[0]) < MIN_SINGLE_WORD:
        return False
    return True
