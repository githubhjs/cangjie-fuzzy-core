#!/usr/bin/env python3
"""Headless engine test for the Cangjie schemas, identical on Linux, macOS and Windows (Python 3.8+, standard library only).

It loads the platform's OWN librime (Weasel's rime.dll, Squirrel's librime.1.dylib, the distro's librime.so.1), points it at a user
folder produced by the installer under test, deploys that folder (builds the schemas), types keys through the librime C API and checks
the candidates. No GUI, no focus, no permissions: it can run over ssh.

  python3 cj_headless.py --lib LIBRIME --user USERDIR [--shared SHAREDDIR] [--preload-plugin PATH:SYMBOL] [--json OUT]
                         [--suite fluency|fuzzy|all] [--schema-prefix cangjie3|cangjie5]

Exit code 0 = every assertion passed. A schema that is not installed in USERDIR is reported as SKIP, not as a failure, unless
--require lists it.
"""
import argparse, ctypes, json, os, sys, time
from ctypes import CFUNCTYPE, c_char_p, c_int, c_size_t, c_void_p, POINTER, Structure, byref, sizeof


class Traits(Structure):
    _fields_ = [("data_size", c_int), ("shared_data_dir", c_char_p), ("user_data_dir", c_char_p),
                ("distribution_name", c_char_p), ("distribution_code_name", c_char_p), ("distribution_version", c_char_p),
                ("app_name", c_char_p), ("modules", POINTER(c_char_p)), ("min_log_level", c_int), ("log_dir", c_char_p),
                ("prebuilt_data_dir", c_char_p), ("staging_dir", c_char_p)]


class Composition(Structure):
    _fields_ = [("length", c_int), ("cursor_pos", c_int), ("sel_start", c_int), ("sel_end", c_int), ("preedit", c_char_p)]


class Candidate(Structure):
    _fields_ = [("text", c_char_p), ("comment", c_char_p), ("reserved", c_void_p)]


class Menu(Structure):
    _fields_ = [("page_size", c_int), ("page_no", c_int), ("is_last_page", c_int), ("highlighted_candidate_index", c_int),
                ("num_candidates", c_int), ("candidates", POINTER(Candidate)), ("select_keys", c_char_p)]


class Context(Structure):
    _fields_ = [("data_size", c_int), ("composition", Composition), ("menu", Menu), ("commit_text_preview", c_char_p),
                ("select_labels", POINTER(c_char_p))]


_V = c_void_p  # function pointers we do not call
_FIELDS = [
    ("setup", CFUNCTYPE(None, POINTER(Traits))), ("set_notification_handler", _V),
    ("initialize", CFUNCTYPE(None, POINTER(Traits))), ("finalize", CFUNCTYPE(None)),
    ("start_maintenance", CFUNCTYPE(c_int, c_int)), ("is_maintenance_mode", _V),
    ("join_maintenance_thread", CFUNCTYPE(None)), ("deployer_initialize", _V), ("prebuild", _V), ("deploy", _V),
    ("deploy_schema", _V), ("deploy_config_file", _V), ("sync_user_data", _V),
    ("create_session", CFUNCTYPE(c_size_t)), ("find_session", _V), ("destroy_session", CFUNCTYPE(c_int, c_size_t)),
    ("cleanup_stale_sessions", _V), ("cleanup_all_sessions", _V),
    ("process_key", CFUNCTYPE(c_int, c_size_t, c_int, c_int)), ("commit_composition", _V),
    ("clear_composition", CFUNCTYPE(None, c_size_t)), ("get_commit", _V), ("free_commit", _V),
    ("get_context", CFUNCTYPE(c_int, c_size_t, POINTER(Context))), ("free_context", CFUNCTYPE(c_int, POINTER(Context))),
    ("get_status", _V), ("free_status", _V), ("set_option", _V), ("get_option", _V), ("set_property", _V),
    ("get_property", _V), ("get_schema_list", _V), ("free_schema_list", _V), ("get_current_schema", _V),
    ("select_schema", CFUNCTYPE(c_int, c_size_t, c_char_p)),
]


class RimeApi(Structure):  # the function table returned by rime_get_api(); layout of rime_api.h up to select_schema
    _fields_ = [("data_size", c_int)] + _FIELDS


# (suite, schema, keys, kind, value)  kinds: top = first candidate equals value, has = value among all pages,
# lacks = value not among all pages, same_top = first candidate equals the first candidate of <value> typed in the plain schema
CASES = [
    ("fluency", "{g}_fluency", "dhedhkb", "top", "板橋"),
    ("fluency", "{g}_fluency", "mwyl", "top", "面"),
    ("fluency", "{g}_fluency", "yhmbc", "has", "顏"),
    ("fluency", "{g}_fluency", "yhmbv", "lacks", "顏"),
    ("fuzzy", "{g}_fuzzy", "dhedhkb", "top", "板橋"),
    ("fuzzy", "{g}_fuzzy", "mwyl", "top", "面"),
    ("fuzzy", "{g}_fuzzy", "yhmbc", "has", "顏"),
    ("fuzzy", "{g}_fuzzy", "yhmbv", "has", "顏"),       # c -> v, the owner's example (adjacent keys)
    ("fuzzy", "{g}_fuzzy", "yhnbc", "has", "顏"),       # m -> n
    ("fuzzy", "{g}_fuzzy", "yhnbv", "lacks", "顏"),     # two positions differ: not tolerated
    ("fuzzy", "{g}_fuzzy", "yhmbp", "lacks", "顏"),     # p is not next to c
    ("fuzzy", "{g}_fuzzy", "mwyl", "same_top", "{g}_fluency"),
    ("fuzzy", "{g}_fuzzy", "dhedhkb", "same_top", "{g}_fluency"),
    ("fuzzy", "{g}_fuzzy", "yhmbc", "same_top", "{g}_fluency"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True, help="path of librime (rime.dll / librime.1.dylib / librime.so.1)")
    ap.add_argument("--user", required=True, help="Rime user folder produced by the installer under test")
    ap.add_argument("--shared", default="", help="shared data folder of the front end (schemas such as luna_quanpin live there)")
    ap.add_argument("--preload-plugin", action="append", default=[], help="PATH:SYMBOL, e.g. .../librime-octagram.so:_Z28rime_require_module_octagramv")
    ap.add_argument("--modules", default="", help="comma separated module names; empty = library default")
    ap.add_argument("--suite", choices=["fluency", "fuzzy", "all"], default="all")
    ap.add_argument("--gens", default="3", help="generations to test, e.g. 3 or 3,5")
    ap.add_argument("--require", default="", help="comma separated schema ids that must be installed (else SKIP is a failure)")
    ap.add_argument("--json", default="")
    ap.add_argument("--no-deploy", action="store_true")
    a = ap.parse_args()

    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(os.path.dirname(os.path.abspath(a.lib)))
    rime = ctypes.CDLL(a.lib, mode=getattr(ctypes, "RTLD_GLOBAL", 0)) if os.name != "nt" else ctypes.CDLL(a.lib)
    for spec in a.preload_plugin:
        path, _, sym = spec.rpartition(":")
        plug = ctypes.CDLL(path, mode=getattr(ctypes, "RTLD_GLOBAL", 0))
        getattr(plug, sym)()
    mods = [m.strip().encode() for m in a.modules.split(",") if m.strip()]
    arr = (c_char_p * (len(mods) + 1))(*mods, None) if mods else None

    rime.rime_get_api.restype = POINTER(RimeApi)
    api = rime.rime_get_api().contents   # Squirrel/Weasel builds export only this entry point

    os.makedirs(os.path.join(a.user, "log"), exist_ok=True)
    keep = []
    def b(s):
        x = s.encode("utf-8"); keep.append(x); return x
    t = Traits()
    t.data_size = sizeof(Traits) - sizeof(c_int)
    t.shared_data_dir = b(a.shared) if a.shared else None
    t.user_data_dir = b(a.user)
    t.app_name = b"rime.cj-headless"
    t.distribution_name = b"cj-headless"
    t.modules = arr
    t.min_log_level = 1
    t.log_dir = b(os.path.join(a.user, "log"))
    api.setup(byref(t))
    api.initialize(byref(t))
    t0 = time.time()
    if not a.no_deploy:
        api.start_maintenance(1)
        api.join_maintenance_thread()
    deploy_s = round(time.time() - t0, 1)
    sid = api.create_session()

    def ctx_cands():
        c = Context()
        c.data_size = sizeof(Context) - sizeof(c_int)
        if not api.get_context(sid, byref(c)):
            return []
        out = [(c.menu.candidates[i].text or b"").decode("utf-8") for i in range(c.menu.num_candidates)]
        api.free_context(byref(c))
        return out

    def type_keys(schema, keys):
        if not api.select_schema(sid, schema.encode()):
            return None
        api.clear_composition(sid)
        for k in keys:
            api.process_key(sid, 0x20 if k == " " else ord(k), 0)
        allc = ctx_cands()
        for _ in range(60):  # following pages
            c = Context()
            c.data_size = sizeof(Context) - sizeof(c_int)
            if not api.get_context(sid, byref(c)):
                break
            last = c.menu.is_last_page
            api.free_context(byref(c))
            if last or not api.process_key(sid, 0xff56, 0):
                break
            allc.extend(ctx_cands())
        api.clear_composition(sid)
        return allc

    installed = {}
    def has_schema(sid_name):
        if sid_name not in installed:
            installed[sid_name] = os.path.exists(os.path.join(a.user, sid_name + ".schema.yaml"))
        return installed[sid_name]

    required = {x.strip() for x in a.require.split(",") if x.strip()}
    results, fails, skips = [], 0, 0
    for g in [x.strip() for x in a.gens.split(",") if x.strip()]:
        gname = "cangjie" + g
        for suite, schema_t, keys, kind, val in CASES:
            if a.suite != "all" and suite != a.suite:
                continue
            if g == "5" and keys in ("yhmbc", "yhmbv", "yhnbc", "yhnbv", "yhmbp", "mwyl"):
                continue  # the 5th-generation code of 顏 is not asserted here
            schema = schema_t.format(g=gname)
            r = {"schema": schema, "keys": keys, "kind": kind, "expect": val.format(g=gname)}
            if not has_schema(schema):
                r["status"] = "FAIL" if schema in required else "SKIP"
                r["note"] = "schema not installed"
                skips += r["status"] == "SKIP"
                fails += r["status"] == "FAIL"
                results.append(r)
                continue
            cands = type_keys(schema, keys)
            if cands is None:
                r.update(status="FAIL", note="select schema failed (deploy error?)"); fails += 1; results.append(r); continue
            r["top"] = cands[0] if cands else None
            r["first5"] = cands[:5]
            if kind == "top":
                ok = bool(cands) and cands[0] == r["expect"]
            elif kind == "has":
                ok = r["expect"] in cands
            elif kind == "lacks":
                ok = r["expect"] not in cands
            else:  # same_top
                ref = type_keys(r["expect"], keys)
                r["ref_top"] = ref[0] if ref else None
                ok = bool(cands) and bool(ref) and cands[0] == ref[0]
            r["status"] = "PASS" if ok else "FAIL"
            fails += not ok
            results.append(r)

    for r in results:
        extra = r.get("note") or ("top=%s first5=%s" % (r.get("top"), "".join(r.get("first5", []))))
        print("%-4s %-18s %-8s %-9s expect=%s  %s" % (r["status"], r["schema"], r["keys"], r["kind"], r["expect"], extra))
    passed = sum(r["status"] == "PASS" for r in results)
    print("deploy %.1fs | passed: %d  failed: %d  skipped: %d" % (deploy_s, passed, fails, skips))
    if a.json:
        json.dump({"results": results, "passed": passed, "failed": fails, "skipped": skips, "deploy_s": deploy_s},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    api.destroy_session(sid)
    api.finalize()
    sys.exit(1 if fails or passed == 0 else 0)


if __name__ == "__main__":
    main()
