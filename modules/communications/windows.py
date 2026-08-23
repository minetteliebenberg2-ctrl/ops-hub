# ==========================================================
# FC Hub - Communications Windows
# ----------------------------------------------------------
# Purpose:
# Native Hub screens for Communications workflows.
# Refactored to use separate floating windows per utility.
#
# Author: Minette & James
# Version: 2.0 (Windows Layout)
# ==========================================================

from pathlib import Path
import queue
import threading

import customtkinter as ctk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

from core.crm_repository import ContactRepository
from core.crm_service import CRMService
from modules.communications.mailbox_adapter import MailboxDiscoveryAdapter
from modules.communications.services import (
    AddressClassification,
    AutomaticEmailAddressCollector,
    CommunicationsDatabase,
    ContactCandidateRepository,
    CRMImportCoordinator,
    filter_review_queue,
    IgnoreListService,
    REVIEW_APPROVED,
    REVIEW_IGNORED,
    REVIEW_IMPORTED,
    REVIEW_NEEDS_ATTENTION,
    REVIEW_PENDING,
    REVIEW_REJECTED,
)

from gui.design_tokens import COLORS

THEME_DARK_GREY = COLORS["surface_primary"]
THEME_SURFACE = COLORS["surface_secondary"]
THEME_SURFACE_LIGHT = COLORS["surface_tertiary"]
THEME_TEXT_PRIMARY = COLORS["text_primary"]
THEME_TEXT_SECONDARY = COLORS["text_secondary"]


class CommunicationsHub(ctk.CTkToplevel):
    """Dockable hub launcher for Communications utilities.

    Must be a Toplevel, not a second ctk.CTk() root - see the matching
    comment on ProposalsHub for why."""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Communications Hub")
        self.geometry("480x400")
        self.resizable(False, False)
        self.configure(fg_color=THEME_DARK_GREY)

        ctk.CTkLabel(
            self,
            text="Communications Hub",
            font=("Segoe UI", 24, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(20, 30))

        ctk.CTkLabel(
            self,
            text="Open utilities as separate windows to work with multiple views simultaneously.",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
        ).pack(pady=(0, 30), padx=20)

        button_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        button_frame.pack(pady=20, padx=20, fill="both", expand=True)

        buttons = [
            ("📧 Mailbox Intelligence", self.open_mailbox_intelligence),
            ("👥 Contact Intelligence", self.open_contact_intelligence),
            ("✓ Contact Review Queue", self.open_review_queue),
        ]

        for label, command in buttons:
            ctk.CTkButton(
                button_frame,
                text=label,
                command=command,
                height=50,
                font=("Segoe UI", 12),
                fg_color=COLORS["accent_primary"],
                hover_color=COLORS["accent_hover"],
            ).pack(pady=10, fill="x")

        ctk.CTkButton(
            self,
            text="Close Hub",
            command=self.destroy,
            width=200,
            fg_color=COLORS["button_secondary"],
            hover_color=COLORS["button_secondary_hover"],
        ).pack(pady=(0, 20))

        self.open_windows = set()
        self.mailbox_intelligence_window = None
        self.contact_intelligence_window = None
        self.review_queue_window = None

    def open_mailbox_intelligence(self):
        if self.mailbox_intelligence_window is None or not self.mailbox_intelligence_window.winfo_exists():
            self.mailbox_intelligence_window = MailboxIntelligenceWindow(self, self.on_window_open, self.on_window_close)
            self.open_windows.add(self.mailbox_intelligence_window)
        else:
            self.mailbox_intelligence_window.lift()
            self.mailbox_intelligence_window.focus()

    def open_contact_intelligence(self):
        if self.contact_intelligence_window is None or not self.contact_intelligence_window.winfo_exists():
            self.contact_intelligence_window = ContactIntelligenceWindow(self, self.on_window_open, self.on_window_close)
            self.open_windows.add(self.contact_intelligence_window)
        else:
            self.contact_intelligence_window.lift()
            self.contact_intelligence_window.focus()

    def open_review_queue(self):
        if self.review_queue_window is None or not self.review_queue_window.winfo_exists():
            self.review_queue_window = ReviewQueueWindow(self, self.on_window_open, self.on_window_close)
            self.open_windows.add(self.review_queue_window)
        else:
            self.review_queue_window.lift()
            self.review_queue_window.focus()

    def on_window_open(self, window):
        self.open_windows.add(window)

    def on_window_close(self, window):
        self.open_windows.discard(window)


class CommunicationsModuleWindow(ctk.CTkFrame):
    """Module frame - launches hub automatically"""

    def __init__(self, master):
        super().__init__(master)

        self.database = CommunicationsDatabase()
        self.database.initialize()
        self.hub = None

        ctk.CTkLabel(
            self,
            text="Communications Hub",
            font=("Segoe UI", 22, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(20, 30))

        info_frame = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        info_frame.pack(pady=20, padx=40, fill="both", expand=True)

        ctk.CTkLabel(
            info_frame,
            text="Communications utilities are now available as separate windows.\n\nClick the button below to open the hub, or use the buttons to launch specific utilities.",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
            justify="center",
        ).pack(pady=20, padx=20)

        button_frame = ctk.CTkFrame(info_frame, fg_color=THEME_SURFACE)
        button_frame.pack(pady=20, padx=20, fill="x")

        ctk.CTkButton(
            button_frame,
            text="Open Communications Hub",
            command=self.launch_hub,
            height=50,
            font=("Segoe UI", 12),
            fg_color="#1B7A3D",
            hover_color="#165a30",
        ).pack(pady=10, fill="x")

        ctk.CTkButton(
            button_frame,
            text="📧 Mailbox Intelligence",
            command=self.open_mailbox,
            height=40,
            font=("Segoe UI", 11),
        ).pack(pady=5, fill="x")

        ctk.CTkButton(
            button_frame,
            text="👥 Contact Intelligence",
            command=self.open_contact,
            height=40,
            font=("Segoe UI", 11),
        ).pack(pady=5, fill="x")

        ctk.CTkButton(
            button_frame,
            text="✓ Contact Review Queue",
            command=self.open_review,
            height=40,
            font=("Segoe UI", 11),
        ).pack(pady=5, fill="x")

    def launch_hub(self):
        if self.hub is None or not self.hub.winfo_exists():
            self.hub = CommunicationsHub(self.winfo_toplevel())
        else:
            self.hub.lift()
            self.hub.focus()

    def open_mailbox(self):
        if self.hub is None or not self.hub.winfo_exists():
            self.hub = CommunicationsHub(self.winfo_toplevel())
        self.hub.open_mailbox_intelligence()

    def open_contact(self):
        if self.hub is None or not self.hub.winfo_exists():
            self.hub = CommunicationsHub(self.winfo_toplevel())
        self.hub.open_contact_intelligence()

    def open_review(self):
        if self.hub is None or not self.hub.winfo_exists():
            self.hub = CommunicationsHub(self.winfo_toplevel())
        self.hub.open_review_queue()


class MailboxIntelligenceWindow(ctk.CTkToplevel):
    """Mailbox Intelligence utility window"""

    def __init__(self, parent, on_open=None, on_close=None):
        super().__init__(parent)

        self.title("Mailbox Intelligence")
        self.geometry("1200x750")
        self.configure(fg_color=THEME_DARK_GREY)
        self.on_close = on_close

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        if on_open:
            on_open(self)

        ctk.CTkLabel(
            self,
            text="Mailbox Intelligence",
            font=("Segoe UI", 18, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(10, 15), padx=20)

        try:

            from gui.duplicate_email_window import DuplicateEmailWindow

            DuplicateEmailWindow(self).pack(fill="both", expand=True)

        except Exception as error:

            ctk.CTkLabel(
                self,
                text=(
                    "Mailbox Intelligence requires the Duplicate Email & Mail "
                    f"Cleanup files to be available. {error}"
                ),
                text_color=THEME_TEXT_SECONDARY,
            ).pack(padx=20, pady=40)

    def _on_closing(self):
        if self.on_close:
            self.on_close(self)
        self.destroy()


class ContactIntelligenceWindow(ctk.CTkToplevel):

    def __init__(self, parent, on_open=None, on_close=None):
        super().__init__(parent)

        self.title("Contact Intelligence")
        self.geometry("1200x750")
        self.configure(fg_color=THEME_DARK_GREY)
        self.on_close = on_close

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        if on_open:
            on_open(self)

        self.database = CommunicationsDatabase()
        self.database.initialize()
        self.contact_repository = ContactRepository()
        self.collector = AutomaticEmailAddressCollector(
            self.database.database_path,
            self.contact_repository,
        )
        self.mailbox_adapter = MailboxDiscoveryAdapter()
        self.repository = ContactCandidateRepository(self.database)
        self.ignore_list = IgnoreListService(self.database)
        self.mailboxes = []
        self.candidates = []
        self.visible_candidates = []
        self.active_filter = ctk.StringVar(value="All")
        self.search_text = ctk.StringVar(value="")
        self.sort_column = ""
        self.sort_reverse = False

        # Background thread -> main thread communication. Tkinter/Tcl on
        # this machine is not built with thread support, so calling
        # self.after(...) (or any widget method) from a worker thread
        # raises "RuntimeError: main thread is not in main loop". The
        # worker thread only ever pushes plain data onto this queue; a
        # self.after() poll loop running on the main thread drains it and
        # is the only thing that touches widgets.
        self.collection_queue = queue.Queue()
        self.collection_running = False
        self._closed = False

        ctk.CTkLabel(
            self,
            text="Contact Intelligence",
            font=("Segoe UI", 18, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(0, 10))

        control_frame = ctk.CTkFrame(self)
        control_frame.pack(fill="x", padx=10, pady=(0, 8))

        control_actions = (
            ("Load Mailboxes", self.load_mailboxes),
            ("Collect Selected", self.collect_selected),
            ("Cancel", self.cancel_collection),
            ("Export Results", self.export_results),
            ("Send to Review Queue", self.send_to_review_queue),
            ("Ignore Selected", self.ignore_selected_candidates),
            ("Delete Selected", self.delete_selected_candidates),
        )
        for index, (label, command) in enumerate(control_actions):
            ctk.CTkButton(
                control_frame,
                text=label,
                command=command,
            ).grid(
                row=index // 3,
                column=index % 3,
                padx=4,
                pady=4,
                sticky="ew",
            )
        for column in range(3):
            control_frame.grid_columnconfigure(column, weight=1)

        self.status_label = ctk.CTkLabel(
            self,
            text="→ Step 1: Click 'Load Mailboxes' | Step 2: Select mailboxes (blue highlight) | Step 3: Click 'Collect Selected'",
            text_color=THEME_TEXT_SECONDARY,
        )
        self.status_label.pack(fill="x", padx=10, pady=(0, 8))

        mailbox_frame = ctk.CTkFrame(self)
        mailbox_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.mailbox_sort_column = ""
        self.mailbox_sort_reverse = False

        self.mailbox_table = ttk.Treeview(
            mailbox_frame,
            columns=("Email Address", "Size"),
            show="tree headings",
            selectmode="extended",
            height=7,
        )
        self.mailbox_table.heading("#0", text="Mailbox", command=lambda: self.sort_mailboxes("#0"))
        self.mailbox_table.heading("Email Address", text="Email Address", command=lambda: self.sort_mailboxes("Email Address"))
        self.mailbox_table.heading("Size", text="MB", command=lambda: self.sort_mailboxes("Size"))
        self.mailbox_table.column("#0", width=460, stretch=True)
        self.mailbox_table.column("Email Address", width=240, stretch=True)
        self.mailbox_table.column("Size", width=100, anchor="e", stretch=False)

        mailbox_scrollbar = ttk.Scrollbar(
            mailbox_frame,
            orient="vertical",
            command=self.mailbox_table.yview,
        )
        mailbox_horizontal_scrollbar = ttk.Scrollbar(
            mailbox_frame,
            orient="horizontal",
            command=self.mailbox_table.xview,
        )
        self.mailbox_table.configure(
            yscrollcommand=mailbox_scrollbar.set,
            xscrollcommand=mailbox_horizontal_scrollbar.set,
        )
        self.mailbox_table.bind('<<TreeviewSelect>>', self._on_mailbox_select)
        self.mailbox_table.grid(row=0, column=0, sticky="nsew")
        mailbox_scrollbar.grid(row=0, column=1, sticky="ns")
        mailbox_horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        mailbox_frame.grid_columnconfigure(0, weight=1)

        filter_frame = ctk.CTkFrame(self)
        filter_frame.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkOptionMenu(
            filter_frame,
            values=[
                "All",
                "New Candidates",
                "Existing CRM Contacts",
                "Valid",
                "Invalid",
                "Automated or System",
                "Ignored",
                "Duplicates",
            ],
            variable=self.active_filter,
            command=lambda value: self.refresh_candidates(),
        ).pack(side="left", padx=4)

        ctk.CTkEntry(
            filter_frame,
            textvariable=self.search_text,
            placeholder_text="Search email or name",
            width=280,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            filter_frame,
            text="Search",
            command=self.refresh_candidates,
        ).pack(side="left", padx=4)

        self.statistics_label = ctk.CTkLabel(self, text="")
        self.statistics_label.pack(fill="x", padx=10, pady=(0, 8))

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.columns = (
            "Email Address",
            "Display Name",
            "Classification",
            "Existing CRM Match",
            "Occurrences",
            "First Seen",
            "Last Seen",
            "Source Mailbox",
            "Direction",
            "Review Status",
            "Phone",
            "Website",
            "VAT No.",
            "Company",
        )

        self.candidate_table = ttk.Treeview(
            table_frame,
            columns=self.columns,
            show="headings",
            selectmode="extended",
            height=14,
        )

        for column in self.columns:

            self.candidate_table.heading(
                column,
                text=column,
                command=lambda c=column: self.sort_candidates(c),
            )

        self.candidate_table.column("Email Address", width=220, stretch=True)
        self.candidate_table.column("Display Name", width=180, stretch=True)
        self.candidate_table.column("Classification", width=160, stretch=False)
        self.candidate_table.column("Existing CRM Match", width=170, stretch=False)
        self.candidate_table.column("Occurrences", width=100, anchor="e", stretch=False)
        self.candidate_table.column("First Seen", width=170, stretch=False)
        self.candidate_table.column("Last Seen", width=170, stretch=False)
        self.candidate_table.column("Source Mailbox", width=220, stretch=True)
        self.candidate_table.column("Direction", width=120, stretch=False)
        self.candidate_table.column("Review Status", width=150, stretch=False)
        self.candidate_table.column("Phone", width=150, stretch=False)
        self.candidate_table.column("Website", width=170, stretch=False)
        self.candidate_table.column("VAT No.", width=150, stretch=False)
        self.candidate_table.column("Company", width=170, stretch=False)

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.candidate_table.yview,
        )
        horizontal_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.candidate_table.xview,
        )
        self.candidate_table.configure(
            yscrollcommand=scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set,
        )
        self.candidate_table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------

    def _on_closing(self):
        """Stops the poll loop from touching widgets after this window
        (and its widgets) are destroyed. A collection already running in
        the background thread is left to finish quietly - it will keep
        pushing onto self.collection_queue, but _poll_collection_queue
        checks self._closed on every tick and stops draining/scheduling
        once this flag is set, instead of hitting the destroyed
        self.status_label and raising TclError."""

        self._closed = True

        if self.on_close:
            self.on_close(self)

        self.destroy()

    # ------------------------------------------------------

    def load_mailboxes(self):

        try:
            self.mailbox_table.delete(*self.mailbox_table.get_children())
            self.mailboxes = self.mailbox_adapter.scan_mailboxes()

            if not self.mailboxes:
                messagebox.showwarning("No Mailboxes", "No mailboxes found. Check Thunderbird is installed and configured.")
                self.status_label.configure(text="No mailboxes found.")
                return

            for mailbox in self.mailboxes:

                self.mailbox_table.insert(
                    "",
                    "end",
                    iid=f"mailbox_{id(mailbox)}",
                    text=mailbox.display_name,
                    values=(
                        self.mailbox_email_address(mailbox),
                        round(mailbox.size / 1024 / 1024, 2),
                    ),
                )

            self.status_label.configure(text=f"{len(self.mailboxes)} mailboxes loaded. Select and click 'Collect Selected'.")

        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load mailboxes:\n{str(e)}")
            self.status_label.configure(text=f"Error loading mailboxes: {str(e)}")

    # ------------------------------------------------------

    def mailbox_email_address(self, mailbox):

        accounts = mailbox.parent

        if isinstance(accounts, str):

            return accounts

        return ", ".join(accounts) if accounts else ""

    # ------------------------------------------------------

    def _on_mailbox_select(self, event):
        """Handle mailbox selection - show count"""
        selected_count = len(self.mailbox_table.selection())
        if selected_count > 0:
            self.status_label.configure(
                text=f"✓ {selected_count} mailbox(es) selected. Click 'Collect Selected' to scan for emails."
            )

    # ------------------------------------------------------

    def sort_mailboxes(self, column):

        self.mailbox_sort_reverse = not self.mailbox_sort_reverse if self.mailbox_sort_column == column else False
        self.mailbox_sort_column = column

        rows = [
            (self.mailbox_sort_value(mailbox, column), item)
            for item, mailbox in zip(self.mailbox_table.get_children(""), self.mailboxes)
        ]
        rows.sort(key=lambda row: row[0], reverse=self.mailbox_sort_reverse)

        for index, row in enumerate(rows):

            self.mailbox_table.move(row[1], "", index)

    # ------------------------------------------------------

    def mailbox_sort_value(self, mailbox, column):

        if column == "#0":

            return mailbox.display_name.lower()

        if column == "Email Address":

            return self.mailbox_email_address(mailbox).lower()

        if column == "Size":

            return mailbox.size

        return ""

    # ------------------------------------------------------

    def collect_selected(self):

        if self.collection_running:

            messagebox.showinfo("Collection", "A collection is already running.")

            return

        selected_mailboxes = self.get_selected_mailboxes()

        if not selected_mailboxes:

            messagebox.showwarning("Collection", "Select one or more mailboxes.")

            return

        self.collection_running = True
        self.status_label.configure(text="Starting collection...")

        threading.Thread(
            target=self.run_collection,
            args=(selected_mailboxes,),
            daemon=True,
        ).start()

        # Only the main thread ever touches Tk widgets. The poll loop is
        # started here (on the main thread) and re-schedules itself with
        # self.after() each tick, draining whatever the worker thread put
        # on self.collection_queue.
        self.after(100, self._poll_collection_queue)

    # ------------------------------------------------------

    def run_collection(self, selected_mailboxes):
        """Runs on a background thread. Must NOT call any Tk/CTk method
        (including self.after) - only ever push plain data onto the
        thread-safe queue for the main thread to consume."""

        try:
            result = self.collector.collect(
                selected_mailboxes,
                progress_callback=self._queue_progress,
            )
            self.collection_queue.put(("done", result))

        except Exception as e:

            self.collection_queue.put(("error", str(e)))

    # ------------------------------------------------------

    def _queue_progress(self, message, current, total):
        """Called from the background thread - queue only, no Tk calls."""

        self.collection_queue.put(("progress", f"{message} ({current} of {total})"))

    # ------------------------------------------------------

    def _poll_collection_queue(self):
        """Runs on the main thread via self.after(). Drains queued
        messages from the background collection thread and updates the
        UI. Reschedules itself while the collection is still running."""

        if self._closed:

            # Window was closed while a collection was still in flight.
            # Widgets are gone (or going) - stop touching them and stop
            # rescheduling. The background thread finishes on its own and
            # its remaining queue messages are simply left unread.
            return

        try:

            while True:

                kind, payload = self.collection_queue.get_nowait()

                if kind == "progress":

                    self.status_label.configure(text=payload)

                elif kind == "done":

                    self.collection_running = False
                    self.candidates = payload["candidates"]

                    if not self.candidates:
                        messagebox.showinfo("Collection Complete", "No email addresses found in selected mailboxes.")
                        self.status_label.configure(text="Collection complete. No candidates found.")
                    else:
                        messagebox.showinfo("Collection Complete", f"Found {len(self.candidates)} unique email addresses.")
                        self.status_label.configure(text=f"Loaded {len(self.candidates)} candidates. Apply filters to review.")

                    self.refresh_candidates()
                    return

                elif kind == "error":

                    self.collection_running = False
                    messagebox.showerror("Collection Error", f"Failed to collect emails:\n{payload}")
                    self.status_label.configure(text=f"Error: {payload}")
                    return

        except queue.Empty:

            pass

        if self.collection_running:

            self.after(100, self._poll_collection_queue)

    # ------------------------------------------------------

    def cancel_collection(self):

        self.collector.cancel()
        self.status_label.configure(text="Cancelling collection...")

    # ------------------------------------------------------

    def get_selected_mailboxes(self):

        selected = []

        for item in self.mailbox_table.selection():

            if not item.startswith("mailbox_"):

                continue

            mailbox_id = item.replace("mailbox_", "", 1)

            for mailbox in self.mailboxes:

                if str(id(mailbox)) == mailbox_id:

                    selected.append(mailbox)

        # Update status with selection count
        if selected:
            self.status_label.configure(
                text=f"→ {len(selected)} mailbox(es) selected. Click 'Collect Selected' to scan for emails."
            )
        else:
            self.status_label.configure(
                text="→ Step 1: Click 'Load Mailboxes' | Step 2: Select mailboxes (blue highlight) | Step 3: Click 'Collect Selected'"
            )

        return selected

    # ------------------------------------------------------

    def refresh_candidates(self):

        self.candidate_table.delete(*self.candidate_table.get_children())

        if not self.candidates:
            self.statistics_label.configure(text="No candidates loaded. Click 'Load Mailboxes' then 'Collect Selected'.")
            self.status_label.configure(text="0 candidates visible.")
            return

        self.visible_candidates = self.apply_filters(self.candidates)

        for index, candidate in enumerate(self.visible_candidates):

            self.candidate_table.insert(
                "",
                "end",
                iid=f"candidate_{index}",
                values=self.candidate_values(candidate),
            )

        stats = self.collector.get_statistics(self.candidates)
        self.statistics_label.configure(text=self.format_statistics(stats))
        self.status_label.configure(text=f"{len(self.visible_candidates)} candidates visible out of {len(self.candidates)} total.")

    # ------------------------------------------------------

    def apply_filters(self, candidates):

        selected_filter = self.active_filter.get()
        search = self.search_text.get().lower().strip()
        results = []

        for candidate in candidates:

            if search and search not in candidate.normalized_email and search not in candidate.display_name.lower():

                continue

            if selected_filter != "All" and not self.matches_filter(candidate, selected_filter):

                continue

            results.append(candidate)

        return results

    # ------------------------------------------------------

    def matches_filter(self, candidate, selected_filter):

        return (
            selected_filter == candidate.classification
            or (
                selected_filter == "New Candidates"
                and candidate.classification == AddressClassification.NEW
            )
            or (
                selected_filter == "Existing CRM Contacts"
                and candidate.classification == AddressClassification.EXISTING
            )
            or (
                selected_filter == "Duplicates"
                and candidate.occurrences > 1
            )
        )

    # ------------------------------------------------------

    def candidate_values(self, candidate):

        return (
            candidate.normalized_email,
            candidate.display_name,
            candidate.classification,
            candidate.existing_match_status,
            candidate.occurrences,
            candidate.first_seen,
            candidate.last_seen,
            candidate.source_mailbox,
            candidate.source_header_types,
            candidate.review_status,
            candidate.extracted_phone,
            candidate.extracted_website,
            candidate.extracted_vat_number,
            candidate.extracted_company_name,
        )

    # ------------------------------------------------------

    def sort_candidates(self, column):

        self.sort_reverse = not self.sort_reverse if self.sort_column == column else False
        self.sort_column = column
        column_index = self.columns.index(column)

        rows = [
            (
                self.get_sort_value(candidate, column),
                item,
            )
            for item, candidate in zip(
                self.candidate_table.get_children(""),
                self.visible_candidates,
            )
        ]
        rows.sort(key=lambda row: row[0], reverse=self.sort_reverse)

        for index, row in enumerate(rows):

            self.candidate_table.move(row[1], "", index)

    # ------------------------------------------------------

    def get_sort_value(self, candidate, column):

        if column == "Occurrences":

            return candidate.occurrences

        if column in {"First Seen", "Last Seen"}:

            return candidate.first_seen if column == "First Seen" else candidate.last_seen

        return str(self.candidate_values(candidate)[self.columns.index(column)]).lower()

    # ------------------------------------------------------

    def send_to_review_queue(self):

        messagebox.showinfo(
            "Review Queue",
            "Collected candidates have been saved to the Contact Review Queue.",
        )

    # ------------------------------------------------------

    def get_selected_candidates(self):

        selected = []

        for item in self.candidate_table.selection():

            if not item.startswith("candidate_"):

                continue

            index = int(item.replace("candidate_", "", 1))

            if index < len(self.visible_candidates):

                selected.append(self.visible_candidates[index])

        return selected

    # ------------------------------------------------------

    def ignore_selected_candidates(self):

        candidates = self.get_selected_candidates()

        if not candidates:

            messagebox.showwarning("Ignore", "Select one or more candidates.")

            return

        if not messagebox.askyesno(
            "Ignore Selected",
            f"Ignore {len(candidates)} candidate(s)? They will no longer appear in future scans.",
        ):

            return

        for candidate in candidates:

            self.ignore_list.add_email(candidate.normalized_email, "Ignored from Contact Intelligence")

        self.repository.update_review_status(
            [candidate.normalized_email for candidate in candidates],
            REVIEW_IGNORED,
        )

        self.candidates = self.repository.get_candidates()
        self.refresh_candidates()

    # ------------------------------------------------------

    def delete_selected_candidates(self):

        candidates = self.get_selected_candidates()

        if not candidates:

            messagebox.showwarning("Delete", "Select one or more candidates.")

            return

        if not messagebox.askyesno(
            "Delete Selected",
            f"Permanently delete {len(candidates)} candidate(s)? This cannot be undone. "
            "They may reappear on a future scan unless also ignored.",
        ):

            return

        self.repository.delete_candidates(
            [candidate.normalized_email for candidate in candidates]
        )

        self.candidates = self.repository.get_candidates()
        self.refresh_candidates()

    # ------------------------------------------------------

    def export_results(self):

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile="Contact_Intelligence.csv",
        )

        if filename:

            self.collector.export_candidates(self.visible_candidates, filename)

    # ------------------------------------------------------

    def format_statistics(self, stats):

        return " | ".join(
            f"{name.title()}: {value}"
            for name, value in stats.items()
        )


class ReviewQueueWindow(ctk.CTkToplevel):

    def __init__(self, parent, on_open=None, on_close=None):
        super().__init__(parent)

        self.title("Contact Review Queue")
        self.geometry("1200x750")
        self.configure(fg_color=THEME_DARK_GREY)
        self.on_close = on_close

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        if on_open:
            on_open(self)

        self.database = CommunicationsDatabase()
        self.database.initialize()
        self.repository = ContactCandidateRepository(self.database)
        self.ignore_list = IgnoreListService(self.database)
        self.crm_service = CRMService()
        self.importer = CRMImportCoordinator(self.database, self.crm_service)
        self.candidates = []
        self.visible_candidates = []
        self.active_status = ctk.StringVar(value="All")
        self.search_text = ctk.StringVar(value="")
        self.hide_archived = ctk.BooleanVar(value=True)
        self.sort_column = ""
        self.sort_reverse = False

        ctk.CTkLabel(
            self,
            text="Contact Review Queue",
            font=("Segoe UI", 18, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(0, 10))

        controls = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        controls.pack(fill="x", padx=10, pady=(0, 8))

        queue_actions = (
            ("Refresh", self.load_queue),
            (
                "Approve Selected",
                lambda: self.update_selected(REVIEW_APPROVED),
            ),
            (
                "Reject Selected",
                lambda: self.update_selected(REVIEW_REJECTED),
            ),
            ("Ignore Selected", self.ignore_selected),
            (
                "Restore Pending",
                lambda: self.update_selected(REVIEW_PENDING),
            ),
            ("Open in CRM", self.open_in_crm),
            ("CRM Import Wizard", self.open_import_wizard),
            ("Export Queue", self.export_queue),
        )
        for index, (label, command) in enumerate(queue_actions):
            ctk.CTkButton(
                controls,
                text=label,
                command=command,
            ).grid(
                row=index // 3,
                column=index % 3,
                padx=4,
                pady=4,
                sticky="ew",
            )
        for column in range(3):
            controls.grid_columnconfigure(column, weight=1)

        filters = ctk.CTkFrame(self)
        filters.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkOptionMenu(
            filters,
            values=[
                "All",
                REVIEW_PENDING,
                REVIEW_APPROVED,
                REVIEW_REJECTED,
                REVIEW_IGNORED,
                REVIEW_IMPORTED,
                REVIEW_NEEDS_ATTENTION,
            ],
            variable=self.active_status,
            command=lambda value: self.refresh_queue(),
        ).pack(side="left", padx=4)

        ctk.CTkEntry(
            filters,
            textvariable=self.search_text,
            placeholder_text="Search email or name",
            width=280,
        ).pack(side="left", padx=4)

        ctk.CTkButton(filters, text="Search", command=self.refresh_queue).pack(side="left", padx=4)

        hide_archived_checkbox = ctk.CTkCheckBox(
            filters, text="Hide archived/rejected", variable=self.hide_archived,
            command=self.refresh_queue,
        )
        hide_archived_checkbox.pack(side="left", padx=4)
        # Passing variable=self.hide_archived alone doesn't reliably sync
        # the checkbox's rendered glyph to the BooleanVar's initial True
        # value on every CustomTkinter version - force it explicitly so
        # what she sees checked matches what's actually being filtered.
        if self.hide_archived.get():
            hide_archived_checkbox.select()

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.columns = (
            "Email Address",
            "Display Name",
            "Classification",
            "Existing CRM Match",
            "Occurrences",
            "First Seen",
            "Last Seen",
            "Source Mailbox",
            "Direction",
            "Review Status",
        )
        self.table = ttk.Treeview(
            table_frame,
            columns=self.columns,
            show="headings",
            selectmode="extended",
            height=16,
        )

        for column in self.columns:

            self.table.heading(column, text=column, command=lambda c=column: self.sort_queue(c))
            self.table.column(column, width=150, stretch=True)

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.table.yview,
        )
        horizontal_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.table.xview,
        )
        self.table.configure(
            yscrollcommand=scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set,
        )
        self.table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.load_queue()

    # ------------------------------------------------------

    def load_queue(self):

        self.candidates = self.repository.get_candidates()
        self.refresh_queue()

    # ------------------------------------------------------

    def refresh_queue(self):

        status = self.active_status.get()
        search = self.search_text.get().strip()

        self.visible_candidates = filter_review_queue(
            self.candidates, status, self.hide_archived.get(), search,
        )

        if self.sort_column:
            self.visible_candidates.sort(
                key=lambda candidate: self._sort_value(candidate, self.sort_column),
                reverse=self.sort_reverse,
            )

        self._render_visible()

    # ------------------------------------------------------

    def _render_visible(self):

        self.table.delete(*self.table.get_children())

        for index, candidate in enumerate(self.visible_candidates):

            self.table.insert(
                "",
                "end",
                iid=f"candidate_{index}",
                values=self._candidate_values(candidate),
            )

    # ------------------------------------------------------

    def _candidate_values(self, candidate):

        return (
            candidate.normalized_email,
            candidate.display_name,
            candidate.classification,
            candidate.existing_match_status,
            candidate.occurrences,
            candidate.first_seen,
            candidate.last_seen,
            candidate.source_mailbox,
            candidate.source_header_types,
            candidate.review_status,
        )

    # ------------------------------------------------------

    def sort_queue(self, column):

        self.sort_reverse = not self.sort_reverse if self.sort_column == column else False
        self.sort_column = column
        self.visible_candidates.sort(
            key=lambda candidate: self._sort_value(candidate, column),
            reverse=self.sort_reverse,
        )
        self._render_visible()

    # ------------------------------------------------------

    def _sort_value(self, candidate, column):

        if column == "Occurrences":
            return candidate.occurrences

        return str(self._candidate_values(candidate)[self.columns.index(column)]).lower()

    # ------------------------------------------------------

    def get_selected_candidates(self):

        selected = []

        for item in self.table.selection():

            if not item.startswith("candidate_"):

                continue

            index = int(item.replace("candidate_", "", 1))

            if index < len(self.visible_candidates):

                selected.append(self.visible_candidates[index])

        return selected

    # ------------------------------------------------------

    def update_selected(self, status):

        candidates = self.get_selected_candidates()

        if not candidates:

            messagebox.showwarning("Review Queue", "Select one or more candidates.")

            return

        self.repository.update_review_status(
            [candidate.normalized_email for candidate in candidates],
            status,
        )
        self.load_queue()

    # ------------------------------------------------------

    def ignore_selected(self):

        candidates = self.get_selected_candidates()

        if not candidates:

            messagebox.showwarning("Ignore", "Select one or more candidates.")

            return

        for candidate in candidates:

            self.ignore_list.add_email(candidate.normalized_email, "Ignored from review queue")

        self.repository.update_review_status(
            [candidate.normalized_email for candidate in candidates],
            REVIEW_IGNORED,
        )
        self.load_queue()

    # ------------------------------------------------------

    def open_in_crm(self):
        """Jump straight to the matched customer's CRM record instead
        of noting the match here and searching for them by hand."""

        candidates = self.get_selected_candidates()

        if not candidates:
            messagebox.showwarning("Open in CRM", "Select a candidate first.")
            return
        if len(candidates) > 1:
            messagebox.showwarning("Open in CRM", "Select only one candidate to open.")
            return

        customer_id = self._resolve_customer_id(candidates[0].normalized_email)
        if customer_id is None:
            messagebox.showinfo("Open in CRM", "No matching CRM customer found for this email.")
            return

        customer = self.crm_service.get_customer(customer_id)
        if customer is None:
            messagebox.showinfo("Open in CRM", "That customer is no longer in the CRM.")
            return

        # There is no standalone CustomerDetailWindow - the detail view
        # lives inside CRMWindow, so host one in its own window and open
        # it straight on this customer. Parented to the toplevel, never
        # to a CTkFrame, or it freezes on grab_set.
        from modules.crm.windows import CRMWindow

        holder = ctk.CTkToplevel(self.winfo_toplevel())
        holder.title(f"CRM — {customer.name}")
        holder.geometry("1200x800")
        crm_view = CRMWindow(holder)
        crm_view.pack(fill="both", expand=True)
        crm_view._show_customer_detail(customer)

    # ------------------------------------------------------

    def _resolve_customer_id(self, email):

        contacts = self.crm_service.contacts.find_contacts_by_email(email)
        if contacts:
            return contacts[0].customer_id

        customers = self.crm_service.customers.find_by_normalized_email(email)
        if customers:
            return customers[0].id

        return None

    # ------------------------------------------------------

    def open_import_wizard(self):

        approved = [
            candidate
            for candidate in self.get_selected_candidates()
            if candidate.review_status == REVIEW_APPROVED
        ]

        if not approved:

            messagebox.showwarning("CRM Import", "Select approved candidates first.")

            return

        CRMImportWizard(self, self.importer, self.repository, approved)

    # ------------------------------------------------------

    def export_queue(self):

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile="Contact_Review_Queue.csv",
        )

        if filename:

            collector = AutomaticEmailAddressCollector()
            collector.export_candidates(self.visible_candidates, filename)

    # ------------------------------------------------------

    def _on_closing(self):

        if self.on_close:

            self.on_close(self)

        self.destroy()


class CRMImportWizard(ctk.CTkToplevel):

    def __init__(self, master, importer, repository, candidates):
        super().__init__(master)

        self.importer = importer
        self.repository = repository
        self.candidates = candidates

        self.title("CRM Import Wizard")
        self.geometry("1200x750")

        ctk.CTkLabel(
            self,
            text="CRM Import Wizard",
            font=("Segoe UI", 20, "bold"),
        ).pack(pady=(20, 10))

        self.action = ctk.StringVar(value="Skip")

        ctk.CTkOptionMenu(
            self,
            values=[
                "Link to Existing Contact",
                "Add Email to Existing Contact",
                "Create New Contact under Existing Customer",
                "Create New Customer and Contact",
                "Skip",
                "Return to Review Queue",
            ],
            variable=self.action,
        ).pack(pady=(0, 10))

        table = ttk.Treeview(
            self,
            columns=(
                "Email",
                "Display Name",
                "Occurrences",
                "First Seen",
                "Last Seen",
                "Source Mailbox",
                "Direction",
                "Existing Match",
                "Proposed Action",
            ),
            show="headings",
            selectmode="extended",
        )
        for column in table["columns"]:

            table.heading(column, text=column)
            table.column(column, width=130, stretch=True)

        for candidate in candidates:

            table.insert(
                "",
                "end",
                values=(
                    candidate.normalized_email,
                    candidate.display_name,
                    candidate.occurrences,
                    candidate.first_seen,
                    candidate.last_seen,
                    candidate.source_mailbox,
                    candidate.source_header_types,
                    candidate.existing_match_status,
                    self.action.get(),
                ),
            )

        table.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        ctk.CTkButton(
            self,
            text="Import Approved Candidates",
            command=self.import_candidates,
        ).pack(pady=(0, 20))

    # ------------------------------------------------------

    def import_candidates(self):

        action = self.action.get()

        if action == "Return to Review Queue":

            self.destroy()

            return

        if action.startswith("Create") and not messagebox.askyesno(
            "CRM Import",
            "Creating CRM data requires explicit confirmation. Continue?",
        ):

            return

        imported = []

        for candidate in self.candidates:

            status = self.importer.import_candidate(candidate, action)

            if status == "Imported":

                imported.append(candidate.normalized_email)

        if imported:

            self.repository.update_review_status(imported, REVIEW_IMPORTED)

        messagebox.showinfo(
            "CRM Import",
            f"{len(imported)} candidates imported.",
        )
        self.destroy()
