"""Tests of the sweep decoder, simulator and port vectors.   python3 sweep/tests/test_sweep.py -v
Real-table tests run when the Cangjie 3 table is found (env CJF_TABLE_TSV or the path used for the published results), else skipped."""
import json
import math
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from core.layout import qwerty_pc  # noqa: E402
from sweep.decoder import (Lexicon, SweepConfig, SweepDecoder, collapse, detect_dwells, end_alphas,  # noqa: E402
                           repeat_positions, resample)
from sweep.keyboard import default_layout, key_sequence, layout_from_rects, to_key_units  # noqa: E402
from sweep.simulate import LEVELS, PROFILES, generate  # noqa: E402

TABLE = os.environ.get("CJF_TABLE_TSV", "/tmp/fw/f5a/app/src/main/assets/fuzzy/cangjie3.tsv")
L = default_layout()


def straight(code, layout=L, ms=300):
    """Noiseless polyline through the key centres, constant speed, 10 ms sampling."""
    keys = collapse(code)
    pts = [layout.centers[k] for k in keys]
    out, t = [], 0.0
    for a, b in zip(pts, pts[1:]):
        steps = max(2, int(ms / 10))
        for i in range(steps):
            f = i / steps
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, t))
            t += 10
    out.append((pts[-1][0], pts[-1][1], t))
    return out


class Basics(unittest.TestCase):
    def test_collapse_and_repeats(self):
        self.assertEqual(collapse("aab"), "ab")
        self.assertEqual(collapse("hhh"), "h")
        self.assertEqual(collapse("yhmbc"), "yhmbc")
        self.assertEqual(repeat_positions("aab"), frozenset([0]))
        self.assertEqual(repeat_positions("abb"), frozenset([1]))
        self.assertEqual(repeat_positions("aabb"), frozenset([0, 1]))
        self.assertEqual(repeat_positions("abc"), frozenset())

    def test_geometry_is_core_layout(self):
        self.assertEqual(default_layout().centers, qwerty_pc().centers)

    def test_resample_equidistant(self):
        pts = [(0, 0), (4, 0), (4, 3)]
        r = resample(pts, 8)
        self.assertEqual(len(r), 8)
        self.assertEqual(r[0], (0, 0))
        self.assertAlmostEqual(r[-1][0], 4)
        self.assertAlmostEqual(r[-1][1], 3)
        steps = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(r, r[1:])]
        # equidistant along the path (the corner makes the chord of one step shorter than the arc step)
        self.assertAlmostEqual(sum(steps) > 0 and max(steps), 1.0, places=6)
        self.assertEqual(len(resample([(1, 1)], 5)), 5)
        self.assertEqual(resample([(1, 1), (1, 1)], 3), [(1, 1)] * 3)

    def test_alphas(self):
        a = end_alphas(9, 3.0)
        self.assertAlmostEqual(sum(a), 1.0)
        self.assertGreater(a[0], a[4])
        self.assertAlmostEqual(a[0], a[8])

    def test_dwell_detection(self):
        cfg = SweepConfig()
        moving = [(i * 0.5, 0.0, i * 10.0) for i in range(40)]
        self.assertEqual(detect_dwells(moving, cfg), [])
        still = [(1.0 + 0.01 * (i % 3), 1.0, i * 10.0) for i in range(40)]
        self.assertEqual(len(detect_dwells(still, cfg)), 1)
        gap = [(1.0, 1.0, 0.0), (1.0, 1.0, 10.0), (3.0, 1.0, 400.0), (3.5, 1.0, 410.0)]  # mouse: no events while still
        self.assertEqual(len(detect_dwells(gap, cfg)), 1)
        short = [(1.0, 1.0, i * 10.0) for i in range(10)]  # 90 ms < 200 ms
        self.assertEqual(detect_dwells(short, cfg), [])


class DecoderMini(unittest.TestCase):
    ents = [("ab", "A", 100), ("ab", "B", 10), ("aab", "C", 50), ("abb", "D", 50), ("ak", "E", 100), ("yhmbc", "顏", 1586),
            ("yhmbv", "X", 1000), ("a", "T", 99999)]

    def make(self, **kw):
        lex = Lexicon([e for e in self.ents if len(e[0]) >= 2], L, 32)
        return SweepDecoder(lex, SweepConfig(**kw))

    def test_exact_path(self):
        d = self.make()
        r = d.decode(straight("yhmbc"))
        self.assertEqual(r[0][0], "顏")

    def test_shared_code_ranks_by_weight(self):
        d = self.make()
        r = [x[0] for x in d.decode(straight("ab"))]
        self.assertLess(r.index("A"), r.index("B"))

    def test_prior_weight_zero_still_returns_both(self):
        d = self.make(prior_weight=0.0)
        r = [x[0] for x in d.decode(straight("ab"))]
        self.assertIn("A", r)
        self.assertIn("B", r)

    def test_dwell_selects_repeat_variant(self):
        d = self.make()
        base = straight("ab")
        # dwell 400 ms on the first key: code aab
        dw = [(base[0][0], base[0][1], i * 10.0) for i in range(40)]
        shift = 400.0
        pts = dw + [(x, y, t + shift) for (x, y, t) in base[1:]]
        self.assertEqual(d.decode(pts)[0][0], "C")
        # dwell on the last key: code abb
        last = base[-1]
        pts2 = base + [(last[0], last[1], last[2] + 10.0 * i) for i in range(1, 45)]
        self.assertEqual(d.decode(pts2)[0][0], "D")
        # no dwell: the plain ab entries
        self.assertEqual(d.decode(base)[0][0], "A")

    def test_ignore_repeat_mode_ranks_by_prior(self):
        d = self.make(repeat_mode="ignore")
        r = [x[0] for x in d.decode(straight("ab"))]
        self.assertEqual(r[0], "A")
        self.assertEqual(set(r[:4]), {"A", "B", "C", "D"})

    def test_index_matches_scan(self):
        rng = random.Random(3)
        d1 = self.make(use_index=True)
        d2 = self.make(use_index=False)
        for code in ("yhmbc", "ab", "ak", "yhmbv"):
            pts = generate(code, L, PROFILES["finger"], 1.0, rng)
            self.assertEqual(d1.decode(pts), d2.decode(pts))

    def test_pruning_fallback(self):
        d = self.make(prune_radius=0.2)
        pts = [(x + 0.8, y, t) for (x, y, t) in straight("yhmbc")]  # start far from any template start
        self.assertTrue(d.decode(pts))  # fallback widens, never returns nothing
        d2 = self.make(prune_radius=0.2, prune_fallback=False)
        self.assertEqual(d2.decode(pts), [])

    def test_empty_and_single_point(self):
        d = self.make()
        self.assertEqual(d.decode([]), [])
        self.assertTrue(d.decode([(L.centers["a"][0], L.centers["a"][1], 0.0)]) is not None)

    def test_pixel_input_equals_key_unit_input(self):
        rects = {k: (int(x * 40 - 20), int(y * 40 - 20), int(x * 40 + 20), int(y * 40 + 20)) for k, (x, y) in L.centers.items()}
        lay, scale = layout_from_rects(rects)
        self.assertAlmostEqual(scale, 40.0)
        px = [(x * 40, y * 40, t) for (x, y, t) in straight("yhmbc")]
        kw = to_key_units(px, scale)
        lex = Lexicon([e for e in self.ents if len(e[0]) >= 2], lay, 32)
        self.assertEqual(SweepDecoder(lex).decode(kw)[0][0], "顏")

    def test_deterministic(self):
        d = self.make()
        pts = generate("yhmbc", L, PROFILES["mouse"], 1.0, random.Random(9))
        self.assertEqual(d.decode(pts), d.decode(pts))


class Simulator(unittest.TestCase):
    def test_seeded_and_monotone_time(self):
        a = generate("yhmbc", L, PROFILES["finger"], 1.0, random.Random(5))
        b = generate("yhmbc", L, PROFILES["finger"], 1.0, random.Random(5))
        self.assertEqual(a, b)
        ts = [p[2] for p in a]
        self.assertEqual(ts, sorted(ts))

    def test_oracle_visits_every_key(self):
        pts = generate("yhmbc", L, PROFILES["mouse"], 0.0, random.Random(1))
        seq = "".join(key_sequence(L, pts, 0.3))
        for k in "yhmbc":
            self.assertIn(k, seq)
        self.assertEqual(seq[0], "y")
        self.assertEqual(seq[-1], "c")

    def test_oracle_dwell_for_repeats(self):
        pts = generate("hhx", L, PROFILES["mouse"], 0.0, random.Random(1))
        self.assertEqual(len(detect_dwells(pts, SweepConfig())), 1)
        pts = generate("hx", L, PROFILES["mouse"], 0.0, random.Random(1))
        self.assertEqual(len(detect_dwells(pts, SweepConfig())), 0)

    def test_event_driven_mouse_has_time_gap_in_dwell(self):
        pts = generate("hhx", L, PROFILES["mouse"], 0.0, random.Random(1), dwell=True)
        gaps = [b[2] - a[2] for a, b in zip(pts, pts[1:])]
        self.assertGreater(max(gaps), 250.0)
        fing = generate("hhx", L, PROFILES["finger"], 0.0, random.Random(1), dwell=True)
        self.assertLess(max(b[2] - a[2] for a, b in zip(fing, fing[1:])), 30.0)

    def test_noise_grows_with_level(self):
        def spread(level):
            tot = 0.0
            for s in range(40):
                p = generate("yhmbc", L, PROFILES["finger"], level, random.Random(s))
                tot += math.hypot(p[-1][0] - L.centers["c"][0], p[-1][1] - L.centers["c"][1])
            return tot / 40
        self.assertLess(spread(0.0), spread(1.0))
        self.assertLess(spread(1.0), spread(1.6))

    def test_profiles_present(self):
        for name in ("finger", "mouse", "touchpad", "touchscreen"):
            self.assertIn(name, PROFILES)
        self.assertIn("oracle", LEVELS)


class Vectors(unittest.TestCase):
    """The reference vectors must reproduce exactly (they are what the Kotlin / JS ports are checked against)."""

    def test_vectors(self):
        path = os.path.join(ROOT, "sweep", "vectors", "vectors.json")
        if not os.path.exists(path):
            self.skipTest("vectors not generated yet")
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        cfg = SweepConfig(**v["config"])
        lex = Lexicon([tuple(e) for e in v["lexicon"]], default_layout(), cfg.n)
        dec = SweepDecoder(lex, cfg)
        self.assertTrue(v["cases"])
        for c in v["cases"]:
            got = [r[0] for r in dec.decode([tuple(p) for p in c["points"]], top_k=len(c["expected"]))]
            self.assertEqual(got, c["expected"], c["id"])


@unittest.skipUnless(os.path.exists(TABLE), "Cangjie 3 table not found")
class RealTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = Lexicon.from_tsv(TABLE, L, 32)
        cls.dec = SweepDecoder(cls.lex)

    def test_yan_oracle_and_slip(self):
        r = [x[0] for x in self.dec.decode(straight("yhmbc"), top_k=5)]
        self.assertIn("顏", r)
        # the slip path of the brief: y h y j m n b v c
        slip = [L.centers[k] for k in "yhyjmnbvc"]
        pts, t = [], 0.0
        for a, b in zip(slip, slip[1:]):
            for i in range(8):
                pts.append((a[0] + (b[0] - a[0]) * i / 8, a[1] + (b[1] - a[1]) * i / 8, t))
                t += 10
        pts.append((slip[-1][0], slip[-1][1], t))
        r2 = [x[0] for x in self.dec.decode(pts, top_k=5)]
        self.assertIn("顏", r2)

    def test_latency_budget(self):
        import time
        pts = straight("yhmbc")
        t = time.perf_counter()
        for _ in range(20):
            self.dec.decode(pts)
        per = (time.perf_counter() - t) / 20 * 1000
        self.assertLess(per, 100.0)  # generous: pure Python, loaded CI machine


if __name__ == "__main__":
    unittest.main()
