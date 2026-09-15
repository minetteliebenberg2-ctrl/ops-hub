# ==========================================================
# FC Hub - CRM Window (Phase 3 Redesign - Light Theme)
# ----------------------------------------------------------
# Professional customer management interface with:
# - Clean customer list
# - Inline detail view (no floating windows)
# - Search and filter
# - Light theme throughout
#
# Author: Claude (Redesign Phase 3)
# ==========================================================

import getpass
import os

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.crm_service import CRMService
from core.payment_service import PaymentService
from core.pdf_customer_extractor import PdfCustomerExtractor
from core.quote_document import TAX_INVOICE
from core.quote_pdf import format_money
from core.quote_repository import QuoteRepository
from gui.components.clickable_card import ClickableCard
from gui.design_tokens import COLORS, FONTS, SPACING
from gui.form_dialogs import EntityFormDialog, TextPromptDialog

_ADDRESS_TYPE_PRIORITY = ("Physical", "Site", "Billing", "Postal")


class CRMWindow(ctk.CTkFrame):
    """Professional customer management window."""

    def __init__(self, master):
        super().__init__(
            master,
            fg_color=COLORS["surface_primary"],
        )

        self.crm_service = CRMService()
        self.payment_service = PaymentService()
        self.quote_repo = QuoteRepository()

        self.current_view = "list"  # "list" or "detail"
        self.selected_customer = None

        # Main container
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True)

        # Build list view
        self._build_list_view()

    # ==================================================
    # List View
    # ==================================================

    def _build_list_view(self):
        """Build customer list interface."""
        # Header
        header = ctk.CTkFrame(
            self.main_frame,
            fg_color="transparent",
        )
        header.pack(fill="x", padx=SPACING["xxl"], pady=(SPACING["xxl"], SPACING["lg"]))

        ctk.CTkLabel(
            header,
            text="Customers",
            font=FONTS["title_lg"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        # Toolbar
        toolbar = ctk.CTkFrame(
            self.main_frame,
            fg_color="transparent",
        )
        toolbar.pack(fill="x", padx=SPACING["xxl"], pady=(0, SPACING["lg"]))

        # Search box
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_list())
        search = ctk.CTkEntry(
            toolbar,
            placeholder_text="Search customers...",
            textvariable=self.search_var,
            font=FONTS["body_md"],
            fg_color=COLORS["surface_secondary"],
            border_color=COLORS["border_default"],
            border_width=1,
            corner_radius=6,
            height=32,
        )
        search.pack(side="left", fill="x", expand=True, padx=(0, SPACING["md"]))

        # New customer button
        ctk.CTkButton(
            toolbar,
            text="+ New Customer",
            font=FONTS["label"],
            fg_color=COLORS["accent_primary"],
            text_color=COLORS["text_inverse"],
            height=32,
            corner_radius=6,
            command=self._new_customer,
        ).pack(side="left")

        ctk.CTkButton(
            toolbar,
            text="Import from PDF",
            font=FONTS["label"],
            fg_color=COLORS["surface_secondary"],
            text_color=COLORS["text_primary"],
            border_color=COLORS["border_default"],
            border_width=1,
            hover_color=COLORS.get("surface_tertiary", COLORS["surface_secondary"]),
            height=32,
            corner_radius=6,
            command=self._import_from_pdf,
        ).pack(side="left", padx=(SPACING["sm"], 0))

        # Customer list (scrollable frame with customer items)
        scroll = ctk.CTkScrollableFrame(
            self.main_frame,
            fg_color=COLORS["surface_primary"],
        )
        scroll.pack(fill="both", expand=True, padx=SPACING["xxl"], pady=(0, SPACING["xxl"]))

        self.customer_list_frame = scroll

        # Load and display customers
        self._refresh_list()

    # ==================================================

    def _refresh_list(self):
        """Refresh customer list."""
        # Clear existing items
        for widget in self.customer_list_frame.winfo_children():
            widget.destroy()

        # Get search term
        search_term = self.search_var.get().lower()

        # Get customers
        try:
            customers = self.crm_service.list_customers()
            if not customers:
                ctk.CTkLabel(
                    self.customer_list_frame,
                    text="No customers yet. Click '+ New Customer' to get started.",
                    font=FONTS["body_md"],
                    text_color=COLORS["text_tertiary"],
                ).pack(pady=SPACING["xxl"])
                return

            # Filter by search term
            filtered = [
                c for c in customers
                if search_term in c.name.lower()
                or search_term in (c.email or "").lower()
                or search_term in (c.phone or "").lower()
            ]

            if not filtered:
                ctk.CTkLabel(
                    self.customer_list_frame,
                    text="No matches found.",
                    font=FONTS["body_md"],
                    text_color=COLORS["text_tertiary"],
                ).pack(pady=SPACING["xxl"])
                return

            # Display customer items
            for customer in filtered:
                self._add_customer_item(customer)

        except Exception as e:
            ctk.CTkLabel(
                self.customer_list_frame,
                text=f"Error loading customers: {e}",
                font=FONTS["body_sm"],
                text_color=COLORS["danger"],
            ).pack(pady=SPACING["lg"])

    # ==================================================

    def _add_customer_item(self, customer):
        """Add a customer item to the list."""
        item = ClickableCard(
            self.customer_list_frame,
            on_click=lambda c=customer: self._show_customer_detail(c),
            hover_color=COLORS.get("surface_tertiary", COLORS["surface_secondary"]),
            fg_color=COLORS["surface_secondary"],
            border_width=1,
            border_color=COLORS["border_default"],
            corner_radius=8,
            height=112,
        )
        item.pack(fill="x", pady=SPACING["sm"])
        item.pack_propagate(False)

        content = ctk.CTkFrame(item, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=SPACING["lg"], pady=SPACING["sm"])

        # Header: Company name + optional Active tick
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x", pady=(0, 2))

        name_text = customer.name
        if customer.customer_number:
            name_text = f"{customer.customer_number}  {customer.name}"
        ctk.CTkLabel(
            header,
            text=name_text,
            font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", side="left")

        if (customer.status or "Active") == "Active":
            ctk.CTkLabel(
                header,
                text="✓",
                font=FONTS["label_sm"],
                text_color=COLORS["success"],
            ).pack(anchor="e", side="right")

        primary_contact = self._primary_contact(customer)
        contact_name = primary_contact.name if primary_contact and primary_contact.name else ""
        contact_number = ""
        if primary_contact:
            contact_number = primary_contact.mobile or primary_contact.phone or ""
        if not contact_number:
            contact_number = customer.phone or ""
        email = (primary_contact.email if primary_contact and primary_contact.email else "") or (customer.email or "")
        address = self._primary_address_line(customer)

        # Two-column body: contact info left, address right
        body = ctk.CTkFrame(content, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1, uniform="cols")
        body.grid_columnconfigure(1, weight=1, uniform="cols")

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, SPACING["md"]))
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        left_rows = [
            ("👤", contact_name, "No contact person"),
            ("📞", contact_number, "No number on file"),
            ("📧", email, "No email on file"),
        ]
        for icon, value, empty in left_rows:
            has = bool(value)
            ctk.CTkLabel(
                left,
                text=f"{icon}  {value if has else empty}",
                font=FONTS["body_sm"],
                text_color=COLORS["text_secondary"] if has else COLORS["text_tertiary"],
                anchor="w",
                justify="left",
            ).pack(anchor="w", fill="x", pady=0)

        has_addr = bool(address)
        ctk.CTkLabel(
            right,
            text=f"📍  {address if has_addr else 'No address on file'}",
            font=FONTS["body_sm"],
            text_color=COLORS["text_secondary"] if has_addr else COLORS["text_tertiary"],
            anchor="nw",
            justify="left",
            wraplength=380,
        ).pack(anchor="nw", fill="both", expand=True, pady=0)

        item.activate()

    def _primary_contact(self, customer):
        try:
            contacts = self.crm_service.list_contacts(customer.id)
        except Exception:
            return None
        if not contacts:
            return None
        return next((c for c in contacts if getattr(c, "is_primary", False)), contacts[0])

    def _primary_address_line(self, customer):
        """Compact address string for the list card.

        Uses the documented type priority Physical > Site > Billing > Postal
        (session 2026-08-13) so a PO Box / Postal address never wins over a
        real physical/site address. is_primary is only used as a tiebreaker
        within the same type.
        """
        try:
            addresses = self.crm_service.list_addresses(customer.id)
        except Exception:
            return ""
        if not addresses:
            return ""

        def rank(addr):
            atype = (addr.address_type or "").strip()
            try:
                type_rank = _ADDRESS_TYPE_PRIORITY.index(atype)
            except ValueError:
                type_rank = len(_ADDRESS_TYPE_PRIORITY)
            return (type_rank, 0 if getattr(addr, "is_primary", False) else 1)

        chosen = min(addresses, key=rank)
        parts = [p for p in [chosen.line1, chosen.city, chosen.province] if p]
        return ", ".join(parts)

    # ==================================================

    def _show_customer_detail(self, customer):
        """Show customer detail view."""
        self.selected_customer = customer
        self.current_view = "detail"

        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        self._build_detail_view(customer)

    # ==================================================
    # Detail View
    # ==================================================

    def _build_detail_view(self, customer):
        """Build HubSpot-style customer detail view."""
        scroll = ctk.CTkScrollableFrame(
            self.main_frame,
            fg_color=COLORS["surface_primary"],
        )
        scroll.pack(fill="both", expand=True)

        # Back button
        ctk.CTkButton(
            scroll,
            text="← Back to Customers",
            font=FONTS["label"],
            fg_color="transparent",
            text_color=COLORS["accent_primary"],
            hover_color=COLORS["surface_tertiary"],
            border_width=0,
            anchor="w",
            command=self._show_list_view,
        ).pack(anchor="w", padx=SPACING["xxl"], pady=(SPACING["lg"], SPACING["sm"]))

        # --- Header card ---
        header_card = ctk.CTkFrame(
            scroll, fg_color=COLORS["surface_secondary"],
            border_width=1, border_color=COLORS["border_default"], corner_radius=8,
        )
        header_card.pack(fill="x", padx=SPACING["xxl"], pady=(0, SPACING["md"]))
        header_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        header_inner.pack(fill="x", padx=SPACING["lg"], pady=SPACING["lg"])

        # Avatar circle
        initials = "".join(w[0] for w in customer.name.split()[:2]).upper()
        avatar = ctk.CTkFrame(
            header_inner, fg_color=COLORS["accent_primary"],
            corner_radius=999, width=48, height=48,
        )
        avatar.pack(side="left", padx=(0, SPACING["md"]))
        avatar.pack_propagate(False)
        ctk.CTkLabel(
            avatar, text=initials, font=("Lato", 16, "bold"),
            text_color=COLORS["text_inverse"],
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Name + contact line
        info_col = ctk.CTkFrame(header_inner, fg_color="transparent")
        info_col.pack(side="left", fill="x", expand=True)

        name_row = ctk.CTkFrame(info_col, fg_color="transparent")
        name_row.pack(fill="x")
        ctk.CTkLabel(
            name_row, text=customer.name, font=FONTS["heading_lg"],
            text_color=COLORS["text_primary"],
        ).pack(side="left")
        if customer.customer_number:
            ctk.CTkLabel(
                name_row, text=f"#{customer.customer_number}",
                font=FONTS["body_md"], text_color=COLORS["text_tertiary"],
            ).pack(side="left", padx=(SPACING["sm"], 0))
        status = customer.status or "Active"
        pill_color = COLORS["success"] if status == "Active" else COLORS["text_tertiary"]
        ctk.CTkLabel(
            name_row, text=f"✓ {status}" if status == "Active" else status,
            font=FONTS["label_sm"], text_color=pill_color,
        ).pack(side="left", padx=(SPACING["sm"], 0))

        primary_contact = self._primary_contact(customer)
        contact_parts = []
        if primary_contact and primary_contact.name:
            contact_parts.append(f"👤 {primary_contact.name}")
        if customer.email:
            contact_parts.append(f"📧 {customer.email}")
        if customer.phone:
            contact_parts.append(f"📞 {customer.phone}")
        if customer.customer_type:
            contact_parts.append(f"🏢 {customer.customer_type}")
        if customer.payment_terms:
            contact_parts.append(f"💳 {customer.payment_terms}")
        ctk.CTkLabel(
            info_col, text=" · ".join(contact_parts) if contact_parts else "—",
            font=FONTS["body_sm"], text_color=COLORS["text_secondary"],
        ).pack(anchor="w", pady=(2, 0))

        # Action buttons
        btn_col = ctk.CTkFrame(header_inner, fg_color="transparent")
        btn_col.pack(side="right")
        ctk.CTkButton(
            btn_col, text="Edit", font=FONTS["label"], height=30,
            fg_color=COLORS["accent_primary"], text_color=COLORS["text_inverse"],
            command=lambda: self._edit_customer(customer),
        ).pack(side="left", padx=(0, SPACING["sm"]))
        ctk.CTkButton(
            btn_col, text="+ New Quote", font=FONTS["label"], height=30,
            fg_color=COLORS["surface_tertiary"], text_color=COLORS["text_primary"],
            border_width=1, border_color=COLORS["border_default"],
            command=lambda: self._new_quote_for_customer(customer),
        ).pack(side="left", padx=(0, SPACING["sm"]))
        ctk.CTkButton(
            btn_col, text="+ Address", font=FONTS["label"], height=30,
            fg_color=COLORS["surface_tertiary"], text_color=COLORS["text_primary"],
            border_width=1, border_color=COLORS["border_default"],
            command=lambda: self._add_address(customer),
        ).pack(side="left")

        # --- KPI cards row ---
        kpi_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        kpi_frame.pack(fill="x", padx=SPACING["xxl"], pady=(0, SPACING["md"]))
        kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")

        try:
            sites = self.crm_service.list_sites(customer.id)
        except Exception:
            sites = []
        try:
            quotes = self.quote_repo.list_for_customer(customer.id)
        except Exception:
            quotes = []
        from core.job_card_service import JobCardService
        try:
            job_cards = JobCardService().list_job_cards_for_customer(customer.id)
        except Exception:
            job_cards = []
        try:
            invoices = self.payment_service.list_invoices_with_status(customer.id)
            total_outstanding = sum(max(0, i["balance_minor"]) for i in invoices)
            open_inv_count = sum(1 for i in invoices if i["balance_minor"] > 0)
        except Exception:
            invoices = []
            total_outstanding = 0
            open_inv_count = 0

        active_jobs = [j for j in job_cards if j.status == "Open"]
        accepted = [q for q in quotes if q.status == "Accepted"]

        kpi_data = [
            ("Sites", str(len(sites)), f"{len(sites)} block(s)" if sites else "None"),
            ("Quotes", str(len(quotes)), f"{len(accepted)} accepted" if accepted else "None issued"),
            ("Active Jobs", str(len(active_jobs)), f"{len(active_jobs)} open" if active_jobs else "None"),
            ("Outstanding", format_money(total_outstanding), f"{open_inv_count} invoice(s)" if open_inv_count else "Paid up"),
        ]
        for col, (label, value, sub) in enumerate(kpi_data):
            card = ctk.CTkFrame(
                kpi_frame, fg_color=COLORS["surface_secondary"],
                border_width=1, border_color=COLORS["border_default"], corner_radius=6,
            )
            card.grid(row=0, column=col, sticky="nsew",
                      padx=(0, SPACING["sm"] if col < 3 else 0), pady=0)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", padx=SPACING["md"], pady=SPACING["md"])
            ctk.CTkLabel(
                inner, text=label, font=FONTS["label_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(anchor="w")
            is_money = label == "Outstanding"
            ctk.CTkLabel(
                inner, text=value, font=FONTS["heading_md"],
                text_color=COLORS["accent_primary"] if is_money else COLORS["text_primary"],
            ).pack(anchor="w", pady=(2, 0))
            ctk.CTkLabel(
                inner, text=sub, font=FONTS["label_sm"],
                text_color=COLORS["text_secondary"],
            ).pack(anchor="w")

        # --- Two-column body: sites panel + tabbed content ---
        body = ctk.CTkFrame(scroll, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=SPACING["xxl"], pady=(0, SPACING["xxl"]))

        # Sites panel (left)
        sites_panel = ctk.CTkFrame(
            body, fg_color=COLORS["surface_secondary"],
            border_width=1, border_color=COLORS["border_default"], corner_radius=6,
            width=220,
        )
        sites_panel.pack(side="left", fill="y", padx=(0, SPACING["md"]))
        sites_panel.pack_propagate(False)

        sp_header = ctk.CTkFrame(sites_panel, fg_color="transparent")
        sp_header.pack(fill="x", padx=SPACING["md"], pady=(SPACING["md"], SPACING["sm"]))
        ctk.CTkLabel(
            sp_header, text="Sites", font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        try:
            addresses = self.crm_service.list_addresses(customer.id)
        except Exception:
            addresses = []

        if addresses:
            ctk.CTkButton(
                sp_header, text="+ Add", font=FONTS["label_sm"], height=22,
                fg_color="transparent", text_color=COLORS["accent_primary"],
                hover_color=COLORS["surface_tertiary"], border_width=0,
                command=lambda: self._add_blocks_bulk(customer),
            ).pack(side="right")

        sp_scroll = ctk.CTkScrollableFrame(
            sites_panel, fg_color="transparent",
        )
        sp_scroll.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        addr_by_id = {a.id: a for a in addresses}

        if not sites:
            msg = "Add an address first." if not addresses else "No sites yet."
            ctk.CTkLabel(
                sp_scroll, text=msg, font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"], wraplength=190,
            ).pack(padx=SPACING["sm"], pady=SPACING["sm"])
        else:
            for i, site in enumerate(sites):
                sf = ctk.CTkFrame(sp_scroll, fg_color="transparent")
                sf.pack(fill="x", padx=SPACING["xs"], pady=(0, SPACING["xs"]))
                ctk.CTkLabel(
                    sf, text=site.name or "(Unnamed)",
                    font=FONTS["heading_sm"] if i == 0 else FONTS["body_md"],
                    text_color=COLORS["text_primary"], anchor="w",
                ).pack(anchor="w", fill="x")
                stype = site.site_type or "Site"
                addr = addr_by_id.get(getattr(site, "address_id", None))
                if addr:
                    loc = ", ".join(p for p in [addr.line1, addr.city] if p)
                    if loc:
                        stype += f" · {loc}"
                ctk.CTkLabel(
                    sf, text=stype, font=FONTS["label_sm"],
                    text_color=COLORS["text_tertiary"], anchor="w",
                ).pack(anchor="w", fill="x")
                btn_row = ctk.CTkFrame(sf, fg_color="transparent")
                btn_row.pack(anchor="w", fill="x", pady=(2, SPACING["xs"]))
                ctk.CTkButton(
                    btn_row, text="Site Plan", font=FONTS["label_sm"], height=22,
                    fg_color=COLORS["surface_tertiary"], text_color=COLORS["text_primary"],
                    border_width=1, border_color=COLORS["border_default"],
                    command=lambda s=site: self._open_site_plan(s),
                ).pack(side="left", padx=(0, 4))
                ctk.CTkButton(
                    btn_row, text="Job Cards", font=FONTS["label_sm"], height=22,
                    fg_color=COLORS["surface_tertiary"], text_color=COLORS["text_primary"],
                    border_width=1, border_color=COLORS["border_default"],
                    command=lambda s=site: self._open_job_cards(s),
                ).pack(side="left")
                # Divider between sites
                if i < len(sites) - 1:
                    ctk.CTkFrame(
                        sp_scroll, fg_color=COLORS["border_light"], height=1,
                    ).pack(fill="x", padx=SPACING["xs"], pady=(0, SPACING["xs"]))

        # Tabbed content panel (right)
        tab_panel = ctk.CTkFrame(
            body, fg_color=COLORS["surface_secondary"],
            border_width=1, border_color=COLORS["border_default"], corner_radius=6,
        )
        tab_panel.pack(side="left", fill="both", expand=True)

        # Tab bar
        tab_bar = ctk.CTkFrame(tab_panel, fg_color="transparent")
        tab_bar.pack(fill="x", padx=0, pady=0)
        ctk.CTkFrame(
            tab_panel, fg_color=COLORS["border_default"], height=1,
        ).pack(fill="x")

        # Tab content container
        tab_content = ctk.CTkFrame(tab_panel, fg_color="transparent")
        tab_content.pack(fill="both", expand=True)

        self._detail_tab_frames = {}
        self._detail_tab_buttons = {}

        try:
            contacts = self.crm_service.list_contacts(customer.id) or []
        except Exception:
            contacts = []

        tab_defs = [
            ("Activity", lambda p: self._build_activity_tab(p, customer)),
            ("Contacts", lambda p: self._build_contacts_tab(p, customer, contacts)),
            ("Quotes", lambda p: self._build_quotes_tab(p, customer, quotes)),
            ("Job Cards", lambda p: self._build_job_cards_tab(p, customer, job_cards)),
            ("Invoices", lambda p: self._build_invoices_tab(p, customer, invoices)),
            ("Payments", lambda p: self._build_payments_tab(p, customer)),
            ("Addresses", lambda p: self._build_addresses_tab(p, customer, addresses)),
            ("Notes", lambda p: self._build_notes_tab(p, customer)),
        ]

        for tab_name, builder in tab_defs:
            frame = ctk.CTkFrame(tab_content, fg_color="transparent")
            builder(frame)
            self._detail_tab_frames[tab_name] = frame

            btn = ctk.CTkButton(
                tab_bar, text=tab_name, font=FONTS["body_sm"], height=36,
                fg_color="transparent", text_color=COLORS["text_tertiary"],
                hover_color=COLORS["surface_tertiary"], border_width=0,
                corner_radius=0,
                command=lambda n=tab_name: self._switch_detail_tab(n),
            )
            btn.pack(side="left", padx=(SPACING["sm"], 0))
            self._detail_tab_buttons[tab_name] = btn

        self._switch_detail_tab("Activity")

    # ==================================================
    # Tab switching
    # ==================================================

    def _switch_detail_tab(self, name):
        for n, frame in self._detail_tab_frames.items():
            if n == name:
                frame.pack(fill="both", expand=True, padx=SPACING["md"], pady=SPACING["md"])
            else:
                frame.pack_forget()
        for n, btn in self._detail_tab_buttons.items():
            if n == name:
                btn.configure(
                    text_color=COLORS["accent_primary"],
                    font=("Lato", 12, "bold"),
                )
            else:
                btn.configure(
                    text_color=COLORS["text_tertiary"],
                    font=FONTS["body_sm"],
                )

    # ==================================================
    # Tab builders
    # ==================================================

    def _build_activity_tab(self, parent, customer):
        try:
            activities = self.crm_service.list_activities(customer.id) or []
        except Exception:
            activities = []
        activities = sorted(
            activities,
            key=lambda a: a.created_at or a.activity_date or "",
            reverse=True,
        )[:20]
        if not activities:
            ctk.CTkLabel(
                parent, text="No recent activity.", font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(anchor="w", pady=SPACING["md"])
            return
        for act in activities:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=(0, SPACING["sm"]))
            dot = ctk.CTkFrame(row, fg_color=COLORS["text_tertiary"], width=8, height=8, corner_radius=4)
            dot.pack(side="left", padx=(0, SPACING["sm"]), pady=(6, 0))
            dot.pack_propagate(False)
            body = ctk.CTkFrame(row, fg_color="transparent")
            body.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(
                body, text=act.subject or act.activity_type or "(No description)",
                font=FONTS["heading_sm"], text_color=COLORS["text_primary"], anchor="w",
            ).pack(anchor="w", fill="x")
            when = (act.activity_date or act.created_at or "—")[:19].replace("T", " ")
            actor = act.created_by or "—"
            ctk.CTkLabel(
                body, text=f"{when} · {actor}", font=FONTS["label_sm"],
                text_color=COLORS["text_tertiary"], anchor="w",
            ).pack(anchor="w", fill="x")
            if act.notes:
                ctk.CTkLabel(
                    body, text=act.notes, font=FONTS["body_sm"],
                    text_color=COLORS["text_secondary"], anchor="w",
                    wraplength=600,
                ).pack(anchor="w", fill="x", pady=(2, 0))
            ctk.CTkFrame(parent, fg_color=COLORS["border_light"], height=1).pack(fill="x")

    def _build_contacts_tab(self, parent, customer, contacts):
        ctk.CTkButton(
            parent, text="+ Add Contact", font=FONTS["label_sm"], height=28,
            fg_color=COLORS["accent_primary"], text_color=COLORS["text_inverse"],
            command=lambda: self._add_contact(customer),
        ).pack(anchor="w", pady=(0, SPACING["md"]))
        if not contacts:
            ctk.CTkLabel(
                parent, text="No contact persons yet.", font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(anchor="w")
            return
        for contact in contacts:
            card = ctk.CTkFrame(
                parent, fg_color=COLORS["surface_primary"],
                border_width=1, border_color=COLORS["border_light"], corner_radius=6,
            )
            card.pack(fill="x", pady=(0, SPACING["sm"]))
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", padx=SPACING["md"], pady=SPACING["md"])
            top_row = ctk.CTkFrame(inner, fg_color="transparent")
            top_row.pack(fill="x")
            name_parts = [contact.name or "(Unnamed)"]
            if contact.job_title:
                name_parts.append(contact.job_title)
            if getattr(contact, "is_primary", False):
                name_parts.append("(Primary)")
            ctk.CTkLabel(
                top_row, text=" — ".join(name_parts),
                font=FONTS["heading_sm"], text_color=COLORS["text_primary"], anchor="w",
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                top_row, text="Edit", font=FONTS["body_sm"], height=24, width=50,
                fg_color=COLORS["surface_tertiary"], text_color=COLORS["text_primary"],
                border_width=1, border_color=COLORS["border_default"],
                command=lambda c=contact, cu=customer: self._edit_contact(cu, c),
            ).pack(side="right", padx=(SPACING["sm"], 0))
            details = []
            if contact.email:
                details.append(f"Email: {contact.email}")
            if contact.phone:
                details.append(f"Phone: {contact.phone}")
            if getattr(contact, "mobile", None):
                details.append(f"Mobile: {contact.mobile}")
            if details:
                ctk.CTkLabel(
                    inner, text=" · ".join(details),
                    font=FONTS["body_sm"], text_color=COLORS["text_secondary"], anchor="w",
                ).pack(anchor="w", fill="x", pady=(SPACING["xs"], 0))

    def _add_contact(self, customer):
        from gui.form_dialogs import EntityFormDialog
        fields = [
            {"key": "name", "label": "Contact Name", "kind": "text", "initial": ""},
            {"key": "job_title", "label": "Job Title", "kind": "text", "initial": ""},
            {"key": "email", "label": "Email", "kind": "text", "initial": ""},
            {"key": "phone", "label": "Phone", "kind": "text", "initial": ""},
            {"key": "mobile", "label": "Mobile", "kind": "text", "initial": ""},
        ]
        result = EntityFormDialog.ask(self.winfo_toplevel(), f"New Contact — {customer.name}", fields)
        if result:
            from core.contact import Contact
            contact = Contact(
                customer_id=customer.id,
                name=result["name"].strip(),
                job_title=result.get("job_title", "").strip(),
                email=result.get("email", "").strip(),
                phone=result.get("phone", "").strip(),
                mobile=result.get("mobile", "").strip(),
                is_primary=not bool(self.crm_service.list_contacts(customer.id)),
            )
            self.crm_service.save_contact(contact)
            self._show_customer_detail(customer)

    def _edit_contact(self, customer, contact):
        from gui.form_dialogs import EntityFormDialog
        fields = [
            {"key": "name", "label": "Contact Name", "kind": "text", "initial": contact.name or ""},
            {"key": "job_title", "label": "Job Title", "kind": "text", "initial": contact.job_title or ""},
            {"key": "email", "label": "Email", "kind": "text", "initial": contact.email or ""},
            {"key": "phone", "label": "Phone", "kind": "text", "initial": contact.phone or ""},
            {"key": "mobile", "label": "Mobile", "kind": "text", "initial": getattr(contact, "mobile", "") or ""},
        ]
        result = EntityFormDialog.ask(self.winfo_toplevel(), f"Edit Contact — {contact.name}", fields)
        if result:
            contact.name = result["name"].strip()
            contact.job_title = result.get("job_title", "").strip()
            contact.email = result.get("email", "").strip()
            contact.phone = result.get("phone", "").strip()
            contact.mobile = result.get("mobile", "").strip()
            self.crm_service.save_contact(contact)
            self._show_customer_detail(customer)

    def _build_quotes_tab(self, parent, customer, quotes):
        if not quotes:
            ctk.CTkLabel(
                parent, text="No quotes yet.", font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(anchor="w", pady=SPACING["md"])
            return
        for quote in quotes:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=(0, SPACING["xs"]))
            ctk.CTkLabel(
                row, text=quote.quote_number or "(Draft)",
                font=FONTS["heading_sm"], text_color=COLORS["text_primary"],
            ).pack(side="left")
            date_str = quote.issue_date or (quote.created_at or "")[:10] or "—"
            ctk.CTkLabel(
                row, text=date_str, font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(side="left", padx=(SPACING["md"], 0))
            st = quote.status or "—"
            st_color = COLORS["accent_primary"] if st == "Accepted" else COLORS["text_secondary"]
            ctk.CTkLabel(
                row, text=st, font=FONTS["label_sm"], text_color=st_color,
            ).pack(side="left", padx=(SPACING["sm"], 0))
            ctk.CTkButton(
                row, text="Open →", font=FONTS["label_sm"], height=22,
                fg_color="transparent", text_color=COLORS["accent_primary"],
                hover_color=COLORS["surface_tertiary"], border_width=0,
                command=lambda q=quote: self._open_quote(q),
            ).pack(side="right")
            ctk.CTkLabel(
                row, text=format_money(quote.total_minor or 0, quote.currency or "ZAR"),
                font=FONTS["body_md"], text_color=COLORS["text_primary"],
            ).pack(side="right", padx=(0, SPACING["sm"]))
            ctk.CTkFrame(parent, fg_color=COLORS["border_light"], height=1).pack(fill="x")

    def _build_job_cards_tab(self, parent, customer, job_cards):
        if not job_cards:
            ctk.CTkLabel(
                parent, text="No job cards yet. Job cards are created when a quote is accepted.",
                font=FONTS["body_sm"], text_color=COLORS["text_tertiary"],
            ).pack(anchor="w", pady=SPACING["md"])
            return
        for jc in job_cards:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=(0, SPACING["xs"]))
            num = jc.job_card_number or "(No number)"
            st_color = COLORS["success"] if jc.status == "Open" else COLORS["text_tertiary"]
            ctk.CTkLabel(
                row, text=num, font=FONTS["heading_sm"], text_color=COLORS["text_primary"],
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=jc.status or "—", font=FONTS["label_sm"], text_color=st_color,
            ).pack(side="left", padx=(SPACING["sm"], 0))
            if jc.purchase_order:
                ctk.CTkLabel(
                    row, text=f"PO: {jc.purchase_order}", font=FONTS["body_sm"],
                    text_color=COLORS["text_secondary"],
                ).pack(side="left", padx=(SPACING["sm"], 0))
            ctk.CTkLabel(
                row, text=(jc.created_at or "")[:10], font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(side="left", padx=(SPACING["sm"], 0))
            ctk.CTkButton(
                row, text="Open →", font=FONTS["label_sm"], height=22,
                fg_color="transparent", text_color=COLORS["accent_primary"],
                hover_color=COLORS["surface_tertiary"], border_width=0,
                command=lambda j=jc: self._open_job_card_window(j, customer),
            ).pack(side="right")
            ctk.CTkFrame(parent, fg_color=COLORS["border_light"], height=1).pack(fill="x")

    def _build_invoices_tab(self, parent, customer, invoices):
        invoices = sorted(
            invoices,
            key=lambda i: (i["document"].issue_date or i["document"].created_at or ""),
            reverse=True,
        )
        if not invoices:
            ctk.CTkLabel(
                parent, text="No invoices yet.", font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(anchor="w", pady=SPACING["md"])
            return
        for item in invoices:
            doc = item["document"]
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=(0, SPACING["xs"]))
            ctk.CTkLabel(
                row, text=doc.document_number or "(Pending)",
                font=FONTS["heading_sm"], text_color=COLORS["text_primary"],
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=doc.issue_date or "—", font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(side="left", padx=(SPACING["md"], 0))
            st = item["status"] or "—"
            st_color = COLORS["danger"] if st == "Overdue" else COLORS["text_secondary"]
            ctk.CTkLabel(
                row, text=st, font=FONTS["label_sm"], text_color=st_color,
            ).pack(side="left", padx=(SPACING["sm"], 0))
            ctk.CTkLabel(
                row, text=format_money(doc.total_minor or 0, doc.currency or "ZAR"),
                font=FONTS["body_md"], text_color=COLORS["text_primary"],
            ).pack(side="right")
            bal = format_money(item["balance_minor"])
            ctk.CTkLabel(
                row, text=f"Bal {bal}", font=FONTS["body_sm"],
                text_color=COLORS["text_secondary"],
            ).pack(side="right", padx=(0, SPACING["sm"]))
            ctk.CTkFrame(parent, fg_color=COLORS["border_light"], height=1).pack(fill="x")

    def _build_payments_tab(self, parent, customer):
        try:
            payments = self.payment_service.list_for_customer(customer.id)
        except Exception:
            payments = []
        payments = sorted(payments, key=lambda p: p.date or p.created_at or "", reverse=True)
        if not payments:
            ctk.CTkLabel(
                parent, text="No payments yet.", font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(anchor="w", pady=SPACING["md"])
            return
        for payment in payments:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=(0, SPACING["xs"]))
            ctk.CTkLabel(
                row, text=payment.reference or "(No reference)",
                font=FONTS["heading_sm"], text_color=COLORS["text_primary"],
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=payment.date or "—", font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(side="left", padx=(SPACING["md"], 0))
            ctk.CTkLabel(
                row, text=payment.status or "—", font=FONTS["label_sm"],
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(SPACING["sm"], 0))
            ctk.CTkLabel(
                row, text=format_money(payment.amount_minor or 0),
                font=FONTS["body_md"], text_color=COLORS["text_primary"],
            ).pack(side="right")
            ctk.CTkFrame(parent, fg_color=COLORS["border_light"], height=1).pack(fill="x")

    def _build_addresses_tab(self, parent, customer, addresses):
        ctk.CTkButton(
            parent, text="+ Add Address", font=FONTS["label_sm"], height=28,
            fg_color=COLORS["accent_primary"], text_color=COLORS["text_inverse"],
            command=lambda: self._add_address(customer),
        ).pack(anchor="w", pady=(0, SPACING["md"]))
        if not addresses:
            ctk.CTkLabel(
                parent, text="No addresses yet.", font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(anchor="w")
            return
        for address in addresses:
            card = ctk.CTkFrame(
                parent, fg_color=COLORS["surface_primary"],
                border_width=1, border_color=COLORS["border_light"], corner_radius=6,
            )
            card.pack(fill="x", pady=(0, SPACING["sm"]))
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", padx=SPACING["md"], pady=SPACING["md"])
            addr_type = address.address_type or "Address"
            if address.is_primary:
                addr_type += " (Primary)"
            ctk.CTkLabel(
                inner, text=addr_type, font=FONTS["label_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(anchor="w")
            lines = []
            if address.line1:
                lines.append(address.line1)
            if address.line2:
                lines.append(address.line2)
            city = ", ".join(p for p in [address.city, address.province, address.postal_code] if p)
            if city:
                lines.append(city)
            ctk.CTkLabel(
                inner, text="\n".join(lines) if lines else "No address",
                font=FONTS["body_md"], text_color=COLORS["text_primary"],
                anchor="w", justify="left",
            ).pack(anchor="w", fill="x", pady=(SPACING["xs"], 0))

    def _build_notes_tab(self, parent, customer):
        notes = (customer.notes or "").strip()
        if not notes:
            ctk.CTkLabel(
                parent, text="No notes yet.", font=FONTS["body_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(anchor="w", pady=SPACING["md"])
            return
        note_box = ctk.CTkFrame(
            parent, fg_color=COLORS["surface_primary"],
            border_width=1, border_color=COLORS["border_light"], corner_radius=6,
        )
        note_box.pack(fill="x")
        ctk.CTkLabel(
            note_box, text=notes, font=FONTS["body_md"],
            text_color=COLORS["text_primary"], anchor="w", justify="left",
            wraplength=600,
        ).pack(padx=SPACING["md"], pady=SPACING["md"], anchor="w", fill="x")

    # ==================================================
    # Helpers (kept from original)
    # ==================================================

    def _new_quote_for_customer(self, customer):
        from core.business_settings_service import BusinessSettingsService
        from core.quote_service import QuoteService
        from modules.quotes.windows import QuoteDetailWindow
        qs = QuoteService()
        quote = qs.new_quote(customer.id)
        qs.save_quote(quote, self._actor())
        QuoteDetailWindow(
            self.winfo_toplevel(), qs, self.crm_service,
            BusinessSettingsService(), quote.id,
        )

    def _open_quote(self, quote):
        from core.business_settings_service import BusinessSettingsService
        from core.quote_service import QuoteService
        from modules.quotes.windows import QuoteDetailWindow
        QuoteDetailWindow(
            self.winfo_toplevel(),
            QuoteService(),
            self.crm_service,
            BusinessSettingsService(),
            quote.id,
        )

    def _open_job_card_window(self, job_card, customer):
        from modules.site_visit.windows import JobCardListWindow
        sites = self.crm_service.list_sites(customer.id)
        site = next((s for s in sites if s.id == job_card.site_id), None)
        if site is None and sites:
            site = sites[0]
        if site:
            JobCardListWindow(self.winfo_toplevel(), customer, site)
        else:
            from tkinter import messagebox as mb
            mb.showinfo("Job Card", f"Job Card {job_card.job_card_number} — no site linked. Open via Sites tab.", parent=self.winfo_toplevel())

    def _new_job_card(self, customer):
        from core.job_card_service import JobCardService
        from tkinter import messagebox as mb
        try:
            sites = self.crm_service.list_sites(customer.id)
        except Exception:
            sites = []
        site_id = sites[0].id if sites else ""
        try:
            jc = JobCardService().create_job_card_from_quote(
                customer, site_id=site_id, actor=self._actor()
            )
            mb.showinfo("Job Card Created", f"Job Card {jc.job_card_number} created.", parent=self.winfo_toplevel())
            self._show_customer_detail(customer)
        except Exception as exc:
            mb.showerror("Job Card Error", str(exc), parent=self.winfo_toplevel())

    def _actor(self):
        try:
            from core.auth import current_actor
            return current_actor()
        except Exception:
            import getpass
            return getpass.getuser()

    def _add_blocks_bulk(self, customer):
        """Bulk-create sites for the customer. Ported from windows_old.py."""
        try:
            addresses = self.crm_service.list_addresses(customer.id)
        except Exception as e:
            messagebox.showerror("Add Blocks", str(e), parent=self.winfo_toplevel())
            return
        if not addresses:
            messagebox.showwarning(
                "Add Blocks",
                "Add an address for this customer first.",
                parent=self.winfo_toplevel(),
            )
            return

        primary_addr = next(
            (a for a in addresses if getattr(a, "is_primary", False)),
            addresses[0],
        )

        result = TextPromptDialog.ask(
            self.winfo_toplevel(),
            "Add Blocks/Areas",
            "Enter one per line, format: Block Name, Description\nExample:\nBlock A, Main Office\nBlock B, Warehouse",
        )
        if not result:
            return

        lines = [line.strip() for line in result.split("\n") if line.strip()]
        if not lines:
            return

        created_count = 0
        for line in lines:
            parts = [p.strip() for p in line.split(",", 1)]
            site_name = parts[0]
            description = parts[1] if len(parts) > 1 else ""
            site = self.crm_service.new_site(customer.id)
            site.name = site_name
            site.site_type = "Property"
            site.address_id = primary_addr.id
            site.notes = description
            # save_site(), not sites.save() - the service is what generates
            # the site's id and timestamps. Going straight to the repository
            # saved every block with an empty id, so all of them collided on
            # one row and every site shared a single site plan.
            self.crm_service.save_site(site)
            created_count += 1

        messagebox.showinfo(
            "Add Blocks",
            f"Created {created_count} site(s).",
            parent=self.winfo_toplevel(),
        )
        # Re-render detail view to show new sites
        self._show_customer_detail(customer)

    def _open_site_plan(self, site):
        from modules.site_visit.windows import SitePlanWindow
        SitePlanWindow(self.winfo_toplevel(), self.selected_customer, site)

    def _open_job_cards(self, site):
        from modules.site_visit.windows import JobCardListWindow
        JobCardListWindow(self.winfo_toplevel(), self.selected_customer, site)

    def _add_address(self, customer):
        """Open the address form; on save, re-render the customer detail."""
        def _after_save(_addr):
            # Reload the customer so the redrawn detail view sees the new address.
            refreshed = self.crm_service.customers.get(customer.id) or customer
            self._show_customer_detail(refreshed)

        AddressForm(self.winfo_toplevel(), customer=customer, on_save=_after_save)

    # ==================================================

    def _show_list_view(self):
        """Return to list view."""
        self.current_view = "list"
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self._build_list_view()

    # ==================================================
    # Actions (Stubs - TODO)
    # ==================================================

    def _import_from_pdf(self):
        """Bulk-import customers from FacilitiesCo Estimate/Invoice PDFs.

        Ported from the pre-redesign windows_old.py (2026-08-07 crash fix
        retained: per-file try/except so a bad file is skipped, not fatal).
        """
        filepaths = filedialog.askopenfilenames(
            title="Select Quote/Invoice PDFs to import",
            filetypes=[("PDF files", "*.pdf")],
            parent=self.winfo_toplevel(),
        )
        if not filepaths:
            return

        extractor = PdfCustomerExtractor()
        actor = getpass.getuser()

        created = 0
        updated = 0
        skipped = 0
        unparseable = []
        unreadable = []

        for filepath in filepaths:
            try:
                extracted = extractor.extract(filepath)
            except Exception as error:
                unreadable.append(f"{os.path.basename(filepath)}: {error}")
                continue

            if extracted.confidence == "low":
                if not extracted.name and not extracted.address_lines and not extracted.email:
                    unparseable.append(os.path.basename(filepath))
                    continue

                values = EntityFormDialog.ask(
                    self.winfo_toplevel(),
                    f"Review import — {os.path.basename(filepath)}",
                    [
                        {"key": "name", "label": "Company / Customer Name", "kind": "text", "initial": extracted.name},
                        {"key": "address", "label": "Address (one line each)", "kind": "textarea", "initial": "\n".join(extracted.address_lines)},
                        {"key": "contact_name", "label": "Contact Person", "kind": "text", "initial": extracted.contact_name},
                        {"key": "email", "label": "Email", "kind": "text", "initial": extracted.email},
                        {"key": "vat_number", "label": "VAT Number", "kind": "text", "initial": extracted.vat_number},
                        {"key": "registration_number", "label": "Registration Number", "kind": "text", "initial": extracted.registration_number},
                    ],
                )
                if values is None or not values["name"].strip():
                    skipped += 1
                    continue

                extracted.name = values["name"].strip()
                extracted.address_lines = [line.strip() for line in values["address"].split("\n") if line.strip()]
                extracted.contact_name = values["contact_name"].strip()
                extracted.email = values["email"].strip()
                extracted.vat_number = values["vat_number"].strip()
                extracted.registration_number = values["registration_number"].strip()

            try:
                customer, is_new = self.crm_service.import_customer_from_pdf(extracted, actor)
            except ValueError as error:
                messagebox.showerror(
                    "Import from PDF",
                    f"{os.path.basename(filepath)}: {error}",
                    parent=self.winfo_toplevel(),
                )
                skipped += 1
                continue

            self.crm_service.client_folder_service.ensure_client_folder(customer)

            if is_new:
                created += 1
            else:
                updated += 1

        self._refresh_list()

        summary_lines = [f"Imported {created} new customer(s), updated {updated} existing match(es)."]
        if skipped:
            summary_lines.append(f"{skipped} skipped.")
        if unparseable:
            summary_lines.append(
                f"{len(unparseable)} file(s) didn't match a recognized layout and weren't imported:\n"
                + "\n".join(unparseable)
            )
        if unreadable:
            summary_lines.append(
                f"{len(unreadable)} file(s) couldn't be read and were skipped:\n"
                + "\n".join(unreadable)
            )
        messagebox.showinfo("Import from PDF", "\n\n".join(summary_lines), parent=self.winfo_toplevel())

    def _new_customer(self):
        """Create new customer."""
        form = CustomerForm(self.winfo_toplevel(), mode="create", on_save=self._on_customer_saved)

    def _edit_customer(self, customer):
        """Edit customer."""
        form = CustomerForm(
            self.winfo_toplevel(),
            mode="edit",
            customer=customer,
            on_save=self._on_customer_saved,
        )

    def _on_customer_saved(self, customer):
        """Handle customer save."""
        if not self.winfo_exists():
            return
        self._refresh_list()
        self._show_customer_detail(customer)

    def _view_projects(self, customer):
        """View customer's projects."""
        # TODO: Filter projects to this customer
        messagebox.showinfo("Projects", f"Projects for {customer.name} coming soon")


# ==================================================
# Customer Form Dialog
# ==================================================

class CustomerForm(ctk.CTkToplevel):
    """Modal form for creating/editing customers."""

    def __init__(self, parent, mode="create", customer=None, on_save=None):
        super().__init__(parent)

        self.mode = mode
        self.customer = customer
        self.on_save = on_save
        self.crm_service = CRMService()

        self.title("New Customer" if mode == "create" else f"Edit {customer.name}")
        self.geometry("560x640")
        self.resizable(False, False)

        # Configure
        self.configure(fg_color=COLORS["surface_primary"])

        # Build form
        self._build_form()

    def _build_form(self):
        """Build form fields."""
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["surface_primary"],
        )
        scroll.pack(fill="both", expand=True, padx=SPACING["lg"], pady=SPACING["lg"])

        # Title
        ctk.CTkLabel(
            scroll,
            text="New Customer" if self.mode == "create" else "Edit Customer",
            font=FONTS["heading_md"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, SPACING["lg"]))

        # Form fields
        self.fields = {}

        self._primary_contact_obj = None
        if self.customer:
            contacts = self.crm_service.list_contacts(self.customer.id)
            self._primary_contact_obj = next(
                (c for c in contacts if getattr(c, "is_primary", False)),
                contacts[0] if contacts else None,
            )

        fields_config = [
            ("name", "Customer Name *", True, "text"),
            ("contact_name", "Contact Person", False, "text"),
            ("customer_type", "Customer Type", False, "text"),
            ("payment_terms", "Payment Terms", False, "text"),
            ("email", "Email", False, "text"),
            ("phone", "Phone", False, "text"),
            ("website", "Website", False, "text"),
            ("vat_number", "VAT Number", False, "text"),
            ("registration_number", "Registration Number", False, "text"),
            ("notes", "Notes", False, "textarea"),
        ]

        for field_id, label, required, kind in fields_config:
            self._add_form_field(scroll, field_id, label, required, kind)

        # Buttons
        button_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        button_frame.pack(fill="x", pady=(SPACING["lg"], 0))

        ctk.CTkButton(
            button_frame,
            text="Save",
            font=FONTS["label"],
            fg_color=COLORS["accent_primary"],
            text_color=COLORS["text_inverse"],
            command=self._save,
        ).pack(side="left", padx=(0, SPACING["md"]))

        ctk.CTkButton(
            button_frame,
            text="Cancel",
            font=FONTS["label"],
            fg_color=COLORS["surface_tertiary"],
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border_default"],
            command=self.destroy,
        ).pack(side="left")

    def _add_form_field(self, parent, field_id, label, required, kind="text"):
        """Add a form field."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=(0, SPACING["md"]))

        # Label
        label_text = label + (" *" if required else "")
        ctk.CTkLabel(
            frame,
            text=label_text,
            font=FONTS["body_sm"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, SPACING["sm"]))

        # Input
        initial_value = ""
        if field_id == "contact_name" and self._primary_contact_obj:
            initial_value = self._primary_contact_obj.name or ""
        elif self.customer:
            initial_value = getattr(self.customer, field_id, "") or ""

        if kind == "textarea":
            widget = ctk.CTkTextbox(
                frame,
                font=FONTS["body_md"],
                fg_color=COLORS["surface_secondary"],
                border_color=COLORS["border_default"],
                border_width=1,
                corner_radius=6,
                height=96,
            )
            widget.pack(fill="x")
            if initial_value:
                widget.insert("1.0", initial_value)
        else:
            widget = ctk.CTkEntry(
                frame,
                font=FONTS["body_md"],
                fg_color=COLORS["surface_secondary"],
                border_color=COLORS["border_default"],
                border_width=1,
                corner_radius=6,
                height=32,
            )
            widget.pack(fill="x")
            widget.insert(0, initial_value)

        self.fields[field_id] = {
            "widget": widget,
            "required": required,
            "kind": kind,
            "error_label": None,
        }

    def _save(self):
        """Save customer."""
        # Validate
        errors = self._validate()
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors), parent=self)
            return

        # Get values
        data = {
            field_id: self._field_value(info)
            for field_id, info in self.fields.items()
        }

        try:
            from datetime import datetime
            now = datetime.now().isoformat()
            if self.mode == "create":
                from core.customer import Customer
                customer = Customer(
                    name=data["name"],
                    customer_type=data["customer_type"],
                    status="Active",
                    payment_terms=data["payment_terms"] or "Standard",
                    email=data["email"],
                    phone=data["phone"],
                    website=data["website"],
                    vat_number=data["vat_number"],
                    registration_number=data["registration_number"],
                    notes=data["notes"],
                    created_at=now,
                    updated_at=now,
                )
                self.customer = self.crm_service.save_customer(customer)
            else:
                self.customer.name = data["name"]
                self.customer.customer_type = data["customer_type"]
                if data["payment_terms"]:
                    self.customer.payment_terms = data["payment_terms"]
                self.customer.email = data["email"]
                self.customer.phone = data["phone"]
                self.customer.website = data["website"]
                self.customer.vat_number = data["vat_number"]
                self.customer.registration_number = data["registration_number"]
                self.customer.notes = data["notes"]
                self.customer.updated_at = now
                self.crm_service.save_customer(self.customer)

            contact_name = data.get("contact_name", "").strip()
            if contact_name:
                if self._primary_contact_obj:
                    self._primary_contact_obj.name = contact_name
                    self.crm_service.save_contact(self._primary_contact_obj)
                else:
                    from core.contact import Contact
                    contact = Contact(
                        customer_id=self.customer.id,
                        name=contact_name,
                        is_primary=True,
                    )
                    self.crm_service.save_contact(contact)

            self.destroy()

            if self.on_save:
                self.on_save(self.customer)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _field_value(self, info):
        widget = info["widget"]
        if info.get("kind") == "textarea":
            return widget.get("1.0", "end").strip()
        return widget.get().strip()

    def _validate(self):
        """Validate form fields."""
        errors = []
        for field_id, field_info in self.fields.items():
            if field_info["required"]:
                if not self._field_value(field_info):
                    field_label = field_id.replace("_", " ").title()
                    errors.append(f"{field_label} is required")
        return errors


class AddressForm(ctk.CTkToplevel):
    """Modal form for creating an address on a customer."""

    # Every type Minette can pick, in the order she reads them off a
    # document. Deliberately NOT _ADDRESS_TYPE_PRIORITY - that tuple
    # controls which address the CRM list column shows and must not
    # gain "Delivery" as a side effect of offering it here.
    ADDRESS_TYPES = ["Billing", "Delivery", "Physical", "Postal", "Site"]

    def __init__(self, parent, customer, on_save=None):
        super().__init__(parent)

        self.customer = customer
        self.on_save = on_save
        self.crm_service = CRMService()

        self.title(f"New Address — {customer.name}")
        self.geometry("520x560")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["surface_primary"])

        self._build_form()

    def _build_form(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["surface_primary"])
        scroll.pack(fill="both", expand=True, padx=SPACING["lg"], pady=SPACING["lg"])

        ctk.CTkLabel(
            scroll,
            text="New Address",
            font=FONTS["heading_md"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, SPACING["lg"]))

        # Address type dropdown
        ctk.CTkLabel(
            scroll, text="Address Type *",
            font=FONTS["body_sm"], text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, SPACING["sm"]))
        self.type_var = ctk.StringVar(value=self.ADDRESS_TYPES[0])
        ctk.CTkOptionMenu(
            scroll,
            variable=self.type_var,
            values=self.ADDRESS_TYPES,
            fg_color=COLORS["surface_secondary"],
            button_color=COLORS["accent_primary"],
            text_color=COLORS["text_primary"],
        ).pack(fill="x", pady=(0, SPACING["md"]))

        # Text fields
        self.entries = {}
        text_fields = [
            ("line1", "Address Line 1 *", True),
            ("line2", "Address Line 2", False),
            ("city", "City", False),
            ("province", "Province", False),
            ("postal_code", "Postal Code", False),
        ]
        for key, label, required in text_fields:
            self._add_entry(scroll, key, label, required)

        # is_primary checkbox
        self.primary_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            scroll,
            text="Set as primary address",
            variable=self.primary_var,
            font=FONTS["body_sm"],
            text_color=COLORS["text_primary"],
            fg_color=COLORS["accent_primary"],
        ).pack(anchor="w", pady=(SPACING["sm"], SPACING["lg"]))

        # Buttons
        button_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        button_frame.pack(fill="x")
        ctk.CTkButton(
            button_frame, text="Save", font=FONTS["label"],
            fg_color=COLORS["accent_primary"], text_color=COLORS["text_inverse"],
            command=self._save,
        ).pack(side="left", padx=(0, SPACING["md"]))
        ctk.CTkButton(
            button_frame, text="Cancel", font=FONTS["label"],
            fg_color=COLORS["surface_tertiary"], text_color=COLORS["text_primary"],
            border_width=1, border_color=COLORS["border_default"],
            command=self.destroy,
        ).pack(side="left")

    def _add_entry(self, parent, key, label, required):
        ctk.CTkLabel(
            parent, text=label,
            font=FONTS["body_sm"], text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, SPACING["sm"]))
        entry = ctk.CTkEntry(
            parent, font=FONTS["body_md"],
            fg_color=COLORS["surface_secondary"],
            border_color=COLORS["border_default"], border_width=1,
            corner_radius=6, height=32,
        )
        entry.pack(fill="x", pady=(0, SPACING["md"]))
        self.entries[key] = (entry, required)

    def _save(self):
        errors = []
        values = {}
        for key, (entry, required) in self.entries.items():
            v = entry.get().strip()
            if required and not v:
                errors.append(f"{key.replace('_', ' ').title()} is required")
            values[key] = v
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors), parent=self)
            return

        try:
            address = self.crm_service.new_address(self.customer.id)
            address.address_type = self.type_var.get()
            address.line1 = values["line1"]
            address.line2 = values["line2"]
            address.city = values["city"]
            address.province = values["province"]
            address.postal_code = values["postal_code"]
            address.country = "South Africa"
            address.is_primary = bool(self.primary_var.get())
            address.created_by = getpass.getuser()
            address.updated_by = getpass.getuser()
            saved = self.crm_service.save_address(address)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
            return

        if self.on_save:
            self.on_save(saved)
        self.destroy()
