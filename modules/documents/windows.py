"""Native CustomTkinter window for the FC Hub Documents module.

Two jobs, split into two panes:
  - Create: start a new letter or spreadsheet from the branded templates.
  - Library: store and find the compliance paperwork clients ask for
    (Tax Compliance, COIDA, bank confirmations, insurance), with expiry
    dates surfaced because a lapsed certificate found mid-tender is the
    failure this module exists to prevent.
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from gui.components.date_picker import DateEntry
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from modules.documents.services import (
    CATEGORIES,
    EXPIRY_WARNING_DAYS,
    DocumentsRepository,
    parse_date,
)


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
LETTERHEAD_TEMPLATE = TEMPLATE_DIR / "FacilitiesCo_Letterhead.docx"
SPREADSHEET_TEMPLATE = TEMPLATE_DIR / "FacilitiesCo_Spreadsheet.xlsx"


def open_in_default_app(path):
    """Open a file with whatever the OS has associated (Word, Excel, ...)."""

    path = str(path)
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - intentional, opens the user's own file
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


class DocumentsWindow(ctk.CTkFrame):

    columns = ("title", "category", "issued", "expires", "status")

    def __init__(self, master, repository=None):
        super().__init__(master)
        self.repository = repository or DocumentsRepository()
        self._documents = []
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        ctk.CTkLabel(self, text="Documents", font=("Segoe UI", 22, "bold")).pack(pady=(18, 2))
        ctk.CTkLabel(
            self,
            text="Create letters and spreadsheets on the FacilitiesCo letterhead, "
                 "and keep compliance documents where you can find them.",
        ).pack(pady=(0, 12))

        # --- Create new from template ---
        create_row = ctk.CTkFrame(self)
        create_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(create_row, text="Create new:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=(10, 6))
        ctk.CTkButton(create_row, text="📄  New Letter", command=self.new_letter, width=150).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(create_row, text="📊  New Spreadsheet", command=self.new_spreadsheet, width=170).pack(side="left", padx=5, pady=8)

        # --- Library actions ---
        action_row = ctk.CTkFrame(self)
        action_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(action_row, text="Library:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=(10, 6))
        ctk.CTkButton(action_row, text="＋  Add Document", command=self.add_document, width=150).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(action_row, text="Open", command=self.open_selected, width=90).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(action_row, text="Edit Details", command=self.edit_selected, width=120).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(action_row, text="Remove", command=self.remove_selected, width=100).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(action_row, text="Refresh", command=self.refresh, width=90).pack(side="left", padx=5, pady=8)

        filter_row = ctk.CTkFrame(self)
        filter_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(filter_row, text="Category").pack(side="left", padx=(10, 6))
        self.category_filter = ctk.CTkOptionMenu(
            filter_row, values=["All", *CATEGORIES], command=lambda _: self.refresh(), width=150
        )
        self.category_filter.set("All")
        self.category_filter.pack(side="left", padx=5, pady=8)

        ctk.CTkButton(filter_row, text="Change Storage Folder", command=self.change_root, width=180).pack(side="right", padx=10, pady=8)
        self.root_label = ctk.CTkLabel(filter_row, text="", anchor="e")
        self.root_label.pack(side="right", padx=8)

        # --- Table ---
        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.table = ttk.Treeview(table_frame, columns=self.columns, show="headings", selectmode="browse")
        headings = {
            "title": "Document", "category": "Category", "issued": "Issued",
            "expires": "Expires", "status": "Status",
        }
        widths = {"title": 380, "category": 130, "issued": 120, "expires": 120, "status": 200}
        for column in self.columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=widths[column], minwidth=90, anchor="w",
                              stretch=column == "title")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vertical.set)
        self.table.pack(side="left", fill="both", expand=True)
        vertical.pack(side="right", fill="y")
        self.table.bind("<Double-1>", lambda _event: self.open_selected())

        # Expired rows read red, expiring-soon amber - the whole point of the
        # expiry column is that it should catch the eye before a client asks.
        self.table.tag_configure("expired", foreground="#B91C1C")
        self.table.tag_configure("expiring", foreground="#B45309")

        self.status_label = ctk.CTkLabel(self, text="", anchor="w")
        self.status_label.pack(fill="x", padx=20, pady=(0, 10))

    # -------------------------------------------------------------- actions

    def refresh(self):
        category = self.category_filter.get()
        category = None if category == "All" else category

        try:
            self._documents = self.repository.list_documents(category)
            root = self.repository.get_documents_root()
        except Exception as error:  # noqa: BLE001 - surfaced to the user
            messagebox.showerror("Documents", f"Could not load documents:\n{error}")
            return

        self.root_label.configure(text=str(root))

        for row in self.table.get_children():
            self.table.delete(row)

        expiring = 0
        expired = 0
        for document in self._documents:
            days = document.days_until_expiry()
            if days is None:
                status, tags = "—", ()
            elif days < 0:
                status, tags = f"EXPIRED {abs(days)} days ago", ("expired",)
                expired += 1
            elif days <= EXPIRY_WARNING_DAYS:
                status, tags = f"Expires in {days} days", ("expiring",)
                expiring += 1
            else:
                status, tags = f"Valid ({days} days)", ()

            self.table.insert(
                "", "end", iid=document.id, tags=tags,
                values=(document.title, document.category, document.issue_date or "—",
                        document.expiry_date or "—", status),
            )

        summary = f"{len(self._documents)} document(s)."
        if expired:
            summary += f"  {expired} EXPIRED."
        if expiring:
            summary += f"  {expiring} expiring within {EXPIRY_WARNING_DAYS} days."
        self.status_label.configure(text=summary)

    # --- create from template ---

    def new_letter(self):
        self._new_from_template(LETTERHEAD_TEMPLATE, "Letter", ".docx")

    def new_spreadsheet(self):
        self._new_from_template(SPREADSHEET_TEMPLATE, "Spreadsheet", ".xlsx")

    def _new_from_template(self, template_path, label, suffix):
        if not template_path.is_file():
            messagebox.showerror(
                "Documents",
                f"The {label.lower()} template is missing:\n{template_path}\n\n"
                "Rebuild it with:\n  python modules/documents/templates/build_templates.py",
            )
            return

        default_name = f"FacilitiesCo {label} {datetime.now():%Y-%m-%d}{suffix}"
        destination = filedialog.asksaveasfilename(
            title=f"New {label}", defaultextension=suffix, initialfile=default_name,
            filetypes=[(f"{label} files", f"*{suffix}"), ("All files", "*.*")],
        )
        if not destination:
            return

        try:
            shutil.copy2(template_path, destination)
            open_in_default_app(destination)
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("Documents", f"Could not create the {label.lower()}:\n{error}")
            return

        self.status_label.configure(text=f"Created {destination}")

    # --- library ---

    def add_document(self):
        source = filedialog.askopenfilename(
            title="Add a document",
            filetypes=[("Documents", "*.pdf *.docx *.doc *.xlsx *.xls *.png *.jpg *.jpeg"),
                       ("All files", "*.*")],
        )
        if not source:
            return

        dialog = DocumentDetailsDialog(self, title="Add Document",
                                       initial_title=Path(source).stem)
        details = dialog.result
        if details is None:
            return

        try:
            self.repository.add_document(source_path=source, **details)
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("Documents", f"Could not add the document:\n{error}")
            return
        self.refresh()

    def _selected_document(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showinfo("Documents", "Select a document first.")
            return None
        return self.repository.get(selection[0])

    def open_selected(self):
        document = self._selected_document()
        if document is None:
            return
        path = self.repository.file_path(document)
        if not path.is_file():
            messagebox.showerror(
                "Documents",
                f"The stored file is missing:\n{path}\n\n"
                "It may have been moved or deleted outside FC Hub.",
            )
            return
        open_in_default_app(path)

    def edit_selected(self):
        document = self._selected_document()
        if document is None:
            return
        dialog = DocumentDetailsDialog(
            self, title="Edit Document", initial_title=document.title,
            initial_category=document.category, initial_issue=document.issue_date,
            initial_expiry=document.expiry_date, initial_notes=document.notes,
        )
        if dialog.result is None:
            return
        try:
            self.repository.update_document(document.id, **dialog.result)
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("Documents", f"Could not update the document:\n{error}")
            return
        self.refresh()

    def remove_selected(self):
        document = self._selected_document()
        if document is None:
            return
        if not messagebox.askyesno(
            "Remove document",
            f"Remove '{document.title}' from the library and delete FC Hub's stored copy?\n\n"
            "The original file you added it from is not touched.",
        ):
            return
        try:
            self.repository.delete_document(document.id)
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("Documents", f"Could not remove the document:\n{error}")
            return
        self.refresh()

    def change_root(self):
        current = self.repository.get_documents_root()
        chosen = filedialog.askdirectory(title="Documents storage folder", initialdir=str(current))
        if not chosen:
            return
        if not messagebox.askyesno(
            "Change storage folder",
            f"Store documents in:\n{chosen}\n\n"
            f"Files already in\n{current}\nare NOT moved automatically - "
            "copy them across yourself if you want them to stay available.",
        ):
            return
        self.repository.set_documents_root(chosen)
        self.refresh()


class DocumentDetailsDialog(ctk.CTkToplevel):
    """Title / category / dates / notes for a document."""

    def __init__(self, master, title="Document", initial_title="", initial_category="Compliance",
                 initial_issue="", initial_expiry="", initial_notes=""):
        super().__init__(master)
        self.title(title)
        self.geometry("460x360")
        self.resizable(False, False)
        self.result = None

        ctk.CTkLabel(self, text="Title").pack(anchor="w", padx=20, pady=(18, 2))
        self.title_entry = ctk.CTkEntry(self, width=420)
        self.title_entry.insert(0, initial_title)
        self.title_entry.pack(padx=20)

        ctk.CTkLabel(self, text="Category").pack(anchor="w", padx=20, pady=(12, 2))
        self.category_menu = ctk.CTkOptionMenu(self, values=list(CATEGORIES), width=420)
        self.category_menu.set(initial_category)
        self.category_menu.pack(padx=20)

        dates = ctk.CTkFrame(self, fg_color="transparent")
        dates.pack(fill="x", padx=20, pady=(12, 2))
        ctk.CTkLabel(dates, text="Issued (YYYY-MM-DD)").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(dates, text="Expires (YYYY-MM-DD)").grid(row=0, column=1, sticky="w", padx=(20, 0))
        self.issue_entry = DateEntry(dates, value=initial_issue)
        self.issue_entry.grid(row=1, column=0, sticky="w")
        self.expiry_entry = DateEntry(dates, value=initial_expiry)
        self.expiry_entry.grid(row=1, column=1, sticky="w", padx=(20, 0))

        ctk.CTkLabel(
            self, text="Leave Expires blank for documents that don't lapse.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=20, pady=(4, 0))

        ctk.CTkLabel(self, text="Notes").pack(anchor="w", padx=20, pady=(10, 2))
        self.notes_entry = ctk.CTkEntry(self, width=420)
        self.notes_entry.insert(0, initial_notes)
        self.notes_entry.pack(padx=20)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(pady=18)
        ctk.CTkButton(buttons, text="Save", command=self._save, width=120).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Cancel", command=self.destroy, width=120).pack(side="left", padx=6)

        self.transient(master)
        self.grab_set()
        self.wait_window()

    def _save(self):
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Documents", "A document needs a title.", parent=self)
            return

        for label, entry in (("Issued", self.issue_entry), ("Expires", self.expiry_entry)):
            value = entry.get().strip()
            if value and parse_date(value) is None:
                messagebox.showwarning(
                    "Documents",
                    f"'{value}' isn't a date I recognise for {label}.\n"
                    "Use YYYY-MM-DD (e.g. 2027-03-31).",
                    parent=self,
                )
                return

        self.result = {
            "title": title,
            "category": self.category_menu.get(),
            "issue_date": self.issue_entry.get().strip(),
            "expiry_date": self.expiry_entry.get().strip(),
            "notes": self.notes_entry.get().strip(),
        }
        self.destroy()
