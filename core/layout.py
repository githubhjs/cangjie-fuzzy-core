"""Keyboard geometry: which keys count as 'one key off', decided dynamically from key positions.

A Layout is a set of key centres in units of one key width. Two keys are neighbours when the distance between their centres is at most
`theta` (the global error value). Nothing is precomputed per dictionary and no neighbour table is stored: change the layout or theta and
the answer changes.

  PC          qwerty_pc()                the physical ANSI QWERTY keyboard (staggered rows, 19.05 mm pitch)
  Android     from_rects({...})          the key rectangles the on-screen keyboard actually draws, read at runtime
              phone_qwerty(...)          a stand-in for tests when no rectangles are available (assumption, not a measurement)
"""
import math
from dataclasses import dataclass

ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")


@dataclass(frozen=True)
class Layout:
    centers: dict  # key -> (x, y) in key widths

    def distance(self, a, b):
        (xa, ya), (xb, yb) = self.centers[a], self.centers[b]
        return math.hypot(xa - xb, ya - yb)

    def neighbours(self, key, theta):
        """Keys other than `key` whose centre is within `theta` key widths, nearest first."""
        if key not in self.centers:
            return []
        out = [(self.distance(key, k), k) for k in self.centers if k != key]
        return [k for d, k in sorted(out) if d <= theta + 1e-9]

    def is_neighbour(self, a, b, theta):
        return a != b and a in self.centers and b in self.centers and self.distance(a, b) <= theta + 1e-9

    def table(self, theta):
        return {k: self.neighbours(k, theta) for k in sorted(self.centers)}


def qwerty_pc():
    """ANSI QWERTY: key centres from the standard keycap layout (Tab 1.5u, Caps 1.75u, left Shift 2.25u; rows 1 key apart)."""
    first_centre_x = (2.0, 2.25, 2.75)  # Q after Tab(1.5u)+0.5, A after Caps(1.75u)+0.5, Z after Shift(2.25u)+0.5
    centers = {}
    for r, row in enumerate(ROWS):
        for c, ch in enumerate(row):
            centers[ch] = (first_centre_x[r] + c, float(r))
    return Layout(centers)


def phone_qwerty(row_pitch=1.3, offsets=(0.0, 0.5, 1.5)):
    """Typical phone QWERTY: row 2 shifted half a key, row 3 one and a half keys; keys taller than wide (row_pitch in key widths).
    A stand-in for tests only: real behaviour must come from `from_rects`."""
    centers = {}
    for r, row in enumerate(ROWS):
        for c, ch in enumerate(row):
            centers[ch] = (offsets[r] + c, r * row_pitch)
    return Layout(centers)


def from_rects(rects):
    """On-screen keyboard: rects = {key: (left, top, right, bottom)} in any unit (pixels). Distances are measured in key widths,
    where one key width is the median rectangle width, so the same theta means the same thing on every screen size."""
    widths = sorted(r[2] - r[0] for r in rects.values())
    if not widths:
        raise ValueError("no key rectangles")
    w = widths[len(widths) // 2]
    if w <= 0:
        raise ValueError("key rectangles must have a positive width")
    return Layout({k: (((r[0] + r[2]) / 2) / w, ((r[1] + r[3]) / 2) / w) for k, r in rects.items()})
