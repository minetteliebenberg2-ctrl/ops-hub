"""
ClickableCard - a CTkFrame that reliably fires a click callback.

Why this exists:
    CustomTkinter's CTkFrame is a composite widget: its `.bind()` routes to an
    internal Canvas, and any nested CTkLabel/CTkFrame child intercepts its own
    <Button-1> before it can bubble up. Manually calling `.bind()` on every
    named child is brittle - miss one label or add a new child and clicks
    silently stop working (this bit the CRM customer list twice already).

    ClickableCard walks the entire descendant tree AND probes each widget's
    internal CTk parts (_canvas, _text_label, _entry) after the card is fully
    built, binding <Button-1> and setting a hand cursor everywhere reachable.
    Callers just build children normally, then call `.activate()` once at the
    end.
"""

from __future__ import annotations

import tkinter
import traceback
from typing import Callable, Optional

import customtkinter as ctk


class ClickableCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_click: Callable[[], None],
        *,
        hover_color: Optional[str] = None,
        **frame_kwargs,
    ):
        super().__init__(master, **frame_kwargs)
        self._on_click = on_click
        self._hover_color = hover_color
        self._base_fg_color = frame_kwargs.get("fg_color", None)

    # ------------------------------------------------------------------
    def _handle_click(self, _event=None):
        try:
            self._on_click()
        except Exception:
            traceback.print_exc()
        return "break"

    def _on_enter(self, _event=None):
        if self._hover_color is not None:
            try:
                self.configure(fg_color=self._hover_color)
            except Exception:
                pass

    def _on_leave(self, _event=None):
        if self._hover_color is not None and self._base_fg_color is not None:
            try:
                self.configure(fg_color=self._base_fg_color)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _bind_widget(self, widget):
        # Use tkinter.Misc.bind directly to bypass CTk's bind override,
        # which redirects to an inner canvas and makes event_generate on
        # the outer widget silently no-op.
        try:
            tkinter.Misc.bind(widget, "<Button-1>", self._handle_click, add="+")
        except Exception:
            pass
        try:
            widget.configure(cursor="hand2")
        except Exception:
            pass
        # Also bind on CTk internal parts so real mouse clicks (which land
        # on the inner canvas/label) are caught.
        for attr in ("_canvas", "_text_label", "_entry"):
            inner = getattr(widget, attr, None)
            if inner is None:
                continue
            try:
                tkinter.Misc.bind(inner, "<Button-1>", self._handle_click, add="+")
            except Exception:
                pass
            try:
                inner.configure(cursor="hand2")
            except Exception:
                pass

    def _walk(self, widget):
        self._bind_widget(widget)
        try:
            children = widget.winfo_children()
        except Exception:
            children = []
        for child in children:
            self._walk(child)

    def activate(self):
        """Bind <Button-1> across every reachable descendant + inner CTk part."""
        self._walk(self)
        if self._hover_color is not None:
            try:
                self.bind("<Enter>", self._on_enter, add="+")
                self.bind("<Leave>", self._on_leave, add="+")
            except Exception:
                pass
