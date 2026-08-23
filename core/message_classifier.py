# ==========================================================
# FC Utilities - Message Classifier
# ----------------------------------------------------------
# Purpose:
# Classify duplicate and system-generated email messages.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================


class MessageClassifier:

    EXACT_DUPLICATE = "Exact Duplicate"
    PROBABLE_DUPLICATE = "Probable Duplicate"
    READ_RECEIPT = "Read Receipt"
    DELIVERY_RECEIPT = "Delivery Receipt"
    UNDELIVERABLE_MAIL = "Undeliverable Mail"
    BOUNCE_MESSAGE = "Bounce Message"
    AUTOMATIC_REPLY = "Automatic Reply"
    OUT_OF_OFFICE_REPLY = "Out of Office Reply"
    PROTECTED_DUPLICATE = "Protected Duplicate"
    JUNK_SPAM = "Junk / Spam"
    NORMAL = "Normal"

    def __init__(self, protected_accounts=None):

        self.protected_accounts = {
            account.lower().strip()
            for account in (protected_accounts or [])
        }

        self.rules = [
            (
                self.OUT_OF_OFFICE_REPLY,
                [
                    "out of office",
                    "out-of-office",
                    "automatic reply: out of office",
                ],
            ),
            (
                self.AUTOMATIC_REPLY,
                [
                    "automatic reply",
                    "auto reply",
                    "autoreply",
                    "auto-response",
                    "autoresponder",
                ],
            ),
            (
                self.READ_RECEIPT,
                [
                    "read receipt",
                    "read:",
                    "return receipt",
                ],
            ),
            (
                self.DELIVERY_RECEIPT,
                [
                    "delivery receipt",
                    "delivered:",
                    "delivery status notification",
                ],
            ),
            (
                self.UNDELIVERABLE_MAIL,
                [
                    "undeliverable",
                    "undelivered",
                    "delivery failed",
                    "delivery failure",
                ],
            ),
            (
                self.BOUNCE_MESSAGE,
                [
                    "mailer-daemon",
                    "postmaster",
                    "failure notice",
                    "returned mail",
                    "mail delivery subsystem",
                ],
            ),
        ]

    # ------------------------------------------------------

    def classify(self, message):

        if self.is_junk_spam(message):

            return self.JUNK_SPAM

        text = " ".join(
            [
                message.subject,
                message.sender,
                message.recipient,
                message.message_id,
            ]
        ).lower()

        for classification, keywords in self.rules:

            for keyword in keywords:

                if keyword in text:

                    return classification

        return self.NORMAL

    # ------------------------------------------------------

    def is_junk_spam(self, message):

        mailbox_name = str(message.mailbox_name or "").lower()

        if "junk" in mailbox_name or "spam" in mailbox_name:

            return True

        spam_flag = str(getattr(message, "spam_flag", "") or "").lower().strip()

        if spam_flag == "yes":

            return True

        spam_status = str(getattr(message, "spam_status", "") or "").lower()

        return (
            spam_status.startswith("yes")
            or "status: yes" in spam_status
            or "is spam" in spam_status
        )

    # ------------------------------------------------------

    def apply_duplicate_classification(self, group):

        protected = [
            message
            for message in group
            if self.is_protected(message)
        ]

        if len(protected) == len(group):

            for message in group:

                message.classification = self.PROTECTED_DUPLICATE
                message.deletion_candidate = False

            return

        for index, message in enumerate(group):

            if self.is_protected(message):

                message.deletion_candidate = False

            elif index > 0 or protected:

                message.deletion_candidate = True

    # ------------------------------------------------------

    def is_protected(self, message):

        sender = message.sender.lower().strip()
        recipient = message.recipient.lower().strip()

        return (
            sender in self.protected_accounts
            or recipient in self.protected_accounts
        )

    # ------------------------------------------------------

    def can_bulk_delete(self, message):

        if message.classification == self.PROTECTED_DUPLICATE:

            return False

        if message.classification in {
            self.EXACT_DUPLICATE,
            self.PROBABLE_DUPLICATE,
        } and not message.deletion_candidate:

            return False

        if message.has_attachment:

            return False

        return True
