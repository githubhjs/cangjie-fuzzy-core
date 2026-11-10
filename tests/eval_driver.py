#!/usr/bin/env python3
"""Batch evaluator on top of the ctypes classes of rime_driver.py.

usage: eval_driver.py --env ENVDIR --schema ID [--no-grammar] CASES.jsonl > results.jsonl
CASES.jsonl lines: {"id":..., "truth": "text or null", "keys": "typed keys", "list": true|false}
Each result: {"id","keys","top","cands"(first page),"ms_per_key","truth","ok"}
"""
import argparse, ctypes, json, os, sys, time
from ctypes import c_char_p, c_int, byref, sizeof, POINTER

sys.path.insert(0, "/home/hjs/projects/cangjie-fluency/weasel/docs")
import rime_driver as D  # noqa: E402

R = "/home/hjs/projects/cangjie-fluency/rimebin/root"
SHARED = "/home/hjs/projects/cangjie-fluency/testenv/shared_nogy"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--no-grammar", action="store_true")
    ap.add_argument("--check", action="store_true", help="exit nonzero if an explicit case assertion fails")
    ap.add_argument("cases")
    a = ap.parse_args()
    lib_dir = R + "/usr/lib/aarch64-linux-gnu"
    rime = ctypes.CDLL(lib_dir + "/librime.so.1", mode=ctypes.RTLD_GLOBAL)
    mods = [b"default"]
    if not a.no_grammar:
        plug = ctypes.CDLL(lib_dir + "/rime-plugins/librime-octagram.so", mode=ctypes.RTLD_GLOBAL)
        plug._Z28rime_require_module_octagramv()
        mods.append(b"octagram")
    arr = (c_char_p * (len(mods) + 1))(*mods, None)
    rime.RimeCreateSession.restype = ctypes.c_size_t
    rime.RimeProcessKey.argtypes = [ctypes.c_size_t, c_int, c_int]
    rime.RimeGetContext.argtypes = [ctypes.c_size_t, POINTER(D.Context)]
    rime.RimeFreeContext.argtypes = [POINTER(D.Context)]
    rime.RimeSelectSchema.argtypes = [ctypes.c_size_t, c_char_p]
    rime.RimeClearComposition.argtypes = [ctypes.c_size_t]
    rime.RimeDestroySession.argtypes = [ctypes.c_size_t]
    t = D.Traits()
    t.data_size = sizeof(D.Traits) - sizeof(c_int)
    t.shared_data_dir = SHARED.encode()
    t.user_data_dir = a.env.encode()
    t.app_name = b"rime.fuzzy-spike"
    t.distribution_name = b"test"
    t.modules = arr
    t.min_log_level = 2
    logd = os.path.join(a.env, "log")
    os.makedirs(logd, exist_ok=True)
    t.log_dir = logd.encode()
    rime.RimeSetup(byref(t))
    rime.RimeInitialize(byref(t))
    sid = rime.RimeCreateSession()
    t0 = time.time()
    if not rime.RimeSelectSchema(sid, a.schema.encode()):
        raise RuntimeError("select schema failed: " + a.schema)
    load_s = time.time() - t0

    def ctx():
        c = D.Context()
        c.data_size = sizeof(D.Context) - sizeof(c_int)
        if not rime.RimeGetContext(sid, byref(c)):
            return None, []
        if c.composition.length == 0:
            rime.RimeFreeContext(byref(c))
            return None, []
        cands = [(c.menu.candidates[i].text or b"").decode() for i in range(c.menu.num_candidates)]
        pre = c.composition.preedit.decode()
        rime.RimeFreeContext(byref(c))
        return pre, cands

    failed = 0
    for line in open(a.cases, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        case = json.loads(line)
        keys = case["keys"]
        rime.RimeClearComposition(sid)
        per = []
        for k in keys:
            code = 0x20 if k == " " else ord(k)
            s = time.perf_counter()
            rime.RimeProcessKey(sid, code, 0)
            _ = ctx() if case.get("every_key", True) else None   # a frontend redraws after each key
            per.append((time.perf_counter() - s) * 1000)
        pre, cands = ctx()
        top = cands[0] if cands else None
        all_cands = list(cands)
        pages_complete = False
        for _page in range(100):
            c = D.Context()
            c.data_size = sizeof(D.Context) - sizeof(c_int)
            if not rime.RimeGetContext(sid, byref(c)):
                break
            last = c.menu.is_last_page
            rime.RimeFreeContext(byref(c))
            if last:
                pages_complete = True
                break
            if not rime.RimeProcessKey(sid, 0xff56, 0):  # Page_Down
                break
            _, page_cands = ctx()
            all_cands.extend(page_cands)
        res = {"id": case.get("id"), "keys": keys, "truth": case.get("truth"), "top": top,
               "cands": cands, "ms_per_key": round(sum(per) / max(len(per), 1), 2),
               "ms_max_key": round(max(per), 2) if per else 0,
               "candidate_count": len(all_cands), "pages_complete": pages_complete}
        checks = []
        if case.get("truth") is not None:
            checks.append(top == case["truth"])
        if "contains" in case:
            checks.append(case["contains"] in all_cands)
            res["target_rank"] = all_cands.index(case["contains"]) + 1 if case["contains"] in all_cands else None
        if "excludes" in case:
            checks.append(pages_complete and case["excludes"] not in all_cands)
        res["ok"] = bool(checks) and all(checks)
        if checks and not res["ok"]:
            failed += 1
        print(json.dumps(res, ensure_ascii=False))
        rime.RimeClearComposition(sid)
    print(json.dumps({"_load_schema_seconds": round(load_s, 3)}), file=sys.stderr)
    rime.RimeDestroySession(sid)
    rime.RimeFinalize()
    if a.check and failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
