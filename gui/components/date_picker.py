import calendar
from datetime import date, timedelta

import customtkinter as ctk

from gui.design_tokens import COLORS, FONTS, SPACING


class DatePickerPopup(ctk.CTkToplevel):

    def __init__(self, parent, current_value="", callback=None):
        super().__init__(parent)
        self.overrideredirect(True)
        self.callback = callback
        self.configure(fg_color=COLORS["surface_primary"])

        try:
            self._current = date.fromisoformat(current_value)
        except (ValueError, TypeError):
            self._current = date.today()
        self._viewing = self._current.replace(day=1)

        self._build()
        self._render_month()

        self.after(10, self._position, parent)
        self.grab_set()
        self.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_out(self, event):
        try:
            focused = self.focus_get()
            if focused and (focused == self or str(focused).startswith(str(self))):
                return
        except KeyError:
            pass
        self._close()

    def _position(self, parent):
        x = parent.winfo_rootx()
        y = parent.winfo_rooty() + parent.winfo_height() + 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=4, pady=4)

        ctk.CTkButton(nav, text="<", width=28, height=28,
                       fg_color=COLORS["surface_secondary"], text_color=COLORS["text_primary"],
                       hover_color=COLORS["border_default"],
                       command=self._prev_month).pack(side="left")

        self._title_label = ctk.CTkLabel(nav, text="", font=FONTS["label"],
                                          text_color=COLORS["text_primary"])
        self._title_label.pack(side="left", expand=True)

        ctk.CTkButton(nav, text=">", width=28, height=28,
                       fg_color=COLORS["surface_secondary"], text_color=COLORS["text_primary"],
                       hover_color=COLORS["border_default"],
                       command=self._next_month).pack(side="right")

        day_hdr = ctk.CTkFrame(self, fg_color="transparent")
        day_hdr.pack(fill="x", padx=4)
        for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            ctk.CTkLabel(day_hdr, text=d, width=32, font=FONTS["body_sm"],
                          text_color=COLORS["text_tertiary"]).pack(side="left")

        self._grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._grid_frame.pack(fill="x", padx=4, pady=(0, 4))

    def _render_month(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()

        y, m = self._viewing.year, self._viewing.month
        self._title_label.configure(text=f"{calendar.month_name[m]} {y}")

        cal = calendar.Calendar(firstweekday=0)
        today = date.today()

        row_frame = None
        for i, dt in enumerate(cal.itermonthdates(y, m)):
            if i % 7 == 0:
                row_frame = ctk.CTkFrame(self._grid_frame, fg_color="transparent")
                row_frame.pack(fill="x")

            in_month = dt.month == m
            is_today = dt == today
            is_selected = dt == self._current

            if is_selected:
                bg = COLORS["accent_primary"]
                fg = COLORS["text_inverse"]
            elif is_today:
                bg = COLORS["surface_secondary"]
                fg = COLORS["accent_primary"]
            else:
                bg = "transparent"
                fg = COLORS["text_primary"] if in_month else COLORS["text_tertiary"]

            btn = ctk.CTkButton(
                row_frame, text=str(dt.day), width=32, height=28,
                fg_color=bg, text_color=fg, hover_color=COLORS["border_default"],
                font=FONTS["body_sm"], corner_radius=4,
                command=lambda d=dt: self._select(d),
            )
            btn.pack(side="left")

    def _select(self, dt):
        if self.callback:
            self.callback(dt.isoformat())
        self._close()

    def _prev_month(self):
        if self._viewing.month == 1:
            self._viewing = self._viewing.replace(year=self._viewing.year - 1, month=12)
        else:
            self._viewing = self._viewing.replace(month=self._viewing.month - 1)
        self._render_month()

    def _next_month(self):
        if self._viewing.month == 12:
            self._viewing = self._viewing.replace(year=self._viewing.year + 1, month=1)
        else:
            self._viewing = self._viewing.replace(month=self._viewing.month + 1)
        self._render_month()

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class DateEntry(ctk.CTkFrame):

    def __init__(self, master, value="", placeholder="YYYY-MM-DD", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._value = value or ""
        self._popup = None

        self._entry = ctk.CTkEntry(self, placeholder_text=placeholder,
                                    font=FONTS["body_md"], width=140)
        if self._value:
            self._entry.insert(0, self._value)
        self._entry.pack(side="left")

        self._btn = ctk.CTkButton(
            self, text="...", width=28, height=28,
            fg_color=COLORS["surface_secondary"], text_color=COLORS["text_primary"],
            hover_color=COLORS["border_default"],
            command=self._open_picker,
        )
        self._btn.pack(side="left", padx=(4, 0))

    def _open_picker(self):
        if self._popup and self._popup.winfo_exists():
            return
        self._popup = DatePickerPopup(
            self._entry, current_value=self._entry.get(), callback=self._on_pick,
        )

    def _on_pick(self, iso_date):
        self._entry.delete(0, "end")
        self._entry.insert(0, iso_date)
        self._value = iso_date

    def get(self):
        return self._entry.get().strip()

    def set(self, value):
        self._entry.delete(0, "end")
        if value:
            self._entry.insert(0, value)
        self._value = value or ""
