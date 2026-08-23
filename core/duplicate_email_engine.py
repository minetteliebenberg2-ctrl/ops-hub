# ==========================================================
# FC Utilities - Duplicate Email Engine
# ----------------------------------------------------------
# Purpose:
# Analyse email messages for duplicates and cleanup candidates.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path
import mailbox

from core.duplicate_email_report import DuplicateEmailReport
from core.email_hash import EmailHash
from core.mail_scanner import MailScanner
from core.message_classifier import MessageClassifier
from core.message_comparison import MessageComparison


@dataclass
class DeleteFailure:

    message: object
    reason: str


@dataclass
class DuplicateEmailMessage:

    id: str = ""
    mailbox_key: object = ""
    mailbox_name: str = ""
    mailbox_path: str = ""
    message_id: str = ""
    sender: str = ""
    recipient: str = ""
    subject: str = ""
    date: str = ""
    message_size: int = 0
    classification: str = "Normal"
    has_attachment: bool = False
    attachment_count: int = 0
    attachment_size: int = 0
    spam_flag: str = ""
    spam_status: str = ""
    deletion_candidate: bool = False
    deleted: bool = False
    ignored: bool = False


class DuplicateEmailEngine:

    def __init__(self):

        self.protected_accounts = {
            "minette@facilitiesco.com",
            "sales@facilitiesco.com",
        }

        self.mail_scanner = MailScanner()
        self.hash = EmailHash()
        self.comparison = MessageComparison()
        self.classifier = MessageClassifier(self.protected_accounts)
        self.report = DuplicateEmailReport()

        self.mailboxes = []
        self.messages = []
        self.cancel_requested = False
        self.whitelisted_senders = set()
        self.whitelisted_domains = set()
        self.deleted_messages = []

    # ------------------------------------------------------

    def scan_mailboxes(self):

        profiles = self.mail_scanner.find_profiles()
        self.mail_scanner.read_accounts()

        active_profile = None

        for profile in profiles:

            if profile["active"]:

                active_profile = profile
                break

        if active_profile is None:

            return []

        self.mailboxes = self.mail_scanner.scan(active_profile)

        return self.mailboxes

    # ------------------------------------------------------

    def scan_messages(self, mailboxes, progress_callback=None):

        self.cancel_requested = False
        self.messages = []

        total_mailboxes = len(mailboxes)

        for index, mailbox_item in enumerate(mailboxes):

            if self.cancel_requested:

                break

            if progress_callback is not None:

                progress_callback(
                    f"Scanning {mailbox_item.display_name}",
                    index + 1,
                    total_mailboxes,
                )

            self.messages.extend(self.read_mailbox(mailbox_item))

        self.classify_messages()

        return {
            "messages": self.messages,
            "statistics": self.get_statistics(),
            "cancelled": self.cancel_requested,
        }

    # ------------------------------------------------------

    def cancel_scan(self):

        self.cancel_requested = True

    # ------------------------------------------------------

    def read_mailbox(self, mailbox_item):

        results = []
        mbox = None

        try:

            mbox = mailbox.mbox(mailbox_item.full_path)

            for key in mbox.iterkeys():

                if self.cancel_requested:

                    break

                try:

                    mail = mbox.get_message(key)

                    results.append(
                        self.create_message_record(
                            mailbox_item,
                            key,
                            mail,
                        )
                    )

                except Exception:

                    continue

        except Exception:

            return results

        finally:

            if mbox is not None:

                try:

                    mbox.close()

                except Exception:

                    pass

        return results

    # ------------------------------------------------------

    def create_message_record(self, mailbox_item, key, mail):

        _, sender = parseaddr(mail.get("From", ""))
        _, recipient = parseaddr(mail.get("To", ""))

        attachment_info = self.get_attachment_info(mail)

        message = DuplicateEmailMessage(
            id=f"{mailbox_item.full_path}:{key}",
            mailbox_key=key,
            mailbox_name=mailbox_item.display_name,
            mailbox_path=mailbox_item.full_path,
            message_id=mail.get("Message-ID", ""),
            sender=sender.lower().strip(),
            recipient=recipient.lower().strip(),
            subject=mail.get("Subject", ""),
            date=mail.get("Date", ""),
            message_size=self.get_message_size(mail),
            has_attachment=attachment_info["count"] > 0,
            attachment_count=attachment_info["count"],
            attachment_size=attachment_info["size"],
            spam_flag=mail.get("X-Spam-Flag", ""),
            spam_status=self.get_spam_status(mail),
        )

        message.classification = self.classifier.classify(message)

        return message

    # ------------------------------------------------------

    def get_message_size(self, mail):

        try:

            return len(mail.as_bytes())

        except Exception:

            return 0

    # ------------------------------------------------------

    def get_spam_status(self, mail):

        headers = [
            mail.get("X-Spam-Status", ""),
            mail.get("Spam-Status", ""),
            mail.get("X-Spam-Flag", ""),
        ]

        return " ".join(
            header
            for header in headers
            if header
        )

    # ------------------------------------------------------

    def get_attachment_info(self, mail):

        count = 0
        size = 0

        if not mail.is_multipart():

            return {
                "count": 0,
                "size": 0,
            }

        for part in mail.walk():

            disposition = part.get_content_disposition()

            if disposition != "attachment":

                continue

            count += 1

            try:

                payload = part.get_payload(decode=True)

                if payload:

                    size += len(payload)

            except Exception:

                continue

        return {
            "count": count,
            "size": size,
        }

    # ------------------------------------------------------

    def classify_messages(self):

        exact_groups = {}

        for message in self.messages:

            message_id = self.hash.normalize_message_id(message.message_id)

            if message_id:

                exact_groups.setdefault(
                    message_id,
                    [],
                )
                exact_groups[message_id].append(message)

        for group in exact_groups.values():

            if len(group) < 2:

                continue

            for message in group:

                message.classification = MessageClassifier.EXACT_DUPLICATE

            self.classifier.apply_duplicate_classification(group)

        probable_groups = self.find_probable_duplicates()

        for group in probable_groups:

            for message in group:

                if message.classification == MessageClassifier.NORMAL:

                    message.classification = MessageClassifier.PROBABLE_DUPLICATE

            self.classifier.apply_duplicate_classification(group)

        for message in self.messages:

            if message.classification != MessageClassifier.NORMAL:

                continue

            message.classification = self.classifier.classify(message)

    # ------------------------------------------------------

    def find_probable_duplicates(self):

        groups = []
        used = set()
        buckets = self.get_probable_duplicate_buckets()

        for bucket in buckets:

            if len(bucket) < 2:

                continue

            for index, first in bucket:

                if index in used:

                    continue

                group = [first]

                for second_index, second in bucket:

                    if second_index <= index or second_index in used:

                        continue

                    if self.comparison.is_probable_duplicate(
                        first,
                        second,
                    ):

                        group.append(second)
                        used.add(second_index)

                if len(group) > 1:

                    groups.append(group)
                    used.add(index)

        return groups

    # ------------------------------------------------------

    def get_probable_duplicate_buckets(self):

        buckets = {}

        for index, message in enumerate(self.messages):

            subject = self.comparison.normalize_text(message.subject)

            if not subject:

                continue

            buckets.setdefault(
                subject,
                [],
            )
            buckets[subject].append(
                (
                    index,
                    message,
                )
            )

        return buckets.values()

    # ------------------------------------------------------

    def get_cleanup_candidates(self, classification=None, include_attachments=False):

        candidates = []

        for message in self.messages:

            if message.deleted or message.ignored:

                continue

            if classification and message.classification != classification:

                continue

            if self.is_whitelisted(message):

                continue

            if self.is_duplicate_classification(message) and not message.deletion_candidate:

                continue

            if include_attachments:

                if message.classification == MessageClassifier.PROTECTED_DUPLICATE:

                    continue

            elif not self.classifier.can_bulk_delete(message):

                continue

            if message.classification == MessageClassifier.NORMAL:

                continue

            candidates.append(message)

        return candidates

    # ------------------------------------------------------

    def is_duplicate_classification(self, message):

        return message.classification in {
            MessageClassifier.EXACT_DUPLICATE,
            MessageClassifier.PROBABLE_DUPLICATE,
            MessageClassifier.PROTECTED_DUPLICATE,
        }

    # ------------------------------------------------------

    def delete_messages(self, messages):

        deleted = []
        failures = []
        by_mailbox = {}

        for message in messages:

            if message.deleted:

                continue

            by_mailbox.setdefault(
                message.mailbox_path,
                [],
            )
            by_mailbox[message.mailbox_path].append(message)

        for mailbox_path, mailbox_messages in by_mailbox.items():

            if not Path(mailbox_path).exists():

                for message in mailbox_messages:

                    failures.append(
                        DeleteFailure(
                            message=message,
                            reason=f"Mailbox file not found: {mailbox_path}",
                        )
                    )

                continue

            try:

                mbox = mailbox.mbox(mailbox_path, create=False)
                mbox.lock()

            except Exception as error:

                for message in mailbox_messages:

                    failures.append(
                        DeleteFailure(
                            message=message,
                            reason=(
                                "Could not open or lock mailbox: "
                                f"{type(error).__name__}: {error}"
                            ),
                        )
                    )

                continue

            batch_deleted = []

            try:

                for message in mailbox_messages:

                    try:

                        del mbox[message.mailbox_key]
                        batch_deleted.append(message)

                    except Exception as error:

                        failures.append(
                            DeleteFailure(
                                message=message,
                                reason=f"{type(error).__name__}: {error}",
                            )
                        )

                mbox.flush()

            except Exception as error:

                for message in batch_deleted:

                    failures.append(
                        DeleteFailure(
                            message=message,
                            reason=(
                                "Mailbox flush failed: "
                                f"{type(error).__name__}: {error}"
                            ),
                        )
                    )

                batch_deleted = []

            finally:

                try:

                    mbox.unlock()

                except Exception:

                    pass

                try:

                    mbox.close()

                except Exception:

                    pass

            for message in batch_deleted:

                message.deleted = True
                deleted.append(message)

        self.deleted_messages.extend(deleted)
        self.report.log_cleanup(deleted)

        return {
            "deleted": deleted,
            "failures": failures,
        }

    # ------------------------------------------------------

    def ignore_messages(self, messages):

        for message in messages:

            message.ignored = True

    # ------------------------------------------------------

    def whitelist_sender(self, messages):

        for message in messages:

            if message.sender:

                self.whitelisted_senders.add(message.sender.lower().strip())

    # ------------------------------------------------------

    def whitelist_domain(self, messages):

        for message in messages:

            domain = self.get_domain(message.sender)

            if domain:

                self.whitelisted_domains.add(domain)

    # ------------------------------------------------------

    def is_whitelisted(self, message):

        sender = message.sender.lower().strip()
        domain = self.get_domain(sender)

        return sender in self.whitelisted_senders or domain in self.whitelisted_domains

    # ------------------------------------------------------

    def get_domain(self, email):

        if "@" not in email:

            return ""

        return email.split("@", 1)[1].lower().strip()

    # ------------------------------------------------------

    def get_statistics(self):

        stats = {
            "Messages Scanned": len(self.messages),
            "Exact Duplicates": 0,
            "Probable Duplicates": 0,
            "Protected Duplicates": 0,
            "Read Receipts": 0,
            "Delivery Receipts": 0,
            "Undeliverable Messages": 0,
            "Bounce Messages": 0,
            "Automatic Replies": 0,
            "Out of Office Replies": 0,
            "Junk / Spam": 0,
            "Messages with Attachments": 0,
            "Deleted Messages": len(self.deleted_messages),
            "Recoverable Mailbox Space": 0,
        }

        classification_map = {
            MessageClassifier.EXACT_DUPLICATE: "Exact Duplicates",
            MessageClassifier.PROBABLE_DUPLICATE: "Probable Duplicates",
            MessageClassifier.PROTECTED_DUPLICATE: "Protected Duplicates",
            MessageClassifier.READ_RECEIPT: "Read Receipts",
            MessageClassifier.DELIVERY_RECEIPT: "Delivery Receipts",
            MessageClassifier.UNDELIVERABLE_MAIL: "Undeliverable Messages",
            MessageClassifier.BOUNCE_MESSAGE: "Bounce Messages",
            MessageClassifier.AUTOMATIC_REPLY: "Automatic Replies",
            MessageClassifier.OUT_OF_OFFICE_REPLY: "Out of Office Replies",
            MessageClassifier.JUNK_SPAM: "Junk / Spam",
        }

        for message in self.messages:

            if message.classification in classification_map:

                stats[classification_map[message.classification]] += 1

            if message.has_attachment:

                stats["Messages with Attachments"] += 1

            if not message.deleted and self.classifier.can_bulk_delete(message):

                stats["Recoverable Mailbox Space"] += message.message_size

        return stats

    # ------------------------------------------------------

    def export_duplicate_csv(self, filename):

        self.report.export_duplicate_csv(
            self.messages,
            filename,
        )

    # ------------------------------------------------------

    def export_cleanup_report(self, filename):

        self.report.export_cleanup_report(
            self.messages,
            self.get_statistics(),
            filename,
        )

    # ------------------------------------------------------

    def export_summary_report(self, filename):

        self.report.export_summary_report(
            self.get_statistics(),
            filename,
        )
