"""Dynamic one-key-off matcher over a dictionary of Cangjie codes.

For a typed string it returns every word whose code equals the typed string (cost 0) or differs from it in at most `budget` positions,
where each differing position must hold a key that is a neighbour of the typed key in the given Layout within `theta` (cost = the
distance between the two key centres). The dictionary is a trie; the search follows the typed key, and, while budget remains, the
neighbour keys of the typed key. Work per lookup is O(len(typed) x neighbours), independent of the dictionary size.

Contract (see SPEC): exact matches first (in dictionary weight order), then fuzzy matches by total distance, then weight;
no insertion, deletion, transposition; codes shorter than `min_len` are never fuzzy-matched (single letter codes stay exact).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    text: str
    code: str
    cost: float      # 0.0 for an exact match, else the sum of key distances
    subs: int        # number of substituted positions


class Trie:
    __slots__ = ("kids", "words")

    def __init__(self):
        self.kids = {}
        self.words = []  # (weight, text) at a node that ends a code

    @classmethod
    def build(cls, entries):
        """entries: iterable of (text, code, weight)."""
        root = cls()
        for text, code, weight in entries:
            node = root
            for ch in code:
                node = node.kids.setdefault(ch, cls())
            node.words.append((weight, text))
        return root


def load_rime_dict(path):
    """Read a Rime *.dict.yaml with columns text, code, weight (as written by tools/cin2rime.py)."""
    on = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip() == "...":
                on = True
                continue
            if on and line.strip() and not line.startswith("#"):
                p = line.rstrip("\n").split("\t")
                if len(p) >= 3:
                    yield p[0], p[1], int(p[2])


class Matcher:
    def __init__(self, entries, layout, theta=1.3, budget=1, min_len=2, config=None):
        if config is not None:  # a FuzzyConfig overrides the individual numbers
            theta, budget, min_len = config.theta, config.per_code, config.min_code_len
        self.root = Trie.build(entries)
        self.layout, self.theta, self.budget, self.min_len = layout, theta, budget, min_len
        self._nb = {}

    def _neighbours(self, key):
        if key not in self._nb:
            self._nb[key] = [(self.layout.distance(key, k), k) for k in self.layout.neighbours(key, self.theta)]
        return self._nb[key]

    def lookup(self, typed, theta=None, budget=None):
        """Return Candidates, best first. theta / budget override the instance values (the global error setting)."""
        if theta is not None and theta != self.theta:
            self.theta, self._nb = theta, {}
        budget = self.budget if budget is None else budget
        if budget > 0 and len(typed) < self.min_len:
            budget = 0
        found = []

        def walk(node, i, left, cost, subs, code):
            if i == len(typed):
                for weight, text in node.words:
                    found.append((subs, cost, -weight, Candidate(text, code, round(cost, 6), subs)))
                return
            ch = typed[i]
            nxt = node.kids.get(ch)
            if nxt is not None:
                walk(nxt, i + 1, left, cost, subs, code + ch)
            if left > 0:
                for dist, other in self._neighbours(ch):
                    nxt = node.kids.get(other)
                    if nxt is not None:
                        walk(nxt, i + 1, left - 1, cost + dist, subs + 1, code + other)

        walk(self.root, 0, budget, 0.0, 0, "")
        seen, out = set(), []
        for _, _, _, cand in sorted(found, key=lambda t: t[:3]):
            if cand.text not in seen:
                seen.add(cand.text)
                out.append(cand)
        return out
