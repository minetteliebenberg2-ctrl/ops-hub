# ==========================================================
# FC Hub - Site Visit Windows
# ----------------------------------------------------------
# Purpose:
# Job cards, measurement forms, site inspection interface.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import getpass
import json
import math
import os
import tkinter as tk
from datetime import date
from gui.components.date_picker import DateEntry
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk

# modules.site_visit.services still holds the in-memory
# Measurement/ChecklistItem/legacy-SiteVisit dataclasses used by the
# still-placeholder Measurement/Checklist windows below - deferred,
# not touched in this pass. The real, persisted site visit workflow
# (New Site Visit / Visit History) uses core.site_visit_service
# instead.
from modules.site_visit.services import SiteVisitService as LegacySiteVisitService, Measurement, ChecklistItem
from core.app_paths import get_assets_dir
from core.business_settings_service import BusinessSettingsService
from core.crm_service import CRMService
from core.job_card import CLOSED, OPEN
from core.job_card_service import JobCardService
from core.picklist_service import LINE_ITEM_TYPE, PicklistService
from core.quote_pdf import format_money
from core.quote_service import QuoteService
from core.site_plan_geometry import (
    angle_of,
    perpendicular_distance,
    point_in_polygon,
    rectangle_from_baseline,
    rotated_corners,
    snap_to_nearest,
)
from core.site_plan import LANDSCAPE, PORTRAIT, grid_template_filename
from core.site_plan_pdf import generate_site_plan_pdf
from core.site_plan_service import SitePlanService
from core.site_visit_service import SiteVisitService
from core.structure_catalog import (
    CANTILEVER, STANDARD, SHADE_SAIL, REPLACE_CABLE, DEFAULT_HEIGHT_M,
    car_bay_size, size_label_for, size_options_for,
)
from gui.design_tokens import COLORS, FONTS
from gui.document_saving import file_document_for_customer
from gui.entity_table import build_entity_table
from gui.flow_layout import reflow_widgets
from gui.form_dialogs import EntityFormDialog, TextPromptDialog

THEME_DARK_GREY = COLORS["surface_primary"]
THEME_SURFACE = COLORS["surface_secondary"]
THEME_SURFACE_LIGHT = COLORS["surface_tertiary"]
THEME_TEXT_PRIMARY = COLORS["text_primary"]
THEME_TEXT_SECONDARY = COLORS["text_secondary"]


def current_actor():

    try:
        return getpass.getuser()
    except Exception:
        return ""


class SiteVisitHub(ctk.CTkToplevel):
    """Hub launcher for Site Visit utilities"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Site Visit Hub")
        self.geometry("500x420")
        self.resizable(False, False)
        self.configure(fg_color=THEME_DARK_GREY)

        ctk.CTkLabel(
            self,
            text="Site Visit Hub",
            font=FONTS["title_lg"],
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(20, 30))

        ctk.CTkLabel(
            self,
            text="Manage site visits, inspections, and job documentation.",
            font=FONTS["body_sm"],
            text_color=THEME_TEXT_SECONDARY,
        ).pack(pady=(0, 30), padx=20)

        button_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        button_frame.pack(pady=20, padx=20, fill="both", expand=True)

        buttons = [
            ("📋 New Site Visit", self.open_job_card),
            ("📏 Measurement Form", self.open_measurements),
            ("✅ Inspection Checklist", self.open_checklist),
            ("📑 Visit History", self.open_history),
            ("📄 Generate Report", self.open_reports),
        ]

        for label, command in buttons:
            ctk.CTkButton(
                button_frame,
                text=label,
                command=command,
                height=50,
                font=FONTS["body_md"],
                fg_color=COLORS["accent_primary"],
                hover_color=COLORS["accent_hover"],
            ).pack(pady=8, fill="x")

        ctk.CTkButton(
            self,
            text="Close Hub",
            command=self.destroy,
            width=200,
            fg_color=COLORS["surface_tertiary"],
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border_default"],
            hover_color=COLORS["border_default"],
        ).pack(pady=(0, 20))

        self.job_card_window = None
        self.measurements_window = None
        self.checklist_window = None
        self.history_window = None

    def open_job_card(self):
        if self.job_card_window is None or not self.job_card_window.winfo_exists():
            self.job_card_window = NewSiteVisitWindow(self)
        else:
            self.job_card_window.lift()

    def open_measurements(self):
        if self.measurements_window is None or not self.measurements_window.winfo_exists():
            self.measurements_window = MeasurementFormWindow(self)
        else:
            self.measurements_window.lift()

    def open_checklist(self):
        if self.checklist_window is None or not self.checklist_window.winfo_exists():
            self.checklist_window = ChecklistWindow(self)
        else:
            self.checklist_window.lift()

    def open_history(self):
        if self.history_window is None or not self.history_window.winfo_exists():
            self.history_window = SiteVisitListWindow(self)
        else:
            self.history_window.lift()

    def open_reports(self):
        messagebox.showinfo("Reports", "Generate site visit reports (placeholder)")


class NewSiteVisitWindow(ctk.CTkToplevel):
    """New Site Visit form - schedules a real visit against a real
    customer (and optionally one of their Sites), replacing the old
    free-typed Job ID/Customer Name/Address fields that never saved
    anywhere. Measurements/checklist/photos/sign-off stay deferred
    (see MeasurementFormWindow/ChecklistWindow below, still
    placeholder) - this covers just the core "schedule it for real"
    workflow.

    NOTE: this class was called JobCardWindow until 2026-08-12, which
    collided with the unrelated Job Card feature's JobCardWindow lower
    in this file. Python kept only the later definition, so both of
    this form's entry points raised TypeError on click. Distinct
    concepts, distinct names - do not rename this back."""

    def __init__(self, parent, on_saved=None):
        super().__init__(parent)

        self.title("New Site Visit")
        self.geometry("600x560")
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)
        self.grab_set()

        self.crm_service = CRMService()
        self.site_visit_service = SiteVisitService()
        self.on_saved = on_saved
        self._customer_by_label = {}
        self._site_by_label = {}

        self._build_ui()

    def _build_ui(self):
        """Build the New Site Visit form"""

        main_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            main_frame,
            text="New Site Visit",
            font=FONTS["heading_lg"],
            text_color=THEME_TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 15))

        customers = self.crm_service.list_customers()
        labels = [f"{c.customer_number} — {c.name}" for c in customers]
        self._customer_by_label = {f"{c.customer_number} — {c.name}": c for c in customers}

        ctk.CTkLabel(main_frame, text="Customer:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.customer_var = ctk.StringVar(value=labels[0] if labels else "")
        ctk.CTkOptionMenu(
            main_frame, variable=self.customer_var, values=labels or ["(no customers)"],
            command=self._on_customer_changed,
        ).pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(main_frame, text="Site (optional):", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.site_var = ctk.StringVar(value="(none)")
        self.site_menu = ctk.CTkOptionMenu(main_frame, variable=self.site_var, values=["(none)"])
        self.site_menu.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(main_frame, text="Visit Date:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.date_entry = DateEntry(main_frame, value=date.today().isoformat())
        self.date_entry.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(main_frame, text="Visit Time:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.time_entry = ctk.CTkEntry(main_frame, placeholder_text="e.g. 10:00 AM")
        self.time_entry.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(main_frame, text="Notes:", text_color=THEME_TEXT_SECONDARY).pack(anchor="w")
        self.notes_text = ctk.CTkTextbox(
            main_frame, height=120, text_color=THEME_TEXT_PRIMARY, fg_color=THEME_SURFACE_LIGHT,
        )
        self.notes_text.pack(fill="both", expand=True, pady=(2, 15))

        button_row = ctk.CTkFrame(main_frame, fg_color=THEME_DARK_GREY)
        button_row.pack(fill="x")
        ctk.CTkButton(button_row, text="Save Visit", command=self._save, width=120).pack(side="left", padx=(0, 8))
        ctk.CTkButton(button_row, text="Cancel", command=self.destroy, width=100).pack(side="left")

        if customers:
            self._on_customer_changed(labels[0])

    def _on_customer_changed(self, _value=None):
        """Refresh the Site dropdown to the selected customer's real
        sites (e.g. Cavaleros' Block A-F)."""

        customer = self._customer_by_label.get(self.customer_var.get())
        self._site_by_label = {}
        if customer is None:
            self.site_menu.configure(values=["(none)"])
            self.site_var.set("(none)")
            return

        sites = self.crm_service.list_sites(customer.id)
        labels = ["(none)"] + [site.name for site in sites]
        self._site_by_label = {site.name: site.id for site in sites}
        self.site_menu.configure(values=labels)
        self.site_var.set("(none)")

    def _save(self):

        customer = self._customer_by_label.get(self.customer_var.get())
        if customer is None:
            messagebox.showwarning("New Site Visit", "Select a customer first.", parent=self)
            return

        site_id = self._site_by_label.get(self.site_var.get(), "")
        visit = self.site_visit_service.new_visit(customer.id, site_id)
        visit.visit_date = self.date_entry.get().strip()
        visit.visit_time = self.time_entry.get().strip()
        visit.notes = self.notes_text.get("1.0", "end").strip()

        try:
            self.site_visit_service.save_visit(visit, current_actor())
        except ValueError as error:
            messagebox.showerror("New Site Visit", str(error), parent=self)
            return

        if self.on_saved:
            self.on_saved()
        self.destroy()


class SiteVisitListWindow(ctk.CTkToplevel):
    """Real list of scheduled/completed site visits - previously
    "Visit History" just showed a placeholder message box."""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Visit History")
        self.geometry("1000x650")
        self.configure(fg_color=THEME_DARK_GREY)

        self.crm_service = CRMService()
        self.site_visit_service = SiteVisitService()

        self.table = build_entity_table(
            self,
            ("Customer", "Site", "Date", "Time", "Status"),
            (
                ("Refresh", self.refresh),
                ("New Site Visit", self.new_visit),
                ("Mark Complete", self.mark_complete),
                ("Measurements", self.open_measurements),
                ("Checklist", self.open_checklist),
                ("Job Cards", self.open_job_cards),
                ("Photos", self.open_photos),
                ("Archive", self.archive_selected),
            ),
        )
        self.refresh()

    def refresh(self):

        customers_by_id = {c.id: c for c in self.crm_service.list_customers()}
        sites_by_id = {s.id: s for s in self.crm_service.sites.list_all()}

        self.table.delete(*self.table.get_children())
        for visit in self.site_visit_service.list_visits():
            if visit.archived_at:
                continue
            customer = customers_by_id.get(visit.customer_id)
            site = sites_by_id.get(visit.site_id) if visit.site_id else None
            self.table.insert(
                "", "end", iid=visit.id, text=visit.visit_date,
                values=(
                    customer.name if customer else "(unknown customer)",
                    site.name if site else "",
                    visit.visit_date,
                    visit.visit_time,
                    visit.status,
                ),
            )

    def new_visit(self):
        NewSiteVisitWindow(self, on_saved=self.refresh)

    def _selected_visit_id(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showwarning("Site Visit", "Select a visit first.", parent=self)
            return None
        return selection[0]

    def mark_complete(self):
        visit_id = self._selected_visit_id()
        if visit_id is None:
            return
        self.site_visit_service.mark_complete(visit_id, current_actor())
        self.refresh()

    def archive_selected(self):
        visit_id = self._selected_visit_id()
        if visit_id is None:
            return
        reason = TextPromptDialog.ask(self, "Archive Site Visit", "Reason for archiving this visit:")
        if reason is None:
            return
        try:
            self.site_visit_service.archive_visit(visit_id, current_actor(), reason)
        except ValueError as error:
            messagebox.showerror("Archive Site Visit", str(error), parent=self)
            return
        self.refresh()

    def open_measurements(self):
        visit_id = self._selected_visit_id()
        if visit_id is None:
            return
        visit = self.site_visit_service.get_visit(visit_id)
        customer = self.crm_service.get_customer(visit.customer_id)
        MeasurementFormWindow(self, visit, customer)

    def open_checklist(self):
        visit_id = self._selected_visit_id()
        if visit_id is None:
            return
        visit = self.site_visit_service.get_visit(visit_id)
        customer = self.crm_service.get_customer(visit.customer_id)
        ChecklistWindow(self, visit, customer)

    def open_job_cards(self):
        visit_id = self._selected_visit_id()
        if visit_id is None:
            return
        visit = self.site_visit_service.get_visit(visit_id)
        customer = self.crm_service.get_customer(visit.customer_id)
        if customer is None:
            messagebox.showwarning("Job Cards", "This visit has no customer on file.", parent=self)
            return
        site = None
        if visit.site_id:
            site = self.crm_service.sites.get(visit.site_id)
        if site is None:
            messagebox.showwarning("Job Cards", "No site linked to this visit. Assign a site first.", parent=self)
            return
        JobCardListWindow(self, customer, site)

    def open_photos(self):
        visit_id = self._selected_visit_id()
        if visit_id is None:
            return
        visit = self.site_visit_service.get_visit(visit_id)
        customer = self.crm_service.get_customer(visit.customer_id)
        if customer is None:
            messagebox.showwarning("Photos", "This visit has no customer on file.", parent=self)
            return
        SitePhotosWindow(self, customer, visit)


class SitePhotosWindow(ctk.CTkToplevel):
    """Real photo upload/list for one Site Visit - auto rename/resize/
    strip-EXIF on upload (core.image_processing_service), saved into
    the customer's real Images folder. "Open" hands off to the OS's
    own photo viewer rather than building one here."""

    def __init__(self, parent, customer, visit):
        super().__init__(parent)

        self.title(f"Photos — {customer.name} — {visit.visit_date}")
        self.geometry("900x600")
        self.configure(fg_color=THEME_DARK_GREY)

        self.customer = customer
        self.visit = visit

        from core.site_image_service import SiteImageService

        self.site_image_service = SiteImageService()

        self.table = build_entity_table(
            self,
            ("Caption", "Taken", "Uploaded"),
            (
                ("Refresh", self.refresh),
                ("Upload Photos", self.upload_photos),
                ("Edit Caption", self.edit_caption),
                ("Open", self.open_selected),
                ("Archive", self.archive_selected),
            ),
        )
        self.refresh()

    def refresh(self):

        self.table.delete(*self.table.get_children())
        for image in self.site_image_service.list_for_visit(self.visit.id):
            if image.archived_at:
                continue
            self.table.insert(
                "", "end", iid=image.id, text=image.stored_filename,
                values=(image.caption, image.taken_at, image.created_at),
            )

    def upload_photos(self):

        paths = filedialog.askopenfilenames(
            title="Select site photos to upload",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.heic *.heif *.bmp *.tiff")],
        )
        if not paths:
            return

        caption = TextPromptDialog.ask(
            self, "Upload Photos", "Caption for this batch (optional - edit individually after):",
            required=False,
        )
        if caption is None:
            return

        failed = []
        for path in paths:
            try:
                self.site_image_service.upload_image(
                    path, self.customer, current_actor(),
                    site_id=self.visit.site_id, site_visit_id=self.visit.id, caption=caption,
                )
            except Exception as error:
                failed.append(f"{os.path.basename(path)}: {error}")

        self.refresh()
        if failed:
            messagebox.showerror("Upload Photos", "Some photos failed to upload:\n" + "\n".join(failed), parent=self)

    def _selected_image_id(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showwarning("Photos", "Select a photo first.", parent=self)
            return None
        return selection[0]

    def edit_caption(self):
        image_id = self._selected_image_id()
        if image_id is None:
            return
        image = self.site_image_service.images.get(image_id)
        new_caption = TextPromptDialog.ask(self, "Edit Caption", "Caption:", initial=image.caption, required=False)
        if new_caption is None:
            return
        self.site_image_service.update_caption(image_id, new_caption, current_actor())
        self.refresh()

    def open_selected(self):
        image_id = self._selected_image_id()
        if image_id is None:
            return
        image = self.site_image_service.images.get(image_id)
        path = self.site_image_service.image_path(image, self.customer)
        if not path.is_file():
            messagebox.showerror("Photos", f"File not found on disk:\n{path}", parent=self)
            return
        os.startfile(str(path))

    def archive_selected(self):
        image_id = self._selected_image_id()
        if image_id is None:
            return
        reason = TextPromptDialog.ask(self, "Archive Photo", "Reason for archiving this photo:")
        if reason is None:
            return
        try:
            self.site_image_service.archive_image(image_id, current_actor(), reason)
        except ValueError as error:
            messagebox.showerror("Archive Photo", str(error), parent=self)
            return
        self.refresh()


class SitePlanWindow(ctk.CTkToplevel):
    """The persistent per-Site diagram - a backdrop image she pastes
    in herself (her own satellite screenshot, no maps API) plus
    freeform rectangles, each one both a drawn structure AND a
    prospective Quote line item at once. Mapped out with Minette
    2026-08-07: "nothing changes on my side between drawing the site
    plan and doing the quote."

    v1 is draw-once + click-to-select-then-edit-fields, NOT
    drag-to-resize/move - she explicitly likes "small adjustments
    after the fact", and real resize/move is canvas hit-testing/drag-
    state complexity worth adding later only if she actually asks."""

    MIN_DRAG_PIXELS = 6

    def __init__(self, parent, customer, site):
        super().__init__(parent)

        self.title(f"Site Plan — {customer.name} — {site.name or 'Unnamed Site'}")
        self.geometry("1000x700")
        self.configure(fg_color=THEME_DARK_GREY)

        self.customer = customer
        self.site = site
        self.site_plan_service = SitePlanService()
        self.picklists = PicklistService()
        self.crm_service = CRMService()
        self.quote_service = QuoteService()
        self.business_settings = BusinessSettingsService()

        self.plan = self.site_plan_service.get_or_create_plan(site, current_actor())
        self._items_by_id = {}
        self._item_polygons = {}  # item_id -> [(x, y) x4] in canvas pixels, for hit-testing
        self._image_rect = None  # (x0, y0, x1, y1) in canvas pixels the backdrop currently occupies
        self._backdrop_pil = None
        self._using_default_grid = False
        self._backdrop_photo = None  # kept alive - Tk drops PhotoImages with no live reference
        self._selected_item_id = None
        self._drag_start = None
        self._drag_rect_id = None

        # Two-stage draw (Minette 2026-08-12): drag along the row to set
        # the angle, then pull the depth out perpendicular. Real parking
        # bays are rarely square to the image, and her Cavaleros site has
        # half a dozen orientations on one plan.
        self._baseline = None      # (x0, y0, x1, y1) once the first drag lands
        self._preview_ids = []     # canvas ids of the live preview
        self._last_angle = None    # so the next structure in a row lines up free

        self._build_ui()
        self.refresh()

    def _build_ui(self):

        toolbar = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        toolbar.pack(fill="x", padx=15, pady=(15, 5))

        # Wrapped, not packed left-to-right: there are seven buttons with
        # long labels, so on a narrower window "Rotate 90°" and the ones
        # after it were pushed past the visible edge and looked like they
        # simply didn't work. reflow_widgets wraps onto a second row
        # instead of ever hiding a button (same fix as the Quote header
        # row).
        buttons = [
            ctk.CTkButton(toolbar, text="Upload Real Image (e.g. Google Satellite)", command=self.change_backdrop),
            ctk.CTkButton(toolbar, text="Grid Template (Portrait/Landscape)", command=self.use_grid_template),
            ctk.CTkButton(toolbar, text="Edit Selected", command=self.edit_selected),
            ctk.CTkButton(toolbar, text="Rotate 90°", command=self.rotate_selected),
            ctk.CTkButton(toolbar, text="Delete Selected", command=self.delete_selected),
            ctk.CTkButton(toolbar, text="Export PDF (Landscape)", command=self.export_pdf),
            ctk.CTkButton(
                toolbar, text="Generate Quote", command=self.generate_quote,
                fg_color=COLORS["accent_primary"], hover_color=COLORS["accent_hover"],
            ),
            ctk.CTkButton(toolbar, text="Close", command=self.destroy),
        ]
        reflow_widgets(toolbar, buttons)

        self.summary_label = ctk.CTkLabel(self, text="", text_color=THEME_TEXT_SECONDARY)
        self.summary_label.pack(fill="x", padx=15, anchor="w")

        self._hint_default_text = "Drag ALONG a row of structures to set its angle, then move out and click to set the depth. Click an existing structure to select it, then Edit or Delete."
        self.hint_label = ctk.CTkLabel(self, text=self._hint_default_text, text_color=THEME_TEXT_SECONDARY)
        self.hint_label.pack(fill="x", padx=15)

        canvas_frame = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        canvas_frame.pack(fill="both", expand=True, padx=15, pady=15)

        self.canvas = tk.Canvas(canvas_frame, bg="#F5F5F5", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Configure>", lambda _event: self._redraw())
        self.bind("<Escape>", self._cancel_draw)

    def refresh(self):

        self.plan = self.site_plan_service.plans.get(self.plan.id) or self.plan
        items = self.site_plan_service.list_items(self.plan.id)
        self._items_by_id = {item.id: item for item in items}
        if self._selected_item_id not in self._items_by_id:
            self._selected_item_id = None

        self._load_backdrop_image()
        self._redraw()

        total_minor = sum(item.amount_minor for item in items)
        self.summary_label.configure(
            text=f"{len(items)} structure(s) · Estimated value: {format_money(total_minor)}"
        )

    def _load_backdrop_image(self):

        self._backdrop_pil = None
        self._using_default_grid = False

        if not self.plan.backdrop_filename:
            # No real image uploaded yet - fall back to the bundled blank
            # grid template (her own "Measurement Form" sheet) so there's
            # always something to draw on, rather than an empty canvas.
            grid_path = get_assets_dir() / grid_template_filename(self.plan.grid_orientation)
            if grid_path.is_file():
                try:
                    self._backdrop_pil = Image.open(grid_path).convert("RGB")
                    self._using_default_grid = True
                except Exception:
                    self._backdrop_pil = None
            return

        path = self.site_plan_service.backdrop_path(self.plan, self.customer)
        if path is None or not path.is_file():
            return
        try:
            self._backdrop_pil = Image.open(path).convert("RGB")
        except Exception:
            self._backdrop_pil = None

    def _redraw(self):

        self.canvas.delete("all")
        self._item_polygons = {}
        self._image_rect = None

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            return

        if self._backdrop_pil is None:
            # Should only happen if the bundled grid template asset is
            # missing/unreadable - the normal empty state loads it instead.
            self.canvas.create_text(
                canvas_w / 2, canvas_h / 2,
                text="No backdrop available.\nClick \"Upload Real Image\" to add a satellite screenshot of this site.",
                fill=THEME_TEXT_SECONDARY, justify="center", font=FONTS["body_md"],
            )
            return

        img_w, img_h = self._backdrop_pil.size
        scale = min(canvas_w / img_w, canvas_h / img_h)
        display_w = max(1, round(img_w * scale))
        display_h = max(1, round(img_h * scale))
        offset_x = (canvas_w - display_w) // 2
        offset_y = (canvas_h - display_h) // 2

        resized = self._backdrop_pil.resize((display_w, display_h), Image.Resampling.LANCZOS)
        self._backdrop_photo = ImageTk.PhotoImage(resized)
        self.canvas.create_image(offset_x, offset_y, anchor="nw", image=self._backdrop_photo)
        self._image_rect = (offset_x, offset_y, offset_x + display_w, offset_y + display_h)

        for item in self._items_by_id.values():
            corners = self._item_corners(item, offset_x, offset_y, display_w, display_h)
            is_selected = item.id == self._selected_item_id
            outline = "#F2994A" if is_selected else "#1B7A3D"

            # create_polygon, not create_rectangle - a Tk rectangle is
            # axis-aligned by definition and cannot be rotated.
            self.canvas.create_polygon(
                [coordinate for corner in corners for coordinate in corner],
                outline=outline, fill="", width=3 if is_selected else 2,
            )
            label_x, label_y = corners[0]
            self.canvas.create_text(
                label_x + 4, label_y + 4, anchor="nw", text=item.structure_type or "(untitled)",
                fill=outline, font=("Lato", 9, "bold"),
            )
            if item.unit_price_minor:
                total_rands = item.quantity * item.unit_price_minor / 100
                self.canvas.create_text(
                    label_x + 4, label_y + 20, anchor="nw",
                    text=f"R{total_rands:,.2f}",
                    fill=outline, font=("Lato", 8),
                )
            self._item_polygons[item.id] = corners

    def _item_corners(self, item, offset_x, offset_y, display_w, display_h):
        """The item's four canvas-pixel corners.

        x/y/width/height still describe the UNROTATED box (so a
        rotation of 0 draws exactly what it always did); rotation is
        applied about its centre, in pixel space."""

        width_px = item.width * display_w
        height_px = item.height * display_h
        centre_x = offset_x + (item.x + item.width / 2) * display_w
        centre_y = offset_y + (item.y + item.height / 2) * display_h

        return rotated_corners(centre_x, centre_y, width_px, height_px, item.rotation)

    def _item_at(self, x, y):
        """Topmost structure containing this point, or None.

        Point-in-polygon rather than a bounding-box test: a rotated
        rectangle's bounding box is much larger than the shape, so on a
        dense lot a box test selects the row next door."""

        for item_id in reversed(list(self._item_polygons)):
            if point_in_polygon(x, y, self._item_polygons[item_id]):
                return item_id
        return None

    def _is_on_image(self, x, y):
        """Is this canvas point actually on the backdrop?

        The backdrop is centred, so there is dead canvas either side of
        it. Drawing must START on the image - but nothing is clamped
        afterwards, deliberately: clamping a baseline's endpoint per
        axis silently CHANGES the angle she traced (a drag from just
        off the left edge came out 6 degrees different), and the whole
        point of the first drag is that the angle is exactly what she
        drew. A structure that overhangs the edge is honest; a rotated
        one is not."""

        if self._image_rect is None:
            return False
        img_x0, img_y0, img_x1, img_y1 = self._image_rect
        return img_x0 <= x <= img_x1 and img_y0 <= y <= img_y1

    def _clear_preview(self):

        for canvas_id in self._preview_ids:
            self.canvas.delete(canvas_id)
        self._preview_ids = []

    def _cancel_draw(self, _event=None):
        """Abandon a half-drawn structure - Escape, or a baseline too
        short to mean anything."""

        self._clear_preview()
        self._baseline = None
        self._drag_start = None
        self._drag_rect_id = None
        self.hint_label.configure(text=self._hint_default_text)

    def _snap_candidates(self, centre_x, centre_y):
        """Angles worth lining up with: the nearest existing structure,
        and the last one she drew.

        Deliberately NOT a single site-wide angle - her Cavaleros plan
        has half a dozen orientations because the structures follow
        curved driveways, so a global angle would be wrong for most of
        the site and would fight her on every row."""

        candidates = []

        nearest, nearest_distance = None, None
        for item_id, corners in self._item_polygons.items():
            item = self._items_by_id.get(item_id)
            if item is None:
                continue
            item_centre_x = sum(point[0] for point in corners) / 4
            item_centre_y = sum(point[1] for point in corners) / 4
            distance = (item_centre_x - centre_x) ** 2 + (item_centre_y - centre_y) ** 2
            if nearest_distance is None or distance < nearest_distance:
                nearest, nearest_distance = item, distance

        if nearest is not None:
            candidates.append(nearest.rotation)
        if self._last_angle is not None:
            candidates.append(self._last_angle)

        return candidates

    def _on_press(self, event):

        # Second stage: the baseline is down and she is placing the
        # depth, so a click commits rather than starting a new shape.
        if self._baseline is not None:
            self._commit_structure(event)
            return

        self._drag_rect_id = None
        self._drag_start = None

        item_id = self._item_at(event.x, event.y)
        if item_id is not None:
            self._selected_item_id = item_id
            self._redraw()
            return

        if self._image_rect is None:
            return  # no backdrop yet - nothing to draw against

        if not self._is_on_image(event.x, event.y):
            self._flash_hint("Start the drag on the image itself.")
            return

        if self._selected_item_id is not None:
            self._selected_item_id = None
            self._redraw()

        self._drag_start = (event.x, event.y)
        self._drag_rect_id = self.canvas.create_line(
            event.x, event.y, event.x, event.y, fill="#F2994A", width=3,
        )
        self._preview_ids = [self._drag_rect_id]

    def _on_double_click(self, event):
        """Double-clicking a structure opens its edit form directly, so
        changing a net/structure type doesn't need a select-then-Edit
        round trip. Cancels any drag the first click of the pair began.
        """

        item_id = self._item_at(event.x, event.y)
        if item_id is None:
            return

        if self._drag_rect_id is not None or self._baseline is not None:
            self._cancel_draw()

        item = self._items_by_id.get(item_id)
        if item is None:
            return

        self._selected_item_id = item_id
        self._redraw()
        self._open_item_form(item, is_new=False)

    def _on_drag(self, event):

        if self._baseline is not None:
            return  # second stage follows the pointer, not the button
        if self._drag_rect_id is None or self._drag_start is None:
            return
        x0, y0 = self._drag_start
        self.canvas.coords(self._drag_rect_id, x0, y0, event.x, event.y)

    def _on_release(self, event):
        """End of the FIRST drag: the line she just traced along the row
        becomes the structure's angle, and she moves on to pulling out
        the depth."""

        if self._baseline is not None:
            return
        if self._drag_rect_id is None or self._drag_start is None:
            return

        x0, y0 = self._drag_start
        x1, y1 = event.x, event.y
        self._drag_start = None
        self._drag_rect_id = None

        if math.hypot(x1 - x0, y1 - y0) < self.MIN_DRAG_PIXELS:
            # A plain click (or a couple of pixels of accidental jitter)
            # is not a real drag - previously this returned silently,
            # which looked exactly like nothing had happened.
            self._cancel_draw()
            self._flash_hint("That was too short to draw - click and hold, then drag ALONG the row of structures before releasing.")
            return

        self._baseline = (x0, y0, x1, y1)
        self.hint_label.configure(
            text="Now move away from the line to set the depth, and click to place the structure. Escape cancels."
        )

    def _on_motion(self, event):
        """Second stage: preview the structure as she pulls the depth
        out perpendicular to the line she traced."""

        if self._baseline is None:
            return

        self._clear_preview()
        x0, y0, x1, y1 = self._baseline

        depth = perpendicular_distance(x0, y0, x1, y1, event.x, event.y)
        centre_x, centre_y, length, size, degrees = rectangle_from_baseline(x0, y0, x1, y1, depth)
        degrees = snap_to_nearest(degrees, self._snap_candidates(centre_x, centre_y))

        snapped = abs(degrees - angle_of(x0, y0, x1, y1)) > 1e-9
        colour = "#1B7A3D" if snapped else "#888888"

        self._preview_ids.append(
            self.canvas.create_line(x0, y0, x1, y1, fill="#F2994A", width=3)
        )
        if size >= 1:
            corners = rotated_corners(centre_x, centre_y, length, size, degrees)
            self._preview_ids.append(
                self.canvas.create_polygon(
                    [coordinate for corner in corners for coordinate in corner],
                    outline=colour, fill="", width=2, dash=(4, 2),
                )
            )

    def _commit_structure(self, event):
        """Her click ends the second stage - turn the two strokes into a
        real structure and open its form."""

        x0, y0, x1, y1 = self._baseline

        depth = perpendicular_distance(x0, y0, x1, y1, event.x, event.y)
        if abs(depth) < self.MIN_DRAG_PIXELS:
            self._flash_hint("Move further from the line to give the structure some depth, then click.")
            return

        centre_x, centre_y, length, size, degrees = rectangle_from_baseline(x0, y0, x1, y1, depth)
        degrees = snap_to_nearest(degrees, self._snap_candidates(centre_x, centre_y))

        self._cancel_draw()

        img_x0, img_y0, img_x1, img_y1 = self._image_rect
        img_w = img_x1 - img_x0
        img_h = img_y1 - img_y0
        if img_w <= 0 or img_h <= 0:
            return

        # x/y/width/height still describe the UNROTATED box, so a
        # rotation of 0 behaves exactly as it always did.
        fwidth = length / img_w
        fheight = size / img_h
        fx = (centre_x - img_x0) / img_w - fwidth / 2
        fy = (centre_y - img_y0) / img_h - fheight / 2
        if fwidth <= 0 or fheight <= 0:
            return

        self._last_angle = degrees
        item = self.site_plan_service.new_item(self.plan.id, fx, fy, fwidth, fheight, rotation=degrees)
        self._open_item_form(item, is_new=True)

    def _size_options_for(self, structure_type):

        return size_options_for(structure_type)

    def _size_label_for(self, structure_type, car_bays):

        return size_label_for(structure_type, car_bays)

    def _open_item_form(self, item, is_new):

        type_options = [value for value in self.picklists.list_values(LINE_ITEM_TYPE) if value != SHADE_SAIL]
        if not type_options:
            type_options = ["Structure"]
        if item.structure_type and item.structure_type not in type_options:
            type_options = type_options + [item.structure_type]

        initial_structure_type = item.structure_type or type_options[0]

        # The Size dropdown's options are computed from the SAME initial
        # value the Structure Type field itself starts on (so a brand new
        # item, which has no structure_type yet, still gets the right
        # options for whatever type is actually pre-selected) - but if she
        # changes Structure Type inside this dialog to something with a
        # different size concept, Size won't relabel live (this simple
        # generic dialog has no cross-field reactivity, unlike the
        # specialized Quotes grid). Handled after the dialog closes below:
        # car_bays is re-derived from her FINAL structure_type choice, not
        # this pre-form one, so a stale Size selection can never be
        # mis-applied to an unrelated type.
        size_options, _size_by_label = self._size_options_for(initial_structure_type)
        current_size_label = self._size_label_for(initial_structure_type, item.car_bays)

        fields = [
            {"key": "structure_type", "label": "Structure Type", "kind": "dropdown", "options": type_options, "initial": initial_structure_type},
            {"key": "size", "label": "Size", "kind": "dropdown", "options": size_options, "initial": current_size_label},
            {"key": "description", "label": "Description", "kind": "textarea", "initial": item.description},
            {"key": "quantity", "label": "Quantity", "kind": "text", "initial": f"{item.quantity:g}"},
            {"key": "unit_price", "label": "Unit Price (R)", "kind": "text", "initial": f"{item.unit_price_minor / 100:.2f}"},
        ]
        title = "New Structure" if is_new else f"Edit Structure — {item.structure_type or 'Unnamed'}"
        result = EntityFormDialog.ask(self, title, fields)
        if result is None:
            self.refresh()  # drop the rubber-band preview if a new rectangle's form was cancelled
            return

        try:
            quantity = float(result["quantity"] or "1")
            unit_price_minor = round(float(result["unit_price"] or "0") * 100)
        except ValueError:
            messagebox.showerror("Site Plan", "Quantity and unit price must be numbers.", parent=self)
            self.refresh()
            return

        # Re-derive from her FINAL structure_type choice (not the pre-form
        # one used to build the dialog's options) - if she changed types
        # inside the dialog, this correctly drops a now-stale Size
        # selection back to None rather than mis-applying it.
        _final_size_options, final_size_by_label = self._size_options_for(result["structure_type"])
        item.structure_type = result["structure_type"]
        item.car_bays = final_size_by_label.get(result["size"])
        item.description = result["description"]
        item.quantity = quantity
        item.unit_price_minor = unit_price_minor

        if not unit_price_minor:
            item.unit_price_minor = self._estimate_price(item.structure_type, item.car_bays)

        try:
            self.site_plan_service.save_item(item)
        except ValueError as error:
            messagebox.showerror("Site Plan", str(error), parent=self)
            self.refresh()
            return

        self._selected_item_id = item.id
        self.refresh()

    def _estimate_price(self, structure_type, car_bays):
        try:
            from core.structure_quote import quote_structure, size_for_car_bays, can_price
            if can_price(structure_type, car_bays):
                size = size_for_car_bays(car_bays)
                result = quote_structure(structure_type, size)
                return round(result["total_sell"] * 100)
            return self._rate_card_price_minor(structure_type)
        except Exception:
            return 0

    def rotate_selected(self):

        item = self._items_by_id.get(self._selected_item_id)
        if not item:
            messagebox.showinfo("Rotate", "Select a structure first.", parent=self)
            return
        item.rotation = (item.rotation + 90) % 360
        self.site_plan_service.save_item(item)
        self.refresh()

    def edit_selected(self):

        item = self._items_by_id.get(self._selected_item_id)
        if item is None:
            messagebox.showwarning("Site Plan", "Select a structure first.", parent=self)
            return
        self._open_item_form(item, is_new=False)

    def delete_selected(self):

        item = self._items_by_id.get(self._selected_item_id)
        if item is None:
            messagebox.showwarning("Site Plan", "Select a structure first.", parent=self)
            return
        if not messagebox.askyesno(
            "Delete Structure", f"Remove \"{item.structure_type or 'this structure'}\" from the site plan?", parent=self,
        ):
            return
        self.site_plan_service.delete_item(item.id)
        self._selected_item_id = None
        self.refresh()

    def generate_quote(self):
        """Collect every structure currently on the plan into a real,
        saved Quote - mirrors NettingQuoteBuilderWindow._save_as_quote
        (modules/proposals/windows.py), simpler here since the customer
        and site are already implied by which plan is open, no picker
        needed. Always creates a new Quote (same as Netting's "Save as
        Quote") rather than updating a previous one - the plan is the
        living source, quotes are point-in-time snapshots of it."""

        items = self.site_plan_service.list_items(self.plan.id)
        if not items:
            messagebox.showwarning("Generate Quote", "Draw at least one structure before generating a quote.", parent=self)
            return

        # Show pricing options (net supplier, paint, back-to-back) before
        # creating the quote - same dialog as "Calculate Prices" in the
        # Quotes grid so the same choices are available.
        from core.structure_quote import can_price
        from modules.quotes.windows import PricingOptionsDialog
        # Catalog-priced structures need the supplier/paint/back-to-back
        # choices; flat-rate types don't, but they still get priced from
        # the rate card below.
        priceable = [i for i in items if can_price(i.structure_type, i.car_bays)]
        pricing_opts = PricingOptionsDialog.ask(self, len(priceable)) if priceable else {
            "net_supplier": "Plusnet", "include_netting": True,
            "include_paint": True, "back_to_back": False,
        }
        if pricing_opts is None:
            return  # user cancelled

        priced = 0
        failures = []
        try:
            quote = self.quote_service.new_quote(self.customer.id, self.site.id)
            quote = self.quote_service.save_quote(quote, current_actor())
            for item in items:
                line_item = self.quote_service.new_line_item(quote.id)
                line_item.structure_type = item.structure_type
                line_item.description = item.description
                line_item.quantity = item.quantity
                line_item.unit_price_minor = item.unit_price_minor
                # car_bays now carries through for Cable too, not just
                # Cantilever/Standard - the Quotes grid's Car Bay dropdown
                # is type-aware (shows Single/Double/Triple for Cable),
                # so this round-trips correctly instead of needing to be
                # folded into the description as a workaround.
                if item.structure_type in (CANTILEVER, STANDARD):
                    line_item.car_bays = item.car_bays
                    size = car_bay_size(item.car_bays) if item.car_bays else None
                    if size:
                        line_item.width_m, line_item.projection_m = size
                    line_item.height_m = DEFAULT_HEIGHT_M
                elif item.structure_type == REPLACE_CABLE:
                    line_item.car_bays = item.car_bays

                # A structure drawn on the plan usually carries no price -
                # the plan is about position and size, not money. Fill it
                # from real supplier costs rather than sending through a
                # R0 line. Anything already priced on the plan is left as
                # she set it.
                if not line_item.unit_price_minor:
                    try:
                        calculated = self._calculated_price_minor(item, pricing_opts)
                        if calculated:
                            line_item.unit_price_minor = calculated
                            priced += 1
                    except ValueError as price_err:
                        failures.append(f"{item.description or item.structure_type}: {price_err}")

                self.quote_service.save_line_item(line_item)
        except ValueError as error:
            messagebox.showerror("Generate Quote", str(error), parent=self)
            return

        message = f"Saved as a real quote for {self.customer.name}."
        if priced:
            message += (
                f"\n\n{priced} structure(s) priced from supplier costs. "
                "Adjust anything you need to in the quote's grid."
            )
        if failures:
            message += "\n\nCould not auto-price:\n" + "\n".join(failures[:5])
        messagebox.showinfo("Generate Quote", message, parent=self)

        from modules.quotes.windows import QuoteDetailWindow

        QuoteDetailWindow(self, self.quote_service, self.crm_service, self.business_settings, quote.id)

    def _calculated_price_minor(self, item, pricing_opts=None):
        """Sell price for one plan structure, from real supplier costs.

        Returns 0 rather than raising when the structure cannot be priced
        automatically (a shade sail, a 4-bay structure, or a missing
        supplier price) - generating the quote must still succeed, just
        with that line left for her to price by hand.
        """

        from core.structure_quote import can_price, quote_structure, size_for_car_bays

        if not can_price(item.structure_type, item.car_bays):
            # Not a catalog-priced structure (Cantilever/4 Post). Most of
            # what gets drawn on a plan is a flat-rate type - New Net,
            # Refit, Retensioning - which is priced from the picklist rate
            # card, exactly as the Quotes grid does it. Without this the
            # line came through at R0 with no explanation.
            return self._rate_card_price_minor(item.structure_type)

        opts = pricing_opts or {}
        gp = opts.get("gp", 0.45)
        quote = quote_structure(
            item.structure_type,
            size_for_car_bays(item.car_bays),
            net_supplier=opts.get("net_supplier", "Plusnet"),
            include_netting=opts.get("include_netting", True),
            include_paint=opts.get("include_paint", True),
            back_to_back=opts.get("back_to_back", False),
            structure_gp=gp,
            netting_gp=gp,
        )
        return round(quote["total_sell"] * 100)

    def _rate_card_price_minor(self, structure_type):
        """Standard-tier rate for a flat-rate line type, or 0 if that type
        carries no rate (a shade sail, say, which really is priced by
        hand). Mirrors QuoteDetailWindow._rate_for_selected_tier."""

        if not structure_type:
            return 0

        from core.picklist_service import LINE_ITEM_TYPE, PicklistService

        options = PicklistService().list_options(LINE_ITEM_TYPE, include_inactive=True)
        for option in options:
            if option.value == structure_type:
                return option.rate_standard_minor or 0
        return 0

    def _flash_hint(self, text, revert_after_ms=3000):
        """Briefly replace the hint line with a warning message, then put
        the normal instructions back - used so a failed gesture (e.g. a
        click too small to count as a drag) is visible instead of silent."""

        self.hint_label.configure(text=text, text_color="#F2994A")
        self.after(revert_after_ms, self._reset_hint)

    def _reset_hint(self):

        if self.winfo_exists():
            self.hint_label.configure(text=self._hint_default_text, text_color=THEME_TEXT_SECONDARY)

    def change_backdrop(self):

        path = filedialog.askopenfilename(
            title="Select a backdrop image (e.g. a satellite screenshot pasted from Google Maps)",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.heic *.heif *.bmp *.tiff")],
        )
        if not path:
            return
        try:
            self.plan = self.site_plan_service.set_backdrop_image(self.plan, path, self.customer, current_actor())
        except ValueError as error:
            messagebox.showerror("Site Plan", str(error), parent=self)
            return
        self.refresh()

    def export_pdf(self):
        """Export this plan as a landscape PDF, filed into the client's
        Paperwork folder like every other document (see
        core/client_document_saver.py)."""

        items = self.site_plan_service.list_items(self.plan.id)

        backdrop_path = None
        if self.plan.backdrop_filename:
            backdrop_path = self.site_plan_service.backdrop_path(self.plan, self.customer)
        else:
            grid_path = get_assets_dir() / grid_template_filename(self.plan.grid_orientation)
            if grid_path.is_file():
                backdrop_path = grid_path

        site_label = (self.site.name or "Site").replace(" ", "_")
        default_name = f"Site_Plan_{site_label}.pdf"

        def build(output_path):
            generate_site_plan_pdf(
                self.plan, items, self.customer, self.site,
                self.business_settings.get_settings(), output_path, backdrop_path,
            )

        file_document_for_customer(
            self, self.customer, default_name, build,
            title="Export Site Plan",
            heading="Site plan saved",
        )

    def use_grid_template(self):
        """Switch back to the bundled blank grid template, and - once
        already on it - toggle that template between portrait and
        landscape.

        Most of her sites are car parks, which are wide rather than
        tall, so the original portrait-only sheet left more than half
        the canvas unused. One button rather than two, her call.

        Existing structures keep their fractional position; they may
        look slightly off against the different aspect ratio, same as
        switching to any other differently-shaped backdrop."""

        if self.plan.backdrop_filename:
            if not messagebox.askyesno(
                "Use Grid Template", "Switch this site plan back to the blank grid template?", parent=self,
            ):
                return
            self.plan = self.site_plan_service.clear_backdrop_image(self.plan, current_actor())
            self.refresh()
            return

        # Already on the grid - flip its orientation.
        flipped = LANDSCAPE if self.plan.grid_orientation != LANDSCAPE else PORTRAIT
        self.plan = self.site_plan_service.set_grid_orientation(self.plan, flipped, current_actor())
        self.refresh()
        self._flash_hint(f"Grid template switched to {flipped}.")


class MeasurementFormWindow(ctk.CTkToplevel):
    """Measurement entry form — linked to a real site visit.

    Shade-netting measurement rows plus a free-text additional notes
    area. Data is persisted to site_visits.measurements_json on Save.
    """

    _SECTIONS = [
        "Height to Eaves",
        "Bay Width",
        "Structure Length",
        "Cantilever Reach",
        "Ground Condition",
        "Existing Structure",
        "Cable Run",
        "Pole Centres",
        "Clearance Required",
        "Other",
    ]

    def __init__(self, parent, visit=None, customer=None):
        super().__init__(parent)

        self.visit = visit
        self.customer = customer
        self.site_visit_service = SiteVisitService()

        if visit and customer:
            title = f"Measurements — {customer.name} — {visit.visit_date}"
        elif visit:
            title = f"Measurements — {visit.visit_date}"
        else:
            title = "Measurement Form"
        self.title(title)
        self.geometry("900x600")
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)

        # Load existing data
        try:
            saved = json.loads(visit.measurements_json or "{}")
        except Exception:
            saved = {}
        self._rows = {}  # section -> {value_var, unit_var, notes_var}

        self._build_ui(saved)

    def _build_ui(self, saved):

        main_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            main_frame, text="Measurement Form",
            font=FONTS["heading_lg"], text_color=THEME_TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 12))

        scroll = ctk.CTkScrollableFrame(main_frame, fg_color=THEME_SURFACE)
        scroll.pack(fill="both", expand=True, pady=(0, 12))

        # Column headers
        hdr = ctk.CTkFrame(scroll, fg_color=THEME_SURFACE)
        hdr.pack(fill="x", padx=8, pady=(6, 2))
        for text, width in (("Section", 130), ("Value", 100), ("Unit", 80), ("Notes", 0)):
            lbl = ctk.CTkLabel(hdr, text=text, font=FONTS["label_sm"],
                               text_color=THEME_TEXT_SECONDARY, width=width, anchor="w")
            lbl.pack(side="left", padx=(0, 8))

        for section in self._SECTIONS:
            row_data = saved.get(section, {})
            value_var = ctk.StringVar(value=row_data.get("value", ""))
            unit_var = ctk.StringVar(value=row_data.get("unit", "m"))
            notes_var = ctk.StringVar(value=row_data.get("notes", ""))

            row_frame = ctk.CTkFrame(scroll, fg_color=THEME_SURFACE_LIGHT)
            row_frame.pack(fill="x", padx=8, pady=3)

            ctk.CTkLabel(row_frame, text=f"{section}:", width=130, anchor="w",
                         text_color=THEME_TEXT_PRIMARY).pack(side="left", padx=5, pady=5)
            ctk.CTkEntry(row_frame, textvariable=value_var, width=100,
                         placeholder_text="Value").pack(side="left", padx=(0, 8))
            ctk.CTkOptionMenu(row_frame, variable=unit_var, values=["m", "cm", "mm"],
                              width=80, fg_color=THEME_SURFACE).pack(side="left", padx=(0, 8))
            ctk.CTkEntry(row_frame, textvariable=notes_var,
                         placeholder_text="Notes").pack(side="left", padx=(0, 8), expand=True, fill="x")

            self._rows[section] = {"value": value_var, "unit": unit_var, "notes": notes_var}

        # Extra notes
        ctk.CTkLabel(main_frame, text="Additional Notes:", text_color=THEME_TEXT_SECONDARY,
                     anchor="w").pack(anchor="w")
        self.extra_notes = ctk.CTkTextbox(main_frame, height=80, fg_color=THEME_SURFACE_LIGHT)
        self.extra_notes.pack(fill="x", pady=(4, 10))
        if saved.get("_notes"):
            self.extra_notes.insert("1.0", saved["_notes"])

        btn_row = ctk.CTkFrame(main_frame, fg_color=THEME_DARK_GREY)
        btn_row.pack(fill="x")
        ctk.CTkButton(btn_row, text="Save", command=self._save, width=120,
                      fg_color=COLORS["accent_primary"],
                      hover_color=COLORS["accent_hover"]).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Close", command=self.destroy, width=100,
                      fg_color=THEME_SURFACE, text_color=THEME_TEXT_PRIMARY,
                      border_width=1, border_color=COLORS["border_default"]).pack(side="left")

    def _save(self):
        data = {}
        for section, vars_ in self._rows.items():
            data[section] = {
                "value": vars_["value"].get().strip(),
                "unit": vars_["unit"].get(),
                "notes": vars_["notes"].get().strip(),
            }
        data["_notes"] = self.extra_notes.get("1.0", "end").strip()

        if self.visit is None:
            messagebox.showinfo("Measurements", "No visit linked — open from Visit History to save.", parent=self)
            return
        self.visit.measurements_json = json.dumps(data, ensure_ascii=False)
        try:
            self.site_visit_service.save_visit(self.visit, current_actor())
            messagebox.showinfo("Measurements", "Measurements saved.", parent=self)
        except Exception as error:
            messagebox.showerror("Measurements", str(error), parent=self)


class ChecklistWindow(ctk.CTkToplevel):
    """Site inspection checklist — linked to a real site visit.

    10 standard items pre-populated, tick-state persisted to
    site_visits.checklist_json on Save.
    """

    _STANDARD_ITEMS = [
        "Site access verified",
        "Safety zone established",
        "Existing structures assessed",
        "Ground conditions checked",
        "Drainage verified",
        "Utilities located",
        "Photos taken — Before",
        "Measurements recorded",
        "Quotes prepared",
        "Customer sign-off",
    ]

    def __init__(self, parent, visit=None, customer=None):
        super().__init__(parent)

        self.visit = visit
        self.customer = customer
        self.site_visit_service = SiteVisitService()

        if visit and customer:
            title = f"Checklist — {customer.name} — {visit.visit_date}"
        elif visit:
            title = f"Checklist — {visit.visit_date}"
        else:
            title = "Inspection Checklist"
        self.title(title)
        self.geometry("700x560")
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)

        try:
            saved = json.loads(visit.checklist_json or "{}") if visit else {}
        except Exception:
            saved = {}

        self._check_vars = {}
        self._progress_label = None
        self._build_ui(saved)

    def _build_ui(self, saved):

        main_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            main_frame, text="Site Inspection Checklist",
            font=FONTS["heading_lg"], text_color=THEME_TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 8))

        self._progress_label = ctk.CTkLabel(
            main_frame, text="", font=FONTS["label_sm"], text_color=THEME_TEXT_SECONDARY,
        )
        self._progress_label.pack(anchor="w", pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(main_frame, fg_color=THEME_SURFACE)
        scroll.pack(fill="both", expand=True, pady=(0, 12))

        for item in self._STANDARD_ITEMS:
            checked = saved.get(item, False)
            var = ctk.BooleanVar(value=bool(checked))
            var.trace_add("write", lambda *_: self._update_progress())
            self._check_vars[item] = var

            row = ctk.CTkFrame(scroll, fg_color=THEME_SURFACE_LIGHT)
            row.pack(fill="x", padx=8, pady=3)
            ctk.CTkCheckBox(row, text=item, variable=var,
                            text_color=THEME_TEXT_PRIMARY).pack(anchor="w", padx=8, pady=6)

        self._update_progress()

        btn_row = ctk.CTkFrame(main_frame, fg_color=THEME_DARK_GREY)
        btn_row.pack(fill="x")
        ctk.CTkButton(btn_row, text="Save", command=self._save, width=120,
                      fg_color=COLORS["accent_primary"],
                      hover_color=COLORS["accent_hover"]).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Close", command=self.destroy, width=100,
                      fg_color=THEME_SURFACE, text_color=THEME_TEXT_PRIMARY,
                      border_width=1, border_color=COLORS["border_default"]).pack(side="left")

    def _update_progress(self):
        done = sum(1 for v in self._check_vars.values() if v.get())
        total = len(self._check_vars)
        if self._progress_label:
            self._progress_label.configure(text=f"Progress: {done}/{total} items completed")

    def _save(self):
        data = {item: var.get() for item, var in self._check_vars.items()}
        if self.visit is None:
            messagebox.showinfo("Checklist", "No visit linked — open from Visit History to save.", parent=self)
            return
        self.visit.checklist_json = json.dumps(data, ensure_ascii=False)
        try:
            self.site_visit_service.save_visit(self.visit, current_actor())
            messagebox.showinfo("Checklist", "Checklist saved.", parent=self)
        except Exception as error:
            messagebox.showerror("Checklist", str(error), parent=self)


class SiteVisitModuleWindow(ctk.CTkFrame):
    """Module frame embedded in the main window shell.

    Opens SiteVisitHub as a CTkToplevel parented to winfo_toplevel()
    (the real root window), not to self (a CTkFrame) — that was the
    original freeze cause.
    """

    def __init__(self, master):
        super().__init__(master)
        self.configure(fg_color=THEME_DARK_GREY)
        self.hub = None

        ctk.CTkLabel(
            self,
            text="Site Visit",
            font=FONTS["heading_lg"],
            text_color=THEME_TEXT_PRIMARY,
        ).pack(pady=(20, 10))

        ctk.CTkButton(
            self,
            text="Open Site Visit Hub",
            command=self._open_hub,
            height=50,
            font=FONTS["body_md"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
        ).pack(pady=20, padx=40, fill="x")

    def _open_hub(self):
        if self.hub is None or not self.hub.winfo_exists():
            self.hub = SiteVisitHub(self.winfo_toplevel())
        else:
            self.hub.lift()


class JobCardListWindow(ctk.CTkToplevel):
    """Every Job Card for one Site - a per-job/PO work log, scoped
    with Minette 2026-08-07 from a real paper form (a Job Card tied to
    one job/PO, dated rows added as work happens over its life - NOT
    a persistent per-Site record like the Site Plan above). Launched
    from CRM's Sites tab (Site Visit Hub is frozen, so this lives here
    in the same file as SitePlanWindow rather than a standalone
    modules/job_cards package, matching how SitePlanWindow itself is
    launched externally from CRM too - and a standalone package would
    need its own module.py to satisfy framework/module_manager.py's
    auto-discovery, adding an unwanted top-level nav entry she didn't
    ask for). She creates a new one when a job starts and reopens it
    via "Open" (or a double-click) while work is ongoing."""

    def __init__(self, parent, customer, site):
        super().__init__(parent)

        self.title(f"Job Cards — {customer.name} — {site.name or 'Unnamed Site'}")
        self.geometry("800x550")
        self.configure(fg_color=THEME_DARK_GREY)

        self.customer = customer
        self.site = site
        self.service = JobCardService()

        self.table = build_entity_table(
            self,
            ("Job Card #", "PO", "Status", "Created"),
            (
                ("Refresh", self.refresh),
                ("New Job Card", self.new_job_card),
                ("Open", self.open_selected),
                ("Archive", self.archive_selected),
                ("Reactivate", self.reactivate_selected),
            ),
        )
        self.table.bind("<Double-1>", lambda _event: self.open_selected())
        self.refresh()

    def refresh(self):

        self.table.delete(*self.table.get_children())
        for job_card in self.service.list_job_cards_for_site(self.site.id):
            if job_card.archived_at:
                continue
            self.table.insert(
                "", "end", iid=job_card.id, text=job_card.job_card_number,
                values=(job_card.job_card_number, job_card.purchase_order, job_card.status, job_card.created_at[:10]),
            )

    def new_job_card(self):

        po = TextPromptDialog.ask(self, "New Job Card", "Purchase Order (optional):", required=False)
        if po is None:
            return
        job_card = self.service.create_job_card(self.customer, self.site, current_actor(), purchase_order=po)
        self.refresh()
        JobCardWindow(self, self.customer, job_card, on_change=self.refresh)

    def _selected_job_card_id(self):

        selection = self.table.selection()
        if not selection:
            messagebox.showwarning("Job Card", "Select a job card first.", parent=self)
            return None
        return selection[0]

    def open_selected(self):

        job_card_id = self._selected_job_card_id()
        if job_card_id is None:
            return
        job_card = self.service.get_job_card(job_card_id)
        JobCardWindow(self, self.customer, job_card, on_change=self.refresh)

    def archive_selected(self):

        job_card_id = self._selected_job_card_id()
        if job_card_id is None:
            return
        reason = TextPromptDialog.ask(self, "Archive Job Card", "Reason for archiving this job card:")
        if reason is None:
            return
        try:
            self.service.archive_job_card(job_card_id, current_actor(), reason)
        except ValueError as error:
            messagebox.showerror("Archive Job Card", str(error), parent=self)
            return
        self.refresh()

    def reactivate_selected(self):

        job_card_id = self._selected_job_card_id()
        if job_card_id is None:
            return
        self.service.reactivate_job_card(job_card_id, current_actor())
        self.refresh()


class JobCardWindow(ctk.CTkToplevel):
    """One Job Card - header (PO/bill-to/delivery address/status) plus
    the dated work-log entries table. No pricing fields - she said to
    leave amounts off for v1."""

    def __init__(self, parent, customer, job_card, on_change=None):
        super().__init__(parent)

        self.customer = customer
        self.job_card = job_card
        self.service = JobCardService()
        self.on_change = on_change

        self.geometry("1000x650")
        self.configure(fg_color=THEME_DARK_GREY)
        self.transient(parent)

        self.header_frame = ctk.CTkFrame(self, fg_color=THEME_SURFACE)
        self.header_frame.pack(fill="x", padx=15, pady=15)
        self._build_header()

        table_frame = ctk.CTkFrame(self, fg_color=THEME_DARK_GREY)
        table_frame.pack(fill="both", expand=True)
        self.table = build_entity_table(
            table_frame,
            ("Date", "Type", "Job", "Description", "Staff", "Completed", "Director"),
            (
                ("Refresh", self.refresh),
                ("Add Entry", self.add_entry),
                ("Edit Entry", self.edit_entry),
                ("Delete Entry", self.delete_entry),
            ),
        )
        self.refresh()

    def _build_header(self):

        for widget in self.header_frame.winfo_children():
            widget.destroy()

        self.title(f"Job Card {self.job_card.job_card_number} — {self.customer.name}")

        ctk.CTkLabel(
            self.header_frame, text=f"Job Card {self.job_card.job_card_number}",
            font=FONTS["heading_md"], text_color=THEME_TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))

        details = (
            f"Bill To: {self.job_card.bill_to_name or self.customer.name}    "
            f"PO: {self.job_card.purchase_order or '—'}    "
            f"Status: {self.job_card.status}"
        )
        ctk.CTkLabel(self.header_frame, text=details, text_color=THEME_TEXT_SECONDARY).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 4),
        )
        if self.job_card.delivery_address:
            ctk.CTkLabel(
                self.header_frame, text=f"Delivery: {self.job_card.delivery_address}", text_color=THEME_TEXT_SECONDARY,
            ).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))

        button_row = ctk.CTkFrame(self.header_frame, fg_color=THEME_SURFACE)
        button_row.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 10))

        ctk.CTkButton(button_row, text="Edit Job Card", command=self.edit_job_card, width=120).pack(side="left", padx=(0, 8))
        if self.job_card.site_id:
            ctk.CTkButton(button_row, text="Draw Site Plan", command=self._open_site_plan, width=130).pack(side="left", padx=(0, 8))
        toggle_text = "Close Job Card" if self.job_card.status == OPEN else "Reopen Job Card"
        ctk.CTkButton(button_row, text=toggle_text, command=self.toggle_status, width=130).pack(side="left", padx=(0, 8))
        ctk.CTkButton(button_row, text="Export docx", command=self.export_docx, width=110).pack(side="left", padx=(0, 8))
        ctk.CTkButton(button_row, text="Close Window", command=self.destroy, width=110).pack(side="left")

    def _open_site_plan(self):
        from core.crm_service import CRMService
        crm = CRMService()
        site = crm.sites.get(self.job_card.site_id)
        if not site:
            from tkinter import messagebox as mb
            mb.showinfo("No Site", "Could not load the site for this job card.", parent=self)
            return
        SitePlanWindow(self.winfo_toplevel(), self.customer, site)

    def edit_job_card(self):

        fields = [
            {"key": "purchase_order", "label": "Purchase Order", "kind": "text", "initial": self.job_card.purchase_order},
            {"key": "bill_to_name", "label": "Bill To", "kind": "text", "initial": self.job_card.bill_to_name or self.customer.name},
            {"key": "delivery_address", "label": "Delivery Address", "kind": "textarea", "initial": self.job_card.delivery_address},
            {"key": "notes", "label": "Notes", "kind": "textarea", "initial": self.job_card.notes},
        ]
        result = EntityFormDialog.ask(self, f"Edit Job Card {self.job_card.job_card_number}", fields)
        if result is None:
            return

        self.job_card.purchase_order = result["purchase_order"]
        self.job_card.bill_to_name = result["bill_to_name"]
        self.job_card.delivery_address = result["delivery_address"]
        self.job_card.notes = result["notes"]
        self.job_card = self.service.save_job_card(self.job_card, current_actor())
        self._build_header()
        self._notify_change()

    def toggle_status(self):

        if self.job_card.status == OPEN:
            self.job_card = self.service.close_job_card(self.job_card, current_actor())
        else:
            self.job_card = self.service.reopen_job_card(self.job_card, current_actor())
        self._build_header()
        self._notify_change()

    def export_docx(self):
        from tkinter import messagebox, filedialog
        from core.job_card_docx import generate_job_card_docx
        from core.client_document_saver import ClientDocumentSaver, safe_filename

        entries = self.service.list_entries(self.job_card.id)
        filename = safe_filename(self.job_card.job_card_number or "JobCard") + ".docx"

        saver = ClientDocumentSaver()
        path = saver.paperwork_path(self.customer, filename)

        if path is None:
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Save Job Card",
                defaultextension=".docx",
                filetypes=[("Word document", "*.docx")],
                initialfile=filename,
            )
            if not path:
                return

        try:
            generate_job_card_docx(self.job_card, self.customer, entries, path)
            messagebox.showinfo(
                "Exported",
                f"Job Card saved to:\n{path}",
                parent=self,
            )
        except Exception as e:
            messagebox.showerror("Export failed", str(e), parent=self)

    def _notify_change(self):

        if self.on_change:
            self.on_change()

    def refresh(self):

        self.table.delete(*self.table.get_children())
        for entry in self.service.list_entries(self.job_card.id):
            self.table.insert(
                "", "end", iid=entry.id, text=entry.entry_date,
                values=(
                    entry.entry_date, entry.work_type, entry.job_summary, entry.description,
                    entry.staff, "Yes" if entry.completed else "", entry.director_signoff,
                ),
            )

    def add_entry(self):

        entry = self.service.new_entry(self.job_card.id)
        self._open_entry_form(entry, is_new=True)

    def _selected_entry_id(self):

        selection = self.table.selection()
        if not selection:
            messagebox.showwarning("Job Card", "Select an entry first.", parent=self)
            return None
        return selection[0]

    def edit_entry(self):

        entry_id = self._selected_entry_id()
        if entry_id is None:
            return
        entry = next((e for e in self.service.list_entries(self.job_card.id) if e.id == entry_id), None)
        if entry is None:
            return
        self._open_entry_form(entry, is_new=False)

    def _open_entry_form(self, entry, is_new):

        fields = [
            {"key": "entry_date", "label": "Date (YYYY-MM-DD)", "kind": "text", "initial": entry.entry_date},
            {"key": "work_type", "label": "Type (e.g. Repairs)", "kind": "text", "initial": entry.work_type},
            {"key": "job_summary", "label": "Job (e.g. 3 Nets)", "kind": "text", "initial": entry.job_summary},
            {"key": "description", "label": "Description", "kind": "textarea", "initial": entry.description},
            {"key": "staff", "label": "Staff", "kind": "text", "initial": entry.staff},
            {"key": "completed", "label": "Completed", "kind": "checkbox", "initial": entry.completed},
            {"key": "director_signoff", "label": "Director Sign-off", "kind": "text", "initial": entry.director_signoff},
        ]
        title = "Add Entry" if is_new else "Edit Entry"
        result = EntityFormDialog.ask(self, title, fields)
        if result is None:
            return

        entry.entry_date = result["entry_date"].strip()
        entry.work_type = result["work_type"]
        entry.job_summary = result["job_summary"]
        entry.description = result["description"]
        entry.staff = result["staff"]
        entry.completed = result["completed"]
        entry.director_signoff = result["director_signoff"]

        try:
            self.service.save_entry(entry)
        except ValueError as error:
            messagebox.showerror("Job Card", str(error), parent=self)
            return

        self.refresh()

    def delete_entry(self):

        entry_id = self._selected_entry_id()
        if entry_id is None:
            return
        if not messagebox.askyesno("Delete Entry", "Remove this entry from the job card?", parent=self):
            return
        self.service.delete_entry(entry_id)
        self.refresh()
