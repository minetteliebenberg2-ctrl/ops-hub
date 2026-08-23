# ==========================================================
# FC Hub - Communications Mailbox Adapter
# ----------------------------------------------------------
# Purpose:
# Reuse FC Utilities Thunderbird mailbox discovery when available.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================


class MailboxDiscoveryAdapter:

    def __init__(self):

        self.scanner = self.load_scanner()

    # ------------------------------------------------------

    def load_scanner(self):

        try:

            from core.mail_scanner import MailScanner

            return MailScanner()

        except Exception:

            return None

    # ------------------------------------------------------

    def scan_mailboxes(self):

        if self.scanner is None:

            return []

        profiles = self.scanner.find_profiles()
        self.scanner.read_accounts()

        active_profile = None

        for profile in profiles:

            if profile["active"]:

                active_profile = profile
                break

        if active_profile is None:

            return []

        return self.scanner.scan(active_profile)
