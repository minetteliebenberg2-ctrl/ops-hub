# ==========================================================
# FC Hub - Proposals Windows
# ----------------------------------------------------------
# Purpose:
# Proposal creation, editing, and export interface.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import getpass
import os
from tkinter import filedialog, messagebox
import customtkinter as ctk

from modules.proposals.services import ProposalService, AccountingImportService
from modules.proposals.netting_quotes import MAINTENANCE_ITEMS, NettingQuoteService, NetType, Supplier
from core.business_settings_service import BusinessSettingsService
from core.crm_service import CRMService
from core.proposal_docx import generate_proposal_docx
from core.quote_service import QuoteService

from gui.design_tokens import COLORS

THEME_DARK_GREY = COLORS["surface_primary"]
THEME_SURFACE = COLORS["surface_secondary"]
THEME_SURFACE_LIGHT = COLORS["surface_tertiary"]
THEME_TEXT_PRIMARY = COLORS["text_primary"]
THEME_TEXT_SECONDARY = COLORS["text_secondary"]


def current_actor():

    try:
        return getpass.getuser()
    except Exception:
        return ""


class ProposalsPanel(ctk.CTkFrame):
    """Proposals utilities as an embeddable frame - extracted from
    ProposalsHub 2026-08-07 so it can be used both as its own Toplevel
    (unchanged, other entry points still open ProposalsHub directly)
    and as a tab inside modules/quotes/windows.py:QuotesMainWindow
    (module-nav consolidation: "I would like it to open from one
    window" - Minette, 2026-08-04, scope confirmed 2026-08-07). The
    editor/utility windows this launches (ProposalFormWindow,
    NettingQuoteBuilderWindow, etc.) stay their own Toplevels either
    way - same precedent as CRM, where the Customers list is a tab but
    CustomerDetailWindow still opens as its own window."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=THEME_DARK_GREY)

        ctk.CTkLabel(
            self,
            text="Create quotes, proposals, and invoices with integrated client and accounting data.",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
            justify="center",
        ).pack(pady=(20, 20), padx=20)

        button_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        button_frame.pack(pady=20, padx=20, fill="both", expand=True)

        buttons = [
            ("📋 New Proposal", self.new_proposal),
            ("📂 Open Saved Proposal", self.open_saved_proposal),
            ("🌐 Shade Netting Quotes", self.open_netting_quotes),
            ("📸 Gallery Manager", self.open_gallery),
            ("💳 Accounting Import", self.open_accounting),
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
            ).pack(pady=8, fill="x")

        self.editor_window = None
        self.open_windows = set()

    def new_proposal(self):
        if self.editor_window is None or not self.editor_window.winfo_exists():
            self.editor_window = ProposalFormWindow(self)
        else:
            self.editor_window.lift()
            self.editor_window.focus()

    def open_saved_proposal(self):
        from tkinter import simpledialog
        service = ProposalService()
        proposals = service.list_proposals()
        if not proposals:
            messagebox.showinfo("Open Proposal", "No saved proposals found.", parent=self)
            return
        choices = [f"{p.proposal_id}  —  {p.client.company_name or '(no client)'}  [{p.proposal_date}]" for p in proposals]
        choice = simpledialog.askstring(
            "Open Proposal",
            "Saved proposals (enter the ID, e.g. PROP-0001):\n\n" + "\n".join(choices),
            parent=self,
        )
        if not choice:
            return
        proposal_id = choice.strip().split()[0]
        proposal = service.get_proposal(proposal_id)
        if proposal is None:
            messagebox.showerror("Not Found", f'No proposal with ID "{proposal_id}".', parent=self)
            return
        if self.editor_window is None or not self.editor_window.winfo_exists():
            self.editor_window = ProposalFormWindow(self, proposal=proposal)
        else:
            self.editor_window.lift()
            self.editor_window.focus()

    def open_netting_quotes(self):
        window = NettingQuoteBuilderWindow(self)
        self.open_windows.add(window)

    def open_gallery(self):
        window = GalleryManagerWindow(self)
        self.open_windows.add(window)

    def open_accounting(self):
        window = AccountingImportWindow(self)
        self.open_windows.add(window)


class ProposalsHub(ctk.CTkToplevel):
    """Dockable hub launcher for Proposals utilities - thin Toplevel
    wrapper around ProposalsPanel (see its docstring). Still used by
    modules/proposals/module.py's own ProposalsModuleWindow entry
    point; QuotesMainWindow embeds ProposalsPanel directly instead of
    going through this wrapper.

    Must be a Toplevel, not a second ctk.CTk() root - the main app
    already has one running mainloop(), and a second full Tk root
    created mid-session doesn't get serviced by any mainloop, so it
    silently never becomes visible/responsive (looks like "nothing
    happens" when the launching button is clicked)."""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Proposals Hub")
        self.geometry("500x420")
        self.resizable(False, False)
        self.configure(fg_color=THEME_DARK_GREY)

        ctk.CTkLabel(
            self,
            text="Proposals Hub",
            font=("Segoe UI", 24, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(20, 20))

        self.panel = ProposalsPanel(self)
        self.panel.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        ctk.CTkButton(
            self,
            text="Close Hub",
            command=self.destroy,
            width=200,
            fg_color=COLORS["button_secondary"],
            hover_color=COLORS["button_secondary_hover"],
        ).pack(pady=(0, 20))

    def new_proposal(self):
        self.panel.new_proposal()

    def open_gallery(self):
        self.panel.open_gallery()

    def open_accounting(self):
        self.panel.open_accounting()


class ProposalFormWindow(ctk.CTkToplevel):
    """Section-based form editor for the FacilitiesCo Proposal document.

    The proposal .docx (cover, Scope of Work, Site Inspection, Technical
    Specs, Why Invest, Types of Structures, Clients, closing) is a
    multi-section narrative document, not a line-item invoice - so unlike
    QuotesWindow/QuoteDetailWindow this editor is a form whose fields map
    directly onto the variable parts of that template."""

    TIMELINE_LABELS = [
        "1. Site Inspection", "2. Quotation", "3. Order Confirmation",
        "4. Fabrication", "5. Installation", "6. Final Inspection",
    ]

    def __init__(self, parent, proposal=None):
        super().__init__(parent)

        self.title("Proposal Editor")
        self.geometry("1200x750")
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)
        self.lift()

        self.service = ProposalService()
        self.crm_service = CRMService()
        self.proposal = proposal if proposal is not None else self.service.create_proposal("Proposal")
        self.site_photo_paths = list(self.proposal.site_photos or [])
        self.site_photo_rotations = dict(self.proposal.photo_rotations or {})
        self.logo_path_var = ctk.StringVar(value=self.proposal.client_logo_path or "")
        self._thumb_refs = []  # prevent GC of thumbnail PhotoImages

        self._build_ui()
        if proposal is not None:
            self._populate_form()

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=THEME_DARK_GREY)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            scroll,
            text="Proposal Editor",
            font=("Segoe UI", 18, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(0, 15), anchor="w")

        self.entries = {}

        # --- Cover section ---
        cover = self._section(scroll, "Cover Page")
        row = ctk.CTkFrame(cover, fg_color=THEME_SURFACE)
        row.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkLabel(row, text="Company:", text_color=THEME_TEXT_SECONDARY, width=110, anchor="w").pack(side="left", padx=5)
        self.company_entry = ctk.CTkEntry(row, placeholder_text="Enter company name")
        self.company_entry.pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(row, text="Load from CRM", command=self._load_from_crm, width=120).pack(side="left", padx=5)

        self._field(cover, "attention", "Attention (Contact Person)")
        self._field(cover, "site", "Site (Name / Address)")

        logo_row = ctk.CTkFrame(cover, fg_color=THEME_SURFACE)
        logo_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(logo_row, text="Client Logo:", text_color=THEME_TEXT_SECONDARY, width=110, anchor="w").pack(side="left", padx=5)
        ctk.CTkEntry(logo_row, textvariable=self.logo_path_var, state="disabled").pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(logo_row, text="Browse...", command=self._pick_logo, width=90).pack(side="left", padx=5)

        # --- Scope of Work / Site Details ---
        scope = self._section(scroll, "Scope of Work — Site Details")
        self._field(scope, "site_area", "Site / Area (e.g. Directors Parking)")
        self._field(scope, "structure_colour", "Structure Colour")
        self._field(scope, "netting_colour", "Netting Colour")
        self._field(scope, "netting_size", "Netting Size (Single/Double/Triple)")
        self._field(scope, "dimensions", "Dimensions (Width x Length)")

        # --- Timeline ---
        timeline = self._section(scroll, "Project Timeline (durations)")
        self.timeline_entries = []
        for label in self.TIMELINE_LABELS:
            row = ctk.CTkFrame(timeline, fg_color=THEME_SURFACE)
            row.pack(fill="x", padx=10, pady=3)
            ctk.CTkLabel(row, text=label, text_color=THEME_TEXT_SECONDARY, width=160, anchor="w").pack(side="left", padx=5)
            entry = ctk.CTkEntry(row, placeholder_text="e.g. 3-5 days")
            entry.pack(side="left", padx=5, expand=True, fill="x")
            self.timeline_entries.append(entry)

        # --- Site Inspection ---
        inspection = self._section(scroll, "Site Inspection")
        photo_row = ctk.CTkFrame(inspection, fg_color=THEME_SURFACE)
        photo_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(photo_row, text="Add Site Photos...", command=self._pick_photos, width=150).pack(side="left", padx=5)
        self.photo_count_label = ctk.CTkLabel(photo_row, text="0 photos added", text_color=THEME_TEXT_SECONDARY)
        self.photo_count_label.pack(side="left", padx=10)

        # Thumbnail strip for selected photos (with rotate buttons)
        self._thumb_strip = ctk.CTkFrame(inspection, fg_color=THEME_SURFACE)
        self._thumb_strip.pack(fill="x", padx=10, pady=(0, 5))

        self._field(inspection, "net_double_qty", "Net Replacement — Double Qty")
        self._field(inspection, "net_triple_qty", "Net Replacement — Triple Qty")
        self._field(inspection, "painting_light", "Painting — Light (# structures)")
        self._field(inspection, "painting_medium", "Painting — Medium (# structures)")
        self._field(inspection, "painting_full", "Painting — Full (# structures)")

        # --- Actions ---
        action_frame = ctk.CTkFrame(scroll, fg_color=THEME_DARK_GREY)
        action_frame.pack(fill="x", pady=15)

        ctk.CTkButton(
            action_frame, text="Export as DOCX", command=self._export_docx,
            fg_color="#00AA00", hover_color="#008800",
        ).pack(side="left", padx=5)

        ctk.CTkButton(action_frame, text="Save", command=self._save).pack(side="left", padx=5)

    def _section(self, parent, title):
        frame = ctk.CTkFrame(parent, fg_color=THEME_SURFACE)
        frame.pack(fill="x", pady=8)
        ctk.CTkLabel(
            frame, text=title, font=("Segoe UI", 12, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(10, 5), padx=10, anchor="w")
        return frame

    def _field(self, parent, key, label, placeholder=""):
        row = ctk.CTkFrame(parent, fg_color=THEME_SURFACE)
        row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row, text=label + ":", text_color=THEME_TEXT_SECONDARY, width=220, anchor="w").pack(side="left", padx=5)
        entry = ctk.CTkEntry(row, placeholder_text=placeholder)
        entry.pack(side="left", padx=5, expand=True, fill="x")
        self.entries[key] = entry
        return entry

    def _load_from_crm(self):
        customers = self.crm_service.list_customers()
        if not customers:
            messagebox.showwarning("No Customers", "No customers found in CRM. Add one first.")
            return

        dialog = ctk.CTkToplevel(self.winfo_toplevel())
        dialog.title("Select Customer")
        dialog.geometry("400x400")
        dialog.configure(fg_color=THEME_DARK_GREY)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Select Customer", font=("Segoe UI", 14, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=10)

        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(dialog, textvariable=search_var, placeholder_text="Search customer name or email...")
        search_entry.pack(pady=10, padx=20, fill="x")

        list_frame = ctk.CTkScrollableFrame(dialog, fg_color=THEME_SURFACE)
        list_frame.pack(pady=10, padx=20, fill="both", expand=True)

        def populate_list(term=""):
            for widget in list_frame.winfo_children():
                widget.destroy()
            filtered = self.crm_service.search_customers(term) if term else customers
            for customer in filtered:
                ctk.CTkButton(
                    list_frame,
                    text=f"{customer.name} ({customer.email})",
                    command=lambda c=customer: self._select_customer(c, dialog),
                    fg_color=THEME_SURFACE_LIGHT,
                    hover_color=THEME_SURFACE,
                    height=35,
                    anchor="w",
                ).pack(pady=5, fill="x")
            if not filtered:
                ctk.CTkLabel(list_frame, text="No customers found", text_color=THEME_TEXT_SECONDARY).pack(pady=20)

        populate_list()

        def on_search(*args):
            populate_list(search_var.get())

        search_var.trace("w", on_search)

    def _select_customer(self, customer, dialog):
        self.proposal.client.company_name = customer.name
        self.proposal.client.email = customer.email
        self.proposal.client.phone = customer.phone
        self.proposal.client.customer_id = customer.id

        self.company_entry.delete(0, "end")
        self.company_entry.insert(0, customer.name)

        dialog.destroy()
        messagebox.showinfo("Loaded", f"Customer '{customer.name}' loaded into proposal", parent=self)

    def _pick_logo(self):
        filename = filedialog.askopenfilename(
            title="Select client logo",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("All Files", "*.*")],
        )
        if filename:
            self.logo_path_var.set(filename)

    def _resolve_customer_id(self):
        cid = getattr(self.proposal.client, "customer_id", None) or ""
        if cid:
            return cid
        name = getattr(self.proposal.client, "company_name", None) or ""
        if not name.strip():
            return ""
        matches = self.crm_service.search_customers(name.strip())
        for c in matches:
            if c.name.strip().lower() == name.strip().lower():
                self.proposal.client.customer_id = c.id
                return c.id
        return ""

    def _refresh_thumb_strip(self):
        """Rebuild the thumbnail strip showing selected photos with rotate buttons."""
        for widget in self._thumb_strip.winfo_children():
            widget.destroy()
        self._thumb_refs = []

        if not self.site_photo_paths:
            return

        from PIL import Image as _PIL, ImageTk

        for i, path in enumerate(self.site_photo_paths):
            tile = ctk.CTkFrame(self._thumb_strip, fg_color=THEME_SURFACE_LIGHT, corner_radius=4)
            tile.grid(row=0, column=i, padx=3, pady=4, sticky="n")

            try:
                pil = _PIL.open(path)
                # Apply EXIF auto-orient for display
                from core.proposal_docx import _auto_orient
                pil = _auto_orient(pil)
                # Apply manual rotation for display
                angle = self.site_photo_rotations.get(path, 0)
                if angle:
                    pil = pil.rotate(-angle, expand=True)
                pil.thumbnail((80, 80), _PIL.Resampling.LANCZOS)
                tk_img = ImageTk.PhotoImage(pil)
                self._thumb_refs.append(tk_img)
                ctk.CTkLabel(tile, image=tk_img, text="").pack(padx=2, pady=(2, 0))
            except Exception:
                ctk.CTkLabel(tile, text="\U0001F4F7", font=("Segoe UI", 20),
                             text_color=THEME_TEXT_SECONDARY).pack(padx=2, pady=(2, 0))

            def _rotate(p=path):
                self.site_photo_rotations[p] = (self.site_photo_rotations.get(p, 0) + 90) % 360
                self._refresh_thumb_strip()

            ctk.CTkButton(tile, text="↻", width=28, height=22,
                          font=("Segoe UI", 14), command=_rotate).pack(pady=(1, 2))

    def _pick_photos(self):
        filenames = filedialog.askopenfilenames(
            title="Select site photos (up to 8)",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("All Files", "*.*")],
        )
        if filenames:
            self.site_photo_paths.extend(filenames)
            self.site_photo_paths = self.site_photo_paths[:8]
            self.photo_count_label.configure(text=f"{len(self.site_photo_paths)} photo(s) added")
            self._refresh_thumb_strip()

    def _populate_form(self):
        """Fill UI fields from an existing ProposalData (when opening a saved proposal)."""
        p = self.proposal
        self.company_entry.delete(0, "end")
        self.company_entry.insert(0, p.client.company_name or "")
        for key in ("attention", "site", "site_area", "structure_colour", "netting_colour",
                    "netting_size", "dimensions", "net_double_qty", "net_triple_qty",
                    "painting_light", "painting_medium", "painting_full"):
            if key in self.entries:
                self.entries[key].delete(0, "end")
                self.entries[key].insert(0, getattr(p, key, "") or "")
        for i, entry in enumerate(self.timeline_entries):
            val = p.timeline_durations[i] if i < len(p.timeline_durations) else ""
            entry.delete(0, "end")
            entry.insert(0, val or "")
        self.photo_count_label.configure(text=f"{len(self.site_photo_paths)} photo(s) added")
        self.site_photo_rotations = dict(self.proposal.photo_rotations or {})
        self._refresh_thumb_strip()

    def _collect(self):
        """Copy form field values onto the in-memory ProposalData object."""
        p = self.proposal
        p.client.company_name = self.company_entry.get().strip() or p.client.company_name
        p.attention = self.entries["attention"].get().strip()
        p.site = self.entries["site"].get().strip()
        p.client_logo_path = self.logo_path_var.get().strip()
        p.site_area = self.entries["site_area"].get().strip()
        p.structure_colour = self.entries["structure_colour"].get().strip()
        p.netting_colour = self.entries["netting_colour"].get().strip()
        p.netting_size = self.entries["netting_size"].get().strip()
        p.dimensions = self.entries["dimensions"].get().strip()
        p.timeline_durations = [e.get().strip() for e in self.timeline_entries]
        p.net_double_qty = self.entries["net_double_qty"].get().strip()
        p.net_triple_qty = self.entries["net_triple_qty"].get().strip()
        p.painting_light = self.entries["painting_light"].get().strip()
        p.painting_medium = self.entries["painting_medium"].get().strip()
        p.painting_full = self.entries["painting_full"].get().strip()
        p.site_photos = list(self.site_photo_paths)
        p.photo_rotations = dict(self.site_photo_rotations)
        return p

    def _export_docx(self):
        if not self.company_entry.get().strip():
            messagebox.showwarning("Missing Company", "Enter or load a client company name first.", parent=self)
            return

        default_name = f"{self.proposal.proposal_id}_{self.company_entry.get().strip()}.docx"

        # Auto-file into the customer's Paperwork folder when possible.
        filename = None
        customer_id = self._resolve_customer_id()
        if customer_id:
            try:
                from core.client_document_saver import ClientDocumentSaver, safe_filename
                customer = self.crm_service.get_customer(customer_id)
                if customer:
                    saver = ClientDocumentSaver()
                    path = saver.paperwork_path(customer, safe_filename(default_name))
                    if path:
                        filename = str(path)
            except Exception:
                pass

        if not filename:
            filename = filedialog.asksaveasfilename(
                defaultextension=".docx",
                filetypes=[("Word Files", "*.docx")],
                initialfile=default_name,
                parent=self,
            )
        if not filename:
            return

        data = self._collect()
        include_terms = getattr(self, "_include_terms_var", None)
        include_terms = include_terms.get() if include_terms else False
        try:
            generate_proposal_docx(data, filename, include_terms=include_terms,
                                   photo_rotations=data.photo_rotations)
        except Exception as error:
            messagebox.showerror("Export Failed", str(error), parent=self)
            return

        messagebox.showinfo("Export Complete", f"Proposal exported to:\n{filename}", parent=self)

    def _save(self):
        self._collect()
        try:
            self.service.save_proposal(self.proposal)
        except Exception as error:
            messagebox.showerror("Save Failed", str(error), parent=self)
            return
        messagebox.showinfo("Saved", f"Proposal {self.proposal.proposal_id} saved.", parent=self)


class GalleryManagerWindow(ctk.CTkToplevel):
    """Gallery manager for before/during/after images"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Gallery Manager")
        self.geometry("1200x750")
        self.configure(fg_color=THEME_DARK_GREY)

        main_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            main_frame,
            text="Gallery Manager",
            font=("Segoe UI", 18, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(0, 15))

        ctk.CTkLabel(
            main_frame,
            text="Organize project photos: Before, During, After",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
        ).pack(pady=(0, 20))

        # Gallery tabs
        tabs = ctk.CTkTabview(main_frame, fg_color=THEME_SURFACE)
        tabs.pack(fill="both", expand=True)

        for phase in ["Before", "During", "After"]:
            tab = tabs.add(phase)

            ctk.CTkLabel(
                tab,
                text=f"[{phase} images will display here with EXIF metadata]",
                text_color=THEME_TEXT_SECONDARY,
                font=("Segoe UI", 10),
            ).pack(pady=40, fill="both", expand=True)

            ctk.CTkButton(
                tab,
                text=f"Add {phase} Image",
                command=lambda p=phase: self._add_image(p),
            ).pack(pady=10, padx=20, fill="x")

    def _add_image(self, phase):
        filename = filedialog.askopenfilename(
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.gif"), ("All Files", "*.*")]
        )
        if filename:
            messagebox.showinfo("Added", f"Image added to {phase} (placeholder)")


class AccountingImportWindow(ctk.CTkToplevel):
    """Window for importing accounting data"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Accounting Import")
        self.geometry("1200x750")
        self.configure(fg_color=THEME_DARK_GREY)

        self.import_service = AccountingImportService()

        main_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            main_frame,
            text="Accounting Import",
            font=("Segoe UI", 18, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(0, 20))

        ctk.CTkLabel(
            main_frame,
            text="Import financial data from various sources",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
        ).pack(pady=(0, 30))

        button_frame = ctk.CTkFrame(main_frame, fg_color=THEME_DARK_GREY)
        button_frame.pack(fill="x", pady=20)

        ctk.CTkButton(
            button_frame,
            text="Import from PDF (Bank Statement)",
            command=self._import_pdf,
            height=50,
        ).pack(pady=10, fill="x")

        ctk.CTkButton(
            button_frame,
            text="Import from Excel (Financial Data)",
            command=self._import_excel,
            height=50,
        ).pack(pady=10, fill="x")

        ctk.CTkButton(
            button_frame,
            text="Import from CSV (Transactions)",
            command=self._import_csv,
            height=50,
        ).pack(pady=10, fill="x")

        info_frame = ctk.CTkFrame(main_frame, fg_color=THEME_SURFACE)
        info_frame.pack(fill="both", expand=True, pady=20)

        ctk.CTkLabel(
            info_frame,
            text="Import Status",
            font=("Segoe UI", 11, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(10, 5), padx=10, anchor="w")

        self.status_label = ctk.CTkLabel(
            info_frame,
            text="Ready to import",
            text_color=THEME_TEXT_SECONDARY,
            font=("Segoe UI", 10),
            justify="left",
        )
        self.status_label.pack(pady=10, padx=10, fill="both", expand=True)

    def _import_pdf(self):
        filename = filedialog.askopenfilename(
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if filename:
            data = self.import_service.import_from_pdf(filename)
            self.status_label.configure(text=f"✓ PDF imported: {filename}\nStatus: {data['status']}")

    def _import_excel(self):
        filename = filedialog.askopenfilename(
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
        )
        if filename:
            data = self.import_service.import_from_excel(filename)
            self.status_label.configure(text=f"✓ Excel imported: {filename}\nStatus: {data['status']}")

    def _import_csv(self):
        filename = filedialog.askopenfilename(
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if filename:
            self.status_label.configure(text=f"✓ CSV imported: {filename}\nStatus: ready_for_import")


class ProposalsModuleWindow(ctk.CTkFrame):
    """Module frame - launches hub with quick access"""

    def __init__(self, master):
        super().__init__(master)

        self.configure(fg_color=THEME_DARK_GREY)
        self.hub = None

        ctk.CTkLabel(
            self,
            text="Proposals Hub",
            font=("Segoe UI", 22, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(20, 30))

        info_frame = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        info_frame.pack(pady=20, padx=40, fill="both", expand=True)

        ctk.CTkLabel(
            info_frame,
            text="Create proposals with integrated client, gallery, and accounting data.\n\nFor quotes and invoices, use the Quotes and Accounting modules.",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
            justify="center",
        ).pack(pady=20, padx=20)

        button_frame = ctk.CTkFrame(info_frame, fg_color=THEME_SURFACE)
        button_frame.pack(pady=20, padx=20, fill="x")

        buttons = [
            ("📋 New Proposal", self._new_proposal),
            ("📸 Gallery", self._open_gallery),
            ("💳 Accounting", self._open_accounting),
        ]

        for label, command in buttons:
            ctk.CTkButton(
                button_frame,
                text=label,
                command=command,
                height=40,
                font=("Segoe UI", 11),
            ).pack(pady=5, fill="x")

    def _ensure_hub(self):
        if self.hub is None or not self.hub.winfo_exists():
            self.hub = ProposalsHub(self.winfo_toplevel())
        return self.hub

    def _new_proposal(self):
        hub = self._ensure_hub()
        hub.new_proposal()

    def _open_gallery(self):
        hub = self._ensure_hub()
        hub.open_gallery()

    def _open_accounting(self):
        hub = self._ensure_hub()
        hub.open_accounting()


class NettingQuoteBuilderWindow(ctk.CTkToplevel):
    """Window for building shade netting quotes with pricing comparison"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Shade Netting Quote Builder")
        self.geometry("1200x750")
        self.configure(fg_color=THEME_DARK_GREY)

        self.service = NettingQuoteService()
        self.crm_service = CRMService()
        self.quote_service = QuoteService()
        self.business_settings = BusinessSettingsService()
        self.current_quote = None

        self._build_ui()

    def _build_ui(self):
        """Build the quote builder UI"""

        main_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Title
        ctk.CTkLabel(
            main_frame,
            text="Shade Netting Quote Builder",
            font=("Segoe UI", 18, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(0, 20))

        # Customer / Site — required before saving as a real Quote
        customer_frame = ctk.CTkFrame(main_frame, fg_color=THEME_SURFACE)
        customer_frame.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(customer_frame, text="Customer:", text_color=THEME_TEXT_PRIMARY, font=("Segoe UI", 11, "bold")).pack(side="left", padx=(10, 5), pady=10)
        self._customers = self.crm_service.list_customers()
        customer_labels = ["(select a customer)"] + [f"{c.customer_number} — {c.name}" for c in self._customers]
        self._customer_by_label = {f"{c.customer_number} — {c.name}": c for c in self._customers}
        self.customer_var = ctk.StringVar(value=customer_labels[0])
        self.customer_dropdown = ctk.CTkOptionMenu(
            customer_frame, variable=self.customer_var, values=customer_labels,
            command=self._on_customer_changed, width=260,
        )
        self.customer_dropdown.pack(side="left", padx=5, pady=10)

        ctk.CTkLabel(customer_frame, text="Site:", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=(15, 5), pady=10)
        self.site_var = ctk.StringVar(value="(none)")
        self.site_dropdown = ctk.CTkOptionMenu(customer_frame, variable=self.site_var, values=["(none)"], width=200)
        self.site_dropdown.pack(side="left", padx=5, pady=10)
        self._site_by_label = {}

        # Options frame
        options_frame = ctk.CTkFrame(main_frame, fg_color=THEME_SURFACE)
        options_frame.pack(fill="x", pady=(0, 20))

        # Block selector
        block_frame = ctk.CTkFrame(options_frame, fg_color=THEME_SURFACE)
        block_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(block_frame, text="Block Type:", text_color=THEME_TEXT_PRIMARY, font=("Segoe UI", 11, "bold")).pack(side="left", padx=5)
        self.block_var = ctk.StringVar(value="block_a")
        for block_name, block_value in [("Block A - New Nets", "block_a"), ("Block B - Paint & Cable", "block_b"), ("Block F - Maintenance", "block_f")]:
            ctk.CTkRadioButton(block_frame, text=block_name, variable=self.block_var, value=block_value, command=self._update_options).pack(side="left", padx=10)

        # Block A options
        self.block_a_frame = ctk.CTkFrame(options_frame, fg_color=THEME_SURFACE)
        self.block_a_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(self.block_a_frame, text="Net Type:", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=5)
        self.net_type_var = ctk.StringVar(value="Double")
        net_lengths = {"Single": 8, "Double": 12, "Triple": 16}
        for net_type in ["Single", "Double", "Triple"]:
            label = f"{net_type} ({net_lengths[net_type]}m)"
            ctk.CTkRadioButton(self.block_a_frame, text=label, variable=self.net_type_var, value=net_type).pack(side="left", padx=10)

        ctk.CTkLabel(self.block_a_frame, text="Color:", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=5)
        self.color_var = ctk.StringVar(value="Charcoal")
        self.color_dropdown = ctk.CTkComboBox(self.block_a_frame, variable=self.color_var, values=self.service.get_colors_for_supplier(Supplier.KNITTEX_Z25), width=120)
        self.color_dropdown.pack(side="left", padx=5)

        ctk.CTkLabel(self.block_a_frame, text="Quantity:", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=5)
        self.qty_var = ctk.StringVar(value="1")
        self.qty_entry = ctk.CTkEntry(self.block_a_frame, textvariable=self.qty_var, width=50)
        self.qty_entry.pack(side="left", padx=5)

        ctk.CTkLabel(self.block_a_frame, text="Use for Quote:", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=5)
        self.block_a_price_var = ctk.StringVar(value="Plusnet (recommended)")
        ctk.CTkOptionMenu(
            self.block_a_frame, variable=self.block_a_price_var,
            values=["Plusnet (recommended)", "Knittex Z25", "High Tier"], width=170,
        ).pack(side="left", padx=5)

        # Margin control
        margin_frame = ctk.CTkFrame(options_frame, fg_color=THEME_SURFACE)
        margin_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(margin_frame, text="Margin %:", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=5)
        self.margin_var = ctk.StringVar(value="45")
        self.margin_entry = ctk.CTkEntry(margin_frame, textvariable=self.margin_var, width=60)
        self.margin_entry.pack(side="left", padx=5)

        # Block B options
        self.block_b_frame = ctk.CTkFrame(options_frame, fg_color=THEME_SURFACE)

        ctk.CTkLabel(self.block_b_frame, text="Structures:", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=5)
        self.structures_var = ctk.StringVar(value="2")
        ctk.CTkEntry(self.block_b_frame, textvariable=self.structures_var, width=50).pack(side="left", padx=5)

        ctk.CTkLabel(self.block_b_frame, text="Cable (m):", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=5)
        self.cable_var = ctk.StringVar(value="50")
        ctk.CTkEntry(self.block_b_frame, textvariable=self.cable_var, width=50).pack(side="left", padx=5)

        # Block F options
        self.block_f_frame = ctk.CTkFrame(options_frame, fg_color=THEME_SURFACE)

        tier_row = ctk.CTkFrame(self.block_f_frame, fg_color=THEME_SURFACE)
        tier_row.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(tier_row, text="Tier:", text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=5)
        self.tier_var = ctk.StringVar(value="standard")
        ctk.CTkRadioButton(tier_row, text="Standard", variable=self.tier_var, value="standard").pack(side="left", padx=10)
        ctk.CTkRadioButton(tier_row, text="High", variable=self.tier_var, value="high").pack(side="left", padx=10)

        # Real per-item quantities - the old version always priced a
        # fixed "example" (1 refit + 1 restitch + 1 cable) regardless of
        # what she actually needed, so saving it as a real quote would
        # have saved made-up numbers. Each item defaults to 0 (not
        # included) and only items she sets a quantity for end up on
        # the quote.
        self.maintenance_qty_vars = {}
        items_row = ctk.CTkFrame(self.block_f_frame, fg_color=THEME_SURFACE)
        items_row.pack(fill="x", padx=10, pady=10)
        for key, item in MAINTENANCE_ITEMS.items():
            item_frame = ctk.CTkFrame(items_row, fg_color=THEME_SURFACE)
            item_frame.pack(side="left", padx=8)
            ctk.CTkLabel(item_frame, text=item["description"], text_color=THEME_TEXT_PRIMARY, font=("Segoe UI", 9)).pack()
            qty_var = ctk.StringVar(value="0")
            ctk.CTkEntry(item_frame, textvariable=qty_var, width=50).pack()
            self.maintenance_qty_vars[key] = qty_var

        # Generate / Save buttons
        button_row = ctk.CTkFrame(main_frame, fg_color=THEME_DARK_GREY)
        button_row.pack(pady=(0, 20), fill="x")

        ctk.CTkButton(
            button_row,
            text="Generate Quote",
            command=self._generate_quote,
            height=40,
            fg_color="#1B7A3D",
            hover_color="#165a30",
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(
            button_row,
            text="Save as Quote",
            command=self._save_as_quote,
            height=40,
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Results frame
        self.results_frame = ctk.CTkFrame(main_frame, fg_color=THEME_SURFACE)
        self.results_frame.pack(fill="both", expand=True, pady=10)

        self.results_label = ctk.CTkLabel(
            self.results_frame,
            text="Generate a quote to see results",
            text_color=THEME_TEXT_SECONDARY,
            font=("Segoe UI", 11),
            justify="left",
        )
        self.results_label.pack(pady=20, padx=20, fill="both", expand=True)

        # Update options visibility
        self._update_options()

    def _update_options(self):
        """Show/hide block-specific options"""
        block = self.block_var.get()
        self.block_a_frame.pack_forget()
        self.block_b_frame.pack_forget()
        self.block_f_frame.pack_forget()

        if block == "block_a":
            self.block_a_frame.pack(fill="x", padx=10, pady=10)
            self.margin_var.set("45")
        elif block == "block_b":
            self.block_b_frame.pack(fill="x", padx=10, pady=10)
            self.margin_var.set("60")
        elif block == "block_f":
            self.block_f_frame.pack(fill="x", padx=10, pady=10)

    def _generate_quote(self):
        """Generate and display the quote"""
        try:
            block = self.block_var.get()

            if block == "block_a":
                net_type_map = {"Single": NetType.SINGLE, "Double": NetType.DOUBLE, "Triple": NetType.TRIPLE}
                net_type = net_type_map[self.net_type_var.get()]
                color = self.color_var.get()
                qty = int(self.qty_var.get())
                margin = float(self.margin_var.get())

                quote = self.service.create_comparison_quote(
                    net_type=net_type,
                    color=color,
                    qty=qty,
                    margin_percent=margin,
                )

                result_text = f"NET TYPE: {quote['net_type']}\nCOLOR: {quote['color']}\nQTY: {quote['qty']}\nMARGIN: {quote['margin_percent']}%\n\n"
                result_text += "KNITTEX Z25:\n"
                result_text += f"  Supply Cost:    R{quote['knittex_z25']['supply_cost']:>10,.2f}\n"
                result_text += f"  Quote Price:    R{quote['knittex_z25']['quote_price']:>10,.2f}\n"
                result_text += f"  Delivery:       R{quote['knittex_z25']['delivery']:>10,.2f}\n"
                result_text += f"  FINAL PRICE:    R{quote['knittex_z25']['final_price']:>10,.2f}\n\n"
                result_text += "PLUSNET (RECOMMENDED):\n"
                result_text += f"  Supply Cost:    R{quote['plusnet']['supply_cost']:>10,.2f}\n"
                result_text += f"  Quote Price:    R{quote['plusnet']['quote_price']:>10,.2f}\n"
                result_text += f"  Delivery:       R{quote['plusnet']['delivery']:>10,.2f}\n"
                result_text += f"  FINAL PRICE:    R{quote['plusnet']['final_price']:>10,.2f}\n\n"
                result_text += f"MARGIN DIFFERENCE: R{quote['margin_difference']:,.2f}"

            elif block == "block_b":
                num_structures = int(self.structures_var.get())
                cable_m = int(self.cable_var.get())
                margin = float(self.margin_var.get())

                quote = self.service.create_painting_cable_quote(
                    num_structures=num_structures,
                    cable_meters=cable_m if cable_m > 0 else None,
                    margin_percent=margin,
                )

                result_text = f"BLOCK B: PAINTING & CABLE\nMARGIN: {quote['margin_percent']}%\n\n"
                result_text += "LINE ITEMS:\n"
                for item in quote['line_items']:
                    result_text += f"  {item['description']:<45} R{item['total']:>10,.2f}\n"
                result_text += f"\nTOTAL COST:   R{quote['total_cost']:>10,.2f}\n"
                result_text += f"FINAL PRICE:  R{quote['total_price']:>10,.2f}"

            elif block == "block_f":
                tier = self.tier_var.get()

                items = {
                    key: int(qty_var.get())
                    for key, qty_var in self.maintenance_qty_vars.items()
                    if qty_var.get().strip() and int(qty_var.get()) > 0
                }
                if not items:
                    raise ValueError("Set a quantity for at least one maintenance item.")

                quote = self.service.create_maintenance_quote(
                    items=items,
                    tier=tier,
                )

                result_text = f"BLOCK F: MAINTENANCE\nTIER: {quote['tier'].upper()}\n\n"
                result_text += "LINE ITEMS:\n"
                for item in quote["line_items"]:
                    result_text += f"  {item['description']:<45} R{item['total']:>10,.2f}\n"
                result_text += f"\nTOTAL PRICE:  R{quote['total_price']:>10,.2f}"

            self.results_label.configure(text=result_text)
            self.current_quote = quote
            self.current_quote_block = block

        except Exception as e:
            self.results_label.configure(text=f"Error: {str(e)}", text_color="#FF6B6B")

    def _on_customer_changed(self, _value=None):
        """Refresh the Site dropdown to the selected customer's real
        sites (e.g. Cavaleros' Block A-F properties) - unrelated to
        this window's own "Block A/B/F" quote-category radio buttons
        above, which are about what's being quoted, not where."""

        customer = self._customer_by_label.get(self.customer_var.get())
        self._site_by_label = {}
        if customer is None:
            self.site_dropdown.configure(values=["(none)"])
            self.site_var.set("(none)")
            return

        sites = self.crm_service.list_sites(customer.id)
        labels = ["(none)"] + [site.name for site in sites]
        self._site_by_label = {site.name: site.id for site in sites}
        self.site_dropdown.configure(values=labels)
        self.site_var.set("(none)")

    def _save_as_quote(self):
        """Turn the last generated calculation into a real, saved Quote
        linked to a customer - previously "Generate Quote" only printed
        a result to a text box, with nothing saved or findable
        afterward; she had to manually re-type the numbers into an
        actual quote."""

        if self.current_quote is None:
            messagebox.showwarning("Save as Quote", "Generate a quote first.", parent=self)
            return

        customer = self._customer_by_label.get(self.customer_var.get())
        if customer is None:
            messagebox.showwarning("Save as Quote", "Select a customer first.", parent=self)
            return
        site_id = self._site_by_label.get(self.site_var.get(), "")

        block = self.current_quote_block
        quote_data = self.current_quote
        line_items = []

        if block == "block_a":
            structure_type_by_net = {
                "Single": "New Net - Single", "Double": "New Net - Double", "Triple": "New Net - Triple",
            }
            structure_type = structure_type_by_net.get(self.net_type_var.get(), "New Net - Double")
            qty = quote_data["qty"]
            choice = self.block_a_price_var.get()
            if choice.startswith("Knittex"):
                final_price, supplier_label = quote_data["knittex_z25"]["final_price"], "Knittex Z25"
            elif choice.startswith("High"):
                final_price, supplier_label = quote_data["high_tier_price"], "High Tier"
            else:
                final_price, supplier_label = quote_data["plusnet"]["final_price"], "Plusnet"
            unit_price_minor = round((final_price / qty) * 100)
            description = f"{quote_data['color']} {quote_data['net_type']} netting - {supplier_label}"
            line_items.append((structure_type, description, qty, unit_price_minor))

        elif block == "block_b":
            for item in quote_data["line_items"]:
                structure_type = "Replace Cable" if "Cable" in item["description"] else "Repaint Structure"
                unit_price_minor = round(item["unit_price"] * 100)
                line_items.append((structure_type, item["description"], item["qty"], unit_price_minor))

        elif block == "block_f":
            structure_type_by_key = {
                "refit_net": "Refit Net", "restitch_net": "Restitch Net", "retensioning": "Retensioning",
                "replace_cable": "Replace Cable", "repaint_structure": "Repaint Structure",
            }
            tier = self.tier_var.get()
            for key, qty_var in self.maintenance_qty_vars.items():
                qty = int(qty_var.get()) if qty_var.get().strip() else 0
                if qty <= 0:
                    continue
                unit_price_minor = round(MAINTENANCE_ITEMS[key][tier] * 100)
                line_items.append((structure_type_by_key[key], MAINTENANCE_ITEMS[key]["description"], qty, unit_price_minor))

        if not line_items:
            messagebox.showwarning("Save as Quote", "Nothing to save.", parent=self)
            return

        try:
            quote = self.quote_service.new_quote(customer.id, site_id)
            quote = self.quote_service.save_quote(quote, current_actor())
            for structure_type, description, qty, unit_price_minor in line_items:
                line_item = self.quote_service.new_line_item(quote.id)
                line_item.structure_type = structure_type
                line_item.description = description
                line_item.quantity = qty
                line_item.unit_price_minor = unit_price_minor
                self.quote_service.save_line_item(line_item)
        except ValueError as error:
            messagebox.showerror("Save as Quote", str(error), parent=self)
            return

        messagebox.showinfo("Save as Quote", f"Saved as a real quote for {customer.name}.", parent=self)

        from modules.quotes.windows import QuoteDetailWindow

        QuoteDetailWindow(self, self.quote_service, self.crm_service, self.business_settings, quote.id)
