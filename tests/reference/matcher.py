"""Original reference matcher; no dictionary or model data bundled.

Exact dictionary ordering wins. Fuzzy paths change exactly one neighboring key.
This is a behavioral reference, not an Android integration or sentence engine.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    text: str
    code: str
    exact: bool


class Matcher:
    def __init__(self, dictionary, neighbors):
        alphabet = set('abcdefghijklmnopqrstuvwxyz')
        if set(neighbors) != alphabet:
            raise ValueError('neighbors must define all 26 lowercase keys')
        self.neighbors = {}
        for key, adjacent in neighbors.items():
            values = tuple(sorted(set(adjacent)))
            if key in values or not set(values) <= alphabet:
                raise ValueError('invalid neighbor edge')
            if any(key not in neighbors[other] for other in values):
                raise ValueError('neighbor edges must be symmetric')
            self.neighbors[key] = values
        self.dictionary = {}
        for code, words in dictionary.items():
            if not 1 <= len(code) <= 5 or not set(code) <= alphabet:
                raise ValueError('dictionary codes must contain 1–5 lowercase keys')
            words = tuple(words)
            if any(not isinstance(word, str) or not word for word in words):
                raise ValueError('dictionary entries must be nonempty strings')
            self.dictionary[code] = words

    def lookup(self, typed, tolerance=0):
        if type(tolerance) is not int or tolerance not in (0, 1):
            raise ValueError('tolerance must be 0 or 1')
        if not 1 <= len(typed) <= 5 or not set(typed) <= set(self.neighbors):
            return []
        codes = [typed]
        # Keep the desktop prototype rule: single-letter codes stay exact.
        if tolerance and len(typed) >= 2:
            codes.extend(typed[:i] + other + typed[i + 1:]
                         for i, key in enumerate(typed)
                         for other in self.neighbors[key])
        seen = set()
        result = []
        for code in codes:
            for word in self.dictionary.get(code, ()):
                if word not in seen:
                    seen.add(word)
                    result.append(Candidate(word, code, code == typed))
        return result
