"""Random search + local refinement of SweepConfig on the TRAIN split (synthetic sweeps). Held-out numbers come from evaluate.py on
the test split with different noise seeds.

  python3 -m sweep.tune --profile mouse --trials 120 --refine 60 --sample 900 --out sweep/results/tuned_mouse.json
Objective = mean over levels low/mid/high/vhigh of 0.5*(top1 + w1) + 0.25*(top5 + w5); w = frequency weighted.
n (24), prune_radius (1.2) and dwell_ms (250; a user-interface constant, and a tuned value was seen to exploit the simulator's assumed hold time) are fixed, not searched: they trade latency for nothing (see results/REPORT.md).
"""
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
from sweep.evaluate import DEFAULT_TABLE, load_entries, run_trial, sample, split_entries  # noqa: E402

LEVELS_USED = ("low", "mid", "high", "vhigh")


def logu(rng, lo, hi):
    return math.exp(rng.uniform(math.log(lo), math.log(hi)))


SPACE = {
    "shape_weight": lambda r: r.choice([0.0, logu(r, 0.5, 24)]),
    "loc_weight": lambda r: logu(r, 0.5, 24),
    "end_weight": lambda r: r.choice([0.0, logu(r, 0.5, 24)]),
    "cover_weight": lambda r: r.choice([0.0, logu(r, 0.5, 24)]),
    "end_alpha": lambda r: r.uniform(1.0, 4.0),
    "loc_tolerance": lambda r: r.choice([0.0, r.uniform(0.05, 0.4)]),
    "shape_short_scale": lambda r: r.uniform(0.0, 1.0),
    "prior_weight": lambda r: logu(r, 0.05, 0.4),
    "repeat_miss_penalty": lambda r: logu(r, 0.3, 6.0),
    "dwell_extra_penalty": lambda r: logu(r, 0.3, 6.0),
}


def objective(lex_entries, tr, cfg, profile, layout, seed, workers=None):
    tot, per = 0.0, {}
    for lv in LEVELS_USED:
        r = run_trial(lex_entries, tr, cfg, profile, lv, seed=seed, layout=layout, workers=workers)["all"]
        per[lv] = (r["top1"], r["top3"], r["top5"], r["w1"], r["w5"])
        # unweighted (every character counts once: rare characters matter) and frequency-weighted (what a user types)
        tot += 0.5 * (r["top1"] + r["w1"]) + 0.25 * (r["top5"] + r["w5"])
    return tot / len(LEVELS_USED), per


def perturb(cfg, rng):
    key = rng.choice(list(SPACE))
    cur = getattr(cfg, key)
    if isinstance(cur, float) and cur > 0:
        new = cur * math.exp(rng.gauss(0, 0.35))
        if key == "end_alpha":
            new = max(1.0, new)
        if key == "prior_weight":
            new = min(0.4, max(0.05, new))
        if key in ("shape_short_scale",):
            new = min(1.0, new)
    else:
        new = SPACE[key](rng)
    return cfg.replace(**{key: new})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--trials", type=int, default=100)
    ap.add_argument("--refine", type=int, default=50)
    ap.add_argument("--sample", type=int, default=900)
    ap.add_argument("--layout", default="pc")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    lex_entries = load_entries(a.table)
    tr = sample(split_entries(lex_entries, "train"), a.sample, 5)
    rng = random.Random(a.seed)
    log = []
    base = SweepConfig().replace(n=24, prune_radius=1.2)
    best_cfg, (best_obj, best_per) = base, objective(lex_entries, tr, base, a.profile, a.layout, 101, a.workers)
    log.append({"cfg": base.to_dict(), "obj": best_obj, "per": best_per, "phase": "default"})
    print("default obj %.4f" % best_obj, flush=True)
    t0 = time.time()
    for i in range(a.trials + a.refine):
        if i < a.trials:
            cfg = base.replace(**{k: f(rng) for k, f in SPACE.items()})
            phase = "random"
        else:
            cfg = perturb(best_cfg, rng)
            phase = "refine"
        obj, per = objective(lex_entries, tr, cfg, a.profile, a.layout, 101, a.workers)
        log.append({"cfg": cfg.to_dict(), "obj": obj, "per": per, "phase": phase})
        if obj > best_obj:
            best_cfg, best_obj, best_per = cfg, obj, per
            print("[%d %s] obj %.4f  mid top1 %.3f top5 %.3f  (%.0fs)" % (i, phase, obj, per["mid"][0], per["mid"][2], time.time() - t0), flush=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"profile": a.profile, "best": best_cfg.to_dict(), "best_obj": best_obj, "best_per": best_per, "train_n": len(tr),
                   "trials": log}, f, indent=1)
    print("BEST", json.dumps(best_cfg.to_dict()), best_obj)


if __name__ == "__main__":
    main()
