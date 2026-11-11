"""Evaluation harness for the sweep decoder on SYNTHETIC sweeps (see simulate.py; not real finger/mouse data).

Unit of evaluation: one lexicon entry (code, char) with len(code) >= 2. A decode is correct at k if `char` is among the first k ranked
characters. Entries are split train/test by hash of the CHARACTER (so a character with two codes never straddles the split).

  python3 -m sweep.evaluate --table cangjie3.tsv --profiles finger,mouse --levels oracle,low,mid,high --split test
Rows: overall, by code length, repeat codes ('hh'), shared codes (another char has the exact same code), clean (unique, no repeat).
The 'oracle' level (noiseless path through the exact code keys) is the CEILING: characters sharing a code can never all be first.
"""
import argparse
import hashlib
import json
import multiprocessing
import os
import random
import sys
import time

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.decoder import Lexicon, SweepConfig, SweepDecoder, repeat_positions  # noqa: E402
from sweep.keyboard import default_layout, phone_qwerty  # noqa: E402
from sweep.simulate import LEVELS, PROFILES, generate  # noqa: E402

DEFAULT_TABLE = "/tmp/fw/f5a/app/src/main/assets/fuzzy/cangjie3.tsv"
CATS = ["all", "len2", "len3", "len4", "len5", "repeat", "shared", "clean"]


def load_entries(path, min_len=2):
    ents = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3 and len(p[0]) >= min_len:
                ents.append((p[0], p[1], float(p[2])))
    return ents


def table_sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def split_of(ch, train_frac=0.25):
    h = int(hashlib.md5(ch.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "train" if h < train_frac else "test"


def split_entries(entries, which):
    return [e for e in entries if which == "all" or split_of(e[1]) == which]


def categories(entries):
    cnt = {}
    for c, ch, w in entries:
        cnt[c] = cnt.get(c, 0) + 1
    out = []
    for c, ch, w in entries:
        cats = ["all", "len%d" % len(c)]
        if repeat_positions(c):
            cats.append("repeat")
        if cnt[c] > 1:
            cats.append("shared")
        if not repeat_positions(c) and cnt[c] == 1:
            cats.append("clean")
        out.append(cats)
    return out


def entry_seed(seed, code, ch):
    return int(hashlib.md5(("%d|%s|%s" % (seed, code, ch)).encode("utf-8")).hexdigest()[:12], 16)


def level_value(level):
    """'low' / 'mid' / ... or 'k0.75' (any multiplier) or a number."""
    if isinstance(level, str):
        return float(level[1:]) if level.startswith("k") else LEVELS[level]
    return float(level)


def parse_layout(name):
    """'pc' | 'phone' (raw pitch 1.3) | 'phone:<pitch>:raw' | 'phone:<pitch>:norm'. Returns (layout the strokes are simulated on,
    layout the decoder uses, y divisor applied to the strokes before decoding). 'norm' = per-axis normalisation: strokes' y / pitch, decoder
    layout with pitch 1 (the SPEC rule); 'raw' = decode in key widths on both axes."""
    if name == "pc":
        return default_layout(), default_layout(), 1.0
    if name == "phone":
        lay = phone_qwerty()
        return lay, lay, 1.0
    _, pitch, mode = name.split(":")
    pitch = float(pitch)
    raw = phone_qwerty(row_pitch=pitch)
    if mode == "norm":
        return raw, phone_qwerty(row_pitch=1.0), pitch
    return raw, raw, 1.0


_G = {}


def _init(layout_name, lex_entries, cfg_dict, profile, level, seed):
    layout, dec_layout, ysc = parse_layout(layout_name)
    lex = Lexicon(lex_entries, dec_layout, cfg_dict["n"])
    _G["dec"] = SweepDecoder(lex, SweepConfig(**cfg_dict))
    _G["layout"] = layout
    _G["ysc"] = ysc
    _G["profile"] = PROFILES[profile] if isinstance(profile, str) else profile
    _G["level"] = level_value(level)
    _G["seed"] = seed


def _work(item):
    code, ch, w = item
    rng = random.Random(entry_seed(_G["seed"], code, ch))
    pts = generate(code, _G["layout"], _G["profile"], _G["level"], rng)
    if _G["ysc"] != 1.0:
        pts = [(x, y / _G["ysc"], t) for (x, y, t) in pts]
    res = _G["dec"].decode(pts, top_k=5)
    chars = [r[0] for r in res]
    return chars.index(ch) + 1 if ch in chars else 99


def run_trial(lex_entries, test_entries, cfg, profile, level, seed=1, workers=None, layout="pc"):
    """Returns {cat: {n, top1, top3, top5, w1, w3, w5}} (fractions; w* = frequency weighted)."""
    workers = workers or max(1, (os.cpu_count() or 2) - 2)
    cats = categories(test_entries)
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(workers, initializer=_init, initargs=(layout, lex_entries, cfg.to_dict(), profile, level, seed)) as pool:
        ranks = pool.map(_work, test_entries, chunksize=64)
    agg = {c: {"n": 0, "t1": 0, "t3": 0, "t5": 0, "W": 0.0, "w1": 0.0, "w3": 0.0, "w5": 0.0} for c in CATS}
    for (code, ch, w), r, cs in zip(test_entries, ranks, cats):
        for c in cs:
            a = agg[c]
            a["n"] += 1
            a["W"] += w
            for k, key, wkey in ((1, "t1", "w1"), (3, "t3", "w3"), (5, "t5", "w5")):
                if r <= k:
                    a[key] += 1
                    a[wkey] += w
    out = {}
    for c, a in agg.items():
        if a["n"]:
            out[c] = {"n": a["n"], "top1": a["t1"] / a["n"], "top3": a["t3"] / a["n"], "top5": a["t5"] / a["n"],
                      "w1": a["w1"] / a["W"], "w3": a["w3"] / a["W"], "w5": a["w5"] / a["W"]}
    return out


def sample(entries, n, seed):
    if not n or n >= len(entries):
        return list(entries)
    return random.Random(seed).sample(entries, n)


def latency(lex_entries, cfg, profile, level, items, layout="pc", repeat=1):
    lay = default_layout() if layout == "pc" else phone_qwerty()
    dec = SweepDecoder(Lexicon(lex_entries, lay, cfg.n), cfg)
    paths = [generate(c, lay, PROFILES[profile], level_value(level), random.Random(entry_seed(7, c, ch))) for c, ch, w in items]
    ts = []
    for _ in range(repeat):
        for p in paths:
            t = time.perf_counter()
            dec.decode(p, top_k=5)
            ts.append((time.perf_counter() - t) * 1000.0)
    ts.sort()
    return {"mean_ms": sum(ts) / len(ts), "p50_ms": ts[len(ts) // 2], "p95_ms": ts[int(len(ts) * 0.95)], "max_ms": ts[-1], "n": len(ts)}


def pct(x):
    return "%.1f" % (100.0 * x)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--profiles", default="mouse,finger")
    ap.add_argument("--levels", default="oracle,low,mid,high")
    ap.add_argument("--split", default="test", choices=["train", "test", "all"])
    ap.add_argument("--sample", type=int, default=0, help="0 = all entries of the split")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--config", default="", help="JSON file with SweepConfig overrides")
    ap.add_argument("--layout", default="pc", type=str)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    lex_entries = load_entries(a.table)
    test_entries = split_entries(lex_entries, a.split)
    if a.sample:
        test_entries = sample(test_entries, a.sample, 123)
    cfg = SweepConfig()
    if a.config:
        with open(a.config) as f:
            cfg = cfg.replace(**json.load(f))
    result = {"table_sha256": table_sha(a.table), "n_entries_total": len(lex_entries), "split": a.split, "n_test": len(test_entries),
              "config": cfg.to_dict(), "layout": a.layout, "runs": {}}
    for prof in a.profiles.split(","):
        for lv in a.levels.split(","):
            seeds = 1 if lv == "oracle" else a.seeds
            per = [run_trial(lex_entries, test_entries, cfg, prof, lv, seed=s, layout=a.layout) for s in range(1, seeds + 1)]
            result["runs"]["%s/%s" % (prof, lv)] = per
            r = per[0]["all"]
            print("%s/%s top1 %s top3 %s top5 %s (n=%d)" % (prof, lv, pct(r["top1"]), pct(r["top3"]), pct(r["top5"]), r["n"]), flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    return result


if __name__ == "__main__":
    main()
