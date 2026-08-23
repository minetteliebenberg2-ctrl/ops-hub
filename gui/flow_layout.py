# ==========================================================
# FC Hub - Flow Layout Helper
# ----------------------------------------------------------
# Purpose:
# Lay out already-created child widgets left-to-right within a
# container, wrapping onto additional rows when there isn't enough
# width to fit them all on one line - so a widget is pushed to the
# next row rather than ever being cut off or hidden past the
# window's visible edge. Shared by gui/entity_table.py's action-
# button rows and any other fixed-width header row that grows over
# time (e.g. QuoteDetailWindow's PO/VAT/Reg/Bill To/Change Site row,
# which needed a manual window resize to reach "Change Site" before
# this - found 2026-08-07 while she was testing).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================


def reflow_widgets(container, widgets, spacing=8, row_spacing=8):
    """Grid `widgets` (already created, not yet placed) into `container`
    left-to-right, wrapping onto a new row whenever the next widget
    would overflow the container's current width. Re-runs automatically
    whenever the container is resized."""

    def reflow(_event=None):
        available_width = container.winfo_width()
        if available_width <= 1:
            return
        x = 0
        row = 0
        col = 0
        for widget in widgets:
            widget.update_idletasks()
            widget_width = widget.winfo_reqwidth()
            if col > 0 and x + widget_width > available_width:
                row += 1
                col = 0
                x = 0
            widget.grid(row=row, column=col, padx=(0, spacing), pady=(0, row_spacing), sticky="w")
            x += widget_width + spacing
            col += 1

    container.bind("<Configure>", reflow)
    reflow()  # first pass in case <Configure> doesn't fire before the caller needs the row's height


__all__ = ["reflow_widgets"]
