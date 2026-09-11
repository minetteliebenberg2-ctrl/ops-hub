"""Annual Compliance module UI — Annual Returns, Payroll, COIDA Tracker."""

from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path

import customtkinter as ctk

from modules.annual_compliance.services import (
    AnnualReturn, AnnualReturnRepository,
    Payslip, PayslipRepository,
)
from core.app_paths import get_project_root


# ── helpers ─────────────────────────────────────────────────────────────────

def _label_val(parent, label: str, value: str, row: int, col_offset: int = 0):
    ctk.CTkLabel(parent, text=label, font=("Segoe UI", 10, "bold"),
                 anchor="w").grid(row=row, column=col_offset, sticky="w", padx=(0, 6), pady=2)
    ctk.CTkLabel(parent, text=value, font=("Segoe UI", 10),
                 anchor="w").grid(row=row, column=col_offset + 1, sticky="w", pady=2)


def _open_file(path: str):
    try:
        os.startfile(path)
    except Exception:
        subprocess.Popen(["explorer", path])


# ── Main window ─────────────────────────────────────────────────────────────

class AnnualComplianceWindow(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._return_repo = AnnualReturnRepository()
        self._slip_repo = PayslipRepository()

        ctk.CTkLabel(self, text="Annual Compliance",
                     font=("Segoe UI", 22, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, sticky="nsew")

        self._build_returns_tab()
        self._build_payroll_tab()
        self._build_coida_tab()

    # ── Tab 1: Annual Returns ────────────────────────────────────────────────

    def _build_returns_tab(self):
        tab = self.tabs.add("Annual Returns")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(tab, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkButton(toolbar, text="+ New Year", width=110,
                      command=self._new_return).pack(side="left", padx=(0, 6))

        self._returns_list = ctk.CTkScrollableFrame(tab)
        self._returns_list.grid(row=1, column=0, sticky="nsew")
        self._returns_list.grid_columnconfigure(0, weight=1)

        self._load_returns()

    def _load_returns(self):
        for w in self._returns_list.winfo_children():
            w.destroy()

        records = self._return_repo.list_all()
        if not records:
            ctk.CTkLabel(self._returns_list, text="No annual returns yet. Click + New Year to add one.",
                         text_color="gray60").grid(row=0, column=0, pady=20)
            return

        headers = ["FY", "Revenue", "Net Income", "Director Earnings", "ROE", "LOGS Status"]
        col_w = [70, 90, 90, 120, 80, 100]
        for c, (h, w) in enumerate(zip(headers, col_w)):
            ctk.CTkLabel(self._returns_list, text=h, font=("Segoe UI", 10, "bold"),
                         width=w, anchor="w").grid(row=0, column=c, sticky="w", padx=4, pady=(0, 4))

        for r, ar in enumerate(records, start=1):
            logs_colors = {"OK": "#21A94D", "EXPIRING": "#F59E0B", "EXPIRED": "#EF4444", "NONE": "gray60"}

            vals = [
                ar.financial_year,
                f"R {ar.revenue:,.0f}",
                f"R {ar.net_income:,.2f}",
                f"R {ar.director_total_earnings:,.0f}",
                ar.roe_status,
                ar.logs_status,
            ]
            for c, (v, w) in enumerate(zip(vals, col_w)):
                color = logs_colors.get(v) if c == 5 else None
                lbl = ctk.CTkLabel(self._returns_list, text=v, width=w, anchor="w",
                                   text_color=color or "gray10")
                lbl.grid(row=r, column=c, sticky="w", padx=4, pady=1)

            btn = ctk.CTkButton(self._returns_list, text="Edit", width=60,
                                command=lambda a=ar: self._edit_return(a))
            btn.grid(row=r, column=len(headers), sticky="w", padx=4, pady=1)

            gen = ctk.CTkButton(self._returns_list, text="Generate Excel", width=110,
                                command=lambda a=ar: self._generate_excel(a))
            gen.grid(row=r, column=len(headers) + 1, sticky="w", padx=4, pady=1)

    def _new_return(self):
        ar = AnnualReturn(id=None, financial_year="", year_end="")
        AnnualReturnDialog(self.winfo_toplevel(), ar, self._return_repo,
                           on_save=self._load_returns)

    def _edit_return(self, ar: AnnualReturn):
        AnnualReturnDialog(self.winfo_toplevel(), ar, self._return_repo,
                           on_save=self._load_returns)

    def _generate_excel(self, ar: AnnualReturn):
        try:
            from tools.export_financial_statements import build_statements
            out = build_statements(ar)
            _open_file(out)
        except Exception as e:
            _ErrorDialog(self.winfo_toplevel(), str(e))

    # ── Tab 2: Payroll ───────────────────────────────────────────────────────

    def _build_payroll_tab(self):
        tab = self.tabs.add("Payroll")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(tab, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkButton(toolbar, text="+ New Payslip", width=120,
                      command=self._new_payslip).pack(side="left", padx=(0, 6))

        self._slips_list = ctk.CTkScrollableFrame(tab)
        self._slips_list.grid(row=1, column=0, sticky="nsew")
        self._slips_list.grid_columnconfigure(0, weight=1)

        self._load_slips()

    def _load_slips(self):
        for w in self._slips_list.winfo_children():
            w.destroy()

        slips = self._slip_repo.list_all()
        if not slips:
            ctk.CTkLabel(self._slips_list, text="No payslips yet. Click + New Payslip to generate one.",
                         text_color="gray60").grid(row=0, column=0, pady=20)
            return

        headers = ["Period", "Employee", "Gross", "UIF (Emp)", "UIF (Emplr)", "Net Pay", "PDF"]
        col_w = [100, 150, 80, 80, 80, 80, 200]
        for c, (h, w) in enumerate(zip(headers, col_w)):
            ctk.CTkLabel(self._slips_list, text=h, font=("Segoe UI", 10, "bold"),
                         width=w, anchor="w").grid(row=0, column=c, sticky="w", padx=4, pady=(0, 4))

        for r, slip in enumerate(slips, start=1):
            vals = [
                slip.period_label,
                slip.employee_name,
                f"R {slip.gross_salary:,.2f}",
                f"R {slip.uif_employee:,.2f}",
                f"R {slip.uif_employer:,.2f}",
                f"R {slip.net_salary:,.2f}",
                Path(slip.pdf_path).name if slip.pdf_path else "—",
            ]
            for c, (v, w) in enumerate(zip(vals, col_w)):
                ctk.CTkLabel(self._slips_list, text=v, width=w, anchor="w",
                             text_color="gray10").grid(row=r, column=c, sticky="w", padx=4, pady=1)

            if slip.pdf_path and Path(slip.pdf_path).is_file():
                ctk.CTkButton(self._slips_list, text="Open PDF", width=80,
                              command=lambda p=slip.pdf_path: _open_file(p)).grid(
                    row=r, column=len(headers), sticky="w", padx=4, pady=1)

    def _new_payslip(self):
        PayslipDialog(self.winfo_toplevel(), self._slip_repo, on_save=self._load_slips)

    # ── Tab 3: COIDA Tracker ─────────────────────────────────────────────────

    def _build_coida_tab(self):
        tab = self.tabs.add("COIDA Tracker")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(1, weight=1)

        records = self._return_repo.list_all()

        if not records:
            ctk.CTkLabel(scroll, text="No records found. Add a year in the Annual Returns tab.",
                         text_color="gray60").grid(row=0, column=0, pady=20)
            return

        latest = records[0]

        ctk.CTkLabel(scroll, text="COIDA Account Summary",
                     font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2,
                                                          sticky="w", pady=(0, 10))

        ctk.CTkLabel(scroll, text="Enter your COIDA reference number, working member name, and status in the Annual Returns tab.",
                     font=("Segoe UI", 9), text_color="gray60", wraplength=500).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ctk.CTkLabel(scroll, text="LOGS Status",
                     font=("Segoe UI", 12, "bold")).grid(row=2, column=0, columnspan=2,
                                                          sticky="w", pady=(8, 6))

        logs_col = {"OK": "#21A94D", "EXPIRING": "#F59E0B", "EXPIRED": "#EF4444", "NONE": "gray60"}
        _label_val(scroll, "Certificate No:", latest.logs_certificate_no or "—", 3)
        _label_val(scroll, "Expiry:", latest.logs_expiry or "—", 4)

        status_lbl = ctk.CTkLabel(scroll, text=latest.logs_status,
                                  font=("Segoe UI", 11, "bold"),
                                  text_color=logs_col.get(latest.logs_status, "gray60"))
        status_lbl.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ctk.CTkLabel(scroll, text="Account Balance",
                     font=("Segoe UI", 12, "bold")).grid(row=7, column=0, columnspan=2,
                                                          sticky="w", pady=(16, 6))

        _label_val(scroll, "Credit on account:", f"R {latest.coida_credit:,.2f}", 8)
        ctk.CTkLabel(scroll, text="(Credit = you are owed money; Debit = you owe COIDA)",
                     font=("Segoe UI", 8), text_color="gray60").grid(
            row=9, column=0, columnspan=2, sticky="w")

        ctk.CTkLabel(scroll, text="ROE Submissions",
                     font=("Segoe UI", 12, "bold")).grid(row=11, column=0, columnspan=2,
                                                          sticky="w", pady=(16, 6))

        roe_headers = ["FY", "Year End", "Director Earnings", "ROE Submitted", "Assessment", "Paid"]
        for c, h in enumerate(roe_headers):
            ctk.CTkLabel(scroll, text=h, font=("Segoe UI", 10, "bold"),
                         anchor="w").grid(row=12, column=c, sticky="w", padx=4)

        for r, ar in enumerate(records, start=13):
            vals = [
                ar.financial_year,
                ar.year_end,
                f"R {ar.director_total_earnings:,.0f}",
                "Yes" if ar.roe_submitted else "No",
                f"R {ar.assessment_amount:,.2f}" if ar.assessment_amount else "—",
                "Yes" if ar.assessment_paid else "No",
            ]
            for c, v in enumerate(vals):
                ctk.CTkLabel(scroll, text=v, anchor="w",
                             text_color="gray10").grid(row=r, column=c, sticky="w", padx=4, pady=1)

        if latest.notes:
            note_row = 13 + len(records) + 1
            ctk.CTkLabel(scroll, text="Notes",
                         font=("Segoe UI", 12, "bold")).grid(
                row=note_row, column=0, columnspan=2, sticky="w", pady=(16, 4))
            notes_box = ctk.CTkTextbox(scroll, height=80, wrap="word")
            notes_box.grid(row=note_row + 1, column=0, columnspan=4, sticky="ew", pady=(0, 8))
            notes_box.insert("1.0", latest.notes)
            notes_box.configure(state="disabled")


# ── Dialogs ──────────────────────────────────────────────────────────────────

class AnnualReturnDialog(ctk.CTkToplevel):

    def __init__(self, master, ar: AnnualReturn, repo: AnnualReturnRepository, on_save):
        super().__init__(master)
        self.title("Annual Return" + (f" — {ar.financial_year}" if ar.financial_year else ""))
        self.geometry("560x700")
        self.grab_set()
        self.lift()

        self._ar = ar
        self._repo = repo
        self._on_save = on_save

        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=16, pady=16)
        scroll.grid_columnconfigure(1, weight=1)

        fields = [
            ("Financial Year (e.g. FY2026)", "financial_year"),
            ("Year End Date (YYYY-MM-DD)", "year_end"),
            ("Revenue (R)", "revenue"),
            ("Sub-contractors (R)", "sub_contractors"),
            ("COGS (R)", "cogs"),
            ("Insurance (R)", "insurance"),
            ("Interest Expense (R)", "interest_expense"),
            ("Office Supplies (R)", "office_supplies"),
            ("Advertising (R)", "advertising"),
            ("Other Expenses (R)", "other_expenses"),
            ("Monthly Salary (R)", "monthly_salary"),
            ("Director Total Earnings (R)", "director_total_earnings"),
            ("LOGS Certificate No", "logs_certificate_no"),
            ("LOGS Expiry (YYYY-MM-DD)", "logs_expiry"),
            ("Assessment Amount (R)", "assessment_amount"),
            ("COIDA Credit on Account (R)", "coida_credit"),
        ]

        self._entries: dict[str, ctk.CTkEntry] = {}
        for r, (label, attr) in enumerate(fields):
            ctk.CTkLabel(scroll, text=label, anchor="w").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 8))
            e = ctk.CTkEntry(scroll)
            e.grid(row=r, column=1, sticky="ew", pady=3)
            val = getattr(ar, attr, "")
            if val is not None:
                e.insert(0, str(val) if val != 0.0 else "")
            self._entries[attr] = e

        base_row = len(fields)
        self._roe_var = ctk.BooleanVar(value=ar.roe_submitted)
        ctk.CTkCheckBox(scroll, text="ROE Submitted", variable=self._roe_var).grid(
            row=base_row, column=0, columnspan=2, sticky="w", pady=(8, 3))

        self._paid_var = ctk.BooleanVar(value=ar.assessment_paid)
        ctk.CTkCheckBox(scroll, text="Assessment Paid", variable=self._paid_var).grid(
            row=base_row + 1, column=0, columnspan=2, sticky="w", pady=3)

        ctk.CTkLabel(scroll, text="Notes", anchor="w").grid(
            row=base_row + 2, column=0, sticky="nw", pady=(8, 3))
        self._notes = ctk.CTkTextbox(scroll, height=80, wrap="word")
        self._notes.grid(row=base_row + 2, column=1, sticky="ew", pady=(8, 3))
        if ar.notes:
            self._notes.insert("1.0", ar.notes)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(btn_frame, text="Save", command=self._save).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray70",
                      command=self.destroy).pack(side="right")

    def _save(self):
        ar = self._ar
        ar.financial_year = self._entries["financial_year"].get().strip()
        ar.year_end = self._entries["year_end"].get().strip()

        float_fields = [
            "revenue", "sub_contractors", "cogs", "insurance", "interest_expense",
            "office_supplies", "advertising", "other_expenses",
            "monthly_salary", "director_total_earnings",
            "assessment_amount", "coida_credit",
        ]
        for f in float_fields:
            try:
                setattr(ar, f, float(self._entries[f].get().strip() or 0))
            except ValueError:
                setattr(ar, f, 0.0)

        ar.logs_certificate_no = self._entries["logs_certificate_no"].get().strip() or None
        ar.logs_expiry = self._entries["logs_expiry"].get().strip() or None
        ar.roe_submitted = self._roe_var.get()
        ar.assessment_paid = self._paid_var.get()
        ar.notes = self._notes.get("1.0", "end").strip()

        self._repo.save(ar)
        self._on_save()
        self.destroy()


class PayslipDialog(ctk.CTkToplevel):

    def __init__(self, master, repo: PayslipRepository, on_save):
        super().__init__(master)
        self.title("New Payslip")
        self.geometry("440x380")
        self.grab_set()
        self.lift()

        self._repo = repo
        self._on_save = on_save

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.grid_columnconfigure(1, weight=1)

        today = date.today()
        default_period = today.strftime("%Y-%m")

        fields = [
            ("Period (YYYY-MM)", default_period),
            ("Employee Name", ""),
            ("Gross Salary (R)", ""),
            ("UIF Employee (R)", ""),
            ("UIF Employer (R)", ""),
        ]
        self._entries: list[ctk.CTkEntry] = []
        for r, (label, default) in enumerate(fields):
            ctk.CTkLabel(frame, text=label, anchor="w").grid(row=r, column=0, sticky="w", pady=4, padx=(0, 8))
            e = ctk.CTkEntry(frame)
            if default:
                e.insert(0, default)
            e.grid(row=r, column=1, sticky="ew", pady=4)
            self._entries.append(e)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(btn_frame, text="Generate PDF", command=self._generate).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray70",
                      command=self.destroy).pack(side="right")

    def _generate(self):
        period = self._entries[0].get().strip()
        employee = self._entries[1].get().strip()
        try:
            gross = float(self._entries[2].get().strip())
            uif_emp = float(self._entries[3].get().strip())
            uif_empr = float(self._entries[4].get().strip())
        except ValueError:
            _ErrorDialog(self.winfo_toplevel(), "Please enter valid numbers for salary and UIF fields.")
            return

        net = round(gross - uif_emp, 2)

        payroll_dir = get_project_root() / "documents" / "Payroll"
        payroll_dir.mkdir(parents=True, exist_ok=True)
        pdf_name = f"Payslip_{period}_{employee.replace(' ', '_')}.pdf"
        pdf_path = str(payroll_dir / pdf_name)

        try:
            from core.payslip_pdf import generate_payslip_pdf
            from core.business_settings_service import BusinessSettingsService
            settings = BusinessSettingsService().get_settings()
            generate_payslip_pdf(
                period=period,
                employee_name=employee,
                gross_salary=gross,
                uif_employee=uif_emp,
                uif_employer=uif_empr,
                net_salary=net,
                output_path=pdf_path,
                business_settings=settings,
            )
        except Exception as e:
            _ErrorDialog(self.winfo_toplevel(), f"PDF generation failed: {e}")
            return

        slip = Payslip(
            id=None, period=period, employee_name=employee,
            gross_salary=gross, uif_employee=uif_emp, uif_employer=uif_empr,
            net_salary=net, pdf_path=pdf_path,
        )
        self._repo.save(slip)
        self._on_save()
        self.destroy()
        _open_file(pdf_path)


class _ErrorDialog(ctk.CTkToplevel):
    def __init__(self, master, message: str):
        super().__init__(master)
        self.title("Error")
        self.geometry("400x150")
        self.grab_set()
        self.lift()
        ctk.CTkLabel(self, text=message, wraplength=360).pack(padx=20, pady=20)
        ctk.CTkButton(self, text="OK", command=self.destroy).pack(pady=(0, 16))
