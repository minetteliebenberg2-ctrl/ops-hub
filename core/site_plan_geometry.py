# ==========================================================
# FC Hub - Site Plan Geometry
# ----------------------------------------------------------
# Purpose:
# The maths behind rotated (non-axis-aligned) structures on the
# Site Plan. Scoped with Minette 2026-08-12 from a satellite
# screenshot of Cavaleros head office, where the shade structures
# follow curved driveways at half a dozen different angles.
#
# Pure functions, no Tkinter, no database - so the fiddly parts
# (corner maths, hit-testing, snapping) are testable headless
# rather than only by clicking a canvas.
#
# A note on coordinate spaces, because it is the easy thing to
# get wrong: SitePlanItem stores x/y/width/height as fractions
# (0.0-1.0) of the BACKDROP, and x is a fraction of the image's
# width while y is a fraction of its height. That space is
# anisotropic, so rotating in it would skew the shape on any
# non-square image. Every rotation here happens in DISPLAY PIXEL
# space, which preserves the image's aspect ratio (SitePlanWindow
# scales the backdrop by a single uniform factor). Convert to
# pixels first, rotate, then draw.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import math

# A rectangle rotated by 180 degrees looks identical, so orientation
# is only meaningful modulo 180 - used when comparing/snapping angles.
ORIENTATION_PERIOD = 180.0

# How close to a neighbouring structure's angle counts as "she meant
# to line up with it". Deliberately small: she said structures mostly
# share an angle "with exceptions", so a clearly off-angle drag has to
# survive unsnapped or the exceptions become impossible to draw.
DEFAULT_SNAP_TOLERANCE_DEGREES = 7.0


def normalize_angle(degrees):
    """Fold an angle into (-180, 180]."""

    angle = math.fmod(degrees, 360.0)
    if angle <= -180.0:
        angle += 360.0
    elif angle > 180.0:
        angle -= 360.0
    return angle


def normalize_orientation(degrees):
    """Fold an angle into [0, 180) - the range in which two rectangle
    orientations are genuinely different."""

    return math.fmod(math.fmod(degrees, ORIENTATION_PERIOD) + ORIENTATION_PERIOD, ORIENTATION_PERIOD)


def angle_of(x0, y0, x1, y1):
    """Angle in degrees of the line from (x0, y0) to (x1, y1).

    This is what turns her first drag - tracing along a row of existing
    structures - into the angle the new structure is drawn at."""

    return normalize_angle(math.degrees(math.atan2(y1 - y0, x1 - x0)))


def angular_difference(first, second):
    """Smallest angle between two ORIENTATIONS, in [0, 90].

    Modulo 180 because a rectangle at 10 degrees and one at 190 look
    the same; the extra fold handles 179 vs 1 being 2 degrees apart,
    not 178."""

    difference = abs(normalize_orientation(first) - normalize_orientation(second))
    return min(difference, ORIENTATION_PERIOD - difference)


def snap_to_nearest(angle, candidates, tolerance=DEFAULT_SNAP_TOLERANCE_DEGREES):
    """Return the candidate angle within tolerance of angle, else angle
    unchanged.

    Her rule: snap to what is beside it, not to a site-wide angle. A
    drag that is clearly off-angle keeps exactly what she drew."""

    best = None
    best_difference = None

    for candidate in candidates:
        difference = angular_difference(angle, candidate)
        if difference <= tolerance and (best_difference is None or difference < best_difference):
            best, best_difference = candidate, difference

    return angle if best is None else best


def rotated_corners(centre_x, centre_y, width, height, degrees):
    """The four corners of a width x height rectangle centred at
    (centre_x, centre_y) and rotated by degrees, clockwise on screen
    (y grows downwards on a canvas).

    Returned in order, so the result can go straight to
    Canvas.create_polygon - which is how a rotated structure gets
    drawn at all, since create_rectangle is axis-aligned by
    definition."""

    radians = math.radians(degrees)
    cos_a, sin_a = math.cos(radians), math.sin(radians)
    half_w, half_h = width / 2.0, height / 2.0

    corners = []
    for dx, dy in ((-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)):
        corners.append((centre_x + dx * cos_a - dy * sin_a, centre_y + dx * sin_a + dy * cos_a))
    return corners


def point_in_polygon(x, y, polygon):
    """Ray-casting point-in-polygon test.

    Replaces the bounding-box check the Site Plan used while every
    structure was axis-aligned. A rotated rectangle's bounding box is
    much larger than the shape itself, so on a dense lot like
    Cavaleros a box test would select the structure next door."""

    inside = False
    count = len(polygon)

    for index in range(count):
        x0, y0 = polygon[index]
        x1, y1 = polygon[(index + 1) % count]

        # Does the edge straddle the horizontal ray at y, and is the
        # crossing to the right of x?
        if (y0 > y) != (y1 > y):
            crossing_x = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if crossing_x > x:
                inside = not inside

    return inside


def bounding_box(polygon):
    """Axis-aligned bounds of a polygon - still useful as a cheap
    first pass before the full point-in-polygon test."""

    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def rectangle_from_baseline(x0, y0, x1, y1, depth):
    """Turn her two drags into a rectangle.

    (x0, y0) -> (x1, y1) is the baseline she traced along the row, and
    depth is how far she then pulled it out perpendicular. Returns
    (centre_x, centre_y, length, depth, degrees). A negative depth
    pulls out the other side, so it works whichever way she drags."""

    degrees = angle_of(x0, y0, x1, y1)
    length = math.hypot(x1 - x0, y1 - y0)

    radians = math.radians(degrees)
    midpoint_x = (x0 + x1) / 2.0
    midpoint_y = (y0 + y1) / 2.0

    # Offset half the depth along the baseline's normal.
    centre_x = midpoint_x - (depth / 2.0) * math.sin(radians)
    centre_y = midpoint_y + (depth / 2.0) * math.cos(radians)

    return centre_x, centre_y, length, abs(depth), degrees


def perpendicular_distance(x0, y0, x1, y1, x, y):
    """Signed distance from the baseline (x0,y0)->(x1,y1) to (x, y).

    This is the depth while she is still dragging the second stroke -
    signed, so dragging to either side of the line works."""

    length = math.hypot(x1 - x0, y1 - y0)
    if length == 0:
        return 0.0

    # Cross product of the baseline direction with the vector to (x, y).
    # Negated so that dragging below the baseline (the common case —
    # structures extend downward from their top edge) yields a positive
    # depth, matching screen coordinates where +y is down.
    return -((x - x0) * (y1 - y0) - (y - y0) * (x1 - x0)) / length
