# ==========================================================
# FC Utilities - Message Comparison
# ----------------------------------------------------------
# Purpose:
# Weighted duplicate message comparison.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from email.utils import parsedate_to_datetime


class MessageComparison:

    def __init__(self):

        self.threshold = 80

        self.rules = [
            ("sender", 20),
            ("recipient", 20),
            ("subject", 25),
            ("date", 20),
            ("size", 15),
        ]

    # ------------------------------------------------------

    def compare(self, first, second):

        score = 0

        for rule, weight in self.rules:

            if rule == "sender" and self.same_text(
                first.sender,
                second.sender,
            ):

                score += weight

            elif rule == "recipient" and self.same_text(
                first.recipient,
                second.recipient,
            ):

                score += weight

            elif rule == "subject" and self.same_text(
                first.subject,
                second.subject,
            ):

                score += weight

            elif rule == "date" and self.same_date(
                first.date,
                second.date,
            ):

                score += weight

            elif rule == "size" and self.same_size(
                first.message_size,
                second.message_size,
            ):

                score += weight

        return score

    # ------------------------------------------------------

    def is_probable_duplicate(self, first, second):
        """Same sender/recipient/subject/size alone (80 of the 100 possible
        points) is not enough - that pattern also matches distinct recurring
        template emails (e.g. monthly banking notifications from the same
        sender with the same subject and similar size). Date match is a
        mandatory gate, not just a scored bonus, so two messages received on
        different days are never treated as duplicates of each other."""

        if not self.same_date(first.date, second.date):

            return False

        return self.compare(first, second) >= self.threshold

    # ------------------------------------------------------

    def same_text(self, first, second):

        return self.normalize_text(first) == self.normalize_text(second)

    # ------------------------------------------------------

    def same_date(self, first, second):

        first_value = self.normalize_date(first)
        second_value = self.normalize_date(second)

        if not first_value or not second_value:

            return False

        return first_value == second_value

    # ------------------------------------------------------

    def same_size(self, first, second):

        try:

            first_size = int(first or 0)
            second_size = int(second or 0)

        except Exception:

            return False

        if first_size == second_size:

            return True

        difference = abs(first_size - second_size)

        return difference <= 1024

    # ------------------------------------------------------

    def normalize_text(self, value):

        return " ".join(str(value or "").lower().split())

    # ------------------------------------------------------

    def normalize_date(self, value):

        try:

            parsed = parsedate_to_datetime(str(value or ""))

            return parsed.replace(microsecond=0).isoformat()

        except Exception:

            return self.normalize_text(value)
