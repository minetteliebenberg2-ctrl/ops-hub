import customtkinter as ctk
from tkinter import messagebox, ttk

from core.database import database
from core.job_card_repository import JobCardRepository
from core.job_cost_allocation import (
    JobCostAllocation, JobCostAllocationRepository, INCOME, EXPENSE,
)
from core.ledger_repository import LedgerTransactionRepository
from core.crm_repository import AddressRepository, CustomerRepository, SiteRepository
from core.crm_service import CRMService
from gui.styles import COLORS


class JobCostingModuleWindow(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)

        self.job_card_repo = JobCardRepository(db=database)
        self.allocation_repo = JobCostAllocationRepository(db=database)
        self.ledger_repo = LedgerTransactionRepository(db=database)
        self.customer_repo = CustomerRepository(db=database)

        self._build_ui()
        self._refresh_jobs()

    def _build_ui(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(top, text="Job Costing", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Refresh", width=80, command=self._refresh_jobs).pack(side="right", padx=5)
        ctk.CTkButton(top, text="+ New Job", width=100, command=self._new_job).pack(side="right", padx=5)

        pane = ctk.CTkFrame(self)
        pane.pack(fill="both", expand=True, padx=10, pady=5)
        pane.grid_columnconfigure(0, weight=1)
        pane.grid_rowconfigure(0, weight=1)

        cols = ("job_number", "customer", "po", "status", "revenue", "costs", "gp", "gp_pct")
        self.tree = ttk.Treeview(pane, columns=cols, show="headings", selectmode="browse")
        for cid, text, w in [
            ("job_number", "Job #", 120), ("customer", "Customer", 180),
            ("po", "PO", 80), ("status", "Status", 70),
            ("revenue", "Revenue", 100), ("costs", "Costs", 100),
            ("gp", "GP", 100), ("gp_pct", "GP%", 60),
        ]:
            self.tree.heading(cid, text=text)
            anchor = "e" if cid in ("revenue", "costs", "gp", "gp_pct") else "w"
            self.tree.column(cid, width=w, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(pane, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self._on_job_double_click)

        summary = ctk.CTkFrame(self)
        summary.pack(fill="x", padx=10, pady=(0, 10))
        self._summary_label = ctk.CTkLabel(summary, text="", font=ctk.CTkFont(size=12))
        self._summary_label.pack(side="left", padx=5)

    def _refresh_jobs(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        jobs = self.job_card_repo.list_all()
        summaries = self.allocation_repo.summary_all_jobs()

        customers = {}
        total_rev = 0
        total_cost = 0

        for job in jobs:
            if job.customer_id not in customers:
                cust = self.customer_repo.get(job.customer_id)
                customers[job.customer_id] = cust.name if cust else "Unknown"

            s = summaries.get(job.id, {"income": 0, "expense": 0})
            rev = s["income"]
            cost = s["expense"]
            gp = rev - cost
            gp_pct = f"{gp / rev * 100:.0f}%" if rev > 0 else "-"

            total_rev += rev
            total_cost += cost

            self.tree.insert("", "end", iid=job.id, values=(
                job.job_card_number,
                customers[job.customer_id],
                job.purchase_order or "-",
                job.status,
                f"R{rev / 100:,.2f}",
                f"R{cost / 100:,.2f}",
                f"R{gp / 100:,.2f}",
                gp_pct,
            ))

        total_gp = total_rev - total_cost
        total_pct = f"{total_gp / total_rev * 100:.0f}%" if total_rev > 0 else "-"
        self._summary_label.configure(
            text=f"Total:  Revenue R{total_rev / 100:,.2f}  |  "
                 f"Costs R{total_cost / 100:,.2f}  |  "
                 f"GP R{total_gp / 100:,.2f} ({total_pct})"
        )

    def _new_job(self):
        """Jobs used to be created from the Quotes/CRM job-card buttons.
        Those were removed when Ops Hub went generic, so Job Costing
        owns the only remaining way to open a job to cost against."""

        NewJobDialog(
            self.winfo_toplevel(), self.job_card_repo, self.customer_repo,
            on_saved=self._refresh_jobs,
        )

    def _on_job_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        job_id = sel[0]
        job = self.job_card_repo.get(job_id)
        if job:
            JobCostDetailWindow(
                self.winfo_toplevel(), job,
                self.allocation_repo, self.ledger_repo,
                self.customer_repo,
                on_change=self._refresh_jobs,
            )


class JobCostDetailWindow(ctk.CTkToplevel):

    def __init__(self, master, job, allocation_repo, ledger_repo, customer_repo, on_change=None):
        super().__init__(master)
        self.job = job
        self.allocation_repo = allocation_repo
        self.ledger_repo = ledger_repo
        self.customer_repo = customer_repo
        self.on_change = on_change

        cust = customer_repo.get(job.customer_id)
        cust_name = cust.name if cust else "Unknown"
        self.title(f"Job Costing — {job.job_card_number} ({cust_name})")
        self.geometry("900x600")
        self.lift()
        self.focus_force()

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(header, text=f"{self.job.job_card_number}", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        if self.job.purchase_order:
            ctk.CTkLabel(header, text=f"PO: {self.job.purchase_order}", font=ctk.CTkFont(size=14)).pack(side="left", padx=15)

        btn_row = ctk.CTkFrame(self)
        btn_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(btn_row, text="+ Add Revenue", width=120, fg_color="#21A94D",
                       command=self._add_revenue).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="+ Add Cost", width=120,
                       command=self._add_cost).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="Allocate from Bank", width=140,
                       command=self._allocate_from_bank).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="Delete Selected", width=120, fg_color="#CC3333",
                       command=self._delete_selected).pack(side="right", padx=2)

        pane = ctk.CTkFrame(self)
        pane.pack(fill="both", expand=True, padx=10, pady=5)
        pane.grid_columnconfigure(0, weight=1)
        pane.grid_rowconfigure(0, weight=1)

        cols = ("type", "date", "description", "bucket", "amount", "notes")
        self.tree = ttk.Treeview(pane, columns=cols, show="headings", selectmode="browse")
        for cid, text, w in [
            ("type", "Type", 70), ("date", "Date", 90), ("description", "Description", 250),
            ("bucket", "Bucket", 90), ("amount", "Amount", 110), ("notes", "Notes", 150),
        ]:
            self.tree.heading(cid, text=text)
            anchor = "e" if cid == "amount" else "w"
            self.tree.column(cid, width=w, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(pane, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        self._summary_frame = ctk.CTkFrame(self)
        self._summary_frame.pack(fill="x", padx=10, pady=(0, 10))
        self._summary_label = ctk.CTkLabel(self._summary_frame, text="", font=ctk.CTkFont(size=13, weight="bold"))
        self._summary_label.pack(side="left", padx=5, pady=5)

    def _refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        self._allocations = self.allocation_repo.list_for_job(self.job.id)
        for a in self._allocations:
            sign = "" if a.allocation_type == INCOME else "-"
            self.tree.insert("", "end", iid=a.id, values=(
                a.allocation_type,
                a.date,
                a.description,
                a.cost_bucket or "-",
                f"{sign}R{abs(a.amount_minor) / 100:,.2f}",
                a.notes,
            ))

        income, expenses = self.allocation_repo.summary_for_job(self.job.id)
        total_cost = sum(expenses.values())
        gp = income - total_cost
        gp_pct = f"{gp / income * 100:.0f}%" if income > 0 else "-"

        parts = [f"Revenue: R{income / 100:,.2f}"]
        for bucket, amt in sorted(expenses.items()):
            parts.append(f"{bucket.title()}: R{amt / 100:,.2f}")
        parts.append(f"Total Cost: R{total_cost / 100:,.2f}")
        parts.append(f"GP: R{gp / 100:,.2f} ({gp_pct})")
        self._summary_label.configure(text="   |   ".join(parts))

    def _add_revenue(self):
        AddAllocationDialog(self, INCOME, self.job, self.allocation_repo, on_saved=self._on_saved)

    def _add_cost(self):
        AddAllocationDialog(self, EXPENSE, self.job, self.allocation_repo, on_saved=self._on_saved)

    def _allocate_from_bank(self):
        BankAllocationDialog(self, self.job, self.allocation_repo, self.ledger_repo, on_saved=self._on_saved)

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Delete Allocation", "Remove this allocation?", parent=self):
            return
        self.allocation_repo.delete(sel[0])
        self._on_saved()

    def _on_saved(self):
        self._refresh()
        if self.on_change:
            self.on_change()


class NewJobDialog(ctk.CTkToplevel):
    """Minimal job opener: pick a customer and one of its sites, then
    give the job a PO and a reference. job_cards.site_id is NOT NULL
    with a foreign key onto customer_sites, so a job always needs a
    real site - when a customer has none, this creates a 'Main Site'
    rather than making her go to CRM and come back."""

    NO_CUSTOMERS = "(no customers - add one in CRM first)"

    def __init__(self, master, job_card_repo, customer_repo, on_saved=None):
        super().__init__(master)
        self.job_card_repo = job_card_repo
        self.customer_repo = customer_repo
        self.on_saved = on_saved
        # Bound to the customer repository's database so the dialog
        # reads and writes the same one the rest of the module does.
        self.crm = CRMService(
            customer_repository=customer_repo,
            site_repository=SiteRepository(db=customer_repo.db),
            address_repository=AddressRepository(db=customer_repo.db),
        )

        self.title("New Job")
        self.geometry("440x340")
        self.lift()
        self.focus_force()

        pad = dict(padx=10, pady=4)

        self._customers = sorted(self.customer_repo.list_all(), key=lambda c: (c.name or "").lower())
        names = [c.name for c in self._customers] or [self.NO_CUSTOMERS]

        ctk.CTkLabel(self, text="Customer:").pack(**pad, anchor="w")
        self._customer = ctk.CTkComboBox(self, values=names, state="readonly", command=self._load_sites)
        self._customer.set(names[0])
        self._customer.pack(fill="x", **pad)

        ctk.CTkLabel(self, text="Site:").pack(**pad, anchor="w")
        self._site = ctk.CTkComboBox(self, values=["Main Site"], state="readonly")
        self._site.pack(fill="x", **pad)

        ctk.CTkLabel(self, text="PO / Order number:").pack(**pad, anchor="w")
        self._po = ctk.CTkEntry(self)
        self._po.pack(fill="x", **pad)

        ctk.CTkLabel(self, text="Reference / notes:").pack(**pad, anchor="w")
        self._notes = ctk.CTkEntry(self)
        self._notes.pack(fill="x", **pad)

        ctk.CTkButton(self, text="Create Job", command=self._save).pack(pady=14)

        self._sites = []
        self._load_sites(self._customer.get())

    # --------------------------------------------------

    def _selected_customer(self):

        return next((c for c in self._customers if c.name == self._customer.get()), None)

    def _load_sites(self, _choice=None):

        customer = self._selected_customer()
        self._sites = self.crm.list_sites(customer.id) if customer else []
        names = [s.name or "(unnamed site)" for s in self._sites] or ["Main Site (will be created)"]
        self._site.configure(values=names)
        self._site.set(names[0])

    def _site_id_for(self, customer):
        """The chosen site's id, creating a default site when the
        customer has none yet."""

        chosen = self._site.get()
        for site in self._sites:
            if (site.name or "(unnamed site)") == chosen:
                return site.id

        site = self.crm.new_site(customer.id)
        site.name = "Main Site"
        # A default site carries no address; SiteRepository.save stores
        # an empty address_id as NULL so the foreign key is satisfied.
        addresses = self.crm.list_addresses(customer.id)
        primary = next((a for a in addresses if getattr(a, "is_primary", False)), None)
        chosen_address = primary or (addresses[0] if addresses else None)
        site.address_id = chosen_address.id if chosen_address else ""
        return self.crm.save_site(site).id

    def _save(self):
        customer = self._selected_customer()
        if customer is None:
            messagebox.showerror(
                "New Job", "Add a customer in CRM first - a job has to belong to one.", parent=self,
            )
            return

        try:
            site_id = self._site_id_for(customer)
            job = self.job_card_repo.create(customer.id, site_id, actor="minette")
            job.purchase_order = self._po.get().strip()
            job.bill_to_name = customer.name
            job.notes = self._notes.get().strip()
            self.job_card_repo.save(job, actor="minette")
        except Exception as error:
            messagebox.showerror("New Job", f"Could not create the job:\n{error}", parent=self)
            return

        self.destroy()
        if self.on_saved:
            self.on_saved()


class AddAllocationDialog(ctk.CTkToplevel):

    def __init__(self, master, alloc_type, job, allocation_repo, on_saved=None):
        super().__init__(master)
        self.alloc_type = alloc_type
        self.job = job
        self.allocation_repo = allocation_repo
        self.on_saved = on_saved

        self.title(f"Add {alloc_type}")
        self.geometry("400x350")
        self.lift()
        self.focus_force()

        from datetime import date
        pad = dict(padx=10, pady=4)

        ctk.CTkLabel(self, text="Date:").pack(**pad, anchor="w")
        self._date = ctk.CTkEntry(self)
        self._date.insert(0, date.today().strftime("%Y-%m-%d"))
        self._date.pack(fill="x", **pad)

        ctk.CTkLabel(self, text="Description:").pack(**pad, anchor="w")
        self._desc = ctk.CTkEntry(self)
        self._desc.pack(fill="x", **pad)

        ctk.CTkLabel(self, text="Amount (R):").pack(**pad, anchor="w")
        self._amount = ctk.CTkEntry(self)
        self._amount.pack(fill="x", **pad)

        if alloc_type == EXPENSE:
            ctk.CTkLabel(self, text="Cost Bucket:").pack(**pad, anchor="w")
            self._bucket = ctk.CTkComboBox(self, values=["labour", "materials", "transport", "other"])
            self._bucket.set("materials")
            self._bucket.pack(fill="x", **pad)
        else:
            self._bucket = None

        ctk.CTkLabel(self, text="Notes:").pack(**pad, anchor="w")
        self._notes = ctk.CTkEntry(self)
        self._notes.pack(fill="x", **pad)

        ctk.CTkButton(self, text="Save", command=self._save).pack(pady=10)

    def _save(self):
        try:
            amount = round(float(self._amount.get()) * 100)
        except ValueError:
            messagebox.showerror("Error", "Enter a valid amount.", parent=self)
            return
        if amount <= 0:
            messagebox.showerror("Error", "Amount must be positive.", parent=self)
            return

        alloc = JobCostAllocation(
            job_card_id=self.job.id,
            allocation_type=self.alloc_type,
            description=self._desc.get().strip(),
            amount_minor=amount,
            cost_bucket=self._bucket.get() if self._bucket else "",
            date=self._date.get().strip(),
            notes=self._notes.get().strip(),
        )
        self.allocation_repo.save(alloc, actor="minette")
        self.destroy()
        if self.on_saved:
            self.on_saved()


class BankAllocationDialog(ctk.CTkToplevel):

    def __init__(self, master, job, allocation_repo, ledger_repo, on_saved=None):
        super().__init__(master)
        self.job = job
        self.allocation_repo = allocation_repo
        self.ledger_repo = ledger_repo
        self.on_saved = on_saved

        self.title(f"Allocate Bank Transactions to {job.job_card_number}")
        self.geometry("800x500")
        self.lift()
        self.focus_force()

        self._build_ui()
        self._load_transactions()

    def _build_ui(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(top, text="Select transactions to allocate:").pack(side="left")

        filter_frame = ctk.CTkFrame(self)
        filter_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(filter_frame, text="Type:").pack(side="left", padx=5)
        self._type_filter = ctk.CTkComboBox(filter_frame, values=["All", "Income", "Expense"], width=100,
                                             command=lambda _: self._load_transactions())
        self._type_filter.set("All")
        self._type_filter.pack(side="left", padx=5)

        ctk.CTkLabel(filter_frame, text="Category:").pack(side="left", padx=5)
        self._category_filter = ctk.CTkComboBox(filter_frame, values=["All"], width=160,
                                                  command=lambda _: self._load_transactions())
        self._category_filter.set("All")
        self._category_filter.pack(side="left", padx=5)

        ctk.CTkLabel(filter_frame, text="Search:").pack(side="left", padx=5)
        self._search = ctk.CTkEntry(filter_frame, width=150)
        self._search.pack(side="left", padx=5)
        ctk.CTkButton(filter_frame, text="Filter", width=60, command=self._load_transactions).pack(side="left", padx=5)

        assign_frame = ctk.CTkFrame(self)
        assign_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(assign_frame, text="Assign as bucket:").pack(side="left", padx=5)
        self._bucket = ctk.CTkComboBox(assign_frame, values=["labour", "materials", "transport", "other"], width=120)
        self._bucket.set("materials")
        self._bucket.pack(side="left", padx=5)
        ctk.CTkLabel(assign_frame, text="(applied to selected transactions when allocated)", font=ctk.CTkFont(size=11)).pack(side="left", padx=5)

        pane = ctk.CTkFrame(self)
        pane.pack(fill="both", expand=True, padx=10, pady=5)
        pane.grid_columnconfigure(0, weight=1)
        pane.grid_rowconfigure(0, weight=1)

        cols = ("date", "description", "amount", "type", "category", "account")
        self.tree = ttk.Treeview(pane, columns=cols, show="headings", selectmode="extended")
        for cid, text, w in [
            ("date", "Date", 90), ("description", "Description", 250),
            ("amount", "Amount", 100), ("type", "Type", 70),
            ("category", "Category", 120), ("account", "Account", 100),
        ]:
            self.tree.heading(cid, text=text)
            anchor = "e" if cid == "amount" else "w"
            self.tree.column(cid, width=w, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(pane, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        btn = ctk.CTkFrame(self)
        btn.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btn, text="Allocate Selected", fg_color="#21A94D",
                       command=self._allocate_selected).pack(side="right", padx=5)
        ctk.CTkButton(btn, text="Cancel", command=self.destroy).pack(side="right", padx=5)

    def _load_transactions(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        filters = {}
        type_val = self._type_filter.get()
        if type_val != "All":
            filters["transaction_type"] = type_val

        category_val = self._category_filter.get()
        if category_val != "All":
            filters["category"] = category_val

        search = self._search.get().strip().lower()

        all_transactions = self.ledger_repo.list_all(filters={})
        categories = sorted({tx.category for tx in all_transactions if tx.category})
        current_cat = self._category_filter.get()
        self._category_filter.configure(values=["All"] + categories)
        if current_cat in (["All"] + categories):
            self._category_filter.set(current_cat)

        transactions = self.ledger_repo.list_all(filters=filters)
        self._tx_map = {}
        for tx in transactions:
            if search and search not in tx.description.lower() and search not in tx.reference.lower():
                continue
            self._tx_map[tx.id] = tx
            self.tree.insert("", "end", iid=tx.id, values=(
                tx.date,
                tx.description,
                f"R{abs(tx.amount_minor) / 100:,.2f}",
                tx.transaction_type,
                tx.category,
                tx.account,
            ))

    def _allocate_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Select at least one transaction.", parent=self)
            return

        bucket = self._bucket.get()
        count = 0
        for tx_id in selected:
            tx = self._tx_map.get(tx_id)
            if not tx:
                continue
            alloc_type = INCOME if tx.transaction_type == "Income" else EXPENSE
            alloc = JobCostAllocation(
                job_card_id=self.job.id,
                ledger_transaction_id=tx.id,
                allocation_type=alloc_type,
                description=tx.description,
                amount_minor=abs(tx.amount_minor),
                cost_bucket=bucket if alloc_type == EXPENSE else "",
                date=tx.date,
                notes=f"From bank: {tx.reference}" if tx.reference else "",
            )
            self.allocation_repo.save(alloc, actor="minette")
            count += 1

        messagebox.showinfo("Allocated", f"{count} transaction(s) allocated to {self.job.job_card_number}.", parent=self)
        self.destroy()
        if self.on_saved:
            self.on_saved()
