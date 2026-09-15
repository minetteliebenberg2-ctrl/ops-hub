# ==========================================================
# FC Hub - Dashboard View (HubSpot-style Redesign)
# ----------------------------------------------------------
# KPI strip, A-Z client finder, 2x2 card grid
# ==========================================================

import customtkinter as ctk
from datetime import datetime

from modules.dashboard.dashboard_data import DashboardData
from core.contact import Contact
from core.crm_service import CRMService
from core.quote_pdf import format_money
from gui.design_tokens import COLORS, FONTS, SPACING

_main_window_ref = None


def set_main_window_ref(window_ref):
    global _main_window_ref
    _main_window_ref = window_ref


class DashboardView(ctk.CTkFrame):
    """HubSpot-style dashboard with KPIs, client finder, and card grid."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["surface_primary"],
            **kwargs
        )

        self.data = DashboardData()
        self.crm_service = CRMService()
        self.kpi_labels = {}
        self._all_customers = []
        self._active_letter = None

        self._build_layout()

        self.data.load_kpis_async(self._on_kpis_loaded)
        self.data.load_activities_async(self._on_activities_loaded)
        self.data.load_sidebar_widgets_async(self._on_sidebar_loaded)
        self._load_customers()

    # ==================================================
    # Layout
    # ==================================================

    def _build_layout(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["surface_primary"])
        scroll.pack(fill="both", expand=True)
        self._scroll = scroll

        self._build_header(scroll)
        self._build_kpi_strip(scroll)
        self._build_client_bar(scroll)
        self._build_quick_actions(scroll)
        self._build_card_grid(scroll)

    # ==================================================

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=SPACING["xxl"], pady=(SPACING["xxl"], SPACING["sm"]))

        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.pack(fill="x")

        ctk.CTkLabel(
            title_row, text="Dashboard", font=FONTS["title_lg"],
            text_color=COLORS["text_primary"],
        ).pack(side="left", anchor="w")

        ctk.CTkButton(
            title_row, text="⛶", width=30, height=30,
            font=("Lato", 16),
            fg_color="transparent",
            text_color=COLORS["text_tertiary"],
            hover_color=COLORS["surface_secondary"],
            border_width=0,
            command=lambda: self.winfo_toplevel().state("zoomed"),
        ).pack(side="left", padx=(8, 0), anchor="w")

        now = datetime.now()
        ctk.CTkLabel(
            header, text=now.strftime("%A %d %B %Y · FacilitiesCo"),
            font=FONTS["body_sm"], text_color=COLORS["text_tertiary"],
        ).pack(anchor="w", pady=(2, 0))

    # ==================================================

    def _build_kpi_strip(self, parent):
        strip = ctk.CTkFrame(parent, fg_color="transparent")
        strip.pack(fill="x", padx=SPACING["xxl"], pady=(SPACING["sm"], SPACING["md"]))
        strip.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="kpi")

        kpis = [
            ("customers", "Customers", "—", "—"),
            ("active_quotes", "Open Quotes", "—", "—"),
            ("upcoming_visits", "Visits", "—", "—"),
            ("outstanding_invoices", "Outstanding", "—", "—"),
            ("overdue", "Overdue", "—", "—"),
        ]

        for col, (kpi_id, label, val, sub) in enumerate(kpis):
            card = ctk.CTkFrame(
                strip, fg_color=COLORS["surface_secondary"],
                border_width=1, border_color=COLORS["border_default"], corner_radius=6,
            )
            card.grid(row=0, column=col, sticky="nsew",
                      padx=(0, SPACING["sm"] if col < 4 else 0))
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", padx=SPACING["md"], pady=SPACING["md"])

            ctk.CTkLabel(
                inner, text=label, font=FONTS["label_sm"],
                text_color=COLORS["text_tertiary"],
            ).pack(anchor="w")

            is_money = kpi_id in ("outstanding_invoices", "overdue")
            val_label = ctk.CTkLabel(
                inner, text=val, font=FONTS["heading_md"],
                text_color=COLORS["accent_primary"] if is_money else COLORS["text_primary"],
            )
            val_label.pack(anchor="w", pady=(2, 0))

            sub_label = ctk.CTkLabel(
                inner, text=sub, font=FONTS["label_sm"],
                text_color=COLORS["text_secondary"],
            )
            sub_label.pack(anchor="w")

            self.kpi_labels[kpi_id] = (val_label, sub_label)

    # ==================================================

    def _build_client_bar(self, parent):
        bar = ctk.CTkFrame(
            parent, fg_color=COLORS["surface_secondary"],
            border_width=1, border_color=COLORS["border_default"], corner_radius=6,
        )
        bar.pack(fill="x", padx=SPACING["xxl"], pady=(0, SPACING["md"]))

        top = ctk.CTkFrame(bar, fg_color="transparent")
        top.pack(fill="x", padx=SPACING["md"], pady=(SPACING["md"], SPACING["sm"]))

        self._client_search_var = ctk.StringVar()
        self._client_search_var.trace_add("write", lambda *_: self._filter_clients())
        search = ctk.CTkEntry(
            top, placeholder_text="Search clients...",
            textvariable=self._client_search_var,
            font=FONTS["body_md"],
            fg_color=COLORS["surface_primary"],
            border_color=COLORS["border_default"], border_width=1,
            corner_radius=4, height=30,
        )
        search.pack(side="left", fill="x", expand=True, padx=(0, SPACING["md"]))

        self._client_count_label = ctk.CTkLabel(
            top, text="", font=FONTS["body_sm"],
            text_color=COLORS["text_tertiary"],
        )
        self._client_count_label.pack(side="right")

        # A-Z strip
        az_frame = ctk.CTkFrame(bar, fg_color="transparent")
        az_frame.pack(fill="x", padx=SPACING["md"], pady=(0, SPACING["sm"]))
        self._az_buttons = {}
        for i in range(26):
            ch = chr(65 + i)
            btn = ctk.CTkButton(
                az_frame, text=ch, font=("Lato", 10, "bold"),
                fg_color="transparent", text_color=COLORS["text_tertiary"],
                hover_color=COLORS["surface_tertiary"],
                border_width=0, corner_radius=3,
                width=28, height=22,
                command=lambda c=ch: self._pick_letter(c),
            )
            btn.pack(side="left", padx=0)
            self._az_buttons[ch] = btn

        # Results dropdown
        self._client_results_frame = ctk.CTkFrame(bar, fg_color="transparent")
        self._client_results_scroll = None

    # ==================================================

    def _build_quick_actions(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=SPACING["xxl"], pady=(0, SPACING["md"]))

        actions = [
            ("+ New Quote", self._action_new_quote),
            ("+ New Customer", self._action_new_customer),
            ("+ Add Contact", self._action_add_contact),
            ("Schedule Job", self._action_schedule_visit),
            ("Documents", self._action_documents),
            ("Job KPIs", self._action_job_kpis),
        ]

        for label, callback in actions:
            is_primary = label.startswith("+")
            ctk.CTkButton(
                frame, text=label, font=FONTS["label"], height=30,
                fg_color=COLORS["accent_primary"] if is_primary else COLORS["surface_secondary"],
                text_color=COLORS["text_inverse"] if is_primary else COLORS["text_primary"],
                border_width=0 if is_primary else 1,
                border_color=COLORS["border_default"],
                hover_color=COLORS["accent_hover"] if is_primary else COLORS["surface_tertiary"],
                corner_radius=4,
                command=callback,
            ).pack(side="left", padx=(0, SPACING["sm"]))

    # ==================================================

    def _build_card_grid(self, parent):
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=SPACING["xxl"], pady=(0, SPACING["xxl"]))
        grid.grid_columnconfigure((0, 1), weight=1, uniform="cards")
        grid.grid_rowconfigure((0, 1), weight=1)

        # Recent Quotes (top-left)
        self._quotes_card = self._card_shell(grid, "Recent Quotes", 0, 0)
        self._quotes_content = ctk.CTkFrame(self._quotes_card, fg_color="transparent")
        self._quotes_content.pack(fill="both", expand=True)
        ctk.CTkLabel(
            self._quotes_content, text="Loading...", font=FONTS["body_sm"],
            text_color=COLORS["text_tertiary"],
        ).pack(anchor="w")

        # This Week (top-right)
        self._schedule_card = self._card_shell(grid, "This Week", 0, 1)
        self._schedule_content = ctk.CTkFrame(self._schedule_card, fg_color="transparent")
        self._schedule_content.pack(fill="both", expand=True)
        ctk.CTkLabel(
            self._schedule_content, text="Loading...", font=FONTS["body_sm"],
            text_color=COLORS["text_tertiary"],
        ).pack(anchor="w")

        # Overdue Invoices (bottom-left)
        self._overdue_card = self._card_shell(grid, "Overdue Invoices", 1, 0)
        self._overdue_content = ctk.CTkFrame(self._overdue_card, fg_color="transparent")
        self._overdue_content.pack(fill="both", expand=True)
        ctk.CTkLabel(
            self._overdue_content, text="Loading...", font=FONTS["body_sm"],
            text_color=COLORS["text_tertiary"],
        ).pack(anchor="w")

        # Recent Activity (bottom-right)
        self._activity_card = self._card_shell(grid, "Recent Activity", 1, 1)
        self._activity_content = ctk.CTkFrame(self._activity_card, fg_color="transparent")
        self._activity_content.pack(fill="both", expand=True)
        ctk.CTkLabel(
            self._activity_content, text="Loading...", font=FONTS["body_sm"],
            text_color=COLORS["text_tertiary"],
        ).pack(anchor="w")

    def _card_shell(self, parent, title, row, col):
        card = ctk.CTkFrame(
            parent, fg_color=COLORS["surface_secondary"],
            border_width=1, border_color=COLORS["border_default"], corner_radius=6,
        )
        card.grid(row=row, column=col, sticky="nsew",
                  padx=(0, SPACING["sm"] if col == 0 else 0),
                  pady=(0, SPACING["sm"] if row == 0 else 0))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=SPACING["md"], pady=SPACING["md"])
        ctk.CTkLabel(
            inner, text=title, font=FONTS["heading_sm"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, SPACING["sm"]))
        return inner

    # ==================================================
    # Client finder
    # ==================================================

    def _load_customers(self):
        import threading
        def _load():
            try:
                self._all_customers = self.crm_service.list_customers() or []
            except Exception:
                self._all_customers = []
            if self.winfo_exists():
                self.after(0, self._update_az_strip)
        threading.Thread(target=_load, daemon=True).start()

    def _update_az_strip(self):
        if not self.winfo_exists():
            return
        used = set()
        for c in self._all_customers:
            if c.name:
                used.add(c.name[0].upper())
        for ch, btn in self._az_buttons.items():
            try:
                if ch in used:
                    btn.configure(text_color=COLORS["text_tertiary"])
                else:
                    btn.configure(text_color=COLORS["border_default"])
            except Exception:
                return
        try:
            self._client_count_label.configure(text=f"{len(self._all_customers)} clients")
        except Exception:
            pass

    def _pick_letter(self, ch):
        if self._active_letter == ch:
            self._active_letter = None
        else:
            self._active_letter = ch
        for letter, btn in self._az_buttons.items():
            if letter == self._active_letter:
                btn.configure(fg_color=COLORS["accent_primary"], text_color=COLORS["text_inverse"])
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_tertiary"])
        self._client_search_var.set("")
        self._show_client_results()

    def _filter_clients(self):
        self._active_letter = None
        for btn in self._az_buttons.values():
            btn.configure(fg_color="transparent", text_color=COLORS["text_tertiary"])
        self._show_client_results()

    def _show_client_results(self):
        q = self._client_search_var.get().lower()
        letter = self._active_letter

        if not q and not letter:
            self._client_results_frame.pack_forget()
            self._client_count_label.configure(text=f"{len(self._all_customers)} clients")
            return

        filtered = self._all_customers
        if letter:
            filtered = [c for c in filtered if c.name and c.name[0].upper() == letter]
        if q:
            filtered = [c for c in filtered if q in c.name.lower()]

        self._client_count_label.configure(text=f"{len(filtered)} client{'s' if len(filtered) != 1 else ''}")

        # Clear and rebuild results
        for w in self._client_results_frame.winfo_children():
            w.destroy()

        if not filtered:
            ctk.CTkLabel(
                self._client_results_frame, text="No matches.",
                font=FONTS["body_sm"], text_color=COLORS["text_tertiary"],
            ).pack(padx=SPACING["md"], pady=SPACING["sm"])
        else:
            for c in filtered[:15]:
                row = ctk.CTkFrame(self._client_results_frame, fg_color="transparent")
                row.pack(fill="x", padx=SPACING["sm"], pady=1)
                row.bind("<Enter>", lambda e, r=row: r.configure(fg_color=COLORS["surface_tertiary"]))
                row.bind("<Leave>", lambda e, r=row: r.configure(fg_color="transparent"))

                initials = "".join(w[0] for w in c.name.split()[:2]).upper()
                av = ctk.CTkFrame(row, fg_color=COLORS["accent_primary"],
                                  corner_radius=999, width=24, height=24)
                av.pack(side="left", padx=(SPACING["sm"], SPACING["sm"]), pady=3)
                av.pack_propagate(False)
                ctk.CTkLabel(av, text=initials, font=("Lato", 9, "bold"),
                             text_color=COLORS["text_inverse"]).place(relx=0.5, rely=0.5, anchor="center")

                num = c.customer_number or ""
                display = f"{num}  {c.name}" if num else c.name
                ctk.CTkLabel(
                    row, text=display, font=FONTS["body_sm"],
                    text_color=COLORS["text_primary"], anchor="w",
                ).pack(side="left", fill="x", expand=True)

                # Make entire row clickable
                def _on_click(event, cust=c):
                    self._open_customer(cust)
                row.bind("<Button-1>", _on_click)
                for child in row.winfo_children():
                    child.bind("<Button-1>", _on_click)

        self._client_results_frame.pack(fill="x", padx=0, pady=(0, SPACING["sm"]))

    def _open_customer(self, customer):
        if _main_window_ref:
            _main_window_ref.open_module_by_id("crm")
            # Find the CRM window and show customer detail
            try:
                host = _main_window_ref.module_host
                if host and host.current_frame:
                    host.current_frame._show_customer_detail(customer)
            except Exception:
                pass

    # ==================================================
    # Data callbacks
    # ==================================================

    def _on_kpis_loaded(self, data):
        if self.winfo_exists():
            self.after(0, lambda: self._update_kpis(data))

    def _update_kpis(self, data):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        updates = {
            "customers": (str(len(self._all_customers)), ""),
            "active_quotes": (str(data.get("active_quotes", "—")), ""),
            "upcoming_visits": (str(data.get("upcoming_visits", "—")), ""),
            "outstanding_invoices": (str(data.get("outstanding_invoices", "—")), ""),
            "overdue": ("—", ""),
        }
        for kpi_id, (val, sub) in updates.items():
            if kpi_id in self.kpi_labels:
                try:
                    self.kpi_labels[kpi_id][0].configure(text=val)
                except Exception:
                    pass

    def _on_activities_loaded(self, activities):
        if self.winfo_exists():
            self.after(0, lambda: self._update_activities(activities))

    def _update_activities(self, activities):
        try:
            if not self.winfo_exists():
                return
            for w in self._activity_content.winfo_children():
                w.destroy()
        except Exception:
            return

        if not activities:
            ctk.CTkLabel(
                self._activity_content, text="No recent activity.",
                font=FONTS["body_sm"], text_color=COLORS["text_tertiary"],
            ).pack(anchor="w")
            return

        for act in activities[:6]:
            row = ctk.CTkFrame(self._activity_content, fg_color="transparent")
            row.pack(fill="x", pady=(0, SPACING["xs"]))
            ctk.CTkLabel(
                row, text=act.get("icon", "📌"), font=("Arial", 12),
                text_color=COLORS["text_primary"],
            ).pack(side="left", padx=(0, SPACING["sm"]))
            body = ctk.CTkFrame(row, fg_color="transparent")
            body.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(
                body, text=act.get("entity", ""), font=FONTS["body_sm"],
                text_color=COLORS["text_primary"], anchor="w",
            ).pack(anchor="w", fill="x")
            ctk.CTkLabel(
                body, text=act.get("description", ""), font=FONTS["label_sm"],
                text_color=COLORS["text_tertiary"], anchor="w",
            ).pack(anchor="w", fill="x")
            ts = act.get("timestamp", "")
            if ts:
                ctk.CTkLabel(
                    row, text=self._format_time(ts), font=FONTS["label_sm"],
                    text_color=COLORS["text_tertiary"],
                ).pack(side="right")

    def _on_sidebar_loaded(self, data):
        if self.winfo_exists():
            self.after(0, lambda: self._update_sidebar(data))

    def _update_sidebar(self, data):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        # Recent quotes
        try:
            for w in self._quotes_content.winfo_children():
                w.destroy()
            from core.quote_service import QuoteService
            quotes = QuoteService().list_quotes() or []
            quotes = sorted(quotes, key=lambda q: q.created_at or "", reverse=True)[:5]
            if not quotes:
                ctk.CTkLabel(
                    self._quotes_content, text="No quotes yet.",
                    font=FONTS["body_sm"], text_color=COLORS["text_tertiary"],
                ).pack(anchor="w")
            else:
                for q in quotes:
                    row = ctk.CTkFrame(self._quotes_content, fg_color="transparent")
                    row.pack(fill="x", pady=(0, 2))
                    ctk.CTkLabel(
                        row, text=q.quote_number or "(Draft)",
                        font=FONTS["heading_sm"], text_color=COLORS["text_primary"],
                    ).pack(side="left")
                    st = q.status or "—"
                    st_color = COLORS["accent_primary"] if st == "Accepted" else COLORS["text_secondary"]
                    ctk.CTkLabel(
                        row, text=st, font=FONTS["label_sm"], text_color=st_color,
                    ).pack(side="left", padx=(SPACING["sm"], 0))
                    ctk.CTkLabel(
                        row, text=format_money(q.total_minor or 0),
                        font=FONTS["body_sm"], text_color=COLORS["text_primary"],
                    ).pack(side="right")
                    ctk.CTkFrame(self._quotes_content, fg_color=COLORS["border_light"], height=1).pack(fill="x")
        except Exception:
            pass

        # Overdue invoices
        try:
            for w in self._overdue_content.winfo_children():
                w.destroy()
            overdue = data.get("overdue_invoices", [])
            if not overdue:
                ctk.CTkLabel(
                    self._overdue_content, text="No overdue invoices.",
                    font=FONTS["body_sm"], text_color=COLORS["text_tertiary"],
                ).pack(anchor="w")
            else:
                for inv in overdue:
                    row = ctk.CTkFrame(self._overdue_content, fg_color="transparent")
                    row.pack(fill="x", pady=(0, 2))
                    ctk.CTkLabel(
                        row, text=inv["invoice_number"] or "—",
                        font=FONTS["heading_sm"], text_color=COLORS["text_primary"],
                    ).pack(side="left")
                    ctk.CTkLabel(
                        row, text=f"{inv['days_overdue']}d",
                        font=FONTS["label_sm"], text_color=COLORS["danger"],
                    ).pack(side="left", padx=(SPACING["sm"], 0))
                    ctk.CTkLabel(
                        row, text=inv["customer"], font=FONTS["body_sm"],
                        text_color=COLORS["text_secondary"],
                    ).pack(side="left", padx=(SPACING["sm"], 0))
                    ctk.CTkLabel(
                        row, text=inv["amount"], font=FONTS["body_sm"],
                        text_color=COLORS["text_primary"],
                    ).pack(side="right")
                    ctk.CTkFrame(self._overdue_content, fg_color=COLORS["border_light"], height=1).pack(fill="x")
        except Exception:
            pass

        # Schedule — use upcoming visits
        try:
            for w in self._schedule_content.winfo_children():
                w.destroy()
            visits = data.get("upcoming_visits", [])
            if not visits:
                ctk.CTkLabel(
                    self._schedule_content, text="Nothing scheduled.",
                    font=FONTS["body_sm"], text_color=COLORS["text_tertiary"],
                ).pack(anchor="w")
            else:
                for v in visits:
                    row = ctk.CTkFrame(self._schedule_content, fg_color="transparent")
                    row.pack(fill="x", pady=(0, 2))
                    ctk.CTkLabel(
                        row, text=v["customer"], font=FONTS["heading_sm"],
                        text_color=COLORS["text_primary"],
                    ).pack(side="left")
                    ctk.CTkLabel(
                        row, text=v.get("site_name", ""), font=FONTS["body_sm"],
                        text_color=COLORS["text_secondary"],
                    ).pack(side="left", padx=(SPACING["sm"], 0))
                    ctk.CTkLabel(
                        row, text=v.get("date", ""), font=FONTS["body_sm"],
                        text_color=COLORS["text_tertiary"],
                    ).pack(side="right")
                    ctk.CTkFrame(self._schedule_content, fg_color=COLORS["border_light"], height=1).pack(fill="x")
        except Exception:
            pass

    # ==================================================
    # Quick Actions
    # ==================================================

    def _action_new_quote(self):
        if _main_window_ref:
            _main_window_ref.open_module_by_id("quotes")

    def _action_new_customer(self):
        if _main_window_ref:
            _main_window_ref.open_module_by_id("crm")

    def _action_schedule_visit(self):
        if _main_window_ref:
            _main_window_ref.open_module_by_id("site_visit")

    def _action_documents(self):
        if _main_window_ref:
            _main_window_ref.open_module_by_id("documents")

    def _action_create_invoice(self):
        if _main_window_ref:
            _main_window_ref.open_module_by_id("accounting")

    def _action_job_kpis(self):
        from modules.dashboard.kpi_window import JobKPIWindow
        JobKPIWindow(self.winfo_toplevel())

    def _action_add_contact(self):
        AddContactDialog(self.winfo_toplevel(), self.crm_service, self._all_customers)

    # ==================================================
    # Helpers
    # ==================================================

    @staticmethod
    def _format_time(timestamp):
        if not timestamp:
            return ""
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return ""
        else:
            dt = timestamp
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = now - dt
        if delta.days > 0:
            return f"{delta.days}d ago"
        if delta.seconds > 3600:
            return f"{delta.seconds // 3600}h ago"
        if delta.seconds > 60:
            return f"{delta.seconds // 60}m ago"
        return "now"


class AddContactDialog(ctk.CTkToplevel):
    """Simple dialog to add a contact person to any customer."""

    def __init__(self, parent, crm_service, customers):
        super().__init__(parent)
        self.title("Add Contact Person")
        self.geometry("420x480")
        self.resizable(False, False)
        self.crm_service = crm_service
        self._customers = sorted(customers, key=lambda c: c.name or "")

        self.transient(parent)
        self.grab_set()
        self.focus_force()

        self._build_form()

    def _build_form(self):
        pad = SPACING["md"]

        ctk.CTkLabel(
            self, text="Add Contact Person", font=FONTS["heading_md"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", padx=pad, pady=(pad, SPACING["sm"]))

        ctk.CTkLabel(
            self, text="Link to Customer", font=FONTS["label"],
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", padx=pad, pady=(SPACING["sm"], 2))
        customer_names = [c.name for c in self._customers]
        self._customer_var = ctk.StringVar(value=customer_names[0] if customer_names else "")
        self._customer_menu = ctk.CTkOptionMenu(
            self, values=customer_names or ["(no customers)"],
            variable=self._customer_var,
            font=FONTS["body_md"],
            fg_color=COLORS["surface_secondary"],
            button_color=COLORS["accent_primary"],
            button_hover_color=COLORS["accent_hover"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["surface_secondary"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["surface_tertiary"],
        )
        self._customer_menu.pack(fill="x", padx=pad, pady=(0, SPACING["sm"]))

        fields = [
            ("Name *", "_name_entry"),
            ("Job Title", "_title_entry"),
            ("Email", "_email_entry"),
            ("Phone", "_phone_entry"),
            ("Mobile / WhatsApp", "_mobile_entry"),
        ]
        for label_text, attr in fields:
            ctk.CTkLabel(
                self, text=label_text, font=FONTS["label"],
                text_color=COLORS["text_secondary"],
            ).pack(anchor="w", padx=pad, pady=(SPACING["xs"], 2))
            entry = ctk.CTkEntry(
                self, font=FONTS["body_md"],
                fg_color=COLORS["surface_primary"],
                border_color=COLORS["border_default"], border_width=1,
                corner_radius=4, height=30,
            )
            entry.pack(fill="x", padx=pad)
            setattr(self, attr, entry)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=pad, pady=(SPACING["md"], pad))

        ctk.CTkButton(
            btn_frame, text="Cancel", font=FONTS["label"], height=32,
            fg_color=COLORS["surface_secondary"],
            text_color=COLORS["text_primary"],
            border_width=1, border_color=COLORS["border_default"],
            hover_color=COLORS["surface_tertiary"],
            corner_radius=4, command=self.destroy,
        ).pack(side="right", padx=(SPACING["sm"], 0))

        ctk.CTkButton(
            btn_frame, text="Save Contact", font=FONTS["label"], height=32,
            fg_color=COLORS["accent_primary"],
            text_color=COLORS["text_inverse"],
            hover_color=COLORS["accent_hover"],
            corner_radius=4, command=self._save,
        ).pack(side="right")

    def _save(self):
        name = self._name_entry.get().strip()
        if not name:
            self._name_entry.configure(border_color=COLORS.get("danger", "#E53935"))
            return

        customer_name = self._customer_var.get()
        customer = next((c for c in self._customers if c.name == customer_name), None)
        if not customer:
            return

        contact = Contact(
            customer_id=customer.id,
            name=name,
            job_title=self._title_entry.get().strip(),
            email=self._email_entry.get().strip(),
            phone=self._phone_entry.get().strip(),
            mobile=self._mobile_entry.get().strip(),
            whatsapp=self._mobile_entry.get().strip(),
        )
        self.crm_service.save_contact(contact)
        self.destroy()
