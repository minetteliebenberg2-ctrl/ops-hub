# ==========================================================
# FC Hub - Settings > Appearance Panel
# ----------------------------------------------------------
# Lets Minette change global colours and fonts at runtime.
# Persists overrides to <project_root>/user_theme.json;
# full effect needs an app restart (CTk widgets do not
# re-read tokens after creation), but a live preview strip
# gives immediate colour/font feedback while editing.
# ==========================================================

from tkinter import colorchooser, messagebox
from tkinter import ttk

import customtkinter as ctk

from gui.components.color_swatch import ColorSwatch
from gui.design_tokens import (
    COLORS,
    FONTS,
    THEME_DEFAULTS,
    load_user_theme,
    save_user_theme,
)


# Curated subset - the ones that actually matter for Minette's daily use.
COLOR_KEYS = [
    ("accent_primary", "Buttons & accent (brand green)"),
    ("accent_hover", "Button hover"),
    ("button_secondary", "Secondary buttons (grey)"),
    ("button_secondary_hover", "Secondary button hover"),
    ("text_primary", "Text - primary"),
    ("text_secondary", "Text - secondary"),
    ("text_tertiary", "Text - tertiary"),
    ("surface_primary", "Surface - primary"),
    ("surface_secondary", "Surface - secondary"),
    ("sidebar_bg", "Sidebar background"),
    ("sidebar_active_bg", "Sidebar active item"),
    ("sidebar_active_text", "Sidebar active text"),
    ("border_default", "Border"),
    ("success", "Status - success"),
    ("warning", "Status - warning"),
    ("danger", "Status - danger"),
]

FONT_KEYS = [
    ("title_lg", "Page title"),
    ("heading_sm", "Card heading"),
    ("body_md", "Body text"),
    ("body_sm", "Small body"),
    ("label", "Label"),
    ("label_sm", "Small label"),
]

FONT_FAMILIES = [
    "Segoe UI", "Calibri", "Arial", "Verdana",
    "Tahoma", "Consolas", "Cambria", "Lato",
]


class AppearancePanel(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(master, fg_color="transparent")

        # Work off a mutable draft of the current theme (defaults + saved overrides).
        stored = load_user_theme()
        self._draft_colors = {k: COLORS[k] for k, _ in COLOR_KEYS}
        self._draft_fonts = {k: tuple(FONTS[k]) for k, _ in FONT_KEYS}

        # (stored is already reflected in COLORS/FONTS - drafts start from live values)
        self._stored_snapshot = stored  # kept for reference

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Preview strip
        self._preview_frame = ctk.CTkFrame(self, corner_radius=6)
        self._preview_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 12))
        self._build_preview()

        # Scrollable editor
        editor = ctk.CTkScrollableFrame(self, fg_color="transparent")
        editor.grid(row=1, column=0, sticky="nsew", padx=4)
        editor.grid_columnconfigure(0, weight=1)

        self._color_swatches = {}
        self._font_widgets = {}

        # Colors section
        ctk.CTkLabel(editor, text="Colours", font=("Segoe UI", 14, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", pady=(0, 6)
        )
        colors_frame = ctk.CTkFrame(editor, fg_color="transparent")
        colors_frame.grid(row=1, column=0, sticky="ew")
        colors_frame.grid_columnconfigure(1, weight=1)

        for r, (key, label) in enumerate(COLOR_KEYS):
            ctk.CTkLabel(colors_frame, text=label, anchor="w", width=200).grid(
                row=r, column=0, sticky="w", padx=(0, 8), pady=3
            )
            swatch = ColorSwatch(colors_frame, self._draft_colors[key], size=26)
            swatch.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=3)
            self._color_swatches[key] = swatch
            ctk.CTkButton(
                colors_frame, text="Change...", width=90,
                command=lambda k=key: self._pick_color(k),
            ).grid(row=r, column=2, sticky="w", pady=3)

        # Fonts section
        ctk.CTkLabel(editor, text="Fonts", font=("Segoe UI", 14, "bold"), anchor="w").grid(
            row=2, column=0, sticky="ew", pady=(16, 6)
        )
        fonts_frame = ctk.CTkFrame(editor, fg_color="transparent")
        fonts_frame.grid(row=3, column=0, sticky="ew")
        fonts_frame.grid_columnconfigure(1, weight=1)

        for r, (key, label) in enumerate(FONT_KEYS):
            family, size, weight = self._draft_fonts[key]
            ctk.CTkLabel(fonts_frame, text=label, anchor="w", width=200).grid(
                row=r, column=0, sticky="w", padx=(0, 8), pady=3
            )
            fam_var = ctk.StringVar(value=family)
            fam_combo = ttk.Combobox(
                fonts_frame, values=FONT_FAMILIES, textvariable=fam_var,
                state="readonly", width=14,
            )
            fam_combo.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=3)
            fam_var.trace_add("write", lambda *_a, k=key: self._on_font_change(k))

            size_var = ctk.IntVar(value=int(size))
            size_spin = ttk.Spinbox(
                fonts_frame, from_=8, to=32, textvariable=size_var, width=5,
            )
            size_spin.grid(row=r, column=2, sticky="w", padx=(0, 8), pady=3)
            size_var.trace_add("write", lambda *_a, k=key: self._on_font_change(k))

            bold_var = ctk.BooleanVar(value=(str(weight).lower() == "bold"))
            bold_check = ctk.CTkCheckBox(
                fonts_frame, text="Bold", variable=bold_var,
                command=lambda k=key: self._on_font_change(k),
            )
            bold_check.grid(row=r, column=3, sticky="w", pady=3)

            self._font_widgets[key] = (fam_var, size_var, bold_var)

        # Button row
        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.grid(row=2, column=0, sticky="ew", padx=4, pady=(12, 4))
        ctk.CTkButton(button_row, text="Save", command=self._save, width=100).pack(side="left")
        ctk.CTkButton(
            button_row, text="Reset to Defaults", command=self._reset,
            fg_color=COLORS["danger"], hover_color="#b91c1c", width=160,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            button_row, text="Cancel", command=self._cancel,
            fg_color="transparent", border_width=1, text_color=COLORS["text_primary"],
            width=100,
        ).pack(side="left", padx=(8, 0))

        self._refresh_preview()

    # --------------- Preview ---------------

    def _build_preview(self):

        for child in self._preview_frame.winfo_children():
            child.destroy()

        self._preview_frame.configure(fg_color=self._draft_colors["surface_secondary"])

        wrap = ctk.CTkFrame(self._preview_frame, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            wrap, text="Preview - Page title",
            font=self._draft_fonts["title_lg"],
            text_color=self._draft_colors["text_primary"],
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            wrap, text="Body text sample - this is how paragraph copy will look.",
            font=self._draft_fonts["body_md"],
            text_color=self._draft_colors["text_primary"],
            anchor="w",
        ).pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(
            wrap, text="Secondary metadata line",
            font=self._draft_fonts["body_sm"],
            text_color=self._draft_colors["text_secondary"],
            anchor="w",
        ).pack(fill="x", pady=(2, 8))

        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(
            row, text="Primary action",
            fg_color=self._draft_colors["accent_primary"],
            hover_color=self._draft_colors["accent_primary"],
            text_color="#ffffff",
            font=self._draft_fonts["label"],
        ).pack(side="left")
        ctk.CTkLabel(
            row, text="Success",
            fg_color=self._draft_colors["success"],
            text_color="#ffffff",
            corner_radius=10,
            font=self._draft_fonts["label_sm"],
            padx=10, pady=2,
        ).pack(side="left", padx=(10, 0))

    def _refresh_preview(self):

        self._build_preview()

    # --------------- Handlers ---------------

    def _pick_color(self, key):

        current = self._draft_colors[key]
        result = colorchooser.askcolor(color=current, parent=self.winfo_toplevel(),
                                       title=f"Choose colour - {key}")
        if not result or not result[1]:
            return
        new_hex = result[1]
        self._draft_colors[key] = new_hex
        if key in self._color_swatches:
            self._color_swatches[key].set_color(new_hex)
        self._refresh_preview()

    def _on_font_change(self, key):

        fam_var, size_var, bold_var = self._font_widgets[key]
        try:
            size = int(size_var.get())
        except (ValueError, Exception):
            return
        family = fam_var.get() or self._draft_fonts[key][0]
        weight = "bold" if bold_var.get() else "normal"
        self._draft_fonts[key] = (family, size, weight)
        self._refresh_preview()

    # --------------- Save / Reset / Cancel ---------------

    def _compute_overrides(self):
        """Only-differ-from-defaults keys."""

        default_colors = THEME_DEFAULTS["colors"]
        default_fonts = THEME_DEFAULTS["fonts"]

        color_overrides = {
            k: v for k, v in self._draft_colors.items()
            if k in default_colors and v != default_colors[k]
        }
        font_overrides = {}
        for k, tup in self._draft_fonts.items():
            if k not in default_fonts:
                continue
            if tuple(tup) == tuple(default_fonts[k]):
                continue
            family, size, weight = tup
            font_overrides[k] = {"family": family, "size": int(size), "weight": weight}

        result = {}
        if color_overrides:
            result["colors"] = color_overrides
        if font_overrides:
            result["fonts"] = font_overrides
        return result

    def _save(self):

        overrides = self._compute_overrides()
        try:
            save_user_theme(overrides)
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("Appearance", f"Could not save theme:\n{error}",
                                 parent=self.winfo_toplevel())
            return
        messagebox.showinfo(
            "Appearance saved",
            "Your theme has been saved.\n\n"
            "Restart FC Hub to see all changes take effect.",
            parent=self.winfo_toplevel(),
        )

    def _reset(self):

        if not messagebox.askyesno(
            "Reset appearance",
            "Reset all colours and fonts to the FC Hub defaults?",
            parent=self.winfo_toplevel(),
        ):
            return
        try:
            save_user_theme({})
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("Appearance", f"Could not reset:\n{error}",
                                 parent=self.winfo_toplevel())
            return
        # Reset the draft view to defaults for immediate preview
        default_colors = THEME_DEFAULTS["colors"]
        default_fonts = THEME_DEFAULTS["fonts"]
        for k, _ in COLOR_KEYS:
            self._draft_colors[k] = default_colors[k]
            if k in self._color_swatches:
                self._color_swatches[k].set_color(default_colors[k])
        for k, _ in FONT_KEYS:
            family, size, weight = default_fonts[k]
            self._draft_fonts[k] = (family, size, weight)
            fam_var, size_var, bold_var = self._font_widgets[k]
            fam_var.set(family)
            size_var.set(int(size))
            bold_var.set(str(weight).lower() == "bold")
        self._refresh_preview()
        messagebox.showinfo(
            "Appearance reset",
            "Defaults restored.\n\nRestart FC Hub to see all changes take effect.",
            parent=self.winfo_toplevel(),
        )

    def _cancel(self):
        """Reload from stored file, discarding unsaved edits."""

        stored = load_user_theme()
        stored_colors = stored.get("colors", {}) if isinstance(stored, dict) else {}
        stored_fonts = stored.get("fonts", {}) if isinstance(stored, dict) else {}

        default_colors = THEME_DEFAULTS["colors"]
        default_fonts = THEME_DEFAULTS["fonts"]

        for k, _ in COLOR_KEYS:
            value = stored_colors.get(k, default_colors[k])
            if not isinstance(value, str):
                value = default_colors[k]
            self._draft_colors[k] = value
            if k in self._color_swatches:
                self._color_swatches[k].set_color(value)
        for k, _ in FONT_KEYS:
            default_family, default_size, default_weight = default_fonts[k]
            override = stored_fonts.get(k)
            if isinstance(override, dict):
                family = override.get("family", default_family)
                size = override.get("size", default_size)
                weight = override.get("weight", default_weight)
            else:
                family, size, weight = default_family, default_size, default_weight
            self._draft_fonts[k] = (family, int(size), weight)
            fam_var, size_var, bold_var = self._font_widgets[k]
            fam_var.set(family)
            size_var.set(int(size))
            bold_var.set(str(weight).lower() == "bold")
        self._refresh_preview()


__all__ = ["AppearancePanel"]
