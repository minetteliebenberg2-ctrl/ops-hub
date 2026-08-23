# ==========================================================
# FC Utilities - Duplicate Email Window
# ----------------------------------------------------------
# Purpose:
# User interface for Duplicate Email & Mail Cleanup.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

from core.duplicate_email_engine import DuplicateEmailEngine
from core.duplicate_email_report import format_size
from core.message_classifier import MessageClassifier


def _reflow_toolbar(toolbar, columns=3):
    """Arrange a button toolbar into small-screen-safe rows."""
    buttons = toolbar.winfo_children()

    for button in buttons:
        button.pack_forget()

    for index, button in enumerate(buttons):
        button.grid(
            row=index // columns,
            column=index % columns,
            padx=4,
            pady=4,
            sticky="ew",
        )
    for column in range(columns):
        toolbar.grid_columnconfigure(column, weight=1)


class DuplicateEmailWindow(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)

        self.engine = DuplicateEmailEngine()
        self.mailboxes = []
        self.messages = []
        self.visible_messages = []
        self.sort_column = ""
        self.sort_reverse = False

        ctk.CTkLabel(
            self,
            text="Duplicate Email & Mail Cleanup",
            font=("Segoe UI", 22, "bold"),
        ).pack(pady=(0, 15))

        self.status_label = ctk.CTkLabel(
            self,
            text="Scan mailboxes to begin.",
        )

        self.status_label.pack(pady=(0, 10))

        mailbox_buttons = ctk.CTkFrame(self)

        mailbox_buttons.pack(pady=(0, 10))

        ctk.CTkButton(
            mailbox_buttons,
            text="Load Mailboxes",
            command=self.load_mailboxes,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            mailbox_buttons,
            text="Scan Selected Mailboxes",
            command=self.scan_selected_mailboxes,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            mailbox_buttons,
            text="Scan All Mailboxes",
            command=self.scan_all_mailboxes,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            mailbox_buttons,
            text="Cancel Scan",
            command=self.cancel_scan,
        ).pack(side="left", padx=5)

        mailbox_table_frame = ctk.CTkFrame(self)

        mailbox_table_frame.pack(
            fill="x",
            padx=20,
            pady=(0, 15),
        )

        self.mailbox_table = ttk.Treeview(
            mailbox_table_frame,
            columns=("Size",),
            show="tree headings",
            selectmode="extended",
            height=8,
        )

        self.mailbox_table.heading(
            "#0",
            text="Email Account / Mailbox",
        )
        self.mailbox_table.heading(
            "Size",
            text="MB",
        )

        self.mailbox_table.column(
            "#0",
            width=650,
            stretch=True,
        )
        self.mailbox_table.column(
            "Size",
            width=120,
            anchor="e",
            stretch=False,
        )

        mailbox_scrollbar = ttk.Scrollbar(
            mailbox_table_frame,
            orient="vertical",
            command=self.mailbox_table.yview,
        )
        mailbox_horizontal_scrollbar = ttk.Scrollbar(
            mailbox_table_frame,
            orient="horizontal",
            command=self.mailbox_table.xview,
        )

        self.mailbox_table.configure(
            yscrollcommand=mailbox_scrollbar.set,
            xscrollcommand=mailbox_horizontal_scrollbar.set,
        )
        self.mailbox_table.grid(row=0, column=0, sticky="nsew")
        mailbox_scrollbar.grid(row=0, column=1, sticky="ns")
        mailbox_horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        mailbox_table_frame.grid_columnconfigure(0, weight=1)

        self.mailbox_table.bind("<MouseWheel>", self.scroll_mailbox_table)
        self.mailbox_table.bind("<Button-4>", self.scroll_mailbox_table)
        self.mailbox_table.bind("<Button-5>", self.scroll_mailbox_table)

        selection_buttons = ctk.CTkFrame(self)

        selection_buttons.pack(pady=(0, 8))

        ctk.CTkButton(
            selection_buttons,
            text="Select All",
            width=130,
            command=self.select_all_results,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            selection_buttons,
            text="Clear Selection",
            width=130,
            command=self.clear_result_selection,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            selection_buttons,
            text="Invert Selection",
            width=130,
            command=self.invert_result_selection,
        ).pack(side="left", padx=4)

        table_frame = ctk.CTkFrame(self)

        table_frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 10),
        )

        self.result_columns = (
            "Subject",
            "Sender",
            "Recipient",
            "Date",
            "Message Size",
            "Mailbox",
            "Classification",
            "Has Attachment",
            "Attachment Count",
            "Attachment Size",
        )

        self.result_table = ttk.Treeview(
            table_frame,
            columns=self.result_columns,
            show="headings",
            selectmode="extended",
            height=14,
        )

        for column in self.result_columns:

            self.result_table.heading(
                column,
                text=column,
                command=lambda c=column: self.sort_results(c),
            )

        self.result_table.column("Subject", width=260, stretch=True)
        self.result_table.column("Sender", width=180, stretch=True)
        self.result_table.column("Recipient", width=180, stretch=True)
        self.result_table.column("Date", width=160, stretch=False)
        self.result_table.column("Message Size", width=110, anchor="e", stretch=False)
        self.result_table.column("Mailbox", width=180, stretch=True)
        self.result_table.column("Classification", width=160, stretch=False)
        self.result_table.column("Has Attachment", width=110, stretch=False)
        self.result_table.column(
            "Attachment Count",
            width=120,
            anchor="e",
            stretch=False,
        )
        self.result_table.column(
            "Attachment Size",
            width=120,
            anchor="e",
            stretch=False,
        )

        result_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.result_table.yview,
        )
        result_horizontal_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.result_table.xview,
        )

        self.result_table.configure(
            yscrollcommand=result_scrollbar.set,
            xscrollcommand=result_horizontal_scrollbar.set,
        )
        self.result_table.grid(row=0, column=0, sticky="nsew")
        result_scrollbar.grid(row=0, column=1, sticky="ns")
        result_horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        cleanup_buttons = ctk.CTkFrame(self)

        cleanup_buttons.pack(pady=(0, 8))

        ctk.CTkButton(
            cleanup_buttons,
            text="Delete Selected",
            width=130,
            command=self.delete_selected,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            cleanup_buttons,
            text="Exact Duplicates",
            width=130,
            command=lambda: self.delete_all_by_classification(
                MessageClassifier.EXACT_DUPLICATE
            ),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            cleanup_buttons,
            text="Probable Duplicates",
            width=145,
            command=lambda: self.delete_all_by_classification(
                MessageClassifier.PROBABLE_DUPLICATE
            ),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            cleanup_buttons,
            text="Read Receipts",
            width=125,
            command=lambda: self.delete_all_by_classification(
                MessageClassifier.READ_RECEIPT
            ),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            cleanup_buttons,
            text="Delivery Receipts",
            width=140,
            command=lambda: self.delete_all_by_classification(
                MessageClassifier.DELIVERY_RECEIPT
            ),
        ).pack(side="left", padx=4)

        _reflow_toolbar(cleanup_buttons)

        cleanup_buttons_2 = ctk.CTkFrame(self)

        cleanup_buttons_2.pack(pady=(0, 8))

        ctk.CTkButton(
            cleanup_buttons_2,
            text="Undeliverable",
            width=130,
            command=lambda: self.delete_all_by_classification(
                MessageClassifier.UNDELIVERABLE_MAIL
            ),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            cleanup_buttons_2,
            text="Bounce Messages",
            width=140,
            command=lambda: self.delete_all_by_classification(
                MessageClassifier.BOUNCE_MESSAGE
            ),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            cleanup_buttons_2,
            text="Automatic Replies",
            width=145,
            command=lambda: self.delete_all_by_classification(
                MessageClassifier.AUTOMATIC_REPLY
            ),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            cleanup_buttons_2,
            text="Out of Office",
            width=130,
            command=lambda: self.delete_all_by_classification(
                MessageClassifier.OUT_OF_OFFICE_REPLY
            ),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            cleanup_buttons_2,
            text="Junk / Spam",
            width=120,
            command=lambda: self.delete_all_by_classification(
                MessageClassifier.JUNK_SPAM
            ),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            cleanup_buttons_2,
            text="Refresh Scan",
            width=120,
            command=self.refresh_scan,
        ).pack(side="left", padx=4)

        _reflow_toolbar(cleanup_buttons_2)

        workflow_buttons = ctk.CTkFrame(self)

        workflow_buttons.pack(pady=(0, 8))

        ctk.CTkButton(
            workflow_buttons,
            text="Ignore Selected",
            width=145,
            command=self.ignore_selected,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            workflow_buttons,
            text="Whitelist Sender",
            width=145,
            command=self.whitelist_sender,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            workflow_buttons,
            text="Whitelist Domain",
            width=145,
            command=self.whitelist_domain,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            workflow_buttons,
            text="Duplicate CSV",
            width=145,
            command=self.export_duplicate_csv,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            workflow_buttons,
            text="Cleanup Report",
            width=145,
            command=self.export_cleanup_report,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            workflow_buttons,
            text="Summary Report",
            width=145,
            command=self.export_summary_report,
        ).pack(side="left", padx=4)

        _reflow_toolbar(workflow_buttons)

        self.statistics_label = ctk.CTkLabel(
            self,
            text=self.format_statistics({}),
            justify="left",
        )

        self.statistics_label.pack(
            fill="x",
            padx=20,
            pady=(0, 20),
        )

    # ------------------------------------------------------

    def load_mailboxes(self):

        self.mailbox_table.delete(*self.mailbox_table.get_children())
        self.mailboxes = self.engine.scan_mailboxes()

        grouped = {}

        for mailbox in self.mailboxes:

            account = mailbox.parent[0] if mailbox.parent else "Local Mail"

            grouped.setdefault(account, [])
            grouped[account].append(mailbox)

        for account in sorted(grouped):

            account_node = self.mailbox_table.insert(
                "",
                "end",
                text=account,
                iid=f"account_{account}",
                open=True,
            )

            for mailbox in sorted(
                grouped[account],
                key=lambda m: m.display_name.lower(),
            ):

                self.mailbox_table.insert(
                    account_node,
                    "end",
                    iid=f"mailbox_{id(mailbox)}",
                    text=mailbox.display_name,
                    values=(
                        round(mailbox.size / 1024 / 1024, 2),
                    ),
                )

        self.status_label.configure(
            text=f"{len(self.mailboxes)} mailboxes loaded."
        )

    # ------------------------------------------------------

    def scan_selected_mailboxes(self):

        selected_mailboxes = self.get_selected_mailboxes()

        if not selected_mailboxes:

            messagebox.showwarning(
                "Scan",
                "Select one or more mailboxes.",
            )

            return

        self.scan_mailboxes(selected_mailboxes)

    # ------------------------------------------------------

    def scan_all_mailboxes(self):

        if not self.mailboxes:

            self.load_mailboxes()

        self.scan_mailboxes(self.mailboxes)

    # ------------------------------------------------------

    def scan_mailboxes(self, mailboxes):

        self.result_table.delete(*self.result_table.get_children())
        self.messages = []
        self.visible_messages = []

        result = self.engine.scan_messages(
            mailboxes,
            self.update_scan_progress,
        )

        self.messages = result["messages"]

        self.refresh_results()

        if result["cancelled"]:

            self.status_label.configure(text="Scan cancelled safely.")

        else:

            self.status_label.configure(
                text=f"{len(self.messages)} messages scanned."
            )

    # ------------------------------------------------------

    def cancel_scan(self):

        self.engine.cancel_scan()
        self.status_label.configure(text="Cancelling scan...")

    # ------------------------------------------------------

    def update_scan_progress(self, message, current, total):

        self.status_label.configure(
            text=f"{message} ({current} of {total})"
        )
        self.update_idletasks()

    # ------------------------------------------------------

    def refresh_scan(self):

        selected_mailboxes = self.get_selected_mailboxes()

        if selected_mailboxes:

            self.scan_mailboxes(selected_mailboxes)

        elif self.mailboxes:

            self.scan_mailboxes(self.mailboxes)

        else:

            self.load_mailboxes()

    # ------------------------------------------------------

    def refresh_results(self):

        self.result_table.delete(*self.result_table.get_children())
        self.visible_messages = []

        for message in self.messages:

            if message.deleted or message.ignored:

                continue

            if self.engine.is_whitelisted(message):

                continue

            if message.classification == MessageClassifier.NORMAL:

                continue

            self.visible_messages.append(message)

            self.result_table.insert(
                "",
                "end",
                iid=f"message_{len(self.visible_messages) - 1}",
                values=self.message_values(message),
            )

        self.update_statistics()

    # ------------------------------------------------------

    def message_values(self, message):

        return (
            message.subject,
            message.sender,
            message.recipient,
            message.date,
            format_size(message.message_size),
            message.mailbox_name,
            message.classification,
            "Yes" if message.has_attachment else "No",
            message.attachment_count,
            format_size(message.attachment_size),
        )

    # ------------------------------------------------------

    def sort_results(self, column):

        if self.sort_column == column:

            self.sort_reverse = not self.sort_reverse

        else:

            self.sort_column = column
            self.sort_reverse = False

        rows = self.get_sort_rows(column)

        rows.sort(
            key=lambda row: row[0],
            reverse=self.sort_reverse,
        )

        for index, row in enumerate(rows):

            self.result_table.move(row[1], "", index)

    # ------------------------------------------------------

    def get_sort_rows(self, column):

        rows = []

        for item in self.result_table.get_children(""):

            message = self.get_message_from_result_item(item)

            if column == "Message Size" and message is not None:

                sort_value = message.message_size

            elif column == "Attachment Size" and message is not None:

                sort_value = message.attachment_size

            else:

                sort_value = self.sort_value(self.result_table.set(item, column))

            rows.append(
                (
                    sort_value,
                    item,
                )
            )

        return rows

    # ------------------------------------------------------

    def get_message_from_result_item(self, item):

        message_id = self.get_item_id(
            item,
            "message_",
        )

        if not message_id:

            return None

        index = int(message_id)

        if index >= len(self.visible_messages):

            return None

        return self.visible_messages[index]

    # ------------------------------------------------------

    def sort_value(self, value):

        try:

            return float(value)

        except Exception:

            return str(value).lower()

    # ------------------------------------------------------

    def get_selected_mailboxes(self):

        selected = []

        for item in self.mailbox_table.selection():

            mailbox_id = self.get_item_id(
                item,
                "mailbox_",
            )

            if not mailbox_id:

                continue

            for mailbox in self.mailboxes:

                if str(id(mailbox)) == mailbox_id:

                    selected.append(mailbox)

        return selected

    # ------------------------------------------------------

    def get_selected_messages(self):

        selected = []

        for item in self.result_table.selection():

            message_id = self.get_item_id(
                item,
                "message_",
            )

            if not message_id:

                continue

            index = int(message_id)

            if index < len(self.visible_messages):

                selected.append(self.visible_messages[index])

        return selected

    # ------------------------------------------------------

    def get_item_id(self, item, prefix):

        if not item.startswith(prefix):

            return ""

        return item.replace(prefix, "", 1)

    # ------------------------------------------------------

    def scroll_mailbox_table(self, event):

        if getattr(
            event,
            "num",
            None,
        ) == 4:

            self.mailbox_table.yview_scroll(
                -1,
                "units",
            )

        elif getattr(
            event,
            "num",
            None,
        ) == 5:

            self.mailbox_table.yview_scroll(
                1,
                "units",
            )

        else:

            units = int(-1 * (event.delta / 120))

            if units == 0 and event.delta != 0:

                units = -1 if event.delta > 0 else 1

            self.mailbox_table.yview_scroll(
                units,
                "units",
            )

        return "break"

    # ------------------------------------------------------

    def select_all_results(self):

        self.result_table.selection_set(self.result_table.get_children())

    # ------------------------------------------------------

    def clear_result_selection(self):

        self.result_table.selection_remove(self.result_table.selection())

    # ------------------------------------------------------

    def invert_result_selection(self):

        selected = set(self.result_table.selection())

        for item in self.result_table.get_children():

            if item in selected:

                self.result_table.selection_remove(item)

            else:

                self.result_table.selection_add(item)

    # ------------------------------------------------------

    def delete_selected(self):

        messages = self.get_selected_messages()

        if not messages:

            messagebox.showwarning(
                "Delete",
                "Select one or more messages.",
            )

            return

        self.confirm_and_delete(
            messages,
            "selected messages",
            allow_attachment_warning=True,
        )

    # ------------------------------------------------------

    def delete_all_by_classification(self, classification):

        messages = self.engine.get_cleanup_candidates(
            classification,
            include_attachments=True,
        )

        if not messages:

            messagebox.showinfo(
                "Cleanup",
                f"No safe {classification} messages are available for cleanup.",
            )

            return

        self.confirm_and_delete(
            messages,
            classification,
            allow_attachment_warning=True,
        )

    # ------------------------------------------------------

    def confirm_and_delete(self, messages, label, allow_attachment_warning):

        protected_messages = self.get_protected_messages(messages)

        if protected_messages:

            messagebox.showwarning(
                "Retained Duplicates",
                (
                    "Retained duplicate messages cannot be deleted by this utility. "
                    "They will be excluded from this cleanup."
                ),
            )

        delete_messages = self.exclude_messages(
            messages,
            protected_messages,
        )

        attachment_messages = self.get_attachment_messages(delete_messages)

        if attachment_messages and not allow_attachment_warning:

            delete_messages = self.exclude_attachment_messages(delete_messages)

        elif attachment_messages:

            if not messagebox.askyesno(
                "Attachment Warning",
                (
                    f"{len(attachment_messages)} selected messages contain "
                    "attachments. Delete them anyway?"
                ),
            ):

                delete_messages = self.exclude_attachment_messages(delete_messages)

        if not delete_messages:

            messagebox.showinfo(
                "Cleanup",
                "No messages are safe to delete.",
            )

            return

        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete {len(delete_messages)} {label}?",
        ):

            return

        result = self.engine.delete_messages(delete_messages)

        self.refresh_results()

        self.show_delete_result(
            result["deleted"],
            result["failures"],
        )

    # ------------------------------------------------------

    def show_delete_result(self, deleted, failures):

        if failures:

            details = "\n".join(
                f"{failure.message.mailbox_name} - "
                f"{failure.message.subject}: {failure.reason}"
                for failure in failures
            )

            messagebox.showwarning(
                "Cleanup Completed With Failures",
                (
                    f"{len(deleted)} messages deleted. "
                    f"{len(failures)} messages could not be deleted:\n\n"
                    f"{details}"
                ),
            )

        else:

            messagebox.showinfo(
                "Cleanup Complete",
                f"{len(deleted)} messages deleted.",
            )

    # ------------------------------------------------------

    def get_protected_messages(self, messages):

        return [
            message
            for message in messages
            if message.classification == MessageClassifier.PROTECTED_DUPLICATE
            or (
                message.classification
                in {
                    MessageClassifier.EXACT_DUPLICATE,
                    MessageClassifier.PROBABLE_DUPLICATE,
                }
                and not message.deletion_candidate
            )
        ]

    # ------------------------------------------------------

    def get_attachment_messages(self, messages):

        return [
            message
            for message in messages
            if message.has_attachment
        ]

    # ------------------------------------------------------

    def exclude_messages(self, messages, excluded_messages):

        excluded_ids = {
            id(message)
            for message in excluded_messages
        }

        return [
            message
            for message in messages
            if id(message) not in excluded_ids
        ]

    # ------------------------------------------------------

    def exclude_attachment_messages(self, messages):

        return [
            message
            for message in messages
            if not message.has_attachment
        ]

    # ------------------------------------------------------

    def ignore_selected(self):

        messages = self.get_selected_messages()

        if not messages:

            messagebox.showwarning(
                "Ignore",
                "Select one or more messages.",
            )

            return

        self.engine.ignore_messages(messages)
        self.refresh_results()

    # ------------------------------------------------------

    def whitelist_sender(self):

        messages = self.get_selected_messages()

        if not messages:

            messagebox.showwarning(
                "Whitelist",
                "Select one or more messages.",
            )

            return

        self.engine.whitelist_sender(messages)
        self.refresh_results()

    # ------------------------------------------------------

    def whitelist_domain(self):

        messages = self.get_selected_messages()

        if not messages:

            messagebox.showwarning(
                "Whitelist",
                "Select one or more messages.",
            )

            return

        self.engine.whitelist_domain(messages)
        self.refresh_results()

    # ------------------------------------------------------

    def export_duplicate_csv(self):

        filename = self.get_export_filename(
            "Duplicate_Email_Report.csv",
            ".csv",
        )

        if filename:

            self.engine.export_duplicate_csv(filename)

    # ------------------------------------------------------

    def export_cleanup_report(self):

        filename = self.get_export_filename(
            "Mail_Cleanup_Report.txt",
            ".txt",
        )

        if filename:

            self.engine.export_cleanup_report(filename)

    # ------------------------------------------------------

    def export_summary_report(self):

        filename = self.get_export_filename(
            "Summary_Report.txt",
            ".txt",
        )

        if filename:

            self.engine.export_summary_report(filename)

    # ------------------------------------------------------

    def get_export_filename(self, initialfile, extension):

        exports_folder = Path("exports").resolve()

        exports_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        return filedialog.asksaveasfilename(
            initialdir=str(exports_folder),
            initialfile=initialfile,
            defaultextension=extension,
            filetypes=[
                ("CSV Files", "*.csv"),
                ("Text Files", "*.txt"),
                ("All Files", "*.*"),
            ],
        )

    # ------------------------------------------------------

    def update_statistics(self):

        self.statistics_label.configure(
            text=self.format_statistics(self.engine.get_statistics())
        )

    # ------------------------------------------------------

    def format_statistics(self, stats):

        if not stats:

            stats = {
                "Messages Scanned": 0,
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
                "Deleted Messages": 0,
                "Recoverable Mailbox Space": 0,
            }

        return (
            f"Messages Scanned: {stats['Messages Scanned']}    "
            f"Exact Duplicates: {stats['Exact Duplicates']}    "
            f"Probable Duplicates: {stats['Probable Duplicates']}    "
            f"Protected Duplicates: {stats['Protected Duplicates']}\n"
            f"Read Receipts: {stats['Read Receipts']}    "
            f"Delivery Receipts: {stats['Delivery Receipts']}    "
            f"Undeliverable Messages: {stats['Undeliverable Messages']}    "
            f"Bounce Messages: {stats['Bounce Messages']}\n"
            f"Automatic Replies: {stats['Automatic Replies']}    "
            f"Out of Office Replies: {stats['Out of Office Replies']}    "
            f"Junk / Spam: {stats['Junk / Spam']}    "
            f"Messages with Attachments: {stats['Messages with Attachments']}\n"
            f"Deleted Messages: {stats['Deleted Messages']}    "
            "Recoverable Mailbox Space: "
            f"{format_size(stats['Recoverable Mailbox Space'])}"
        )
