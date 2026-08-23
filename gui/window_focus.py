# ==========================================================
# FC Hub - Window Focus Fix
# ----------------------------------------------------------
# Purpose:
# Every popup window in FC Hub (Quote editor, Statement, Hub
# launchers, ...) is a customtkinter CTkToplevel opened from another
# Toplevel (a Hub window), not from the root. On Windows, a Toplevel
# created from another Toplevel does not reliably raise itself above
# its parent - it can open behind it, looking like nothing happened.
#
# Patching every affected window class individually isn't practical
# (three dozen+ classes across a dozen modules). Instead this patches
# customtkinter.CTkToplevel itself, once, at startup - every popup
# site-wide gets the fix automatically, including any added later.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import customtkinter as ctk

_installed = False


def install():
    """Make every CTkToplevel raise itself above its parent on open.
    Call once, early in launcher startup, before any window is created."""

    global _installed
    if _installed:
        return
    _installed = True

    original_init = ctk.CTkToplevel.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.after(50, lambda: _bring_to_front(self))

    ctk.CTkToplevel.__init__ = patched_init


def _bring_to_front(window):

    try:
        if not window.winfo_exists():
            return
        window.lift()
        window.focus_force()
        window.attributes("-topmost", True)
        window.after(150, lambda: _clear_topmost(window))
    except Exception:
        pass


def _clear_topmost(window):

    try:
        if window.winfo_exists():
            window.attributes("-topmost", False)
    except Exception:
        pass
