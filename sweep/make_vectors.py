"""Generate sweep/vectors/vectors.json: reference test vectors for ports (Kotlin, JavaScript/TypeScript).

Each case = a path of (x, y, t_ms) in key widths + the expected ranked characters from THIS Python decoder, using the embedded MINI
lexicon (so a port can be checked without the full table). Cases also carry the top-5 against the full table (`expected_full`, with
the table's sha256) for ports that load the real table. Paths are rounded to 4 decimals before decoding, so the stored numbers are
exactly what the Python decoder saw. Cases whose top-k score margins are below 1e-6 are dropped (float-tie fragility across languages).

  python3 -m sweep.make_vectors --table cangjie3.tsv --config sweep/results/defaults_mouse.json
"""
import argparse
import json
import os
import random
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sweep.decoder import Lexicon, SweepConfig, SweepDecoder, collapse, repeat_positions  # noqa: E402
from sweep.evaluate import DEFAULT_TABLE, entry_seed, load_entries, table_sha  # noqa: E402
from sweep.keyboard import default_layout  # noqa: E402
from sweep.simulate import LEVELS, PROFILES, generate  # noqa: E402

TOPK = 5


def rounded(pts):
    return [[round(x, 4), round(y, 4), round(t, 1)] for (x, y, t) in pts]


def polyline_path(keys, layout, step_ms=10, steps=8):
    pts, t = [], 0.0
    cs = [layout.centers[k] for k in keys]
    for a, b in zip(cs, cs[1:]):
        for i in range(steps):
            pts.append((a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps, t))
            t += step_ms
    pts.append((cs[-1][0], cs[-1][1], t))
    return pts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--config", default="")
    ap.add_argument("--out", default=os.path.join(_ROOT, "sweep", "vectors", "vectors.json"))
    a = ap.parse_args(argv)
    L = default_layout()
    full = load_entries(a.table)
    cfg = SweepConfig()
    if a.config:
        with open(a.config) as f:
            d = json.load(f)
        cfg = cfg.replace(**d.get("best", d))
    rng = random.Random(2026)
    by_char = {}
    for e in full:
        by_char.setdefault(e[1], []).append(e)
    by_code = {}
    for e in full:
        by_code.setdefault(e[0], []).append(e)

    wanted = []  # (id, code, char, how)
    wanted.append(("yan-exact", "yhmbc", "顏", "exact"))
    wanted.append(("yan-slip-y-h-y-j-m-n-b-v-c", "yhmbc", "顏", "slip"))
    wanted.append(("spur-yhyjmnbvc", "yhmbc", "顏", "keys:yhyjmnbvc"))
    wanted.append(("spur-yhyhmbc", "yhmbc", "顏", "keys:yhyhmbc"))
    wanted.append(("spur-yuyjmnbc-ambiguous", "yjmbc", "贑", "keys:yuyjmnbc"))
    pool = {n: [e for e in full if len(e[0]) == n and not repeat_positions(e[0]) and len(by_code[e[0]]) <= 2] for n in (2, 3, 4, 5)}
    for n in (2, 3, 4, 5):
        for i, e in enumerate(rng.sample(pool[n], 4)):
            wanted.append(("len%d-%d" % (n, i), e[0], e[1], ("mouse", "mid") if i % 2 == 0 else ("finger", "low")))
    reps = [e for e in full if repeat_positions(e[0]) and 3 <= len(e[0]) <= 5 and len(by_code[e[0]]) == 1]
    for i, e in enumerate(rng.sample(reps, 4)):
        wanted.append(("repeat-dwell-%d" % i, e[0], e[1], "dwell"))
        wanted.append(("repeat-nodwell-%d" % i, e[0], e[1], "nodwell"))
    for code in ("dd", "hh", "aa"):
        if code in by_code:
            wanted.append(("double-" + code, code, by_code[code][0][1], "dwell"))
    wanted.append(("shared-code-ab-style", pool[2][0][0], by_code[pool[2][0][0]][0][1], "exact"))

    cases, targets = [], set()
    for cid, code, ch, how in wanted:
        if how == "exact":
            pts = generate(code, L, PROFILES["mouse"], 0.0, random.Random(1))
        elif isinstance(how, str) and how.startswith("keys:"):
            pts = polyline_path(how[5:], L)
        elif how == "slip":
            pts = polyline_path("yhyjmnbvc", L)
        elif how == "dwell":
            pts = generate(code, L, PROFILES["mouse"], 0.0, random.Random(1), dwell=True)
        elif how == "nodwell":
            pts = generate(code, L, PROFILES["mouse"], 0.0, random.Random(1), dwell=False)
        else:
            pts = generate(code, L, PROFILES[how[0]], LEVELS[how[1]], random.Random(entry_seed(5, code, ch)))
        cases.append({"id": cid, "target": ch, "code": code, "how": how if isinstance(how, str) else "%s/%s" % how, "points": rounded(pts)})
        targets.add(code)

    # mini lexicon. REAL rows (a few dozen, functionally required): every entry sharing a collapsed code with a target and every entry the
    # full decoder ranks in its top 12 for a case. FILLER rows are SYNTHETIC (random codes, private-use characters, random weights): the
    # repository contains no copy of the table.
    tcollapsed = {collapse(c) for c in targets}
    real = {(e[0], e[1]): e for e in full if collapse(e[0]) in tcollapsed}
    dec_full0 = SweepDecoder(Lexicon(full, L, cfg.n), cfg)
    for c in cases:
        for ch, code, sc in dec_full0.decode([tuple(p) for p in c["points"]], top_k=12):
            for e in by_char[ch]:
                real[(e[0], e[1])] = e
    mini = list(real.values())
    fr = random.Random(77)
    alpha = "abcdefghijklmnopqrstuvwxy"
    for i in range(1500):
        mini.append(("".join(fr.choice(alpha) for _ in range(fr.randint(2, 5))), chr(0xE000 + i), float(fr.randint(1, 5000))))
    mini.sort()
    dec_mini = SweepDecoder(Lexicon(mini, L, cfg.n), cfg)
    dec_full = SweepDecoder(Lexicon(full, L, cfg.n), cfg)
    kept = []
    for c in cases:
        pts = [tuple(p) for p in c["points"]]
        res = dec_mini.decode(pts, top_k=TOPK + 1)
        scores = [r[2] for r in res]
        margins = [scores[i] - scores[i + 1] for i in range(min(TOPK, len(scores) - 1))]
        if margins and min(margins) < 1e-6:
            print("drop (tie)", c["id"])
            continue
        c["expected"] = [r[0] for r in res[:TOPK]]
        c["expected_codes"] = [r[1] for r in res[:TOPK]]
        c["expected_scores"] = [round(r[2], 6) for r in res[:TOPK]]
        c["expected_full"] = [r[0] for r in dec_full.decode(pts, top_k=TOPK)]
        kept.append(c)
    out = {"format": "cangjie-sweep-vectors-1", "note": "points are (x, y, t_ms) in key widths of `centers`; decode with `config`; "
           "compare the ranked characters (scores to 1e-6). 'lexicon' = [code, char, weight] mini lexicon for `expected`: a few dozen REAL rows from the Cangjie 3 table (the targets' code groups and the top-ranked competitors) plus SYNTHETIC filler rows (random codes, private-use characters U+E000.., random weights); the repository does not contain the table.",
           "table_sha256": table_sha(a.table), "centers": {k: list(v) for k, v in L.centers.items()}, "config": cfg.to_dict(),
           "lexicon": [[c, ch, w] for c, ch, w in mini], "cases": kept}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote", a.out, len(kept), "cases", len(mini), "mini entries", os.path.getsize(a.out), "bytes")


if __name__ == "__main__":
    main()
