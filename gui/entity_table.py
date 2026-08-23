# ==========================================================
# FC Hub - Shared Entity Table
# ----------------------------------------------------------
# Purpose:
# Treeview + action-button-row builder for record lists,
# shared across modules (CRM, Settings, ...).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from tkinter import ttk

import customtkinter as ctk

from gui.flow_layout import reflow_widgets


def _build_action_buttons(container, action_specs):
    """Lay out action buttons left-to-right, wrapping onto additional
    rows when the container isn't wide enough to fit them all on one
    line - a button is pushed to the next row rather than ever being
    cut off or hidden. Found necessary once an action row grew past
    ~5-6 buttons (e.g. CRM's Sites tab after adding Site Plan/Job
    Cards) and started overflowing narrower windows with no way to
    reach the missing buttons at all."""

    buttons = [ctk.CTkButton(container, text=label, command=command) for label, command in action_specs]
    reflow_widgets(container, buttons)


def build_entity_table(parent, columns, action_specs, height=18):
    """Build a labelled action-button row plus a scrollable Treeview."""

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    action_row = ctk.CTkFrame(parent)
    action_row.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

    _build_action_buttons(action_row, action_specs)

    frame = ctk.CTkFrame(parent)
    frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_rowconfigure(0, weight=1)

    table = ttk.Treeview(
        frame,
        columns=columns,
        show="tree headings",
        selectmode="extended",
        height=height,
    )

    table.heading("#0", text="Name")
    table.column("#0", width=240, stretch=True)

    for column in columns:
        table.heading(column, text=column)
        table.column(column, width=130, stretch=True)

    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)

    table.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    return table


__all__ = ["build_entity_table"]
