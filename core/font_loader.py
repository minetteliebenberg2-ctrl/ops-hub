# ==========================================================
# FC Hub - Runtime font loader
# ----------------------------------------------------------
# The bundled Lato TTFs in assets/fonts/ are used for PDF and DOCX
# output. Tk / customtkinter can also render them at runtime, but only
# if Windows knows the font family exists in the current process. On
# machines where Lato isn't installed system-wide, requesting
# ("Lato", 12, "normal") silently falls back to the Tk default -
# which is visibly worse than Segoe UI.
#
# AddFontResourceExW with FR_PRIVATE registers a TTF for THIS process
# only (nothing installed system-wide, no admin required, cleared when
# the process exits). Called once from launcher.py before any Tk
# window opens.
# ==========================================================

from __future__ import annotations

import sys
from pathlib import Path

from core.app_paths import get_project_root

_FR_PRIVATE = 0x10


def register_bundled_fonts() -> list[str]:
    """Register every .ttf under assets/fonts/ with the current process.

    Returns the list of TTF paths that registered successfully. Silently
    returns an empty list on non-Windows platforms or if the assets
    directory is missing - the app must still start on machines with no
    bundled fonts, using whatever font family the design tokens fall
    back to.
    """
    if sys.platform != "win32":
        return []

    fonts_dir = get_project_root() / "assets" / "fonts"
    if not fonts_dir.is_dir():
        return []

    try:
        import ctypes
        gdi32 = ctypes.windll.gdi32
    except Exception:
        return []

    registered: list[str] = []
    for ttf in sorted(fonts_dir.glob("*.ttf")):
        try:
            added = gdi32.AddFontResourceExW(str(ttf), _FR_PRIVATE, 0)
        except Exception:
            continue
        if added:
            registered.append(str(ttf))
    return registered
