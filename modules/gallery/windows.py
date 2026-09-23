# ==========================================================
# FC Hub - Gallery Windows
# ----------------------------------------------------------
# Purpose:
# Image galleries with EXIF metadata, project organization, and phase tracking.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import getpass
import os
from tkinter import filedialog, messagebox
from pathlib import Path
import customtkinter as ctk

from core.crm_service import CRMService
from core.site_image_service import SiteImageService
from modules.gallery.services import GalleryService, ImageMetadata


def current_actor():

    try:
        return getpass.getuser()
    except Exception:
        return ""

from gui.design_tokens import COLORS, FONTS

THEME_DARK_GREY = COLORS["surface_primary"]
THEME_SURFACE = COLORS["surface_secondary"]
THEME_SURFACE_LIGHT = COLORS["surface_tertiary"]
THEME_TEXT_PRIMARY = COLORS["text_primary"]
THEME_TEXT_SECONDARY = COLORS["text_secondary"]


class GalleryPanel(ctk.CTkFrame):
    """Gallery utilities as an embeddable frame - extracted from
    GalleryHub 2026-08-07, same reasoning as ProposalsPanel (see its
    docstring): used both as its own Toplevel (via GalleryHub,
    unchanged) and as a tab inside
    modules/quotes/windows.py:QuotesMainWindow."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=THEME_DARK_GREY)

        ctk.CTkLabel(
            self,
            text="Organize project photos with EXIF metadata and phase tracking.",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
            justify="center",
        ).pack(pady=(20, 20), padx=20)

        button_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        button_frame.pack(pady=20, padx=20, fill="both", expand=True)

        buttons = [
            ("📁 Project Gallery", self.open_project_gallery),
            ("📸 Photo Uploader", self.open_uploader),
            ("🏷️ Browse by Tag", self.open_tags),
            ("📊 Gallery Stats", self.open_stats),
            ("⚙️ Settings", self.open_settings),
        ]

        for label, command in buttons:
            ctk.CTkButton(
                button_frame,
                text=label,
                command=command,
                height=50,
                font=("Segoe UI", 12),
                fg_color=COLORS["accent_primary"],
                hover_color=COLORS["accent_hover"],
            ).pack(pady=8, fill="x")

        self.gallery_window = None
        self.uploader_window = None
        self.open_windows = set()

    def open_project_gallery(self):
        if self.gallery_window is None or not self.gallery_window.winfo_exists():
            self.gallery_window = ProjectGalleryWindow(self)
        else:
            self.gallery_window.lift()
            self.gallery_window.focus()

    def open_uploader(self):
        if self.uploader_window is None or not self.uploader_window.winfo_exists():
            self.uploader_window = PhotoUploaderWindow(self)
        else:
            self.uploader_window.lift()
            self.uploader_window.focus()

    def open_tags(self):
        self.open_project_gallery()

    def open_stats(self):
        GalleryStatsWindow(self)

    def open_settings(self):
        messagebox.showinfo("Settings", "Gallery settings — nothing to configure yet.")


class GalleryHub(ctk.CTkToplevel):
    """Dockable hub launcher for Gallery utilities - thin Toplevel
    wrapper around GalleryPanel (see its docstring). Still used by
    modules/gallery/module.py's own GalleryModuleWindow entry point;
    QuotesMainWindow embeds GalleryPanel directly instead.

    Must be a Toplevel, not a second ctk.CTk() root - see the matching
    comment on ProposalsHub for why."""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Gallery Hub")
        self.geometry("500x420")
        self.resizable(False, False)
        self.configure(fg_color=THEME_DARK_GREY)

        ctk.CTkLabel(
            self,
            text="Gallery Hub",
            font=("Segoe UI", 24, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(20, 20))

        self.panel = GalleryPanel(self)
        self.panel.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        ctk.CTkButton(
            self,
            text="Close Hub",
            command=self.destroy,
            width=200,
            fg_color=COLORS["surface_tertiary"],
            hover_color=COLORS["border_strong"],
            text_color=COLORS["text_primary"],
        ).pack(pady=(0, 20))


class ProjectGalleryWindow(ctk.CTkToplevel):
    """Real per-customer photo gallery.

    Replaces the original wireframe (fake "Project 1/2/3" dropdown,
    "[images will display here]" labels, buttons wired to nothing) with
    the actual photo pipeline already used by Site Visit -
    SiteImageService, which stores processed files in each customer's
    own client folder. Reused deliberately rather than building a second
    image store, so there is one place photos live.
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Project Gallery")
        self.geometry("1100x720")
        self.minsize(820, 560)
        self.configure(fg_color=THEME_DARK_GREY)

        self.crm_service = CRMService()
        self.image_service = SiteImageService()

        self._customers = []
        self._images = []
        self._selected_customer = None
        self._thumbnails = []
        self._selected_ids = set()
        self._check_vars = {}

        self._build_ui()
        self.refresh()

        self.bind("<Control-a>", self._on_select_all_shortcut)
        self.bind("<Control-A>", self._on_select_all_shortcut)
        self.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, event):
        # Only react to this window's own destroy, not a child widget's.
        if event.widget is self:
            self.unbind("<Control-a>")
            self.unbind("<Control-A>")

    def _on_select_all_shortcut(self, event=None):
        if self._is_text_entry_widget(event.widget if event is not None else None):
            return None
        if self._is_text_entry_widget(self.focus_get()):
            return None
        self._select_all()
        return "break"

    @staticmethod
    def _is_text_entry_widget(widget):
        if widget is None:
            return False
        try:
            widget_class = widget.winfo_class()
        except Exception:
            widget_class = ""
        if widget_class in ("Entry", "TEntry", "Text", "TCombobox", "ComboBox"):
            return True
        type_name = type(widget).__name__
        return "Entry" in type_name or "Textbox" in type_name or "ComboBox" in type_name

    def _build_ui(self):

        main_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        top_row = ctk.CTkFrame(main_frame, fg_color=THEME_SURFACE)
        top_row.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            top_row, text="Customer:", font=("Segoe UI", 11), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="left", padx=(10, 4), pady=10)

        self.customer_var = ctk.StringVar(value="")
        self.customer_menu = ctk.CTkOptionMenu(
            top_row, values=[""], variable=self.customer_var,
            command=lambda _value: self._on_customer_change(), width=220,
        )
        self.customer_menu.pack(side="left", padx=5)

        ctk.CTkButton(top_row, text="Refresh", command=self.refresh, width=90).pack(side="right", padx=10, pady=10)
        ctk.CTkButton(top_row, text="Add Photos", command=self._add_photos, width=110).pack(side="right", pady=10)

        filter_row = ctk.CTkFrame(main_frame, fg_color=THEME_SURFACE)
        filter_row.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            filter_row, text="Album:", font=("Segoe UI", 11), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="left", padx=(10, 4), pady=10)
        self.album_var = ctk.StringVar(value="All")
        self.album_menu = ctk.CTkOptionMenu(
            filter_row, values=["All"], variable=self.album_var,
            command=lambda _value: self._load_images(), width=180,
        )
        self.album_menu.pack(side="left", padx=5)

        ctk.CTkLabel(
            filter_row, text="Tag:", font=("Segoe UI", 11), text_color=THEME_TEXT_PRIMARY,
        ).pack(side="left", padx=(16, 4), pady=10)
        self.tag_var = ctk.StringVar(value="All")
        self.tag_menu = ctk.CTkOptionMenu(
            filter_row, values=["All"], variable=self.tag_var,
            command=lambda _value: self._load_images(), width=180,
        )
        self.tag_menu.pack(side="left", padx=5)

        self.count_label = ctk.CTkLabel(
            main_frame, text="", font=("Segoe UI", 11, "bold"), text_color=THEME_TEXT_PRIMARY,
        )
        self.count_label.pack(anchor="w", pady=(0, 6))

        selection_row = ctk.CTkFrame(main_frame, fg_color=THEME_SURFACE)
        selection_row.pack(fill="x", pady=(0, 12))

        ctk.CTkButton(
            selection_row, text="Select All", width=100, command=self._select_all,
        ).pack(side="left", padx=(10, 5), pady=10)
        ctk.CTkButton(
            selection_row, text="Clear Selection", width=120, command=self._clear_selection,
        ).pack(side="left", padx=5, pady=10)
        self.tag_selected_btn = ctk.CTkButton(
            selection_row, text="Tag Selected (0)", width=140, state="disabled",
            command=self._open_bulk_tag_dialog,
        )
        self.tag_selected_btn.pack(side="left", padx=5, pady=10)

        self.grid_frame = ctk.CTkScrollableFrame(main_frame, fg_color=THEME_SURFACE)
        self.grid_frame.pack(fill="both", expand=True)

    def refresh(self):

        self._customers = [c for c in self.crm_service.list_customers() if c.name]
        names = ["All Clients"] + [c.name for c in self._customers]
        self.customer_menu.configure(values=names)
        if self.customer_var.get() not in names:
            self.customer_var.set("All Clients")
        self._refresh_filters()
        self._load_images()

    def _on_customer_change(self):
        self._refresh_filters()
        self._load_images()

    def _refresh_filters(self):
        customer = self._current_customer()
        if customer is None:
            # "All Clients" — disable album/tag filters
            self.album_menu.configure(values=["All"], state="disabled")
            self.tag_menu.configure(values=["All"], state="disabled")
            self.album_var.set("All")
            self.tag_var.set("All")
            return

        self.album_menu.configure(state="normal")
        self.tag_menu.configure(state="normal")
        albums = ["All"] + self.image_service.list_albums(customer.id)
        tags = ["All"] + self.image_service.list_tags(customer.id)
        self.album_menu.configure(values=albums)
        self.tag_menu.configure(values=tags)
        if self.album_var.get() not in albums:
            self.album_var.set("All")
        if self.tag_var.get() not in tags:
            self.tag_var.set("All")

    def _current_customer(self):
        """Returns the selected Customer object, or None when 'All Clients' is selected."""
        name = self.customer_var.get()
        if name == "All Clients":
            return None
        for customer in self._customers:
            if customer.name == name:
                return customer
        return None

    def _load_images(self):

        for child in self.grid_frame.winfo_children():
            child.destroy()
        self._thumbnails = []
        self._selected_ids = set()
        self._check_vars = {}

        customer = self._current_customer()
        self._selected_customer = customer

        if customer is None:
            # All Clients — aggregate across every customer
            all_images = []
            customer_map = {}
            for c in self._customers:
                for img in self.image_service.list_for_customer(c.id):
                    if not getattr(img, "archived_at", ""):
                        all_images.append(img)
                        customer_map[img.id] = c
            self._images = all_images
            self._customer_map = customer_map
            self.count_label.configure(text=f"{len(self._images)} photo(s) across all clients")
        else:
            self._customer_map = {}
            images = [
                image for image in self.image_service.list_for_customer(customer.id)
                if not getattr(image, "archived_at", "")
            ]
            album_filter = self.album_var.get()
            if album_filter and album_filter != "All":
                images = [img for img in images if img.album == album_filter]
            tag_filter = self.tag_var.get()
            if tag_filter and tag_filter != "All":
                images = [img for img in images if tag_filter in img.tag_list]
            self._images = images
            self.count_label.configure(text=f"{len(self._images)} photo(s) for {customer.name}")

        if not self._images:
            ctk.CTkLabel(
                self.grid_frame,
                text="No photos match. Use \"Add Photos\" to upload some, or clear the filters.",
                text_color=THEME_TEXT_SECONDARY, font=("Segoe UI", 11),
            ).pack(pady=40)
            return

        columns = 4
        for index, image in enumerate(self._images):
            cell = ctk.CTkFrame(self.grid_frame, fg_color=THEME_SURFACE_LIGHT)
            cell.grid(row=index // columns, column=index % columns, padx=6, pady=6, sticky="nsew")
            img_customer = self._customer_map.get(image.id, customer)
            self._build_thumbnail(cell, image, img_customer)

        for column in range(columns):
            self.grid_frame.grid_columnconfigure(column, weight=1)

    def _build_thumbnail(self, cell, image, customer):

        check_var = ctk.BooleanVar(value=image.id in self._selected_ids)
        self._check_vars[image.id] = check_var
        ctk.CTkCheckBox(
            cell, text="Select", variable=check_var, width=20, height=20, font=("Segoe UI", 9),
            command=lambda img_id=image.id, var=check_var: self._on_toggle_select(img_id, var),
        ).pack(anchor="w", padx=6, pady=(6, 0))

        path = self.image_service.image_path(image, customer)
        thumbnail = None

        if path and Path(path).is_file():
            try:
                from PIL import Image as PILImage

                pil = PILImage.open(path)
                pil.thumbnail((200, 150))
                thumbnail = ctk.CTkImage(light_image=pil, dark_image=pil, size=pil.size)
                self._thumbnails.append(thumbnail)
            except Exception:
                thumbnail = None

        if thumbnail is not None:
            label = ctk.CTkLabel(cell, image=thumbnail, text="")
        else:
            label = ctk.CTkLabel(
                cell, text="(preview unavailable)", text_color=THEME_TEXT_SECONDARY, font=("Segoe UI", 9),
            )
        label.pack(padx=6, pady=(6, 2))
        label.bind("<Double-Button-1>", lambda _event, p=path: self._open_file(p))

        caption_text = (image.caption or image.original_filename or "")[:34]
        if image.album:
            caption_text += f"\n📁 {image.album}"
        if image.tags:
            caption_text += f"\n🏷️ {image.tags}"
        ctk.CTkLabel(
            cell, text=caption_text,
            text_color=THEME_TEXT_SECONDARY, font=("Segoe UI", 9), wraplength=190, justify="left",
        ).pack(padx=6, pady=(0, 2))
        if self.customer_var.get() == "All Clients" and customer:
            ctk.CTkLabel(
                cell, text=f"👤 {customer.name}",
                text_color=THEME_TEXT_PRIMARY, font=("Segoe UI", 9, "bold"), wraplength=190, justify="left",
            ).pack(padx=6, pady=(0, 4))

        btn_row = ctk.CTkFrame(cell, fg_color="transparent")
        btn_row.pack(padx=6, pady=(0, 6), fill="x")
        ctk.CTkButton(
            btn_row, text="Edit", width=60, height=22, font=("Segoe UI", 9),
            command=lambda img=image: self._edit_image(img, customer),
        ).pack(side="left")
        ctk.CTkButton(
            btn_row, text="Delete", width=60, height=22, font=("Segoe UI", 9),
            fg_color=COLORS["danger"], hover_color=COLORS["danger"],
            command=lambda img=image: self._delete_image(img),
        ).pack(side="right")

    def _edit_image(self, image, customer):
        EditPhotoDialog(self, image, customer, self.image_service, on_saved=self._load_images)

    def _delete_image(self, image):
        if not messagebox.askyesno(
            "Delete Photo",
            f"Remove \"{image.caption or image.original_filename}\" from the gallery?\n\n"
            "The file stays in the client folder; this just hides it here.",
            parent=self,
        ):
            return
        try:
            self.image_service.archive_image(image.id, current_actor(), "Deleted from Gallery")
        except Exception as error:
            messagebox.showerror("Gallery", str(error), parent=self)
            return
        self._refresh_filters()
        self._load_images()

    def _open_file(self, path):

        if not path or not Path(path).is_file():
            return
        try:
            os.startfile(str(path))
        except Exception as error:
            messagebox.showerror("Gallery", f"Could not open the file: {error}", parent=self)

    def _add_photos(self):

        customer = self._current_customer()
        if customer is None:
            messagebox.showwarning("Gallery", "Select a customer first.", parent=self)
            return

        filenames = filedialog.askopenfilenames(
            title="Add Photos",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.gif *.bmp"), ("All Files", "*.*")],
        )
        if not filenames:
            return

        added, failures, sizes = 0, [], []
        for filename in filenames:
            try:
                orig_kb = os.path.getsize(filename) / 1024
                img = self.image_service.upload_image(filename, customer, current_actor())
                saved_kb = (img.file_size or 0) / 1024
                sizes.append(f"{Path(filename).name}: {orig_kb:.0f} KB -> {saved_kb:.0f} KB ({img.width}x{img.height})")
                added += 1
            except Exception as error:
                failures.append(f"{Path(filename).name}: {error}")

        self._load_images()

        size_info = "\n".join(sizes[:10]) if sizes else ""
        if failures:
            messagebox.showwarning(
                "Gallery",
                f"Added {added} photo(s).\n\n{size_info}\n\nCould not add:\n" + "\n".join(failures[:5]),
                parent=self,
            )
        else:
            messagebox.showinfo("Gallery", f"Added {added} photo(s) to {customer.name}.\n\n{size_info}", parent=self)


    # -------------------- bulk selection --------------------

    def _on_toggle_select(self, image_id, var):
        if var.get():
            self._selected_ids.add(image_id)
        else:
            self._selected_ids.discard(image_id)
        self._update_tag_selected_button()

    def _select_all(self):
        """Select every photo currently visible under the active filters."""
        for image in self._images:
            self._selected_ids.add(image.id)
            var = self._check_vars.get(image.id)
            if var is not None:
                var.set(True)
        self._update_tag_selected_button()

    def _clear_selection(self):
        self._selected_ids = set()
        for var in self._check_vars.values():
            var.set(False)
        self._update_tag_selected_button()

    def _update_tag_selected_button(self):
        count = len(self._selected_ids)
        self.tag_selected_btn.configure(
            text=f"Tag Selected ({count})",
            state="normal" if count else "disabled",
        )

    def _open_bulk_tag_dialog(self):
        if not self._selected_ids:
            return
        selected_images = [img for img in self._images if img.id in self._selected_ids]
        BulkTagDialog(self, selected_images, self.image_service, on_saved=self._on_bulk_tag_saved)

    def _on_bulk_tag_saved(self):
        self._refresh_filters()
        self._load_images()


class BulkTagDialog(ctk.CTkToplevel):
    """Add tags to multiple selected photos at once (additive, not replace)."""

    def __init__(self, parent, images, image_service, on_saved=None):
        super().__init__(parent.winfo_toplevel())
        self.title("Tag Selected Photos")
        self.geometry("420x220")
        self.resizable(False, False)
        self.configure(fg_color=THEME_DARK_GREY)

        self.images = images
        self.image_service = image_service
        self.on_saved = on_saved

        ctk.CTkLabel(
            self, text=f"Add tags to {len(images)} photo(s)", font=("Segoe UI", 12, "bold"),
            text_color=THEME_TEXT_PRIMARY, wraplength=380,
        ).pack(pady=(16, 12), padx=20)

        ctk.CTkLabel(
            self, text="Tags (comma-separated)", font=("Segoe UI", 10),
            text_color=THEME_TEXT_SECONDARY, anchor="w",
        ).pack(fill="x", padx=20)
        self.tags_entry = ctk.CTkEntry(self, width=380, placeholder_text="e.g. roof, before, after")
        self.tags_entry.pack(padx=20, pady=(2, 16))

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(pady=(0, 16))
        ctk.CTkButton(button_row, text="Cancel", width=100, fg_color=COLORS["surface_tertiary"],
                      text_color=COLORS["text_primary"], command=self.destroy).pack(side="left", padx=8)
        ctk.CTkButton(button_row, text="Apply", width=100, command=self._apply).pack(side="left", padx=8)

    def _apply(self):
        new_tags = [t.strip() for t in self.tags_entry.get().split(",") if t.strip()]
        if not new_tags:
            messagebox.showwarning("Gallery", "Enter at least one tag.", parent=self)
            return

        actor = current_actor()
        try:
            for image in self.images:
                merged = list(image.tag_list)
                for tag in new_tags:
                    if tag not in merged:
                        merged.append(tag)
                self.image_service.update_tags(image.id, ", ".join(merged), actor)
        except Exception as error:
            messagebox.showerror("Gallery", str(error), parent=self)
            return

        if self.on_saved:
            self.on_saved()
        self.destroy()


class EditPhotoDialog(ctk.CTkToplevel):
    """Edit caption, album, and tags for one photo."""

    def __init__(self, parent, image, customer, image_service, on_saved=None):
        super().__init__(parent)
        self.title("Edit Photo")
        self.geometry("420x320")
        self.resizable(False, False)
        self.configure(fg_color=THEME_DARK_GREY)

        self.image = image
        self.customer = customer
        self.image_service = image_service
        self.on_saved = on_saved

        ctk.CTkLabel(
            self, text=image.original_filename, font=("Segoe UI", 12, "bold"),
            text_color=THEME_TEXT_PRIMARY, wraplength=380,
        ).pack(pady=(16, 12), padx=20)

        ctk.CTkLabel(self, text="Caption", font=("Segoe UI", 10), text_color=THEME_TEXT_SECONDARY, anchor="w").pack(fill="x", padx=20)
        self.caption_entry = ctk.CTkEntry(self, width=380)
        self.caption_entry.insert(0, image.caption)
        self.caption_entry.pack(padx=20, pady=(2, 12))

        ctk.CTkLabel(self, text="Album", font=("Segoe UI", 10), text_color=THEME_TEXT_SECONDARY, anchor="w").pack(fill="x", padx=20)
        self.album_entry = ctk.CTkEntry(self, width=380, placeholder_text="e.g. Before / After, Installation 2026")
        self.album_entry.insert(0, image.album)
        self.album_entry.pack(padx=20, pady=(2, 12))

        ctk.CTkLabel(self, text="Tags (comma-separated)", font=("Segoe UI", 10), text_color=THEME_TEXT_SECONDARY, anchor="w").pack(fill="x", padx=20)
        self.tags_entry = ctk.CTkEntry(self, width=380, placeholder_text="e.g. roof, before, after")
        self.tags_entry.insert(0, image.tags)
        self.tags_entry.pack(padx=20, pady=(2, 16))

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(pady=(0, 16))
        ctk.CTkButton(button_row, text="Cancel", width=100, fg_color=COLORS["surface_tertiary"],
                      text_color=COLORS["text_primary"], command=self.destroy).pack(side="left", padx=8)
        ctk.CTkButton(button_row, text="Save", width=100, command=self._save).pack(side="left", padx=8)

    def _save(self):
        actor = current_actor()
        try:
            self.image_service.update_caption(self.image.id, self.caption_entry.get(), actor)
            self.image_service.update_album(self.image.id, self.album_entry.get(), actor)
            self.image_service.update_tags(self.image.id, self.tags_entry.get(), actor)
        except Exception as error:
            messagebox.showerror("Gallery", str(error), parent=self)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()


class GalleryStatsWindow(ctk.CTkToplevel):
    """Simple photo counts per customer/album/tag."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Gallery Stats")
        self.geometry("500x500")
        self.configure(fg_color=THEME_DARK_GREY)

        crm_service = CRMService()
        image_service = SiteImageService()

        ctk.CTkLabel(
            self, text="Gallery Stats", font=("Segoe UI", 18, "bold"), text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(16, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color=THEME_SURFACE)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        total = 0
        with_albums = 0
        with_tags = 0
        customers_with_photos = 0

        for customer in [c for c in crm_service.list_customers() if c.name]:
            images = [img for img in image_service.list_for_customer(customer.id) if not img.archived_at]
            if not images:
                continue
            customers_with_photos += 1
            total += len(images)
            with_albums += sum(1 for img in images if img.album)
            with_tags += sum(1 for img in images if img.tags)

            row = ctk.CTkFrame(scroll, fg_color=THEME_SURFACE_LIGHT)
            row.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(
                row, text=f"{customer.name}", font=("Segoe UI", 11, "bold"),
                text_color=THEME_TEXT_PRIMARY, anchor="w",
            ).pack(side="left", padx=10, pady=8)
            ctk.CTkLabel(
                row, text=f"{len(images)} photo(s)", font=("Segoe UI", 10),
                text_color=THEME_TEXT_SECONDARY,
            ).pack(side="right", padx=10, pady=8)

        summary = (
            f"{total} photo(s) across {customers_with_photos} customer(s)  ·  "
            f"{with_albums} in an album  ·  {with_tags} tagged"
        )
        ctk.CTkLabel(
            self, text=summary, font=("Segoe UI", 10), text_color=THEME_TEXT_SECONDARY,
        ).pack(pady=(0, 16))


class PhotoUploaderWindow(ProjectGalleryWindow):
    """The uploader is the same real gallery, opened ready to add.

    The original separate uploader was a wireframe whose "Upload" button
    only showed a placebo message box, with a fake project dropdown and
    an EXIF panel that never populated. Rather than maintain a second
    half-built screen, this reuses the working gallery (EXIF is already
    stripped and dimensions recorded by ImageProcessingService during
    upload).
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Photo Uploader")


class GalleryModuleWindow(ctk.CTkFrame):
    """Module frame - launches hub with quick access"""

    def __init__(self, master):
        super().__init__(master)

        self.configure(fg_color=THEME_DARK_GREY)
        self.hub = None

        ctk.CTkLabel(
            self,
            text="Gallery Hub",
            font=("Segoe UI", 22, "bold"),
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(20, 30))

        info_frame = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        info_frame.pack(pady=20, padx=40, fill="both", expand=True)

        ctk.CTkLabel(
            info_frame,
            text="Organize project photos with automatic EXIF extraction.\n\nTrack Before, During, and After phases with full metadata.",
            font=("Segoe UI", 11),
            text_color=THEME_TEXT_SECONDARY,
            justify="center",
        ).pack(pady=20, padx=20)

        button_frame = ctk.CTkFrame(info_frame, fg_color=THEME_SURFACE)
        button_frame.pack(pady=20, padx=20, fill="x")

        buttons = [
            ("📁 Projects", self._open_gallery),
            ("📸 Upload", self._open_uploader),
            ("🏷️ Tags", self._open_tags),
            ("📊 Stats", self._open_stats),
        ]

        for label, command in buttons:
            ctk.CTkButton(
                button_frame,
                text=label,
                command=command,
                height=40,
                font=("Segoe UI", 11),
            ).pack(pady=5, fill="x")

    def _ensure_hub(self):
        if self.hub is None or not self.hub.winfo_exists():
            self.hub = GalleryHub(self.winfo_toplevel())
        return self.hub

    def _open_gallery(self):
        hub = self._ensure_hub()
        hub.panel.open_project_gallery()

    def _open_uploader(self):
        hub = self._ensure_hub()
        hub.panel.open_uploader()

    def _open_tags(self):
        hub = self._ensure_hub()
        hub.panel.open_tags()

    def _open_stats(self):
        hub = self._ensure_hub()
        hub.panel.open_stats()
