"""Random search + local refinement of the word-level parameters (WordConfig) on the TRAIN words (synthetic sweeps).
  python3 -m sweep.tune_words --trials 40 --refine 40 --per-cell 50 --out sweep/results/tune_words.json
Objective = mean over (mouse, finger) x (mid, high) of 0.5*(word top1 + 0.5*top5) + 0.5*(single-character-sweep top1 + 0.5*top5), on train words / chars. Channel weights are searched too because the
evidence of a long path is not the sum of the evidence of short ones."""
import argparse
import json
import math
import os
import random
import sys
import time

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.decoder import SweepConfig  # noqa: E402
from sweep.evaluate import DEFAULT_TABLE, load_entries, split_of  # noqa: E402
from sweep.evaluate_words import DEFAULT_ESSAY, load_words, run_words, stratified  # noqa: E402
from sweep.keyboard import default_layout  # noqa: E402
from sweep.words import WordConfig, WordLexicon, main_codes  # noqa: E402


def logu(r, lo, hi):
    return math.exp(r.uniform(math.log(lo), math.log(hi)))


SPACE = {
    "word_prior_weight": lambda r: logu(r, 0.05, 3.0),
    "char_offset": lambda r: r.uniform(-3.0, 3.0),
    "evidence_power": lambda r: r.uniform(0.0, 1.2),
    "loc_weight": lambda r: logu(r, 2.0, 40.0),
    "end_weight": lambda r: r.choice([0.0, logu(r, 1.0, 40.0)]),
    "cover_weight": lambda r: r.choice([0.0, logu(r, 0.5, 20.0)]),
    "end_alpha": lambda r: r.uniform(1.0, 3.0),
    "boundary_dwell_bonus": lambda r: r.uniform(0.0, 2.0),
    "lift_weight": lambda r: logu(r, 0.5, 20.0),
}


def perturb(cfg, rng):
    k = rng.choice(list(SPACE))
    cur = getattr(cfg, k)
    if k == "char_offset":
        new = cur + rng.gauss(0, 0.6)
    elif cur > 0:
        new = cur * math.exp(rng.gauss(0, 0.35))
        if k == "end_alpha":
            new = max(1.0, new)
        if k == "evidence_power":
            new = min(1.5, new)
    else:
        new = SPACE[k](rng)
    return cfg.replace(**{k: new})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--essay", default=DEFAULT_ESSAY)
    ap.add_argument("--min-freq", type=int, default=100)
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--refine", type=int, default=40)
    ap.add_argument("--per-cell", type=int, default=50)
    ap.add_argument("--char-items", type=int, default=300)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    chars = load_entries(a.table, min_len=1)
    words = load_words(a.essay, a.min_freq)
    base = WordConfig()
    lex = WordLexicon(chars, words, default_layout(), base)
    mc = main_codes(chars)
    items = stratified(words, mc, "train", a.per_cell, 11)
    rngc = random.Random(31)
    train_chars = [(e[1], e[0]) for e in chars if len(e[0]) >= 2 and split_of(e[1]) == "train"]
    char_items = rngc.sample(train_chars, a.char_items)
    print("train words", len(items), "train char sweeps", len(char_items), flush=True)

    def objective(cfg):
        tot, per = 0.0, {}
        for prof in ("mouse", "finger"):
            for lv in ("mid", "high"):
                r = run_words(lex, cfg, items, prof, lv, seed=101, mc=mc, workers=a.workers)["all"]
                c = run_words(lex, cfg, char_items, prof, lv, seed=101, kind="char", mc=mc, workers=a.workers)["all"]
                per["%s/%s" % (prof, lv)] = (r["top1"], r["top5"], c["top1"], c["top5"])
                # half word sweeps, half single-character sweeps: both are decoded by the same unified lexicon
                tot += 0.5 * (r["top1"] + 0.5 * r["top5"]) + 0.5 * (c["top1"] + 0.5 * c["top5"])
        return tot / 4, per

    rng = random.Random(21)
    best_cfg = base
    best_obj, best_per = objective(base)
    log = [{"cfg": base.to_dict(), "obj": best_obj, "per": best_per, "phase": "default"}]
    print("default obj %.4f" % best_obj, best_per, flush=True)
    t0 = time.time()
    for i in range(a.trials + a.refine):
        if i < a.trials:
            cfg = base.replace(**{k: f(rng) for k, f in SPACE.items()})
            phase = "random"
        else:
            cfg = perturb(best_cfg, rng)
            phase = "refine"
        obj, per = objective(cfg)
        log.append({"cfg": cfg.to_dict(), "obj": obj, "per": per, "phase": phase})
        if obj > best_obj:
            best_cfg, best_obj, best_per = cfg, obj, per
            print("[%d %s] obj %.4f %s (%.0fs)" % (i, phase, obj, {k: tuple(round(x, 3) for x in v) for k, v in per.items()}, time.time() - t0), flush=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"best": best_cfg.to_dict(), "best_obj": best_obj, "best_per": best_per, "train_n": len(items), "trials": log}, f, indent=1)
    print("BEST", json.dumps(best_cfg.to_dict()), best_obj)


if __name__ == "__main__":
    main()
