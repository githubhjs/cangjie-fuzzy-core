"""Tests of the word-level sweep decoder.   python3 sweep/tests/test_words.py -v
Real-data tests (the two owner cases) run when the Cangjie 3 table and essay.txt are found, else skipped."""
import json
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from sweep.decoder import concat_template  # noqa: E402
from sweep.keyboard import default_layout  # noqa: E402
from sweep.make_vectors import polyline_path  # noqa: E402
from sweep.simulate import PROFILES, generate_word  # noqa: E402
from sweep.words import CharSegmenter, WordConfig, WordDecoder, WordLexicon, main_codes, split_strokes  # noqa: E402

TABLE = os.environ.get("CJF_TABLE_TSV", "/tmp/fw/f5a/app/src/main/assets/fuzzy/cangjie3.tsv")
ESSAY = os.environ.get("CJF_ESSAY", os.path.expanduser("~/projects/cangjie-fluency/data/essay.txt"))
L = default_layout()

CHARS = [("yhmbc", "顏", 1586), ("yhmbc", "頻", 1587), ("ojbm", "值", 10062), ("yioj", "率", 7531), ("a", "日", 71052),
         ("ab", "明", 100), ("ak", "冐", 50), ("bk", "甲", 80), ("kb", "乙", 70)]
WORDS = [("顏值", 11796), ("頻率", 12176), ("明甲", 500), ("冐乙", 400)]


class Template(unittest.TestCase):
    def test_concat_boundaries(self):
        self.assertEqual(concat_template(["yhmbc", "ojbm"]), ("yhmbcojbm", [(4, 5)], frozenset()))
        keys, bounds, reps = concat_template(["abb", "bcc", "c"])
        self.assertEqual(keys, "abc")
        self.assertEqual(bounds, [(1, 1), (2, 2)])
        self.assertEqual(reps, frozenset([1, 2]))

    def test_main_code_is_shortest_then_heaviest(self):
        mc = main_codes([("abc", "X", 5), ("ab", "X", 1), ("ab", "Y", 3), ("ac", "Y", 9)])
        self.assertEqual(mc["X"], "ab")
        self.assertEqual(mc["Y"], "ac")  # same length: heavier wins
        self.assertEqual(main_codes([("ab", "Y", 3), ("ac", "Y", 9)])["Y"], "ac")

    def test_split_strokes(self):
        pts = [(i, 0, i) for i in range(6)]
        self.assertEqual([len(s) for s in split_strokes(pts, [1, 3])], [2, 2, 2])
        self.assertEqual(len(split_strokes(pts, [])), 1)


class MiniWordDecoder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = WordConfig()
        cls.lex = WordLexicon(CHARS, WORDS, L, cls.cfg)
        cls.dec = WordDecoder(cls.lex, cls.cfg)

    def test_word_continuous(self):
        pts = polyline_path("yhmbcojbm", L)
        r = self.dec.decode(pts)
        self.assertEqual(r[0][1], "word")
        self.assertIn(r[0][0], ("顏值",))

    def test_second_character_decides_between_same_code_chars(self):
        pts = polyline_path("yhmbcyioj", L)
        self.assertEqual(self.dec.decode(pts)[0][0], "頻率")

    def test_lift_hint_and_candidate_boundary(self):
        a = polyline_path("yhmbc", L)
        b = polyline_path("ojbm", L)
        pts = a + [(x, y, t + a[-1][2] + 250.0) for (x, y, t) in b]
        r = self.dec.decode(pts, [len(a) - 1])
        self.assertEqual(r[0][0], "顏值")

    def test_single_character_still_decodes(self):
        pts = polyline_path("bk", L)
        r = self.dec.decode(pts)
        self.assertIn("甲", [x[0] for x in r[:3]])

    def test_empty(self):
        self.assertEqual(self.dec.decode([]), [])

    def test_deterministic_and_seeded_noise(self):
        rng = random.Random(4)
        pts, lifts = generate_word(["yhmbc", "ojbm"], L, PROFILES["mouse"], 1.0, rng, "continuous")
        self.assertEqual(self.dec.decode(pts, lifts), self.dec.decode(pts, lifts))

    def test_segmenter_returns_parts(self):
        from sweep.decoder import Lexicon, SweepDecoder
        chars2 = [c for c in CHARS if len(c[0]) >= 2]
        seg = CharSegmenter(SweepDecoder(Lexicon(chars2, L, 24)), grid=10)
        a = polyline_path("ab", L)
        b = polyline_path("bk", L)
        pts = a + [(x, y, t + a[-1][2] + 250.0) for (x, y, t) in b]
        r = seg.segment(pts, [len(a) - 1])
        self.assertIsNotNone(r)
        self.assertEqual(r[0], "明甲")


class WordVectors(unittest.TestCase):
    def test_vectors(self):
        path = os.path.join(ROOT, "sweep", "vectors", "word_vectors.json")
        if not os.path.exists(path):
            self.skipTest("word vectors not generated yet")
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        cfg = WordConfig(**v["config"])
        lex = WordLexicon([tuple(e) for e in v["chars"]], [tuple(w) for w in v["words"]], L, cfg)
        dec = WordDecoder(lex, cfg)
        self.assertTrue(v["cases"])
        for c in v["cases"]:
            got = [r[0] for r in dec.decode([tuple(p) for p in c["points"]], c["lifts"], top_k=len(c["expected"]))]
            self.assertEqual(got, c["expected"], c["id"])


@unittest.skipUnless(os.path.exists(TABLE) and os.path.exists(ESSAY), "table or essay.txt not found")
class OwnerCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sweep.evaluate import load_entries
        from sweep.evaluate_words import load_words
        cls.cfg = WordConfig()
        p = os.path.join(ROOT, "sweep", "results", "defaults_words.json")
        if os.path.exists(p):
            with open(p) as f:
                cls.cfg = WordConfig(**json.load(f))
        chars = load_entries(TABLE, min_len=1)
        cls.lex = WordLexicon(chars, load_words(ESSAY, 1000), L, cls.cfg)
        cls.dec = WordDecoder(cls.lex, cls.cfg)

    def run_case(self, s, mode):
        from sweep.report_words import literal
        pts, lifts = literal(s, mode)
        return [x[0] for x in self.dec.decode(pts, lifts, top_k=5)]

    def test_yan_zhi_all_boundaries(self):
        for mode in ("continuous", "lift", "dwell"):
            self.assertEqual(self.run_case("yhmnbvc ojhbnm", mode)[0], "顏值", mode)

    def test_pin_lv_in_top5(self):
        for mode in ("continuous", "lift", "dwell"):
            self.assertIn("頻率", self.run_case("yhjmnbvc yuiokjhj", mode), mode)


if __name__ == "__main__":
    unittest.main()
