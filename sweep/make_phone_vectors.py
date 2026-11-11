"""Generate sweep/vectors/phone_vectors.json: vectors on a real phone soft-keyboard geometry (Android emulator: key centres in PIXELS,
key pitch 32 px, row pitch 48 px = 1.5 key widths). Points are PIXELS; a port must apply the per-axis normalisation of SPEC.md section 2c
(x / sx, y / sy from the centres) before decoding.  Cases: the owner slip y h y j m n b v c and relatives (characters), 顏值 / 頻率 (words).
  python3 -m sweep.make_phone_vectors [--layout path/to/layout.txt]   (layout.txt lines: key x y, pixels; default = the bundled emulator one)"""
import argparse
import json
import os
import random
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.decoder import Lexicon, SweepConfig, SweepDecoder, collapse  # noqa: E402
from sweep.evaluate import DEFAULT_TABLE, load_entries, table_sha  # noqa: E402
from sweep.evaluate_words import DEFAULT_ESSAY, load_words  # noqa: E402
from sweep.keyboard import layout_from_centers_xy, to_key_units_xy  # noqa: E402
from sweep.words import WordConfig, WordDecoder, WordLexicon, main_codes  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EMULATOR = {  # key -> (x, y) pixel centres of the Android emulator keyboard used in the e2e test
    "a": (32, 520), "b": (192, 568), "c": (128, 568), "d": (96, 520), "e": (80, 472), "f": (128, 520), "g": (160, 520), "h": (192, 520),
    "i": (240, 472), "j": (224, 520), "k": (256, 520), "l": (288, 520), "m": (256, 568), "n": (224, 568), "o": (272, 472), "p": (304, 472),
    "q": (16, 472), "r": (112, 472), "s": (64, 520), "t": (144, 472), "u": (208, 472), "v": (160, 568), "w": (48, 472), "x": (96, 568),
    "y": (176, 472), "z": (64, 568)}


def px_path(keys, centers, step=50.0):
    return [[float(centers[k][0]), float(centers[k][1]), i * step] for i, k in enumerate(keys)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default="")
    a = ap.parse_args(argv)
    centers = dict(EMULATOR)
    if a.layout:
        centers = {}
        for line in open(a.layout):
            k, x, y = line.split()
            centers[k] = (int(x), int(y))
    L, sx, sy = layout_from_centers_xy(centers)
    chars = load_entries(DEFAULT_TABLE, min_len=1)
    ents = [e for e in chars if len(e[0]) >= 2]
    words = load_words(DEFAULT_ESSAY, 100)
    mc = main_codes(chars)
    cfg, wcfg = SweepConfig(), WordConfig()
    cases = []
    for cid, keys, target in (("slip-yhyjmnbvc", "yhyjmnbvc", "yhmbc"), ("slip-yhyhmbc", "yhyhmbc", "yhmbc"), ("slip-yuyjmnbc-ambiguous", "yuyjmnbc", "yjmbc"),
                              ("mild-yhjmnbvc", "yhjmnbvc", "yhmbc"), ("mild-yhmnbvc", "yhmnbvc", "yhmbc"), ("exact-yhmbc", "yhmbc", "yhmbc")):
        cases.append({"id": cid, "kind": "char", "keys": keys, "target_code": target, "points": px_path(keys, centers), "lifts": []})
    for cid, keys, target in (("word-顏值", "yhmnbvcojhbnm", "顏值"), ("word-頻率", "yhjmnbvcyuiokjhj", "頻率"), ("word-顏值-spur", "yhyjmnbvcojhbnm", "顏值")):
        cases.append({"id": cid, "kind": "word", "keys": keys, "target": target, "points": px_path(keys, centers), "lifts": []})
    full_c = SweepDecoder(Lexicon(ents, L, cfg.n), cfg)
    full_w = WordDecoder(WordLexicon(chars, words, L, wcfg), wcfg)
    # mini lexicons: REAL rows needed by the cases (code groups, top-12 competitors) + SYNTHETIC filler (private-use characters)
    real_c, real_w, wchars = {}, {}, set()
    wd = dict(words)
    for c in cases:
        pts = to_key_units_xy([tuple(p) for p in c["points"]], sx, sy)
        if c["kind"] == "char":
            for ch, code, sc in full_c.decode(pts, top_k=12):
                for e in ents:
                    if e[1] == ch or collapse(e[0]) == collapse(c["target_code"]):
                        real_c[(e[0], e[1])] = e
        else:
            for text, kind, sc in full_w.decode(pts, top_k=12):
                if kind == "word":
                    real_w[text] = wd[text]
                else:
                    wchars.add(text)
            real_w[c["target"]] = wd[c["target"]]
    for w in real_w:
        wchars.update(w)
    fr = random.Random(79)
    alpha = "abcdefghijklmnopqrstuvwxy"
    mini_c = sorted(real_c.values()) + [("".join(fr.choice(alpha) for _ in range(fr.randint(2, 5))), chr(0xE000 + i), float(fr.randint(1, 5000))) for i in range(1500)]
    mini_c.sort()
    wchar_rows = [e for e in chars if e[1] in wchars] + [("".join(fr.choice(alpha) for _ in range(fr.randint(2, 5))), chr(0xE800 + i), float(fr.randint(1, 5000))) for i in range(600)]
    wchar_rows.sort()
    for i in range(800):
        real_w.setdefault("".join(chr(0xE800 + fr.randrange(600)) for _ in range(fr.randint(2, 4))), fr.randint(1, 20000))
    mc_dec = SweepDecoder(Lexicon(mini_c, L, cfg.n), cfg)
    mw_dec = WordDecoder(WordLexicon(wchar_rows, sorted(real_w.items()), L, wcfg), wcfg)
    for c in cases:
        pts = to_key_units_xy([tuple(p) for p in c["points"]], sx, sy)
        if c["kind"] == "char":
            r = mc_dec.decode(pts, top_k=5)
            c["expected"] = [x[0] for x in r]
            c["expected_codes"] = [x[1] for x in r]
            c["expected_scores"] = [round(x[2], 6) for x in r]
            c["expected_full"] = [x[0] for x in full_c.decode(pts, top_k=5)]
            c["expected_full_codes"] = [x[1] for x in full_c.decode(pts, top_k=5)]
        else:
            r = mw_dec.decode(pts, c["lifts"], top_k=5)
            c["expected"] = [x[0] for x in r]
            c["expected_scores"] = [round(x[2], 6) for x in r]
            c["expected_full"] = [x[0] for x in full_w.decode(pts, c["lifts"], top_k=5)]
    out = {"format": "cangjie-sweep-phone-vectors-1",
           "note": "points are PIXELS on the emulator keyboard (centres below). Normalise first: sx, sy from the centres (SPEC.md 2c; here sx = 32, sy = 48), "
                   "u = ((x - 0) / sx, (y - 0) / sy, t); then decode with `config` / `word_config`. Char cases: compare ranked chars and codes; word cases: "
                   "ranked texts; scores to 1e-6. Lexicons: a few hundred REAL rows from the Cangjie 3 table / essay.txt (code groups of the targets, "
                   "top-ranked competitors) plus SYNTHETIC filler (random codes, private-use characters); the repository does not contain the table.",
           "table_sha256": table_sha(DEFAULT_TABLE), "centers_px": {k: list(v) for k, v in centers.items()}, "sx": sx, "sy": sy,
           "config": cfg.to_dict(), "word_config": wcfg.to_dict(), "chars": [[c, ch, w] for c, ch, w in mini_c],
           "word_chars": [[c, ch, w] for c, ch, w in wchar_rows], "words": [[w, f] for w, f in sorted(real_w.items())], "cases": cases}
    path = os.path.join(HERE, "vectors", "phone_vectors.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote", path, len(cases), "cases", os.path.getsize(path), "bytes")
    for c in cases:
        print(c["id"], c["expected"][:3], c.get("expected_codes", [])[:2], c["expected_full"][:2])


if __name__ == "__main__":
    main()
