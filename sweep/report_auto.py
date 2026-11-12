"""Before / after of the product-level policy (sweep/auto.py) on SYNTHETIC sweeps -> results/AUTO.md, auto.json.
'one-list' = the word decoder alone (characters + words 243k, defaults_words.json); 'auto' = decode_auto.   python3 -m sweep.report_auto"""
import argparse
import hashlib
import json
import multiprocessing
import os
import random
import sys
import time
from dataclasses import replace

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.auto import AutoDecoder, char_config  # noqa: E402
from sweep.decoder import Lexicon, SweepDecoder  # noqa: E402
from sweep.evaluate import DEFAULT_TABLE, entry_seed, load_entries, sample, split_entries  # noqa: E402
from sweep.evaluate_words import DEFAULT_ESSAY, MODES, load_words, stratified  # noqa: E402
from sweep.keyboard import default_layout  # noqa: E402
from sweep.simulate import PROFILES, generate, generate_word  # noqa: E402
from sweep.words import WordConfig, WordDecoder, WordLexicon, main_codes  # noqa: E402

RES = os.path.join(_ROOT, "sweep", "results")
_G = {}


def _work(item):
    kind, text, code = item
    rng = random.Random(entry_seed(1, text, kind))
    if kind == "char":
        pts, lifts = generate(code, _G["layout"], _G["profile"], 1.0, rng), []
    else:
        mode = MODES[int(hashlib.md5(text.encode("utf-8")).hexdigest()[:4], 16) % len(MODES)]
        pts, lifts = generate_word([_G["mc"][c] for c in text], _G["layout"], _G["profile"], 1.0, rng, mode)
    out = []
    for dec in (_G["one"], _G["auto"], _G["auto_mouse"]):
        res = dec.decode(pts, lifts, top_k=5)
        texts = [r[0] for r in res]
        out.append(texts.index(text) + 1 if text in texts else 99)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--essay", default=DEFAULT_ESSAY)
    a = ap.parse_args(argv)
    L = default_layout()
    chars = load_entries(a.table, min_len=1)
    ents = [e for e in chars if len(e[0]) >= 2]
    words = load_words(a.essay, 100)
    mc = main_codes(chars)
    wcfg = WordConfig()
    lex = WordLexicon(chars, words, L, wcfg)
    one = WordDecoder(lex, wcfg)
    citems = [("char", e[1], e[0]) for e in sample(split_entries(ents, "test"), 3000, 4)]
    cw = {e[1]: e[2] for e in ents}
    witems = [("word", w, f) for w, f in stratified(words, mc, "test", 100, 5)]
    R = {}
    md = ["# Product-level decode policy: one-list decoder alone vs decode_auto (SYNTHETIC sweeps)", "",
          "One-list = word decoder over characters + 243k words (defaults_words.json). Auto = SPEC section 12: single-character decoder and the one-list decoder; "
          "if the one-list best guess is a word its list is returned, else the characters followed by the words. 'auto (profile cfg)' uses the profile's own "
          "character config (defaults_<profile>.json), 'auto (mouse cfg)' the mouse defaults for every profile. Level mid, held-out %d characters and %d words "
          "(mixed continuous / dwell / lift). top-1 / top-5 %%; 'w' = frequency-weighted top-1 over characters (word sweeps are not weighted)." % (len(citems), len(witems)), "",
          "| profile | backtrack | sweeps | one-list | auto (profile cfg) | auto (mouse cfg) |", "|---|---|---|---|---|---|"]
    ctx = multiprocessing.get_context("fork")
    mcc = char_config("mouse")
    auto_mouse = AutoDecoder(SweepDecoder(Lexicon(ents, L, mcc.n), mcc), one)
    for prof in ("mouse", "finger"):
        cc = char_config(prof)
        auto = AutoDecoder(SweepDecoder(Lexicon(ents, L, cc.n), cc), one)
        for rate in (0.0, 0.4):
            _G.update(layout=L, profile=replace(PROFILES[prof], backtrack_prob=rate), mc=mc, one=one, auto=auto, auto_mouse=auto_mouse)
            with ctx.Pool(16) as pool:
                for name, items in (("char", citems), ("word", witems)):
                    ranks = pool.map(_work, items, chunksize=16)
                    cells = []
                    for j in range(3):
                        r = [x[j] for x in ranks]
                        t1 = sum(1 for v in r if v <= 1) / len(r)
                        t5 = sum(1 for v in r if v <= 5) / len(r)
                        wsum = sum(cw[it[1]] for it in items) if name == "char" else 1
                        w1 = (sum(cw[it[1]] for v, it in zip(r, items) if v <= 1) / wsum) if name == "char" else 0
                        cells.append((t1, t5, w1))
                    R["%s|%.1f|%s" % (prof, rate, name)] = cells
                    f = lambda c: "%.1f / %.1f%s" % (100 * c[0], 100 * c[1], (" (w %.1f)" % (100 * c[2])) if name == "char" else "")
                    md.append("| %s | %.1f | %s | %s | %s | %s |" % (prof, rate, name, f(cells[0]), f(cells[1]), f(cells[2])))
            print(prof, rate, flush=True)
    # latency
    paths = [generate_word([mc[c] for c in t], L, PROFILES["mouse"], 1.0, random.Random(entry_seed(3, t, "lat")), "continuous") for _, t, f in witems[::6]]
    cpaths = [(generate(c, L, PROFILES["mouse"], 1.0, random.Random(entry_seed(3, t, "lat"))), []) for _, t, c in citems[:100]]
    cc = char_config("mouse")
    auto = AutoDecoder(SweepDecoder(Lexicon(ents, L, cc.n), cc), one)
    md += ["", "Latency (pure Python, one core, mean / p95 ms): ", "", "| sweep | one-list | auto |", "|---|---|---|"]
    for name, ps in (("word", paths), ("character", cpaths)):
        row = []
        for dec in (one, auto):
            ts = []
            for pts, lifts in ps:
                t0 = time.perf_counter()
                dec.decode(pts, lifts, top_k=5)
                ts.append((time.perf_counter() - t0) * 1000)
            ts.sort()
            row.append("%.1f / %.1f" % (sum(ts) / len(ts), ts[int(len(ts) * 0.95)]))
        md.append("| %s | %s | %s |" % (name, row[0], row[1]))
    with open(os.path.join(RES, "auto.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, indent=1)
    with open(os.path.join(RES, "AUTO.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("wrote AUTO.md")


if __name__ == "__main__":
    main()
