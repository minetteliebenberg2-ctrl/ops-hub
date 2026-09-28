"""The Social Media page.

The poster studio itself is a web page served on loopback - see the
docstring in core/social_studio.py for why it is not a file:// document.
This page starts that server, opens the browser at it, and gives her the
folder her exports land in.
"""

import webbrowser

import customtkinter as ctk
from tkinter import messagebox as mb

from core.crm_service import CRMService
from core.site_image_service import SiteImageService
from core.social_studio import (
    GalleryIndex, StudioServer, exports_root, month_folder, open_folder,
)
from gui.design_tokens import COLORS


TEXT = COLORS["text_primary"]
MUTED = COLORS["text_secondary"]
GREEN = COLORS["accent_primary"]

TIKTOK_UPLOAD = "https://www.tiktok.com/tiktokstudio/upload"
META_SUITE = "https://business.facebook.com/latest/composer"

BLURB = (
    "The studio opens in your browser. Pick a size and a layout, click a photo slot to "
    "pull a picture out of the Gallery or off your PC, type over the text, then save."
    "\n\n"
    "Your name, phone and website come from Settings - Business Settings."
    "\n\n"
    "Every poster is filed under Social by month, so nothing gets lost and nothing is "
    "overwritten."
)

POSTING = (
    "Facebook and Instagram post together from Meta Business Suite - one schedule, both "
    "pages, free. TikTok needs its own upload page. Neither platform allows a desktop app "
    "to post on your behalf without a registered developer app and a business account, so "
    "the studio saves the picture and takes you to the right page.\n\n"
    "TikTok and Reels want a 1080x1920 video. The studio makes the branded cover frame; "
    "the clip itself still gets cut in CapCut or on your phone."
)


class SocialMediaModuleWindow(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["surface_primary"])

        self.server = None
        self._build_ui()

    # ----------------------------------------------------------

    def _build_ui(self):

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(
            wrap, text="Social Media", font=("Segoe UI", 20, "bold"), text_color=TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            wrap, text="Branded posters for Instagram, Facebook, LinkedIn and TikTok.",
            font=("Segoe UI", 12), text_color=MUTED,
        ).pack(anchor="w", pady=(2, 18))

        card = ctk.CTkFrame(wrap, fg_color=COLORS["surface_tertiary"], corner_radius=8)
        card.pack(fill="x")

        ctk.CTkLabel(
            card, text=BLURB, font=("Segoe UI", 12), text_color=TEXT,
            justify="left", wraplength=620,
        ).pack(anchor="w", padx=20, pady=(18, 14))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(anchor="w", padx=20, pady=(0, 18))

        ctk.CTkButton(
            row, text="Open poster studio", width=190, height=38,
            fg_color=GREEN, hover_color=COLORS["accent_hover"], font=("Segoe UI", 12, "bold"),
            command=self.open_studio,
        ).pack(side="left")

        ctk.CTkButton(
            row, text="Open this month's folder", width=180, height=38,
            fg_color="transparent", border_width=1, border_color=COLORS["border_default"],
            text_color=TEXT, hover_color=COLORS["accent_light"],
            command=lambda: open_folder(month_folder()),
        ).pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            row, text="All posters", width=110, height=38,
            fg_color="transparent", border_width=1, border_color=COLORS["border_default"],
            text_color=TEXT, hover_color=COLORS["accent_light"],
            command=lambda: open_folder(exports_root()),
        ).pack(side="left", padx=(10, 0))

        self.status = ctk.CTkLabel(
            wrap, text=str(exports_root()), font=("Segoe UI", 11), text_color=MUTED,
        )
        self.status.pack(anchor="w", pady=(8, 20))

        # ------------------------------------------------------

        posting = ctk.CTkFrame(wrap, fg_color=COLORS["surface_tertiary"], corner_radius=8)
        posting.pack(fill="x")

        ctk.CTkLabel(
            posting, text="Posting it", font=("Segoe UI", 14, "bold"), text_color=TEXT,
        ).pack(anchor="w", padx=20, pady=(16, 6))
        ctk.CTkLabel(
            posting, text=POSTING, font=("Segoe UI", 12), text_color=TEXT,
            justify="left", wraplength=620,
        ).pack(anchor="w", padx=20, pady=(0, 12))

        links = ctk.CTkFrame(posting, fg_color="transparent")
        links.pack(anchor="w", padx=20, pady=(0, 18))

        for label, url in (
            ("Meta Business Suite", META_SUITE),
            ("TikTok upload", TIKTOK_UPLOAD),
        ):
            ctk.CTkButton(
                links, text=label, width=150, height=32,
                fg_color="transparent", border_width=1, border_color=COLORS["border_default"],
                text_color=TEXT, hover_color=COLORS["accent_light"], font=("Segoe UI", 11),
                command=lambda u=url: webbrowser.open(u),
            ).pack(side="left", padx=(0, 10))

    # ----------------------------------------------------------

    def open_studio(self):
        """Start the loopback server the first time, then open the browser at it."""

        try:
            if self.server is None:
                gallery = GalleryIndex(CRMService(), SiteImageService())
                self.server = StudioServer(gallery=gallery)
                self.server.start()
            else:
                # Re-index so photos added since the last open show up.
                self.server.gallery.build()
        except Exception as error:
            mb.showerror("Poster studio", "The studio could not start.\n\n{}".format(error))
            return

        count = len(self.server.gallery.entries)
        self.status.configure(
            text="Studio running on {}  -  {} Gallery photo{} available".format(
                self.server.url, count, "" if count == 1 else "s")
        )
        webbrowser.open(self.server.url)

    def destroy(self):
        """The loopback server must not outlive the page."""

        if self.server is not None:
            self.server.stop()
            self.server = None
        super().destroy()
