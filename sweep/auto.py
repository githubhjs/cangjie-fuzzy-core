"""Product-level decode policy `decode_auto`: one gesture, characters and words, one ranked list. SPEC.md section 12.

Why a policy and not just the one-list word decoder: on a slide over ONE character the one-list decoder (characters + words) can be weaker
than the single-character decoder, especially for backtracking slips (it ranked ytmbc 顱 before yhmbc for y h y j m n b v c). The word
decoder is better when the slide really spans a word. So both run:

  1. chars = single-character decoder(points)                      (character config of the device profile)
  2. all   = one-list word decoder(points, lifts)                   (defaults_words.json; characters and words together)
  3. if all[0] is a WORD (kind "word": 2-4 characters): the slide spanned a word -> return `all` unchanged.
  4. otherwise (best guess is a single character, or nothing): return chars followed by the words of `all` that are not already in chars
     (each word keeps the relative order it has in `all`), cut to top_k.

No score threshold and no margin test decide between the two lists (their scores are on different scales and are never compared);
the only test is the kind of the one-list decoder's first candidate. Ties inside a list are the decoders' own (score, then code / text).
Android's SweepEngine.decode implements exactly steps 1-4 (it passes no lifts: a lift ends the sweep there).

Known limit (measured, SPEC section 12): with a large word list a backtracking slide over one character can itself match a word (for example
y h y h m b c matched the word with codes ygyhmbc, y h y j m n b v c on the phone geometry matched 主頻 when words >= 100 were loaded; with
words >= 1000 it does not). Thresholds on the scores or on key coverage that would catch these cost word-sweep accuracy (SPEC section 12).
"""
import json
import os

from sweep.decoder import SweepConfig

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def char_config(profile="mouse"):
    """Character-decoder config of a device profile: results/defaults_<profile>.json (mouse = SweepConfig())."""
    path = os.path.join(_ROOT, "sweep", "results", "defaults_%s.json" % profile)
    if profile != "mouse" and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return SweepConfig(**json.load(f))
    return SweepConfig()


class AutoDecoder:
    """decode(points, lifts=(), top_k=None) -> [(text, kind, score, code)]; kind is "char" or "word"; code is the decoded Cangjie code for
    characters coming from the single-character decoder and "" otherwise (words: join the main codes of the characters)."""

    def __init__(self, char_decoder, word_decoder, top_k=10):
        self.chars = char_decoder
        self.words = word_decoder
        self.top_k = top_k

    def decode(self, points, lifts=(), top_k=None):
        k = top_k or self.top_k
        if len(points) < 2:
            return []
        chars = [(ch, "char", sc, code) for ch, code, sc in self.chars.decode(points, top_k=k)]
        if self.words is None:
            return chars
        allr = [(text, kind, sc, "") for text, kind, sc in self.words.decode(points, lifts, top_k=k)]
        if allr and allr[0][1] == "word":
            return allr
        seen = set(c[0] for c in chars)
        return (chars + [r for r in allr if r[1] == "word" and r[0] not in seen])[:k]


def decode_auto(char_decoder, word_decoder, points, lifts=(), top_k=10):
    return AutoDecoder(char_decoder, word_decoder, top_k).decode(points, lifts, top_k)
