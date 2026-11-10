#!/usr/bin/env python3
"""Sentence-level one-neighbour-typo evaluation (KAN-225 remaining check: sentences, inclusion vs top-1).

make   : writes cases_typo_sentences.jsonl from the 91 real sentences (weasel/docs/sentences.txt + hard.txt):
         one EXACT case per sentence (expects top-1 == sentence) and 3 TYPO cases per sentence (one letter replaced by a
         PC neighbour, expects the sentence to be among the candidates; rank recorded).
summary: reads result files produced by eval_driver.py and prints the rates.
Usage:  python3 sentence_typo_eval.py make
        python3 sentence_typo_eval.py summary results_a.jsonl [results_b.jsonl ...]
"""
import json, random, re, sys, os, statistics

TABLE = os.path.expanduser("~/.config/ibus/rime/cangjie3.base.dict.yaml")
DOCS = "/home/hjs/projects/cangjie-fluency/weasel/docs"
NEI = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "neighbors_pc.json")))


def load_codes():
    first, on = {}, False
    for line in open(TABLE, encoding="utf-8"):
        if line.strip() == "...":
            on = True
            continue
        if on and line.strip() and not line.startswith("#"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2 and p[0] not in first:
                first[p[0]] = p[1]
    return first


def sentences():
    out = []
    for f in ("sentences.txt", "hard.txt"):
        for line in open(os.path.join(DOCS, f), encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^[a-z]+:", "", line)
            out.append(line)
    return out


def keys_of(s, codes):
    segs = []
    for ch in s:
        c = codes[ch]
        segs.append(c + (" " if len(c) == 1 else ""))
    return segs


def make():
    codes = load_codes()
    rnd = random.Random(20261110)
    n_ex = n_ty = skipped = 0
    with open("cases_typo_sentences.jsonl", "w", encoding="utf-8") as out:
        for i, s in enumerate(sentences()):
            if any(ch not in codes for ch in s):
                skipped += 1
                continue
            segs = keys_of(s, codes)
            out.write(json.dumps({"id": f"E{i}", "keys": "".join(segs), "truth": s}, ensure_ascii=False) + "\n")
            n_ex += 1
            made = set()
            for k in range(3):
                for _ in range(20):
                    si = rnd.randrange(len(segs))
                    letters = [j for j, c in enumerate(segs[si]) if c != " "]
                    j = rnd.choice(letters)
                    nb = NEI.get(segs[si][j], [])
                    if not nb:
                        continue
                    new = list(segs)
                    new[si] = segs[si][:j] + rnd.choice(nb) + segs[si][j + 1:]
                    key = "".join(new)
                    if key in made or key == "".join(segs):
                        continue
                    made.add(key)
                    out.write(json.dumps({"id": f"T{i}-{k}", "keys": key, "contains": s, "typo_at": [si, j]}, ensure_ascii=False) + "\n")
                    n_ty += 1
                    break
    print(f"exact cases {n_ex}, typo cases {n_ty}, skipped sentences (char without code) {skipped}")


def summary(files):
    for f in files:
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        ex = [r for r in rows if r["id"].startswith("E")]
        ty = [r for r in rows if r["id"].startswith("T")]
        ex_ok = sum(1 for r in ex if r.get("top") == r.get("truth"))
        ranks = [r.get("target_rank") for r in ty]
        found = [x for x in ranks if x]
        r1 = sum(1 for x in found if x == 1)
        r5 = sum(1 for x in found if x <= 5)
        r9 = sum(1 for x in found if x <= 9)
        print(f"{os.path.basename(f)}: exact top-1 {ex_ok}/{len(ex)} | typo: top-1 {r1}/{len(ty)}, in first 5 {r5}/{len(ty)}, "
              f"in first 9 {r9}/{len(ty)}, anywhere {len(found)}/{len(ty)}, median rank {statistics.median(found) if found else None}, "
              f"max pages incomplete {sum(1 for r in rows if not r.get('pages_complete'))}")


if __name__ == "__main__":
    if sys.argv[1] == "make":
        make()
    else:
        summary(sys.argv[2:])
