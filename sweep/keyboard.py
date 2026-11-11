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


def _median(v):
    v = sorted(v)
    return v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2.0


def axis_scales(centers_px, rect_widths=None):
    """THE NORMALISATION RULE (ports must follow it). centers_px = {key: (cx, cy)} in pixels (any origin).
    sx = median distance between horizontally adjacent keys of the same row (centre to centre; includes the gap between keys);
    sy = median distance between consecutive ROW centres (mean cy of each row; rows = clusters of cy separated by more than half the largest cy gap).
    Falls back to the median rect width (sx) and to sx (sy) when a row/column cannot be formed. x / sx and y / sy give a layout whose keys are
    one unit apart in both directions, so every parameter of the decoder (tuned for row pitch 1.0) transfers."""
    items = sorted(centers_px.items(), key=lambda kv: kv[1][1])
    # group rows by clustering on cy: keys within half the largest cy gap of the row's first key belong to it
    ys = sorted(set(round(v[1], 3) for v in centers_px.values()))
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    thr = (max(gaps) / 2.0) if gaps else 1.0
    rows = []
    for k, (x, y) in items:
        if rows and abs(y - rows[-1][-1][1][1]) <= thr and abs(y - rows[-1][0][1][1]) <= thr:
            rows[-1].append((k, (x, y)))
        else:
            rows.append([(k, (x, y))])
    steps = []
    for row in rows:
        xs = sorted(x for k, (x, y) in row)
        steps += [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    sx = _median(steps) if steps else (rect_widths or 1.0)
    rys = [sum(y for k, (x, y) in row) / len(row) for row in rows]
    dys = [rys[i + 1] - rys[i] for i in range(len(rys) - 1)]
    sy = _median(dys) if dys else sx
    return sx, sy


def layout_from_centers_xy(centers_px):
    """Pixel key centres -> (Layout in normalised units, sx, sy); see axis_scales."""
    sx, sy = axis_scales(centers_px)
    return Layout({k: (x / sx, y / sy) for k, (x, y) in centers_px.items()}), sx, sy


def layout_from_rects_xy(rects):
    """rects = {key: (left, top, right, bottom)} pixels -> (Layout, sx, sy) with the per-axis rule of axis_scales."""
    return layout_from_centers_xy({k: ((r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0) for k, r in rects.items()})


def to_key_units_xy(points, sx, sy, origin=(0.0, 0.0)):
    """Pixel samples (x, y, t_ms) -> normalised units: x / sx, y / sy (use the SAME origin as the centres)."""
    ox, oy = origin
    return [((x - ox) / sx, (y - oy) / sy, t) for (x, y, t) in points]


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
