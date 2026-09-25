# ==========================================================
# FC Hub - Quotes Module (Phase 3 Redesign - Light Theme)
# ----------------------------------------------------------
# Professional quote management with:
# - Quote list with status badges
# - Search/filter functionality
# - Inline detail view (back button navigation)
# - Light theme throughout
#
# Author: Claude (Redesign Phase 3)
# ==========================================================

from datetime import date
import getpass
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from gui.components.date_picker import DateEntry

from core.address import Address
from core.quote_document import balance_percent, deposit_percent
from core.business_document_pdf import generate_invoice_pdf, generate_proforma_pdf, generate_statement_pdf
from core.business_settings_service import BusinessSettingsService
from core.crm_service import CRMService
from core.picklist_service import LINE_ITEM_TYPE, PicklistService
from core.quote import format_quote_number
from core.quote_document_service import QuoteDocumentService
from core.quote_pdf import format_money, generate_quote_pdf
from core.quote_service import QuoteService, validate_document_date
from core.statement_service import StatementService
from gui.entity_table import build_entity_table
from gui.flow_layout import reflow_widgets
from gui.document_saving import file_document_for_customer
from gui.form_dialogs import EntityFormDialog, TextPromptDialog
from gui.design_tokens import COLORS, FONTS, SPACING, STATUS_COLORS


def current_actor():
    try:
        return getpass.getuser()
    except Exception:
        return ""


STATUS_COLUMNS = ("Quote #", "Customer", "Site", "Status", "Total", "Issue Date", "Expiry Date")

COLOUR_OPTIONS = []


class QuotesWindow(ctk.CTkFrame):
    """Professional quotes list view with light theme."""

    def __init__(self, master):
        super().__init__(
            master,
            fg_color=COLORS["surface_primary"],
        )

        self.quote_service = QuoteService()
        self.crm_service = CRMService()
        self.business_settings = BusinessSettingsService()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=SPACING["xxl"], pady=(SPACING["xxl"], SPACING["lg"]))

        ctk.CTkLabel(
            header_frame,
            text="Quotes",
            font=FONTS["title_lg"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            header_frame,
            text="Create, manage, and track all your quotes",
            font=FONTS["body_md"],
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", pady=(SPACING["sm"], 0))

        # Table
        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.grid(row=1, column=0, sticky="nsew", padx=SPACING["xxl"], pady=(0, SPACING["xxl"]))

        self.table = build_entity_table(
            table_frame,
            STATUS_COLUMNS,
            (
                ("Refresh", self.refresh),
                ("New Quote", self.new_quote),
                ("Open", self.open_quote),
                ("Delete Draft", self.delete_draft),
                ("Delete Quote", self.delete_quote),
                ("Statement", self.open_statement),
            ),
        )
        self.table.bind("<Double-1>", lambda _event: self.open_quote())

        self._customers_by_id = {}
        self.refresh()

    def open_statement(self):
        selected = self.table.selection()
        quote = self.quote_service.get_quote(selected[0]) if selected else None
        StatementEditorWindow(self.winfo_toplevel(), customer_id=quote.customer_id if quote else None)

    def refresh(self):
        self._customers_by_id = {c.id: c for c in self.crm_service.list_customers()}

        self.table.delete(*self.table.get_children())
        for quote in self.quote_service.list_quotes():
            customer = self._customers_by_id.get(quote.customer_id)
            site = self.crm_service.sites.get(quote.site_id) if quote.site_id else None
            self.table.insert(
                "",
                "end",
                iid=quote.id,
                text=format_quote_number(quote) if quote.quote_number else "(Draft)",
                values=(
                    format_quote_number(quote) if quote.quote_number else "(Draft)",
                    customer.name if customer else "",
                    site.name if site else "",
                    quote.status,
                    format_money(quote.total_minor, quote.currency),
                    quote.issue_date,
                    quote.expiry_date,
                ),
            )

    def _selected_quote_id(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showwarning("Quotes", "Select a quote first.", parent=self.winfo_toplevel())
            return None
        return selection[0]

    def new_quote(self):
        customers = self.crm_service.list_customers()
        if not customers:
            messagebox.showwarning("Quotes", "Create a customer in CRM first.", parent=self.winfo_toplevel())
            return

        labels = [f"{c.customer_number} — {c.name}" for c in customers]
        customer_by_label = dict(zip(labels, [c.id for c in customers]))

        result = EntityFormDialog.ask(
            self.winfo_toplevel(),
            "New Quote — Choose Customer",
            [{"key": "customer", "label": "Customer", "kind": "dropdown", "options": labels, "initial": labels[0]}],
        )
        if result is None:
            return

        customer_id = customer_by_label[result["customer"]]
        sites = self.crm_service.list_sites(customer_id)
        site_id = ""
        if sites:
            site_labels = ["(none)"] + [s.name for s in sites]
            site_by_label = {s.name: s.id for s in sites}
            site_result = EntityFormDialog.ask(
                self.winfo_toplevel(),
                "New Quote — Choose Site (optional)",
                [{"key": "site", "label": "Site", "kind": "dropdown", "options": site_labels, "initial": "(none)"}],
            )
            if site_result is None:
                return
            site_id = site_by_label.get(site_result["site"], "")

        try:
            quote = self.quote_service.new_quote(customer_id, site_id)
            saved = self.quote_service.save_quote(quote, current_actor())
        except ValueError as error:
            messagebox.showerror("Quotes", str(error), parent=self.winfo_toplevel())
            return

        self.refresh()
        QuoteDetailWindow(self.winfo_toplevel(), self.quote_service, self.crm_service, self.business_settings, saved.id, on_change=self.refresh)

    def open_quote(self):
        quote_id = self._selected_quote_id()
        if quote_id is None:
            return
        QuoteDetailWindow(self.winfo_toplevel(), self.quote_service, self.crm_service, self.business_settings, quote_id, on_change=self.refresh)

    def delete_draft(self):
        quote_id = self._selected_quote_id()
        if quote_id is None:
            return
        quote = self.quote_service.get_quote(quote_id)
        if quote is None:
            return
        if not messagebox.askyesno(
            "Delete Draft Quote",
            "Delete this draft quote permanently? Only never-issued drafts can be deleted.",
            parent=self.winfo_toplevel(),
        ):
            return
        try:
            self.quote_service.delete_draft_quote(quote_id)
        except ValueError as error:
            messagebox.showerror("Delete Draft Quote", str(error), parent=self.winfo_toplevel())
            return
        self.refresh()

    def delete_quote(self):
        quote_id = self._selected_quote_id()
        if quote_id is None:
            return
        quote = self.quote_service.get_quote(quote_id)
        if quote is None:
            return
        display_number = format_quote_number(quote)
        if not messagebox.askyesno(
            "Delete Quote",
            f"Permanently delete {display_number} ({quote.status})?\n\n"
            "This also removes any Pro-Forma or Tax Invoice already generated from it. "
            "The quote number will not be reused. This cannot be undone.",
            parent=self.winfo_toplevel(),
        ):
            return
        try:
            self.quote_service.delete_quote(quote_id)
        except ValueError as error:
            messagebox.showerror("Delete Quote", str(error), parent=self.winfo_toplevel())
            return
        self.refresh()


class QuoteDetailWindow(ctk.CTkToplevel):

    def __init__(self, master, quote_service, crm_service, business_settings, quote_id, on_change=None):
        super().__init__(master)

        self.quote_service = quote_service
        self.crm_service = crm_service
        self.business_settings = business_settings
        self.quote_id = quote_id
        self.on_change = on_change

        self.picklists = PicklistService()
        self.quote_documents = QuoteDocumentService(quote_service=quote_service)

        self.geometry("1280x700")
        self.minsize(1100, 600)
        self.transient(master)

        self.header_label = ctk.CTkLabel(self, font=("Segoe UI", 18, "bold"), anchor="w")
        self.header_label.pack(fill="x", padx=20, pady=(18, 2))
        self.subheader_label = ctk.CTkLabel(self, anchor="w", wraplength=1220, justify="left")
        self.subheader_label.pack(fill="x", padx=20, pady=(0, 6))

        # This row's content (3 label+combo pairs, a label+entry, and 2
        # buttons) is wider than the window's own default size - it used
        # to just run off the right edge with no way to reach "Change
        # Site" without manually dragging the window wider. Built as a
        # list of widgets (not packed immediately) and reflowed via
        # gui/flow_layout.py so it wraps onto a second line instead of
        # ever being cut off, whatever the window's actual width is.
        details_row = ctk.CTkFrame(self)
        details_row.pack(fill="x", padx=20, pady=(0, 10))
        details_row_widgets = []

        details_row_widgets.append(ctk.CTkLabel(details_row, text="PO Number:", anchor="w"))
        self.po_combo = ctk.CTkComboBox(details_row, width=180, values=["N/A", "TBC"])
        self.po_combo.bind("<FocusOut>", lambda _e: self._save_po_number())
        self.po_combo.bind("<Return>", lambda _e: self._save_po_number())
        self.po_combo.configure(command=lambda _v: self._save_po_number())
        details_row_widgets.append(self.po_combo)

        details_row_widgets.append(ctk.CTkLabel(details_row, text="VAT No:", anchor="w"))
        self.vat_combo = ctk.CTkComboBox(details_row, width=180, values=["N/A", "TBC"])
        self.vat_combo.bind("<FocusOut>", lambda _e: self._save_vat_number())
        self.vat_combo.bind("<Return>", lambda _e: self._save_vat_number())
        self.vat_combo.configure(command=lambda _v: self._save_vat_number())
        details_row_widgets.append(self.vat_combo)

        details_row_widgets.append(ctk.CTkLabel(details_row, text="Reg No:", anchor="w"))
        self.registration_combo = ctk.CTkComboBox(details_row, width=180, values=["N/A", "TBC"])
        self.registration_combo.bind("<FocusOut>", lambda _e: self._save_registration_number())
        self.registration_combo.bind("<Return>", lambda _e: self._save_registration_number())
        self.registration_combo.configure(command=lambda _v: self._save_registration_number())
        details_row_widgets.append(self.registration_combo)

        details_row_widgets.append(ctk.CTkLabel(details_row, text="Bill To:", anchor="w"))
        self.bill_to_entry = ctk.CTkEntry(details_row, width=220)
        self.bill_to_entry.bind("<FocusOut>", lambda _e: self._save_bill_to_name())
        self.bill_to_entry.bind("<Return>", lambda _e: self._save_bill_to_name())
        details_row_widgets.append(self.bill_to_entry)

        details_row_widgets.append(ctk.CTkButton(details_row, text="Billing / Delivery Address", command=self.edit_billing_delivery_address, width=190))
        details_row_widgets.append(ctk.CTkButton(details_row, text="Change Site", command=self.change_site, width=120))
        details_row_widgets.append(ctk.CTkButton(details_row, text="+ New Site", command=self._create_site, width=100))

        reflow_widgets(details_row, details_row_widgets)

        action_row = ctk.CTkFrame(self)
        action_row.pack(fill="x", padx=20, pady=(0, 10))
        # Nine buttons need ~1210px on one line. Packed side by side they
        # ran off the right edge on anything narrower and the last ones
        # simply weren't reachable - the same way "Change Site" and
        # "Rotate" were lost before. reflow_widgets wraps onto a second
        # row instead. Close goes last in the flow rather than packed
        # right, so it can't be overlapped by the row it shares.
        action_buttons = [
            ctk.CTkButton(action_row, text="Issue Quote", command=self.issue_quote, width=120),
            ctk.CTkButton(action_row, text="Mark Accepted", command=lambda: self.set_status("Accepted"), width=130),
            ctk.CTkButton(action_row, text="Mark Rejected", command=lambda: self.set_status("Rejected"), width=130),
            ctk.CTkButton(action_row, text="Generate PDF", command=self.generate_pdf, width=120),
            ctk.CTkButton(action_row, text="Edit Notes / Expiry", command=self.edit_quote_details, width=150),
            ctk.CTkButton(action_row, text="Create Revision", command=self.create_revision, width=130),
            ctk.CTkButton(action_row, text="Archive", command=self.archive_quote, width=100),
            ctk.CTkButton(action_row, text="Delete Quote", command=self.delete_quote, width=120),
            ctk.CTkButton(action_row, text="Close", command=self.destroy, width=90),
        ]
        reflow_widgets(action_row, action_buttons)

        doc_row = ctk.CTkFrame(self)
        doc_row.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(doc_row, text="Generate from this Quote:", anchor="w").pack(side="left", padx=(0, 8))
        ctk.CTkButton(doc_row, text="Pro-Forma", command=self.generate_pro_forma, width=110).pack(side="left", padx=4)
        # Tax Invoice slot: one "Tax Invoice" button, or Deposit + Balance
        # buttons when "Split deposit / balance" is ticked (2026-09-22).
        invoice_slot = ctk.CTkFrame(doc_row, fg_color="transparent")
        invoice_slot.pack(side="left")
        self._tax_invoice_btn = ctk.CTkButton(invoice_slot, text="Tax Invoice", command=self.generate_tax_invoice, width=110)
        # Split % comes from Business Settings (v0058), so the labels
        # are read at build time rather than baked in as a constant.
        deposit_pct = deposit_percent()
        self._deposit_invoice_btn = ctk.CTkButton(
            invoice_slot, text=f"Deposit Invoice ({deposit_pct}%)", command=self.generate_deposit_invoice, width=160,
        )
        self._balance_invoice_btn = ctk.CTkButton(
            invoice_slot, text=f"Balance Invoice ({balance_percent()}%)", command=self.generate_balance_invoice, width=160,
        )
        self._tax_invoice_btn.pack(side="left", padx=4)
        ctk.CTkButton(doc_row, text="Statement", command=self.open_statement, width=110).pack(side="left", padx=4)
        ctk.CTkButton(doc_row, text="Dates...", command=self.edit_dates, width=90).pack(side="left", padx=4)


        self._split_invoice_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            doc_row, text="Split deposit / balance",
            variable=self._split_invoice_var,
            command=self._save_split_invoice,
            width=170,
        ).pack(side="right", padx=(4, 8))

        grid_header = ctk.CTkFrame(self)
        grid_header.pack(fill="x", padx=20, pady=(0, 0))
        self.add_row_button = ctk.CTkButton(grid_header, text="+ Add Row", command=self.new_line_item, width=100)
        self.add_row_button.pack(side="left")
        self.locked_label = ctk.CTkLabel(
            grid_header,
            text="This quote is Issued — line items are locked. Use Create Revision to make changes.",
            text_color="#E0A030",
        )

        self.grid_scroll = ctk.CTkScrollableFrame(self, height=280)
        self.grid_scroll.pack(fill="both", expand=True, padx=20, pady=(4, 4))
        for col, weight in enumerate(self.GRID_COLUMN_WEIGHTS):
            self.grid_scroll.grid_columnconfigure(col, weight=weight)
        self._build_grid_header()
        self._row_widgets = {}
        self._row_tiers = {}

        self.totals_label = ctk.CTkLabel(self, font=("Consolas", 13), anchor="e", justify="right")
        self.totals_label.pack(fill="x", padx=20, pady=(6, 16))

        self.refresh()

    # --------------------------------------------------
    # Spreadsheet-style line item grid
    # --------------------------------------------------

    GRID_COLUMNS = ("Item Type", "Tier", "Width (m)", "Length (m)", "Colour", "Qty", "Unit Price (R)", "Description (optional)", "Amount", "")
    GRID_COLUMN_WEIGHTS = (2, 1, 1, 1, 1, 1, 1, 2, 1, 0)

    def _build_grid_header(self):
        for col, label in enumerate(self.GRID_COLUMNS):
            ctk.CTkLabel(
                self.grid_scroll, text=label, font=("Segoe UI", 11, "bold"), anchor="w",
            ).grid(row=0, column=col, sticky="ew", padx=3, pady=(0, 4))

    def refresh(self):

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            self.destroy()
            return
        self._quote = quote

        customer = self.crm_service.get_customer(quote.customer_id)
        site = self.crm_service.sites.get(quote.site_id) if quote.site_id else None

        display_number = format_quote_number(quote)
        self.title(f"Quote — {display_number if quote.quote_number else 'Draft'}")
        self.header_label.configure(text=f"{display_number if quote.quote_number else 'Draft Quote'}  ({quote.status})")
        subheader = f"{customer.name if customer else 'Unknown customer'}"
        if site:
            subheader += f"  ·  {site.name}"
        subheader += f"  ·  Terms: {quote.payment_terms_snapshot or '—'}"
        if quote.issue_date:
            subheader += f"  ·  Issued {quote.issue_date}, valid until {quote.expiry_date}"
        if quote.accepted_date:
            subheader += f"  ·  Accepted {quote.accepted_date}"
        self.subheader_label.configure(text=subheader)

        self.po_combo.set(quote.po_number or "TBC")
        default_vat = quote.vat_number or (customer.vat_number if customer else "") or "TBC"
        self.vat_combo.set(default_vat)
        default_registration = quote.registration_number or (customer.registration_number if customer else "") or "TBC"
        self.registration_combo.set(default_registration)
        self.bill_to_entry.delete(0, "end")
        self.bill_to_entry.insert(0, quote.bill_to_name or (customer.name if customer else ""))
        self._split_invoice_var.set(quote.split_invoice)
        self._show_invoice_buttons(quote.split_invoice)

        self._editable = quote.status == "Draft"
        self.add_row_button.configure(state="normal" if self._editable else "disabled")
        if self._editable:
            self.locked_label.pack_forget()
        else:
            self.locked_label.pack(side="left", padx=(12, 0))

        for widgets in self._row_widgets.values():
            for widget in widgets.values():
                if hasattr(widget, "destroy"):
                    widget.destroy()
        self._row_widgets = {}

        for row_index, item in enumerate(self.quote_service.list_line_items(self.quote_id), start=1):
            self._build_grid_row(row_index, item)

        self.totals_label.configure(
            text=f"Subtotal: {format_money(quote.subtotal_minor, quote.currency)}    "
            f"Total: {format_money(quote.total_minor, quote.currency)}"
        )

        if self.on_change:
            self.on_change()

    def _build_grid_row(self, row_index, item):

        widgets = {}
        state = "normal" if self._editable else "disabled"

        type_options = self.picklists.list_values(LINE_ITEM_TYPE) or ["Item"]
        if item.structure_type and item.structure_type not in type_options:
            type_options = type_options + [item.structure_type]

        initial_structure_type = item.structure_type or type_options[0]

        structure_var = ctk.StringVar(value=initial_structure_type)
        structure_menu = ctk.CTkOptionMenu(
            self.grid_scroll, variable=structure_var, values=type_options,
            command=lambda _v, iid=item.id: self._on_structure_type_change(iid), state=state,
        )
        structure_menu.grid(row=row_index, column=0, sticky="ew", padx=3, pady=2)
        widgets["structure_type"] = structure_menu

        tier_var = ctk.StringVar(value=self._row_tiers.get(item.id, "Standard"))
        tier_menu = ctk.CTkOptionMenu(
            self.grid_scroll, variable=tier_var, values=["Standard", "High"],
            command=lambda _v, iid=item.id: self._on_tier_change(iid), state=state,
        )
        tier_menu.grid(row=row_index, column=1, sticky="ew", padx=3, pady=2)
        widgets["tier"] = tier_menu

        def make_entry(col, key, initial):
            entry = ctk.CTkEntry(self.grid_scroll)
            entry.insert(0, initial)
            entry.grid(row=row_index, column=col, sticky="ew", padx=3, pady=2)
            entry.bind("<FocusOut>", lambda _e, iid=item.id: self._commit_row(iid))
            entry.bind("<Return>", lambda _e, iid=item.id: self._commit_row(iid))
            entry.configure(state=state)
            widgets[key] = entry
            return entry

        make_entry(2, "width_m", "" if item.width_m is None else f"{item.width_m:g}")
        make_entry(3, "projection_m", "" if item.projection_m is None else f"{item.projection_m:g}")

        colour_combo = ctk.CTkComboBox(self.grid_scroll, values=["N/A"] + COLOUR_OPTIONS, state=state)
        colour_combo.set(item.colour or "N/A")
        colour_combo.grid(row=row_index, column=4, sticky="ew", padx=3, pady=2)
        colour_combo.bind("<FocusOut>", lambda _e, iid=item.id: self._commit_row(iid))
        colour_combo.bind("<Return>", lambda _e, iid=item.id: self._commit_row(iid))
        colour_combo.configure(command=lambda _v, iid=item.id: self._commit_row(iid))
        widgets["colour"] = colour_combo

        make_entry(5, "quantity", f"{item.quantity:g}")
        make_entry(6, "unit_price", f"{item.unit_price_minor / 100:.2f}")
        make_entry(7, "description", item.description)

        amount_label = ctk.CTkLabel(self.grid_scroll, text=format_money(item.amount_minor, self._quote.currency), anchor="e")
        amount_label.grid(row=row_index, column=8, sticky="ew", padx=3, pady=2)
        widgets["amount"] = amount_label

        delete_button = ctk.CTkButton(
            self.grid_scroll, text="✕", width=28, fg_color="#8B2E2E", hover_color="#6E2222",
            command=lambda iid=item.id: self._delete_row(iid), state=state,
        )
        delete_button.grid(row=row_index, column=9, sticky="ew", padx=3, pady=2)
        widgets["delete"] = delete_button

        self._row_widgets[item.id] = widgets

    def _rate_for_selected_tier(self, widgets):
        """The picklist rate matching the row's current Structure type +
        Tier selection, or None if that type has no flat rate (e.g. a
        real structure priced from the catalog, not the rate card)."""

        selected_type = widgets["structure_type"].get()
        tier = widgets["tier"].get()
        options = {o.value: o for o in self.picklists.list_options(LINE_ITEM_TYPE, include_inactive=True)}
        option = options.get(selected_type)
        if option is None:
            return None
        return option.rate_high_minor if tier == "High" else option.rate_standard_minor

    def _on_structure_type_change(self, item_id):
        """Selecting a flat-rate type (e.g. Refit Net) fills in a
        starting Unit Price from its picklist rate at the row's current
        Tier — but only when the field is still blank/zero, so it never
        clobbers a price someone already typed."""

        widgets = self._row_widgets.get(item_id)
        if widgets is not None:
            current_price = self._parse_float(widgets["unit_price"].get())
            rate = self._rate_for_selected_tier(widgets)
            if rate is not None and not current_price:
                widgets["unit_price"].delete(0, "end")
                widgets["unit_price"].insert(0, f"{rate / 100:.2f}")

        self._commit_row(item_id)

    def _on_tier_change(self, item_id):
        """Switching Standard/High on a rate-carrying type always applies
        that tier's rate - unlike the structure-type auto-fill, this is
        an explicit choice, so it overwrites whatever was there."""

        widgets = self._row_widgets.get(item_id)
        if widgets is not None:
            self._row_tiers[item_id] = widgets["tier"].get()
            rate = self._rate_for_selected_tier(widgets)
            if rate is not None:
                widgets["unit_price"].delete(0, "end")
                widgets["unit_price"].insert(0, f"{rate / 100:.2f}")

        self._commit_row(item_id)

    def _commit_row(self, item_id):

        if not self._editable:
            return

        widgets = self._row_widgets.get(item_id)
        if widgets is None:
            return

        item = None
        for candidate in self.quote_service.list_line_items(self.quote_id):
            if candidate.id == item_id:
                item = candidate
                break
        if item is None:
            return

        structure_type = widgets["structure_type"].get()
        width_m = self._parse_float(widgets["width_m"].get())
        projection_m = self._parse_float(widgets["projection_m"].get())

        item.structure_type = structure_type
        item.width_m = width_m
        item.projection_m = projection_m
        colour = widgets["colour"].get().strip()
        item.colour = "" if colour == "N/A" else colour
        item.description = widgets["description"].get()

        try:
            item.quantity = float(widgets["quantity"].get() or "1")
            item.unit_price_minor = round(float(widgets["unit_price"].get() or "0") * 100)
        except ValueError:
            messagebox.showerror("Line Item", "Quantity and unit price must be numbers.", parent=self)
            return

        try:
            self.quote_service.save_line_item(item)
        except ValueError as error:
            messagebox.showerror("Line Item", str(error), parent=self)
            return

        self.refresh()

    def _delete_row(self, item_id):

        if not self._editable:
            return
        if not messagebox.askyesno("Delete Line Item", "Remove this line item?", parent=self):
            return
        self.quote_service.delete_line_item(item_id, self.quote_id)
        self.refresh()

    # --------------------------------------------------

    def issue_quote(self):

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        # Draft is the normal path, but a quote that somehow reached another
        # status without ever being numbered must still be issuable -
        # otherwise it is stuck: no number, so no Pro-Forma and no invoice.
        if quote.quote_number and quote.status != "Draft":
            messagebox.showinfo(
                "Issue Quote",
                "This quote already has a number - it has been issued.",
                parent=self,
            )
            return
        prompt = (
            "Issue this revision? It keeps the same quote number as the original."
            if quote.revision_number
            else "Issue this quote? It will be assigned a permanent number."
        )
        issue_date = _ask_date(
            self, "Issue Quote", prompt + "\n\nIssue date:",
            quote.issue_date or date.today().strftime("%Y-%m-%d"),
        )
        if issue_date is None:
            return
        try:
            self.quote_service.issue_quote(self.quote_id, current_actor(), issue_date=issue_date)
        except Exception as error:
            messagebox.showerror("Issue Quote", str(error), parent=self)
            return
        self.refresh()

    def create_revision(self):

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        if quote.status == "Draft":
            messagebox.showinfo("Create Revision", "This quote is still a Draft — edit it directly instead of revising it.", parent=self)
            return
        if not messagebox.askyesno(
            "Create Revision",
            "Create an editable revision of this quote? It keeps the same quote number "
            f"({format_quote_number(quote)}) as a new version — the original is left untouched.",
            parent=self,
        ):
            return
        try:
            revision = self.quote_service.create_quote_revision(self.quote_id, current_actor())
        except Exception as error:
            messagebox.showerror("Create Revision", str(error), parent=self)
            return
        if self.on_change:
            self.on_change()
        QuoteDetailWindow(self.master, self.quote_service, self.crm_service, self.business_settings, revision.id, on_change=self.on_change)

    # --------------------------------------------------

    def set_status(self, status):

        try:
            self.quote_service.set_status(self.quote_id, status, current_actor())
        except ValueError as error:
            # Accepting an un-issued quote is refused at the service. Offer
            # the way out rather than leaving her at a dead end.
            if status == "Accepted" and messagebox.askyesno(
                "Mark Accepted", f"{error}\n\nIssue it now?", parent=self,
            ):
                self.issue_quote()
                if self.quote_service.get_quote(self.quote_id).quote_number:
                    self.quote_service.set_status(self.quote_id, status, current_actor())
                else:
                    return
            else:
                messagebox.showinfo("Mark Accepted", str(error), parent=self)
                return
        if status == "Accepted":
            self.open_statement()
        self.refresh()

    def edit_dates(self):
        """One place for every date on this quote's chain - the quote's own
        issue and accepted dates, then each Pro-Forma and Invoice. This is
        what puts the Statement in the right order."""

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        QuoteDatesWindow(
            self.winfo_toplevel(), quote_id=self.quote_id,
            quote_service=self.quote_service,
            quote_documents=self.quote_documents,
            on_saved=self.refresh,
        )

    def open_statement(self):
        quote = self.quote_service.get_quote(self.quote_id)
        StatementEditorWindow(self.winfo_toplevel(), customer_id=quote.customer_id if quote else None)

    # --------------------------------------------------

    def archive_quote(self):

        reason = TextPromptDialog.ask(self, "Archive Quote", "Reason for archiving this quote:")
        if reason is None:
            return
        try:
            self.quote_service.archive_quote(self.quote_id, current_actor(), reason)
        except ValueError as error:
            messagebox.showerror("Archive Quote", str(error), parent=self)
            return
        self.refresh()

    # --------------------------------------------------

    def delete_quote(self):
        """Deletes this quote regardless of status (Draft or Issued),
        including any Pro-Forma/Tax Invoice generated from it. Blocked
        if a real payment has been allocated against one of those
        documents - see QuoteService.delete_quote."""

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        display_number = format_quote_number(quote)
        if not messagebox.askyesno(
            "Delete Quote",
            f"Permanently delete {display_number} ({quote.status})?\n\n"
            "This also removes any Pro-Forma or Tax Invoice already generated from it. "
            "The quote number will not be reused. This cannot be undone.",
            parent=self,
        ):
            return
        try:
            self.quote_service.delete_quote(self.quote_id)
        except ValueError as error:
            messagebox.showerror("Delete Quote", str(error), parent=self)
            return
        if self.on_change:
            self.on_change()
        self.destroy()

    # --------------------------------------------------

    def edit_quote_details(self):

        quote = self.quote_service.get_quote(self.quote_id)
        fields = [
            {"key": "expiry_date", "label": "Valid Until", "kind": "date", "initial": quote.expiry_date},
            {"key": "notes", "label": "Notes (shown on the PDF)", "kind": "textarea", "initial": quote.notes},
        ]
        result = EntityFormDialog.ask(self, "Edit Quote Details", fields)
        if result is None:
            return
        quote.expiry_date = result["expiry_date"]
        quote.notes = result["notes"]
        self.quote_service.save_quote(quote, current_actor())
        self.refresh()

    def _save_po_number(self):

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        new_value = self.po_combo.get().strip()
        if new_value == quote.po_number:
            return
        quote.po_number = new_value
        self.quote_service.save_quote(quote, current_actor())
        self.refresh()

    def _save_vat_number(self):

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        new_value = self.vat_combo.get().strip()
        if new_value == quote.vat_number:
            return
        quote.vat_number = new_value
        self.quote_service.save_quote(quote, current_actor())
        self.refresh()

    def _save_registration_number(self):

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        new_value = self.registration_combo.get().strip()
        if new_value == quote.registration_number:
            return
        quote.registration_number = new_value
        self.quote_service.save_quote(quote, current_actor())
        self.refresh()

    def _save_bill_to_name(self):

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        new_value = self.bill_to_entry.get().strip()
        if new_value == quote.bill_to_name:
            return
        quote.bill_to_name = new_value
        self.quote_service.save_quote(quote, current_actor())
        self.refresh()

    def _save_split_invoice(self):

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        quote.split_invoice = self._split_invoice_var.get()
        self.quote_service.save_quote(quote, current_actor())
        self._show_invoice_buttons(quote.split_invoice)

    def _show_invoice_buttons(self, split):

        for button in (self._tax_invoice_btn, self._deposit_invoice_btn, self._balance_invoice_btn):
            button.pack_forget()
        if split:
            self._deposit_invoice_btn.pack(side="left", padx=4)
            self._balance_invoice_btn.pack(side="left", padx=4)
        else:
            self._tax_invoice_btn.pack(side="left", padx=4)

    def edit_billing_delivery_address(self):
        """Add or edit the customer's Billing/Delivery address without
        leaving the Quote window - previously only possible from CRM."""

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        customer = self.crm_service.get_customer(quote.customer_id)
        if customer is None:
            messagebox.showwarning("Billing / Delivery Address", "This quote has no customer.", parent=self)
            return

        addresses = {a.address_type: a for a in self.crm_service.list_addresses(customer.id) if a.address_type in ("Billing", "Delivery", "Postal")}

        # Step 1: which type. Deliberately a separate dialog rather than
        # one form with a type dropdown - EntityFormDialog's fields are
        # static, so a dropdown change can't re-populate the other
        # fields with that type's actual stored address (that bug: it
        # always showed Billing's values even when Delivery was picked).
        type_result = EntityFormDialog.ask(
            self,
            f"{customer.name} — Billing / Delivery / Postal Address",
            [{"key": "address_type", "label": "Which address?", "kind": "dropdown", "options": ["Billing", "Delivery", "Postal"], "initial": "Billing"}],
        )
        if type_result is None:
            return
        address_type = type_result["address_type"]
        existing = addresses.get(address_type)

        # Step 2: edit that type's real values.
        fields = [
            {"key": "line1", "label": "Address Line 1", "kind": "text", "initial": existing.line1 if existing else ""},
            {"key": "line2", "label": "Address Line 2", "kind": "text", "initial": existing.line2 if existing else ""},
            {"key": "city", "label": "City", "kind": "text", "initial": existing.city if existing else ""},
            {"key": "province", "label": "Province", "kind": "text", "initial": existing.province if existing else ""},
            {"key": "postal_code", "label": "Postal Code", "kind": "text", "initial": existing.postal_code if existing else ""},
        ]
        result = EntityFormDialog.ask(self, f"{customer.name} — {address_type} Address", fields)
        if result is None:
            return

        address = existing or Address(customer_id=customer.id, address_type=address_type)
        address.line1 = result["line1"]
        address.line2 = result["line2"]
        address.city = result["city"]
        address.province = result["province"]
        address.postal_code = result["postal_code"]
        address.is_primary = True

        try:
            self.crm_service.save_address(address)
        except Exception as error:
            messagebox.showerror("Billing / Delivery Address", str(error), parent=self)
            return
        messagebox.showinfo("Billing / Delivery Address", f"{address_type} address saved for {customer.name}.", parent=self)

    def change_site(self):
        """Change which of the customer's Sites this quote is for,
        after creation - previously only choosable when the quote was
        first created."""

        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        customer = self.crm_service.get_customer(quote.customer_id)
        if customer is None:
            messagebox.showwarning("Change Site", "This quote has no customer.", parent=self)
            return

        sites = self.crm_service.list_sites(customer.id)
        if not sites:
            messagebox.showwarning("Change Site", f"{customer.name} has no sites on file yet - add one in CRM first.", parent=self)
            return

        site_labels = ["(none)"] + [s.name for s in sites]
        site_by_label = {s.name: s.id for s in sites}
        current_label = next((label for label, site_id in site_by_label.items() if site_id == quote.site_id), "(none)")

        result = EntityFormDialog.ask(
            self,
            f"{customer.name} — Change Site",
            [{"key": "site", "label": "Site", "kind": "dropdown", "options": site_labels, "initial": current_label}],
        )
        if result is None:
            return

        quote.site_id = site_by_label.get(result["site"], "")
        self.quote_service.save_quote(quote, current_actor())
        self.refresh()

    # --------------------------------------------------

    def _create_site(self):
        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        customer = self.crm_service.get_customer(quote.customer_id)
        if customer is None:
            return
        result = EntityFormDialog.ask(
            self, f"New Site for {customer.name}",
            [
                {"key": "name", "label": "Site Name", "kind": "text", "initial": ""},
                {"key": "site_type", "label": "Type", "kind": "dropdown",
                 "options": ["Property", "Car Park", "School", "Office", "Industrial", "Other"],
                 "initial": "Property"},
            ],
        )
        if not result or not result["name"].strip():
            return
        site = self.crm_service.new_site(customer.id)
        site.name = result["name"].strip()
        site.site_type = result["site_type"]
        addresses = self.crm_service.list_addresses(customer.id)
        if addresses:
            site.address_id = addresses[0].id
        self.crm_service.save_site(site)
        quote.site_id = site.id
        self.quote_service.save_quote(quote, current_actor())
        self.refresh()

    def _resolve_addresses(self, customer, site):
        """The customer's primary Billing and Delivery addresses, and
        the selected site's own structured address, for printing on
        the PDF."""

        billing_address = None
        delivery_address = None
        postal_address = None
        if customer is not None:
            addresses = self.crm_service.list_addresses(customer.id)
            billing_address = next(
                (a for a in addresses if a.address_type == "Billing" and a.is_primary),
                next((a for a in addresses if a.address_type == "Billing"), None),
            )
            delivery_address = next(
                (a for a in addresses if a.address_type == "Delivery" and a.is_primary),
                next((a for a in addresses if a.address_type == "Delivery"), None),
            )
            postal_address = next(
                (a for a in addresses if a.address_type == "Postal" and a.is_primary),
                next((a for a in addresses if a.address_type == "Postal"), None),
            )

        site_address = None
        if site is not None and site.address_id:
            site_address = self.crm_service.addresses.get(site.address_id)

        # If no explicit delivery address, use site address as delivery (common for GHH-style Site-type addresses)
        if delivery_address is None and site_address is not None:
            delivery_address = site_address

        return billing_address, site_address, delivery_address, postal_address

    def generate_pdf(self):

        quote = self.quote_service.get_quote(self.quote_id)
        line_items = self.quote_service.list_line_items(self.quote_id)
        if not line_items:
            messagebox.showwarning("Generate PDF", "Add at least one line item first.", parent=self)
            return

        customer = self.crm_service.get_customer(quote.customer_id)
        site = self.crm_service.sites.get(quote.site_id) if quote.site_id else None
        business = self.business_settings.get_settings()
        billing_address, site_address, delivery_address, postal_address = self._resolve_addresses(customer, site)

        # An unnumbered draft always files as Draft_Quote.pdf and
        # replaces the previous draft - her call, to keep Paperwork
        # tidy rather than accumulating a draft per attempt.
        default_name = f"{format_quote_number(quote) if quote.quote_number else 'Draft_Quote'}.pdf".replace("/", "-").replace(" ", "_").replace("(", "").replace(")", "")

        contacts = self.crm_service.list_contacts(quote.customer_id)
        primary = next((c for c in contacts if c.is_primary), contacts[0] if contacts else None)
        contact_name = primary.name if primary and primary.name else None

        def build(output_path):
            generate_quote_pdf(
                quote, line_items, customer, site, business, output_path,
                billing_address=billing_address, site_address=site_address, delivery_address=delivery_address,
                postal_address=postal_address, contact_name=contact_name,
            )

        file_document_for_customer(
            self, customer, default_name, build,
            title="Generate PDF",
            heading="Quote saved",
        )

    # --------------------------------------------------
    # Pro-Forma / Tax Invoice (generated from this quote)
    # --------------------------------------------------

    def generate_pro_forma(self):
        self._generate_document(
            generator=self.quote_documents.generate_pro_forma,
            pdf_builder=generate_proforma_pdf,
            label="Pro-Forma",
        )

    def generate_tax_invoice(self):
        self._generate_document(
            generator=self.quote_documents.generate_tax_invoice,
            pdf_builder=generate_invoice_pdf,
            label="Tax Invoice",
        )

    def generate_deposit_invoice(self):
        self._generate_document(
            generator=self.quote_documents.generate_deposit_invoice,
            pdf_builder=generate_invoice_pdf,
            label="Deposit Invoice",
        )

    def generate_balance_invoice(self):
        if self.quote_documents.deposit_invoice_for_quote(self.quote_id) is None:
            messagebox.showinfo(
                "Balance Invoice",
                f"Generate the Deposit Invoice ({deposit_percent()}%) first. "
                "The balance invoice deducts the deposit, so it needs the deposit invoice number.",
                parent=self,
            )
            return
        self._generate_document(
            generator=self.quote_documents.generate_balance_invoice,
            pdf_builder=generate_invoice_pdf,
            label="Balance Invoice",
        )

    def _generate_document(self, generator, pdf_builder, label):

        issue_date = _ask_date(
            self, label, f"Date for this {label}:", date.today().strftime("%Y-%m-%d"),
        )
        if issue_date is None:
            return
        try:
            document = generator(self.quote_id, current_actor(), issue_date=issue_date)
        except Exception as error:
            messagebox.showerror(label, str(error), parent=self)
            return

        quote = self.quote_service.get_quote(self.quote_id)
        line_items = self.quote_service.list_line_items(self.quote_id)
        customer = self.crm_service.get_customer(quote.customer_id)
        site = self.crm_service.sites.get(quote.site_id) if quote.site_id else None
        business = self.business_settings.get_settings()
        billing_address, site_address, delivery_address, postal_address = self._resolve_addresses(customer, site)

        contacts = self.crm_service.list_contacts(quote.customer_id)
        primary = next((c for c in contacts if c.is_primary), contacts[0] if contacts else None)
        contact_name = primary.name if primary and primary.name else None

        default_name = f"{document.document_number}.pdf".replace("/", "-")
        extra = {}
        if getattr(document, "invoice_part", "") == "balance":
            extra["deposit_document"] = self.quote_documents.deposit_invoice_for_quote(self.quote_id)

        def build(output_path):
            pdf_builder(
                document, quote, line_items, customer, site, business, output_path,
                billing_address=billing_address, site_address=site_address, delivery_address=delivery_address,
                postal_address=postal_address, contact_name=contact_name,
                **extra,
            )

        file_document_for_customer(
            self, customer, default_name, build,
            title=label,
            heading=f"{label} saved",
        )

    # --------------------------------------------------
    # Line items
    # --------------------------------------------------

    def new_line_item(self):

        if not self._editable:
            return
        item = self.quote_service.new_line_item(self.quote_id)
        type_options = self.picklists.list_values(LINE_ITEM_TYPE)
        item.structure_type = type_options[0] if type_options else "Item"
        item.quantity = 1
        try:
            self.quote_service.save_line_item(item)
        except ValueError as error:
            messagebox.showerror("Line Item", str(error), parent=self)
            return
        self.refresh()

    @staticmethod
    def _parse_float(value):
        try:
            return float(value) if value not in (None, "") else None
        except ValueError:
            return None


class StatementEditorWindow(ctk.CTkToplevel):
    """Editable customer Statement. Pre-fills one line per quote at its
    furthest stage (Tax Invoice > Pro-Forma > Accepted Quote); every line
    can be edited, removed, or added to (adjustments, payments received as
    negative amounts) before the PDF is saved. Restored 2026-09-22 after the
    Statements tab was lost in the 5a74e86 redesign."""

    def __init__(self, parent, customer_id=None):
        super().__init__(parent)
        self.title("Statement")
        self.geometry("900x640")

        self.crm_service = CRMService()
        self.statement_service = StatementService()
        self.business_settings = BusinessSettingsService()
        self._rows = []

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(16, 8))

        customers = self.crm_service.list_customers()
        self._customer_by_label = {f"{c.customer_number} — {c.name}": c for c in customers}
        labels = list(self._customer_by_label.keys())
        initial = next((l for l, c in self._customer_by_label.items() if c.id == customer_id), labels[0] if labels else "")
        ctk.CTkLabel(top, text="Customer:").pack(side="left")
        self.customer_var = ctk.StringVar(value=initial)
        ctk.CTkOptionMenu(top, variable=self.customer_var, values=labels or ["(no customers)"], width=300,
                          command=lambda _v: self._reload()).pack(side="left", padx=(4, 12))

        today = date.today()
        ctk.CTkLabel(top, text="From:").pack(side="left")
        self.start_entry = DateEntry(top, value=today.replace(month=1, day=1).strftime("%Y-%m-%d"))
        self.start_entry.pack(side="left", padx=4)
        ctk.CTkLabel(top, text="To:").pack(side="left")
        self.end_entry = DateEntry(top, value=today.strftime("%Y-%m-%d"))
        self.end_entry.pack(side="left", padx=4)
        ctk.CTkButton(top, text="Reload", width=80, command=self._reload).pack(side="left", padx=8)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16)
        for text, width in (("Reference", 150), ("Date", 110), ("Description", 330), ("Amount (R)", 120)):
            ctk.CTkLabel(header, text=text, width=width, anchor="w", font=("Segoe UI", 12, "bold")).pack(side="left", padx=2)

        self.rows_frame = ctk.CTkScrollableFrame(self, height=330)
        self.rows_frame.pack(fill="both", expand=True, padx=16, pady=4)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=4)
        ctk.CTkButton(
            bottom, text="+ Add Adjustment Line", width=170,
            command=lambda: self._add_row({"ref": "", "date": date.today().strftime("%Y-%m-%d"),
                                           "description": "Adjustment", "amount_minor": 0}),
        ).pack(side="left")
        ctk.CTkLabel(bottom, text="Use a minus amount for payments received / credits.",
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=10)
        self.total_label = ctk.CTkLabel(bottom, text="Total: R 0.00", font=("Segoe UI", 14, "bold"))
        self.total_label.pack(side="right")

        ctk.CTkLabel(self, text="Notes (printed on statement):", anchor="w").pack(fill="x", padx=16)
        self.notes_box = ctk.CTkTextbox(self, height=60)
        self.notes_box.pack(fill="x", padx=16, pady=(2, 8))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(actions, text="Close", width=90, command=self.destroy).pack(side="right", padx=4)
        ctk.CTkButton(actions, text="Save Statement PDF", width=170, command=self._generate).pack(side="right", padx=4)

        self._reload()
        self.after(100, self._force_front)

    def _force_front(self):
        if not self.winfo_exists():
            return
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.winfo_exists() and self.attributes("-topmost", False))
        self.focus_force()

    def _customer(self):
        return self._customer_by_label.get(self.customer_var.get())

    def _reload(self):
        for row in self._rows:
            row["frame"].destroy()
        self._rows = []
        customer = self._customer()
        if customer is not None:
            try:
                lines = self.statement_service.build_lines(customer.id, self.start_entry.get(), self.end_entry.get())
            except Exception as error:
                messagebox.showerror("Statement", str(error), parent=self)
                lines = []
            for line in lines:
                self._add_row(line)
        self._update_total()

    def _add_row(self, line):
        frame = ctk.CTkFrame(self.rows_frame, fg_color="transparent")
        frame.pack(fill="x", pady=1)
        entries = {}
        for key, width in (("ref", 150), ("date", 110), ("description", 330), ("amount", 120)):
            entry = ctk.CTkEntry(frame, width=width)
            value = f"{line['amount_minor'] / 100:.2f}" if key == "amount" else (line.get(key) or "")
            entry.insert(0, value)
            entry.pack(side="left", padx=2)
            entries[key] = entry
        entries["amount"].bind("<KeyRelease>", lambda _e: self._update_total())
        row = {"frame": frame, "entries": entries, "document_id": line.get("document_id", "")}
        ctk.CTkButton(frame, text="✕", width=30, fg_color="#B04040", hover_color="#8A3030",
                      command=lambda: self._remove_row(row)).pack(side="left", padx=4)
        self._rows.append(row)
        self._update_total()

    def _remove_row(self, row):
        row["frame"].destroy()
        self._rows.remove(row)
        self._update_total()

    @staticmethod
    def _parse_amount(text):
        cleaned = text.replace("R", "").replace(",", "").replace(" ", "").strip()
        if not cleaned:
            return 0
        return int(round(float(cleaned) * 100))

    def _collect_lines(self):
        lines = []
        for row in self._rows:
            e = row["entries"]
            lines.append({
                "ref": e["ref"].get().strip(),
                "date": e["date"].get().strip(),
                "description": e["description"].get().strip(),
                "amount_minor": self._parse_amount(e["amount"].get()),
                "document_id": row["document_id"],
                "currency": "ZAR",
            })
        return lines

    def _update_total(self):
        try:
            total = sum(self._parse_amount(r["entries"]["amount"].get()) for r in self._rows)
            self.total_label.configure(text=f"Total: {format_money(total, 'ZAR')}")
        except ValueError:
            self.total_label.configure(text="Total: (check amounts)")

    def _generate(self):
        customer = self._customer()
        if customer is None:
            messagebox.showwarning("Statement", "Select a customer first.", parent=self)
            return
        try:
            lines = self._collect_lines()
        except ValueError:
            messagebox.showerror("Statement", "One of the amounts is not a valid number.", parent=self)
            return
        notes = self.notes_box.get("1.0", "end").strip()
        try:
            statement = self.statement_service.save_statement(
                customer.id, self.start_entry.get(), self.end_entry.get(), lines, current_actor(), notes=notes,
            )
        except ValueError as error:
            messagebox.showerror("Statement", str(error), parent=self)
            return

        addresses = self.crm_service.list_addresses(customer.id)
        billing_address = next(
            (a for a in addresses if a.address_type == "Billing" and a.is_primary),
            next((a for a in addresses if a.address_type == "Billing"), None),
        )

        def build(output_path):
            generate_statement_pdf(
                statement, [], customer, self.business_settings.get_settings(), output_path,
                billing_address=billing_address, lines=lines,
            )

        file_document_for_customer(
            self, customer, f"{statement.document_number}.pdf".replace("/", "-"), build,
            title="Statement", heading=f"Statement {statement.document_number} saved",
        )


# ==========================================================
# Dates
# ----------------------------------------------------------
# Document dates used to be stamped "today" at generation and were then
# immutable, so a chain captured in one sitting all carried one date and
# the Statement could not read chronologically. These two let the real
# dates be set - on generation, and afterwards.
# ==========================================================


def _ask_date(parent, title, prompt, initial):
    """Small date prompt with the calendar picker. Returns an ISO date, or
    None if she cancelled (so the caller does nothing at all)."""

    dialog = _DatePromptDialog(parent.winfo_toplevel(), title, prompt, initial)
    parent.wait_window(dialog)
    return dialog.result


class _DatePromptDialog(ctk.CTkToplevel):

    def __init__(self, parent, title, prompt, initial):
        super().__init__(parent)
        self.title(title)
        self.geometry("420x190")
        self.resizable(False, False)
        self.result = None

        ctk.CTkLabel(self, text=prompt, justify="left", wraplength=380).pack(
            padx=20, pady=(20, 10), anchor="w",
        )
        self.entry = DateEntry(self, value=initial)
        self.entry.pack(padx=20, anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=16)
        ctk.CTkButton(row, text="Cancel", width=90, command=self.destroy).pack(side="right")
        ctk.CTkButton(row, text="OK", width=90, command=self._ok).pack(side="right", padx=8)

        self.after(100, self._force_front)

    def _force_front(self):
        if not self.winfo_exists():
            return
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.winfo_exists() and self.attributes("-topmost", False))
        self.focus_force()

    def _ok(self):
        value = self.entry.get()
        try:
            validate_document_date(value)
        except ValueError as error:
            messagebox.showerror(self.title(), str(error), parent=self)
            return
        self.result = value
        self.destroy()


class QuoteDatesWindow(ctk.CTkToplevel):
    """Every date on one quote's chain, in one list: the quote's own issue
    and accepted dates, then each Pro-Forma and Invoice in the order they
    will print on the Statement. Numbers and amounts are never touched -
    only the dates move."""

    def __init__(self, parent, quote_id, quote_service, quote_documents, on_saved=None):
        super().__init__(parent)
        self.title("Dates")
        self.geometry("620x520")

        self.quote_id = quote_id
        self.quote_service = quote_service
        self.quote_documents = quote_documents
        self.on_saved = on_saved
        self._doc_entries = []

        self._build_ui()
        self.after(100, self._force_front)

    def _force_front(self):
        if not self.winfo_exists():
            return
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.winfo_exists() and self.attributes("-topmost", False))
        self.focus_force()

    def _build_ui(self):

        quote = self.quote_service.get_quote(self.quote_id)
        ctk.CTkLabel(
            self, text="Dates on this quote and its documents",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(
            self,
            text="The Statement reads in date order, so these are what put the\n"
                 "chain in the right sequence. Numbers and amounts don't change.",
            justify="left", text_color="#6B6B6B",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        body = ctk.CTkScrollableFrame(self, height=320)
        body.pack(fill="both", expand=True, padx=20)

        quote_number = quote.quote_number if quote and quote.quote_number else "(not issued yet)"
        self.issue_entry = self._row(body, quote_number, "Quote issued", quote.issue_date if quote else "")
        self.accepted_entry = self._row(body, "", "Quote accepted", quote.accepted_date if quote else "")
        self.expiry_entry = self._row(body, "", "Quote expires", quote.expiry_date if quote else "")

        documents = sorted(
            self.quote_documents.list_for_quote(self.quote_id),
            key=lambda d: ((d.issue_date or "")[:10], d.document_number or ""),
        )
        for document in documents:
            part = f" ({document.invoice_part.capitalize()})" if getattr(document, "invoice_part", "") else ""
            entry = self._row(body, document.document_number, f"{document.doc_type}{part}", document.issue_date)
            self._doc_entries.append((document, entry))

        if not documents:
            ctk.CTkLabel(
                body, text="No Pro-Formas or Invoices generated from this quote yet.",
                text_color="#6B6B6B",
            ).pack(anchor="w", pady=8)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=14)
        ctk.CTkButton(row, text="Close", width=90, command=self.destroy).pack(side="right")
        ctk.CTkButton(row, text="Save Dates", width=110, command=self._save).pack(side="right", padx=8)

    def _row(self, parent, reference, label, value):

        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=3)
        ctk.CTkLabel(frame, text=reference, width=150, anchor="w").pack(side="left")
        ctk.CTkLabel(frame, text=label, width=190, anchor="w").pack(side="left")
        entry = DateEntry(frame, value=(value or "")[:10])
        entry.pack(side="left")
        return entry

    def _save(self):

        try:
            self.quote_service.set_quote_dates(
                self.quote_id, current_actor(),
                issue_date=self.issue_entry.get(),
                accepted_date=self.accepted_entry.get(),
                expiry_date=self.expiry_entry.get(),
            )
            for document, entry in self._doc_entries:
                value = entry.get()
                if value != (document.issue_date or "")[:10]:
                    self.quote_documents.set_document_dates(
                        document.id, issue_date=value, actor=current_actor(),
                    )
        except ValueError as error:
            messagebox.showerror("Dates", str(error), parent=self)
            return

        messagebox.showinfo("Dates", "Dates saved.", parent=self)
        if self.on_saved:
            self.on_saved()
        self.destroy()
