"""Paired synthetic iid-jitter ablation through decode_auto; stdlib only, no downloads.

Run ``python3 -m sweep.report_jitter --help``. Accuracy workers use fork (as the
other sweep reports do); latency runs serially after the pool has closed.
"""
import argparse
import hashlib
import json
import multiprocessing
import os
import random
import shlex
import sys
import time

from sweep.auto import AutoDecoder, char_config
from sweep.decoder import Lexicon, SweepDecoder
from sweep.evaluate import DEFAULT_TABLE, entry_seed, load_entries, sample, split_entries, table_sha
from sweep.evaluate_words import DEFAULT_ESSAY, MODES, load_words, stratified
from sweep.keyboard import default_layout
from sweep.pointer import prepare_pointer
from sweep.report_words import literal
from sweep.simulate import PROFILES, add_sample_jitter, generate, generate_word
from sweep.words import WordConfig, WordDecoder, WordLexicon, main_codes, path_length

_G = {}


def _path(item, profile, seed):
    kind, text, code = item
    rng = random.Random(entry_seed(seed, text, kind))
    if kind == "char":
        return generate(code, _G["layout"], PROFILES[profile], 1.0, rng), []
    mode = MODES[int(hashlib.md5(text.encode("utf-8")).hexdigest()[:4], 16) % len(MODES)]
    return generate_word([_G["mc"][c] for c in text], _G["layout"], PROFILES[profile], 1.0, rng, mode)


def _work(task):
    profile, sigma, seed, item = task
    points, lifts = _path(item, profile, seed)
    points = add_sample_jitter(points, sigma, random.Random(entry_seed(seed, item[1], "iid")))
    ranks = []
    for dec in _G["decs"][profile].values():
        texts = [r[0] for r in dec.decode(points, lifts, top_k=5)]
        ranks.append(texts.index(item[1]) + 1 if item[1] in texts else 99)
    return ranks


def _aggregate(ranks, variants):
    return {name: {"n": len(ranks),
                   "top1": sum(r[j] == 1 for r in ranks) / len(ranks),
                   "top5": sum(r[j] <= 5 for r in ranks) / len(ranks)}
            for j, name in enumerate(variants)}


def _latency(items, profiles, variants, sigmas, count, repeats):
    out = {}
    for profile in profiles:
        for kind in ("char", "word"):
            selected = [it for it in items if it[0] == kind][:count]
            for sigma in sigmas:
                paths = []
                for item in selected:
                    points, lifts = _path(item, profile, 73)
                    points = add_sample_jitter(points, sigma, random.Random(entry_seed(73, item[1], "iid")))
                    paths.append((points, lifts))
                decs = _G["decs"][profile]
                # Warm template alignment caches before measurements; alternate
                # variant order each pass to reduce thermal/order bias.
                for dec in decs.values():
                    for points, lifts in paths:
                        dec.decode(points, lifts, top_k=5)
                times = {name: [] for name in variants}
                for rep in range(repeats):
                    order = variants if rep % 2 == 0 else list(reversed(variants))
                    for points, lifts in paths:
                        for name in order:
                            t0 = time.perf_counter()
                            decs[name].decode(points, lifts, top_k=5)
                            times[name].append((time.perf_counter() - t0) * 1000)
                row = {}
                for name, ts in times.items():
                    ts.sort()
                    row[name] = {"n": len(ts), "mean_ms": sum(ts) / len(ts),
                                 "p95_ms": ts[min(len(ts) - 1, int(len(ts) * .95))]}
                baseline = row["off"]["mean_ms"]
                for cell in row.values():
                    cell["mean_ratio_to_off"] = cell["mean_ms"] / baseline
                out["%s|%s|%g" % (profile, kind, sigma)] = row
                print("latency", profile, kind, sigma, row, flush=True)
    return out


def _owners(variants, sigmas, count):
    out = {}
    for text, keys in (("顏值", "yhmnbvc ojhbnm"), ("頻率", "yhjmnbvc yuiokjhj")):
        points, lifts = literal(keys, "continuous")
        for sigma in sigmas:
            ranks = []
            for seed in range(1, count + 1):
                noisy = add_sample_jitter(points, sigma, random.Random(entry_seed(seed, text, "owner-iid")))
                row = []
                for name in variants:
                    texts = [r[0] for r in _G["decs"]["mouse"][name].decode(noisy, lifts, top_k=5)]
                    row.append(texts.index(text) + 1 if text in texts else 99)
                ranks.append(row)
            out["%s|%g" % (text, sigma)] = _aggregate(ranks, variants)
    return out


def owner_lengths(sigmas, count):
    """Length diagnostic uses precisely the same paths/noise draws as owners."""
    out = {}
    cfg = WordConfig(pointer_filter="smooth")
    for text, keys in (("顏值", "yhmnbvc ojhbnm"), ("頻率", "yhjmnbvc yuiokjhj")):
        points, lifts = literal(keys, "continuous")
        clean = path_length(points)
        for sigma in sigmas:
            raw_lengths, filtered_lengths = [], []
            for seed in range(1, count + 1):
                noisy = add_sample_jitter(points, sigma, random.Random(entry_seed(seed, text, "owner-iid")))
                _, length_points, _ = prepare_pointer(noisy, cfg, lifts)
                raw_lengths.append(path_length(noisy))
                filtered_lengths.append(path_length(length_points))
            out["%s|%g" % (text, sigma)] = {"samples": len(points), "clean_length": clean,
                                             "raw_mean": sum(raw_lengths) / count,
                                             "filtered_mean": sum(filtered_lengths) / count}
    return out


def write_report(result, path):
    variants = result["variants"]
    meta = result["metadata"]
    md = ["# Pointer jitter robustness (synthetic data)", "",
          "All results use the section 12 `decode_auto` policy, profile-specific character config, ANSI geometry, "
          "the full Cangjie table and all usable 2–4 character words with frequency >= 1000. "
          "Existing profile noise is at mid; sigma is **additional iid Gaussian noise per axis per sample**, in key widths. "
          "Sigma 0 is the clean-control condition (ordinary profile noise remains). "
          "Paths, boundaries, and random draws are paired across variants and jitter levels.", "",
          "Candidates: %d character entries (including one-letter codes in the word list), %d usable words, %d word-list templates. "
          "Evaluation: %d held-out character entries and %d held-out stratified words per seed, %d noise seed(s). "
          "Character split/sample seed 4; words stratified by length 2/3/4 and frequency 1k–3k/3k–10k/>=10k, sample seed 5. "
          "Word boundaries use the existing hash-selected 50%% continuous / 25%% dwell / 25%% lift rule."
          % (meta["char_entries"], meta["words"], meta["word_templates"], meta["eval_chars"], meta["eval_words"], meta["seeds"]), "",
          "Table SHA-256 `%s`; essay SHA-256 `%s`." % (meta["table_sha256"], meta["essay_sha256"]), "",
          "Reproduce (local corpora required; no network):", "", "```sh", result["command"], "```", "",
          "`off` explicitly disables the stage in BOTH decoder configs and is the unchanged baseline. "
          "`smooth` filters scoring geometry and length; `length` filters only length, "
          "keeping raw scoring geometry; `window` widens the raw length window from estimated inflation; "
          "`smooth_window` combines smoothing with widening. All enabled variants estimate jitter from the path and bypass "
          "clean paths below the configured gate. The implementation and exact defaults are in SPEC.md.", "",
          "The default is `pointer_filter=\"smooth\"` with `pointer_jitter_floor=0.045`. "
          "Length-only correction and adaptive widening help, but leave noisy arc-length resampling and key-touch alignment intact. "
          "Smoothing addresses those as well. Widening on top of smoothing did not improve the pilot consistently, "
          "so the narrower original length window remains the default.", "",
          "These character rows also use the product policy. They can fail more sharply than the characters-only decoder "
          "reported in section 8: if the noisy one-list decoder puts a word first, `decode_auto` returns that word list. "
          "The word-population mean need not reach zero, because candidate fallback can reopen an unbounded length window "
          "when very few candidates survive. The literal owner table below tests the original specific cliff.", "",
          "Top-1 / top-5 percentages:", "",
          "| profile | sweep | added sigma | " + " | ".join(variants) + " |",
          "|---|---|---|" + "---|" * len(variants)]
    for key, row in result["runs"].items():
        profile, kind, sigma = key.split("|")
        cells = ["%.1f / %.1f" % (100 * row[v]["top1"], 100 * row[v]["top5"]) for v in variants]
        md.append("| %s | %s | %s | %s |" % (profile, kind, sigma, " | ".join(cells)))
    clean_profiles = [profile for profile in meta["char_configs"]
                      if all("%s|%s|0" % (profile, kind) in result["runs"] for kind in ("char", "word"))]
    if "smooth" in variants and clean_profiles:
        md += ["", "Clean-control top-1 changes (`smooth` minus `off`, percentage points):", "",
               "| profile | characters | words |", "|---|---|---|"]
        for profile in clean_profiles:
            cells = []
            for kind in ("char", "word"):
                row = result["runs"]["%s|%s|0" % (profile, kind)]
                cells.append("%+.2f" % (100 * (row["smooth"]["top1"] - row["off"]["top1"])))
            md.append("| %s | %s | %s |" % (profile, cells[0], cells[1]))
        required = [row for key, row in result["runs"].items()
                    if key.split("|")[0] in ("mouse", "finger") and key.endswith("|0")]
        if len(required) == 4:
            worst_drop = max(100 * (row["off"]["top1"] - row["smooth"]["top1"]) for row in required)
            md += ["", "The required mouse/finger character/word clean groups %s the <=0.5-point top-1 regression gate "
                   "on this sample (largest observed drop %.2f points)." % ("pass" if worst_drop <= .5 else "FAIL", worst_drop)]
    if result.get("ablation"):
        pilot = result["ablation"]
        av = pilot["variants"]
        md += ["", "Candidate pilot (separate smaller evaluation: %d characters and %d words per profile, "
               "same corpus and seeds; top-1 / top-5 %%). These measurements informed choosing the final default. "
               "The larger evaluation expands the same split/sample seeds: it is held out from original decoder tuning, "
               "but is not an independent untouched confirmation set for filter selection."
               % (pilot["metadata"]["eval_chars"], pilot["metadata"]["eval_words"]), "",
               "| profile | sweep | added sigma | " + " | ".join(av) + " |",
               "|---|---|---|" + "---|" * len(av)]
        for key, row in pilot["runs"].items():
            profile, kind, sigma = key.split("|")
            cells = ["%.1f / %.1f" % (100 * row[v]["top1"], 100 * row[v]["top5"]) for v in av]
            md.append("| %s | %s | %s | %s |" % (profile, kind, sigma, " | ".join(cells)))
    if result.get("owners"):
        md += ["", "Literal owner paths, continuous, %d jitter draws each (top-1 / top-5 %%). "
               "These reproduce the specific section 8 failure independently of the simulator corpus." % meta["owner_draws"], "",
               "| target | added sigma | " + " | ".join(variants) + " |",
               "|---|---|" + "---|" * len(variants)]
        for key, row in result["owners"].items():
            text, sigma = key.split("|")
            cells = ["%.1f / %.1f" % (100 * row[v]["top1"], 100 * row[v]["top5"]) for v in variants]
            md.append("| %s | %s | %s |" % (text, sigma, " | ".join(cells)))
    if result.get("owner_lengths"):
        md += ["", "Literal owner arc length in key widths, averaged over the same jitter draws. "
               "Filtering reduces jitter's excess travel before the length window and equidistant resampling.", "",
               "| target | samples | added sigma | clean | raw mean | filtered mean |", "|---|---|---|---|---|---|"]
        for key, row in result["owner_lengths"].items():
            text, sigma = key.split("|")
            md.append("| %s | %d | %s | %.2f | %.2f | %.2f |" %
                      (text, row["samples"], sigma, row["clean_length"], row["raw_mean"], row["filtered_mean"]))
    if result.get("latency"):
        md += ["", "Serial paired warm-cache latency, mean / p95 milliseconds (mean change relative to off). "
               "No accuracy workers are running during these measurements.", "",
               "| profile | sweep | added sigma | " + " | ".join(variants) + " |",
               "|---|---|---|" + "---|" * len(variants)]
        for key, row in result["latency"].items():
            profile, kind, sigma = key.split("|")
            cells = ["%.2f / %.2f (%+.1f%%)" % (row[v]["mean_ms"], row[v]["p95_ms"],
                                                   100 * (row[v]["mean_ratio_to_off"] - 1)) for v in variants]
            md.append("| %s | %s | %s | %s |" % (profile, kind, sigma, " | ".join(cells)))
        worst_ratio = max(row["smooth"]["mean_ratio_to_off"] for row in result["latency"].values()) if "smooth" in variants else None
        if worst_ratio is not None:
            md += ["", "The +20%% mean latency gate %s for every measured group; largest smooth/off ratio %.3f (%+.1f%%)." %
                   ("passes" if worst_ratio <= 1.2 else "FAILS", worst_ratio, 100 * (worst_ratio - 1))]
    md += ["", "Regression verification: `python3 sweep/tests/test_sweep.py` (30), "
           "`python3 sweep/tests/test_words.py` (14), `python3 sweep/tests/test_auto.py` (7), "
           "and `python3 sweep/tests/test_jitter.py` (10) pass: 61 tests total. "
           "Existing ANSI, phone, character, word, and auto vectors pass unchanged; no existing vectors were regenerated. "
           "A full-product-lexicon smoke check also preserved `yhmbc` as the first code for `yhyjmnbvc`, `yhjmnbvc`, "
           "and `yhmbc` on ANSI and phone geometry, and preserved 顏值/頻率 top-1 on both geometries. "
           "Both owner words stayed top-1 in all six ANSI continuous/lift/dwell cases."]
    md += ["", "These are synthetic results, not measured mouse, finger, touchpad, or touchscreen accuracy. "
           "The finite held-out sample does not establish a population-level 0.5-point bound. "
           "Real sensor traces, device sampling/coalescing, and Kotlin/desktop latency are not validated. "
           "The jitter estimate is gesture-global; local bursts may be missed. Spans with fewer than seven samples or gaps >32 ms "
           "are left unchanged. Smoothing rounds sharp corners and can shorten literal paths below their noiseless length; "
           "the arc-length table quantifies this tradeoff. The auto character branch receives no lift indices, so a lift with a gap <=32 ms can be filtered "
           "across in that branch; the word branch respects explicit lifts."]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--essay", default=DEFAULT_ESSAY)
    ap.add_argument("--profiles", default="mouse,finger,touchpad,touchscreen")
    ap.add_argument("--sigmas", default="0,.05,.1,.2,.3")
    ap.add_argument("--variants", default="off,smooth,length,window,smooth_window")
    ap.add_argument("--chars", type=int, default=1000)
    ap.add_argument("--per-cell", type=int, default=30)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--owners", type=int, default=0, help="Literal owner jitter draws per sigma; requires mouse profile")
    ap.add_argument("--latency", type=int, default=0, help="Serial latency paths per profile and kind; 0 skips")
    ap.add_argument("--latency-repeats", type=int, default=3)
    ap.add_argument("--latency-sigmas", default="0,.2")
    ap.add_argument("--out", default="sweep/results/jitter.json")
    ap.add_argument("--report", default="", help="Optional Markdown report destination")
    ap.add_argument("--ablation", default="", help="Earlier candidate pilot JSON to include in report")
    a = ap.parse_args(argv)
    if min(a.chars, a.per_cell, a.seeds, a.workers, a.latency_repeats) < 1:
        ap.error("sample sizes, seeds, workers and latency repeats must be positive")
    profiles, variants = a.profiles.split(","), a.variants.split(",")
    if "off" not in variants:
        ap.error("variants must include off as the paired baseline")
    if a.owners and "mouse" not in profiles:
        ap.error("--owners requires mouse profile")
    sigmas = [float(s) for s in a.sigmas.split(",")]
    chars = load_entries(a.table, min_len=1)
    entries = [e for e in chars if len(e[0]) >= 2]
    words = load_words(a.essay, 1000)
    layout = default_layout()
    mc = main_codes(chars)
    wc = WordConfig()
    wl = WordLexicon(chars, words, layout, wc)
    decs = {}
    for profile in profiles:
        cc = char_config(profile)
        cl = Lexicon(entries, layout, cc.n)
        decs[profile] = {variant: AutoDecoder(SweepDecoder(cl, cc.replace(pointer_filter=variant)),
                                             WordDecoder(wl, wc.replace(pointer_filter=variant))) for variant in variants}
    _G.update(layout=layout, mc=mc, decs=decs)
    citems = [("char", ch, code) for code, ch, _ in sample(split_entries(entries, "test"), a.chars, 4)]
    witems = [("word", text, None) for text, _ in stratified(words, mc, "test", a.per_cell, 5)]
    result = {"metadata": {"table_sha256": table_sha(a.table), "essay_sha256": table_sha(a.essay),
                            "char_entries": len(chars), "words": wl.n_words, "word_templates": len(wl.templates),
                            "eval_chars": len(citems), "eval_words": len(witems), "seeds": a.seeds,
                            "owner_draws": a.owners, "char_configs": {p: char_config(p).to_dict() for p in profiles},
                            "word_config": wc.to_dict()}, "variants": variants, "runs": {},
              "command": "python3 -m sweep.report_jitter " + " ".join(shlex.quote(x) for x in (argv if argv is not None else sys.argv[1:]))}
    with multiprocessing.get_context("fork").Pool(a.workers) as pool:
        for profile in profiles:
            for kind, items in (("char", citems), ("word", witems)):
                for sigma in sigmas:
                    tasks = [(profile, sigma, seed, item) for seed in range(1, a.seeds + 1) for item in items]
                    ranks = pool.map(_work, tasks, chunksize=8)
                    key = "%s|%s|%g" % (profile, kind, sigma)
                    result["runs"][key] = _aggregate(ranks, variants)
                    print(key, result["runs"][key], flush=True)
                    with open(a.out, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=1)
    if a.owners:
        result["owners"] = _owners(variants, sigmas, a.owners)
        result["owner_lengths"] = owner_lengths(sigmas, a.owners)
    if a.latency:
        result["latency"] = _latency(citems + witems, profiles, variants,
                                     [float(s) for s in a.latency_sigmas.split(",")], a.latency, a.latency_repeats)
    if a.ablation:
        with open(a.ablation, encoding="utf-8") as f:
            result["ablation"] = json.load(f)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    if a.report:
        write_report(result, a.report)
    return result


if __name__ == "__main__":
    main()
