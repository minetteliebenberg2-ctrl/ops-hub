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

import re

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
        self.after(150, lambda: _bring_to_front(self))
        self.after(350, lambda: _bring_to_front(self))

    ctk.CTkToplevel.__init__ = patched_init

    # CustomTkinter multiplies every geometry by the display's widget
    # scaling. On Minette's 1536x864 screen at 1.25, geometry("1050x750")
    # becomes 1312x938 real pixels - 74px taller than the screen, so the
    # bottom of the window is off the edge and the content reads as "cut
    # off". Measured in FC Hub on 2026-10-05, where 27 windows asked for
    # more than her screen can show; the window count here has not been
    # measured, but the scaling cause is the same display and the same
    # CustomTkinter version.
    #
    # Patched in the same place and for the same reason as the raise
    # above: fixing 27 call sites by hand would leave the 28th broken.
    # This only ever makes a window smaller, never bigger, so a window
    # that already fits is untouched.
    original_geometry = ctk.CTkToplevel.geometry

    def patched_geometry(self, geometry_string=None):
        if geometry_string:
            geometry_string = _clamp_geometry(self, geometry_string)
        return original_geometry(self, geometry_string)

    ctk.CTkToplevel.geometry = patched_geometry

    # customtkinter 6.0.0 bug: CTkScrollbar._on_motion reads
    # _motion_center_offset, but only _clicked ever sets it. Dragging a
    # scrollbar that was never clicked first raises AttributeError and
    # prints a traceback on every mouse move. A class-level default fixes
    # it; _clicked still sets a real per-instance value when it runs.
    if not hasattr(ctk.CTkScrollbar, "_motion_center_offset"):
        ctk.CTkScrollbar._motion_center_offset = 0


_GEOMETRY = re.compile(r"^(?:(\d+)x(\d+))?(?:([+-]\d+)([+-]\d+))?$")

# Room for the taskbar and the window's own title bar.
_CHROME_HEIGHT = 70
_CHROME_WIDTH = 16


def _clamp_geometry(window, geometry_string):
    """Shrink a WxH request so the window still fits on screen once
    CustomTkinter has applied display scaling. Position-only strings and
    anything unrecognised pass straight through untouched."""

    try:
        match = _GEOMETRY.match(geometry_string.strip())
        if match is None or match.group(1) is None:
            return geometry_string

        width, height = int(match.group(1)), int(match.group(2))

        try:
            scaling = ctk.ScalingTracker.get_window_scaling(window) or 1.0
        except Exception:
            scaling = 1.0

        max_width = int((window.winfo_screenwidth() - _CHROME_WIDTH) / scaling)
        max_height = int((window.winfo_screenheight() - _CHROME_HEIGHT) / scaling)

        new_width = min(width, max_width)
        new_height = min(height, max_height)
        if (new_width, new_height) == (width, height):
            return geometry_string

        position = ""
        if match.group(3) is not None:
            position = f"{match.group(3)}{match.group(4)}"
        return f"{new_width}x{new_height}{position}"
    except Exception:
        # A window that opens slightly too big beats one that doesn't open.
        return geometry_string


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
