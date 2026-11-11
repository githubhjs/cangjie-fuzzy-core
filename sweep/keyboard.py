"""Keyboard geometry for the sweep decoder. Re-uses core/layout.py (one source of truth for key centres).

Everything is in KEY-WIDTH units, so one parameter set means the same thing on every screen.
  default_layout()          ANSI QWERTY, the same geometry as core.layout.qwerty_pc()
  layout_from_rects(rects)  the keys an on-screen keyboard actually draws; returns (Layout, key_width_in_pixels)
  to_key_units(points, scale, origin)  pixels -> key widths for (x, y, t_ms) samples
"""
import math
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.layout import Layout, qwerty_pc, phone_qwerty, from_rects  # noqa: E402,F401

ALPHA = "abcdefghijklmnopqrstuvwxyz"


def default_layout():
    return qwerty_pc()


def layout_from_rects(rects):
    """rects = {key: (left, top, right, bottom)} in pixels. Returns (Layout in key widths, pixels per key width)."""
    layout = from_rects(rects)
    widths = sorted(r[2] - r[0] for r in rects.values())
    return layout, float(widths[len(widths) // 2])


def to_key_units(points, scale, origin=(0.0, 0.0)):
    """Pixel samples (x, y, t_ms) -> key widths. `origin` is the pixel position that corresponds to layout (0, 0):
    pass (0, 0) when the rects were given in the same pixel frame as the points (the usual case)."""
    ox, oy = origin
    return [((x - ox) / scale, (y - oy) / scale, t) for (x, y, t) in points]


def nearest_key(layout, x, y):
    best, bd = None, 1e18
    for k, (cx, cy) in layout.centers.items():
        d = (cx - x) ** 2 + (cy - y) ** 2
        if d < bd:
            best, bd = k, d
    return best, math.sqrt(bd)


def key_sequence(layout, points, max_dist=0.75):
    """Keys the path passes over (nearest key within max_dist key widths), repeats collapsed. For display and tests."""
    seq = []
    for p in points:
        k, d = nearest_key(layout, p[0], p[1])
        if d <= max_dist and (not seq or seq[-1] != k):
            seq.append(k)
    return seq
