# ==========================================================
# FC Hub - Design System Tokens
# ----------------------------------------------------------
# Light theme, professional construction CRM aesthetic
# All colors, spacing, typography in one place
#
# Author: Claude (Redesign Phase 2)
# ==========================================================

# ==========================================================
# COLOR PALETTE
# ==========================================================

COLORS = {
    # Primary backgrounds (light theme)
    "surface_primary": "#ffffff",        # Main content area
    "surface_secondary": "#fafafa",      # Headers, cards
    "surface_tertiary": "#f5f5f5",       # Sidebar, disabled states

    # Text colors
    "text_primary": "#1a1a1a",           # Body text, headings
    "text_secondary": "#666666",         # Supporting text
    "text_tertiary": "#999999",          # Metadata, hints
    "text_muted": "#cccccc",             # Disabled, placeholders
    "text_inverse": "#ffffff",           # On dark backgrounds

    # Accent & actions
    "accent_primary": "#1B7A3D",         # FC Hub brand green
    "accent_hover": "#165a30",           # Darker green on hover
    "accent_light": "#e8f5f0",           # Light green tint for badges

    # Semantic colors
    "success": "#10b981",                # Green for positive/completed
    "warning": "#f59e0b",                # Amber for caution
    "danger": "#ef4444",                 # Red for destructive actions
    "info": "#3b82f6",                   # Blue for information

    # Secondary buttons (grey)
    "button_secondary": "#555555",       # Secondary action buttons
    "button_secondary_hover": "#666666", # Secondary button hover

    # Borders & dividers
    "border_default": "#e5e7eb",         # Standard borders
    "border_light": "#f0f0f0",           # Subtle dividers
    "border_strong": "#d1d5db",          # Emphasized borders

    # Sidebar
    "sidebar_bg": "#f5f5f5",             # Sidebar background
    "sidebar_text": "#1a1a1a",           # Sidebar text
    "sidebar_active_bg": "#e8f5f0",      # Active item background
    "sidebar_active_text": "#1B7A3D",    # Active item text
    "sidebar_hover_bg": "#ebebeb",       # Hover state
}

# ==========================================================
# TYPOGRAPHY
# ==========================================================

FONTS = {
    # Page title (h1)
    "title_lg": ("Lato", 24, "bold"),

    # Section heading (h2)
    "heading_lg": ("Lato", 18, "bold"),

    # Subsection heading (h3)
    "heading_md": ("Lato", 16, "bold"),

    # Card title
    "heading_sm": ("Lato", 14, "bold"),

    # Body text (regular)
    "body_lg": ("Lato", 13, "normal"),
    "body_md": ("Lato", 12, "normal"),
    "body_sm": ("Lato", 11, "normal"),

    # Labels, small text
    "label": ("Lato", 11, "normal"),
    "label_sm": ("Lato", 10, "normal"),

    # Monospace (for codes, technical text)
    "mono": ("Courier New", 11, "normal"),
}

# ==========================================================
# SPACING
# ==========================================================

SPACING = {
    "xs": 4,      # Minimal gaps
    "sm": 8,      # Small padding/gaps
    "md": 12,     # Standard padding
    "lg": 16,     # Large padding
    "xl": 20,     # Extra large
    "xxl": 24,    # Section spacing
    "xxxl": 32,   # Page-level spacing
}

# ==========================================================
# BORDER RADIUS
# ==========================================================

RADIUS = {
    "sm": 4,      # Buttons, small components
    "md": 6,      # Cards, input fields
    "lg": 8,      # Larger cards, panels
    "xl": 12,     # Modals, special cards
    "full": 999,  # Avatars, circles
}

# ==========================================================
# LAYOUT DIMENSIONS
# ==========================================================

LAYOUT = {
    "sidebar_width": 240,          # Fixed sidebar width
    "sidebar_width_collapsed": 60, # Future: collapsed width
    "topbar_height": 48,           # Top navigation bar height
    "content_max_width": 1600,     # Max content width
    "content_padding": 24,         # Page content padding
}

# ==========================================================
# SHADOWS
# ==========================================================

SHADOWS = {
    "none": "none",
    "sm": "0 1px 2px rgba(0,0,0,0.05)",
    "md": "0 4px 6px rgba(0,0,0,0.1)",
    "lg": "0 10px 15px rgba(0,0,0,0.15)",
}

# ==========================================================
# STATUS COLORS
# ==========================================================

STATUS_COLORS = {
    # Project statuses
    "new_project": {"bg": "#fef3c7", "text": "#92400e", "label": "New project"},
    "site_visit_required": {"bg": "#fecaca", "text": "#991b1b", "label": "Site visit required"},
    "measured": {"bg": "#d1fae5", "text": "#065f46", "label": "Measured"},
    "quote_drafted": {"bg": "#dbeafe", "text": "#0c2340", "label": "Quote drafted"},
    "quote_sent": {"bg": "#dbeafe", "text": "#0c2340", "label": "Quote sent"},
    "quote_approved": {"bg": "#dcfce7", "text": "#15803d", "label": "Quote approved"},
    "deposit_required": {"bg": "#fef3c7", "text": "#92400e", "label": "Deposit required"},
    "ready_for_production": {"bg": "#dbeafe", "text": "#0c2340", "label": "Ready for production"},
    "scheduled": {"bg": "#d1fae5", "text": "#065f46", "label": "Scheduled"},
    "installation_in_progress": {"bg": "#fed7aa", "text": "#7c2d12", "label": "Installation in progress"},
    "awaiting_final_payment": {"bg": "#fecaca", "text": "#7f1d1d", "label": "Awaiting final payment"},
    "completed": {"bg": "#d1fae5", "text": "#15803d", "label": "Completed"},
    "warranty": {"bg": "#dbeafe", "text": "#1e40af", "label": "Warranty"},

    # Quote statuses
    "draft": {"bg": "#f3f4f6", "text": "#374151", "label": "Draft"},
    "sent": {"bg": "#dbeafe", "text": "#1e3a8a", "label": "Sent"},
    "viewed": {"bg": "#c7d2fe", "text": "#3730a3", "label": "Viewed"},
    "approved": {"bg": "#dcfce7", "text": "#166534", "label": "Approved"},
    "rejected": {"bg": "#fee2e2", "text": "#991b1b", "label": "Rejected"},
    "expired": {"bg": "#f3f4f6", "text": "#6b7280", "label": "Expired"},

    # Financial statuses
    "paid": {"bg": "#dcfce7", "text": "#15803d", "label": "Paid"},
    "overdue": {"bg": "#fecaca", "text": "#991b1b", "label": "Overdue"},
    "outstanding": {"bg": "#fef3c7", "text": "#92400e", "label": "Outstanding"},
    "pending": {"bg": "#f3f4f6", "text": "#4b5563", "label": "Pending"},
}


# ==========================================================
# USER THEME OVERRIDES
# ----------------------------------------------------------
# Snapshot the pristine defaults, then apply any overrides
# from <project_root>/user_theme.json. Only overridden keys
# are read from JSON; everything else falls back to defaults.
# The public names (COLORS, FONTS, SPACING, STATUS_COLORS)
# stay unchanged so no other module has to be edited.
# ==========================================================

import copy as _copy
import json as _json
import logging as _logging

_log = _logging.getLogger(__name__)

THEME_DEFAULTS = {
    "colors": _copy.deepcopy(COLORS),
    "fonts": {k: tuple(v) for k, v in FONTS.items()},
    "spacing": dict(SPACING),
    "status_colors": _copy.deepcopy(STATUS_COLORS),
}


def _user_theme_path():

    try:
        from core.app_paths import get_project_root
        return get_project_root() / "user_theme.json"
    except Exception:  # noqa: BLE001
        return None


def load_user_theme():
    """Return {"colors": {...}, "fonts": {...}} from disk, or {} if none."""

    path = _user_theme_path()
    if path is None or not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = _json.load(fh)
        if not isinstance(data, dict):
            _log.warning("user_theme.json root is not an object; ignoring")
            return {}
        return data
    except (OSError, ValueError) as error:
        _log.warning("Could not read user_theme.json: %s", error)
        return {}


def save_user_theme(overrides):
    """Write only-overridden keys to user_theme.json. Pass {} to clear."""

    path = _user_theme_path()
    if path is None:
        raise RuntimeError("Could not resolve project root for user_theme.json")
    if not overrides:
        try:
            if path.exists():
                path.unlink()
        except OSError as error:
            _log.warning("Could not delete user_theme.json: %s", error)
        return
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        _json.dump(overrides, fh, indent=2)
    tmp.replace(path)


def _apply_overrides():

    overrides = load_user_theme()
    if not overrides:
        return

    color_overrides = overrides.get("colors") or {}
    if isinstance(color_overrides, dict):
        for key, value in color_overrides.items():
            if key in COLORS and isinstance(value, str):
                COLORS[key] = value
            else:
                _log.warning("Ignoring unknown/invalid color override: %s", key)

    font_overrides = overrides.get("fonts") or {}
    if isinstance(font_overrides, dict):
        for key, value in font_overrides.items():
            if key not in FONTS:
                _log.warning("Ignoring unknown font override: %s", key)
                continue
            default_family, default_size, default_weight = FONTS[key]
            if isinstance(value, dict):
                family = value.get("family", default_family)
                size = value.get("size", default_size)
                weight = value.get("weight", default_weight)
            elif isinstance(value, (list, tuple)) and len(value) == 3:
                family, size, weight = value
            else:
                _log.warning("Ignoring malformed font override: %s", key)
                continue
            try:
                FONTS[key] = (str(family), int(size), str(weight))
            except (TypeError, ValueError) as error:
                _log.warning("Bad font override %s: %s", key, error)


_apply_overrides()

