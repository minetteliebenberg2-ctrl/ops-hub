"""Generate a custom CTk theme JSON from design_tokens.COLORS at startup.

Called once from launcher.py AFTER design_tokens has loaded (including any
user_theme.json overrides). Writes a temp JSON file and points CTk at it,
so every widget — even ones without explicit fg_color — picks up the
brand accent color.
"""

import json
import tempfile
import os

_theme_file = None


def apply_ctk_theme():
    """Build a CTk theme JSON from COLORS and set it as the default."""
    global _theme_file

    from gui.design_tokens import COLORS

    accent = COLORS["accent_primary"]
    accent_hover = COLORS["accent_hover"]

    theme = {
        "CTk": {
            "fg_color": ["gray92", "gray14"]
        },
        "CTkToplevel": {
            "fg_color": ["gray92", "gray14"]
        },
        "CTkFrame": {
            "corner_radius": 6,
            "border_width": 0,
            "fg_color": ["gray86", "gray17"],
            "top_fg_color": ["gray81", "gray20"],
            "border_color": ["gray65", "gray28"]
        },
        "CTkButton": {
            "corner_radius": 6,
            "border_width": 0,
            "fg_color": [accent, accent],
            "hover_color": [accent_hover, accent_hover],
            "border_color": ["#3E454A", "#949A9F"],
            "text_color": ["gray98", "#DCE4EE"],
            "text_color_disabled": ["gray78", "gray68"]
        },
        "CTkLabel": {
            "corner_radius": 0,
            "border_width": 0,
            "fg_color": "transparent",
            "border_color": ["#979DA2", "#565B5E"],
            "text_color": ["gray10", "#DCE4EE"]
        },
        "CTkEntry": {
            "corner_radius": 6,
            "border_width": 2,
            "fg_color": ["#F9F9FA", "#343638"],
            "border_color": ["#979DA2", "#565B5E"],
            "text_color": ["gray10", "#DCE4EE"],
            "placeholder_text_color": ["gray52", "gray62"]
        },
        "CTkCheckBox": {
            "corner_radius": 6,
            "border_width": 3,
            "fg_color": [accent, accent],
            "border_color": ["#3E454A", "#949A9F"],
            "hover_color": [accent_hover, accent_hover],
            "checkmark_color": ["#DCE4EE", "gray90"],
            "text_color": ["gray10", "#DCE4EE"],
            "text_color_disabled": ["gray60", "gray45"]
        },
        "CTkSwitch": {
            "corner_radius": 1000,
            "border_width": 3,
            "button_length": 0,
            "fg_color": ["#939BA2", "#4A4D50"],
            "progress_color": [accent, accent],
            "button_color": ["gray36", "#D5D9DE"],
            "button_hover_color": ["gray20", "gray100"],
            "text_color": ["gray10", "#DCE4EE"],
            "text_color_disabled": ["gray60", "gray45"]
        },
        "CTkRadioButton": {
            "corner_radius": 1000,
            "border_width_checked": 6,
            "border_width_unchecked": 3,
            "fg_color": [accent, accent],
            "border_color": ["#3E454A", "#949A9F"],
            "hover_color": [accent_hover, accent_hover],
            "text_color": ["gray10", "#DCE4EE"],
            "text_color_disabled": ["gray60", "gray45"]
        },
        "CTkProgressBar": {
            "corner_radius": 1000,
            "border_width": 0,
            "fg_color": ["#939BA2", "#4A4D50"],
            "progress_color": [accent, accent],
            "border_color": ["gray", "gray"]
        },
        "CTkSlider": {
            "corner_radius": 1000,
            "button_corner_radius": 1000,
            "border_width": 6,
            "button_length": 0,
            "fg_color": ["#939BA2", "#4A4D50"],
            "progress_color": ["gray40", "#AAB0B5"],
            "button_color": [accent, accent],
            "button_hover_color": [accent_hover, accent_hover]
        },
        "CTkOptionMenu": {
            "corner_radius": 6,
            "fg_color": [accent, accent],
            "button_color": [accent_hover, accent_hover],
            "button_hover_color": [accent, accent],
            "text_color": ["gray98", "#DCE4EE"],
            "text_color_disabled": ["gray78", "gray68"]
        },
        "CTkComboBox": {
            "corner_radius": 6,
            "border_width": 2,
            "fg_color": ["#F9F9FA", "#343638"],
            "border_color": ["#979DA2", "#565B5E"],
            "button_color": ["#979DA2", "#565B5E"],
            "button_hover_color": ["#6E7174", "#7A848D"],
            "text_color": ["gray10", "#DCE4EE"],
            "text_color_disabled": ["gray50", "gray45"]
        },
        "CTkScrollbar": {
            "corner_radius": 1000,
            "border_spacing": 4,
            "fg_color": "transparent",
            "button_color": ["gray55", "gray41"],
            "button_hover_color": ["gray40", "gray53"]
        },
        "CTkSegmentedButton": {
            "corner_radius": 6,
            "border_width": 2,
            "fg_color": [accent, accent],
            "selected_color": [accent, accent],
            "selected_hover_color": [accent_hover, accent_hover],
            "unselected_color": ["gray86", "gray17"],
            "unselected_hover_color": ["gray70", "gray30"],
            "text_color": ["gray98", "#DCE4EE"],
            "text_color_disabled": ["gray78", "gray68"]
        },
        "CTkTextbox": {
            "corner_radius": 6,
            "border_width": 0,
            "fg_color": ["#F9F9FA", "#1D1E1E"],
            "border_color": ["#979DA2", "#565B5E"],
            "text_color": ["gray10", "#DCE4EE"],
            "scrollbar_button_color": ["gray55", "gray41"],
            "scrollbar_button_hover_color": ["gray40", "gray53"]
        },
        "CTkScrollableFrame": {
            "label_fg_color": ["gray78", "gray21"]
        },
        "DropdownMenu": {
            "fg_color": ["gray90", "gray20"],
            "hover_color": ["gray75", "gray28"],
            "text_color": ["gray10", "gray90"]
        },
        "CTkFont": {
            "macOS": {"family": "SF Display", "size": 13, "weight": "normal"},
            "Windows": {"family": "Segoe UI", "size": 13, "weight": "normal"},
            "Linux": {"family": "Noto Sans", "size": 13, "weight": "normal"}
        }
    }

    fd, path = tempfile.mkstemp(suffix=".json", prefix="fc_hub_theme_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(theme, f, indent=2)
    _theme_file = path

    import customtkinter as ctk
    ctk.set_default_color_theme(path)
