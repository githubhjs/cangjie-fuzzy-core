"""Word-level evaluation on SYNTHETIC sweeps: whole words (2-4 characters) swept in one stroke or with lifts / dwells at the boundaries.

  python3 -m sweep.evaluate_words --table cangjie3.tsv --essay essay.txt --profiles mouse,finger --levels mid,high
Words: essay.txt lines `word<TAB>freq`; only words whose characters all have a Cangjie 3 code are usable (main code = shortest).
Train/test split by hash of the WORD (tuning uses train only). Boundary modes are mixed 50% continuous / 25% dwell / 25% lift.
"""
import argparse
import hashlib
import json
import math
import multiprocessing
import os
import random
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.decoder import SweepConfig, SweepDecoder, Lexicon  # noqa: E402
from sweep.evaluate import DEFAULT_TABLE, entry_seed, level_value, load_entries, table_sha  # noqa: E402
from sweep.keyboard import default_layout  # noqa: E402
from sweep.simulate import PROFILES, generate, generate_word  # noqa: E402
from sweep.words import WordConfig, WordDecoder, WordLexicon, main_codes  # noqa: E402

DEFAULT_ESSAY = os.path.expanduser("~/projects/cangjie-fluency/data/essay.txt")
BANDS = [("1k-3k", 1000, 3000), ("3k-10k", 3000, 10000), (">=10k", 10000, 10 ** 9)]
MODES = ["continuous", "continuous", "dwell", "lift"]


def load_words(path, min_freq):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) == 2 and p[1].isdigit() and int(p[1]) >= min_freq:
                out.append((p[0], int(p[1])))
    return out


def word_split(word):
    h = int(hashlib.md5(("w" + word).encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "train" if h < 0.3 else "test"


def stratified(words, mc, split, per_cell, seed):
    cells = {}
    for w, f in words:
        if not (2 <= len(w) <= 4) or any(c not in mc for c in w) or word_split(w) != split:
            continue
        for name, lo, hi in BANDS:
            if lo <= f < hi:
                cells.setdefault((len(w), name), []).append((w, f))
    rng = random.Random(seed)
    out = []
    for key in sorted(cells):
        lst = sorted(cells[key])
        out.extend(rng.sample(lst, min(per_cell, len(lst))))
    return out


_G = {}


def _winit(lex, cfg_dict, mc, profile, level, seed, kind):
    _G["dec"] = WordDecoder(lex, WordConfig(**cfg_dict))
    _G["mc"] = mc
    _G["profile"] = PROFILES[profile] if isinstance(profile, str) else profile
    _G["level"] = level_value(level)
    _G["seed"] = seed
    _G["kind"] = kind
    _G["layout"] = lex.layout


def _wwork(item):
    text, freq = item
    rng = random.Random(entry_seed(_G["seed"], text, "w"))
    if _G["kind"] == "word":
        mode = MODES[int(hashlib.md5(text.encode("utf-8")).hexdigest()[:4], 16) % len(MODES)]
        pts, lifts = generate_word([_G["mc"][c] for c in text], _G["layout"], _G["profile"], _G["level"], rng, mode)
    else:  # single character sweep, item = (char, code)
        mode = "char"
        pts, lifts = generate(freq, _G["layout"], _G["profile"], _G["level"], rng), []
    res = _G["dec"].decode(pts, lifts, top_k=5)
    texts = [r[0] for r in res]
    rank = texts.index(text) + 1 if text in texts else 99
    top = res[0][0] if res else ""
    # per-position character accuracy of the top-1 candidate (words only)
    pos = 0
    if _G["kind"] == "word" and len(top) == len(text):
        pos = sum(1 for a, b in zip(top, text) if a == b)
    return rank, mode, pos


def run_words(lex, cfg, items, profile, level, seed=1, kind="word", workers=None, mc=None):
    workers = workers or max(1, (os.cpu_count() or 2) - 2)
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(workers, initializer=_winit, initargs=(lex, cfg.to_dict(), mc, profile, level, seed, kind)) as pool:
        res = pool.map(_wwork, items, chunksize=8)
    out = {"n": len(items)}
    def agg(filt):
        rows = [(r, it) for r, it in zip(res, items) if filt(r, it)]
        if not rows:
            return None
        n = len(rows)
        return {"n": n, "top1": sum(1 for (rk, m, p), _ in rows if rk <= 1) / n, "top3": sum(1 for (rk, m, p), _ in rows if rk <= 3) / n,
                "top5": sum(1 for (rk, m, p), _ in rows if rk <= 5) / n}
    out["all"] = agg(lambda r, it: True)
    if kind == "word":
        for mode in ("continuous", "dwell", "lift"):
            out["mode_" + mode] = agg(lambda r, it, mode=mode: r[1] == mode)
        for L in (2, 3, 4):
            out["len%d" % L] = agg(lambda r, it, L=L: len(it[0]) == L)
        for name, lo, hi in BANDS:
            out["freq_" + name] = agg(lambda r, it, lo=lo, hi=hi: lo <= it[1] < hi)
        tot = sum(len(it[0]) for it in items)
        out["char_pos_acc_top1"] = sum(r[2] for r in res) / tot
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--essay", default=DEFAULT_ESSAY)
    ap.add_argument("--min-freq", type=int, default=100)
    ap.add_argument("--profiles", default="mouse,finger")
    ap.add_argument("--levels", default="low,mid,high")
    ap.add_argument("--split", default="test")
    ap.add_argument("--per-cell", type=int, default=100)
    ap.add_argument("--config", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    chars = load_entries(a.table, min_len=1)
    words = load_words(a.essay, a.min_freq)
    cfg = WordConfig()
    if a.config:
        with open(a.config) as f:
            d = json.load(f)
        cfg = cfg.replace(**d.get("best", d))
    lex = WordLexicon(chars, words, default_layout(), cfg)
    mc = main_codes(chars)
    items = stratified(words, mc, a.split, a.per_cell, 5)
    print("lexicon: %d words, %d templates; eval words %d" % (lex.n_words, len(lex.templates), len(items)), flush=True)
    res = {"table_sha256": table_sha(a.table), "min_freq": a.min_freq, "n_words_lexicon": lex.n_words, "config": cfg.to_dict(), "runs": {}}
    for p in a.profiles.split(","):
        for lv in a.levels.split(","):
            r = run_words(lex, cfg, items, p, lv, mc=mc)
            res["runs"]["%s/%s" % (p, lv)] = r
            print("%s/%s words top1 %.1f top5 %.1f (char-pos acc %.1f)" % (p, lv, 100 * r["all"]["top1"], 100 * r["all"]["top5"], 100 * r["char_pos_acc_top1"]), flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    return res


if __name__ == "__main__":
    main()
