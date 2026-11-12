"""Tests of the product-level policy decode_auto (sweep/auto.py).   python3 sweep/tests/test_auto.py -v"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from sweep.auto import AutoDecoder, char_config  # noqa: E402
from sweep.decoder import Lexicon, SweepConfig, SweepDecoder  # noqa: E402
from sweep.keyboard import default_layout, layout_from_centers_xy, to_key_units_xy  # noqa: E402
from sweep.words import WordConfig, WordDecoder, WordLexicon  # noqa: E402

PTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 10.0), (2.0, 0.0, 20.0)]


class Stub:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def decode(self, points, *a, **kw):
        self.calls.append((a, kw))
        return list(self.rows)


class PolicyRules(unittest.TestCase):
    chars = [("頻", "yhmbc", -5.0), ("顏", "yhmbc", -5.5), ("顱", "ytmbc", -6.0)]

    def test_word_first_returns_one_list_unchanged(self):
        words = [("顏值", "word", 1.0), ("頻", "char", 0.5), ("市值", "word", 0.0)]
        r = AutoDecoder(Stub(self.chars), Stub(words)).decode(PTS, top_k=5)
        self.assertEqual([x[0] for x in r], ["顏值", "頻", "市值"])
        self.assertEqual([x[1] for x in r], ["word", "char", "word"])

    def test_char_first_returns_chars_then_new_words(self):
        words = [("顱", "char", -7.0), ("主頻", "word", -8.0), ("頻", "char", -9.0), ("頻率", "word", -9.5)]
        r = AutoDecoder(Stub(self.chars), Stub(words)).decode(PTS, top_k=10)
        self.assertEqual([x[0] for x in r], ["頻", "顏", "顱", "主頻", "頻率"])
        self.assertEqual([x[3] for x in r][:3], ["yhmbc", "yhmbc", "ytmbc"])  # codes come from the character decoder
        self.assertEqual(r[3][1], "word")

    def test_cut_to_top_k_and_word_already_listed_is_not_duplicated(self):
        words = [("頻", "char", 0.0), ("頻", "word", -1.0), ("主頻", "word", -2.0)]
        r = AutoDecoder(Stub(self.chars), Stub(words)).decode(PTS, top_k=3)
        self.assertEqual([x[0] for x in r], ["頻", "顏", "顱"])
        r = AutoDecoder(Stub(self.chars), Stub(words)).decode(PTS, top_k=4)
        self.assertEqual([x[0] for x in r], ["頻", "顏", "顱", "主頻"])

    def test_no_word_decoder_and_short_input(self):
        self.assertEqual([x[0] for x in AutoDecoder(Stub(self.chars), None).decode(PTS, top_k=2)], ["頻", "顏", "顱"])  # chars as given
        self.assertEqual(AutoDecoder(Stub(self.chars), Stub([])).decode(PTS[:1]), [])
        r = AutoDecoder(Stub(self.chars), Stub([])).decode(PTS, top_k=5)  # empty word list: characters
        self.assertEqual(len(r), 3)

    def test_lifts_go_to_the_word_decoder_only(self):
        w = Stub([])
        AutoDecoder(Stub(self.chars), w).decode(PTS, [1], top_k=4)
        self.assertEqual(w.calls[0][0][0], [1])

    def test_char_config_files(self):
        self.assertEqual(char_config("mouse").to_dict(), SweepConfig().to_dict())
        self.assertEqual(char_config("finger").dwell_ms, 250.0)
        self.assertNotEqual(char_config("finger").loc_weight, SweepConfig().loc_weight)


class AutoVectors(unittest.TestCase):
    def test_vectors(self):
        path = os.path.join(ROOT, "sweep", "vectors", "auto_vectors.json")
        if not os.path.exists(path):
            self.skipTest("auto vectors not generated yet")
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        ccfg, wcfg = SweepConfig(**v["config"]), WordConfig(**v["word_config"])
        ansi = default_layout()
        phone = layout_from_centers_xy({k: tuple(c) for k, c in v["centers_px"].items()})[0]
        decs = {}
        for g, lay in (("ansi", ansi), ("phone", phone)):
            decs[g] = AutoDecoder(SweepDecoder(Lexicon([tuple(e) for e in v["chars"]], lay, ccfg.n), ccfg),
                                  WordDecoder(WordLexicon([tuple(e) for e in v["word_chars"]], [tuple(w) for w in v["words"]], lay, wcfg), wcfg))
        for c in v["cases"]:
            pts = [tuple(p) for p in c["points"]]
            if c["geometry"] == "phone":
                pts = to_key_units_xy(pts, v["sx"], v["sy"])
            r = decs[c["geometry"]].decode(pts, c["lifts"], top_k=len(c["expected"]))
            self.assertEqual([x[0] for x in r], c["expected"], c["id"])
            self.assertEqual([x[1] for x in r], c["expected_kinds"], c["id"])
            self.assertEqual([x[3] for x in r], c["expected_codes"], c["id"])
            if "slip" in c["id"] or "mild" in c["id"] or "clean-yhmbc" in c["id"]:
                self.assertEqual((r[0][1], r[0][3]), ("char", "yhmbc"), c["id"])  # the owner's single-character paths: right code FIRST
            if "word-顏值" in c["id"]:
                self.assertEqual(r[0][0], "顏值", c["id"])
            if "word-頻率" in c["id"]:
                self.assertEqual(r[0][0], "頻率", c["id"])


if __name__ == "__main__":
    unittest.main()
