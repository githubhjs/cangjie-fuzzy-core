#!/usr/bin/env python3
"""Quantitative study of the two tolerance knobs, to justify (and let you change) the defaults.

  theta   the fuzzy RANGE: two keys count as neighbours when their centres are within theta key widths
  budget  typos tolerated PER CODE (one character's code)         -> Matcher(budget=...)
  phrase  typos tolerated PER PHRASE (several characters typed in one go) -> a cap applied on top, see phrase_cap()

Simulated user: each key press is wrong with probability p (per-key substitution rate). A wrong key is a physical neighbour
(within NEAR key widths) with probability ADJ, otherwise a random other key. Characters are drawn by corpus weight.
No insertions, deletions or transpositions (outside the feature, see SPEC.md).

usage: python3 tests/range_study.py [--table PATH] [--n 20000] [--json OUT.json] [--md OUT.md]
"""
import argparse, json, os, random, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from core import Matcher, qwerty_pc, load_rime_dict

ALPHA = "abcdefghijklmnopqrstuvwxyz"
NEAR = 1.5  # a real adjacent-key slip lands within this distance (key widths) of the intended key


def make_typo(code, p, adj, layout, rnd):
    """Return (typed, number_of_wrong_keys)."""
    out, wrong = [], 0
    for ch in code:
        if rnd.random() < p:
            nb = layout.neighbours(ch, NEAR)
            if nb and rnd.random() < adj:
                w = [1.0 / max(layout.distance(ch, k), 0.5) ** 2 for k in nb]
                out.append(rnd.choices(nb, w)[0])
            else:
                out.append(rnd.choice([c for c in ALPHA if c != ch]))
            wrong += 1
        else:
            out.append(ch)
    return "".join(out), wrong


def rank_of(cands, text):
    for i, c in enumerate(cands):
        if c.text == text:
            return i + 1
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=os.environ.get("CJF_TABLE", os.path.expanduser("~/.config/ibus/rime/cangjie3.base.dict.yaml")))
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--adj", type=float, default=0.5, help="share of wrong keys that are physical neighbours (see the literature note)")
    ap.add_argument("--json", default="")
    ap.add_argument("--md", default="")
    a = ap.parse_args()

    layout = qwerty_pc()
    entries = list(load_rime_dict(a.table))
    rnd = random.Random(2026)
    # pick characters by corpus weight (single characters only), skip 1-key codes (never fuzzy, see Matcher.min_len)
    chars = [(t, c, w) for t, c, w in entries if len(t) == 1 and len(c) >= 2]
    weights = [max(w, 1) for _, _, w in chars]
    thetas = [0.0, 1.0, 1.15, 1.3, 1.5, 1.8, 2.2]
    budgets = [1, 2]
    rates = [0.01, 0.02, 0.05]
    rows = []
    t0 = time.time()
    matchers = {}
    for th in thetas:
        for b in budgets:
            if th == 0.0 and b != 1:
                continue
            matchers[(th, b)] = Matcher(entries, layout, th if th > 0 else 0.1, budget=0 if th == 0.0 else b)

    for p in rates:
        sample = rnd.choices(chars, weights, k=a.n)
        typed = [(t, c, make_typo(c, p, a.adj, layout, rnd)) for t, c, _ in sample]
        with_typo = [x for x in typed if x[2][1] > 0]
        for (th, b), m in matchers.items():
            hit1 = hit5 = hit9 = n = 0
            extra_sum = 0
            for text, code, (ty, wrong) in typed:
                cands = m.lookup(ty, theta=th if th > 0 else 0.1, budget=0 if th == 0.0 else b)
                r = rank_of(cands, text)
                hit1 += r == 1
                hit5 += r is not None and r <= 5
                hit9 += r is not None and r <= 9
                n += 1
                extra_sum += sum(1 for c in cands if c.subs > 0)
            rows.append({"p": p, "theta": th, "budget": b, "top1": hit1 / n, "top5": hit5 / n, "top9": hit9 / n,
                         "avg_fuzzy_cands": extra_sum / n, "chars": n, "chars_with_typo": len(with_typo)})
        print("p=%.2f done (%.0fs)" % (p, time.time() - t0), file=sys.stderr)

    # noise cost on CORRECT typing: how many extra (fuzzy) candidates appear next to the exact ones
    noise = []
    sample = rnd.choices(chars, weights, k=a.n)
    for (th, b), m in matchers.items():
        if th == 0.0:
            continue
        extra = lens = over9 = 0
        for text, code, _ in sample:
            cands = m.lookup(code, theta=th, budget=b)
            k = sum(1 for c in cands if c.subs > 0)
            extra += k
            lens += len(cands)
            over9 += len(cands) > 9
        noise.append({"theta": th, "budget": b, "avg_extra": extra / len(sample), "avg_total": lens / len(sample),
                      "share_over_one_page": over9 / len(sample)})

    # phrase level: NCH characters typed together, per-code budget 1, a cap on how many codes may be corrected per phrase
    phrase = []
    for NCH in (3, 5, 8):
        for p in rates:
            for th in ((1.0, 1.3, 1.8) if NCH == 5 else (1.3,)):
                m = matchers[(th, 1)]
                caps = sorted({0, 1, 2, 3, NCH})
                for cap in caps:
                    ok = 0
                    trials = max(a.n // 4, 2000)
                    rr = random.Random(NCH * 1000 + int(p * 1000) + int(th * 10))  # same phrases for every cap
                    for _ in range(trials):
                        ph = rr.choices(chars, weights, k=NCH)
                        all_ok = True
                        fixed = 0
                        for text, code, _ in ph:
                            ty, wrong = make_typo(code, p, a.adj, layout, rr)
                            cands = m.lookup(ty, theta=th, budget=1)
                            r = rank_of(cands, text)
                            if r is None or r > 5:
                                all_ok = False
                                break
                            if cands[r - 1].subs > 0:
                                fixed += 1
                        ok += all_ok and fixed <= cap
                    phrase.append({"p": p, "theta": th, "cap": cap, "phrase_ok": ok / trials, "chars_per_phrase": NCH})

    res = {"rows": rows, "noise": noise, "phrase": phrase, "n": a.n, "adj_share": a.adj, "near": NEAR}
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    lines = ["# Fuzzy range and tolerance study (simulation)", "",
             "Per-key substitution rate p; wrong key is a physical neighbour with probability %.2f; %d characters per cell." % (a.adj, a.n), "",
             "## A. Recovering a mistyped character (per code), by range theta and per-code budget", "",
             "| p | theta | budget | top-1 | top-5 | top-9 | avg fuzzy candidates |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %.0f%% | %s | %d | %.1f%% | %.1f%% | %.1f%% | %.1f |" % (
            r["p"] * 100, "off" if r["theta"] == 0 else r["theta"], r["budget"], r["top1"] * 100, r["top5"] * 100, r["top9"] * 100, r["avg_fuzzy_cands"]))
    lines += ["", "## B. Noise when typing CORRECTLY (extra candidates shown after the exact ones)", "",
              "| theta | budget | avg extra | avg total | lists longer than 9 |", "|---|---|---|---|---|"]
    for r in noise:
        lines.append("| %s | %d | %.1f | %.1f | %.0f%% |" % (r["theta"], r["budget"], r["avg_extra"], r["avg_total"], r["share_over_one_page"] * 100))
    lines += ["", "## C. Per-phrase cap: share of phrases fully recovered (every character in top-5)", "",
              "Cap = how many codes of one phrase may be corrected by the fuzzy stream. 'all' = no cap.", "",
              "| chars | p | theta | cap 0 | cap 1 | cap 2 | cap 3 | all |", "|---|---|---|---|---|---|---|---|"]
    for NCH in (3, 5, 8):
        for p in rates:
            for th in ((1.0, 1.3, 1.8) if NCH == 5 else (1.3,)):
                vals = {x["cap"]: x["phrase_ok"] for x in phrase if x["p"] == p and x["theta"] == th and x["chars_per_phrase"] == NCH}
                cells = [("%.1f%%" % (vals[c] * 100)) if c in vals else "-" for c in (0, 1, 2, 3, NCH)]
                lines.append("| %d | %.0f%% | %s | %s |" % (NCH, p * 100, th, " | ".join(cells)))
    text = "\n".join(lines) + "\n"
    if a.md:
        open(a.md, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
