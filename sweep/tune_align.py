"""Tune the spur / backtrack tolerance (key-sequence alignment rerank) on the TRAIN split of characters, synthetic sweeps.
  python3 -m sweep.tune_align --out sweep/results/tune_align.json
Scenarios (profile x layout x backtrack rate, level mid): mouse/ANSI, finger/ANSI, finger/phone pitch 1.5 normalised; rates 0 / 0.15 / 0.4. Objective = mean over scenarios of
0.5*(top1 + w1) + 0.25*(top5 + w5), with the clean scenarios (rate 0) counted double so clean accuracy is protected."""
import argparse
import json
import math
import os
import random
import sys
import time
from dataclasses import replace

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.decoder import SweepConfig  # noqa: E402
from sweep.evaluate import DEFAULT_TABLE, load_entries, run_trial, sample, split_entries  # noqa: E402
from sweep.simulate import PROFILES  # noqa: E402

RATES = (0.0, 0.15, 0.4)


def logu(r, lo, hi):
    return math.exp(r.uniform(math.log(lo), math.log(hi)))


SPACE = {
    "align_weight": lambda r: logu(r, 0.2, 10.0),
    "align_gate": lambda r: logu(r, 0.5, 30.0),
    "align_ins": lambda r: r.uniform(0.05, 0.6),
    "hit_radius": lambda r: r.uniform(0.35, 0.65),
}


def objective(lex, tr, cfg, workers):
    tot, wsum, per = 0.0, 0.0, {}
    for prof, layout in (('mouse', 'pc'), ('finger', 'pc'), ('finger', 'phone:1.5:norm')):
        for rate in RATES:
            pr = replace(PROFILES[prof], backtrack_prob=rate)
            r = run_trial(lex, tr, cfg, pr, 'mid', seed=101, workers=workers, layout=layout)['all']
            wgt = 2.0 if rate == 0.0 else 1.0
            tot += wgt * (0.5 * (r['top1'] + r['w1']) + 0.25 * (r['top5'] + r['w5']))
            wsum += wgt
            per['%s/%s/%.2f' % (prof, layout, rate)] = (r['top1'], r['top5'], r['w1'])
    return tot / wsum, per


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--refine", type=int, default=40)
    ap.add_argument("--sample", type=int, default=800)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    lex = load_entries(a.table)
    tr = sample(split_entries(lex, "train"), a.sample, 5)
    rng = random.Random(41)
    base = SweepConfig()
    best_cfg = base
    best_obj, best_per = objective(lex, tr, base, a.workers)
    log = [{"cfg": base.to_dict(), "obj": best_obj, "per": best_per, "phase": "off"}]
    print("align off obj %.4f" % best_obj, {k: tuple(round(x, 3) for x in v) for k, v in best_per.items()}, flush=True)
    t0 = time.time()
    for i in range(a.trials + a.refine):
        if i < a.trials:
            cfg = base.replace(**{k: f(rng) for k, f in SPACE.items()})
            phase = "random"
        else:
            k = rng.choice(list(SPACE))
            cur = getattr(best_cfg, k)
            cfg = best_cfg.replace(**{k: max(0.05, cur * math.exp(rng.gauss(0, 0.3)))})
            phase = "refine"
        obj, per = objective(lex, tr, cfg, a.workers)
        log.append({"cfg": cfg.to_dict(), "obj": obj, "per": per, "phase": phase})
        if obj > best_obj:
            best_cfg, best_obj, best_per = cfg, obj, per
            print("[%d %s] obj %.4f %s (%.0fs)" % (i, phase, obj, {k: tuple(round(x, 3) for x in v[:2]) for k, v in per.items()}, time.time() - t0), flush=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"best": {k: getattr(best_cfg, k) for k in SPACE}, "best_obj": best_obj, "best_per": best_per, "trials": log}, f, indent=1)
    print("BEST", {k: getattr(best_cfg, k) for k in SPACE}, best_obj)


if __name__ == "__main__":
    main()
