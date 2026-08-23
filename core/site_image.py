# ==========================================================
# FC Hub - Site Image
# ----------------------------------------------------------
# Purpose:
# A real, processed site photo linked to a customer (and optionally a
# Site / Site Visit). Physical file lives in the customer's own
# client folder; this is the metadata record.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class SiteImage:

    id: str = ""
    customer_id: str = ""
    site_id: str = ""
    site_visit_id: str = ""
    stored_filename: str = ""
    original_filename: str = ""
    caption: str = ""
    width: int = 0
    height: int = 0
    taken_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    archived_at: str = ""
    archived_by: str = ""
    archive_reason: str = ""
    tags: str = ""
    album: str = ""
    file_hash: str = ""
    file_size: int = 0

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]
