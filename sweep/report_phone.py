"""Phone-like layouts (row pitch 1.0 / 1.3 / 1.5 / 1.7 key widths): raw decoding vs per-axis normalisation (y divided by the row pitch).
Strokes are SIMULATED on the raw layout (isotropic noise in key widths, as a finger would make it), then either decoded as they are on the raw
layout ("raw") or with y divided by the pitch on a pitch-1 layout ("normalised": the rule the ports must use).  -> results/PHONE.md, phone.json
  python3 -m sweep.report_phone [--table T] [--essay E]"""
import argparse
import hashlib
import json
import multiprocessing
import os
import random
import sys
from dataclasses import replace

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.layout import Layout  # noqa: E402
from sweep.decoder import Lexicon, SweepConfig, SweepDecoder  # noqa: E402
from sweep.evaluate import DEFAULT_TABLE, entry_seed, load_entries, sample, split_entries  # noqa: E402
from sweep.evaluate_words import DEFAULT_ESSAY, MODES, load_words, stratified  # noqa: E402
from sweep.keyboard import phone_qwerty  # noqa: E402
from sweep.simulate import PROFILES, generate, generate_word  # noqa: E402
from sweep.words import WordConfig, WordDecoder, WordLexicon, main_codes  # noqa: E402

RES = os.path.join(_ROOT, "sweep", "results")
_G = {}


def norm_layout(raw, pitch):
    return Layout({k: (x, y / pitch) for k, (x, y) in raw.centers.items()})


def _work(item):
    kind, a, b = item
    raw, pitch, norm = _G["raw"], _G["pitch"], _G["norm"]
    prof = _G["profile"]
    rng = random.Random(entry_seed(1, a, kind))
    if kind == "char":
        pts = generate(b, raw, prof, 1.0, rng)
        lifts = []
        text = a
    else:
        mode = MODES[int(hashlib.md5(a.encode("utf-8")).hexdigest()[:4], 16) % len(MODES)]
        pts, lifts = generate_word([_G["mc"][c] for c in a], raw, prof, 1.0, rng, mode)
        text = a
    if norm:
        pts = [(x, y / pitch, t) for (x, y, t) in pts]
    if kind == "char":
        res = _G["cdec"].decode(pts, top_k=5)
    else:
        res = _G["wdec"].decode(pts, lifts, top_k=5)
    texts = [r[0] for r in res]
    return texts.index(text) + 1 if text in texts else 99


def run(chars_items, word_items, raw_layout, pitch, norm, profile, ents, lexw, mc, workers=16):
    lay = norm_layout(raw_layout, pitch) if norm else raw_layout
    _G.update(raw=raw_layout, pitch=pitch, norm=norm, profile=profile, mc=mc)
    ccfg = SweepConfig()
    _G["cdec"] = SweepDecoder(Lexicon(ents, lay, ccfg.n), ccfg)
    wcfg = WordConfig()
    _G["wdec"] = WordDecoder(WordLexicon(lexw[0], lexw[1], lay, wcfg), wcfg) if word_items else None
    ctx = multiprocessing.get_context("fork")
    out = {}
    with ctx.Pool(workers) as pool:
        for name, items in (("char", chars_items), ("word", word_items)):
            if not items:
                continue
            ranks = pool.map(_work, items, chunksize=16)
            out[name] = (sum(1 for r in ranks if r <= 1) / len(ranks), sum(1 for r in ranks if r <= 5) / len(ranks))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--essay", default=DEFAULT_ESSAY)
    a = ap.parse_args(argv)
    chars = load_entries(a.table, min_len=1)
    ents = [e for e in chars if len(e[0]) >= 2]
    mc = main_codes(chars)
    words = load_words(a.essay, 1000)  # frequent words only: the geometry effect, not the lexicon size, is the subject here
    citems = [("char", e[1], e[0]) for e in sample(split_entries(ents, "test"), 3000, 4)]
    witems = [("word", w, f) for w, f in stratified(words, mc, "test", 40, 5)]
    R = {}
    md = ["# Phone-like layouts: raw vs per-axis normalised decoding (SYNTHETIC strokes)", "",
          "Layout = `phone_qwerty(row_pitch=p)` (rows staggered 0 / 0.5 / 1.5 key widths like the emulator keyboard). Strokes are simulated on the raw layout "
          "with isotropic noise in key widths. 'raw' decodes with the raw layout (y in key widths); 'normalised' divides y by the pitch (pitch-1 layout), "
          "the rule in SPEC.md. Level mid, default configs. Characters: %d held-out entries; words: %d (freq >= 1000 lexicon + chars; mixed boundaries). "
          "top-1 / top-5 %%." % (len(citems), len(witems)), "",
          "| profile | backtrack | pitch | chars raw | chars normalised | words raw | words normalised |", "|---|---|---|---|---|---|---|"]
    for prof in ("finger", "touchscreen"):
        for rate in (0.0, 0.4):
            pr = replace(PROFILES[prof], backtrack_prob=rate)
            for pitch in (1.0, 1.3, 1.5, 1.7):
                raw = phone_qwerty(row_pitch=pitch)
                cells = []
                for norm in (False, True):
                    o = run(citems, witems, raw, pitch, norm, pr, ents, (chars, words), mc)
                    R["%s|%.1f|%.1f|%s" % (prof, rate, pitch, "norm" if norm else "raw")] = o
                    cells.append(o)
                md.append("| %s | %.1f | %.1f | %.1f / %.1f | %.1f / %.1f | %.1f / %.1f | %.1f / %.1f |" % (
                    prof, rate, pitch, *(100 * v for v in cells[0]["char"]), *(100 * v for v in cells[1]["char"]),
                    *(100 * v for v in cells[0]["word"]), *(100 * v for v in cells[1]["word"])))
                print(prof, rate, pitch, flush=True)
    with open(os.path.join(RES, "phone.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, indent=1)
    with open(os.path.join(RES, "PHONE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
