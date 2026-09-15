# ==========================================================
# FC Hub - Shared Form Dialogs
# ----------------------------------------------------------
# Purpose:
# Generic create/edit form dialog and a required-text prompt,
# shared across modules (CRM, Settings, ...) so each module
# does not reimplement the same Toplevel form machinery.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk


class EntityFormDialog(ctk.CTkToplevel):
    """Generic create/edit form: renders text/dropdown/combo/checkbox/
    textarea fields and returns a dict of values, or None if cancelled."""

    def __init__(self, master, title, fields):
        super().__init__(master)

        self.title(title)
        self.geometry("480x560")
        self.transient(master)
        self.grab_set()
        self.lift()
        self.focus_force()

        self.fields = fields
        self.widgets = {}
        self.result = None

        ctk.CTkLabel(self, text=title, font=("Segoe UI", 18, "bold")).pack(pady=(15, 10), padx=15, anchor="w")

        form_frame = ctk.CTkScrollableFrame(self)
        form_frame.pack(fill="both", expand=True, padx=15, pady=5)

        for field in fields:
            ctk.CTkLabel(form_frame, text=field["label"], anchor="w").pack(fill="x", pady=(8, 0))
            self.widgets[field["key"]] = self._build_field(form_frame, field)

        button_row = ctk.CTkFrame(self)
        button_row.pack(fill="x", padx=15, pady=15)
        ctk.CTkButton(button_row, text="Cancel", command=self._cancel, width=100).pack(side="right", padx=5)
        ctk.CTkButton(button_row, text="Save", command=self._save, width=100).pack(side="right", padx=5)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Return>", self._on_return)
        self.bind("<Escape>", lambda _event: self._cancel())

    def _on_return(self, _event=None):
        # Enter submits the form, except inside a multi-line "textarea"
        # field (a CTkTextbox, backed by a real tk.Text widget) where
        # Enter should just insert a newline like it does everywhere
        # else in the OS.
        if isinstance(self.focus_get(), tk.Text):
            return
        self._save()

    def _build_field(self, parent, field):

        kind = field["kind"]
        initial = field.get("initial", "")

        if kind == "dropdown":
            variable = ctk.StringVar(value=initial)
            widget = ctk.CTkOptionMenu(parent, values=list(field["options"]), variable=variable)
            widget.pack(fill="x", pady=(2, 0))
            widget.variable = variable
            return widget

        if kind == "combo":
            variable = ctk.StringVar(value=initial)
            widget = ttk.Combobox(parent, textvariable=variable, values=list(field["options"]))
            widget.pack(fill="x", pady=(2, 0))
            widget.variable = variable
            return widget

        if kind == "checkbox":
            variable = ctk.BooleanVar(value=bool(initial))
            widget = ctk.CTkCheckBox(parent, text="", variable=variable)
            widget.pack(anchor="w", pady=(2, 0))
            widget.variable = variable
            return widget

        if kind == "textarea":
            widget = ctk.CTkTextbox(parent, height=80)
            widget.pack(fill="x", pady=(2, 0))
            widget.insert("1.0", initial or "")
            return widget

        widget = ctk.CTkEntry(parent)
        widget.pack(fill="x", pady=(2, 0))
        widget.insert(0, initial or "")
        return widget

    def _collect(self):

        values = {}
        for field in self.fields:
            widget = self.widgets[field["key"]]
            if field["kind"] in ("dropdown", "combo"):
                values[field["key"]] = widget.variable.get()
            elif field["kind"] == "checkbox":
                values[field["key"]] = bool(widget.variable.get())
            elif field["kind"] == "textarea":
                values[field["key"]] = widget.get("1.0", "end-1c").strip()
            else:
                values[field["key"]] = widget.get().strip()
        return values

    def _save(self):

        self.result = self._collect()
        self.destroy()

    def _cancel(self):

        self.result = None
        self.destroy()

    @classmethod
    def ask(cls, master, title, fields):
        dialog = cls(master, title, fields)
        dialog.wait_window()
        return dialog.result


class TextPromptDialog(ctk.CTkToplevel):
    """Small text prompt - required by default (used for archive
    reasons), but supports an optional pre-filled, non-required mode
    (used for editable/optional captions) via required=False."""

    def __init__(self, master, title, prompt, initial="", required=True):
        super().__init__(master)

        self.title(title)
        self.geometry("420x200")
        self.transient(master)
        self.grab_set()
        self.lift()
        self.focus_force()

        self.required = required
        self.result = None

        ctk.CTkLabel(self, text=prompt, anchor="w", wraplength=380).pack(fill="x", padx=15, pady=(15, 5))
        self.entry = ctk.CTkEntry(self)
        if initial:
            self.entry.insert(0, initial)
        self.entry.pack(fill="x", padx=15, pady=5)
        self.entry.focus_set()

        button_row = ctk.CTkFrame(self)
        button_row.pack(fill="x", padx=15, pady=15)
        ctk.CTkButton(button_row, text="Cancel", command=self._cancel, width=100).pack(side="right", padx=5)
        ctk.CTkButton(button_row, text="Confirm", command=self._confirm, width=100).pack(side="right", padx=5)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Return>", lambda _event: self._confirm())
        self.bind("<Escape>", lambda _event: self._cancel())

    def _confirm(self):

        value = self.entry.get().strip()
        if self.required and not value:
            messagebox.showwarning("Required", "A reason is required.", parent=self)
            return
        self.result = value
        self.destroy()

    def _cancel(self):

        self.result = None
        self.destroy()

    @classmethod
    def ask(cls, master, title, prompt, initial="", required=True):
        dialog = cls(master, title, prompt, initial=initial, required=required)
        dialog.wait_window()
        return dialog.result


class SavedDocumentDialog(ctk.CTkToplevel):
    """Shown after a document is filed into a client's Paperwork
    folder - replaces the old "Saved to: <long path>" info box, which
    told her where the file went but gave her no way to get to it.

    "Save a Copy..." is the escape hatch that keeps the old behaviour
    available for emailing, so auto-filing never takes an option away."""

    def __init__(self, master, title, heading, filename, customer_label, path):
        super().__init__(master)

        self.title(title)
        self.geometry("560x260")
        self.transient(master)
        self.grab_set()
        self.lift()
        self.focus_force()

        self.path = path

        ctk.CTkLabel(self, text=heading, font=("Segoe UI", 16, "bold"), anchor="w").pack(
            fill="x", padx=18, pady=(16, 4),
        )
        ctk.CTkLabel(self, text=filename, font=("Segoe UI", 13, "bold"), anchor="w").pack(
            fill="x", padx=18, pady=(4, 2),
        )
        ctk.CTkLabel(self, text=customer_label, anchor="w", text_color="#A0A0A0").pack(
            fill="x", padx=18, pady=(0, 2),
        )
        ctk.CTkLabel(
            self, text=str(path), anchor="w", text_color="#4FC3F7",
            wraplength=520, justify="left", font=("Segoe UI", 11),
        ).pack(fill="x", padx=18, pady=(0, 8))

        button_row = ctk.CTkFrame(self)
        button_row.pack(fill="x", padx=18, pady=(4, 16))
        ctk.CTkButton(button_row, text="Open PDF", command=self._open_file, width=110).pack(side="left", padx=(0, 6))
        ctk.CTkButton(button_row, text="Open Folder", command=self._open_folder, width=110).pack(side="left", padx=6)
        ctk.CTkButton(button_row, text="Save a Copy...", command=self._save_copy, width=120).pack(side="left", padx=6)
        ctk.CTkButton(button_row, text="Close", command=self.destroy, width=90).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())

    # --------------------------------------------------

    def _reveal(self, target):
        """os.startfile is Windows-only and absent on other platforms -
        the tests run headless, so never let this take the app down."""

        import os

        try:
            os.startfile(str(target))
        except Exception as error:
            messagebox.showerror("Open", f"Could not open:\n{target}\n\n{error}", parent=self)

    def _open_file(self):
        self._reveal(self.path)

    def _open_folder(self):
        self._reveal(self.path.parent)

    def _save_copy(self):
        """The old Save As behaviour, kept for emailing a copy out."""

        import shutil
        from tkinter import filedialog

        destination = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=self.path.suffix,
            initialfile=self.path.name,
            filetypes=[("PDF Files", "*.pdf")],
        )
        if not destination:
            return
        while True:
            try:
                shutil.copy2(self.path, destination)
            except Exception as error:
                retry = messagebox.askretrycancel(
                    "Save a Copy",
                    f"Could not save a copy - the file may be open in another program.\n\n{error}"
                    "\n\nClose it and press Retry, or pick a different name.",
                    parent=self,
                )
                if retry:
                    continue
                return
            break
        messagebox.showinfo("Save a Copy", f"Copy saved to:\n{destination}", parent=self)

    # --------------------------------------------------

    @classmethod
    def show(cls, master, title, heading, filename, customer_label, path):
        dialog = cls(master, title, heading, filename, customer_label, path)
        dialog.wait_window()


__all__ = ["EntityFormDialog", "TextPromptDialog", "SavedDocumentDialog"]
