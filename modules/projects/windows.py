import customtkinter as ctk

from core.crm_service import CRMService
from core.quote_repository import QuoteRepository
from core.quote_pdf import format_money
from core.scheduled_job_service import ScheduledJobService
from gui.design_tokens import COLORS, FONTS, SPACING


class ProjectsView(ctk.CTkFrame):
    """Projects = accepted quotes. Shows each accepted quote as a project
    card with its scheduled jobs and total value."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["surface_primary"], **kwargs)

        self.crm_service = CRMService()
        self.quote_repo = QuoteRepository()
        self.sched_service = ScheduledJobService()
        self._filter_var = ctk.StringVar(value="Accepted")

        self._build()
        self._load()

    def _build(self):
        scroll_host = ctk.CTkFrame(self, fg_color=COLORS["surface_primary"])
        scroll_host.pack(fill="both", expand=True)

        hdr = ctk.CTkFrame(scroll_host, fg_color="transparent")
        hdr.pack(fill="x", padx=SPACING["xxl"], pady=(SPACING["xxl"], SPACING["lg"]))

        ctk.CTkLabel(hdr, text="Projects", font=FONTS["title_lg"],
                     text_color=COLORS["text_primary"]).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Accepted quotes become projects. Track progress and scheduling here.",
                     font=FONTS["body_md"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(SPACING["sm"], 0))

        filter_row = ctk.CTkFrame(scroll_host, fg_color="transparent")
        filter_row.pack(fill="x", padx=SPACING["xxl"], pady=(0, SPACING["md"]))

        ctk.CTkLabel(filter_row, text="Show:", font=FONTS["body_sm"],
                     text_color=COLORS["text_secondary"]).pack(side="left")
        for label in ("Accepted", "All", "Issued"):
            ctk.CTkRadioButton(
                filter_row, text=label, variable=self._filter_var, value=label,
                font=FONTS["body_sm"], text_color=COLORS["text_primary"],
                fg_color=COLORS["accent_primary"], command=self._load,
            ).pack(side="left", padx=(SPACING["lg"], 0))

        self._scroll = ctk.CTkScrollableFrame(scroll_host, fg_color=COLORS["surface_primary"])
        self._scroll.pack(fill="both", expand=True, padx=SPACING["xxl"], pady=(0, SPACING["xxl"]))

    def _load(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        status_filter = self._filter_var.get()
        all_quotes = self.quote_repo.list_all()
        if status_filter != "All":
            all_quotes = [q for q in all_quotes if q.status == status_filter]

        customers = {}
        for q in all_quotes:
            if q.customer_id and q.customer_id not in customers:
                try:
                    customers[q.customer_id] = self.crm_service.get_customer(q.customer_id)
                except Exception:
                    customers[q.customer_id] = None

        if not all_quotes:
            ctk.CTkLabel(self._scroll, text="No projects yet. Accept a quote to start a project.",
                         font=FONTS["body_md"], text_color=COLORS["text_tertiary"]).pack(pady=SPACING["xxl"])
            return

        for q in all_quotes:
            cust = customers.get(q.customer_id)
            cust_name = cust.name if cust else "Unknown"
            self._project_card(q, cust_name)

    def _project_card(self, quote, customer_name):
        card = ctk.CTkFrame(self._scroll, fg_color=COLORS["surface_secondary"],
                            border_width=1, border_color=COLORS["border_default"], corner_radius=8)
        card.pack(fill="x", pady=(0, SPACING["md"]))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=SPACING["lg"], pady=SPACING["lg"])

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(top, text=quote.quote_number or "DRAFT", font=FONTS["heading_sm"],
                     text_color=COLORS["text_primary"]).pack(side="left")

        sell = format_money(quote.total_minor or 0, quote.currency or "ZAR")
        ctk.CTkLabel(top, text=sell, font=FONTS["heading_sm"],
                     text_color=COLORS["accent_primary"]).pack(side="right")

        status_color = COLORS["success"] if quote.status == "Accepted" else COLORS["text_secondary"]
        badge = ctk.CTkFrame(top, fg_color=status_color, corner_radius=4)
        badge.pack(side="right", padx=SPACING["md"])
        ctk.CTkLabel(badge, text=quote.status, font=FONTS["label_sm"],
                     text_color="#ffffff").pack(padx=8, pady=2)

        meta = f"{customer_name}  ·  {(quote.issue_date or (quote.created_at or '')[:10] or '—')}"
        ctk.CTkLabel(inner, text=meta, font=FONTS["body_sm"],
                     text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w", pady=(SPACING["xs"], 0))

        scheduled = self.sched_service.list_for_customer(quote.customer_id) if quote.customer_id else []
        linked = [j for j in scheduled if j.quote_id == quote.id]
        if linked:
            sched_text = "  ".join(f"📅 {j.title} ({j.start_date[:10]})" for j in linked[:3])
            ctk.CTkLabel(inner, text=sched_text, font=FONTS["body_sm"],
                         text_color=COLORS["accent_primary"], anchor="w").pack(anchor="w", pady=(SPACING["xs"], 0))
