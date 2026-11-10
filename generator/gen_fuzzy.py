#!/usr/bin/env python3
"""Generate Rime spelling-algebra rules for ONE adjacent-key substitution (typo tolerance).

usage:
  gen_fuzzy.py neighbors pc|phone            # (re)write neighbors_<name>.json from the layout model
  gen_fuzzy.py schema --map FILE.json --out OUT.schema.yaml [--tolerance 1] [--min-len 2]
                      [--max-len 5] [--stages 1] [--naive] [--schema-id ID] [--src SCHEMA]

Design (single substitution, no cascade):
  rule for position k and typed key n:
     fuzz/^([a-z]{k})[R]([a-z]*)$/${1}N${2}/      R = intended keys whose neighbour set contains n, N = upper-case n
  The pattern needs an all-lower-case spelling, the output contains one upper-case marker letter,
  so no later rule can match an already-derived spelling => at most ONE substitution.
  Extra "stage" rules (fuzz again, adding a prefix ~ ^ ...) stack one log(0.5) penalty per stage.
  Finally the prefix is erased and the marker is lower-cased (xform / xlit), and the 1-letter rule runs.
--naive writes the plain per-pair rules (derive/fuzz of lower-case letters, replace-all semantics) to demonstrate cascading.
"""
import argparse, json, re, sys

ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]


def layout_neighbors(kind):
    # key centre x per row (units of one key); threshold = max horizontal distance to count as adjacent row
    offs = {"pc": (0.0, 0.25, 0.75), "phone": (0.0, 0.5, 1.5)}[kind]
    thr = {"pc": 1.0, "phone": 0.75}[kind]
    xy = {}
    for r, row in enumerate(ROWS):
        for c, ch in enumerate(row):
            xy[ch] = (r, c + offs[r])
    nb = {ch: set() for ch in xy}
    for a in xy:
        for b in xy:
            if a == b:
                continue
            (ra, xa), (rb, xb) = xy[a], xy[b]
            if ra == rb and abs(xa - xb) <= 1.0:
                nb[a].add(b)
            elif abs(ra - rb) == 1 and abs(xa - xb) < thr:
                nb[a].add(b)
    return {k: sorted(v) for k, v in sorted(nb.items())}


def rules(nbmap, tolerance, min_len, max_len, stages, naive, pairs=None):
    out = []
    if pairs:
        return ["fuzz/%s/%s/" % tuple(p.split(":")) for p in pairs.split(",")]
    if tolerance <= 0:
        return out
    keys = sorted(nbmap)
    if naive:
        # one rule per ordered pair, replace-all semantics, NO markers: deliberately cascading
        for r in keys:
            for n in nbmap[r]:
                out.append("derive/%s/%s/" % (r, n))
        return out
    # typed key n  <-  intended keys r with n in nbmap[r]
    for k in range(0, max_len):
        for n in keys:
            R = sorted(r for r in keys if n in nbmap[r])
            if not R:
                continue
            # spelling length must be >= min_len and > k
            lo = max(min_len, k + 1)
            pat = r"^([a-z]{%d})[%s]([a-z]{%d,})$" % (k, "".join(R), max(lo - k - 1, 0))
            # allow rest of any length >= lo-k-1 : [a-z]{m,} ; for m=0 -> [a-z]{0,}
            out.append(r"fuzz/%s/${1}%s${2}/" % (pat, n.upper()))
    # extra penalty stages (each fuzz adds log(0.5)); markers keep exactly one upper-case letter
    prefixes = ["~", "^", "_", "@", "%"]
    prev = ""
    for s in range(stages - 1):
        pre = prefixes[s]
        out.append(r"fuzz/^%s([a-z]*[A-Z][a-z]*)$/%s$1/" % (re.escape(prev) if prev else "", pre))
        prev = pre
    # erase prefixes, lower-case marker
    if prev:
        out.append(r"xform/^%s//" % re.escape(prev))
    out.append("xlit|ABCDEFGHIJKLMNOPQRSTUVWXYZ|abcdefghijklmnopqrstuvwxyz|")
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("neighbors")
    a.add_argument("kind", choices=["pc", "phone"])
    b = sub.add_parser("schema")
    b.add_argument("--map", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--tolerance", type=int, default=1)
    b.add_argument("--min-len", type=int, default=2)
    b.add_argument("--max-len", type=int, default=5)
    b.add_argument("--stages", type=int, default=1)
    b.add_argument("--naive", action="store_true")
    b.add_argument("--pairs", default=None, help="naive demo: ordered r:n,r:n (fuzz, replace-all)")
    b.add_argument("--schema-id", default="cangjie3_fuzzy_spike")
    b.add_argument("--src", default="/home/hjs/projects/cangjie-fluency/weasel/cangjie3_fluency.schema.yaml")
    args = ap.parse_args()
    if args.cmd == "neighbors":
        m = layout_neighbors(args.kind)
        fn = "neighbors_%s.json" % args.kind
        json.dump(m, open(fn, "w"), indent=1)
        print(fn, sum(len(v) for v in m.values()), "directed edges")
        return
    nbmap = json.load(open(args.map))
    rs = rules(nbmap, args.tolerance, args.min_len, args.max_len, args.stages, args.naive, args.pairs)
    src = open(args.src, encoding="utf-8").read()
    src = src.replace("schema_id: cangjie3_fluency", "schema_id: " + args.schema_id)
    src = src.replace("prism: cangjie3_fluency", "prism: " + args.schema_id)
    marker = "    - 'xform/^(\\w)$/$1 /'"
    assert marker in src
    block = "".join("    - '%s'\n" % r for r in rs)
    src = src.replace(marker, block + marker)
    open(args.out, "w", encoding="utf-8").write(src)
    print("%s: %d fuzzy rules written" % (args.out, len(rs)))


if __name__ == "__main__":
    main()
