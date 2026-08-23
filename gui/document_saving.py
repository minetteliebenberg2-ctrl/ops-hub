# ==========================================================
# FC Hub - Document Saving
# ----------------------------------------------------------
# Purpose:
# Save a generated customer document into that customer's own
# Paperwork folder instead of asking where to put it, and show her
# where it went with a way to get to it.
#
# Shared by Quotes (Quote / Pro-Forma / Tax Invoice / Statement)
# and the Site Plan export - it lives here rather than in either
# module so neither has to import the other.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from tkinter import filedialog, messagebox

from core.client_document_saver import ClientDocumentSaver, write_with_retry
from gui.form_dialogs import SavedDocumentDialog


def file_document_for_customer(parent, customer, default_name, build, title, heading):
    """Generate a document straight into the customer's Paperwork
    folder, and show her where it went with a way to get to it.

    Replaces the Save As dialog that used to front every Quote /
    Pro-Forma / Tax Invoice / Statement - scoped with Minette
    2026-08-12 as her biggest annoyance when quoting.

    Falls back to the old Save As flow when the customer has no client
    folder yet (no customer number until first save), so an unnumbered
    customer can still get a PDF out. Returns True if something was
    written."""

    saver = ClientDocumentSaver()
    try:
        path = saver.paperwork_path(customer, default_name)
    except OSError as error:
        retry = messagebox.askretrycancel(
            title,
            f"Could not open {customer.name}'s Paperwork folder - it may be open in "
            f"another program or syncing (OneDrive).\n\n{error}\n\nClose it and press Retry.",
            parent=parent,
        )
        while retry:
            try:
                path = saver.paperwork_path(customer, default_name)
                break
            except OSError as retry_error:
                retry = messagebox.askretrycancel(
                    title,
                    f"Still could not open {customer.name}'s Paperwork folder.\n\n{retry_error}"
                    "\n\nClose it and press Retry.",
                    parent=parent,
                )
        else:
            return False

    if path is None:
        filename = filedialog.asksaveasfilename(
            parent=parent,
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=default_name,
        )
        if not filename:
            return False
        try:
            build(filename)
        except Exception as error:
            messagebox.showerror(title, f"Could not generate PDF: {error}", parent=parent)
            return False
        messagebox.showinfo(title, f"Saved to:\n{filename}", parent=parent)
        return True

    def on_locked(locked_path):
        return messagebox.askretrycancel(
            title,
            f"{locked_path.name} is open in another program, so it could not be replaced."
            "\n\nClose it and press Retry.",
            parent=parent,
        )

    try:
        saved = write_with_retry(build, path, on_locked)
    except Exception as error:
        messagebox.showerror(title, f"Could not generate PDF: {error}", parent=parent)
        return False

    if saved is None:
        return False

    customer_label = customer.name
    if customer.customer_number:
        customer_label = f"{customer.name} ({customer.customer_number})"

    SavedDocumentDialog.show(parent, title, heading, saved.name, customer_label, saved)
    return True
