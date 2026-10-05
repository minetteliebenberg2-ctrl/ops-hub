"""Money Owing module — customer ageing table + bank payment matching."""

import customtkinter as ctk
from tkinter import messagebox, ttk

from core.database import database
from core.money_owing import MoneyOwingService, BUCKETS
from gui.styles import COLORS


def _fmt(minor):
    """Format cents as Rands."""
    return f"R{minor / 100:,.2f}"


class MoneyOwingModuleWindow(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)
        self.service = MoneyOwingService(db=database)
        self._build_ui()
        self._refresh()

    # ----------------------------------------------------------
    # UI layout
    # ----------------------------------------------------------

    def _build_ui(self):
        # Header
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(top, text="Money Owing",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Refresh", width=80,
                      command=self._refresh).pack(side="right", padx=5)

        # Two panes side by side
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=5)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        # --- LEFT: Ageing table ---
        left = ctk.CTkFrame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="Customer Ageing",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        age_cols = ("customer", "current", "d30", "d60", "d90", "d90p", "total")
        self.age_tree = ttk.Treeview(left, columns=age_cols,
                                     show="headings", selectmode="browse")
        for cid, text, w in [
            ("customer", "Customer", 180),
            ("current", "Current", 100), ("d30", "1-30", 100),
            ("d60", "31-60", 100), ("d90", "61-90", 100),
            ("d90p", "90+", 100), ("total", "Total", 110),
        ]:
            self.age_tree.heading(cid, text=text)
            anchor = "e" if cid != "customer" else "w"
            self.age_tree.column(cid, width=w, anchor=anchor)

        self.age_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        age_scroll = ttk.Scrollbar(left, orient="vertical",
                                   command=self.age_tree.yview)
        self.age_tree.configure(yscrollcommand=age_scroll.set)
        age_scroll.grid(row=1, column=1, sticky="ns")
        self.age_tree.bind("<Double-1>", self._on_customer_dblclick)

        # Totals row label
        self._age_total = ctk.CTkLabel(left, text="",
                                       font=ctk.CTkFont(size=12, weight="bold"))
        self._age_total.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 8))

        # Invoice detail below ageing
        ctk.CTkLabel(left, text="Open Invoices (double-click customer above)",
                     font=ctk.CTkFont(size=12)).grid(
            row=3, column=0, sticky="w", padx=10, pady=(4, 2))

        inv_cols = ("number", "date", "total", "paid", "balance", "overdue")
        self.inv_tree = ttk.Treeview(left, columns=inv_cols,
                                     show="headings", selectmode="browse",
                                     height=6)
        for cid, text, w in [
            ("number", "Invoice #", 140), ("date", "Date", 100),
            ("total", "Total", 100), ("paid", "Paid", 100),
            ("balance", "Balance", 100), ("overdue", "Days", 60),
        ]:
            self.inv_tree.heading(cid, text=text)
            anchor = "e" if cid not in ("number", "date") else "w"
            self.inv_tree.column(cid, width=w, anchor=anchor)
        self.inv_tree.grid(row=4, column=0, columnspan=2,
                           sticky="nsew", padx=5, pady=(0, 5))

        # --- RIGHT: Bank credit matching ---
        right = ctk.CTkFrame(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(right, text="Unmatched Bank Credits",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        cr_cols = ("date", "description", "amount", "suggestion")
        self.cr_tree = ttk.Treeview(right, columns=cr_cols,
                                    show="headings", selectmode="browse")
        for cid, text, w in [
            ("date", "Date", 90), ("description", "Description", 200),
            ("amount", "Amount", 100), ("suggestion", "Suggested Match", 180),
        ]:
            self.cr_tree.heading(cid, text=text)
            anchor = "e" if cid == "amount" else "w"
            self.cr_tree.column(cid, width=w, anchor=anchor)
        self.cr_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        cr_scroll = ttk.Scrollbar(right, orient="vertical",
                                  command=self.cr_tree.yview)
        self.cr_tree.configure(yscrollcommand=cr_scroll.set)
        cr_scroll.grid(row=1, column=1, sticky="ns")

        # Match / Unmatch buttons
        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 8))
        ctk.CTkButton(btn_row, text="Match to Invoice...", width=140,
                      fg_color="#21A94D",
                      command=self._match_selected).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="Unmatch Payment", width=130,
                      fg_color="#CC3333",
                      command=self._unmatch_selected).pack(side="left", padx=5)

        # Store credit data for selection
        self._credits = []
        self._ageing = []

    # ----------------------------------------------------------
    # Data refresh
    # ----------------------------------------------------------

    def _refresh(self):
        # Ageing
        for item in self.age_tree.get_children():
            self.age_tree.delete(item)
        for item in self.inv_tree.get_children():
            self.inv_tree.delete(item)

        self._ageing = self.service.ageing_by_customer()
        grand = [0] * 5
        grand_total = 0
        for entry in self._ageing:
            b = entry["buckets"]
            self.age_tree.insert("", "end", iid=entry["customer_id"],
                                 values=(
                                     entry["customer"],
                                     _fmt(b[0]), _fmt(b[1]), _fmt(b[2]),
                                     _fmt(b[3]), _fmt(b[4]),
                                     _fmt(entry["total"]),
                                 ))
            for i in range(5):
                grand[i] += b[i]
            grand_total += entry["total"]

        self._age_total.configure(
            text=f"Total outstanding: {_fmt(grand_total)}"
            if grand_total else "No outstanding invoices")

        # Credits
        for item in self.cr_tree.get_children():
            self.cr_tree.delete(item)

        self._credits = self.service.unmatched_credits()
        for i, cr in enumerate(self._credits):
            suggestion = self.service.suggest(cr)
            sug_text = suggestion["number"] if suggestion else ""
            self.cr_tree.insert("", "end", iid=str(i),
                                values=(
                                    cr["date"], cr["description"][:40],
                                    _fmt(cr["amount_minor"]), sug_text,
                                ))

    # ----------------------------------------------------------
    # Customer drill-down
    # ----------------------------------------------------------

    def _on_customer_dblclick(self, _event):
        sel = self.age_tree.selection()
        if not sel:
            return
        customer_id = sel[0]
        for item in self.inv_tree.get_children():
            self.inv_tree.delete(item)

        invoices = self.service.invoices_for(customer_id)
        for inv in invoices:
            self.inv_tree.insert("", "end", values=(
                inv["number"], inv["issue_date"],
                _fmt(inv["total_minor"]), _fmt(inv["paid_minor"]),
                _fmt(inv["balance_minor"]), inv["days_overdue"],
            ))

    # ----------------------------------------------------------
    # Match a bank credit to one or more invoices
    # ----------------------------------------------------------

    def _match_selected(self):
        sel = self.cr_tree.selection()
        if not sel:
            messagebox.showinfo("Match", "Select a bank credit first.",
                                parent=self.winfo_toplevel())
            return
        idx = int(sel[0])
        credit = self._credits[idx]

        # Open match dialog
        MatchDialog(self.winfo_toplevel(), self.service, credit,
                    on_matched=self._refresh)

    def _unmatch_selected(self):
        """Unmatch: find the payment linked to this credit and reverse it."""
        sel = self.cr_tree.selection()
        if not sel:
            messagebox.showinfo("Unmatch", "Select a matched credit first.",
                                parent=self.winfo_toplevel())
            return

        # This only works on matched credits — for now show the payments
        # list from the service and let her pick
        payments = self.service.payments.list_payments()
        if not payments:
            messagebox.showinfo("Unmatch", "No matched payments to undo.",
                                parent=self.winfo_toplevel())
            return

        UnmatchDialog(self.winfo_toplevel(), self.service,
                      on_unmatched=self._refresh)


class MatchDialog(ctk.CTkToplevel):
    """Pick invoice(s) and allocate a bank credit."""

    def __init__(self, parent, service, credit, on_matched=None):
        super().__init__(parent)
        self.title("Match Bank Credit to Invoice")
        self.geometry("700x500")
        self.service = service
        self.credit = credit
        self.on_matched = on_matched
        self._splits = []  # (document_id, amount_minor, customer_id)

        self._build_ui()
        self._force_front()

    def _force_front(self):
        self.lift()
        self.focus_force()
        self.after(150, lambda: self.attributes("-topmost", True))
        self.after(350, lambda: self.attributes("-topmost", False))

    def _build_ui(self):
        # Credit info
        info = ctk.CTkFrame(self)
        info.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(info, text=f"Bank Credit: {self.credit['date']}  "
                     f"{self.credit['description']}  "
                     f"{_fmt(self.credit['amount_minor'])}",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=5, pady=5)

        # Open invoices list
        ctk.CTkLabel(self, text="Open Invoices — tick to allocate:",
                     font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=15, pady=(5, 2))

        inv_frame = ctk.CTkFrame(self)
        inv_frame.pack(fill="both", expand=True, padx=10, pady=5)
        inv_frame.grid_columnconfigure(0, weight=1)
        inv_frame.grid_rowconfigure(0, weight=1)

        inv_cols = ("select", "customer", "number", "balance", "allocate")
        self.inv_tree = ttk.Treeview(inv_frame, columns=inv_cols,
                                     show="headings", selectmode="browse")
        for cid, text, w in [
            ("select", "  ", 30), ("customer", "Customer", 160),
            ("number", "Invoice #", 140), ("balance", "Balance", 100),
            ("allocate", "Allocate", 100),
        ]:
            self.inv_tree.heading(cid, text=text)
            anchor = "e" if cid in ("balance", "allocate") else "w"
            self.inv_tree.column(cid, width=w, anchor=anchor)
        self.inv_tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(inv_frame, orient="vertical",
                                command=self.inv_tree.yview)
        self.inv_tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")
        self.inv_tree.bind("<Double-1>", self._toggle_invoice)

        self._invoices = self.service.open_invoices()
        # Sort suggestion first
        suggestion = self.service.suggest(self.credit)
        if suggestion:
            sug_id = suggestion["document_id"]
            self._invoices.sort(
                key=lambda x: (0 if x["document_id"] == sug_id else 1,
                               x["customer"]))

        self._selected = {}  # document_id -> amount_minor
        for inv in self._invoices:
            tag = "(*)" if (suggestion and
                            inv["document_id"] == suggestion["document_id"]) else ""
            self.inv_tree.insert("", "end", iid=inv["document_id"],
                                 values=(
                                     tag, inv["customer"], inv["number"],
                                     _fmt(inv["balance_minor"]), "",
                                 ))

        # Remaining label + confirm
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=10, pady=(5, 10))
        self._remaining = ctk.CTkLabel(bottom, text=f"Remaining: "
                                       f"{_fmt(self.credit['amount_minor'])}",
                                       font=ctk.CTkFont(size=12))
        self._remaining.pack(side="left", padx=5)
        ctk.CTkButton(bottom, text="Confirm Match", fg_color="#21A94D",
                      command=self._confirm).pack(side="right", padx=5)
        ctk.CTkButton(bottom, text="Cancel",
                      command=self.destroy).pack(side="right", padx=5)

    def _toggle_invoice(self, _event):
        sel = self.inv_tree.selection()
        if not sel:
            return
        doc_id = sel[0]
        inv = next(i for i in self._invoices if i["document_id"] == doc_id)

        if doc_id in self._selected:
            # Deselect
            del self._selected[doc_id]
            self.inv_tree.set(doc_id, "select", "")
            self.inv_tree.set(doc_id, "allocate", "")
        else:
            # Select — allocate up to remaining
            allocated_so_far = sum(self._selected.values())
            remaining = self.credit["amount_minor"] - allocated_so_far
            alloc = min(inv["balance_minor"], remaining)
            if alloc <= 0:
                messagebox.showinfo("Match", "No remaining credit to allocate.",
                                    parent=self)
                return
            self._selected[doc_id] = alloc
            self.inv_tree.set(doc_id, "select", ">>")
            self.inv_tree.set(doc_id, "allocate", _fmt(alloc))

        # Update remaining
        allocated = sum(self._selected.values())
        rem = self.credit["amount_minor"] - allocated
        self._remaining.configure(text=f"Remaining: {_fmt(rem)}")

    def _confirm(self):
        if not self._selected:
            messagebox.showinfo("Match", "Double-click at least one invoice.",
                                parent=self)
            return

        # Find customer from first selected invoice
        first_doc_id = next(iter(self._selected))
        inv = next(i for i in self._invoices
                   if i["document_id"] == first_doc_id)
        customer_id = inv["customer_id"]

        splits = list(self._selected.items())
        try:
            self.service.match(self.credit, customer_id, splits)
        except Exception as e:
            messagebox.showerror("Match Error", str(e), parent=self)
            return

        allocated = sum(self._selected.values())
        messagebox.showinfo(
            "Matched",
            f"Payment of {_fmt(allocated)} matched to "
            f"{len(splits)} invoice(s).",
            parent=self)
        if self.on_matched:
            self.on_matched()
        self.destroy()


class UnmatchDialog(ctk.CTkToplevel):
    """List matched payments and allow reversal."""

    def __init__(self, parent, service, on_unmatched=None):
        super().__init__(parent)
        self.title("Unmatch Payment")
        self.geometry("600x400")
        self.service = service
        self.on_unmatched = on_unmatched

        self._build_ui()
        self._force_front()

    def _force_front(self):
        self.lift()
        self.focus_force()
        self.after(150, lambda: self.attributes("-topmost", True))
        self.after(350, lambda: self.attributes("-topmost", False))

    def _build_ui(self):
        ctk.CTkLabel(self, text="Matched Payments — double-click to unmatch",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=10, pady=10)

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        cols = ("date", "reference", "amount", "customer")
        self.tree = ttk.Treeview(frame, columns=cols,
                                 show="headings", selectmode="browse")
        for cid, text, w in [
            ("date", "Date", 100), ("reference", "Reference", 200),
            ("amount", "Amount", 120), ("customer", "Customer", 160),
        ]:
            self.tree.heading(cid, text=text)
            anchor = "e" if cid == "amount" else "w"
            self.tree.column(cid, width=w, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky="nsew")

        self._payments = self.service.payments.list_payments()
        names = self.service._customer_names()
        for p in self._payments:
            self.tree.insert("", "end", iid=p.id, values=(
                p.date, p.reference or "",
                _fmt(p.amount_minor),
                names.get(p.customer_id, "Unknown"),
            ))
        self.tree.bind("<Double-1>", self._on_unmatch)

        ctk.CTkButton(self, text="Close",
                      command=self.destroy).pack(pady=10)

    def _on_unmatch(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        pid = sel[0]
        payment = next((p for p in self._payments if p.id == pid), None)
        if not payment:
            return

        if not messagebox.askyesno(
            "Unmatch",
            f"Reverse this payment of {_fmt(payment.amount_minor)}?\n"
            f"({payment.reference})",
            parent=self
        ):
            return

        try:
            self.service.unmatch(pid)
        except Exception as e:
            messagebox.showerror("Unmatch Error", str(e), parent=self)
            return

        self.tree.delete(pid)
        messagebox.showinfo("Unmatched", "Payment reversed.", parent=self)
        if self.on_unmatched:
            self.on_unmatched()
