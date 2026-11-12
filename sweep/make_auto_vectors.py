"""Generate sweep/vectors/auto_vectors.json: vectors of the product-level policy decode_auto (sweep/auto.py, SPEC section 12), on the ANSI
geometry and on the Android emulator phone geometry (pixel paths; apply the per-axis normalisation of SPEC section 2c first).
  python3 -m sweep.make_auto_vectors"""
import json
import os
import random
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.auto import AutoDecoder, char_config  # noqa: E402
from sweep.decoder import Lexicon, SweepDecoder, collapse  # noqa: E402
from sweep.evaluate import DEFAULT_TABLE, load_entries, table_sha  # noqa: E402
from sweep.evaluate_words import DEFAULT_ESSAY, load_words  # noqa: E402
from sweep.keyboard import default_layout, layout_from_centers_xy, to_key_units_xy  # noqa: E402
from sweep.make_phone_vectors import EMULATOR, px_path  # noqa: E402
from sweep.make_vectors import polyline_path  # noqa: E402
from sweep.words import WordConfig, WordDecoder, WordLexicon, main_codes  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TOPK = 5


def main():
    chars = load_entries(DEFAULT_TABLE, min_len=1)
    ents = [e for e in chars if len(e[0]) >= 2]
    words = load_words(DEFAULT_ESSAY, 1000)  # the Android lexicon size; the pad uses 100
    wd = dict(words)
    mc = main_codes(chars)
    ccfg, wcfg = char_config("mouse"), WordConfig()
    ansi = default_layout()
    phone, sx, sy = layout_from_centers_xy(EMULATOR)
    clean_word = max((w for w in words if len(w[0]) == 2 and all(c in mc for c in w[0])), key=lambda w: w[1])[0]
    specs = [("slip-yhyjmnbvc", "char", "yhyjmnbvc"), ("mild-yhjmnbvc", "char", "yhjmnbvc"), ("clean-yhmbc", "char", "yhmbc"),
             ("word-顏值", "word", "yhmnbvcojhbnm"), ("word-頻率", "word", "yhjmnbvcyuiokjhj"),
             ("clean-word-" + clean_word, "word", "".join(mc[c] for c in clean_word))]
    cases = []
    for geo in ("ansi", "phone"):
        for cid, kind, keys in specs:
            if geo == "ansi":
                pts = [[round(x, 4), round(y, 4), round(t, 1)] for (x, y, t) in polyline_path(keys, ansi)]
            else:
                pts = px_path(keys, EMULATOR)
            cases.append({"id": "%s-%s" % (geo, cid), "geometry": geo, "kind": kind, "points": pts, "lifts": []})

    def units(c):
        p = [tuple(q) for q in c["points"]]
        return p if c["geometry"] == "ansi" else to_key_units_xy(p, sx, sy)

    def lay(c):
        return ansi if c["geometry"] == "ansi" else phone

    full = {}
    for g, L in (("ansi", ansi), ("phone", phone)):
        full[g] = AutoDecoder(SweepDecoder(Lexicon(ents, L, ccfg.n), ccfg), WordDecoder(WordLexicon(chars, words, L, wcfg), wcfg))
    real_c, real_w, wchars = {}, {}, set()
    for c in cases:
        for text, kind, sc, code in full[c["geometry"]].decode(units(c), c["lifts"], top_k=12):
            if kind == "word":
                real_w[text] = wd[text]
            else:
                wchars.add(text)
    for w in list(real_w):
        wchars.update(w)
    real_w[clean_word] = wd[clean_word]
    wchars.update(clean_word)
    for e in ents:
        if collapse(e[0]) == "yhmbc" or e[1] in wchars:
            real_c[(e[0], e[1])] = e
    fr = random.Random(80)
    alpha = "abcdefghijklmnopqrstuvwxy"
    synth = [("".join(fr.choice(alpha) for _ in range(fr.randint(2, 5))), chr(0xE000 + i), float(fr.randint(1, 5000))) for i in range(1500)]
    mini_c = sorted(real_c.values()) + synth
    mini_c.sort()
    single = [e for e in chars if len(e[0]) == 1 and e[1] in wchars]
    word_chars = sorted(set(mini_c) | set(single))
    for i in range(800):
        real_w.setdefault("".join(chr(0xE000 + fr.randrange(1500)) for _ in range(fr.randint(2, 4))), fr.randint(1, 20000))
    kept = []
    for g, L in (("ansi", ansi), ("phone", phone)):
        dec = AutoDecoder(SweepDecoder(Lexicon(mini_c, L, ccfg.n), ccfg), WordDecoder(WordLexicon(word_chars, sorted(real_w.items()), L, wcfg), wcfg))
        for c in cases:
            if c["geometry"] != g:
                continue
            r = dec.decode(units(c), c["lifts"], top_k=TOPK)
            c["expected"] = [x[0] for x in r]
            c["expected_kinds"] = [x[1] for x in r]
            c["expected_codes"] = [x[3] for x in r]
            c["expected_scores"] = [round(x[2], 6) for x in r]
            rf = full[g].decode(units(c), c["lifts"], top_k=TOPK)
            c["expected_full"] = [x[0] for x in rf]
            c["expected_full_codes"] = [x[3] for x in rf]
            kept.append(c)
    out = {"format": "cangjie-sweep-auto-vectors-1",
           "note": "decode_auto (SPEC section 12): points are key-width units for geometry 'ansi', PIXELS for 'phone' (apply sx, sy from the centres first). "
                   "Ports: run the character decoder and the one-list word decoder with `config` / `word_config`; apply the policy; compare ranked texts, kinds, "
                   "codes (characters only) exactly and scores to 1e-6. Lexicons: a few hundred REAL rows (Cangjie 3 table / essay.txt) plus SYNTHETIC filler "
                   "(random codes, private-use characters); the repository does not contain the table.",
           "table_sha256": table_sha(DEFAULT_TABLE), "centers_px": {k: list(v) for k, v in EMULATOR.items()}, "sx": sx, "sy": sy,
           "config": ccfg.to_dict(), "word_config": wcfg.to_dict(), "chars": [[c, ch, w] for c, ch, w in mini_c],
           "word_chars": [[c, ch, w] for c, ch, w in word_chars], "words": [[w, f] for w, f in sorted(real_w.items())], "cases": kept}
    path = os.path.join(HERE, "vectors", "auto_vectors.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote", path, len(kept), "cases", os.path.getsize(path), "bytes")
    for c in kept:
        print(c["id"], c["expected"][:3], c["expected_kinds"][:2], c["expected_codes"][:1], c["expected_full"][:2])


if __name__ == "__main__":
    main()
