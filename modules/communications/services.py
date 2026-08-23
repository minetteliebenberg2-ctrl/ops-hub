# ==========================================================
# FC Hub - Communications Services
# ----------------------------------------------------------
# Purpose:
# Contact collection, review queue, ignore list and CRM handoff.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime
import csv
import mailbox
import re

from core.database import Database, DATABASE_PATH
from core.signature_field_extractor import SignatureFieldExtractor


EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


REVIEW_PENDING = "Pending Review"
REVIEW_APPROVED = "Approved"
REVIEW_REJECTED = "Rejected"
REVIEW_IGNORED = "Ignored"
REVIEW_IMPORTED = "Imported"
REVIEW_EXISTING = "Existing Match"
REVIEW_NEEDS_ATTENTION = "Needs Attention"


class AddressClassification:

    VALID = "Valid"
    INVALID = "Invalid"
    BLANK = "Blank"
    DUPLICATE = "Duplicate"
    IGNORED = "Ignored"
    AUTOMATED = "Automated or System"
    EXISTING = "Existing CRM Contact"
    NEW = "New Candidate"


@dataclass
class AddressOccurrence:

    normalized_email: str
    original_email: str
    display_name: str
    source_mailbox: str
    source_folder: str
    source_message_id: str
    message_date: str
    message_subject: str
    header_source: str
    direction: str
    body_text: str = ""


@dataclass
class ContactCandidate:

    normalized_email: str
    original_email: str = ""
    display_name: str = ""
    classification: str = AddressClassification.NEW
    classification_reason: str = ""
    existing_match_status: str = "No Match"
    review_status: str = REVIEW_PENDING
    ignore_status: str = "Active"
    occurrences: int = 0
    first_seen: str = ""
    last_seen: str = ""
    inbound_count: int = 0
    outbound_count: int = 0
    source_mailbox: str = ""
    source_folder: str = ""
    source_header_types: str = ""
    source_message_ids: str = ""
    imported: bool = False

    # Best-effort guesses extracted from the sender's email signature
    # block. These are NEVER auto-trusted and must be confirmed by a
    # human reviewer before being written to the CRM.
    extracted_phone: str = ""
    extracted_website: str = ""
    extracted_vat_number: str = ""
    extracted_company_name: str = ""


def filter_review_queue(candidates, status, hide_archived, search=""):
    """Real filtering logic behind the Contact Review Queue's status
    dropdown, "Hide archived/rejected" checkbox, and search box -
    extracted out of ReviewQueueWindow so it's covered by a real test,
    not just eyeballed in the running app.

    Bug fixed 2026-08-07: the checkbox previously only took effect
    when the status dropdown was on "All" (`hide_archived and status ==
    "All"`), so picking any other status silently disabled it. Now it
    only stands down when she's explicitly asked to see Rejected/
    Ignored via the dropdown itself. Also now excludes
    AddressClassification.INVALID directly, regardless of what
    review_status a given invalid address happens to carry.
    """

    search_term = search.lower().strip()
    hide_active = hide_archived and status not in (REVIEW_REJECTED, REVIEW_IGNORED)

    return [
        candidate
        for candidate in candidates
        if (status == "All" or candidate.review_status == status)
        and (
            not hide_active
            or (
                candidate.review_status not in (REVIEW_IGNORED, REVIEW_REJECTED)
                and candidate.classification != AddressClassification.INVALID
            )
        )
        and (
            not search_term
            or search_term in candidate.normalized_email
            or search_term in candidate.display_name.lower()
        )
    ]


@dataclass
class CRMMatchResult:

    status: str
    matches: list


class EmailAddressNormalizer:

    def normalize(self, value):

        raw_value = str(value or "").strip()

        if not raw_value:

            return {
                "original": value or "",
                "display_name": "",
                "email": "",
            }

        display_name, email = parseaddr(raw_value)

        return {
            "original": raw_value,
            "display_name": display_name.strip(),
            "email": email.strip().lower(),
        }


class EmailAddressValidator:

    def validate(self, normalized_email):

        if not normalized_email:

            return AddressClassification.BLANK

        if not EMAIL_PATTERN.match(normalized_email):

            return AddressClassification.INVALID

        return AddressClassification.VALID


class AutomatedAddressClassifier:

    def __init__(self):

        self.local_part_rules = {
            "no-reply": "No-reply sender",
            "noreply": "No-reply sender",
            "do-not-reply": "Do-not-reply sender",
            "donotreply": "Do-not-reply sender",
            "mailer-daemon": "Mailer daemon",
            "postmaster": "Postmaster",
        }

    # ------------------------------------------------------

    def classify(self, normalized_email, headers=None):

        local_part = normalized_email.split("@", 1)[0] if "@" in normalized_email else ""

        if local_part in self.local_part_rules:

            return self.local_part_rules[local_part]

        headers = headers or {}

        auto_submitted = str(headers.get("Auto-Submitted", "")).lower()

        if auto_submitted and auto_submitted != "no":

            return "Auto-Submitted header"

        content_type = str(headers.get("Content-Type", "")).lower()

        if "delivery-status" in content_type:

            return "Delivery status notification"

        return ""


class CommunicationsDatabase:

    def __init__(self, database_path=None):

        self.database = Database(database_path or DATABASE_PATH)
        self.database_path = self.database.path

    # ------------------------------------------------------

    def connect(self):

        return self.database.connect()

    # ------------------------------------------------------

    def initialize(self):

        return self.database.initialize()


class IgnoreListService:

    def __init__(self, database):

        self.database = database

    # ------------------------------------------------------

    def add_email(self, email, reason=""):

        return self.add_entry("email", email, reason)

    # ------------------------------------------------------

    def add_domain(self, domain, reason=""):

        return self.add_entry("domain", domain, reason)

    # ------------------------------------------------------

    def add_entry(self, entry_type, value, reason=""):

        value = str(value or "").strip().lower()

        if not value:

            return

        with self.database.connect() as connection:

            connection.execute(
                """
                INSERT INTO communication_ignore_list (
                    entry_type,
                    value,
                    reason,
                    created_date,
                    active
                )
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(entry_type, value) DO UPDATE SET
                    reason = excluded.reason,
                    active = 1
                """,
                (
                    entry_type,
                    value,
                    reason,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    # ------------------------------------------------------

    def remove_entry(self, entry_type, value):

        with self.database.connect() as connection:

            connection.execute(
                """
                UPDATE communication_ignore_list
                SET active = 0
                WHERE entry_type = ? AND value = ?
                """,
                (
                    entry_type,
                    str(value or "").strip().lower(),
                ),
            )

    # ------------------------------------------------------

    def is_ignored(self, email):

        email = str(email or "").strip().lower()
        domain = email.split("@", 1)[1] if "@" in email else ""

        with self.database.connect() as connection:

            rows = connection.execute(
                """
                SELECT entry_type, value
                FROM communication_ignore_list
                WHERE active = 1
                """
            ).fetchall()

        for row in rows:

            if row["entry_type"] == "email" and row["value"] == email:

                return True

            if row["entry_type"] == "domain" and row["value"] == domain:

                return True

        return False

    # ------------------------------------------------------

    def list_entries(self):

        with self.database.connect() as connection:

            return connection.execute(
                """
                SELECT entry_type, value, reason, created_date, active
                FROM communication_ignore_list
                ORDER BY entry_type, value
                """
            ).fetchall()


class CRMMatcher:

    def __init__(self, crm_repository=None):

        self.crm_repository = crm_repository

    # ------------------------------------------------------

    def match(self, normalized_email):

        if self.crm_repository is None:

            return CRMMatchResult("No Match", [])

        if hasattr(self.crm_repository, "find_contacts_by_email"):

            matches = self.crm_repository.find_contacts_by_email(normalized_email)

        elif hasattr(self.crm_repository, "find_by_email"):

            matches = self.crm_repository.find_by_email(normalized_email)

        else:

            return CRMMatchResult("No Match", [])

        if not matches:

            return CRMMatchResult("No Match", [])

        if len(matches) == 1:

            return CRMMatchResult("Exact Existing Contact Match", matches)

        return CRMMatchResult("Multiple Existing Matches", matches)


class ContactCandidateRepository:

    def __init__(self, database):

        self.database = database

    # ------------------------------------------------------

    def save_candidate(self, candidate):

        with self.database.connect() as connection:

            connection.execute(
                """
                INSERT INTO communication_candidates (
                    normalized_email,
                    original_email,
                    display_name,
                    classification,
                    classification_reason,
                    existing_match_status,
                    review_status,
                    ignore_status,
                    occurrences,
                    first_seen,
                    last_seen,
                    inbound_count,
                    outbound_count,
                    source_mailbox,
                    source_folder,
                    source_header_types,
                    source_message_ids,
                    imported,
                    extracted_phone,
                    extracted_website,
                    extracted_vat_number,
                    extracted_company_name,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(normalized_email) DO UPDATE SET
                    original_email = excluded.original_email,
                    display_name = excluded.display_name,
                    classification = excluded.classification,
                    classification_reason = excluded.classification_reason,
                    existing_match_status = excluded.existing_match_status,
                    ignore_status = excluded.ignore_status,
                    occurrences = excluded.occurrences,
                    first_seen = excluded.first_seen,
                    last_seen = excluded.last_seen,
                    inbound_count = excluded.inbound_count,
                    outbound_count = excluded.outbound_count,
                    source_mailbox = excluded.source_mailbox,
                    source_folder = excluded.source_folder,
                    source_header_types = excluded.source_header_types,
                    source_message_ids = excluded.source_message_ids,
                    extracted_phone = excluded.extracted_phone,
                    extracted_website = excluded.extracted_website,
                    extracted_vat_number = excluded.extracted_vat_number,
                    extracted_company_name = excluded.extracted_company_name,
                    updated_at = excluded.updated_at
                """,
                self.candidate_values(candidate),
            )

    # ------------------------------------------------------

    def save_occurrence(self, occurrence):

        with self.database.connect() as connection:

            connection.execute(
                """
                INSERT OR IGNORE INTO communication_occurrences (
                    normalized_email,
                    source_message_id,
                    header_source,
                    source_mailbox,
                    message_date
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    occurrence.normalized_email,
                    occurrence.source_message_id,
                    occurrence.header_source,
                    occurrence.source_mailbox,
                    occurrence.message_date,
                ),
            )

    # ------------------------------------------------------

    def get_candidates(self):

        with self.database.connect() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM communication_candidates
                ORDER BY normalized_email
                """
            ).fetchall()

        return [
            self.row_to_candidate(row)
            for row in rows
        ]

    # ------------------------------------------------------

    def update_review_status(self, emails, status):

        if not emails:

            return

        with self.database.connect() as connection:

            connection.executemany(
                """
                UPDATE communication_candidates
                SET review_status = ?, updated_at = ?
                WHERE normalized_email = ?
                """,
                [
                    (
                        status,
                        datetime.now().isoformat(timespec="seconds"),
                        email,
                    )
                    for email in emails
                ],
            )

    # ------------------------------------------------------

    def delete_candidates(self, emails):

        if not emails:

            return

        with self.database.connect() as connection:

            connection.executemany(
                "DELETE FROM communication_candidates WHERE normalized_email = ?",
                [(email,) for email in emails],
            )

    # ------------------------------------------------------

    def candidate_values(self, candidate):

        return (
            candidate.normalized_email,
            candidate.original_email,
            candidate.display_name,
            candidate.classification,
            candidate.classification_reason,
            candidate.existing_match_status,
            candidate.review_status,
            candidate.ignore_status,
            candidate.occurrences,
            candidate.first_seen,
            candidate.last_seen,
            candidate.inbound_count,
            candidate.outbound_count,
            candidate.source_mailbox,
            candidate.source_folder,
            candidate.source_header_types,
            candidate.source_message_ids,
            1 if candidate.imported else 0,
            candidate.extracted_phone,
            candidate.extracted_website,
            candidate.extracted_vat_number,
            candidate.extracted_company_name,
            datetime.now().isoformat(timespec="seconds"),
        )

    # ------------------------------------------------------

    def row_to_candidate(self, row):

        return ContactCandidate(
            normalized_email=row["normalized_email"],
            original_email=row["original_email"],
            display_name=row["display_name"],
            classification=row["classification"],
            classification_reason=row["classification_reason"],
            existing_match_status=row["existing_match_status"],
            review_status=row["review_status"],
            ignore_status=row["ignore_status"],
            occurrences=row["occurrences"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            inbound_count=row["inbound_count"],
            outbound_count=row["outbound_count"],
            source_mailbox=row["source_mailbox"],
            source_folder=row["source_folder"],
            source_header_types=row["source_header_types"],
            source_message_ids=row["source_message_ids"],
            imported=bool(row["imported"]),
            extracted_phone=row["extracted_phone"] or "",
            extracted_website=row["extracted_website"] or "",
            extracted_vat_number=row["extracted_vat_number"] or "",
            extracted_company_name=row["extracted_company_name"] or "",
        )


class AutomaticEmailAddressCollector:

    def __init__(self, database_path=None, crm_repository=None):

        self.database = CommunicationsDatabase(database_path)
        self.database.initialize()
        self.normalizer = EmailAddressNormalizer()
        self.validator = EmailAddressValidator()
        self.automated_classifier = AutomatedAddressClassifier()
        self.ignore_list = IgnoreListService(self.database)
        self.crm_matcher = CRMMatcher(crm_repository)
        self.repository = ContactCandidateRepository(self.database)
        self.signature_extractor = SignatureFieldExtractor()
        self.cancel_requested = False

    # ------------------------------------------------------

    def collect(self, mailboxes, progress_callback=None):

        self.cancel_requested = False
        occurrences = []

        for index, mailbox_item in enumerate(mailboxes):

            if self.cancel_requested:

                break

            if progress_callback:

                progress_callback(
                    f"Collecting {mailbox_item.display_name}",
                    index + 1,
                    len(mailboxes),
                )

            occurrences.extend(self.collect_from_mailbox(mailbox_item))

        candidates = self.aggregate(occurrences)

        for candidate in candidates:

            self.repository.save_candidate(candidate)

        return {
            "candidates": candidates,
            "statistics": self.get_statistics(candidates),
            "cancelled": self.cancel_requested,
        }

    # ------------------------------------------------------

    def cancel(self):

        self.cancel_requested = True

    # ------------------------------------------------------

    def collect_from_mailbox(self, mailbox_item):

        occurrences = []
        mbox = None

        try:
            # Try to open as mbox file (local mailboxes)
            try:
                mbox = mailbox.mbox(mailbox_item.full_path)

                for key in mbox.iterkeys():

                    if self.cancel_requested:
                        break

                    try:
                        message = mbox.get_message(key)
                        occurrences.extend(
                            self.extract_message_addresses(
                                mailbox_item,
                                key,
                                message,
                            )
                        )
                    except Exception:
                        continue

            except (FileNotFoundError, IsADirectoryError, OSError):
                # If mbox fails, try IMAP directory structure
                occurrences.extend(self._collect_from_imap_directory(mailbox_item))

        except Exception:

            return occurrences

        finally:

            if mbox is not None:

                try:

                    mbox.close()

                except Exception:

                    pass

        return occurrences

    # --------------------------------------------------

    def _collect_from_imap_directory(self, mailbox_item):
        """Collect emails from Thunderbird IMAP directory structure"""

        occurrences = []

        try:
            from pathlib import Path

            # Look for message files in the IMAP directory
            base_path = Path(mailbox_item.full_path)

            if not base_path.is_dir():
                return occurrences

            # Walk through all .eml and message files
            for msg_file in base_path.rglob('*'):

                if self.cancel_requested:
                    break

                # Skip directories and non-message files
                if msg_file.is_dir() or msg_file.name.startswith('.'):
                    continue

                try:
                    # Try to parse as email message
                    from email import message_from_binary_file

                    with open(msg_file, 'rb') as f:
                        message = message_from_binary_file(f)

                    # Skip if not a valid email message
                    if not message.get('From') and not message.get('To'):
                        continue

                    occurrences.extend(
                        self.extract_message_addresses(
                            mailbox_item,
                            str(msg_file),
                            message,
                        )
                    )

                except Exception:
                    continue

        except Exception:
            pass

        return occurrences

    # ------------------------------------------------------

    def extract_message_addresses(self, mailbox_item, key, message):

        occurrences = []
        body_text = ""

        for header_name, direction in [
            ("From", "Inbound"),
            ("Reply-To", "Inbound"),
            ("To", "Outbound"),
            ("Cc", "Outbound"),
            ("Bcc", "Outbound"),
        ]:

            raw_value = message.get(header_name, "")

            if not raw_value:

                continue

            # Only the sender's own message body is captured. Attributing
            # the sender's signature to every recipient would put wrong
            # phone/company/VAT guesses on people who never wrote them.
            if header_name == "From" and not body_text:

                body_text = self._get_message_body(message)

            for value in raw_value.split(","):

                normalized = self.normalizer.normalize(value)

                if not normalized["email"]:

                    continue

                occurrences.append(
                    AddressOccurrence(
                        normalized_email=normalized["email"],
                        original_email=normalized["original"],
                        display_name=normalized["display_name"],
                        source_mailbox=mailbox_item.display_name,
                        source_folder=mailbox_item.relative_path,
                        source_message_id=message.get("Message-ID", str(key)),
                        message_date=message.get("Date", ""),
                        message_subject=message.get("Subject", ""),
                        header_source=header_name,
                        direction=direction,
                        body_text=body_text if header_name == "From" else "",
                    )
                )

        return occurrences

    # ------------------------------------------------------

    def _get_message_body(self, message):

        if message.is_multipart():

            for part in message.walk():

                if part.get_content_type() != "text/plain":

                    continue

                if part.get_content_disposition() == "attachment":

                    continue

                return self._decode_payload(part)

            return ""

        return self._decode_payload(message)

    # ------------------------------------------------------

    def _decode_payload(self, part):

        try:

            payload = part.get_payload(decode=True)

        except Exception:

            return ""

        if not payload:

            return ""

        charset = part.get_content_charset() or "utf-8"

        try:

            return payload.decode(charset, errors="ignore")

        except Exception:

            return payload.decode("utf-8", errors="ignore")

    # ------------------------------------------------------

    def aggregate(self, occurrences):

        grouped = {}

        for occurrence in occurrences:

            grouped.setdefault(
                occurrence.normalized_email,
                [],
            )
            grouped[occurrence.normalized_email].append(occurrence)
            self.repository.save_occurrence(occurrence)

        candidates = []

        for email, group in grouped.items():

            candidates.append(self.create_candidate(email, group))

        return candidates

    # ------------------------------------------------------

    def create_candidate(self, email, occurrences):

        first = occurrences[0]
        dates = [
            self.normalize_date(occurrence.message_date)
            for occurrence in occurrences
            if self.normalize_date(occurrence.message_date)
        ]
        header_types = sorted({occurrence.header_source for occurrence in occurrences})
        message_ids = sorted({occurrence.source_message_id for occurrence in occurrences})
        mailboxes = sorted({occurrence.source_mailbox for occurrence in occurrences})
        folders = sorted({occurrence.source_folder for occurrence in occurrences})

        classification = self.validator.validate(email)
        reason = ""

        if classification == AddressClassification.VALID:

            reason = self.automated_classifier.classify(email)

            if reason:

                classification = AddressClassification.AUTOMATED

            elif self.ignore_list.is_ignored(email):

                classification = AddressClassification.IGNORED
                reason = "Matched Ignore List"

            else:

                match = self.crm_matcher.match(email)

                if match.status == "Exact Existing Contact Match":

                    classification = AddressClassification.EXISTING

                elif match.status == "Multiple Existing Matches":

                    classification = AddressClassification.EXISTING

                else:

                    classification = AddressClassification.NEW

        review_status = self.get_initial_review_status(classification, email)
        match_status = self.crm_matcher.match(email).status

        signature_source = next(
            (occurrence for occurrence in occurrences if occurrence.body_text),
            None,
        )

        extracted = self.signature_extractor.extract(
            signature_source.body_text if signature_source else ""
        )

        return ContactCandidate(
            normalized_email=email,
            original_email=first.original_email,
            display_name=first.display_name,
            classification=classification,
            classification_reason=reason,
            existing_match_status=match_status,
            review_status=review_status,
            ignore_status="Ignored" if classification == AddressClassification.IGNORED else "Active",
            occurrences=len(occurrences),
            first_seen=min(dates) if dates else "",
            last_seen=max(dates) if dates else "",
            inbound_count=len([item for item in occurrences if item.direction == "Inbound"]),
            outbound_count=len([item for item in occurrences if item.direction == "Outbound"]),
            source_mailbox="; ".join(mailboxes),
            source_folder="; ".join(folders),
            source_header_types="; ".join(header_types),
            source_message_ids="; ".join(message_ids),
            imported=False,
            extracted_phone=extracted["phone"],
            extracted_website=extracted["website"],
            extracted_vat_number=extracted["vat_number"],
            extracted_company_name=extracted["company_name"],
        )

    # ------------------------------------------------------

    def get_initial_review_status(self, classification, email):

        if classification == AddressClassification.EXISTING:

            match = self.crm_matcher.match(email)

            if match.status == "Multiple Existing Matches":

                return REVIEW_NEEDS_ATTENTION

            return REVIEW_EXISTING

        if classification == AddressClassification.NEW:

            return REVIEW_PENDING

        if classification == AddressClassification.IGNORED:

            return REVIEW_IGNORED

        return REVIEW_NEEDS_ATTENTION

    # ------------------------------------------------------

    def normalize_date(self, value):

        try:

            return parsedate_to_datetime(str(value or "")).isoformat()

        except Exception:

            return str(value or "").strip()

    # ------------------------------------------------------

    def get_statistics(self, candidates):

        all_message_ids = set()
        for candidate in candidates:
            ids = [msg_id.strip() for msg_id in candidate.source_message_ids.split(";") if msg_id.strip()]
            all_message_ids.update(ids)

        return {
            "messages scanned": len(all_message_ids),
            "unique email addresses discovered": len(candidates),
            "valid candidates": len([c for c in candidates if c.classification == AddressClassification.NEW]),
            "invalid addresses": len([c for c in candidates if c.classification == AddressClassification.INVALID]),
            "automated or system addresses": len([c for c in candidates if c.classification == AddressClassification.AUTOMATED]),
            "existing CRM matches": len([c for c in candidates if c.classification == AddressClassification.EXISTING]),
            "new candidates": len([c for c in candidates if c.classification == AddressClassification.NEW]),
            "ignored addresses": len([c for c in candidates if c.classification == AddressClassification.IGNORED]),
            "pending review": len([c for c in candidates if c.review_status == REVIEW_PENDING]),
            "approved": len([c for c in candidates if c.review_status == REVIEW_APPROVED]),
            "rejected": len([c for c in candidates if c.review_status == REVIEW_REJECTED]),
            "imported": len([c for c in candidates if c.review_status == REVIEW_IMPORTED]),
            "candidates needing attention": len([c for c in candidates if c.review_status == REVIEW_NEEDS_ATTENTION]),
        }

    # ------------------------------------------------------

    def export_candidates(self, candidates, filename):

        with open(filename, "w", newline="", encoding="utf-8") as file:

            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "Email Address",
                    "Display Name",
                    "Classification",
                    "Classification Reason",
                    "Existing CRM Match",
                    "Occurrences",
                    "First Seen",
                    "Last Seen",
                    "Source Mailbox",
                    "Direction",
                    "Review Status",
                ],
            )

            writer.writeheader()

            for candidate in candidates:

                direction = "Inbound" if candidate.inbound_count >= candidate.outbound_count else "Outbound"

                writer.writerow(
                    {
                        "Email Address": candidate.normalized_email,
                        "Display Name": candidate.display_name,
                        "Classification": candidate.classification,
                        "Classification Reason": candidate.classification_reason,
                        "Existing CRM Match": candidate.existing_match_status,
                        "Occurrences": candidate.occurrences,
                        "First Seen": candidate.first_seen,
                        "Last Seen": candidate.last_seen,
                        "Source Mailbox": candidate.source_mailbox,
                        "Direction": direction,
                        "Review Status": candidate.review_status,
                    }
                )


class CRMImportCoordinator:

    def __init__(self, database, crm_service=None):

        self.database = database
        self.crm_service = crm_service

    # ------------------------------------------------------

    def import_candidate(self, candidate, action, payload=None):

        payload = payload or {}
        import_date = datetime.now().isoformat(timespec="seconds")

        try:

            if candidate.review_status != REVIEW_APPROVED:

                raise ValueError("Only approved candidates can be imported.")

            if action == "Skip":

                self.record_history(candidate, import_date, action, "", "", "Skipped", "")

                return "Skipped"

            if self.crm_service is None:

                raise ValueError("CRM service is unavailable.")

            result = self.crm_service.import_contact(candidate, action, payload)

            self.record_history(
                candidate,
                import_date,
                action,
                result.get("customer_id", ""),
                result.get("contact_id", ""),
                "Imported",
                "",
            )

            return "Imported"

        except Exception as error:

            self.record_history(
                candidate,
                import_date,
                action,
                "",
                "",
                "Failed",
                str(error),
            )

            return "Failed"

    # ------------------------------------------------------

    def record_history(
        self,
        candidate,
        import_date,
        action,
        customer_id,
        contact_id,
        status,
        error_message,
    ):

        with self.database.connect() as connection:

            connection.execute(
                """
                INSERT INTO communication_import_history (
                    normalized_email,
                    import_date,
                    selected_action,
                    crm_customer_id,
                    crm_contact_id,
                    import_status,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.normalized_email,
                    import_date,
                    action,
                    customer_id,
                    contact_id,
                    status,
                    error_message,
                ),
            )
