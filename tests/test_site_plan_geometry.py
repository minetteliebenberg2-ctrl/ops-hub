"""Tests for rotated Site Plan structures - scoped with Minette
2026-08-12 from a satellite screenshot of Cavaleros head office, where
the shade structures follow curved driveways at half a dozen angles.

These are the fiddly parts (corner maths, hit-testing, snapping) that
would otherwise only be testable by clicking a canvas.
"""

import math

import pytest

from core.site_plan_geometry import (
    DEFAULT_SNAP_TOLERANCE_DEGREES,
    angle_of,
    angular_difference,
    bounding_box,
    normalize_angle,
    normalize_orientation,
    perpendicular_distance,
    point_in_polygon,
    rectangle_from_baseline,
    rotated_corners,
    snap_to_nearest,
)


def close(a, b, tolerance=1e-6):
    return abs(a - b) < tolerance


# ------------------------------------------------------------------
# Angles
# ------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    (0, 0), (90, 90), (180, 180), (181, -179), (360, 0), (-90, -90), (450, 90),
])
def test_normalize_angle_folds_into_a_half_turn_either_way(raw, expected):
    assert close(normalize_angle(raw), expected)


@pytest.mark.parametrize("raw, expected", [
    (0, 0), (10, 10), (180, 0), (190, 10), (-170, 10), (360, 0),
])
def test_normalize_orientation_treats_a_half_turn_as_the_same(raw, expected):
    """A rectangle at 10 degrees and one at 190 look identical."""
    assert close(normalize_orientation(raw), expected)


def test_angle_of_a_horizontal_drag_is_zero():
    assert close(angle_of(0, 0, 100, 0), 0)


def test_angle_of_a_downward_drag_is_positive():
    """Canvas y grows downwards, so a drag down-right reads positive."""
    assert close(angle_of(0, 0, 100, 100), 45)


def test_angle_of_an_upward_drag_is_negative():
    assert close(angle_of(0, 0, 100, -100), -45)


def test_angle_of_a_vertical_drag():
    assert close(angle_of(0, 0, 0, 100), 90)


# ------------------------------------------------------------------
# Angular difference - the basis of snapping
# ------------------------------------------------------------------

@pytest.mark.parametrize("a, b, expected", [
    (0, 0, 0),
    (10, 15, 5),
    (0, 180, 0),      # same orientation
    (179, 1, 2),      # wraps the short way, not 178
    (0, 90, 90),      # the most two orientations can differ
    (-15, 165, 0),
])
def test_angular_difference(a, b, expected):
    assert close(angular_difference(a, b), expected)


def test_angular_difference_never_exceeds_ninety():
    for a in range(-360, 361, 7):
        for b in range(-360, 361, 11):
            assert 0 <= angular_difference(a, b) <= 90 + 1e-9


# ------------------------------------------------------------------
# Snapping - her rule: line up with neighbours, but let exceptions be
# ------------------------------------------------------------------

def test_a_near_miss_snaps_to_the_neighbour():
    assert close(snap_to_nearest(-17.0, [-15.0], tolerance=7.0), -15.0)


def test_a_deliberate_off_angle_drag_is_left_alone():
    """She said structures mostly share an angle "with exceptions" - if
    everything snapped, the exceptions would be impossible to draw."""
    assert close(snap_to_nearest(40.0, [-15.0], tolerance=7.0), 40.0)


def test_snapping_picks_the_closest_of_several_neighbours():
    assert close(snap_to_nearest(-16.0, [-15.0, -20.0, 80.0], tolerance=7.0), -15.0)


def test_no_neighbours_means_no_snapping():
    assert close(snap_to_nearest(33.3, [], tolerance=7.0), 33.3)


def test_snapping_respects_the_half_turn_equivalence():
    """Tracing a row right-to-left gives an angle 180 off, but it is
    the same orientation and must still line up."""
    assert close(snap_to_nearest(163.0, [-15.0], tolerance=7.0), -15.0)


def test_default_tolerance_is_tight_enough_for_cavaleros():
    """Cavaleros has rows at distinctly different angles; the default
    tolerance must not drag one row onto another's angle."""
    cavaleros_angles = [-15.0, 80.0, -7.0, 87.0, -28.0]
    for i, a in enumerate(cavaleros_angles):
        others = [b for j, b in enumerate(cavaleros_angles) if j != i]
        snapped = snap_to_nearest(a, others, tolerance=DEFAULT_SNAP_TOLERANCE_DEGREES)
        if min(angular_difference(a, b) for b in others) > DEFAULT_SNAP_TOLERANCE_DEGREES:
            assert close(snapped, a), f"{a} was wrongly pulled onto another row"


# ------------------------------------------------------------------
# Corners
# ------------------------------------------------------------------

def test_unrotated_corners_match_a_plain_rectangle():
    corners = rotated_corners(100, 100, 40, 20, 0)
    assert corners == [(80, 90), (120, 90), (120, 110), (80, 110)]


def test_rotating_by_ninety_swaps_the_extents():
    x0, y0, x1, y1 = bounding_box(rotated_corners(100, 100, 40, 20, 90))
    assert close(x1 - x0, 20)
    assert close(y1 - y0, 40)


def test_rotation_preserves_the_centre():
    for degrees in (0, 17, 45, 90, 133, -62):
        corners = rotated_corners(250, 175, 60, 30, degrees)
        assert close(sum(p[0] for p in corners) / 4, 250, 1e-9)
        assert close(sum(p[1] for p in corners) / 4, 175, 1e-9)


def test_rotation_preserves_side_lengths():
    corners = rotated_corners(0, 0, 80, 40, 33)
    sides = [math.dist(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    assert close(sides[0], 80, 1e-9) and close(sides[2], 80, 1e-9)
    assert close(sides[1], 40, 1e-9) and close(sides[3], 40, 1e-9)


def test_corners_stay_in_order_for_create_polygon():
    """Adjacent corners must share an edge, or the polygon draws as a
    bow tie."""
    corners = rotated_corners(0, 0, 100, 20, 25)
    long_sides = [math.dist(corners[0], corners[1]), math.dist(corners[2], corners[3])]
    assert all(close(s, 100, 1e-9) for s in long_sides)


def test_a_half_turn_gives_the_same_shape():
    a = bounding_box(rotated_corners(50, 50, 40, 20, 20))
    b = bounding_box(rotated_corners(50, 50, 40, 20, 200))
    assert all(close(p, q, 1e-9) for p, q in zip(a, b))


# ------------------------------------------------------------------
# Hit-testing - the bug a bounding box would cause on a dense lot
# ------------------------------------------------------------------

def test_centre_is_inside():
    assert point_in_polygon(100, 100, rotated_corners(100, 100, 60, 30, 30))


def test_far_away_is_outside():
    assert not point_in_polygon(500, 500, rotated_corners(100, 100, 60, 30, 30))


def test_a_corner_of_the_bounding_box_is_outside_the_rotated_shape():
    """The exact reason a bounding-box test is wrong: this point is
    inside the bounds but outside the structure, and on a dense lot it
    belongs to the neighbouring row."""
    corners = rotated_corners(100, 100, 100, 20, 45)
    x0, y0, _x1, _y1 = bounding_box(corners)

    assert not point_in_polygon(x0 + 1, y0 + 1, corners)


def test_points_along_the_long_axis_are_inside():
    corners = rotated_corners(0, 0, 200, 20, 0)
    for x in (-90, -40, 0, 40, 90):
        assert point_in_polygon(x, 0, corners), x


def test_just_outside_the_long_edge_is_outside():
    corners = rotated_corners(0, 0, 200, 20, 0)
    assert not point_in_polygon(0, 11, corners)
    assert point_in_polygon(0, 9, corners)


def test_two_adjacent_rows_do_not_claim_each_others_points():
    """Two parallel structures 40px apart, angled - a click on one must
    never register as the other."""
    lower = rotated_corners(100, 140, 160, 30, -20)
    upper = rotated_corners(100, 100, 160, 30, -20)

    centre_of_upper = (100, 100)
    assert point_in_polygon(*centre_of_upper, upper)
    assert not point_in_polygon(*centre_of_upper, lower)


# ------------------------------------------------------------------
# Turning her two drags into a structure
# ------------------------------------------------------------------

def test_baseline_sets_the_angle():
    *_rest, degrees = rectangle_from_baseline(0, 0, 100, -100, depth=40)
    assert close(degrees, -45)


def test_baseline_length_becomes_the_structure_length():
    _cx, _cy, length, _depth, _deg = rectangle_from_baseline(0, 0, 300, 0, depth=50)
    assert close(length, 300)


def test_depth_is_measured_from_the_baseline_not_through_it():
    """The traced line is one edge of the structure, so the centre sits
    half the depth off it - otherwise the structure would straddle the
    row she traced."""
    cx, cy, _length, depth, _deg = rectangle_from_baseline(0, 0, 100, 0, depth=40)

    assert close(cx, 50)
    assert close(cy, 20)
    assert close(depth, 40)


def test_dragging_the_depth_the_other_way_still_works():
    cx, cy, _length, depth, _deg = rectangle_from_baseline(0, 0, 100, 0, depth=-40)

    assert close(cx, 50)
    assert close(cy, -20)
    assert close(depth, 40), "depth is a size, so it is never negative"


def test_the_traced_baseline_lies_on_the_structures_edge():
    cx, cy, length, depth, degrees = rectangle_from_baseline(20, 60, 220, 60, depth=40)
    corners = rotated_corners(cx, cy, length, depth, degrees)

    assert any(close(x, 20, 1e-6) and close(y, 60, 1e-6) for x, y in corners)
    assert any(close(x, 220, 1e-6) and close(y, 60, 1e-6) for x, y in corners)


def test_an_angled_baseline_also_lands_on_the_edge():
    x0, y0, x1, y1 = 40, 200, 240, 130
    cx, cy, length, depth, degrees = rectangle_from_baseline(x0, y0, x1, y1, depth=55)
    corners = rotated_corners(cx, cy, length, depth, degrees)

    assert any(close(x, x0, 1e-6) and close(y, y0, 1e-6) for x, y in corners)
    assert any(close(x, x1, 1e-6) and close(y, y1, 1e-6) for x, y in corners)


# ------------------------------------------------------------------
# Live depth while the second drag is in progress
# ------------------------------------------------------------------

def test_perpendicular_distance_is_zero_on_the_line():
    assert close(perpendicular_distance(0, 0, 100, 0, 50, 0), 0)


def test_perpendicular_distance_measures_straight_out():
    assert close(abs(perpendicular_distance(0, 0, 100, 0, 50, 30)), 30)


def test_perpendicular_distance_is_signed_for_either_side():
    above = perpendicular_distance(0, 0, 100, 0, 50, -30)
    below = perpendicular_distance(0, 0, 100, 0, 50, 30)
    assert above * below < 0, "the two sides must have opposite signs"


def test_perpendicular_distance_survives_a_zero_length_baseline():
    """Guards a click without a drag - must not divide by zero."""
    assert close(perpendicular_distance(10, 10, 10, 10, 40, 40), 0)


def test_depth_round_trips_through_the_rectangle():
    """What she sees while dragging must match what gets stored."""
    x0, y0, x1, y1 = 30, 90, 210, 150
    pointer_x, pointer_y = 120, 200

    depth = perpendicular_distance(x0, y0, x1, y1, pointer_x, pointer_y)
    _cx, _cy, _length, stored_depth, _deg = rectangle_from_baseline(x0, y0, x1, y1, depth)

    assert close(stored_depth, abs(depth))
