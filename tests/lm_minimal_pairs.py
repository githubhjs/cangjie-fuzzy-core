#!/usr/bin/env python3
"""Does the language model matter? Same-code character pairs decided only by word / context.

Pairs (same 3rd-generation code): 感/怠 (irp), 頻/顏 (yhmbc). Typed with the first code of every character, no space/selection.
make    : writes cases_lm_pairs.jsonl  (truth = intended text)
summary : python3 lm_minimal_pairs.py summary on.jsonl off.jsonl
"""
import json, os, sys

TABLE = os.path.expanduser("~/.config/ibus/rime/cangjie3.base.dict.yaml")
S = [
    # word level
    "手感", "手怠", "頻率", "顏率", "顏色", "頻道", "感覺", "怠慢", "懈怠", "感謝", "顏值", "頻繁",
    # short context
    "手感很好", "手感不錯", "頻率很高", "頻率太低", "顏值很高", "顏色很好看", "感覺很好", "怠慢了客人",
    # sentences
    "這個鍵盤的手感很好", "這把吉他的手感不錯", "調整取樣頻率", "收音機的頻率是多少", "訊號的頻率太高了",
    "他的顏值真的很高", "這個顏色很好看", "我覺得手感比較重要", "請不要怠慢客人", "怠工是不對的",
    "出現的頻率越來越高", "他對這件事很感興趣", "謝謝你的感謝信", "工作不要懈怠",
]


def codes():
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


def make():
    c = codes()
    n = 0
    with open("cases_lm_pairs.jsonl", "w", encoding="utf-8") as f:
        for i, s in enumerate(S):
            if any(ch not in c for ch in s):
                print("skip (no code):", s, [ch for ch in s if ch not in c])
                continue
            keys = "".join(c[ch] + (" " if len(c[ch]) == 1 else "") for ch in s)
            f.write(json.dumps({"id": f"L{i}", "keys": keys, "truth": s}, ensure_ascii=False) + "\n")
            n += 1
    print("cases", n)


def summary(files):
    rows = {}
    for f in files:
        rows[f] = {r["id"]: r for r in (json.loads(l) for l in open(f, encoding="utf-8"))}
    ids = list(next(iter(rows.values())).keys())
    names = list(rows)
    print("%-22s" % "truth" + "".join("%-26s" % os.path.basename(n) for n in names))
    ok = {n: 0 for n in names}
    for i in ids:
        line = "%-22s" % rows[names[0]][i]["truth"]
        for n in names:
            r = rows[n][i]
            good = r["top"] == r["truth"]
            ok[n] += good
            line += "%-26s" % (("OK  " if good else "XX  ") + r["top"])
        print(line)
    print("top-1 correct:", {os.path.basename(n): f"{ok[n]}/{len(ids)}" for n in names})


if __name__ == "__main__":
    make() if sys.argv[1] == "make" else summary(sys.argv[2:])
