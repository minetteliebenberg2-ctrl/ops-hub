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
from core.business_document_pdf import generate_invoice_pdf, generate_proforma_pdf, generate_statement_pdf
from core.business_settings_service import BusinessSettingsService
from core.crm_service import CRMService
from core.picklist_service import LINE_ITEM_TYPE, PicklistService
from modules.proposals.netting_quotes import PAINT_COLORS, SUPPLIER_PRICES, Supplier
from core.quote import format_quote_number
from core.quote_document_service import QuoteDocumentService
from core.quote_pdf import format_money, generate_quote_pdf
from core.quote_service import QuoteService
from core.statement_service import StatementService
from core.structure_catalog import (
    CANTILEVER,
    DEFAULT_HEIGHT_M,
    STANDARD,
    STRUCTURE_TYPES,
    car_bay_size,
    size_label_for,
    size_options_for,
)
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

COLOUR_OPTIONS = sorted(set(SUPPLIER_PRICES[Supplier.KNITTEX_Z25]["colors"].keys()) | set(PAINT_COLORS))


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
            ),
        )
        self.table.bind("<Double-1>", lambda _event: self.open_quote())

        self._customers_by_id = {}
        self.refresh()

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
        ctk.CTkButton(doc_row, text="Tax Invoice", command=self.generate_tax_invoice, width=110).pack(side="left", padx=4)

        self._site_plan_btn = ctk.CTkButton(doc_row, text="Open Site Plan", command=self._open_site_plan, width=130)
        self._job_card_btn = ctk.CTkButton(doc_row, text="Open Job Card", command=self._open_job_card, width=130)

        grid_header = ctk.CTkFrame(self)
        grid_header.pack(fill="x", padx=20, pady=(0, 0))
        self.add_row_button = ctk.CTkButton(grid_header, text="+ Add Row", command=self.new_line_item, width=100)
        self.add_row_button.pack(side="left")
        self.price_button = ctk.CTkButton(
            grid_header, text="Calculate Prices", command=self.calculate_prices, width=140,
        )
        self.price_button.pack(side="left", padx=8)
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

    GRID_COLUMNS = ("Structure", "Car Bays", "Tier", "Width (m)", "Proj. (m)", "Colour", "Qty", "Unit Price (R)", "Description (optional)", "Amount", "")
    GRID_COLUMN_WEIGHTS = (2, 2, 1, 1, 1, 1, 1, 1, 2, 1, 0)

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

        self._update_job_card_buttons(quote)

        if self.on_change:
            self.on_change()

    def _update_job_card_buttons(self, quote):
        self._site_plan_btn.pack_forget()
        self._job_card_btn.pack_forget()
        if quote.site_id:
            self._site_plan_btn.pack(side="left", padx=(12, 4))
        if quote.status == "Accepted":
            jc = self._find_job_card_for_quote(quote)
            if jc:
                self._job_card_btn.pack(side="left", padx=4)

    def _find_job_card_for_quote(self, quote):
        from core.job_card_service import JobCardService
        try:
            svc = JobCardService()
            for jc in svc.list_job_cards_for_customer(quote.customer_id):
                if quote.quote_number and quote.quote_number in (jc.notes or ""):
                    return jc
        except Exception:
            pass
        return None

    def _open_job_card(self):
        quote = self._quote
        jc = self._find_job_card_for_quote(quote)
        if not jc:
            from tkinter import messagebox as mb
            mb.showinfo("No Job Card", "No job card found for this quote.", parent=self)
            return
        customer = self.crm_service.get_customer(quote.customer_id)
        if not customer:
            return
        from modules.site_visit.windows import JobCardWindow
        JobCardWindow(self.winfo_toplevel(), customer, jc, on_change=self.refresh)

    def _open_site_plan(self):
        quote = self._quote
        if not quote.site_id:
            from tkinter import messagebox as mb
            mb.showinfo("No Site", "Assign a site to this quote first.", parent=self)
            return
        customer = self.crm_service.get_customer(quote.customer_id)
        site = self.crm_service.sites.get(quote.site_id)
        if not customer or not site:
            return
        from modules.site_visit.windows import SitePlanWindow
        SitePlanWindow(self.winfo_toplevel(), customer, site)

    def _build_grid_row(self, row_index, item):

        widgets = {}
        state = "normal" if self._editable else "disabled"

        type_options = self.picklists.list_values(LINE_ITEM_TYPE) or list(STRUCTURE_TYPES)
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

        # Car Bay's options/labels depend on the structure type - real
        # car-bay dimensions for Cantilever/Standard, Single/Double/
        # Triple for Cable, just "N/A" for anything else. Kept in sync
        # live via _on_structure_type_change below.
        car_bay_labels, _by_label = size_options_for(initial_structure_type)
        current_car_label = size_label_for(initial_structure_type, item.car_bays)

        car_bay_var = ctk.StringVar(value=current_car_label)
        car_bay_menu = ctk.CTkOptionMenu(
            self.grid_scroll, variable=car_bay_var, values=car_bay_labels,
            command=lambda _v, iid=item.id: self._commit_row(iid), state=state,
        )
        car_bay_menu.grid(row=row_index, column=1, sticky="ew", padx=3, pady=2)
        widgets["car_bay_label"] = car_bay_menu

        tier_var = ctk.StringVar(value=self._row_tiers.get(item.id, "Standard"))
        tier_menu = ctk.CTkOptionMenu(
            self.grid_scroll, variable=tier_var, values=["Standard", "High"],
            command=lambda _v, iid=item.id: self._on_tier_change(iid), state=state,
        )
        tier_menu.grid(row=row_index, column=2, sticky="ew", padx=3, pady=2)
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

        make_entry(3, "width_m", "" if item.width_m is None else f"{item.width_m:g}")
        make_entry(4, "projection_m", "" if item.projection_m is None else f"{item.projection_m:g}")

        colour_combo = ctk.CTkComboBox(self.grid_scroll, values=["N/A"] + COLOUR_OPTIONS, state=state)
        colour_combo.set(item.colour or "N/A")
        colour_combo.grid(row=row_index, column=5, sticky="ew", padx=3, pady=2)
        colour_combo.bind("<FocusOut>", lambda _e, iid=item.id: self._commit_row(iid))
        colour_combo.bind("<Return>", lambda _e, iid=item.id: self._commit_row(iid))
        colour_combo.configure(command=lambda _v, iid=item.id: self._commit_row(iid))
        widgets["colour"] = colour_combo

        make_entry(6, "quantity", f"{item.quantity:g}")
        make_entry(7, "unit_price", f"{item.unit_price_minor / 100:.2f}")
        make_entry(8, "description", item.description)

        amount_label = ctk.CTkLabel(self.grid_scroll, text=format_money(item.amount_minor, self._quote.currency), anchor="e")
        amount_label.grid(row=row_index, column=9, sticky="ew", padx=3, pady=2)
        widgets["amount"] = amount_label

        delete_button = ctk.CTkButton(
            self.grid_scroll, text="✕", width=28, fg_color="#8B2E2E", hover_color="#6E2222",
            command=lambda iid=item.id: self._delete_row(iid), state=state,
        )
        delete_button.grid(row=row_index, column=10, sticky="ew", padx=3, pady=2)
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
        clobbers a price someone already typed. Also refreshes the Car
        Bay dropdown's options for the newly-selected type (real car-bay
        dimensions for Cantilever/Standard, Single/Double/Triple for
        Cable, just N/A otherwise) - a size picked for the old type
        rarely still makes sense for the new one, so it resets to N/A."""

        widgets = self._row_widgets.get(item_id)
        if widgets is not None:
            current_price = self._parse_float(widgets["unit_price"].get())
            rate = self._rate_for_selected_tier(widgets)
            if rate is not None and not current_price:
                widgets["unit_price"].delete(0, "end")
                widgets["unit_price"].insert(0, f"{rate / 100:.2f}")

            new_labels, _by_label = size_options_for(widgets["structure_type"].get())
            widgets["car_bay_label"].configure(values=new_labels)
            widgets["car_bay_label"].set("N/A")

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
        # Re-derived from the row's CURRENT structure_type, not a fixed
        # universal label set - a size label only means something for
        # types size_options_for() actually recognizes (Cantilever/
        # Standard/Cable); anything else always resolves to None.
        _size_options, size_by_label = size_options_for(structure_type)
        car_bays = size_by_label.get(widgets["car_bay_label"].get())
        width_m = self._parse_float(widgets["width_m"].get())
        projection_m = self._parse_float(widgets["projection_m"].get())

        if car_bays and structure_type in (CANTILEVER, STANDARD) and not (width_m and projection_m):
            width_m, projection_m = car_bay_size(car_bays)

        item.structure_type = structure_type
        item.car_bays = car_bays
        # Shape (Shade Sail) no longer has a grid column - preserve
        # whatever was already stored rather than clearing it.
        item.width_m = width_m
        item.projection_m = projection_m
        # No per-row height field anymore - any charge for height above
        # the 2.1m standard is its own "Additional Height" line item
        # instead. A real structure still needs a height for its own
        # geometry/pricing, so keep the standard default.
        item.height_m = DEFAULT_HEIGHT_M if structure_type in STRUCTURE_TYPES else None
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

    def calculate_prices(self):
        """Fill line-item prices from real supplier costs.

        Prices every Cantilever/Standard row whose size is known, using
        core/structure_quote - materials from the editable Supplier
        Pricing table, plus labour, paint, netting, cable and clamps,
        marked up to the gross profit target. Rows it cannot price
        (Shade Sail, maintenance items, 4-bay structures) are left alone
        and reported, never silently zeroed or guessed at.
        """

        if not self._editable:
            return

        from core.structure_quote import STRUCTURE_GP, can_price, quote_structure, size_for_car_bays

        items = self.quote_service.list_line_items(self.quote_id)
        priceable = [item for item in items if can_price(item.structure_type, item.car_bays)]

        if not priceable:
            messagebox.showinfo(
                "Calculate Prices",
                "No rows can be priced automatically.\n\n"
                "Automatic pricing covers Cantilever and Standard structures "
                "sized 1-3 car bays. Shade sails, maintenance items and 4-bay "
                "structures are still priced by hand.",
                parent=self,
            )
            return

        options = PricingOptionsDialog.ask(self, len(priceable))
        if options is None:
            return

        already_priced = [item for item in priceable if item.unit_price_minor]
        if already_priced and not messagebox.askyesno(
            "Calculate Prices",
            f"{len(already_priced)} of these rows already have a price.\n\nOverwrite them?",
            parent=self,
        ):
            priceable = [item for item in priceable if not item.unit_price_minor]
            if not priceable:
                return

        priced, failures = 0, []
        for item in priceable:
            try:
                gp = options.get("gp", STRUCTURE_GP)
                quote = quote_structure(
                    item.structure_type,
                    size_for_car_bays(item.car_bays),
                    net_supplier=options["net_supplier"],
                    include_paint=options["include_paint"],
                    include_netting=options["include_netting"],
                    back_to_back=options["back_to_back"],
                    structure_gp=gp,
                    netting_gp=gp,
                )
                item.unit_price_minor = round(quote["total_sell"] * 100)
                self.quote_service.save_line_item(item)
                priced += 1
            except ValueError as error:
                failures.append(f"{item.structure_type}: {error}")

        self.refresh()

        skipped = len(items) - len(priceable)
        gp_pct = int(options.get("gp", STRUCTURE_GP) * 100)
        summary = f"Priced {priced} row(s) at {gp_pct}% GP."
        if skipped:
            summary += f"\n{skipped} row(s) left alone - not automatically priceable."
        if failures:
            summary += "\n\nCould not price:\n" + "\n".join(failures[:5])

        messagebox.showinfo("Calculate Prices", summary, parent=self)

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
        if quote.status != "Draft":
            messagebox.showinfo("Issue Quote", "Only a Draft quote can be issued.", parent=self)
            return
        prompt = (
            "Issue this revision? It keeps the same quote number as the original."
            if quote.revision_number
            else "Issue this quote? It will be assigned a permanent number."
        )
        if not messagebox.askyesno("Issue Quote", prompt, parent=self):
            return
        try:
            self.quote_service.issue_quote(self.quote_id, current_actor())
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

        self.quote_service.set_status(self.quote_id, status, current_actor())
        if status == "Accepted":
            self._offer_job_card()
        self.refresh()

    def _offer_job_card(self):
        from core.job_card_service import JobCardService
        from tkinter import messagebox as mb
        quote = self.quote_service.get_quote(self.quote_id)
        if quote is None:
            return
        customer = self.crm_service.get_customer(quote.customer_id)
        if customer is None:
            return
        answer = mb.askyesno(
            "Create Job Card",
            f"Quote accepted — create a Job Card for {customer.name}?",
            parent=self,
        )
        if not answer:
            return
        try:
            svc = JobCardService()
            jc = svc.create_job_card_from_quote(
                customer,
                site_id=quote.site_id or "",
                actor=current_actor(),
                quote_number=quote.quote_number,
                purchase_order=quote.po_number or "",
                bill_to=quote.bill_to_name or customer.name,
                accepted_date=quote.accepted_date or "",
            )
            from modules.site_visit.windows import JobCardWindow
            JobCardWindow(self.winfo_toplevel(), customer, jc, on_change=self.refresh)
        except Exception as exc:
            mb.showerror("Job Card Error", str(exc), parent=self)

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
            {"key": "expiry_date", "label": "Valid Until (YYYY-MM-DD)", "kind": "text", "initial": quote.expiry_date},
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

    def _generate_document(self, generator, pdf_builder, label):

        try:
            document = generator(self.quote_id, current_actor())
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

        def build(output_path):
            pdf_builder(
                document, quote, line_items, customer, site, business, output_path,
                billing_address=billing_address, site_address=site_address, delivery_address=delivery_address,
                postal_address=postal_address, contact_name=contact_name,
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
        item.structure_type = CANTILEVER
        item.height_m = DEFAULT_HEIGHT_M
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


class PricingOptionsDialog(ctk.CTkToplevel):
    """What to include when pricing line items from supplier costs.

    These are the choices that genuinely change the number and that
    Minette makes per job - which net supplier (Knittex has got a lot
    dearer than Plusnet), whether the structures share anchor poles
    back-to-back, and whether paint is in (standard on new installs, but
    not on a frame-only job)."""

    def __init__(self, parent, row_count):
        super().__init__(parent)

        self.title("Calculate Prices")
        self.geometry("430x390")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None

        ctk.CTkLabel(
            self, text=f"Pricing {row_count} line item(s)", font=("Segoe UI", 14, "bold"),
        ).pack(pady=(15, 4), padx=20, anchor="w")
        ctk.CTkLabel(
            self,
            text="Costs come from Settings > Supplier Pricing, so they stay current.",
            text_color=COLORS["text_secondary"], wraplength=380, justify="left",
        ).pack(pady=(0, 12), padx=20, anchor="w")

        ctk.CTkLabel(self, text="Gross profit margin").pack(padx=20, anchor="w")
        self.gp_var = ctk.StringVar(value="45%")
        ctk.CTkOptionMenu(
            self, values=["45%", "65%"], variable=self.gp_var, width=250,
        ).pack(padx=20, pady=(2, 12), anchor="w")

        ctk.CTkLabel(self, text="Netting supplier").pack(padx=20, anchor="w")
        self.supplier_var = ctk.StringVar(value="Plusnet")
        ctk.CTkOptionMenu(
            self, values=self._netting_suppliers(), variable=self.supplier_var, width=250,
        ).pack(padx=20, pady=(2, 12), anchor="w")

        self.netting_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self, text="Include netting, cable and clamps", variable=self.netting_var).pack(
            padx=20, pady=4, anchor="w",
        )

        self.paint_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self, text="Include paint (standard on new installs)", variable=self.paint_var).pack(
            padx=20, pady=4, anchor="w",
        )

        self.back_to_back_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self, text="Back-to-back (shared poles, 10% off steel)", variable=self.back_to_back_var,
        ).pack(padx=20, pady=4, anchor="w")

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=20, pady=(16, 15))
        ctk.CTkButton(button_row, text="Cancel", command=self._cancel, width=100).pack(side="right", padx=4)
        ctk.CTkButton(button_row, text="Calculate", command=self._ok, width=100).pack(side="right", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Return>", lambda _event: self._ok())
        self.bind("<Escape>", lambda _event: self._cancel())

    def _netting_suppliers(self):

        try:
            from core.supplier_pricing_service import SupplierPricingService

            names = [item.supplier_name for item in SupplierPricingService().list_items("Netting")]
            return sorted(set(names)) or ["Plusnet"]
        except Exception:
            return ["Plusnet"]

    def _ok(self):

        from core.structure_quote import GP_OPTIONS
        gp = GP_OPTIONS.get(self.gp_var.get(), 0.45)
        self.result = {
            "net_supplier": self.supplier_var.get(),
            "include_netting": bool(self.netting_var.get()),
            "include_paint": bool(self.paint_var.get()),
            "back_to_back": bool(self.back_to_back_var.get()),
            "gp": gp,
        }
        self.destroy()

    def _cancel(self):

        self.result = None
        self.destroy()

    @classmethod
    def ask(cls, parent, row_count):
        dialog = cls(parent, row_count)
        dialog.wait_window()
        return dialog.result
