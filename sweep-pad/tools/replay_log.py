#!/usr/bin/env python3
"""Replay and calibrate logged sweeps using the desktop pad decoder. Python 3.8+ stdlib."""
import argparse
import json
import math
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PAD = HERE.parent
if not (PAD / 'sweep').is_dir():
    sys.path.insert(0, str(PAD.parent))
sys.path.insert(0, str(PAD))

from sweep.auto import AutoDecoder
from sweep.decoder import SweepDecoder
from sweep.words import WordDecoder
from pad_words import make_decoder


def load_log_files(paths):
    entries = []
    for p in paths:
        path = Path(p)
        if not path.is_file():
            raise FileNotFoundError(f"Log file not found: {path}")
        with path.open(encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def path_length(points):
    if len(points) < 2:
        return 0.0
    return sum(math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
               for i in range(1, len(points)))


def length_bucket(length):
    if length < 5.0:
        return "<5"
    elif length < 10.0:
        return "5-10"
    elif length < 15.0:
        return "10-15"
    else:
        return ">=15"


def evaluate_log(log_paths_or_entries, decoder, top_k=5):
    if isinstance(log_paths_or_entries, (str, Path)):
        entries = load_log_files([log_paths_or_entries])
    elif isinstance(log_paths_or_entries, list) and log_paths_or_entries and isinstance(log_paths_or_entries[0], dict):
        entries = log_paths_or_entries
    else:
        entries = load_log_files(log_paths_or_entries)

    total_sweeps = len(entries)
    chosen_sweeps = []
    for e in entries:
        chosen = e.get('chosen')
        if isinstance(chosen, dict) and 'text' in chosen and chosen['text']:
            chosen_sweeps.append(e)

    by_type = {
        "char": {"n": 0, "top1": 0, "top3": 0, "top5": 0},
        "word": {"n": 0, "top1": 0, "top3": 0, "top5": 0},
    }
    by_length = {
        "<5": {"n": 0, "top1": 0, "top3": 0, "top5": 0},
        "5-10": {"n": 0, "top1": 0, "top3": 0, "top5": 0},
        "10-15": {"n": 0, "top1": 0, "top3": 0, "top5": 0},
        ">=15": {"n": 0, "top1": 0, "top3": 0, "top5": 0},
    }

    top1_total = 0
    top3_total = 0
    top5_total = 0
    misses = []

    for entry in chosen_sweeps:
        pts = entry.get('points', [])
        lifts = entry.get('lifts', [])
        chosen = entry['chosen']
        target_text = chosen['text']
        code = chosen.get('code', '')
        pts_count = len(pts)
        geom_len = path_length(pts)
        len_b = length_bucket(geom_len)
        kind = "char" if len(target_text) == 1 else "word"

        results = decoder.decode(pts, lifts, top_k=top_k)
        rank = None
        for i, (text, c, score) in enumerate(results):
            if text == target_text:
                rank = i + 1
                break

        r_top1 = 1 if rank == 1 else 0
        r_top3 = 1 if (rank is not None and rank <= 3) else 0
        r_top5 = 1 if (rank is not None and rank <= 5) else 0

        top1_total += r_top1
        top3_total += r_top3
        top5_total += r_top5

        bt = by_type[kind]
        bt["n"] += 1
        bt["top1"] += r_top1
        bt["top3"] += r_top3
        bt["top5"] += r_top5

        bl = by_length[len_b]
        bl["n"] += 1
        bl["top1"] += r_top1
        bl["top3"] += r_top3
        bl["top5"] += r_top5

        if rank != 1:
            misses.append({
                "text": target_text,
                "code": code,
                "points_count": pts_count,
                "rank": rank,
            })

    # Sort misses: unranked (rank is None) first, then rank 5, 4, 3, 2; tie-breaker: points_count descending
    misses.sort(key=lambda m: (float('inf') if m['rank'] is None else m['rank'], m['points_count']), reverse=True)
    worst_misses = misses[:10]

    n_chosen = len(chosen_sweeps)
    report = {
        "total_sweeps": total_sweeps,
        "chosen_sweeps": n_chosen,
        "top1_count": top1_total,
        "top3_count": top3_total,
        "top5_count": top5_total,
        "top1_rate": (top1_total / n_chosen) if n_chosen else 0.0,
        "top3_rate": (top3_total / n_chosen) if n_chosen else 0.0,
        "top5_rate": (top5_total / n_chosen) if n_chosen else 0.0,
        "breakdown": {
            "by_type": {
                k: {
                    "n": v["n"],
                    "top1_rate": (v["top1"] / v["n"]) if v["n"] else 0.0,
                    "top3_rate": (v["top3"] / v["n"]) if v["n"] else 0.0,
                    "top5_rate": (v["top5"] / v["n"]) if v["n"] else 0.0,
                }
                for k, v in by_type.items()
            },
            "by_length": {
                k: {
                    "n": v["n"],
                    "top1_rate": (v["top1"] / v["n"]) if v["n"] else 0.0,
                    "top3_rate": (v["top3"] / v["n"]) if v["n"] else 0.0,
                    "top5_rate": (v["top5"] / v["n"]) if v["n"] else 0.0,
                }
                for k, v in by_length.items()
            },
        },
        "worst_misses": worst_misses,
    }
    return report


def grid_search_tune(chosen_sweeps, base_decoder):
    """Grid-search align_weight, prune_radius, and loc_scale on logged sweeps."""
    align_weights = [1.5, 2.49, 3.5]
    prune_radii = [1.0, 1.2, 1.5]
    loc_scales = [0.9, 1.0, 1.1]

    n = len(chosen_sweeps)
    best_score = None
    best_params = None
    baseline_stats = None

    for aw in align_weights:
        for pr in prune_radii:
            for ls in loc_scales:
                w_cfg = base_decoder.decoder.cfg.replace(
                    align_weight=aw,
                    prune_radius=pr,
                    loc_weight=base_decoder.decoder.cfg.loc_weight * ls
                )
                c_cfg = base_decoder.auto.chars.cfg.replace(
                    align_weight=aw,
                    prune_radius=pr,
                    loc_weight=base_decoder.auto.chars.cfg.loc_weight * ls
                )
                w_dec = WordDecoder(base_decoder.lex, w_cfg)
                c_dec = SweepDecoder(base_decoder.auto.chars.lex, c_cfg)
                auto_dec = AutoDecoder(c_dec, w_dec, top_k=5)

                top1 = 0
                top3 = 0
                top5 = 0
                for entry in chosen_sweeps:
                    pts = entry.get('points', [])
                    lifts = entry.get('lifts', [])
                    target = entry['chosen']['text']
                    res = auto_dec.decode(pts, lifts, 5)
                    rank = None
                    for i, r in enumerate(res):
                        if r[0] == target:
                            rank = i + 1
                            break
                    if rank == 1:
                        top1 += 1
                    if rank is not None and rank <= 3:
                        top3 += 1
                    if rank is not None and rank <= 5:
                        top5 += 1

                # Tie-breaker favors default parameters
                dist_from_default = abs(aw - 2.49) + abs(pr - 1.2) + abs(ls - 1.0)
                score = (top1, top3, top5, -dist_from_default)

                if (aw, pr, ls) == (2.49, 1.2, 1.0):
                    baseline_stats = {
                        "align_weight": aw,
                        "prune_radius": pr,
                        "loc_scale": ls,
                        "top1_rate": top1 / n,
                        "top3_rate": top3 / n,
                        "top5_rate": top5 / n,
                    }

                if best_score is None or score > best_score:
                    best_score = score
                    best_params = {
                        "align_weight": aw,
                        "prune_radius": pr,
                        "loc_scale": ls,
                        "top1_rate": top1 / n,
                        "top3_rate": top3 / n,
                        "top5_rate": top5 / n,
                    }

    return {
        "n_sweeps": n,
        "grid": {
            "align_weight": align_weights,
            "prune_radius": prune_radii,
            "loc_scale": loc_scales,
        },
        "baseline": baseline_stats or best_params,
        "best": best_params,
        "caveat": (
            f"Tuning was performed on {n} logged sweeps without an independent held-out split. "
            "Parameters may overfit to this specific sample; validate on independent sessions "
            "before modifying default configuration."
        ),
    }


def format_text_report(report, tune_report=None):
    lines = []
    lines.append("=== Cangjie Sweep Pad: Replay Report ===")
    lines.append(f"Total sweeps in log: {report['total_sweeps']}")
    n = report['chosen_sweeps']
    pct_chosen = (n / report['total_sweeps'] * 100.0) if report['total_sweeps'] else 0.0
    lines.append(f"Sweeps with chosen candidate: {n} ({pct_chosen:.1f}%)")
    lines.append("")

    lines.append(f"Top-1 accuracy: {report['top1_count']}/{n} ({report['top1_rate'] * 100:.1f}%)")
    lines.append(f"Top-3 accuracy: {report['top3_count']}/{n} ({report['top3_rate'] * 100:.1f}%)")
    lines.append(f"Top-5 accuracy: {report['top5_count']}/{n} ({report['top5_rate'] * 100:.1f}%)")
    lines.append("")

    lines.append("Breakdown by type:")
    for k in ("char", "word"):
        v = report['breakdown']['by_type'][k]
        lines.append(f"  {k:<5}: n={v['n']:<3} top-1: {v['top1_rate']*100:5.1f}%  "
                     f"top-3: {v['top3_rate']*100:5.1f}%  top-5: {v['top5_rate']*100:5.1f}%")
    lines.append("")

    lines.append("Breakdown by path length (key widths):")
    for k in ("<5", "5-10", "10-15", ">=15"):
        v = report['breakdown']['by_length'][k]
        lines.append(f"  {k:<6}: n={v['n']:<3} top-1: {v['top1_rate']*100:5.1f}%  "
                     f"top-3: {v['top3_rate']*100:5.1f}%  top-5: {v['top5_rate']*100:5.1f}%")
    lines.append("")

    lines.append("Worst misses (up to 10):")
    if not report['worst_misses']:
        lines.append("  (none; all sweeps matched top candidate)")
    else:
        for idx, m in enumerate(report['worst_misses'], 1):
            rank_str = f"rank={m['rank']}" if m['rank'] is not None else "rank=>5"
            lines.append(f"  {idx:>2}. text={m['text']}  code={m['code']}  points={m['points_count']}  {rank_str}")
    lines.append("")

    if tune_report:
        lines.append("=== Decoder Parameter Tuning (Grid Search) ===")
        lines.append(f"Sweeps evaluated: {tune_report['n_sweeps']}")
        b = tune_report['baseline']
        lines.append(f"Baseline (defaults: align_weight={b['align_weight']}, prune_radius={b['prune_radius']}, loc_scale={b['loc_scale']}):")
        lines.append(f"  top-1: {b['top1_rate']*100:.1f}%  top-3: {b['top3_rate']*100:.1f}%  top-5: {b['top5_rate']*100:.1f}%")
        best = tune_report['best']
        lines.append(f"Best settings (align_weight={best['align_weight']}, prune_radius={best['prune_radius']}, loc_scale={best['loc_scale']}):")
        lines.append(f"  top-1: {best['top1_rate']*100:.1f}%  top-3: {best['top3_rate']*100:.1f}%  top-5: {best['top5_rate']*100:.1f}%")
        lines.append("")
        lines.append("Caveat:")
        lines.append(f"  {tune_report['caveat']}")
        lines.append("")

    return "\n".join(lines)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('logs', nargs='+', type=Path, help='one or more sweep log JSONL files')
    ap.add_argument('--table', type=Path, default=PAD / 'data/cangjie3.tsv')
    ap.add_argument('--essay', type=Path, default=PAD / 'data/essay.txt')
    ap.add_argument('--profile', default='mouse', choices=('mouse', 'touchpad', 'touchscreen'))
    ap.add_argument('--strictness', type=float, default=1.0)
    ap.add_argument('--top-k', type=int, default=5)
    ap.add_argument('--json', action='store_true', help='output machine-readable JSON')
    ap.add_argument('--tune', action='store_true', help='grid-search decoder parameters on logged sweeps (requires >= 50 sweeps)')
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    entries = load_log_files(args.logs)

    chosen_entries = [e for e in entries if isinstance(e.get('chosen'), dict) and e['chosen'].get('text')]

    if args.tune and len(chosen_entries) < 50:
        msg = f"Tuning requires at least 50 sweeps with chosen candidates (found {len(chosen_entries)}); collect more sweeps before tuning."
        if args.json:
            print(json.dumps({"error": msg}, ensure_ascii=False, indent=2))
        else:
            print(msg, file=sys.stderr)
        return 1

    decoder = make_decoder(args)
    report = evaluate_log(entries, decoder, top_k=args.top_k)

    tune_report = None
    if args.tune:
        tune_report = grid_search_tune(chosen_entries, decoder)
        report["tune"] = tune_report

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text_report(report, tune_report))

    return 0


if __name__ == '__main__':
    sys.exit(main())
