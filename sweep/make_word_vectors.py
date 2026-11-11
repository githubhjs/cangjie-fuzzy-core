"""Generate sweep/vectors/word_vectors.json: reference vectors for the word-level decoder (ports in Kotlin / JS).
Cases: the two owner paths (continuous, lift, dwell) + simulated word sweeps. Embedded mini lexicon (chars + words) gives `expected`;
`expected_full` is against table + essay.txt (freq >= 100) whose sha256 / line count are recorded.
  python3 -m sweep.make_word_vectors"""
import json
import os
import random
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.evaluate import DEFAULT_TABLE, entry_seed, load_entries, table_sha  # noqa: E402
from sweep.evaluate_words import DEFAULT_ESSAY, load_words, stratified  # noqa: E402
from sweep.keyboard import default_layout  # noqa: E402
from sweep.report_words import OWNER, literal  # noqa: E402
from sweep.simulate import PROFILES, generate_word  # noqa: E402
from sweep.words import WordConfig, WordDecoder, WordLexicon, main_codes  # noqa: E402

TOPK = 5


def rounded(pts):
    return [[round(x, 4), round(y, 4), round(t, 1)] for (x, y, t) in pts]


def main():
    L = default_layout()
    cfg_path = os.path.join(_ROOT, "sweep", "results", "defaults_words.json")
    with open(cfg_path) as f:
        cfg = WordConfig(**json.load(f))
    chars = load_entries(DEFAULT_TABLE, min_len=1)
    mc = main_codes(chars)
    words = load_words(DEFAULT_ESSAY, 100)
    full_lex = WordLexicon(chars, words, L, cfg)
    full = WordDecoder(full_lex, cfg)
    cases = []
    for target, s in OWNER:
        for mode in ("continuous", "lift", "dwell"):
            pts, lifts = literal(s, mode)
            cases.append({"id": "owner-%s-%s" % (target, mode), "target": target, "how": "literal path '%s', boundary %s" % (s, mode),
                          "points": rounded(pts), "lifts": lifts})
    items = stratified(words, mc, "test", 2, 7)
    rng = random.Random(3)
    rng.shuffle(items)
    for i, (text, f) in enumerate(items[:12]):
        prof, lv = [("mouse", 1.0), ("finger", 0.5), ("mouse", 1.6)][i % 3]
        mode = ["continuous", "lift", "dwell"][i % 3]
        pts, lifts = generate_word([mc[c] for c in text], L, PROFILES[prof], lv, random.Random(entry_seed(9, text, "v")), mode)
        cases.append({"id": "sim-%d-%s" % (i, text), "target": text, "how": "simulated %s level %.1f boundary %s" % (prof, lv, mode),
                      "points": rounded(pts), "lifts": lifts})
    # mini lexicon. REAL rows (functionally required): the target words and every word the full decoder ranks in its top 12 for a case,
    # with all codes of their characters. FILLER is SYNTHETIC (random codes, private-use characters, random frequencies): the repository
    # contains no copy of the table or of essay.txt.
    mw, mchars = {}, set()
    wd = dict(words)
    for c in cases:
        pts = [tuple(p) for p in c["points"]]
        for text, kind, sc in full.decode(pts, c["lifts"], top_k=12):
            if kind == "word":
                mw[text] = wd[text]
            else:
                mchars.add(text)
        mw[c["target"]] = wd[c["target"]]
    for w in mw:
        mchars.update(w)
    mini_chars = [e for e in chars if e[1] in mchars]
    fr = random.Random(78)
    alpha = "abcdefghijklmnopqrstuvwxy"
    synth = []
    for i in range(600):
        synth.append(("".join(fr.choice(alpha) for _ in range(fr.randint(2, 5))), chr(0xE800 + i), float(fr.randint(1, 5000))))
    mini_chars += synth
    mini_chars.sort()
    for i in range(800):
        w = "".join(chr(0xE800 + fr.randrange(600)) for _ in range(fr.randint(2, 4)))
        mw.setdefault(w, fr.randint(1, 20000))
    mini = WordDecoder(WordLexicon(mini_chars, sorted(mw.items()), L, cfg), cfg)
    kept = []
    for c in cases:
        pts = [tuple(p) for p in c["points"]]
        res = mini.decode(pts, c["lifts"], top_k=TOPK + 1)
        sc = [r[2] for r in res]
        if len(sc) > 1 and min(sc[i] - sc[i + 1] for i in range(min(TOPK, len(sc) - 1))) < 1e-6:
            print("drop (tie)", c["id"])
            continue
        c["expected"] = [r[0] for r in res[:TOPK]]
        c["expected_scores"] = [round(r[2], 6) for r in res[:TOPK]]
        c["expected_full"] = [r[0] for r in full.decode(pts, c["lifts"], top_k=TOPK)]
        kept.append(c)
    out = {"format": "cangjie-sweep-word-vectors-1",
           "note": "points (x, y, t_ms) in key widths of `centers`; `lifts` = indices i with a finger lift between points[i] and points[i+1]; "
                   "decode with `config`; `chars` = [code, char, weight] (all codes), `words` = [word, freq]; main code of a char = shortest code, "
                   "ties by higher weight then code. Compare ranked texts exactly and scores to 1e-6. The mini lexicon holds a few hundred REAL rows from the "
                   "Cangjie 3 table / essay.txt (the targets and their top-ranked competitors) plus SYNTHETIC filler (random codes, private-use characters U+E800.., "
                   "random frequencies); the repository does not contain the table or the word list.",
           "table_sha256": table_sha(DEFAULT_TABLE), "essay_min_freq": 100, "essay_words_in_full_lexicon": full_lex.n_words,
           "centers": {k: list(v) for k, v in L.centers.items()}, "config": cfg.to_dict(),
           "chars": [[c, ch, w] for c, ch, w in mini_chars], "words": [[w, f] for w, f in sorted(mw.items())], "cases": kept}
    path = os.path.join(_ROOT, "sweep", "vectors", "word_vectors.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote", path, len(kept), "cases", len(mw), "words", len(mini_chars), "char entries", os.path.getsize(path), "bytes")
    for c in kept:
        if c["id"].startswith("owner"):
            print(c["id"], c["expected"][:3], c["expected_full"][:3])


if __name__ == "__main__":
    main()
