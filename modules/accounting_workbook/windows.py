"""Accounting Workbook module UI — FY picker + generate Excel workbook."""

from __future__ import annotations

import os
import subprocess
import threading
from datetime import date
from pathlib import Path

import customtkinter as ctk

from gui.components.date_picker import DateEntry
from core.app_paths import get_project_root


def _open_file(path: str):
    try:
        os.startfile(path)
    except Exception:
        subprocess.Popen(["explorer", str(Path(path).parent)])


class AccountingWorkbookWindow(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Accounting Workbook",
                     font=("Segoe UI", 22, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 16))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="n")
        body.grid_columnconfigure(1, weight=0)

        # ── FY picker ────────────────────────────────────────────────────────
        # Financial year runs 1 March – end February.
        # "FY start year" = the March that opens the year.
        # Default: if today is before 1 March, start year = last year; else current year.
        today = date.today()
        default_fy = today.year if today.month >= 3 else today.year - 1
        default_date = f"{default_fy}-03-01"

        ctk.CTkLabel(body, text="Financial year start date",
                     font=("Segoe UI", 11, "bold"), anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 4))

        ctk.CTkLabel(body,
                     text="Select 1 March of the year the FY opens  (e.g. 2026-03-01 = FY2026/27)",
                     font=("Segoe UI", 9), text_color="gray60", anchor="w").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self._date_entry = DateEntry(body, value=default_date)
        self._date_entry.grid(row=2, column=0, sticky="w", pady=(0, 16))

        # ── Output folder info ───────────────────────────────────────────────
        out_dir = get_project_root() / "exports" / "Accounting"
        ctk.CTkLabel(body, text="Output folder",
                     font=("Segoe UI", 11, "bold"), anchor="w").grid(
            row=3, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(body, text=str(out_dir),
                     font=("Segoe UI", 9), text_color="gray60", anchor="w").grid(
            row=4, column=0, sticky="w", pady=(0, 16))

        # ── Generate button ──────────────────────────────────────────────────
        self._btn = ctk.CTkButton(body, text="Generate Workbook", width=180,
                                  command=self._generate)
        self._btn.grid(row=5, column=0, sticky="w", pady=(0, 12))

        self._status = ctk.CTkLabel(body, text="", font=("Segoe UI", 10),
                                    text_color="gray60", anchor="w", wraplength=420)
        self._status.grid(row=6, column=0, sticky="w")

        # ── Recent files ─────────────────────────────────────────────────────
        ctk.CTkLabel(body, text="Recent workbooks",
                     font=("Segoe UI", 11, "bold"), anchor="w").grid(
            row=7, column=0, sticky="w", pady=(20, 6))

        self._recent_frame = ctk.CTkFrame(body, fg_color="transparent")
        self._recent_frame.grid(row=8, column=0, sticky="ew")

        self._load_recent()

    # ── Actions ──────────────────────────────────────────────────────────────

    def _generate(self):
        raw = self._date_entry.get()
        try:
            from datetime import datetime
            d = datetime.strptime(raw, "%Y-%m-%d")
            fy_start = d.year
        except ValueError:
            self._set_status("Invalid date — enter a date in YYYY-MM-DD format.", error=True)
            return

        out_dir = get_project_root() / "exports" / "Accounting"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"Accounts_FY{fy_start}-{str(fy_start + 1)[-2:]}.xlsx"
        out_path = str(out_dir / filename)

        self._btn.configure(state="disabled", text="Generating…")
        self._set_status("Building workbook — this may take a few seconds…")

        def _run():
            try:
                import sys
                sys.path.insert(0, str(get_project_root()))
                from tools.build_accounting_workbook import build
                build(out_path, fy_start)
                self.after(0, self._on_done, out_path, None)
            except Exception as exc:
                self.after(0, self._on_done, out_path, str(exc))

        threading.Thread(target=_run, daemon=True).start()

    def _on_done(self, out_path: str, error: str | None):
        self._btn.configure(state="normal", text="Generate Workbook")
        if error:
            self._set_status(f"Error: {error}", error=True)
        else:
            self._set_status(f"Saved: {out_path}")
            self._load_recent()
            _open_file(out_path)

    def _set_status(self, msg: str, error: bool = False):
        self._status.configure(text=msg,
                               text_color="#EF4444" if error else "gray60")

    def _load_recent(self):
        for w in self._recent_frame.winfo_children():
            w.destroy()

        out_dir = get_project_root() / "exports" / "Accounting"
        if not out_dir.is_dir():
            return

        files = sorted(out_dir.glob("*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)[:5]
        if not files:
            ctk.CTkLabel(self._recent_frame, text="None yet.",
                         font=("Segoe UI", 9), text_color="gray60").pack(anchor="w")
            return

        for f in files:
            row = ctk.CTkFrame(self._recent_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=f.name, font=("Segoe UI", 9),
                         text_color="gray30", anchor="w").pack(side="left")
            ctk.CTkButton(row, text="Open", width=60,
                          command=lambda p=str(f): _open_file(p)).pack(side="left", padx=(8, 0))
