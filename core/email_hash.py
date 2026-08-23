# ==========================================================
# FC Utilities - Email Hash
# ----------------------------------------------------------
# Purpose:
# Generate stable identifiers for duplicate email detection.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import hashlib
from email.utils import parsedate_to_datetime


class EmailHash:

    def normalize_message_id(self, message_id):

        return str(message_id or "").strip().lower()

    # ------------------------------------------------------

    def normalize_text(self, value):

        return " ".join(str(value or "").lower().split())

    # ------------------------------------------------------

    def normalize_date(self, value):

        try:

            return parsedate_to_datetime(str(value or "")).isoformat()

        except Exception:

            return self.normalize_text(value)

    # ------------------------------------------------------

    def message_id_key(self, message):

        return self.normalize_message_id(message.get("Message-ID", ""))

    # ------------------------------------------------------

    def probable_key(self, message, message_size):

        parts = [
            self.normalize_text(message.get("From", "")),
            self.normalize_text(message.get("To", "")),
            self.normalize_text(message.get("Subject", "")),
            self.normalize_date(message.get("Date", "")),
            str(message_size or 0),
        ]

        payload = "|".join(parts)

        return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()
