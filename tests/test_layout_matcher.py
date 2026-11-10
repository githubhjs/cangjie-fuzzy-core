"""Tests of the JUDGMENT (geometry + matcher), not of the dictionary: no whole-dictionary sweep is needed or done.

  python3 tests/test_layout_matcher.py -v
Real-table tests run when a generated cangjie3.base.dict.yaml is found (env CJF_TABLE or ~/.config/ibus/rime/), else they are skipped.
"""
import json, os, random, sys, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from core import Matcher, qwerty_pc, phone_qwerty, from_rects, load_rime_dict
from core.layout import ROWS

ALPHA = "abcdefghijklmnopqrstuvwxyz"
THETA = 1.3
TABLE = os.environ.get("CJF_TABLE", os.path.expanduser("~/.config/ibus/rime/cangjie3.base.dict.yaml"))


def oracle(entries, typed, layout, theta, budget=1, min_len=2):
    """Brute force straight from the definition: same length, at most `budget` differing positions, each a neighbour within theta."""
    out = set()
    if budget > 0 and len(typed) < min_len:
        budget = 0
    for text, code, _ in entries:
        if len(code) != len(typed):
            continue
        diff = [(a, b) for a, b in zip(typed, code) if a != b]
        if len(diff) <= budget and all(layout.is_neighbour(a, b, theta) for a, b in diff):
            out.add(text)
    return out


class Geometry(unittest.TestCase):
    def test_pc_neighbours_are_the_physical_ones(self):
        L = qwerty_pc()
        self.assertEqual(set(L.neighbours("s", THETA)), set("adwezx"))      # left/right + the two above + the two below
        self.assertEqual(set(L.neighbours("c", THETA)), set("xvdf"))        # c and v are neighbours (the owner's example)
        self.assertEqual(set(L.neighbours("q", THETA)), set("wa"))
        self.assertNotIn("p", L.neighbours("c", THETA))

    def test_matches_the_static_spike_map(self):
        spike = json.load(open(os.path.join(HERE, "..", "generator", "neighbors_pc.json")))
        L = qwerty_pc()
        for k, v in spike.items():
            self.assertEqual(set(L.neighbours(k, THETA)), set(v), k)

    def test_key_pair_table(self):  # every one of the 26x26 pairs, not a dictionary
        L = qwerty_pc()
        for a in ALPHA:
            self.assertEqual(L.neighbours(a, 0.5), [])
            self.assertEqual(set(L.neighbours(a, 100)), set(ALPHA) - {a})
            for b in ALPHA:
                self.assertEqual(L.is_neighbour(a, b, THETA), L.is_neighbour(b, a, THETA))
                self.assertFalse(L.is_neighbour(a, a, THETA))
                for t1, t2 in ((1.0, 1.3), (1.3, 1.8)):
                    if L.is_neighbour(a, b, t1):
                        self.assertTrue(L.is_neighbour(a, b, t2))

    def test_screen_keyboard_rectangles_scale_free(self):
        base = phone_qwerty()
        for scale, ox, oy in ((1, 0, 0), (36.0, 12.0, 900.0), (2.7, 5.0, 40.0)):
            rects = {k: ((x - 0.5) * scale + ox, (y - 0.5 * 1.0) * scale + oy, (x + 0.5) * scale + ox, (y + 0.5) * scale + oy)
                     for k, (x, y) in base.centers.items()}
            L = from_rects(rects)
            self.assertEqual({k: set(v) for k, v in L.table(THETA).items()}, {k: set(v) for k, v in base.table(THETA).items()}, scale)

    def test_phone_is_not_pc(self):
        self.assertNotEqual(qwerty_pc().table(THETA), phone_qwerty().table(THETA))


class MatcherAgainstOracle(unittest.TestCase):
    def test_random_dictionaries(self):
        rnd = random.Random(7)
        for layout in (qwerty_pc(), phone_qwerty()):
            for trial in range(120):
                entries = []
                for i in range(rnd.randint(5, 400)):
                    code = "".join(rnd.choice(ALPHA) for _ in range(rnd.randint(1, 5)))
                    entries.append((f"w{i}", code, rnd.randint(1, 1000)))
                m = Matcher(entries, layout, THETA)
                for _ in range(40):
                    base = rnd.choice(entries)[1]
                    typed = list(base)
                    for _ in range(rnd.choice((0, 1, 1, 2))):
                        j = rnd.randrange(len(typed))
                        nb = layout.neighbours(typed[j], rnd.choice((0.9, 1.3, 1.8)))
                        typed[j] = rnd.choice(nb) if nb and rnd.random() < 0.8 else rnd.choice(ALPHA)
                    typed = "".join(typed)
                    for theta in (1.0, 1.3, 1.8):
                        got = {c.text for c in m.lookup(typed, theta=theta)}
                        self.assertEqual(got, oracle(entries, typed, layout, theta), (typed, theta))
                        m.theta, m._nb = THETA, {}

    def test_budget_zero_is_exact(self):
        m = Matcher([("a1", "ab", 1), ("a2", "ac", 1)], qwerty_pc())
        self.assertEqual([c.text for c in m.lookup("ab", budget=0)], ["a1"])

    def test_order_exact_first_then_distance_then_weight(self):
        L = qwerty_pc()
        m = Matcher([("exact", "cv", 1), ("near", "xv", 5), ("far", "cb", 9)], L)  # typed "cv": x is next to c, b is next to v
        out = m.lookup("cv")
        self.assertEqual(out[0].text, "exact")
        self.assertEqual({c.text for c in out[1:]}, {"near", "far"})
        self.assertTrue(all(c.subs == 1 for c in out[1:]))

    def test_theta_monotonic_and_single_letters_stay_exact(self):
        L = qwerty_pc()
        entries = [("m", "m", 1), ("n", "n", 1)]
        self.assertEqual([c.text for c in Matcher(entries, L).lookup("m")], ["m"])
        e2 = [("a", "ab", 1), ("b", "sb", 1), ("c", "qb", 1)]
        small = {c.text for c in Matcher(e2, L).lookup("ab", theta=1.0)}
        large = {c.text for c in Matcher(e2, L).lookup("ab", theta=1.8)}
        self.assertTrue(small <= large)


@unittest.skipUnless(os.path.exists(TABLE), "no generated cangjie3.base.dict.yaml (set CJF_TABLE)")
class RealTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = list(load_rime_dict(TABLE))
        cls.m = Matcher(cls.entries, qwerty_pc(), THETA)

    def texts(self, typed, **kw):
        return [c.text for c in self.m.lookup(typed, **kw)]

    def test_owner_example(self):
        self.assertIn("顏", self.texts("yhmbc"))      # exact
        self.assertIn("顏", self.texts("yhmbv"))      # c -> v: adjacent
        self.assertIn("顏", self.texts("yhnbc"))      # m -> n: adjacent
        self.assertNotIn("顏", self.texts("yhnbv"))   # two positions differ
        self.assertNotIn("顏", self.texts("yhmbp"))   # p is not a neighbour of c
        self.assertEqual(self.m.lookup("yhmbc")[0].subs, 0)
        self.assertNotIn("顏", self.texts("yhmbv", budget=0))

    def test_random_typos_recover_the_intended_word(self):
        rnd = random.Random(11)
        L = qwerty_pc()
        n = 0
        for text, code, _ in rnd.sample(self.entries, 1500):
            if len(code) < 2:
                continue
            j = rnd.randrange(len(code))
            nb = L.neighbours(code[j], THETA)
            if not nb:
                continue
            typed = code[:j] + rnd.choice(nb) + code[j + 1:]
            self.assertIn(text, self.texts(typed), (text, code, typed))
            n += 1
        self.assertGreater(n, 1000)

    def test_speed(self):
        rnd = random.Random(3)
        codes = [c for _, c, _ in rnd.sample(self.entries, 3000)]
        t = time.perf_counter()
        for c in codes:
            self.m.lookup(c)
        us = (time.perf_counter() - t) / len(codes) * 1e6
        print(f"\n  lookup: {us:.0f} microseconds each (python, {len(self.entries)} entries, tolerance 1)")
        self.assertLess(us, 5000)


if __name__ == "__main__":
    unittest.main()
