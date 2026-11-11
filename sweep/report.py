"""Final held-out evaluation: tuned defaults per profile, noise sweep, category rows, ablations, lexicon size, latency.
Writes sweep/results/final.json and sweep/results/REPORT.md.   python3 -m sweep.report [--table T] [--quick]

All numbers are on SYNTHETIC sweeps (sweep/simulate.py). The test split (75% of characters by hash) was never used for tuning.
"""
import argparse
import json
import os
import random
import sys
import time
from dataclasses import replace

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.decoder import Lexicon, SweepConfig, SweepDecoder  # noqa: E402
from sweep.evaluate import (CATS, DEFAULT_TABLE, latency, load_entries, run_trial, sample, split_entries, split_of,  # noqa: E402
                            table_sha)
from sweep.simulate import PROFILES  # noqa: E402

RES = os.path.join(_ROOT, "sweep", "results")
PROFS = ["mouse", "touchpad", "finger", "touchscreen"]


def load_tuned():
    out = {}
    for p in PROFS:
        path = os.path.join(RES, "defaults_%s.json" % p)
        if os.path.exists(path):
            with open(path) as f:
                out[p] = SweepConfig(**json.load(f))
    return out


def mean_over_seeds(runs):
    """runs: list of {cat: {...}} -> {cat: {metric: (mean, lo, hi)}}"""
    out = {}
    for cat in runs[0]:
        out[cat] = {}
        for m in ("n", "top1", "top3", "top5", "w1", "w3", "w5"):
            vals = [r[cat][m] for r in runs]
            out[cat][m] = (sum(vals) / len(vals), min(vals), max(vals))
    return out


def trial(lex, test, cfg, prof, level, seeds):
    return mean_over_seeds([run_trial(lex, test, cfg, prof, level, seed=s) for s in range(1, seeds + 1)])


def cell(m, key):
    v = m[key]
    return "%.1f" % (100 * v[0]) if v[2] - v[1] < 1e-9 else "%.1f (%.1f-%.1f)" % (100 * v[0], 100 * v[1], 100 * v[2])


def analytic_ceiling(lex, test):
    """If the exact code were known with certainty, characters sharing a code are ranked by weight: the best any path decoder can do."""
    groups = {}
    for c, ch, w in lex:
        groups.setdefault(c, []).append((-w, ch))
    rank = {}
    for c, g in groups.items():
        for i, (nw, ch) in enumerate(sorted(g)):
            rank[(c, ch)] = i + 1
    n = len(test)
    out = {}
    for k in (1, 3, 5):
        out["top%d" % k] = sum(1 for c, ch, w in test if rank[(c, ch)] <= k) / n
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args(argv)
    lex = load_entries(a.table)
    test = split_entries(lex, "test")
    if a.quick:
        test = sample(test, 3000, 1)
    abl_test = sample(test, 6000, 2)
    tuned = load_tuned()
    default_cfg = SweepConfig()
    R = {"table_sha256": table_sha(a.table), "n_lexicon_entries_len>=2": len(lex), "n_test": len(test), "seeds": a.seeds,
         "tuned": {p: c.to_dict() for p, c in tuned.items()}, "default_untuned": default_cfg.to_dict()}
    md = ["# Sweep decoder: held-out results on SYNTHETIC sweeps", "",
          "Table sha256 `%s`; %d entries with code length >= 2; test split = %d entries (characters hashed out of the tuning split). "
          "Noise seeds 1..%d, mean (min-max). Levels multiply the profile's spatial errors: low x0.5, mid x1, high x1.6; "
          "oracle = noiseless path through the exact code keys (the CEILING: characters sharing one code cannot all be first)." %
          (R["table_sha256"], len(lex), len(test), a.seeds), ""]

    R["analytic_ceiling"] = analytic_ceiling(lex, test)
    md += ["Analytic ceiling on the test split (exact code known, ties broken by weight): top-1 %.1f, top-3 %.1f, top-5 %.1f." % (
        100 * R["analytic_ceiling"]["top1"], 100 * R["analytic_ceiling"]["top3"], 100 * R["analytic_ceiling"]["top5"]), ""]

    # 1. main table
    R["main"] = {}
    md += ["## 1. Tuned defaults per profile, test split", "", "| profile | level | top-1 | top-3 | top-5 | freq-weighted top-1 / top-5 |", "|---|---|---|---|---|---|"]
    for p in PROFS:
        if p not in tuned:
            continue
        for lv in ("oracle", "low", "mid", "high", "vhigh"):
            m = trial(lex, test, tuned[p], p, lv, 1 if lv == "oracle" else a.seeds)
            R["main"]["%s/%s" % (p, lv)] = m
            md.append("| %s | %s | %s | %s | %s | %.1f / %.1f |" % (p, lv, cell(m["all"], "top1"), cell(m["all"], "top3"), cell(m["all"], "top5"),
                                                              100 * m["all"]["w1"][0], 100 * m["all"]["w5"][0]))
        print("main", p, flush=True)

    # 2. categories at mid
    md += ["", "## 2. By code length and code type at level mid (top-1 / top-5, %)", "",
           "| profile | " + " | ".join(CATS) + " |", "|---|" + "---|" * len(CATS)]
    for p in PROFS:
        if p not in tuned:
            continue
        m = R["main"]["%s/mid" % p]
        o = R["main"]["%s/oracle" % p]
        md.append("| %s | " % p + " | ".join("%.0f / %.0f" % (100 * m[c]["top1"][0], 100 * m[c]["top5"][0]) for c in CATS) + " |")
        md.append("| %s oracle | " % p + " | ".join("%.0f / %.0f" % (100 * o[c]["top1"][0], 100 * o[c]["top5"][0]) for c in CATS) + " |")
    md.append("")
    md.append("Row sizes (n): " + ", ".join("%s=%d" % (c, R["main"]["mouse/mid"][c]["n"][0]) for c in CATS if "mouse/mid" in R["main"]))

    # 3. noise sweep
    md += ["", "## 3. Noise sweep (top-1 / top-5, %), tuned config of the same profile", "",
           "| profile | " + " | ".join("k=%s" % k for k in ("0.25", "0.5", "1", "1.6", "2.5")) + " |", "|---|---|---|---|---|---|"]
    R["sweep"] = {}
    for p in PROFS:
        if p not in tuned:
            continue
        row = []
        for k in ("0.25", "0.5", "1", "1.6", "2.5"):
            m = trial(lex, abl_test, tuned[p], p, "k" + k, 1)["all"]
            R["sweep"]["%s/k%s" % (p, k)] = m
            row.append("%.0f / %.0f" % (100 * m["top1"][0], 100 * m["top5"][0]))
        md.append("| %s | " % p + " | ".join(row) + " |")
        print("sweep", p, flush=True)

    # 4. cross-profile transfer (config tuned on row, noise of column) at mid
    md += ["", "## 4. Transfer: config tuned for ROW profile, noise of COLUMN profile, level mid (top-1 / top-5)", "",
           "| tuned for \\ noise | " + " | ".join(p for p in PROFS if p in tuned) + " |", "|---|" + "---|" * len(tuned)]
    R["transfer"] = {}
    for tp in PROFS:
        if tp not in tuned:
            continue
        row = []
        for np_ in PROFS:
            if np_ not in tuned:
                continue
            m = trial(lex, abl_test, tuned[tp], np_, "mid", 1)["all"]
            R["transfer"]["%s->%s" % (tp, np_)] = m
            row.append("%.0f / %.0f" % (100 * m["top1"][0], 100 * m["top5"][0]))
        md.append("| %s | " % tp + " | ".join(row) + " |")
    row = []
    for np_ in PROFS:
        if np_ in tuned:
            m = trial(lex, abl_test, default_cfg, np_, "mid", 1)["all"]
            R["transfer"]["untuned->%s" % np_] = m
            row.append("%.0f / %.0f" % (100 * m["top1"][0], 100 * m["top5"][0]))
    md.append("| untuned SweepConfig() | " + " | ".join(row) + " |")
    print("transfer done", flush=True)

    # 5. ablations
    variants = [("full", {}), ("no shape channel", {"shape_weight": 0.0}), ("no location channel", {"loc_weight": 0.0}),
                ("no start/end term, flat alphas", {"end_weight": 0.0, "end_alpha": 1.0}), ("no prior", {"prior_weight": 0.0}),
                ("repeat_mode=ignore (no dwell)", {"repeat_mode": "ignore"}),
                ("2-key shape weight x1 (shape_short_scale=1)", {"shape_short_scale": 1.0}),
                ("2-key shape weight x0", {"shape_short_scale": 0.0}),
                ("cover_weight 4", {"cover_weight": 4.0}), ("loc_tolerance 0.25", {"loc_tolerance": 0.25}),
                ("N=16", {"n": 16}), ("N=24", {"n": 24}), ("N=32", {"n": 32}), ("N=48", {"n": 48}), ("N=64", {"n": 64}),
                ("prune_radius 0.8", {"prune_radius": 0.8}), ("prune_radius 1.0", {"prune_radius": 1.0}),
                ("prune_radius 2.0", {"prune_radius": 2.0}), ("no pruning (radius 99)", {"prune_radius": 99.0})]
    R["ablation"] = {}
    md += ["", "## 5. Ablations (one change at a time from the tuned config; level mid; %d test entries; top-1 / top-5 %%, then (w = frequency-weighted top-1 / top-5). Unweighted top-1 cannot see the prior: ordering inside a group of characters sharing one code does not change how many entries are first)" % len(abl_test), "",
           "| variant | " + " | ".join(p for p in ("mouse", "finger") if p in tuned) + " |", "|---|" + "---|" * 2]
    for name, kw in variants:
        row = []
        for p in ("mouse", "finger"):
            if p not in tuned:
                continue
            m = trial(lex, abl_test, tuned[p].replace(**kw), p, "mid", 1)["all"]
            R["ablation"]["%s|%s" % (name, p)] = m
            row.append("%.1f / %.1f (w %.1f / %.1f)" % (100 * m["top1"][0], 100 * m["top5"][0], 100 * m["w1"][0], 100 * m["w5"][0]))
        md.append("| %s | " % name + " | ".join(row) + " |")
        print("ablation", name, flush=True)

    # 5b. stress: large per-stroke bias (hand offset / pointer calibration), shape channel should help here
    md += ["", "## 5b. Stress test: large systematic per-stroke offset (sigma_bias 0.4 key widths; level mid; top-1 / top-5 %)", "",
           "| variant | finger + bias | mouse + bias |", "|---|---|---|"]
    R["bias_stress"] = {}
    for name, kw in (("full (tuned)", {}), ("no shape channel", {"shape_weight": 0.0}), ("shape x3", {"shape_weight": None}),
                     ("no location channel", {"loc_weight": 0.0})):
        row = []
        for p in ("finger", "mouse"):
            if p not in tuned:
                continue
            kw2 = dict(kw)
            if kw2.get("shape_weight", 0) is None:
                kw2["shape_weight"] = tuned[p].shape_weight * 3
            prof = replace(PROFILES[p], sigma_bias=0.4)
            m = run_trial(lex, abl_test, tuned[p].replace(**kw2), prof, "mid", seed=1)["all"]
            R["bias_stress"]["%s|%s" % (name, p)] = m
            row.append("%.1f / %.1f" % (100 * m["top1"], 100 * m["top5"]))
        md.append("| %s | " % name + " | ".join(row) + " |")
    print("bias stress done", flush=True)

    # 6. users who never dwell / always dwell, repeat codes only
    md += ["", "## 6. Repeated-letter codes ('hh'): effect of dwell behaviour (level mid; top-1 / top-5 on the `repeat` rows, %)", "",
           "| profile | user dwells 100% | 80% | 0% (never) | 0% and decoder ignores dwell |", "|---|---|---|---|---|"]
    R["dwell"] = {}
    for p in ("mouse", "finger"):
        if p not in tuned:
            continue
        row = []
        for pd in (1.0, 0.8, 0.0):
            prof = replace(PROFILES[p], p_dwell=pd)
            m = run_trial(lex, abl_test, tuned[p], prof, "mid", seed=1)["repeat"]
            R["dwell"]["%s|%s" % (p, pd)] = m
            row.append("%.0f / %.0f" % (100 * m["top1"], 100 * m["top5"]))
        prof = replace(PROFILES[p], p_dwell=0.0)
        m = run_trial(lex, abl_test, tuned[p].replace(repeat_mode="ignore"), prof, "mid", seed=1)["repeat"]
        row.append("%.0f / %.0f" % (100 * m["top1"], 100 * m["top5"]))
        md.append("| %s | " % p + " | ".join(row) + " |")
    print("dwell done", flush=True)

    # 7. lexicon size
    md += ["", "## 7. Lexicon size (random character subsets; level mid; top-1 / top-5 %)", "",
           "| entries | " + " | ".join(p for p in ("mouse", "finger") if p in tuned) + " |", "|---|---|---|"]
    R["lexsize"] = {}
    chars = sorted({e[1] for e in lex})
    random.Random(4).shuffle(chars)
    for frac in (0.1, 0.25, 0.5, 1.0):
        keep = set(chars[: int(len(chars) * frac)])
        sub = [e for e in lex if e[1] in keep]
        sub_test = [e for e in sub if split_of(e[1]) == "test"]
        sub_test = sample(sub_test, 3000, 3)
        row = []
        for p in ("mouse", "finger"):
            if p not in tuned:
                continue
            m = run_trial(sub, sub_test, tuned[p], p, "mid", seed=1)["all"]
            R["lexsize"]["%d|%s" % (len(sub), p)] = m
            row.append("%.1f / %.1f" % (100 * m["top1"], 100 * m["top5"]))
        md.append("| %d | " % len(sub) + " | ".join(row) + " |")
    print("lexsize done", flush=True)

    # 8. phone layout (key pitch 1.3 x width) robustness
    md += ["", "## 8. Layout robustness: phone-like layout (row pitch 1.3 key widths) for both simulator and decoder (top-1 / top-5 %)", "",
           "| profile | mid | high |", "|---|---|---|"]
    R["phone_layout"] = {}
    for p in ("mouse", "finger"):
        if p not in tuned:
            continue
        row = []
        for lv in ("mid", "high"):
            m = run_trial(lex, abl_test, tuned[p], p, lv, seed=1, layout="phone")["all"]
            R["phone_layout"]["%s/%s" % (p, lv)] = m
            row.append("%.1f / %.1f" % (100 * m["top1"], 100 * m["top5"]))
        md.append("| %s | " % p + " | ".join(row) + " |")

    # 9. latency (single process, nothing else running)
    md += ["", "## 9. Latency, pure Python 3.12, one core (ms per decode, 300 mid-noise mouse paths)", "",
           "| config | mean | p50 | p95 | max |", "|---|---|---|---|---|"]
    R["latency"] = {}
    items = sample(test, 300, 9)
    base = tuned.get("mouse", default_cfg)
    for name, cfg in (("bucket index (default), N=%d" % base.n, base), ("full scan, no index", base.replace(use_index=False)),
                      ("bucket index, N=16", base.replace(n=16)), ("bucket index, prune_radius 1.0", base.replace(prune_radius=1.0)), ("bucket index, N=48", base.replace(n=48)),
                      ("bucket index, prune_radius 2.5", base.replace(prune_radius=2.5))):
        t0 = time.perf_counter()
        Lexicon(lex, None, cfg.n)
        build = time.perf_counter() - t0
        L = latency(lex, cfg, "mouse", "mid", items)
        R["latency"][name] = dict(L, build_s=build)
        md.append("| %s | %.1f | %.1f | %.1f | %.1f |" % (name, L["mean_ms"], L["p50_ms"], L["p95_ms"], L["max_ms"]))
    md.append("")
    md.append("Lexicon build (templates + index) %.2f s one-time." % R["latency"]["bucket index (default), N=%d" % base.n]["build_s"])

    with open(os.path.join(RES, "final.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    with open(os.path.join(RES, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("wrote REPORT.md")


if __name__ == "__main__":
    main()
