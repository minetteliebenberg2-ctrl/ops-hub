# ==========================================================
# FC Utilities - Duplicate Email Report
# ----------------------------------------------------------
# Purpose:
# Export duplicate email cleanup reports.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import csv
from datetime import datetime
from pathlib import Path


def format_size(size):

    try:

        value = float(size or 0)

    except Exception:

        value = 0.0

    units = [
        "B",
        "KB",
        "MB",
        "GB",
    ]

    unit_index = 0

    while value >= 1024 and unit_index < len(units) - 1:

        value = value / 1024
        unit_index += 1

    if unit_index == 0:

        return f"{int(value)} {units[unit_index]}"

    return f"{value:.1f} {units[unit_index]}"


class DuplicateEmailReport:

    def export_duplicate_csv(self, messages, filename):

        self.export_messages(messages, filename)

    # ------------------------------------------------------

    def export_messages(self, messages, filename):

        with open(filename, "w", newline="", encoding="utf-8") as file:

            writer = csv.DictWriter(
                file,
                fieldnames=self.get_message_fieldnames(),
            )

            writer.writeheader()

            for message in messages:

                writer.writerow(self.message_to_row(message))

    # ------------------------------------------------------

    def export_cleanup_report(self, messages, statistics, filename):

        lines = [
            "FC Utilities - Duplicate Email & Mail Cleanup Report",
            f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Statistics",
        ]

        for name, value in statistics.items():

            lines.append(f"{name}: {self.format_statistic(name, value)}")

        lines.append("")
        lines.append("Messages")

        for message in messages:

            lines.append(
                (
                    f"{message.classification} | {message.mailbox_name} | "
                    f"{message.sender} -> {message.recipient} | "
                    f"{message.subject}"
                )
            )

        with open(filename, "w", encoding="utf-8") as file:

            file.write("\n".join(lines))

    # ------------------------------------------------------

    def export_summary_report(self, statistics, filename):

        with open(filename, "w", encoding="utf-8") as file:

            file.write("FC Utilities - Duplicate Email Summary Report\n")
            file.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for name, value in statistics.items():

                file.write(f"{name}: {self.format_statistic(name, value)}\n")

    # ------------------------------------------------------

    def log_cleanup(self, messages, log_folder="logs"):

        folder = Path(log_folder)

        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = folder / (
            "duplicate_email_cleanup_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )

        with open(filename, "w", encoding="utf-8") as file:

            file.write("FC Utilities - Duplicate Email Cleanup Log\n")

            for message in messages:

                file.write(
                    (
                        f"{message.mailbox_path} | {message.mailbox_key} | "
                        f"{message.classification} | {message.subject}\n"
                    )
                )

        return str(filename)

    # ------------------------------------------------------

    def get_message_fieldnames(self):

        return [
            "Classification",
            "Mailbox",
            "Sender",
            "Recipient",
            "Subject",
            "Date",
            "Message Size",
            "Has Attachment",
            "Attachment Count",
            "Attachment Size",
            "Message-ID",
            "Deletion Candidate",
        ]

    # ------------------------------------------------------

    def message_to_row(self, message):

        return {
            "Classification": message.classification,
            "Mailbox": message.mailbox_name,
            "Sender": message.sender,
            "Recipient": message.recipient,
            "Subject": message.subject,
            "Date": message.date,
            "Message Size": format_size(message.message_size),
            "Has Attachment": "Yes" if message.has_attachment else "No",
            "Attachment Count": message.attachment_count,
            "Attachment Size": format_size(message.attachment_size),
            "Message-ID": message.message_id,
            "Deletion Candidate": "Yes" if message.deletion_candidate else "No",
        }

    # ------------------------------------------------------

    def format_statistic(self, name, value):

        if name == "Recoverable Mailbox Space":

            return format_size(value)

        return value
