"""Native Ops Hub Diagnostics user interface."""

import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from core.diagnostics.models import DiagnosticStatus
from modules.troubleshooter.services import TroubleshooterService, summarize


class TroubleshooterWindow(ctk.CTkFrame):
    columns = ("status", "category", "check", "summary")

    def __init__(self, master):
        super().__init__(master)
        self.service = TroubleshooterService()
        self.results = []
        self.result_by_id = {}
        self.running = False
        self.sort_reverse = {}
        self._build_ui()
        self._update_summary()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Ops Hub Diagnostics", font=("Segoe UI", 24, "bold")).pack(anchor="w", padx=15, pady=(15, 2))
        ctk.CTkLabel(self, text="Checks Ops Hub health safely without changing user data.").pack(anchor="w", padx=15, pady=(0, 12))

        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=15, pady=(0, 10))
        self.buttons = []
        for text, command in (("Run All Checks", self.run_all), ("Run Selected", self.run_selected), ("Export Report", self.export_report), ("Clear Results", self.clear_results), ("Check & Apply Migrations", self.check_and_apply_migrations)):
            button = ctk.CTkButton(toolbar, text=text, command=command, width=130)
            button.pack(side="left", padx=5, pady=8)
            self.buttons.append(button)

        summary = ctk.CTkFrame(self)
        summary.pack(fill="x", padx=15, pady=(0, 10))
        self.summary_label = ctk.CTkLabel(summary, text="")
        self.summary_label.pack(anchor="w", padx=10, pady=6)

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=15)
        self.tree = ttk.Treeview(table_frame, columns=self.columns, show="headings", selectmode="extended", height=11)
        widths = {"status": 85, "category": 120, "check": 190, "summary": 520}
        for column in self.columns:
            self.tree.heading(column, text=column.title(), command=lambda item=column: self.sort_by(item))
            self.tree.column(column, width=widths[column], minwidth=70, stretch=column == "summary")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.show_details)
        self.tree.bind("<Double-1>", self.show_details)

        detail_frame = ctk.CTkFrame(self)
        detail_frame.pack(fill="both", expand=True, padx=15, pady=10)
        ctk.CTkLabel(detail_frame, text="Result details", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=8, pady=(5, 0))
        self.details = ctk.CTkTextbox(detail_frame, height=150, wrap="word")
        self.details.pack(fill="both", expand=True, padx=8, pady=6)
        self.details.configure(state="disabled")
        self.status_label = ctk.CTkLabel(self, text="Ready")
        self.status_label.pack(anchor="w", padx=15, pady=(0, 10))

    def run_all(self):
        self._run(self.service.run_all)

    def run_selected(self):
        check_ids = [self.result_by_id[item].check_id for item in self.tree.selection() if item in self.result_by_id]
        if not check_ids:
            messagebox.showinfo("Run Selected", "Select one or more existing results first.", parent=self.winfo_toplevel())
            return
        self._run(lambda: self.service.run_selected(check_ids))

    def _run(self, operation):
        if self.running:
            return
        self.running = True
        self._set_controls("disabled")
        self.status_label.configure(text="Running diagnostics...")
        self.update_idletasks()
        try:
            self._display_results(operation())
            self.status_label.configure(text="Diagnostics completed")
        except Exception as error:
            self.status_label.configure(text="Diagnostics could not be completed")
            messagebox.showerror("Troubleshooter", f"Diagnostics could not be completed.\n\n{error}", parent=self.winfo_toplevel())
        finally:
            self.running = False
            self._set_controls("normal")

    def _display_results(self, results):
        selected_ids = {self.result_by_id[item].check_id for item in self.tree.selection() if item in self.result_by_id}
        existing = {result.check_id: result for result in self.results}
        existing.update({result.check_id: result for result in results})
        order = [check.check_id for check in self.service.registry.get_checks()]
        self.results = sorted(existing.values(), key=lambda result: order.index(result.check_id) if result.check_id in order else len(order))
        self.tree.delete(*self.tree.get_children())
        self.result_by_id.clear()
        for index, result in enumerate(self.results):
            iid = f"result-{index}"
            self.result_by_id[iid] = result
            self.tree.insert("", "end", iid=iid, values=(result.status.value, result.category, result.name, result.summary))
            if result.check_id in selected_ids:
                self.tree.selection_add(iid)
        self._update_summary()

    def show_details(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        result = self.result_by_id[selection[0]]
        text = (f"Status: {result.status.value}\nCategory: {result.category}\nCheck: {result.name}\n"
                f"Blocking: {'Yes' if result.is_blocking else 'No'}\n\nSummary\n{result.summary}\n\n"
                f"Details\n{result.details}\n\nRecommendation\n{result.recommendation}")
        self.details.configure(state="normal")
        self.details.delete("1.0", tk.END)
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def sort_by(self, column):
        selected = self.tree.selection()
        status_rank = {DiagnosticStatus.FAIL.value: 0, DiagnosticStatus.WARNING.value: 1, DiagnosticStatus.INFO.value: 2, DiagnosticStatus.PASS.value: 3}
        index = self.columns.index(column)
        reverse = self.sort_reverse.get(column, False)
        rows = list(self.tree.get_children())
        rows.sort(key=lambda item: status_rank.get(self.tree.set(item, column), 99) if column == "status" else self.tree.set(item, column).casefold(), reverse=reverse)
        for position, item in enumerate(rows):
            self.tree.move(item, "", position)
        self.tree.selection_set(selected)
        self.sort_reverse[column] = not reverse

    def export_report(self):
        if not self.results:
            messagebox.showinfo("Export Report", "Run diagnostics before exporting a report.", parent=self.winfo_toplevel())
            return
        try:
            path = self.service.export_report(self.results)
            self.status_label.configure(text=f"Report exported: {path.name}")
            messagebox.showinfo("Export Report", f"Report exported to:\n{path}", parent=self.winfo_toplevel())
        except Exception as error:
            messagebox.showerror("Export Report", f"The report could not be exported.\n\n{error}", parent=self.winfo_toplevel())

    def clear_results(self):
        self.results = []
        self.result_by_id.clear()
        self.tree.delete(*self.tree.get_children())
        self.details.configure(state="normal")
        self.details.delete("1.0", tk.END)
        self.details.configure(state="disabled")
        self._update_summary()
        self.status_label.configure(text="Ready")

    def check_and_apply_migrations(self):
        try:
            state = self.service.inspect_migrations()
        except Exception as error:
            messagebox.showerror("Migrations", f"Migration status could not be checked.\n\n{error}", parent=self.winfo_toplevel())
            return
        if not state.pending_versions:
            messagebox.showinfo("Migrations", "The database schema is current; no pending migrations were found.", parent=self.winfo_toplevel())
            return
        if not state.supported:
            messagebox.showerror("Migrations", "The database schema is unsupported or a migration checksum changed.\nResolve this before migrating; no changes were made.", parent=self.winfo_toplevel())
            return
        names = self.service.pending_migration_names(state)
        proceed = messagebox.askyesno(
            "Apply Pending Migrations",
            "Pending migrations were found:\n\n" + "\n".join(names) +
            "\n\nA verified backup will be created first, and migrations will only be "
            "applied if that backup succeeds and verifies. Continue?",
            parent=self.winfo_toplevel(),
        )
        if not proceed:
            self.status_label.configure(text="Migration apply cancelled; no changes were made.")
            return
        self._set_controls("disabled")
        self.status_label.configure(text="Creating a verified backup before migrating...")
        self.update_idletasks()
        try:
            result = self.service.apply_pending_migrations()
        finally:
            self._set_controls("normal")
        if result.success:
            self.status_label.configure(text="Migrations applied successfully.")
            messagebox.showinfo("Migrations Applied", result.message, parent=self.winfo_toplevel())
        else:
            self.status_label.configure(text="Migration apply failed; see details.")
            messagebox.showerror("Migration Failed", result.message, parent=self.winfo_toplevel())

    def _update_summary(self):
        values = summarize(self.results)
        self.summary_label.configure(text=(f"Checks: {values['total']}   Passed: {values['passed']}   Warnings: {values['warnings']}   "
                                           f"Failed: {values['failed']}   Info: {values['informational']}   Blocking: {values['blocking']}"))

    def _set_controls(self, state):
        for button in self.buttons:
            button.configure(state=state)
