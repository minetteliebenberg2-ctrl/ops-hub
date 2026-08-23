# ==========================================================
# FC Utilities - Contact
# ----------------------------------------------------------
# Purpose:
# Standard contact model used by all communication plugins.
#
# Author: Minette & James
# Version: 3.0
# ==========================================================

from dataclasses import dataclass, field


@dataclass
class Contact:

    # ------------------------------------------------------
    # Identity
    # ------------------------------------------------------

    id: str = ""

    customer_id: str = ""

    is_primary: bool = False

    name: str = ""

    company: str = ""

    job_title: str = ""

    source: str = ""

    # ------------------------------------------------------
    # Contact Details
    # ------------------------------------------------------

    email: str = ""

    phone: str = ""

    mobile: str = ""

    whatsapp: str = ""

    website: str = ""

    linkedin: str = ""

    facebook: str = ""

    instagram: str = ""

    x: str = ""

    # ------------------------------------------------------
    # Communication Statistics
    # ------------------------------------------------------

    first_contact: str = ""

    last_contact: str = ""

    last_incoming: str = ""

    last_outgoing: str = ""

    incoming: int = 0

    outgoing: int = 0

    total_messages: int = 0

    replies: int = 0

    average_reply_time: float = 0.0

    last_subject: str = ""

    # ------------------------------------------------------
    # Multi-Channel Intelligence
    # ------------------------------------------------------

    email_messages: int = 0

    whatsapp_messages: int = 0

    phone_calls: int = 0

    meetings: int = 0

    preferred_channel: str = ""

    channels: list = field(default_factory=list)

    # ------------------------------------------------------
    # Business
    # ------------------------------------------------------

    category: str = ""

    status: str = ""

    priority: str = ""

    value: float = 0.0

    customer: bool = False

    supplier: bool = False

    prospect: bool = False

    subcontractor: bool = False

    employee: bool = False

    tags: list = field(default_factory=list)

    notes: str = ""

    # ------------------------------------------------------
    # Marketing
    # ------------------------------------------------------

    subscribed: bool = True

    newsletter: bool = False

    quoted: bool = False

    repeat_customer: bool = False

    last_campaign: str = ""

    campaign_opens: int = 0

    campaign_clicks: int = 0

    # ------------------------------------------------------
    # Intelligence
    # ------------------------------------------------------

    domain: str = ""

    department: str = ""

    importance: int = 0

    health_score: int = 0

    first_seen: str = ""

    last_seen: str = ""

    # ------------------------------------------------------
    # Timeline
    # ------------------------------------------------------

    timeline: list = field(default_factory=list)

    created_at: str = ""

    updated_at: str = ""

    created_by: str = ""

    updated_by: str = ""

    archived_at: str = ""

    archived_by: str = ""

    archive_reason: str = ""

    deleted_at: str = ""

    deleted_by: str = ""
