# ==========================================================
# FC Hub - Styling (compatibility shim)
# ----------------------------------------------------------
# All live tokens now live in gui.design_tokens.
# This module re-exports them so existing imports still work.
# ==========================================================

from gui.design_tokens import COLORS, FONTS, SPACING  # noqa: F401

SHADOWS = {
    "sm": "0 1px 2px rgba(0,0,0,0.05)",
    "md": "0 4px 6px rgba(0,0,0,0.1)",
    "lg": "0 10px 15px rgba(0,0,0,0.1)",
    "xl": "0 20px 25px rgba(0,0,0,0.1)",
}
