import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from core import FuzzyConfig, Matcher, qwerty_pc, DEFAULT


class Config(unittest.TestCase):
    def test_defaults_are_the_documented_ones(self):
        self.assertEqual((DEFAULT.theta, DEFAULT.per_code, DEFAULT.phrase_fraction, DEFAULT.phrase_min, DEFAULT.min_code_len),
                         (1.3, 1, 0.4, 2, 2))

    def test_phrase_cap(self):
        c = DEFAULT
        self.assertEqual([c.phrase_cap(n) for n in (0, 1, 2, 3, 4, 5, 8, 10, 20)], [0, 1, 2, 2, 2, 2, 4, 4, 8])
        self.assertEqual(FuzzyConfig(phrase_fraction=0.0, phrase_min=0).phrase_cap(5), 0)      # tolerance switched off per phrase
        self.assertEqual(FuzzyConfig(phrase_fraction=1.0, phrase_min=0).phrase_cap(5), 5)      # no limit
        self.assertEqual(FuzzyConfig(phrase_fraction=0.2, phrase_min=1).phrase_cap(10), 2)     # 20 %

    def test_json_roundtrip_and_validation(self):
        c = FuzzyConfig.from_json('{"theta": 1.8, "per_code": 1, "phrase_fraction": 0.5}')
        self.assertEqual((c.theta, c.phrase_fraction, c.phrase_min), (1.8, 0.5, 2))
        self.assertEqual(FuzzyConfig.from_json(c.to_json()), c)
        for bad in ('{"thetaa": 1}', '{"theta": 9}', '{"per_code": 7}', '{"phrase_fraction": 2}'):
            with self.assertRaises(ValueError):
                FuzzyConfig.from_json(bad)

    def test_matcher_follows_the_config(self):
        entries = [("a", "sd", 1), ("b", "ad", 1), ("c", "wd", 1)]   # typed sd: a exact; b (a is left of s) and c (w is diagonal)
        L = qwerty_pc()
        narrow = {x.text for x in Matcher(entries, L, config=FuzzyConfig(theta=1.0)).lookup("sd")}
        wide = {x.text for x in Matcher(entries, L, config=FuzzyConfig(theta=1.3)).lookup("sd")}
        off = {x.text for x in Matcher(entries, L, config=FuzzyConfig(per_code=0)).lookup("sd")}
        self.assertEqual(off, {"a"})
        self.assertEqual(narrow, {"a", "b"})      # a is beside s; w is a diagonal neighbour, 1.03 away
        self.assertEqual(wide, {"a", "b", "c"})


if __name__ == "__main__":
    unittest.main()
