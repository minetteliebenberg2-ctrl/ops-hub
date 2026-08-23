import customtkinter as ctk
from tkinter import messagebox

from core.crm_service import CRMService
from core.job_cost_item import JobCostItemRepository
from core.quote_pdf import format_money
from core.quote_repository import QuoteRepository
from core.quote_service import QuoteService
from core.structure_quote import quote_structure
from gui.design_tokens import COLORS, FONTS, SPACING

_FULL_STRUCTURE_MAP = {
    "Cantilever - Single": ("Cantilever", "Single"),
    "Cantilever - Double": ("Cantilever", "Double"),
    "Cantilever - Triple": ("Cantilever", "Triple"),
    "4 Post - Single": ("4 Post", "Single"),
    "4 Post - Double": ("4 Post", "Double"),
    "4 Post - Triple": ("4 Post", "Triple"),
}

_NET_ONLY_MAP = {
    "New Net - Single": ("Cantilever", "Single"),
    "New Net - Double": ("Cantilever", "Double"),
    "New Net - Triple": ("Cantilever", "Triple"),
}

_COL_HEADERS = ["Quote", "Customer", "Items", "Sell (R)", "Materials", "Labour", "Netting", "Cable", "GP%"]
_COL_WIDTHS = [100, 170, 40, 100, 80, 70, 80, 70, 60]

_DEFAULT_GP = 0.45


class JobKPIWindow(ctk.CTkToplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Job KPI Overview")
        self.geometry("960x620")
        self.minsize(900, 400)
        self.configure(fg_color=COLORS["surface_primary"])

        self.quote_service = QuoteService()
        self.quote_repo = QuoteRepository()
        self.crm_service = CRMService()
        self.job_cost_repo = JobCostItemRepository()

        self._build()
        self._load()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color=COLORS["surface_secondary"],
                           border_width=1, border_color=COLORS["border_default"])
        top.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(
            top, text="Job KPI Overview",
            font=FONTS["heading_md"], text_color=COLORS["text_primary"],
        ).pack(side="left", padx=SPACING["xxl"], pady=SPACING["lg"])

        ctk.CTkButton(
            top, text="Refresh", font=FONTS["label_sm"],
            fg_color=COLORS["accent_primary"], text_color=COLORS["text_inverse"],
            height=28, width=80, command=self._load,
        ).pack(side="right", padx=SPACING["xxl"], pady=SPACING["lg"])

        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.pack(fill="x", padx=SPACING["xxl"], pady=(SPACING["md"], 0))

        ctk.CTkLabel(filter_row, text="Show:", font=FONTS["label"],
                     text_color=COLORS["text_secondary"]).pack(side="left")

        self._filter_var = ctk.StringVar(value="Accepted")
        for label in ("All", "Draft", "Accepted", "Issued"):
            ctk.CTkRadioButton(
                filter_row, text=label, variable=self._filter_var, value=label,
                font=FONTS["body_sm"], text_color=COLORS["text_primary"],
                fg_color=COLORS["accent_primary"], command=self._load,
            ).pack(side="left", padx=(SPACING["lg"], 0))

        hdr_frame = ctk.CTkFrame(self, fg_color=COLORS["accent_primary"], corner_radius=6)
        hdr_frame.pack(fill="x", padx=SPACING["xl"], pady=(SPACING["md"], 0))

        for i, (text, width) in enumerate(zip(_COL_HEADERS, _COL_WIDTHS)):
            ctk.CTkLabel(
                hdr_frame, text=text, width=width,
                font=FONTS["label_sm"], text_color="#ffffff",
                anchor="w" if i < 3 else "e",
            ).pack(side="left", padx=4, pady=8)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["surface_primary"])
        self._scroll.pack(fill="both", expand=True, padx=SPACING["xl"], pady=(0, SPACING["md"]))

        self._footer = ctk.CTkFrame(self, fg_color=COLORS["surface_secondary"],
                                     border_width=1, border_color=COLORS["border_default"])
        self._footer.pack(fill="x", padx=SPACING["xl"], pady=(0, SPACING["lg"]))
        self._summary_label = ctk.CTkLabel(
            self._footer, text="", font=FONTS["label"],
            text_color=COLORS["text_primary"],
        )
        self._summary_label.pack(side="left", padx=SPACING["xxl"], pady=SPACING["md"])

    def _estimate_costs(self, items):
        materials = 0.0
        labour = 0.0
        netting = 0.0
        cable = 0.0

        for item in items:
            st = getattr(item, "structure_type", "") or ""
            qty = item.quantity or 1

            full_key = _FULL_STRUCTURE_MAP.get(st)
            if full_key:
                try:
                    r = quote_structure(full_key[0], full_key[1])
                    materials += (r["materials"] + r["paint"]) * qty
                    labour += r["labour"] * qty
                    if r.get("netting"):
                        netting += (r["netting"]["total"] - r["netting"].get("cable", {}).get("total", 0)) * qty
                        cable += r["netting"].get("cable", {}).get("total", 0) * qty
                except Exception:
                    pass
                continue

            net_key = _NET_ONLY_MAP.get(st)
            if net_key:
                try:
                    r = quote_structure(net_key[0], net_key[1], include_structure=False)
                    if r.get("netting"):
                        netting += (r["netting"]["total"] - r["netting"].get("cable", {}).get("total", 0)) * qty
                        cable += r["netting"].get("cable", {}).get("total", 0) * qty
                except Exception:
                    pass
                continue

            cost_entry = self._cost_map.get(st)
            if cost_entry:
                bucket, gp_frac = cost_entry
                sell_per_unit = (item.unit_price_minor or 0) / 100
                cost_per_unit = sell_per_unit * (1 - gp_frac)
                if bucket == "cable":
                    cable += cost_per_unit * qty
                elif bucket == "netting":
                    netting += cost_per_unit * qty
                elif bucket == "materials":
                    materials += cost_per_unit * qty
                else:
                    labour += cost_per_unit * qty

        return materials, labour, netting, cable

    def _load(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        self._cost_map = self.job_cost_repo.cost_map()
        status_filter = self._filter_var.get()
        try:
            all_quotes = self.quote_repo.list_all()
        except Exception as exc:
            messagebox.showerror("KPI", f"Could not load quotes: {exc}", parent=self)
            return

        quotes = [q for q in all_quotes if status_filter == "All" or q.status == status_filter]

        customers = {}
        t_sell = 0.0
        t_mat = 0.0
        t_lab = 0.0
        t_net = 0.0
        t_cab = 0.0
        total_items = 0
        row_count = 0

        for quote in quotes:
            if quote.customer_id not in customers:
                try:
                    customers[quote.customer_id] = self.crm_service.get_customer(quote.customer_id)
                except Exception:
                    customers[quote.customer_id] = None
            customer = customers[quote.customer_id]
            customer_name = customer.name if customer else "Unknown"

            try:
                items = self.quote_service.list_line_items(quote.id)
            except Exception:
                items = []

            sell = (quote.total_minor or 0) / 100
            if sell == 0:
                for item in items:
                    qty = item.quantity or 1
                    unit_price = (item.unit_price_minor or 0) / 100
                    sell += unit_price * qty

            mat, lab, net, cab = self._estimate_costs(items)
            cost = mat + lab + net + cab
            gp_pct = ((sell - cost) / sell * 100) if sell > 0 and cost > 0 else 0.0

            item_count = len(items)
            t_sell += sell
            t_mat += mat
            t_lab += lab
            t_net += net
            t_cab += cab
            total_items += item_count
            row_count += 1

            self._add_row(
                quote.quote_number or "DRAFT",
                customer_name,
                item_count,
                sell, mat, lab, net, cab,
                gp_pct,
                row_count,
            )

        total_cost = t_mat + t_lab + t_net + t_cab
        overall_gp = ((t_sell - total_cost) / t_sell * 100) if t_sell > 0 and total_cost > 0 else 0.0
        self._summary_label.configure(
            text=(
                f"  {row_count} quotes  |  "
                f"{total_items} items  |  "
                f"Sell: R {t_sell:,.2f}  |  "
                f"Cost: R {total_cost:,.2f}  |  "
                f"GP: {overall_gp:.1f}%"
            )
        )

    def _add_row(self, quote_num, customer, item_count, sell, mat, lab, net, cab, gp_pct, row_idx):
        bg = COLORS["surface_primary"] if row_idx % 2 == 0 else COLORS["surface_secondary"]
        row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0)
        row.pack(fill="x", pady=0)

        if gp_pct >= 40:
            gp_color = COLORS["success"]
        elif gp_pct >= 30:
            gp_color = COLORS["warning"]
        elif gp_pct > 0:
            gp_color = COLORS["danger"]
        else:
            gp_color = COLORS["text_tertiary"]

        gp_text = f"{gp_pct:.0f}%" if gp_pct > 0 else "—"

        def _fmt(v):
            return f"{v:,.0f}" if v > 0 else "—"

        cells = [
            (quote_num, _COL_WIDTHS[0], "w", COLORS["text_primary"]),
            (customer, _COL_WIDTHS[1], "w", COLORS["text_primary"]),
            (str(item_count), _COL_WIDTHS[2], "e", COLORS["text_primary"]),
            (f"{sell:,.2f}", _COL_WIDTHS[3], "e", COLORS["text_primary"]),
            (_fmt(mat), _COL_WIDTHS[4], "e", COLORS["text_secondary"]),
            (_fmt(lab), _COL_WIDTHS[5], "e", COLORS["text_secondary"]),
            (_fmt(net), _COL_WIDTHS[6], "e", COLORS["text_secondary"]),
            (_fmt(cab), _COL_WIDTHS[7], "e", COLORS["text_secondary"]),
            (gp_text, _COL_WIDTHS[8], "e", gp_color),
        ]

        for text, width, anchor, color in cells:
            ctk.CTkLabel(
                row, text=text, width=width,
                font=FONTS["body_sm"], text_color=color,
                anchor=anchor,
            ).pack(side="left", padx=4, pady=5)
