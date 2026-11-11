"""Before / after report for the spur / backtrack tolerance -> sweep/results/SPUR.md and spur.json (SYNTHETIC sweeps).
  python3 -m sweep.report_spur [--table T] [--essay E]
Noise class: `backtrack_prob` (simulate.py): at each interior waypoint the path goes back toward the previous waypoint before continuing
(y h y j m n b v c for yhmbc). Level mid; held-out characters / words; 'before' = align_weight 0, 'after' = defaults."""
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
from sweep.evaluate import DEFAULT_TABLE, entry_seed, latency, load_entries, run_trial, sample, split_entries  # noqa: E402
from sweep.evaluate_words import DEFAULT_ESSAY, load_words, run_words, stratified  # noqa: E402
from sweep.keyboard import default_layout  # noqa: E402
from sweep.make_vectors import polyline_path  # noqa: E402
from sweep.simulate import PROFILES  # noqa: E402
from sweep.words import WordConfig, WordLexicon, main_codes  # noqa: E402

RES = os.path.join(_ROOT, "sweep", "results")
RATES = (0.0, 0.15, 0.4)


def pct(x):
    return "%.1f" % (100 * x)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--essay", default=DEFAULT_ESSAY)
    a = ap.parse_args(argv)
    L = default_layout()
    chars = load_entries(a.table, min_len=1)
    ents = [e for e in chars if len(e[0]) >= 2]
    test = split_entries(ents, "test")
    R = {}
    md = ["# Spur / backtrack tolerance: before and after (SYNTHETIC sweeps)", "",
          "Noise class `backtrack_prob`: at each interior waypoint the simulated path goes back toward the previous waypoint (70-100%% of the way) "
          "before continuing, e.g. y-h-y-j-m-n-b-v-c for yhmbc. Rates: 0 (none), 0.15, 0.4 per interior waypoint, on top of the profile's normal noise at level mid. "
          "Before = `align_weight` 0; after = defaults (`align_weight` %.2f, `align_gate` %.2f, `align_ins` %.2f, `hit_radius` %.2f, rerank of the best %d). "
          "Held-out test characters (%d) and words." % (SweepConfig().align_weight, SweepConfig().align_gate, SweepConfig().align_ins,
                                                       SweepConfig().hit_radius, SweepConfig().align_top, len(test)), ""]
    md += ["## Characters (top-1 / top-5 / frequency-weighted top-1, %)", "", "| profile | backtrack rate | before | after |", "|---|---|---|---|"]
    after = SweepConfig()
    before = after.replace(align_weight=0.0)
    for prof in ("mouse", "touchpad", "finger"):
        for rate in RATES:
            pr = replace(PROFILES[prof], backtrack_prob=rate)
            row = []
            for tag, cfg in (("before", before), ("after", after)):
                r = run_trial(ents, test, cfg, pr, "mid", seed=1)["all"]
                R["chars|%s|%.2f|%s" % (prof, rate, tag)] = r
                row.append("%s / %s / %s" % (pct(r["top1"]), pct(r["top5"]), pct(r["w1"])))
            md.append("| %s | %.2f | %s | %s |" % (prof, rate, row[0], row[1]))
        print("chars", prof, flush=True)
    # the literal example
    md += ["", "## The literal example (noiseless polylines through the keys, chars decoder)", "", "| path | before: top-3 codes | after: top-3 codes |", "|---|---|---|"]
    for keys in ("yhyjmnbvc", "yhyhmbc", "yuyjmnbc", "yhmbc", "yhjmnbvc", "yhmnbvc"):
        row = []
        for cfg in (before, after):
            d = SweepDecoder(Lexicon(ents, L, cfg.n), cfg)
            r = d.decode(polyline_path(keys, L), top_k=12)
            codes = []
            for x in r:
                if x[1] not in codes:
                    codes.append(x[1])
            row.append(" ".join(codes[:3]))
        md.append("| %s | %s | %s |" % (keys, row[0], row[1]))
    # words
    words = load_words(a.essay, 100)
    mc = main_codes(chars)
    items = stratified(words, mc, "test", 100, 5)
    wafter = WordConfig()
    wbefore = wafter.replace(align_weight=0.0)
    lex = WordLexicon(chars, words, L, wafter)
    md += ["", "## Words (243k words + chars; mixed continuous / dwell / lift boundaries; top-1 / top-5 %)", "", "| profile | backtrack rate | before | after |", "|---|---|---|---|"]
    for prof in ("mouse", "finger"):
        for rate in RATES:
            pr = replace(PROFILES[prof], backtrack_prob=rate)
            row = []
            for tag, cfg in (("before", wbefore), ("after", wafter)):
                r = run_words(lex, cfg, items, pr, "mid", seed=1, mc=mc)["all"]
                R["words|%s|%.2f|%s" % (prof, rate, tag)] = r
                row.append("%s / %s" % (pct(r["top1"]), pct(r["top5"])))
            md.append("| %s | %.2f | %s | %s |" % (prof, rate, row[0], row[1]))
        print("words", prof, flush=True)
    # single characters through the unified word lexicon
    # latency
    md += ["", "## Latency (pure Python, one core, mean / p95 ms)", "", "| decoder | before | after |", "|---|---|---|"]
    items_c = sample(test, 300, 9)
    row = []
    for cfg in (before, after):
        Lt = latency(ents, cfg, "mouse", "mid", items_c)
        row.append("%.1f / %.1f" % (Lt["mean_ms"], Lt["p95_ms"]))
    md.append("| single character | %s | %s |" % (row[0], row[1]))
    from sweep.simulate import generate_word
    from sweep.words import WordDecoder
    paths = [generate_word([mc[c] for c in t], L, PROFILES["mouse"], 1.0, random.Random(entry_seed(3, t, "lat")), "continuous") for t, f in items[::6]]
    row = []
    for cfg in (wbefore, wafter):
        dd = WordDecoder(lex, cfg)
        ts = []
        for pts, lifts in paths:
            t0 = time.perf_counter()
            dd.decode(pts, lifts, top_k=5)
            ts.append((time.perf_counter() - t0) * 1000)
        ts.sort()
        row.append("%.1f / %.1f" % (sum(ts) / len(ts), ts[int(len(ts) * 0.95)]))
    md.append("| word (243k) | %s | %s |" % (row[0], row[1]))
    with open(os.path.join(RES, "spur.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    with open(os.path.join(RES, "SPUR.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("wrote SPUR.md")


if __name__ == "__main__":
    main()
