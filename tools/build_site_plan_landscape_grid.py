# ==========================================================
# FC Hub - Landscape Site Plan Grid Generator
# ----------------------------------------------------------
# Purpose:
# Generate assets/site_plan_default_grid_landscape.png, the
# landscape counterpart of Minette's portrait measurement sheet.
#
# Most of her sites are car parks - wide, not tall - so a portrait
# sheet wasted more than half the canvas (measured: 514 of 1214
# available pixels). Asked for 2026-08-12.
#
# The measurements below were taken FROM the real portrait sheet
# (assets/site_plan_default_grid.png) so the two look like the same
# stationery: 7px black border, a 68px title box, 3px grey (217)
# rules, verticals every 72px, dashed horizontals every 68px.
#
# Run: python tools/build_site_plan_landscape_grid.py
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from pathlib import Path

from PIL import Image, ImageDraw

# Portrait is 1315 x 1907; landscape is the same sheet turned.
WIDTH, HEIGHT = 1907, 1315

BORDER = 7
HEADER_HEIGHT = 68
RULE_COLOUR = (217, 217, 217)
RULE_WIDTH = 3
VERTICAL_SPACING = 72
HORIZONTAL_SPACING = 68
DASH_ON, DASH_OFF = 24, 10   # ~70% duty, matching the portrait sheet


def dashed_line(draw, x_start, x_end, y):

    x = x_start
    while x < x_end:
        draw.line([x, y, min(x + DASH_ON, x_end), y], fill=RULE_COLOUR, width=RULE_WIDTH)
        x += DASH_ON + DASH_OFF


def build():

    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)

    grid_top = BORDER + HEADER_HEIGHT
    left, right = BORDER, WIDTH - BORDER
    bottom = HEIGHT - BORDER

    y = grid_top + HORIZONTAL_SPACING
    while y < bottom:
        dashed_line(draw, left, right, y)
        y += HORIZONTAL_SPACING

    x = left + VERTICAL_SPACING
    while x < right:
        draw.line([x, grid_top, x, bottom], fill=RULE_COLOUR, width=RULE_WIDTH)
        x += VERTICAL_SPACING

    # Outer frame and the title box across the top, drawn last so the
    # rules never overlap them.
    draw.rectangle([0, 0, WIDTH - 1, HEIGHT - 1], outline="black", width=BORDER)
    draw.line([left, grid_top, right, grid_top], fill="black", width=BORDER)

    destination = Path(__file__).resolve().parents[1] / "assets" / "site_plan_default_grid_landscape.png"
    image.save(destination, optimize=True)
    print(f"wrote {destination} ({image.width}x{image.height})")


if __name__ == "__main__":
    build()
