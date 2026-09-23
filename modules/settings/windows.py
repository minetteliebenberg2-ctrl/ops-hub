# ==========================================================
# FC Hub - Settings Window
# ----------------------------------------------------------
# Purpose:
# The business's own business details, banking, and business
# addresses. Distinct from CRM customer records.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import getpass
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from core.business_settings_service import BusinessSettingsService
from core.ledger_service import EXPENSE, INCOME, LedgerService
from core.picklist_service import CUSTOMER_TYPE, DOCUMENT_CATEGORY, LINE_ITEM_TYPE, PAYMENT_TERMS, PicklistService
from core.job_cost_item import COST_BUCKETS, JobCostItem, JobCostItemRepository
from core.supplier_pricing_repository import CATEGORIES as SUPPLIER_PRICE_CATEGORIES
from core.supplier_pricing_service import SupplierPricingService
from gui.entity_table import build_entity_table
from gui.form_dialogs import EntityFormDialog


# Physical first - same default as CRM (see its ADDRESS_TYPES note).
ADDRESS_TYPES = ("Physical", "Delivery", "Billing", "Postal")


def current_actor():

    try:
        return getpass.getuser()
    except Exception:
        return ""


class SettingsWindow(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)

        self.service = BusinessSettingsService()
        self.picklists = PicklistService()
        self.ledger_service = LedgerService()
        self.supplier_pricing = SupplierPricingService()
        self.supplier_price_category = SUPPLIER_PRICE_CATEGORIES[0]
        self.job_cost_repo = JobCostItemRepository()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Settings", font=("Segoe UI", 22, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 15))

        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, sticky="nsew")

        self._build_business_tab()
        self._build_addresses_tab()
        self._build_payment_terms_tab()
        self._build_customer_types_tab()
        self._build_document_types_tab()
        self._build_line_item_types_tab()
        self._build_job_costing_tab()
        self._build_ledger_categories_tab()
        self._build_supplier_pricing_tab()
        self._build_appearance_tab()

        self.refresh()

    def _build_appearance_tab(self):

        from modules.settings.appearance_panel import AppearancePanel

        tab = self.tabs.add("Appearance")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        AppearancePanel(tab).grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

    # --------------------------------------------------
    # Business details
    # --------------------------------------------------

    def _build_business_tab(self):

        tab = self.tabs.add("Business Details")
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(tab, text="Edit Business Details", command=self.edit_business_details, width=180).grid(
            row=0, column=0, sticky="w", padx=10, pady=10
        )

        card = ctk.CTkFrame(tab)
        card.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        tab.grid_rowconfigure(1, weight=1)

        self.business_label = ctk.CTkLabel(card, justify="left", anchor="nw", font=("Consolas", 13))
        self.business_label.pack(fill="both", expand=True, padx=15, pady=15)

    def edit_business_details(self):

        settings = self.service.get_settings()

        fields = [
            {"key": "trading_name", "label": "Trading Name", "kind": "text", "initial": settings.trading_name},
            {"key": "legal_name", "label": "Legal / Registered Name", "kind": "text", "initial": settings.legal_name},
            {"key": "registration_number", "label": "Registration Number", "kind": "text", "initial": settings.registration_number},
            {"key": "vat_registered", "label": "VAT registered", "kind": "checkbox", "initial": settings.vat_registered},
            {"key": "vat_number", "label": "VAT Number (if registered)", "kind": "text", "initial": settings.vat_number},
            {"key": "email", "label": "Email", "kind": "text", "initial": settings.email},
            {"key": "phone", "label": "Phone", "kind": "text", "initial": settings.phone},
            {"key": "website", "label": "Website", "kind": "text", "initial": settings.website},
            {"key": "bank_name", "label": "Bank Name", "kind": "text", "initial": settings.bank_name},
            {"key": "bank_account_name", "label": "Bank Account Name", "kind": "text", "initial": settings.bank_account_name},
            {"key": "bank_account_number", "label": "Bank Account Number", "kind": "text", "initial": settings.bank_account_number},
            {"key": "branch_code", "label": "Branch / BC Code", "kind": "text", "initial": settings.branch_code},
            {"key": "swift_code", "label": "Swift Code", "kind": "text", "initial": settings.swift_code},
            {"key": "deposit_percent", "label": "Deposit % (balance is the rest)", "kind": "text",
             "initial": str(settings.deposit_percent or 65)},
            {"key": "notes", "label": "Notes", "kind": "textarea", "initial": settings.notes},
        ]

        result = EntityFormDialog.ask(self.winfo_toplevel(), "Edit Business Details", fields)
        if result is None:
            return

        settings.trading_name = result["trading_name"]
        settings.legal_name = result["legal_name"]
        settings.registration_number = result["registration_number"]
        settings.vat_registered = result["vat_registered"]
        settings.vat_number = result["vat_number"]
        settings.email = result["email"]
        settings.phone = result["phone"]
        settings.website = result["website"]
        settings.bank_name = result["bank_name"]
        settings.bank_account_name = result["bank_account_name"]
        settings.bank_account_number = result["bank_account_number"]
        settings.branch_code = result["branch_code"]
        settings.swift_code = result["swift_code"]
        settings.deposit_percent = result["deposit_percent"]
        settings.notes = result["notes"]

        try:
            self.service.save_settings(settings, current_actor())
        except ValueError as error:
            messagebox.showerror("Business Details", str(error), parent=self.winfo_toplevel())
            return

        self.refresh()

    def _render_business_details(self):

        settings = self.service.get_settings()
        vat_line = f"VAT Number: {settings.vat_number}" if settings.vat_registered else "Not VAT registered"

        text = (
            f"Trading Name:        {settings.trading_name}\n"
            f"Legal Name:          {settings.legal_name}\n"
            f"Registration Number: {settings.registration_number}\n"
            f"{vat_line}\n"
            "\n"
            f"Email:   {settings.email}\n"
            f"Phone:   {settings.phone}\n"
            f"Website: {settings.website}\n"
            "\n"
            "Banking\n"
            f"Bank:            {settings.bank_name}\n"
            f"Account Name:    {settings.bank_account_name}\n"
            f"Account Number:  {settings.bank_account_number}\n"
            f"Branch Code:     {settings.branch_code}\n"
            f"Swift Code:      {settings.swift_code}\n"
            "\n"
            "Invoicing\n"
            f"Deposit:         {settings.deposit_percent}%  "
            f"(balance {100 - int(settings.deposit_percent or 65)}%)\n"
        )
        if settings.notes:
            text += f"\nNotes\n{settings.notes}\n"

        self.business_label.configure(text=text)

    # --------------------------------------------------
    # Business addresses
    # --------------------------------------------------

    def _build_addresses_tab(self):

        tab = self.tabs.add("Addresses")
        self.address_table = build_entity_table(
            tab,
            ("Type", "Line 1", "City", "Province", "Postal Code", "Primary"),
            (
                ("Refresh", self.refresh),
                ("New Address", self.new_address),
                ("Edit", self.edit_address),
                ("Delete", self.delete_address),
            ),
        )

    def _selected_address(self):

        selection = self.address_table.selection()
        if not selection:
            messagebox.showwarning("Address", "Select an address first.", parent=self.winfo_toplevel())
            return None
        return self.service.address_repository.get(selection[0])

    def new_address(self):

        self._open_address_dialog(self.service.new_address(), is_new=True)

    def edit_address(self):

        address = self._selected_address()
        if address is None:
            return
        self._open_address_dialog(address, is_new=False)

    def _open_address_dialog(self, address, is_new):

        fields = [
            {"key": "address_type", "label": "Address Type", "kind": "dropdown", "options": ADDRESS_TYPES, "initial": address.address_type or ADDRESS_TYPES[0]},
            {"key": "line1", "label": "Line 1", "kind": "text", "initial": address.line1},
            {"key": "line2", "label": "Line 2", "kind": "text", "initial": address.line2},
            {"key": "city", "label": "City", "kind": "text", "initial": address.city},
            {"key": "province", "label": "Province", "kind": "text", "initial": address.province},
            {"key": "postal_code", "label": "Postal Code", "kind": "text", "initial": address.postal_code},
            {"key": "country", "label": "Country", "kind": "text", "initial": address.country or "South Africa"},
            {"key": "is_primary", "label": "Primary address for this type", "kind": "checkbox", "initial": address.is_primary},
        ]
        title = "New Business Address" if is_new else "Edit Business Address"
        result = EntityFormDialog.ask(self.winfo_toplevel(), title, fields)
        if result is None:
            return

        address.address_type = result["address_type"]
        address.line1 = result["line1"]
        address.line2 = result["line2"]
        address.city = result["city"]
        address.province = result["province"]
        address.postal_code = result["postal_code"]
        address.country = result["country"]
        address.is_primary = result["is_primary"]

        try:
            self.service.save_address(address, current_actor())
        except ValueError as error:
            messagebox.showerror("Address", str(error), parent=self.winfo_toplevel())
            return

        self.refresh()

    def delete_address(self):

        address = self._selected_address()
        if address is None:
            return
        if not messagebox.askyesno(
            "Delete Address",
            f"Delete this address?\n\n{address.line1}, {address.city}",
            parent=self.winfo_toplevel(),
        ):
            return
        self.service.delete_address(address.id)
        self.refresh()

    def _load_addresses(self):

        self.address_table.delete(*self.address_table.get_children())
        for address in self.service.list_addresses():
            self.address_table.insert(
                "",
                "end",
                iid=address.id,
                text=address.address_type,
                values=(
                    address.address_type,
                    address.line1,
                    address.city,
                    address.province,
                    address.postal_code,
                    "Yes" if address.is_primary else "",
                ),
            )

    # --------------------------------------------------

    def refresh(self):

        self._render_business_details()
        self._load_addresses()
        self._load_payment_terms()
        self._load_customer_types()
        self._load_document_types()
        self._load_line_item_types()
        self._load_job_cost_items()
        self._load_ledger_categories()
        self._load_supplier_price_items()

    # --------------------------------------------------
    # Payment terms (with real deposit/balance percentages)
    # --------------------------------------------------

    def _build_payment_terms_tab(self):

        tab = self.tabs.add("Payment Terms")
        self.payment_terms_table = build_entity_table(
            tab,
            ("Deposit %", "Balance %", "Status"),
            (
                ("Refresh", self.refresh),
                ("New Term", self.new_payment_term),
                ("Edit", self.edit_payment_term),
                ("Deactivate", self.deactivate_payment_term),
                ("Reactivate", self.reactivate_payment_term),
                ("Delete", self.delete_payment_term),
            ),
        )

    def _selected_payment_term(self):

        selection = self.payment_terms_table.selection()
        if not selection:
            messagebox.showwarning("Payment Terms", "Select a payment term first.", parent=self.winfo_toplevel())
            return None
        return self.picklists.repository.get(selection[0])

    def new_payment_term(self):

        self._open_payment_term_dialog(self.picklists.new_option(PAYMENT_TERMS), is_new=True)

    def edit_payment_term(self):

        option = self._selected_payment_term()
        if option is None:
            return
        self._open_payment_term_dialog(option, is_new=False)

    def _open_payment_term_dialog(self, option, is_new):

        fields = [
            {"key": "value", "label": "Term Name", "kind": "text", "initial": option.value},
            {"key": "deposit_percentage", "label": "Deposit %", "kind": "text", "initial": "" if option.deposit_percentage is None else str(option.deposit_percentage)},
            {"key": "balance_percentage", "label": "Balance %", "kind": "text", "initial": "" if option.balance_percentage is None else str(option.balance_percentage)},
        ]
        title = "New Payment Term" if is_new else f"Edit Payment Term — {option.value}"
        result = EntityFormDialog.ask(self.winfo_toplevel(), title, fields)
        if result is None:
            return

        try:
            deposit = float(result["deposit_percentage"] or 0)
            balance = float(result["balance_percentage"] or 0)
        except ValueError:
            messagebox.showerror("Payment Terms", "Deposit % and balance % must be numbers.", parent=self.winfo_toplevel())
            return

        option.value = result["value"]
        option.deposit_percentage = deposit
        option.balance_percentage = balance

        try:
            self.picklists.save_option(option, current_actor())
        except ValueError as error:
            messagebox.showerror("Payment Terms", str(error), parent=self.winfo_toplevel())
            return

        self.refresh()

    def deactivate_payment_term(self):

        option = self._selected_payment_term()
        if option is None:
            return
        self.picklists.deactivate_option(option.id, current_actor())
        self.refresh()

    def reactivate_payment_term(self):

        option = self._selected_payment_term()
        if option is None:
            return
        self.picklists.reactivate_option(option.id, current_actor())
        self.refresh()

    def delete_payment_term(self):

        option = self._selected_payment_term()
        if option is None:
            return
        if not messagebox.askyesno(
            "Delete Payment Term",
            f"Delete \"{option.value}\" permanently? Customers already using this term keep their stored value; "
            "deleting only removes it from the picker.",
            parent=self.winfo_toplevel(),
        ):
            return
        self.picklists.delete_option(option.id)
        self.refresh()

    def _load_payment_terms(self):

        self.payment_terms_table.delete(*self.payment_terms_table.get_children())
        for option in self.picklists.list_options(PAYMENT_TERMS, include_inactive=True):
            self.payment_terms_table.insert(
                "",
                "end",
                iid=option.id,
                text=option.value,
                values=(
                    "" if option.deposit_percentage is None else f"{option.deposit_percentage:g}",
                    "" if option.balance_percentage is None else f"{option.balance_percentage:g}",
                    "Active" if option.is_active else "Inactive",
                ),
            )

    # --------------------------------------------------
    # Customer types
    # --------------------------------------------------

    def _build_customer_types_tab(self):

        tab = self.tabs.add("Customer Types")
        self.customer_types_table = build_entity_table(
            tab,
            ("Status",),
            (
                ("Refresh", self.refresh),
                ("New Type", self.new_customer_type),
                ("Edit", self.edit_customer_type),
                ("Deactivate", self.deactivate_customer_type),
                ("Reactivate", self.reactivate_customer_type),
                ("Delete", self.delete_customer_type),
            ),
        )

    def _selected_customer_type(self):

        selection = self.customer_types_table.selection()
        if not selection:
            messagebox.showwarning("Customer Types", "Select a customer type first.", parent=self.winfo_toplevel())
            return None
        return self.picklists.repository.get(selection[0])

    def new_customer_type(self):

        self._open_customer_type_dialog(self.picklists.new_option(CUSTOMER_TYPE), is_new=True)

    def edit_customer_type(self):

        option = self._selected_customer_type()
        if option is None:
            return
        self._open_customer_type_dialog(option, is_new=False)

    def _open_customer_type_dialog(self, option, is_new):

        fields = [{"key": "value", "label": "Type Name", "kind": "text", "initial": option.value}]
        title = "New Customer Type" if is_new else f"Edit Customer Type — {option.value}"
        result = EntityFormDialog.ask(self.winfo_toplevel(), title, fields)
        if result is None:
            return

        option.value = result["value"]

        try:
            self.picklists.save_option(option, current_actor())
        except ValueError as error:
            messagebox.showerror("Customer Types", str(error), parent=self.winfo_toplevel())
            return

        self.refresh()

    def deactivate_customer_type(self):

        option = self._selected_customer_type()
        if option is None:
            return
        self.picklists.deactivate_option(option.id, current_actor())
        self.refresh()

    def reactivate_customer_type(self):

        option = self._selected_customer_type()
        if option is None:
            return
        self.picklists.reactivate_option(option.id, current_actor())
        self.refresh()

    def delete_customer_type(self):

        option = self._selected_customer_type()
        if option is None:
            return
        if not messagebox.askyesno(
            "Delete Customer Type",
            f"Delete \"{option.value}\" permanently? Customers already using this type keep their stored value; "
            "deleting only removes it from the picker.",
            parent=self.winfo_toplevel(),
        ):
            return
        self.picklists.delete_option(option.id)
        self.refresh()

    def _load_customer_types(self):

        self.customer_types_table.delete(*self.customer_types_table.get_children())
        for option in self.picklists.list_options(CUSTOMER_TYPE, include_inactive=True):
            self.customer_types_table.insert(
                "",
                "end",
                iid=option.id,
                text=option.value,
                values=("Active" if option.is_active else "Inactive",),
            )

    # --------------------------------------------------
    # Document types (Documents module category + Annual Compliance
    # certificate type). Soft-delete only ("recycle") - deleting a type
    # the type disappears from pickers but stays in the DB so it can be
    # restored, and any document already filed under it keeps the label
    # as plain text (category is not a foreign key).
    # --------------------------------------------------

    def _build_document_types_tab(self):

        tab = self.tabs.add("Document Types")
        self.document_types_table = build_entity_table(
            tab,
            ("Status",),
            (
                ("Refresh", self.refresh),
                ("New Type", self.new_document_type),
                ("Edit", self.edit_document_type),
                ("Delete (recycle)", self.delete_document_type),
                ("Restore", self.restore_document_type),
            ),
        )

    def _selected_document_type(self):

        selection = self.document_types_table.selection()
        if not selection:
            messagebox.showwarning("Document Types", "Select a document type first.", parent=self.winfo_toplevel())
            return None
        return self.picklists.repository.get(selection[0])

    def new_document_type(self):

        self._open_document_type_dialog(self.picklists.new_option(DOCUMENT_CATEGORY), is_new=True)

    def edit_document_type(self):

        option = self._selected_document_type()
        if option is None:
            return
        self._open_document_type_dialog(option, is_new=False)

    def _open_document_type_dialog(self, option, is_new):

        fields = [{"key": "value", "label": "Type Name", "kind": "text", "initial": option.value}]
        title = "New Document Type" if is_new else f"Edit Document Type — {option.value}"
        result = EntityFormDialog.ask(self.winfo_toplevel(), title, fields)
        if result is None:
            return

        option.value = result["value"]

        try:
            self.picklists.save_option(option, current_actor())
        except ValueError as error:
            messagebox.showerror("Document Types", str(error), parent=self.winfo_toplevel())
            return

        self.refresh()

    def delete_document_type(self):

        option = self._selected_document_type()
        if option is None:
            return
        if not messagebox.askyesno(
            "Delete Document Type",
            f"Move \"{option.value}\" to the recycle bin? It disappears from the picker but can be "
            "restored, and documents already filed under it keep the label.",
            parent=self.winfo_toplevel(),
        ):
            return
        self.picklists.deactivate_option(option.id, current_actor())
        self.refresh()

    def restore_document_type(self):

        option = self._selected_document_type()
        if option is None:
            return
        self.picklists.reactivate_option(option.id, current_actor())
        self.refresh()

    def _load_document_types(self):

        self.document_types_table.delete(*self.document_types_table.get_children())
        for option in self.picklists.list_options(DOCUMENT_CATEGORY, include_inactive=True):
            self.document_types_table.insert(
                "",
                "end",
                iid=option.id,
                text=option.value,
                values=("Active" if option.is_active else "Recycled",),
            )

    # --------------------------------------------------
    # Line item types (Quote grid's "Structure" column — Cantilever/
    # Standard/Shade Sail plus whatever else Minette adds, e.g.
    # Maintenance or a one-off client request)
    # --------------------------------------------------

    def _build_line_item_types_tab(self):

        tab = self.tabs.add("Line Item Types")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="Options for the Structure column on a Quote's line item grid.",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))

        table_container = ctk.CTkFrame(tab, fg_color="transparent")
        table_container.grid(row=1, column=0, sticky="nsew")

        self.line_item_types_table = build_entity_table(
            table_container,
            ("Standard Rate", "High Rate", "Status"),
            (
                ("Refresh", self.refresh),
                ("New Type", self.new_line_item_type),
                ("From Supplier Pricing", self._pick_from_supplier_pricing),
                ("Edit", self.edit_line_item_type),
                ("Deactivate", self.deactivate_line_item_type),
                ("Reactivate", self.reactivate_line_item_type),
                ("Delete", self.delete_line_item_type),
            ),
        )

    def _selected_line_item_type(self):

        selection = self.line_item_types_table.selection()
        if not selection:
            messagebox.showwarning("Line Item Types", "Select a line item type first.", parent=self.winfo_toplevel())
            return None
        return self.picklists.repository.get(selection[0])

    def new_line_item_type(self):

        self._open_line_item_type_dialog(self.picklists.new_option(LINE_ITEM_TYPE), is_new=True)

    def edit_line_item_type(self):

        option = self._selected_line_item_type()
        if option is None:
            return
        self._open_line_item_type_dialog(option, is_new=False)

    def _open_line_item_type_dialog(self, option, is_new):

        fields = [
            {"key": "value", "label": "Type Name", "kind": "text", "initial": option.value},
            {
                "key": "rate_standard",
                "label": "Standard Rate (R, optional — blank if not a flat-rate item, e.g. a real structure)",
                "kind": "text",
                "initial": "" if option.rate_standard_minor is None else f"{option.rate_standard_minor / 100:.2f}",
            },
            {
                "key": "rate_high",
                "label": "High Rate (R, optional)",
                "kind": "text",
                "initial": "" if option.rate_high_minor is None else f"{option.rate_high_minor / 100:.2f}",
            },
        ]
        title = "New Line Item Type" if is_new else f"Edit Line Item Type — {option.value}"
        result = EntityFormDialog.ask(self.winfo_toplevel(), title, fields)
        if result is None:
            return

        try:
            rate_standard = result["rate_standard"].strip()
            rate_high = result["rate_high"].strip()
            option.rate_standard_minor = round(float(rate_standard) * 100) if rate_standard else None
            option.rate_high_minor = round(float(rate_high) * 100) if rate_high else None
        except ValueError:
            messagebox.showerror("Line Item Types", "Rates must be numbers.", parent=self.winfo_toplevel())
            return

        option.value = result["value"]

        try:
            self.picklists.save_option(option, current_actor())
        except ValueError as error:
            messagebox.showerror("Line Item Types", str(error), parent=self.winfo_toplevel())
            return

        self.refresh()

    def deactivate_line_item_type(self):

        option = self._selected_line_item_type()
        if option is None:
            return
        self.picklists.deactivate_option(option.id, current_actor())
        self.refresh()

    def reactivate_line_item_type(self):

        option = self._selected_line_item_type()
        if option is None:
            return
        self.picklists.reactivate_option(option.id, current_actor())
        self.refresh()

    def delete_line_item_type(self):

        option = self._selected_line_item_type()
        if option is None:
            return
        if not messagebox.askyesno(
            "Delete Line Item Type",
            f"Delete \"{option.value}\" permanently? Line items already using this type keep their stored value; "
            "deleting only removes it from the picker.",
            parent=self.winfo_toplevel(),
        ):
            return
        self.picklists.delete_option(option.id)
        self.refresh()

    def _load_line_item_types(self):

        self.line_item_types_table.delete(*self.line_item_types_table.get_children())
        for option in self.picklists.list_options(LINE_ITEM_TYPE, include_inactive=True):
            self.line_item_types_table.insert(
                "",
                "end",
                iid=option.id,
                text=option.value,
                values=(
                    "" if option.rate_standard_minor is None else f"R{option.rate_standard_minor / 100:,.2f}",
                    "" if option.rate_high_minor is None else f"R{option.rate_high_minor / 100:,.2f}",
                    "Active" if option.is_active else "Inactive",
                ),
            )


    def _pick_from_supplier_pricing(self):
        _SupplierPricingPickerDialog(
            self.winfo_toplevel(),
            supplier_pricing=self.supplier_pricing,
            picklists=self.picklists,
            on_done=self.refresh,
        )

    # --------------------------------------------------
    # Job Costing — editable cost buckets + GP% for KPI
    # --------------------------------------------------

    def _build_job_costing_tab(self):

        tab = self.tabs.add("Job Costing")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="Cost assumptions — maps line item types to a cost bucket and GP%.",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))

        table_container = ctk.CTkFrame(tab, fg_color="transparent")
        table_container.grid(row=1, column=0, sticky="nsew")

        self.job_cost_table = build_entity_table(
            table_container,
            ("Sell Price (R)", "Cost (R)", "Cost Bucket", "GP %", "Status"),
            (
                ("Refresh", self.refresh),
                ("New Item", self._new_job_cost_item),
                ("Edit", self._edit_job_cost_item),
                ("Deactivate", self._deactivate_job_cost_item),
                ("Delete", self._delete_job_cost_item),
            ),
        )

    def _selected_job_cost_item(self):
        selection = self.job_cost_table.selection()
        if not selection:
            messagebox.showwarning("Job Costing", "Select an item first.", parent=self.winfo_toplevel())
            return None
        return self.job_cost_repo.get(selection[0])

    def _new_job_cost_item(self):
        self._open_job_cost_dialog(JobCostItem(), is_new=True)

    def _edit_job_cost_item(self):
        item = self._selected_job_cost_item()
        if item:
            self._open_job_cost_dialog(item, is_new=False)

    def _open_job_cost_dialog(self, item, is_new):
        fields = [
            {"key": "name", "label": "Item Name (must match a Quote line item type)", "kind": "text", "initial": item.name},
            {"key": "unit_price", "label": "Price (R)", "kind": "text", "initial": f"{item.unit_price:g}" if item.unit_price else "0"},
            {"key": "cost_bucket", "label": "Cost Bucket", "kind": "dropdown", "options": list(COST_BUCKETS), "initial": item.cost_bucket},
            {"key": "gp_percent", "label": "GP % (e.g. 45)", "kind": "text", "initial": f"{item.gp_percent:g}"},
        ]
        title = "New Job Cost Item" if is_new else f"Edit — {item.name}"
        result = EntityFormDialog.ask(self.winfo_toplevel(), title, fields)
        if result is None:
            return

        try:
            gp = float(result["gp_percent"])
            if not (0 <= gp <= 100):
                raise ValueError
        except ValueError:
            messagebox.showerror("Job Costing", "GP% must be a number between 0 and 100.", parent=self.winfo_toplevel())
            return

        try:
            price = float(result.get("unit_price", "0") or "0")
            if price < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Job Costing", "Price must be a positive number.", parent=self.winfo_toplevel())
            return

        item.name = result["name"].strip()
        item.unit_price = price
        item.cost_bucket = result["cost_bucket"]
        item.gp_percent = gp

        try:
            self.job_cost_repo.save(item)
        except Exception as error:
            messagebox.showerror("Job Costing", str(error), parent=self.winfo_toplevel())
            return
        self.refresh()

    def _deactivate_job_cost_item(self):
        item = self._selected_job_cost_item()
        if item is None:
            return
        item.is_active = not item.is_active
        self.job_cost_repo.save(item)
        self.refresh()

    def _delete_job_cost_item(self):
        item = self._selected_job_cost_item()
        if item is None:
            return
        if not messagebox.askyesno("Delete", f"Delete \"{item.name}\" permanently?", parent=self.winfo_toplevel()):
            return
        self.job_cost_repo.delete(item.id)
        self.refresh()

    def _load_job_cost_items(self):
        self.job_cost_table.delete(*self.job_cost_table.get_children())
        for item in self.job_cost_repo.list_all(include_inactive=True):
            cost = item.unit_price * (1 - item.gp_percent / 100) if item.unit_price else 0
            self.job_cost_table.insert(
                "", "end", iid=item.id, text=item.name,
                values=(
                    f"R {item.unit_price:,.2f}" if item.unit_price else "—",
                    f"R {cost:,.2f}" if cost else "—",
                    item.cost_bucket.title(),
                    f"{item.gp_percent:g}%",
                    "Active" if item.is_active else "Inactive",
                ),
            )

    # --------------------------------------------------
    # Ledger categories (self-service Income/Expense categories for
    # Accounting - moved out of hardcoded Python lists, migration
    # v0020. Retiring hides a category from new-entry dropdowns
    # without deleting it or breaking existing transactions.)
    # --------------------------------------------------

    def _build_ledger_categories_tab(self):

        tab = self.tabs.add("Ledger Categories")
        self.ledger_categories_table = build_entity_table(
            tab,
            ("Type", "Status"),
            (
                ("Refresh", self.refresh),
                ("New Category", self.new_ledger_category),
                ("Rename", self.rename_ledger_category),
                ("Retire", self.retire_ledger_category),
                ("Reactivate", self.reactivate_ledger_category),
            ),
        )

    def _selected_ledger_category(self):

        selection = self.ledger_categories_table.selection()
        if not selection:
            messagebox.showwarning("Ledger Categories", "Select a category first.", parent=self.winfo_toplevel())
            return None
        return self.ledger_service.category_repository.get(selection[0])

    def new_ledger_category(self):

        fields = [
            {"key": "name", "label": "Category Name", "kind": "text", "initial": ""},
            {"key": "category_type", "label": "Type", "kind": "dropdown", "options": [INCOME, EXPENSE], "initial": EXPENSE},
        ]
        result = EntityFormDialog.ask(self.winfo_toplevel(), "New Ledger Category", fields)
        if result is None:
            return

        try:
            self.ledger_service.add_category(result["name"].strip(), result["category_type"], current_actor())
        except ValueError as error:
            messagebox.showerror("Ledger Categories", str(error), parent=self.winfo_toplevel())
            return

        self.refresh()

    def rename_ledger_category(self):

        category = self._selected_ledger_category()
        if category is None:
            return

        result = EntityFormDialog.ask(
            self.winfo_toplevel(), f"Rename Category — {category.name}",
            [{"key": "name", "label": "Category Name", "kind": "text", "initial": category.name}],
        )
        if result is None:
            return

        try:
            self.ledger_service.rename_category(category.id, result["name"].strip())
        except ValueError as error:
            messagebox.showerror("Ledger Categories", str(error), parent=self.winfo_toplevel())
            return

        self.refresh()

    def retire_ledger_category(self):

        category = self._selected_ledger_category()
        if category is None:
            return
        self.ledger_service.retire_category(category.id)
        self.refresh()

    def reactivate_ledger_category(self):

        category = self._selected_ledger_category()
        if category is None:
            return
        self.ledger_service.reactivate_category(category.id)
        self.refresh()

    def _load_ledger_categories(self):

        self.ledger_categories_table.delete(*self.ledger_categories_table.get_children())
        for category in self.ledger_service.category_repository.list_all(active_only=False):
            self.ledger_categories_table.insert(
                "",
                "end",
                iid=category.id,
                text=category.name,
                values=(
                    category.category_type,
                    "Active" if category.active else "Retired",
                ),
            )

    # --------------------------------------------------
    # Supplier pricing (Steel/Netting/Paint/Hardware/Labour costs used
    # by Quotes and the Suppliers structure/labour costing — every
    # figure here is user-editable rather than hardcoded, since
    # supplier costs change frequently. More than one row can share
    # an item_name, e.g. "90% Shade Netting" under both Knittex Z25
    # and Plusnet, so the same item can offer a real supplier choice.)
    # --------------------------------------------------

    def _build_supplier_pricing_tab(self):

        tab = self.tabs.add("Supplier Pricing")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        category_row = ctk.CTkFrame(tab, fg_color="transparent")
        category_row.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 8))
        ctk.CTkLabel(category_row, text="Category:").pack(side="left", padx=(0, 8))
        self.supplier_price_category_var = ctk.StringVar(value=self.supplier_price_category)
        ctk.CTkOptionMenu(
            category_row,
            values=list(SUPPLIER_PRICE_CATEGORIES),
            variable=self.supplier_price_category_var,
            command=self._on_supplier_price_category_change,
        ).pack(side="left")
        ctk.CTkButton(
            category_row, text="Import from PDF", width=140,
            command=self._open_supplier_import_dialog,
        ).pack(side="left", padx=(16, 0))

        table_container = ctk.CTkFrame(tab, fg_color="transparent")
        table_container.grid(row=1, column=0, sticky="nsew")

        self.supplier_price_table = build_entity_table(
            table_container,
            ("Supplier", "Spec", "Unit", "Cost", "Status"),
            (
                ("Refresh", self.refresh),
                ("New Item", self.new_supplier_price_item),
                ("Edit", self.edit_supplier_price_item),
                ("Deactivate", self.deactivate_supplier_price_item),
                ("Reactivate", self.reactivate_supplier_price_item),
                ("Delete", self.delete_supplier_price_item),
            ),
        )

    def _on_supplier_price_category_change(self, value):

        self.supplier_price_category = value
        self._load_supplier_price_items()

    def _selected_supplier_price_item(self):

        selection = self.supplier_price_table.selection()
        if not selection:
            messagebox.showwarning("Supplier Pricing", "Select an item first.", parent=self.winfo_toplevel())
            return None
        return self.supplier_pricing.repository.get(selection[0])

    def new_supplier_price_item(self):

        self._open_supplier_price_dialog(self.supplier_pricing.new_item(self.supplier_price_category), is_new=True)

    def edit_supplier_price_item(self):

        item = self._selected_supplier_price_item()
        if item is None:
            return
        self._open_supplier_price_dialog(item, is_new=False)

    def _open_supplier_price_dialog(self, item, is_new):

        fields = [
            {
                "key": "category", "label": "Category", "kind": "dropdown",
                "options": list(SUPPLIER_PRICE_CATEGORIES), "initial": item.category,
            },
            {"key": "item_name", "label": "Item Name", "kind": "text", "initial": item.item_name},
            {"key": "supplier_name", "label": "Supplier", "kind": "text", "initial": item.supplier_name},
            {"key": "spec", "label": "Spec (optional)", "kind": "text", "initial": item.spec},
            {
                "key": "unit", "label": "Unit", "kind": "combo",
                "options": ("per 6m", "per LM", "per m", "per 20L", "each", "per bag", "per set"),
                "initial": item.unit,
            },
            {
                "key": "cost", "label": "Cost (R)", "kind": "text",
                "initial": "" if not item.cost_minor else f"{item.cost_minor / 100:.2f}",
            },
        ]
        title = "New Supplier Price Item" if is_new else f"Edit — {item.item_name} ({item.supplier_name})"
        result = EntityFormDialog.ask(self.winfo_toplevel(), title, fields)
        if result is None:
            return

        try:
            cost = result["cost"].strip()
            item.cost_minor = round(float(cost) * 100) if cost else 0
        except ValueError:
            messagebox.showerror("Supplier Pricing", "Cost must be a number.", parent=self.winfo_toplevel())
            return

        item.category = result["category"]
        item.item_name = result["item_name"]
        item.supplier_name = result["supplier_name"]
        item.spec = result["spec"]
        item.unit = result["unit"]

        try:
            self.supplier_pricing.save_item(item, current_actor())
        except ValueError as error:
            messagebox.showerror("Supplier Pricing", str(error), parent=self.winfo_toplevel())
            return

        self.refresh()

    def deactivate_supplier_price_item(self):

        item = self._selected_supplier_price_item()
        if item is None:
            return
        self.supplier_pricing.deactivate_item(item.id, current_actor())
        self.refresh()

    def reactivate_supplier_price_item(self):

        item = self._selected_supplier_price_item()
        if item is None:
            return
        self.supplier_pricing.reactivate_item(item.id, current_actor())
        self.refresh()

    def delete_supplier_price_item(self):

        item = self._selected_supplier_price_item()
        if item is None:
            return
        if not messagebox.askyesno(
            "Delete Supplier Price Item",
            f"Delete \"{item.item_name}\" ({item.supplier_name}) permanently?",
            parent=self.winfo_toplevel(),
        ):
            return
        self.supplier_pricing.delete_item(item.id)
        self.refresh()

    def _load_supplier_price_items(self):

        if not hasattr(self, "supplier_price_table"):
            return

        self.supplier_price_table.delete(*self.supplier_price_table.get_children())
        for item in self.supplier_pricing.list_items(self.supplier_price_category, include_inactive=True):
            self.supplier_price_table.insert(
                "",
                "end",
                iid=item.id,
                text=item.item_name,
                values=(
                    item.supplier_name,
                    item.spec,
                    item.unit,
                    f"R{item.cost_minor / 100:,.2f}",
                    "Active" if item.is_active else "Inactive",
                ),
            )

    def _open_supplier_import_dialog(self):

        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Select Supplier Price List PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return

        dialog = SupplierPricingImportDialog(
            self.winfo_toplevel(),
            pdf_path=path,
            supplier_pricing=self.supplier_pricing,
            on_imported=self.refresh,
        )
        dialog.grab_set()


# ==========================================================
# Supplier Pricing Import Dialog
# ----------------------------------------------------------
# Two-panel dialog. pdfplumber extracts the tables from the
# PDF and auto-populates the queue on open — one row per
# item × size. User reviews, removes unwanted rows, sets
# category + supplier, then imports. Manual "Add row" form
# handles anything the parser missed.
# ==========================================================

class SupplierPricingImportDialog(ctk.CTkToplevel):

    UNIT_OPTIONS = ("each", "per m", "per roll", "per 6m", "per LM", "per 20L", "per bag", "per set", "per bottle", "per tin")

    # Rows whose first cell matches these prefixes are header/footnote
    # rows, not items — skip them during table parsing.
    _SKIP_PREFIXES = (
        "roll size", "available", "*", "**", "hook and loop prices",
        "colours available", "note:", "nickel plated", "zinc plated",
        "black, beige", "black,beige",
    )

    def __init__(self, master, pdf_path, supplier_pricing, on_imported=None):
        super().__init__(master)

        self.supplier_pricing = supplier_pricing
        self.on_imported = on_imported
        self.pdf_path = pdf_path
        self._queue = []  # list of dicts: name/spec/unit/price

        import os
        self._pdf_filename = os.path.basename(pdf_path)

        self.title("Import from PDF — Supplier Pricing")
        self.geometry("1160x660")
        self.minsize(900, 500)
        self.transient(master)

        # ── header ──────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(header, text="Import from PDF", font=("Segoe UI", 16, "bold")).pack(side="left")
        ctk.CTkLabel(
            header,
            text=f"  —  {self._pdf_filename}",
            font=("Segoe UI", 13), text_color=("gray40", "gray60"),
        ).pack(side="left")

        # ── two-column body ──────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=0, minsize=280)
        body.grid_rowconfigure(0, weight=1)

        # LEFT — queue table (takes most of the space)
        left = ctk.CTkFrame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        queue_header = ctk.CTkFrame(left, fg_color="transparent")
        queue_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        self.queue_count_label = ctk.CTkLabel(
            queue_header, text="Parsing PDF…", font=("Segoe UI", 11, "bold"), anchor="w"
        )
        self.queue_count_label.pack(side="left")
        ctk.CTkButton(
            queue_header, text="Remove Selected", width=130, height=26,
            fg_color="transparent", border_width=1,
            text_color=("gray30", "gray70"),
            command=self._remove_selected,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            queue_header, text="Clear All", width=90, height=26,
            fg_color="transparent", border_width=1,
            text_color=("gray30", "gray70"),
            command=self._clear_queue,
        ).pack(side="right")

        tree_frame = ctk.CTkFrame(left, fg_color="transparent")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 6))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = ("Item", "Spec", "Unit", "Price (R)")
        self.queue_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="extended")
        self.queue_tree.heading("Item", text="Item")
        self.queue_tree.heading("Spec", text="Spec / Size")
        self.queue_tree.heading("Unit", text="Unit")
        self.queue_tree.heading("Price (R)", text="Price (R)")
        self.queue_tree.column("Item", width=220, stretch=True)
        self.queue_tree.column("Spec", width=120, stretch=True)
        self.queue_tree.column("Unit", width=80, stretch=False)
        self.queue_tree.column("Price (R)", width=90, stretch=False, anchor="e")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.queue_tree.yview)
        self.queue_tree.configure(yscrollcommand=vsb.set)
        self.queue_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.queue_tree.bind("<Delete>", lambda _e: self._remove_selected())

        # RIGHT — controls panel
        right = ctk.CTkScrollableFrame(body, width=275)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        r = 0
        ctk.CTkLabel(right, text="APPLIES TO ALL ITEMS", font=("Segoe UI", 10, "bold"), anchor="w").grid(
            row=r, column=0, sticky="w", pady=(6, 10)
        ); r += 1

        ctk.CTkLabel(right, text="Category", anchor="w", font=("Segoe UI", 11)).grid(row=r, column=0, sticky="w"); r += 1
        self.category_var = ctk.StringVar(value=SUPPLIER_PRICE_CATEGORIES[3])  # Hardware default
        ctk.CTkOptionMenu(right, values=list(SUPPLIER_PRICE_CATEGORIES), variable=self.category_var).grid(
            row=r, column=0, sticky="ew", pady=(2, 10)
        ); r += 1

        ctk.CTkLabel(right, text="Supplier", anchor="w", font=("Segoe UI", 11)).grid(row=r, column=0, sticky="w"); r += 1
        self.supplier_entry = ctk.CTkEntry(right, placeholder_text="Supplier name")
        self.supplier_entry.grid(row=r, column=0, sticky="ew", pady=(2, 4)); r += 1

        self.vat_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            right, text="Prices excl. VAT — add 15%", variable=self.vat_var,
            font=("Segoe UI", 11), command=self._reparse,
        ).grid(row=r, column=0, sticky="w", pady=(4, 16)); r += 1

        # divider
        ctk.CTkFrame(right, height=1, fg_color=("gray80", "gray30")).grid(
            row=r, column=0, sticky="ew", pady=(0, 12)
        ); r += 1

        ctk.CTkLabel(right, text="ADD MISSING ITEM", font=("Segoe UI", 10, "bold"), anchor="w").grid(
            row=r, column=0, sticky="w", pady=(0, 8)
        ); r += 1

        ctk.CTkLabel(right, text="Item Name", anchor="w", font=("Segoe UI", 11)).grid(row=r, column=0, sticky="w"); r += 1
        self.name_entry = ctk.CTkEntry(right, placeholder_text="e.g. Snap Hooks")
        self.name_entry.grid(row=r, column=0, sticky="ew", pady=(2, 8)); r += 1

        ctk.CTkLabel(right, text="Spec / Size", anchor="w", font=("Segoe UI", 11)).grid(row=r, column=0, sticky="w"); r += 1
        self.spec_entry = ctk.CTkEntry(right, placeholder_text="e.g. 25mm")
        self.spec_entry.grid(row=r, column=0, sticky="ew", pady=(2, 8)); r += 1

        ctk.CTkLabel(right, text="Unit", anchor="w", font=("Segoe UI", 11)).grid(row=r, column=0, sticky="w"); r += 1
        self.unit_var = ctk.StringVar(value="each")
        ctk.CTkComboBox(right, values=list(self.UNIT_OPTIONS), variable=self.unit_var).grid(
            row=r, column=0, sticky="ew", pady=(2, 8)
        ); r += 1

        ctk.CTkLabel(right, text="Price (R) — as on PDF", anchor="w", font=("Segoe UI", 11)).grid(row=r, column=0, sticky="w"); r += 1
        self.price_entry = ctk.CTkEntry(right, placeholder_text="0.00")
        self.price_entry.grid(row=r, column=0, sticky="ew", pady=(2, 8)); r += 1

        ctk.CTkButton(right, text="+ Add Row", command=self._add_manual_row).grid(
            row=r, column=0, sticky="ew"
        ); r += 1

        # ── footer ──────────────────────────────────────
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(
            footer,
            text="Duplicates (same name + spec + supplier) will prompt: Update / Skip / Add New",
            font=("Segoe UI", 11), text_color=("gray40", "gray60"),
        ).pack(side="left")
        ctk.CTkButton(footer, text="Cancel", width=90, fg_color="transparent",
                      border_width=1, text_color=("gray30", "gray70"),
                      command=self.destroy).pack(side="right", padx=(8, 0))
        self.import_btn = ctk.CTkButton(footer, text="Import 0 Items →", width=160, command=self._do_import)
        self.import_btn.pack(side="right")

        # auto-detect supplier then parse
        self._auto_detect_supplier()
        self.after(50, self._reparse)

    # ── PDF parsing ─────────────────────────────────────

    def _auto_detect_supplier(self):
        candidates = [
        ]
        fname = self._pdf_filename.lower()
        for name, keyword in candidates:
            if keyword in fname:
                self.supplier_entry.delete(0, "end")
                self.supplier_entry.insert(0, name)
                return

    def _reparse(self):
        """Re-extract tables from the PDF and rebuild the queue."""
        try:
            import pdfplumber
        except ImportError:
            messagebox.showerror(
                "pdfplumber missing",
                "Install pdfplumber to enable auto-parsing:\n\n  pip install pdfplumber",
                parent=self,
            )
            return

        add_vat = self.vat_var.get()
        items = []

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    for table in (page.extract_tables() or []):
                        items.extend(self._parse_table(table, add_vat))
        except Exception as error:
            messagebox.showerror("Parse Error", f"Could not read PDF:\n{error}", parent=self)
            return

        self._queue = items
        self._rebuild_queue_display()

    def _parse_table(self, table, add_vat):
        """Turn one pdfplumber table into a list of queue-entry dicts."""
        if not table or len(table) < 2:
            return []

        # Header row: [category/item label, size1, size2, …]
        header = table[0]
        sizes = [str(h).strip() for h in header[1:] if h and str(h).strip()]
        if not sizes:
            return []

        items = []
        for row in table[1:]:
            if not row or not row[0]:
                continue
            name = str(row[0]).strip()
            if not name:
                continue
            name_lower = name.lower()
            if any(name_lower.startswith(p) for p in self._SKIP_PREFIXES):
                continue
            # skip pure-number or very short cells (artefacts)
            if len(name) <= 2:
                continue

            for col_idx, size in enumerate(sizes):
                cell_idx = col_idx + 1
                if cell_idx >= len(row):
                    continue
                cell = row[cell_idx]
                if not cell:
                    continue
                price_str = str(cell).replace("R", "").replace(" ", "").replace("\xa0", "").strip()
                # skip non-price cells (text, POA, custom orders)
                if not price_str or any(c.isalpha() for c in price_str):
                    continue
                try:
                    price = float(price_str)
                except ValueError:
                    continue
                if price <= 0:
                    continue
                if add_vat:
                    price = round(price * 1.15, 2)
                items.append({"name": name, "spec": size, "unit": "each", "price": price})

        return items

    # ── queue display ────────────────────────────────────

    def _rebuild_queue_display(self):
        self.queue_tree.delete(*self.queue_tree.get_children())
        for i, entry in enumerate(self._queue):
            self.queue_tree.insert(
                "", "end", iid=str(i),
                values=(entry["name"], entry["spec"], entry["unit"], f"R {entry['price']:.2f}"),
            )
        self._update_import_btn()

    def _remove_selected(self):
        selected = self.queue_tree.selection()
        if not selected:
            return
        indices = sorted([int(s) for s in selected], reverse=True)
        for i in indices:
            if i < len(self._queue):
                self._queue.pop(i)
        self._rebuild_queue_display()

    def _clear_queue(self):
        self._queue.clear()
        self._rebuild_queue_display()

    def _add_manual_row(self):
        name = self.name_entry.get().strip()
        spec = self.spec_entry.get().strip()
        unit = self.unit_var.get().strip()
        price_str = self.price_entry.get().strip()

        if not name:
            messagebox.showwarning("Add Row", "Item Name is required.", parent=self)
            return
        try:
            price = float(price_str) if price_str else 0.0
        except ValueError:
            messagebox.showerror("Add Row", "Price must be a number.", parent=self)
            return
        if self.vat_var.get():
            price = round(price * 1.15, 2)

        self._queue.append({"name": name, "spec": spec, "unit": unit, "price": price})
        self._rebuild_queue_display()
        self.queue_tree.see(str(len(self._queue) - 1))
        self.name_entry.delete(0, "end")
        self.spec_entry.delete(0, "end")
        self.price_entry.delete(0, "end")
        self.name_entry.focus()

    def _update_import_btn(self):
        n = len(self._queue)
        supplier = self.supplier_entry.get().strip() or "—"
        self.queue_count_label.configure(
            text=f"{n} item{'s' if n != 1 else ''} ready  ·  {supplier}"
        )
        self.import_btn.configure(
            text=f"Import {n} Item{'s' if n != 1 else ''} →",
            state="normal" if n else "disabled",
        )

    def _update_import_btn(self):

        n = len(self._queue)
        self.queue_count_label.configure(
            text=f"{n} item{'s' if n != 1 else ''} queued"
            + (f"  ·  Category: {self.category_var.get()}  ·  Supplier: {self.supplier_entry.get().strip() or '—'}" if n else "")
        )
        self.import_btn.configure(
            text=f"Import {n} Item{'s' if n != 1 else ''} →",
            state="normal" if n else "disabled",
        )

    def _do_import(self):

        if not self._queue:
            return

        category = self.category_var.get()
        supplier = self.supplier_entry.get().strip()

        if not supplier:
            messagebox.showwarning("Import", "Please enter a Supplier name before importing.", parent=self)
            return

        imported = skipped = updated = 0

        for entry in self._queue:
            existing = self._find_existing(entry["name"], entry["spec"], supplier)
            cost_minor = round(entry["price"] * 100)

            if existing:
                answer = self._ask_duplicate(entry["name"], entry["spec"], supplier, existing.cost_minor, cost_minor)
                if answer == "update":
                    existing.cost_minor = cost_minor
                    existing.unit = entry["unit"]
                    self.supplier_pricing.save_item(existing, current_actor())
                    updated += 1
                elif answer == "add":
                    self._create_item(category, supplier, entry, cost_minor)
                    imported += 1
                else:
                    skipped += 1
            else:
                self._create_item(category, supplier, entry, cost_minor)
                imported += 1

        summary = f"Done.\n\n{imported} added, {updated} updated, {skipped} skipped."
        messagebox.showinfo("Import Complete", summary, parent=self)

        if self.on_imported:
            self.on_imported()

        self.destroy()

    def _find_existing(self, name, spec, supplier):
        """Return a matching item if one exists (case-insensitive)."""
        all_items = []
        for cat in SUPPLIER_PRICE_CATEGORIES:
            all_items.extend(self.supplier_pricing.list_items(cat, include_inactive=True))
        full_name = f"{name} — {spec}" if spec else name
        full_l = full_name.lower()
        supplier_l = supplier.lower()
        for item in all_items:
            if (item.item_name.lower() == full_l
                    and item.supplier_name.lower() == supplier_l):
                return item
            if (item.item_name.lower() == name.lower()
                    and item.supplier_name.lower() == supplier_l):
                return item
        return None

    def _ask_duplicate(self, name, spec, supplier, old_minor, new_minor):
        """Return 'update', 'skip', or 'add'."""
        old = f"R{old_minor / 100:.2f}"
        new = f"R{new_minor / 100:.2f}"
        spec_part = f" ({spec})" if spec else ""
        msg = (
            f'"{name}"{spec_part} from {supplier} already exists.\n\n'
            f'Existing price: {old}\n'
            f'New price:      {new}\n\n'
            "What would you like to do?"
        )
        dialog = _DuplicateChoiceDialog(self, msg)
        self.wait_window(dialog)
        return dialog.result

    def _create_item(self, category, supplier, entry, cost_minor):

        item = self.supplier_pricing.new_item(category)
        name = entry["name"]
        spec = entry["spec"]
        if spec:
            name = f"{name} — {spec}"
        item.item_name = name
        item.supplier_name = supplier
        item.spec = spec
        item.unit = entry["unit"]
        item.cost_minor = cost_minor
        try:
            self.supplier_pricing.save_item(item, current_actor())
        except Exception:
            pass


class _SupplierPricingPickerDialog(ctk.CTkToplevel):
    """Pick supplier pricing items to create as Line Item Types."""

    DEFAULT_GP = 45.0

    def __init__(self, master, *, supplier_pricing, picklists, on_done=None):
        super().__init__(master)
        self.supplier_pricing = supplier_pricing
        self.picklists = picklists
        self.on_done = on_done

        self.title("Add Line Item Types from Supplier Pricing")
        self.geometry("780x560")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(12, 4))

        ctk.CTkLabel(top, text="Category:").pack(side="left", padx=(0, 6))
        self._cat_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            top, values=["All"] + list(SUPPLIER_PRICE_CATEGORIES),
            variable=self._cat_var, command=lambda _: self._refresh_list(),
        ).pack(side="left")

        ctk.CTkLabel(top, text="Search:").pack(side="left", padx=(16, 6))
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh_list())
        ctk.CTkEntry(top, textvariable=self._search_var, width=200,
                     placeholder_text="Filter items...").pack(side="left")

        ctk.CTkLabel(top, text="GP%:").pack(side="left", padx=(16, 6))
        self._gp_var = ctk.StringVar(value=str(self.DEFAULT_GP))
        ctk.CTkEntry(top, textvariable=self._gp_var, width=60).pack(side="left")

        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=12, pady=8)

        cols = ("Category", "Supplier", "Cost (R)", "Sell (R)")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="tree headings",
                                  selectmode="extended", height=18)
        self._tree.heading("#0", text="Item Name", anchor="w")
        self._tree.column("#0", width=260, minwidth=120)
        for c in cols:
            self._tree.heading(c, text=c, anchor="w")
            self._tree.column(c, width=100, minwidth=60)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.pack(fill="x", padx=12, pady=(0, 12))

        self._status_label = ctk.CTkLabel(bot, text="", anchor="w")
        self._status_label.pack(side="left")

        ctk.CTkButton(bot, text="Add Selected as Line Item Types", width=240,
                      command=self._add_selected).pack(side="right")

        self._all_items = []
        for cat in SUPPLIER_PRICE_CATEGORIES:
            self._all_items.extend(self.supplier_pricing.list_items(cat))
        self._refresh_list()

    def _get_gp(self):
        try:
            return float(self._gp_var.get()) / 100
        except ValueError:
            return self.DEFAULT_GP / 100

    def _sell_price(self, cost_minor):
        gp = self._get_gp()
        if gp >= 1:
            return cost_minor
        return round(cost_minor / (1 - gp))

    def _refresh_list(self):
        self._tree.delete(*self._tree.get_children())
        cat_filter = self._cat_var.get()
        search = self._search_var.get().lower()
        count = 0
        for item in self._all_items:
            if cat_filter != "All" and item.category != cat_filter:
                continue
            if search and search not in item.item_name.lower():
                continue
            sell = self._sell_price(item.cost_minor)
            self._tree.insert(
                "", "end", iid=str(item.id),
                text=item.item_name,
                values=(
                    item.category,
                    item.supplier_name,
                    f"R{item.cost_minor / 100:,.2f}",
                    f"R{sell / 100:,.2f}",
                ),
            )
            count += 1
        self._status_label.configure(text=f"{count} items")

    def _add_selected(self):
        selection = self._tree.selection()
        if not selection:
            messagebox.showwarning("Picker", "Select at least one item.", parent=self)
            return

        existing_names = {
            opt.value.lower()
            for opt in self.picklists.list_options(LINE_ITEM_TYPE, include_inactive=True)
        }

        added = skipped = 0
        for iid in selection:
            item_id = int(iid)
            item = next((i for i in self._all_items if i.id == item_id), None)
            if item is None:
                continue

            if item.item_name.lower() in existing_names:
                skipped += 1
                continue

            sell = self._sell_price(item.cost_minor)
            option = self.picklists.new_option(LINE_ITEM_TYPE)
            option.value = item.item_name
            option.rate_standard_minor = sell
            option.rate_high_minor = None
            try:
                self.picklists.save_option(option, current_actor())
                existing_names.add(item.item_name.lower())
                added += 1
            except Exception:
                skipped += 1

        messagebox.showinfo(
            "Done", f"{added} line item types added, {skipped} skipped (already exist).",
            parent=self,
        )
        if self.on_done:
            self.on_done()


class _DuplicateChoiceDialog(ctk.CTkToplevel):
    """Simple 3-button dialog: Update / Skip / Add New."""

    def __init__(self, master, message):
        super().__init__(master)
        self.result = "skip"
        self.title("Duplicate Item")
        self.geometry("420x220")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text=message, wraplength=380, justify="left",
                     font=("Segoe UI", 12)).pack(padx=20, pady=(20, 16))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 16))

        ctk.CTkButton(btn_row, text="Update Price", width=120,
                      command=lambda: self._close("update")).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Skip", width=90, fg_color="transparent",
                      border_width=1, text_color=("gray30", "gray70"),
                      command=lambda: self._close("skip")).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Add New", width=100, fg_color="transparent",
                      border_width=1, text_color=("gray30", "gray70"),
                      command=lambda: self._close("add")).pack(side="left", padx=6)

    def _close(self, result):
        self.result = result
        self.destroy()


__all__ = ["SettingsWindow"]
