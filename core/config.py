"""The three tolerance knobs, in one place. Defaults are justified by results/range_study.md (see README, section 'Defaults').

  theta                 range: two keys are neighbours when their centres are within `theta` key widths (1.0 = left/right only,
                        1.3 = also the diagonal neighbours, the default; 1.8 adds the next ring)
  per_code              typos tolerated inside ONE code (one character). 1 by default; 2 almost doubles the candidate noise
                        for under half a percentage point of extra recovery
  phrase_fraction/min   typos tolerated per PHRASE, as a share of the number of codes in the phrase (rounded up) with a floor.
                        Default 40 % and at least 2: that keeps >= 99 % of the recovery of an unlimited setting (study, table C)
  min_code_len          codes shorter than this are never fuzzy-matched (a single key code is ambiguous with every longer code)
"""
import json
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FuzzyConfig:
    theta: float = 1.3
    per_code: int = 1
    phrase_fraction: float = 0.4
    phrase_min: int = 2
    min_code_len: int = 2

    def phrase_cap(self, n_codes: int) -> int:
        """How many codes of a phrase of `n_codes` characters may be corrected."""
        if n_codes <= 0:
            return 0
        return min(n_codes, max(self.phrase_min, math.ceil(self.phrase_fraction * n_codes - 1e-9)))

    def validated(self) -> "FuzzyConfig":
        if not (0.0 <= self.theta <= 4.0):
            raise ValueError("theta must be between 0 and 4 key widths")
        if self.per_code < 0 or self.per_code > 3:
            raise ValueError("per_code must be 0..3")
        if not (0.0 <= self.phrase_fraction <= 1.0) or self.phrase_min < 0 or self.min_code_len < 1:
            raise ValueError("phrase_fraction must be 0..1, phrase_min >= 0, min_code_len >= 1")
        return self

    @classmethod
    def from_json(cls, text_or_path: str) -> "FuzzyConfig":
        """Accepts a JSON string or a path to a JSON file; unknown keys are rejected so a typo in a name is not silently ignored."""
        try:
            data = json.loads(text_or_path)
        except ValueError:
            with open(text_or_path, encoding="utf-8") as f:
                data = json.load(f)
        known = set(cls.__dataclass_fields__)
        bad = set(data) - known
        if bad:
            raise ValueError("unknown setting(s): " + ", ".join(sorted(bad)))
        return cls(**data).validated()

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


DEFAULT = FuzzyConfig()
