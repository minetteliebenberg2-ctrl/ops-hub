# ==========================================================
# FC Hub - Communications Windows Layout Test
# ----------------------------------------------------------
# Purpose:
# Test prototype showing separate windows approach for
# Communications utilities (Mailbox Intelligence, Contact
# Intelligence, Contact Review Queue). Allows working with
# multiple views simultaneously and incorporating images.
#
# Author: Minette & James
# Version: 1.0 (Test/Prototype)
# ==========================================================

import customtkinter as ctk
from tkinter import messagebox


class CommunicationsHubWindow(ctk.CTk):
    """Main hub window - launches separate utility windows"""

    def __init__(self):
        super().__init__()

        self.title("Communications Hub")
        self.geometry("500x400")
        self.resizable(False, False)

        ctk.CTkLabel(
            self,
            text="Communications Hub",
            font=("Segoe UI", 24, "bold"),
        ).pack(pady=(20, 30))

        ctk.CTkLabel(
            self,
            text="Open utilities as separate windows to work with multiple views simultaneously.",
            font=("Segoe UI", 11),
            text_color="gray",
        ).pack(pady=(0, 30), padx=20)

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(pady=20, padx=20, fill="both", expand=True)

        ctk.CTkButton(
            button_frame,
            text="📧 Mailbox Intelligence",
            command=self.open_mailbox_intelligence,
            height=60,
            font=("Segoe UI", 13),
        ).pack(pady=10, fill="x")

        ctk.CTkButton(
            button_frame,
            text="👥 Contact Intelligence",
            command=self.open_contact_intelligence,
            height=60,
            font=("Segoe UI", 13),
        ).pack(pady=10, fill="x")

        ctk.CTkButton(
            button_frame,
            text="✓ Contact Review Queue",
            command=self.open_review_queue,
            height=60,
            font=("Segoe UI", 13),
        ).pack(pady=10, fill="x")

        ctk.CTkButton(
            button_frame,
            text="📄 Company Proposal (Example)",
            command=self.open_proposal_example,
            height=60,
            font=("Segoe UI", 13),
        ).pack(pady=10, fill="x")

        ctk.CTkButton(
            self,
            text="Close Hub",
            command=self.quit,
            width=200,
        ).pack(pady=(0, 20))

        self.open_windows = []

    def open_mailbox_intelligence(self):
        window = MailboxIntelligenceWindow(self)
        self.open_windows.append(window)

    def open_contact_intelligence(self):
        window = ContactIntelligenceWindow(self)
        self.open_windows.append(window)

    def open_review_queue(self):
        window = ReviewQueueWindow(self)
        self.open_windows.append(window)

    def open_proposal_example(self):
        window = ProposalExampleWindow(self)
        self.open_windows.append(window)


class MailboxIntelligenceWindow(ctk.CTkToplevel):
    """Separate window for Mailbox Intelligence"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Mailbox Intelligence")
        self.geometry("900x600")

        ctk.CTkLabel(
            self,
            text="Mailbox Intelligence",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(10, 15), padx=20)

        ctk.CTkLabel(
            self,
            text="• Load and scan mailboxes\n• Identify email addresses\n• Extract signature data\n• Find duplicate emails",
            font=("Segoe UI", 11),
            justify="left",
        ).pack(pady=20, padx=20)

        ctk.CTkButton(
            self,
            text="Load Mailboxes",
            command=lambda: messagebox.showinfo("Info", "Mailbox loading functionality here"),
        ).pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(
            self,
            text="(Treeview table would display mailbox list here)",
            text_color="gray",
            font=("Segoe UI", 10),
        ).pack(pady=30, padx=20, fill="both", expand=True)


class ContactIntelligenceWindow(ctk.CTkToplevel):
    """Separate window for Contact Intelligence"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Contact Intelligence")
        self.geometry("1000x650")

        ctk.CTkLabel(
            self,
            text="Contact Intelligence",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(10, 15), padx=20)

        ctk.CTkLabel(
            self,
            text="• View collected email candidates\n• Filter by classification (New, Existing, Invalid, Automated)\n• Search and sort\n• Manage ignore list & deletions",
            font=("Segoe UI", 11),
            justify="left",
        ).pack(pady=20, padx=20)

        controls = ctk.CTkFrame(self)
        controls.pack(pady=10, padx=20, fill="x")

        ctk.CTkButton(
            controls,
            text="Collect Selected",
            width=120,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls,
            text="Ignore Selected",
            width=120,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls,
            text="Delete Selected",
            width=120,
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            self,
            text="(Treeview table with email candidates would display here)",
            text_color="gray",
            font=("Segoe UI", 10),
        ).pack(pady=40, padx=20, fill="both", expand=True)


class ReviewQueueWindow(ctk.CTkToplevel):
    """Separate window for Contact Review Queue"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Contact Review Queue")
        self.geometry("1000x650")

        ctk.CTkLabel(
            self,
            text="Contact Review Queue",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(10, 15), padx=20)

        ctk.CTkLabel(
            self,
            text="• Review candidates before CRM import\n• Approve, reject, or restore status\n• Link to existing CRM contacts\n• Launch CRM Import Wizard",
            font=("Segoe UI", 11),
            justify="left",
        ).pack(pady=20, padx=20)

        controls = ctk.CTkFrame(self)
        controls.pack(pady=10, padx=20, fill="x")

        ctk.CTkButton(
            controls,
            text="Approve",
            width=100,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls,
            text="Reject",
            width=100,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls,
            text="Import to CRM",
            width=120,
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            self,
            text="(Treeview table with pending contacts would display here)",
            text_color="gray",
            font=("Segoe UI", 10),
        ).pack(pady=40, padx=20, fill="both", expand=True)


class ProposalExampleWindow(ctk.CTkToplevel):
    """Example window showing how proposals with images would work alongside utilities"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Company Proposal (Example)")
        self.geometry("900x700")

        ctk.CTkLabel(
            self,
            text="Company Proposal",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(10, 15), padx=20)

        ctk.CTkLabel(
            self,
            text="This demonstrates how you could have proposal windows open\nalongside Communications utilities to seamlessly integrate images,\nquotes, invoices, and CRM data.",
            font=("Segoe UI", 11),
            justify="center",
            text_color="gray",
        ).pack(pady=20, padx=20)

        content = ctk.CTkFrame(self)
        content.pack(pady=20, padx=20, fill="both", expand=True)

        ctk.CTkLabel(
            content,
            text="PROPOSAL CONTENT AREA",
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=20)

        ctk.CTkLabel(
            content,
            text="[Company Logo Image would render here]",
            text_color="gray",
            font=("Segoe UI", 11),
        ).pack(pady=30, fill="both", expand=True)

        ctk.CTkLabel(
            content,
            text="[Quote/Invoice data pulled from CRM]",
            text_color="gray",
            font=("Segoe UI", 11),
        ).pack(pady=10)

        ctk.CTkButton(
            self,
            text="Insert Contact from Review Queue",
            command=lambda: messagebox.showinfo("Info", "Would insert selected contact data here"),
        ).pack(pady=10, padx=20, fill="x")


if __name__ == "__main__":
    app = CommunicationsHubWindow()
    app.mainloop()
