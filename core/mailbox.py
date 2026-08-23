# ==========================================================
# FC Utilities - Mailbox
# ----------------------------------------------------------
# Purpose:
# Standard mailbox model used by all communication plugins.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass, field


@dataclass
class Mailbox:

    # ----------------------------------------------
    # Identity
    # ----------------------------------------------

    id: str

    name: str

    source: str

    # Thunderbird
    # Gmail
    # Outlook
    # WhatsApp (future)

    # ----------------------------------------------
    # Structure
    # ----------------------------------------------

    parent: str = ""

    relative_path: str = ""

    full_path: str = ""

    children: list = field(default_factory=list)

    # ----------------------------------------------
    # Status
    # ----------------------------------------------

    selected: bool = False

    empty: bool = False

    # ----------------------------------------------
    # Statistics
    # ----------------------------------------------

    size: int = 0

    message_count: int = 0

    unread_count: int = 0

    # ----------------------------------------------
    # Convenience
    # ----------------------------------------------

    @property
    def display_name(self):

        return self.relative_path if self.relative_path else self.name
