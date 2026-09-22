# ==========================================================
# Maximise helper
# ----------------------------------------------------------
# state("zoomed") is silently ignored on some PCs when called before the
# window is mapped (CTk re-applies its own geometry after scaling). This
# retries after the window is drawn and falls back to sizing the window
# to the screen work area if Windows still refuses to zoom it.
# ==========================================================


def maximise(window):
    try:
        window.state("zoomed")
    except Exception:
        pass
    window.after(150, lambda: _fallback(window))


def _fallback(window):
    try:
        if not window.winfo_exists() or window.state() == "zoomed":
            return
        width, height = window.winfo_screenwidth(), window.winfo_screenheight()
        window.geometry(f"{width}x{height - 48}+0+0")
    except Exception:
        pass


def maximise_on_launch(window):
    """Call from startup: retry once the window is actually on screen."""
    for delay in (200, 800):
        window.after(delay, lambda: maximise(window))
