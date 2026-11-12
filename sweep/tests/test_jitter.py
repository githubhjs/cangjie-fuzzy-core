"""Pointer preprocessing invariants and fixed noisy decode_auto port vectors.

Run: python3 sweep/tests/test_jitter.py
The embedded lexicon fixtures require neither the real table nor essay.txt.
"""
import json
import math
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from sweep.auto import AutoDecoder, decode_auto  # noqa: E402
from sweep.decoder import Lexicon, SweepConfig, SweepDecoder  # noqa: E402
from sweep.keyboard import default_layout  # noqa: E402
from sweep.make_vectors import polyline_path  # noqa: E402
from sweep.pointer import estimate_jitter, prepare_pointer  # noqa: E402
from sweep.simulate import add_sample_jitter  # noqa: E402
from sweep.words import WordConfig, WordDecoder, WordLexicon, path_length  # noqa: E402


def noisy_line(seed=17, sigma=0.2, count=160):
    rng = random.Random(seed)
    return [(i * 0.07 + rng.gauss(0, sigma), rng.gauss(0, sigma), i * 10.0)
            for i in range(count)]


class PointerFilter(unittest.TestCase):
    def test_simulator_jitter_is_seeded_and_preserves_input_and_time(self):
        points = [(0.0, 0.0, 0.0), (1.0, 1.0, 13.0)]
        snapshot = list(points)
        a = add_sample_jitter(points, 0.2, random.Random(6))
        b = add_sample_jitter(points, 0.2, random.Random(6))
        self.assertEqual(a, b)
        self.assertNotEqual(a, points)
        self.assertEqual(points, snapshot)
        self.assertEqual([p[2] for p in a], [p[2] for p in points])
        rng = random.Random(6)
        state = rng.getstate()
        clean = add_sample_jitter(points, 0, rng)
        self.assertEqual(clean, points)
        self.assertIsNot(clean, points)
        self.assertEqual(rng.getstate(), state)
        with self.assertRaises(ValueError):
            add_sample_jitter(points, -0.1, rng)

    def test_clean_linear_motion_with_irregular_timestamps_is_exact_bypass(self):
        times = [i * 9.0 + (i % 3) * 0.5 for i in range(50)]
        points = [(0.01 * t, -0.003 * t, t) for t in times]
        scoring, lengths, sigma = prepare_pointer(points, SweepConfig())
        self.assertIs(scoring, points)
        self.assertIs(lengths, points)
        self.assertLess(sigma, 1e-12)

    def test_owner_polylines_and_sparse_corners_are_exact_bypass(self):
        layout = default_layout()
        for keys in ("yhyjmnbvc", "yhjmnbvc", "yhmbc", "yhmnbvcojhbnm", "yhjmnbvcyuiokjhj"):
            for steps, step_ms in ((8, 10), (1, 50)):
                with self.subTest(keys=keys, steps=steps):
                    points = polyline_path(keys, layout, steps=steps, step_ms=step_ms)
                    scoring, lengths, _ = prepare_pointer(points, SweepConfig())
                    self.assertIs(scoring, points)
                    self.assertIs(lengths, points)

    def test_off_short_and_empty_paths_are_exact_bypass(self):
        for points in ([], [(1, 2, 3)], noisy_line(count=6)):
            scoring, lengths, _ = prepare_pointer(points, SweepConfig())
            self.assertIs(scoring, points)
            self.assertIs(lengths, points)
        points = noisy_line()
        scoring, lengths, sigma = prepare_pointer(points, SweepConfig(pointer_filter="off"))
        self.assertIs(scoring, points)
        self.assertIs(lengths, points)
        self.assertEqual(sigma, 0)

    def test_iid_estimate_and_smoothing_reduce_length_inflation(self):
        points = noisy_line()
        snapshot = list(points)
        scoring, lengths, sigma = prepare_pointer(points, SweepConfig())
        self.assertGreater(sigma, 0.15)
        self.assertLess(sigma, 0.25)
        self.assertLess(path_length(lengths), path_length(points) * 0.5)
        raw_error = sum(y * y for _, y, _ in points)
        filtered_error = sum(y * y for _, y, _ in scoring)
        self.assertLess(filtered_error, raw_error * 0.5)
        self.assertEqual(points, snapshot)  # callers retain the raw dwell evidence
        self.assertEqual(len(scoring), len(points))
        self.assertEqual([p[2] for p in scoring], [p[2] for p in points])
        self.assertTrue(all(math.isfinite(v) for p in scoring for v in p))

    def test_lifts_and_event_gaps_prevent_cross_stroke_blending(self):
        first = noisy_line(count=50)
        second = [(x, y, t + 500.0) for x, y, t in first]
        shifted = [(x + 100.0, y - 100.0, t) for x, y, t in second]
        for lifts, gap in (([49], 0.0), ([], 300.0)):
            with self.subTest(lifts=lifts):
                tail = [(x, y, t + gap) for x, y, t in second]
                far_tail = [(x, y, t + gap) for x, y, t in shifted]
                near = prepare_pointer(first + tail, SweepConfig(), lifts)[0]
                far = prepare_pointer(first + far_tail, SweepConfig(), lifts)[0]
                for a, b in zip(near[:50], far[:50]):
                    for x, y in zip(a, b):
                        self.assertAlmostEqual(x, y, places=12)
                # Translation of another stroke does not contribute an artificial jitter spike.
                self.assertAlmostEqual(estimate_jitter(first + tail, lifts),
                                       estimate_jitter(first + far_tail, lifts), places=12)

    def test_duplicate_timestamps_and_stationary_paths_remain_finite(self):
        points = [(1.0, 2.0, 0.0)] * 10
        scoring, lengths, _ = prepare_pointer(points, SweepConfig())
        self.assertEqual(scoring, points)
        self.assertEqual(lengths, points)
        points = [(x, y, float(i // 2) * 10) for i, (x, y, _) in enumerate(noisy_line())]
        scoring, _, _ = prepare_pointer(points, SweepConfig())
        self.assertTrue(all(math.isfinite(v) for p in scoring for v in p))

    def test_length_and_window_modes_keep_raw_scoring_samples(self):
        points = noisy_line()
        for mode in ("length", "window"):
            scoring, lengths, _ = prepare_pointer(points, SweepConfig(pointer_filter=mode))
            self.assertIs(scoring, points)
            self.assertLess(path_length(lengths), path_length(points))

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            prepare_pointer(noisy_line(), SweepConfig(pointer_filter="typo"))


class JitterVectors(unittest.TestCase):
    def test_fixed_noisy_auto_vectors(self):
        with open(os.path.join(ROOT, "sweep", "vectors", "jitter_vectors.json"), encoding="utf-8") as f:
            vectors = json.load(f)
        ccfg, wcfg = SweepConfig(**vectors["config"]), WordConfig(**vectors["word_config"])
        layout = default_layout()
        chars = Lexicon(vectors["chars"], layout, ccfg.n)
        words = WordLexicon(vectors["word_chars"], vectors["words"], layout, wcfg)
        filtered = AutoDecoder(SweepDecoder(chars, ccfg), WordDecoder(words, wcfg))
        raw = AutoDecoder(SweepDecoder(chars, ccfg.replace(pointer_filter="off")),
                          WordDecoder(words, wcfg.replace(pointer_filter="off")))
        improvements = 0
        for case in vectors["cases"]:
            with self.subTest(case=case["id"]):
                points = [tuple(p) for p in case["points"]]
                rows = filtered.decode(points, case["lifts"], top_k=5)
                self.assertEqual([r[0] for r in rows], case["expected"])
                self.assertEqual([r[1] for r in rows], case["expected_kinds"])
                self.assertEqual([r[3] for r in rows], case["expected_codes"])
                if case["target_kind"] == "char":
                    self.assertEqual((rows[0][1], rows[0][3]), ("char", case["target_code"]))
                else:
                    self.assertEqual((rows[0][1], rows[0][0]), ("word", case["target_text"]))
                for row, score in zip(rows, case["expected_scores"]):
                    self.assertAlmostEqual(row[2], score, delta=1e-6)
                off_rows = raw.decode(points, case["lifts"], top_k=5)
                self.assertEqual([r[0] for r in off_rows], case["expected_off"])
                self.assertEqual(decode_auto(filtered.chars, filtered.words, points, case["lifts"], 5), rows)
                if case["target_kind"] == "char":
                    raw_correct = (off_rows[0][1], off_rows[0][3]) == ("char", case["target_code"])
                else:
                    raw_correct = (off_rows[0][1], off_rows[0][0]) == ("word", case["target_text"])
                improvements += not raw_correct  # filtered top-1 was independently checked against the target above
        self.assertGreaterEqual(improvements, 3)


if __name__ == "__main__":
    unittest.main()
