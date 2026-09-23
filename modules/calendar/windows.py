import calendar
import getpass
from datetime import datetime, timedelta
from tkinter import messagebox
from uuid import uuid4

import customtkinter as ctk

from core.crm_service import CRMService
from core.scheduled_job_service import ScheduledJobService
from gui.components.date_picker import DateEntry
from gui.design_tokens import COLORS, FONTS, SPACING

THEME_DARK_GREY = COLORS["surface_primary"]
THEME_SURFACE = COLORS["surface_secondary"]
THEME_SURFACE_LIGHT = COLORS["surface_tertiary"]
THEME_TEXT_PRIMARY = COLORS["text_primary"]
THEME_TEXT_SECONDARY = COLORS["text_secondary"]

STATUS_BADGE = {
    "Scheduled": COLORS["accent_primary"],
    "In Progress": COLORS["warning"],
    "Completed": COLORS["success"],
    "Cancelled": COLORS["danger"],
}


def _actor():
    try:
        return getpass.getuser()
    except Exception:
        return ""


class CalendarHub(ctk.CTkToplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Calendar Hub")
        self.geometry("500x420")
        self.resizable(False, False)
        self.configure(fg_color=THEME_DARK_GREY)

        ctk.CTkLabel(self, text="Calendar Hub", font=("Segoe UI", 24, "bold"),
                     text_color=THEME_TEXT_PRIMARY).pack(pady=(20, 30))
        ctk.CTkLabel(self, text="Schedule jobs and track timelines.",
                     font=("Segoe UI", 11), text_color=THEME_TEXT_SECONDARY).pack(pady=(0, 30), padx=20)

        bf = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        bf.pack(pady=20, padx=20, fill="both", expand=True)

        for label, cmd in [
            ("📅 Month View", self.open_calendar),
            ("📋 Job List", self.open_jobs),
            ("+ Schedule Job", self.open_new_job),
        ]:
            ctk.CTkButton(bf, text=label, command=cmd, height=50, font=("Segoe UI", 12),
                          fg_color=COLORS["accent_primary"], hover_color=COLORS["accent_hover"]).pack(pady=8, fill="x")

        ctk.CTkButton(self, text="Close Hub", command=self.destroy, width=200,
                      fg_color=COLORS["surface_tertiary"], hover_color=COLORS["border_strong"],
                      text_color=COLORS["text_primary"]).pack(pady=(0, 20))

        self.calendar_window = None
        self.jobs_window = None

    def open_calendar(self):
        if self.calendar_window is None or not self.calendar_window.winfo_exists():
            self.calendar_window = CalendarMonthWindow(self)
        else:
            self.calendar_window.lift()

    def open_jobs(self):
        if self.jobs_window is None or not self.jobs_window.winfo_exists():
            self.jobs_window = JobListWindow(self)
        else:
            self.jobs_window.lift()

    def open_new_job(self):
        NewScheduledJobDialog(self, on_saved=self._after_save)

    def _after_save(self):
        if self.calendar_window and self.calendar_window.winfo_exists():
            self.calendar_window.refresh()
        if self.jobs_window and self.jobs_window.winfo_exists():
            self.jobs_window.refresh()


class CalendarMonthWindow(ctk.CTkToplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Calendar - Month View")
        self.geometry("1000x680")
        self.minsize(800, 500)
        self.configure(fg_color=THEME_DARK_GREY)

        self.service = ScheduledJobService()
        self.crm_service = CRMService()
        now = datetime.now()
        self._year = now.year
        self._month = now.month

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        hdr.pack(fill="x", padx=16, pady=(12, 0))

        ctk.CTkButton(hdr, text="◀ Prev", width=80, command=self._prev_month).pack(side="left")
        self._month_label = ctk.CTkLabel(hdr, text="", font=("Segoe UI", 16, "bold"),
                                         text_color=THEME_TEXT_PRIMARY)
        self._month_label.pack(side="left", expand=True)
        ctk.CTkButton(hdr, text="Next ▶", width=80, command=self._next_month).pack(side="right")

        day_hdr = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        day_hdr.pack(fill="x", padx=16, pady=(12, 0))
        for day_name in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
            ctk.CTkLabel(day_hdr, text=day_name, width=120, font=FONTS["label_sm"],
                         text_color=THEME_TEXT_SECONDARY).pack(side="left", expand=True)

        self._grid_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        self._grid_frame.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        footer = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        footer.pack(fill="x", padx=16, pady=(0, 12))
        self._stats_label = ctk.CTkLabel(footer, text="", font=FONTS["body_sm"],
                                         text_color=THEME_TEXT_SECONDARY)
        self._stats_label.pack(padx=12, pady=8)

    def _prev_month(self):
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self.refresh()

    def _next_month(self):
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self.refresh()

    def refresh(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()

        self._month_label.configure(text=f"{calendar.month_name[self._month]} {self._year}")
        ym = f"{self._year}-{self._month:02d}"
        jobs = self.service.list_for_month(ym)
        jobs_by_day = {}
        for j in jobs:
            day = j.start_date[8:10] if len(j.start_date) >= 10 else ""
            if day:
                jobs_by_day.setdefault(day, []).append(j)

        customers = {}
        for j in jobs:
            if j.customer_id and j.customer_id not in customers:
                try:
                    customers[j.customer_id] = self.crm_service.get_customer(j.customer_id)
                except Exception:
                    customers[j.customer_id] = None

        cal = calendar.monthcalendar(self._year, self._month)
        today = datetime.now()

        for week_idx, week in enumerate(cal):
            for col, day in enumerate(week):
                cell = ctk.CTkFrame(self._grid_frame, fg_color=THEME_SURFACE, border_width=1,
                                    border_color=COLORS["border_default"], corner_radius=4)
                cell.grid(row=week_idx, column=col, padx=1, pady=1, sticky="nsew")

                if day == 0:
                    continue

                is_today = (self._year == today.year and self._month == today.month and day == today.day)
                day_color = COLORS["accent_primary"] if is_today else THEME_TEXT_PRIMARY
                ctk.CTkLabel(cell, text=str(day), font=FONTS["label_sm"],
                             text_color=day_color, anchor="nw").pack(anchor="nw", padx=4, pady=2)

                day_key = f"{day:02d}"
                for j in jobs_by_day.get(day_key, [])[:3]:
                    cust = customers.get(j.customer_id)
                    badge_color = STATUS_BADGE.get(j.status, COLORS["accent_primary"])
                    lbl = ctk.CTkLabel(cell, text=f"• {j.title[:18]}", font=("Segoe UI", 8),
                                       text_color=badge_color, anchor="w")
                    lbl.pack(anchor="w", padx=4)

            for col in range(7):
                self._grid_frame.grid_columnconfigure(col, weight=1)
            self._grid_frame.grid_rowconfigure(week_idx, weight=1)

        scheduled = sum(1 for j in jobs if j.status == "Scheduled")
        in_prog = sum(1 for j in jobs if j.status == "In Progress")
        done = sum(1 for j in jobs if j.status == "Completed")
        self._stats_label.configure(text=f"{len(jobs)} jobs this month  ·  {scheduled} scheduled  ·  {in_prog} in progress  ·  {done} completed")


class JobListWindow(ctk.CTkToplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Scheduled Jobs")
        self.geometry("1000x600")
        self.minsize(800, 400)
        self.configure(fg_color=THEME_DARK_GREY)

        self.service = ScheduledJobService()
        self.crm_service = CRMService()

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        top.pack(fill="x", padx=16, pady=(12, 0))

        ctk.CTkLabel(top, text="Filter:", font=FONTS["label_sm"],
                     text_color=THEME_TEXT_SECONDARY).pack(side="left", padx=10, pady=10)
        self._filter_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(top, values=["All", "Scheduled", "In Progress", "Completed", "Cancelled"],
                          variable=self._filter_var, command=lambda _: self.refresh(),
                          width=160).pack(side="left", padx=5)
        ctk.CTkButton(top, text="+ New Job", width=100, command=self._new_job).pack(side="right", padx=10, pady=10)
        ctk.CTkButton(top, text="↻ Refresh", width=80, command=self.refresh).pack(side="right", pady=10)

        cols = ["Title", "Customer", "Start", "End", "Status", "Assigned"]
        widths = [200, 200, 100, 100, 100, 120]
        hdr = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        hdr.pack(fill="x", padx=16, pady=(8, 0))
        for text, w in zip(cols, widths):
            ctk.CTkLabel(hdr, text=text, width=w, font=FONTS["label_sm"],
                         text_color=THEME_TEXT_SECONDARY, anchor="w").pack(side="left", padx=4, pady=6)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=THEME_DARK_GREY)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        jobs = self.service.list_all()
        filt = self._filter_var.get()
        if filt != "All":
            jobs = [j for j in jobs if j.status == filt]

        customers = {}
        for j in jobs:
            if j.customer_id and j.customer_id not in customers:
                try:
                    customers[j.customer_id] = self.crm_service.get_customer(j.customer_id)
                except Exception:
                    customers[j.customer_id] = None

        if not jobs:
            ctk.CTkLabel(self._scroll, text="No scheduled jobs.", font=FONTS["body_md"],
                         text_color=THEME_TEXT_SECONDARY).pack(pady=40)
            return

        widths = [200, 200, 100, 100, 100, 120]
        for idx, j in enumerate(jobs):
            bg = THEME_DARK_GREY if idx % 2 == 0 else THEME_SURFACE
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0)
            row.pack(fill="x")

            cust = customers.get(j.customer_id)
            cust_name = cust.name if cust else "—"

            cells = [
                (j.title[:30], widths[0], "w"),
                (cust_name[:30], widths[1], "w"),
                (j.start_date[:10], widths[2], "w"),
                (j.end_date[:10], widths[3], "w"),
                (j.status, widths[4], "w"),
                (j.assigned_to[:15], widths[5], "w"),
            ]
            for text, w, anchor in cells:
                color = STATUS_BADGE.get(j.status, THEME_TEXT_PRIMARY) if text == j.status else THEME_TEXT_PRIMARY
                ctk.CTkLabel(row, text=text, width=w, font=FONTS["body_sm"],
                             text_color=color, anchor=anchor).pack(side="left", padx=4, pady=4)

            ctk.CTkButton(row, text="Edit", width=50, height=22, font=("Segoe UI", 9),
                          command=lambda job=j: self._edit_job(job)).pack(side="right", padx=4, pady=4)

    def _new_job(self):
        NewScheduledJobDialog(self, on_saved=self.refresh)

    def _edit_job(self, job):
        EditScheduledJobDialog(self, job, on_saved=self.refresh)


class NewScheduledJobDialog(ctk.CTkToplevel):

    def __init__(self, parent, on_saved=None):
        super().__init__(parent)
        self.title("Schedule New Job")
        self.geometry("460x450")
        self.resizable(False, False)
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)

        self.on_saved = on_saved
        self.crm_service = CRMService()
        self.service = ScheduledJobService()

        self._customers = [c for c in self.crm_service.list_customers() if c.name]
        cust_names = [c.name for c in self._customers] or ["(no customers)"]

        self._build("Customer", "customer")
        self.customer_menu = ctk.CTkOptionMenu(self, values=cust_names, width=380)
        self.customer_menu.pack(padx=40, pady=(2, 10))

        self._build("Title", "title")
        self.title_entry = ctk.CTkEntry(self, width=380, placeholder_text="e.g. Site installation")
        self.title_entry.pack(padx=40, pady=(2, 10))

        self._build("Start Date", "start")
        self.start_entry = DateEntry(self, value=datetime.now().strftime("%Y-%m-%d"))
        self.start_entry.pack(padx=40, pady=(2, 10))

        self._build("End Date", "end")
        self.end_entry = DateEntry(self, value=datetime.now().strftime("%Y-%m-%d"))
        self.end_entry.pack(padx=40, pady=(2, 10))

        self._build("Assigned To", "assign")
        self.assign_entry = ctk.CTkEntry(self, width=380, placeholder_text="Team member name")
        self.assign_entry.pack(padx=40, pady=(2, 10))

        self._build("Notes", "notes")
        self.notes_entry = ctk.CTkEntry(self, width=380)
        self.notes_entry.pack(padx=40, pady=(2, 16))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 16))
        ctk.CTkButton(btn_row, text="Cancel", width=100, fg_color=COLORS["surface_tertiary"],
                      text_color=COLORS["text_primary"], command=self.destroy).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Schedule", width=100, command=self._save).pack(side="left", padx=8)

    def _build(self, text, _tag):
        ctk.CTkLabel(self, text=text, font=("Segoe UI", 10), text_color=THEME_TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=40)

    def _current_customer(self):
        name = self.customer_menu.get()
        for c in self._customers:
            if c.name == name:
                return c
        return None

    def _save(self):
        cust = self._current_customer()
        if not cust:
            messagebox.showwarning("Schedule", "Select a customer.", parent=self)
            return
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Schedule", "Enter a job title.", parent=self)
            return
        try:
            self.service.create(
                customer_id=cust.id,
                title=title,
                start_date=self.start_entry.get().strip(),
                end_date=self.end_entry.get().strip(),
                assigned_to=self.assign_entry.get().strip(),
                notes=self.notes_entry.get().strip(),
                actor=_actor(),
            )
        except Exception as exc:
            messagebox.showerror("Schedule", str(exc), parent=self)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()


class EditScheduledJobDialog(ctk.CTkToplevel):

    def __init__(self, parent, job, on_saved=None):
        super().__init__(parent)
        self.title(f"Edit — {job.title}")
        self.geometry("460x500")
        self.resizable(False, False)
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)

        self.job = job
        self.on_saved = on_saved
        self.service = ScheduledJobService()

        self._label("Title")
        self.title_entry = ctk.CTkEntry(self, width=380)
        self.title_entry.insert(0, job.title)
        self.title_entry.pack(padx=40, pady=(2, 10))

        self._label("Status")
        self.status_menu = ctk.CTkOptionMenu(self, values=["Scheduled", "In Progress", "Completed", "Cancelled"], width=380)
        self.status_menu.set(job.status)
        self.status_menu.pack(padx=40, pady=(2, 10))

        self._label("Start Date")
        self.start_entry = DateEntry(self, value=job.start_date[:10])
        self.start_entry.pack(padx=40, pady=(2, 10))

        self._label("End Date")
        self.end_entry = DateEntry(self, value=job.end_date[:10])
        self.end_entry.pack(padx=40, pady=(2, 10))

        self._label("Assigned To")
        self.assign_entry = ctk.CTkEntry(self, width=380)
        self.assign_entry.insert(0, job.assigned_to)
        self.assign_entry.pack(padx=40, pady=(2, 10))

        self._label("Notes")
        self.notes_entry = ctk.CTkEntry(self, width=380)
        self.notes_entry.insert(0, job.notes)
        self.notes_entry.pack(padx=40, pady=(2, 16))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 16))
        ctk.CTkButton(btn_row, text="Delete", width=80, fg_color=COLORS["danger"],
                      command=self._delete).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Cancel", width=80, fg_color=COLORS["surface_tertiary"],
                      text_color=COLORS["text_primary"], command=self.destroy).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Save", width=80, command=self._save).pack(side="left", padx=8)

    def _label(self, text):
        ctk.CTkLabel(self, text=text, font=("Segoe UI", 10), text_color=THEME_TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=40)

    def _save(self):
        try:
            self.service.update(
                self.job.id,
                title=self.title_entry.get().strip(),
                status=self.status_menu.get(),
                start_date=self.start_entry.get().strip(),
                end_date=self.end_entry.get().strip(),
                assigned_to=self.assign_entry.get().strip(),
                notes=self.notes_entry.get().strip(),
            )
        except Exception as exc:
            messagebox.showerror("Schedule", str(exc), parent=self)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()

    def _delete(self):
        if not messagebox.askyesno("Delete", f"Delete scheduled job \"{self.job.title}\"?", parent=self):
            return
        self.service.delete(self.job.id)
        if self.on_saved:
            self.on_saved()
        self.destroy()


class CalendarModuleWindow(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)
        self.configure(fg_color=THEME_DARK_GREY)
        self.hub = None

        ctk.CTkLabel(self, text="Calendar", font=("Segoe UI", 22, "bold"),
                     text_color=THEME_TEXT_PRIMARY).pack(pady=(20, 30))

        info = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        info.pack(pady=20, padx=40, fill="both", expand=True)

        ctk.CTkLabel(info, text="Schedule jobs and track timelines.\n\nUse the buttons below to manage your calendar.",
                     font=("Segoe UI", 11), text_color=THEME_TEXT_SECONDARY, justify="center").pack(pady=20, padx=20)

        bf = ctk.CTkFrame(info, fg_color=THEME_SURFACE)
        bf.pack(pady=20, padx=20, fill="x")

        for label, cmd in [
            ("📅 Calendar", self._open_calendar),
            ("📋 Jobs", self._open_jobs),
            ("+ Schedule Job", self._open_new),
        ]:
            ctk.CTkButton(bf, text=label, command=cmd, height=40, font=("Segoe UI", 11)).pack(pady=5, fill="x")

    def _ensure_hub(self):
        if self.hub is None or not self.hub.winfo_exists():
            self.hub = CalendarHub(self.winfo_toplevel())
        return self.hub

    def _open_calendar(self):
        self._ensure_hub().open_calendar()

    def _open_jobs(self):
        self._ensure_hub().open_jobs()

    def _open_new(self):
        self._ensure_hub().open_new_job()
