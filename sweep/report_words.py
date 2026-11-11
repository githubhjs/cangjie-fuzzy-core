"""Word-level report on SYNTHETIC sweeps -> sweep/results/WORDS.md and words.json.   python3 -m sweep.report_words [--quick]"""
import argparse
import json
import os
import random
import resource
import sys
import time
from dataclasses import replace

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.decoder import Lexicon, SweepConfig, SweepDecoder  # noqa: E402
from sweep.evaluate import DEFAULT_TABLE, entry_seed, load_entries, level_value, table_sha  # noqa: E402
from sweep.evaluate_words import DEFAULT_ESSAY, load_words, run_words, stratified  # noqa: E402
from sweep.keyboard import default_layout  # noqa: E402
from sweep.make_vectors import polyline_path  # noqa: E402
from sweep.simulate import PROFILES, generate_word  # noqa: E402
from sweep.words import CharSegmenter, WordConfig, WordDecoder, WordLexicon, main_codes  # noqa: E402

RES = os.path.join(_ROOT, "sweep", "results")
L = default_layout()
OWNER = [("顏值", "yhmnbvc ojhbnm"), ("頻率", "yhjmnbvc yuiokjhj")]


def literal(path_str, mode, jitter=0.0, rng=None):
    """The owner's literal key sequence as a stroke. mode: continuous | lift | dwell (space = boundary). Returns (points, lifts)."""
    a, b = path_str.split(" ")
    pa, pb = polyline_path(a, L), polyline_path(b, L)
    if mode == "lift":
        t0 = pa[-1][2] + 250.0
        pts = pa + [(x, y, t + t0) for (x, y, t) in pb]
        lifts = [len(pa) - 1]
    else:
        keys = a + b
        pts = polyline_path(keys, L)
        lifts = []
        if mode == "dwell":
            cut = len(polyline_path(a, L)) - 1
            hold = [(pts[cut][0], pts[cut][1], pts[cut][2] + 10.0 * i) for i in range(1, 36)]
            rest = [(x, y, t + 350.0) for (x, y, t) in pts[cut + 1:]]
            pts = pts[:cut + 1] + hold + rest
    if jitter > 0:  # hand wobble: two slow sinusoids per axis (0.7-2.5 Hz) of amplitude  key widths, plus 0.02 sample noise
        import math
        fx1, fx2, fy1, fy2 = (rng.uniform(0.7, 2.5) for _ in range(4))
        px1, px2, py1, py2 = (rng.uniform(0, 6.283) for _ in range(4))
        pts = [(x + jitter * 0.5 * (math.sin(6.283 * fx1 * t / 1000 + px1) + math.sin(6.283 * fx2 * t / 1000 + px2)) + rng.gauss(0, 0.02),
                y + jitter * 0.5 * (math.sin(6.283 * fy1 * t / 1000 + py1) + math.sin(6.283 * fy2 * t / 1000 + py2)) + rng.gauss(0, 0.02), t)
               for (x, y, t) in pts]
    return pts, lifts


def pct(x):
    return "%.1f" % (100 * x)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--essay", default=DEFAULT_ESSAY)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    cfgpath = os.path.join(RES, "defaults_words.json")
    cfg = WordConfig(**json.load(open(cfgpath))) if os.path.exists(cfgpath) else WordConfig()
    chars = load_entries(a.table, min_len=1)
    mc = main_codes(chars)
    words100 = load_words(a.essay, 100)
    per_cell = 40 if a.quick else 100
    R = {"table_sha256": table_sha(a.table), "essay_lines_ge100": len(words100), "config": cfg.to_dict()}
    md = ["# Word-level sweep: results on SYNTHETIC sweeps", "",
          "Table sha256 `%s`. Words = essay.txt entries (word<TAB>freq) of 2-4 characters whose characters all have a Cangjie 3 code (main = shortest code). "
          "Test words (hash split disjoint from tuning), stratified by length (2/3/4) x frequency band (1k-3k, 3k-10k, >=10k), %d per cell. "
          "Boundary modes mixed: 50%% continuous (one stroke, nothing marks the boundary), 25%% dwell on the boundary key, 25%% finger lift. "
          "Candidates: words with freq >= 100 plus every single character (words+chars)." % (R["table_sha256"], per_cell), ""]
    t0 = time.time()
    lex = WordLexicon(chars, words100, L, cfg)
    build = time.time() - t0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    R["lexicon"] = {"words": lex.n_words, "templates": len(lex.templates), "build_s": build, "peak_rss_mb": rss}
    items = stratified(words100, mc, "test", per_cell, 5)
    R["n_test_words"] = len(items)

    # 1. accuracy
    md += ["## 1. Word accuracy (tuned defaults, words + chars candidates)", "", "| profile | level | words top-1 | top-3 | top-5 | chars right in top-1 (per position) | continuous | dwell | lift | len 2 | len 3 | len 4 |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    R["accuracy"] = {}
    for prof in ("mouse", "touchpad", "finger", "touchscreen"):
        for lv in ("low", "mid", "high"):
            r = run_words(lex, cfg, items, prof, lv, seed=1, mc=mc)
            R["accuracy"]["%s/%s" % (prof, lv)] = r
            md.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                prof, lv, pct(r["all"]["top1"]), pct(r["all"]["top3"]), pct(r["all"]["top5"]), pct(r["char_pos_acc_top1"]),
                *(pct(r[k]["top1"]) for k in ("mode_continuous", "mode_dwell", "mode_lift", "len2", "len3", "len4"))))
        print("acc", prof, flush=True)
    md += ["", "Frequency bands (top-1 / top-5, %), mouse and finger at mid:", "", "| profile | 1k-3k | 3k-10k | >=10k |", "|---|---|---|---|"]
    for prof in ("mouse", "finger"):
        r = R["accuracy"]["%s/mid" % prof]
        md.append("| %s | " % prof + " | ".join("%s / %s" % (pct(r["freq_" + b]["top1"]), pct(r["freq_" + b]["top5"])) for b in ("1k-3k", "3k-10k", ">=10k")) + " |")

    # 2. chars vs words, and words-only vs words+chars
    md += ["", "## 2. Characters vs words, and what adding words does to single-character sweeps", ""]
    lex_words_only = WordLexicon(chars, words100, L, cfg, with_chars=False)
    lex_chars_only = WordLexicon(chars, [], L, cfg, with_chars=True)
    rng = random.Random(8)
    ent2 = [e for e in chars if len(e[0]) >= 2]
    char_items = [(e[1], e[0]) for e in rng.sample(ent2, 1500 if not a.quick else 500)]
    R["chars_vs_words"] = {}
    md += ["| candidates | word sweeps top-1 / top-5 (mouse mid) | word sweeps (finger mid) | single-character sweeps top-1 / top-5 (mouse mid) | (finger mid) |", "|---|---|---|---|---|"]
    for name, lx in (("words only", lex_words_only), ("chars only", lex_chars_only), ("words + chars", lex)):
        row = []
        for prof in ("mouse", "finger"):
            if lx is lex_chars_only:
                row.append("n/a")
            else:
                r = run_words(lx, cfg, items, prof, "mid", seed=1, mc=mc)["all"]
                row.append("%s / %s" % (pct(r["top1"]), pct(r["top5"])))
                R["chars_vs_words"]["%s|words|%s" % (name, prof)] = r
        for prof in ("mouse", "finger"):
            if lx is lex_words_only:
                row.append("n/a")
            else:
                r = run_words(lx, cfg, char_items, prof, "mid", seed=1, kind="char", mc=mc)["all"]
                row.append("%s / %s" % (pct(r["top1"]), pct(r["top5"])))
                R["chars_vs_words"]["%s|chars|%s" % (name, prof)] = r
        md.append("| %s | " % name + " | ".join([row[0], row[1], row[2], row[3]]) + " |")
    print("chars vs words", flush=True)

    # 3. lexicon size (word sweeps of frequent words, growing candidate set)
    md += ["", "## 3. Lexicon size (same test words, all with freq >= 1000; candidate words = essay words with freq >= threshold, plus chars)", "",
           "| min freq | words in lexicon | mouse mid top-1 / top-5 | finger mid top-1 / top-5 | mouse high | finger high |", "|---|---|---|---|---|---|"]
    R["lexsize"] = {}
    test1k = [it for it in items if it[1] >= 1000]
    for mf in (3000, 1000, 300, 100, 30):
        wl = load_words(a.essay, mf)
        lx = WordLexicon(chars, wl, L, cfg)
        row = []
        for prof, lv in (("mouse", "mid"), ("finger", "mid"), ("mouse", "high"), ("finger", "high")):
            its = [it for it in test1k if it[1] >= mf]
            r = run_words(lx, cfg, its, prof, lv, seed=1, mc=mc)["all"]
            R["lexsize"]["%d|%s/%s" % (mf, prof, lv)] = r
            row.append("%s / %s" % (pct(r["top1"]), pct(r["top5"])))
        md.append("| %d | %d | %s |" % (mf, lx.n_words, " | ".join(row)))
        print("lexsize", mf, flush=True)

    # 4. owner cases
    md += ["", "## 4. The two owner cases", ""]
    dec = WordDecoder(lex, cfg)
    R["owner"] = {}
    md += ["Exact literal paths (key sequences from the brief, space = boundary), top-5 and score:", "", "| target | boundary | top-5 |", "|---|---|---|"]
    for target, s in OWNER:
        for mode in ("continuous", "lift", "dwell"):
            pts, lifts = literal(s, mode)
            r = dec.decode(pts, lifts, top_k=5)
            R["owner"]["%s|%s|exact" % (target, mode)] = [(x[0], round(x[2], 2)) for x in r]
            md.append("| %s (`%s`) | %s | %s |" % (target, s, mode, ", ".join("%s %.1f" % (x[0], x[2]) for x in r)))
    md += ["", "1000 noisy variants each (seeded). A: generated from the intended codes (yhmbc+ojbm, yhmbc+yioj) with the simulator; "
           "B: the owner's literal slip path with a slow hand wobble added (amplitude in key widths, per-sample noise 0.02). Top-1 / top-5 %.", "",
           "| target | variant | profile / level | continuous | lift | dwell |", "|---|---|---|---|---|---|"]
    n = 200 if a.quick else 1000
    for target, s in OWNER:
        codes = [mc[c] for c in target]
        for prof, lv in (("mouse", "mid"), ("mouse", "high"), ("finger", "mid"), ("touchscreen", "mid")):
            row = []
            for mode in ("continuous", "lift", "dwell"):
                h1 = h5 = 0
                for i in range(n):
                    rng = random.Random(entry_seed(i, target, mode))
                    pts, lifts = generate_word(codes, L, PROFILES[prof], level_value(lv), rng, mode)
                    r = [x[0] for x in dec.decode(pts, lifts, top_k=5)]
                    h1 += r[:1] == [target]
                    h5 += target in r
                row.append("%s / %s" % (pct(h1 / n), pct(h5 / n)))
                R["owner"]["%s|gen|%s/%s|%s" % (target, prof, lv, mode)] = (h1 / n, h5 / n)
            md.append("| %s | A generated | %s / %s | %s |" % (target, prof, lv, " | ".join(row)))
        for jit in (0.1, 0.2, 0.4):
            row = []
            for mode in ("continuous", "lift", "dwell"):
                h1 = h5 = 0
                for i in range(n):
                    rng = random.Random(entry_seed(i, target, "j" + mode))
                    pts, lifts = literal(s, mode, jitter=jit, rng=rng)
                    r = [x[0] for x in dec.decode(pts, lifts, top_k=5)]
                    h1 += r[:1] == [target]
                    h5 += target in r
                row.append("%s / %s" % (pct(h1 / n), pct(h5 / n)))
                R["owner"]["%s|jit%.1f|%s" % (target, jit, mode)] = (h1 / n, h5 / n)
            md.append("| %s | B literal + wobble %.1f key widths | - | %s |" % (target, jit, " | ".join(row)))
    print("owner done", flush=True)

    # 5. latency
    md += ["", "## 5. Latency, pure Python 3.12, one core (ms per decode; mid-noise mouse word sweeps)", "", "| lexicon | mean | p50 | p95 | max |", "|---|---|---|---|---|"]
    R["latency"] = {}
    sample = items[::max(1, len(items) // 150)]
    for name, wl in (("words >= 1000 (%d)" % len(load_words(a.essay, 1000)), load_words(a.essay, 1000)), ("words >= 100 (%d)" % lex.n_words, words100)):
        lx = lex if wl is words100 else WordLexicon(chars, wl, L, cfg)
        dd = WordDecoder(lx, cfg)
        paths = []
        for text, f in sample:
            pts, lifts = generate_word([mc[c] for c in text], L, PROFILES["mouse"], 1.0, random.Random(entry_seed(3, text, "lat")), "continuous")
            paths.append((pts, lifts))
        ts = []
        for pts, lifts in paths:
            t = time.perf_counter()
            dd.decode(pts, lifts, top_k=5)
            ts.append((time.perf_counter() - t) * 1000)
        ts.sort()
        R["latency"][name] = {"mean": sum(ts) / len(ts), "p50": ts[len(ts) // 2], "p95": ts[int(len(ts) * 0.95)], "max": ts[-1]}
        md.append("| %s | %.1f | %.1f | %.1f | %.1f |" % (name, sum(ts) / len(ts), ts[len(ts) // 2], ts[int(len(ts) * 0.95)], ts[-1]))
    md.append("")
    md.append("Build: %.1f s, %d templates (%d words); peak RSS of this process %.0f MB (includes the table and lists; the Python object overhead is far larger than a Kotlin float array would be)." % (
        build, len(lex.templates), lex.n_words, rss))

    # 6. segmentation alternative
    md += ["", "## 6. Best per-character segmentation (no word lexicon, DP over split points, single-character decoder)", ""]
    seg = CharSegmenter(SweepDecoder(Lexicon([e for e in chars if len(e[0]) >= 2], L, 24), SweepConfig()))
    R["segmentation"] = {}
    md += ["| profile / level | boundary | exact text match | right number of characters | ms per call (mean) |", "|---|---|---|---|---|"]
    sub = items[::max(1, len(items) // (40 if a.quick else 120))]
    for prof, lv in (("mouse", "mid"), ("finger", "mid")):
        for mode in ("continuous", "lift", "dwell"):
            ok = okn = 0
            tt = 0.0
            for text, f in sub:
                rng = random.Random(entry_seed(5, text, mode))
                pts, lifts = generate_word([mc[c] for c in text], L, PROFILES[prof], level_value(lv), rng, mode)
                t = time.perf_counter()
                r = seg.segment(pts, lifts)
                tt += time.perf_counter() - t
                if r:
                    ok += r[0] == text
                    okn += len(r[0]) == len(text)
            R["segmentation"]["%s/%s|%s" % (prof, lv, mode)] = (ok / len(sub), okn / len(sub), 1000 * tt / len(sub))
            md.append("| %s / %s | %s | %s | %s | %.0f |" % (prof, lv, mode, pct(ok / len(sub)), pct(okn / len(sub)), 1000 * tt / len(sub)))
        print("seg", prof, flush=True)

    with open(os.path.join(RES, "words.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    with open(os.path.join(RES, "WORDS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("wrote WORDS.md")


if __name__ == "__main__":
    main()
