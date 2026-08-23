# ==========================================================
# FC Hub - Document PDF Branding
# ----------------------------------------------------------
# Purpose:
# Shared branding for every generated business document (Quote,
# Pro Forma, Invoice, Statement, Job Card, ...): colors, the
# tagline, and a branded page frame with clickable social icons
# and website link. Each document type builds its own content
# on top of this via SimpleDocTemplate(onFirstPage=..., ...).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping

from core.app_paths import get_assets_dir


# Lato (SIL Open Font License), chosen 2026-08-03 to replace ReportLab's
# built-in Helvetica default. Humanist sans - warmer than Helvetica, slightly
# narrower so long line-item descriptions wrap less, and it complements the
# geometric FacilitiesCo wordmark. Falls back to Helvetica if the TTFs are
# missing so a document never fails to generate over a font.
FONT_DIR = get_assets_dir() / "fonts"

BODY_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"


def _register_fonts():
    """Register Lato and wire up the bold/italic family mapping so <b> and <i>
    markup inside Paragraphs resolves. Returns (regular, bold) face names."""

    global BODY_FONT, BOLD_FONT

    faces = {
        "Lato": "Lato-Regular.ttf",
        "Lato-Bold": "Lato-Bold.ttf",
        "Lato-Italic": "Lato-Italic.ttf",
        "Lato-BoldItalic": "Lato-BoldItalic.ttf",
    }
    if not all((FONT_DIR / filename).is_file() for filename in faces.values()):
        return BODY_FONT, BOLD_FONT

    try:
        for name, filename in faces.items():
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
    except Exception:
        return BODY_FONT, BOLD_FONT

    # (family, bold, italic) -> face
    addMapping("Lato", 0, 0, "Lato")
    addMapping("Lato", 1, 0, "Lato-Bold")
    addMapping("Lato", 0, 1, "Lato-Italic")
    addMapping("Lato", 1, 1, "Lato-BoldItalic")

    BODY_FONT, BOLD_FONT = "Lato", "Lato-Bold"
    return BODY_FONT, BOLD_FONT


_register_fonts()


# Unified with the proposal/spec-sheet documents on 2026-07-31 (was a
# lighter #4CBE82 sampled from the logo in an earlier session - Minette
# asked for a single consistent green across every document type).
ACCENT_COLOR = colors.HexColor("#1B7A3D")
ACCENT_TINT = colors.HexColor("#ECF4EF")
INK_COLOR = colors.HexColor("#3A3A3A")  # dark grey, not pure black, per Minette's request
GREY_COLOR = colors.HexColor("#6B7280")
RULE_COLOR = colors.HexColor("#E4E7EB")

TAGLINE = "DESIGN  |  CREATE  |  INNOVATE  |  MAINTAIN"

# Deliberately city-level only. The registered address (11 Francis Road) is
# Minette's home address - she asked on 2026-08-03 that it never appear on any
# client-facing document. Do not add a street line here or pull one in from
# an address record.
BUSINESS_LOCALITY = "Germiston, South Africa, 1401"
PROOF_OF_PAYMENT_NOTE = "Please send proof of payment to sales@facilitiesco.com."

SOCIAL_HANDLE = "@FacilitiesCo"

# Built from the confirmed handle pattern (same handle on every platform).
# Not independently verified against Minette's actual profile URLs - if
# any of these don't resolve, tell me the real one and I'll fix it here
# once for every document type.
SOCIAL_LINKS = (
    ("IG", "https://instagram.com/FacilitiesCo"),
    ("FB", "https://facebook.com/FacilitiesCo"),
    ("YT", "https://youtube.com/@FacilitiesCo"),
    ("in", "https://linkedin.com/company/FacilitiesCo"),
)

PAGE_MARGIN = 14 * mm
FOOTER_HEIGHT = 24 * mm

_ICON_DIAMETER = 4.2 * mm
_ICON_GAP = 2.2 * mm


def draw_page_frame(canvas, doc, business_settings):
    """Branded footer used by every document type: tagline, registration/
    VAT line, clickable social icons, clickable website, page number."""

    canvas.saveState()

    # From the doc, not a hardcoded A4, so the same branded footer works
    # on a landscape page (the Site Plan export) - every portrait
    # document still reports exactly A4 here.
    page_width, _page_height = getattr(doc, "pagesize", A4)

    canvas.setStrokeColor(RULE_COLOR)
    canvas.setLineWidth(0.6)
    canvas.line(PAGE_MARGIN, FOOTER_HEIGHT, page_width - PAGE_MARGIN, FOOTER_HEIGHT)

    canvas.setFont(BOLD_FONT, 8)
    canvas.setFillColor(INK_COLOR)
    canvas.drawString(PAGE_MARGIN, FOOTER_HEIGHT - 10, TAGLINE)

    canvas.setFont(BODY_FONT, 7.5)
    canvas.setFillColor(GREY_COLOR)
    vat_line = (
        f"VAT Reg: {business_settings.vat_number}"
        if business_settings.vat_registered
        else "Not VAT registered"
    )
    canvas.drawString(PAGE_MARGIN, FOOTER_HEIGHT - 21, f"Reg: {business_settings.registration_number}  |  {vat_line}")

    if business_settings.website:
        website_text = business_settings.website
        text_width = canvas.stringWidth(website_text, BODY_FONT, 7.5)
        website_x = page_width - PAGE_MARGIN - text_width
        canvas.setFillColor(ACCENT_COLOR)
        canvas.drawString(website_x, FOOTER_HEIGHT - 21, website_text)
        canvas.linkURL(
            f"https://{website_text}" if not website_text.startswith("http") else website_text,
            (website_x, FOOTER_HEIGHT - 24, page_width - PAGE_MARGIN, FOOTER_HEIGHT - 17),
            relative=0,
        )

    _draw_social_icons(canvas, page_width - PAGE_MARGIN, FOOTER_HEIGHT - 10)

    canvas.restoreState()


def _draw_social_icons(canvas, right_x, center_y):

    radius = _ICON_DIAMETER / 2
    x = right_x - radius

    for label, url in reversed(SOCIAL_LINKS):
        canvas.setFillColor(INK_COLOR)
        canvas.circle(x, center_y, radius, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont(BOLD_FONT, 5.2)
        canvas.drawCentredString(x, center_y - 1.8, label)
        canvas.linkURL(
            url,
            (x - radius, center_y - radius, x + radius, center_y + radius),
            relative=0,
        )
        x -= _ICON_DIAMETER + _ICON_GAP
