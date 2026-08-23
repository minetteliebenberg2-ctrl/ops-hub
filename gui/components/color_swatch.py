# ==========================================================
# FC Hub - Color Swatch
# ----------------------------------------------------------
# Small square showing a colour with a border. Not
# clickable; used by the Settings Appearance panel next to
# each colour-token row.
# ==========================================================

import customtkinter as ctk

from gui.design_tokens import COLORS


class ColorSwatch(ctk.CTkFrame):

    def __init__(self, master, color, size=24, **kwargs):

        super().__init__(
            master,
            width=size,
            height=size,
            fg_color=color,
            border_width=1,
            border_color=COLORS["border_strong"],
            corner_radius=4,
            **kwargs,
        )
        self.grid_propagate(False)
        self.pack_propagate(False)
        self._color = color

    def set_color(self, color):

        self._color = color
        self.configure(fg_color=color)


__all__ = ["ColorSwatch"]
