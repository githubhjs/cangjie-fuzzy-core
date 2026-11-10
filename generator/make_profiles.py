#!/usr/bin/env python3
"""Generate the desktop Rime fuzzy packages for any range (theta) and per-code tolerance, from the same geometry the matcher uses.

usage: make_profiles.py [--theta 1.0 1.3 1.8] [--gens 3 5] [--tolerance 1] [--base-dir DIR_WITH_cangjieN_fluency.schema.yaml] [--out DIR]
  default: the three shipped profiles into packages/pc-narrow (1.0), packages/pc (1.3, the default) and packages/pc-wide (1.8)
Any other value works: e.g. `make_profiles.py --theta 1.5 --out /tmp/mine` writes /tmp/mine/pc-theta1.5/.
--tolerance 2 allows two wrong keys per code; it multiplies the index size (study: <0.5 point more recovery, 3-4x more noise).
"""
import argparse, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
from core import qwerty_pc

NAMES = {1.0: "pc-narrow", 1.3: "pc", 1.8: "pc-wide"}
PROFILE_LABEL = {1.0: "pc \u7a84\u7bc4\u570d", 1.3: "pc", 1.8: "pc \u5bec\u7bc4\u570d"}

ap = argparse.ArgumentParser()
ap.add_argument("--theta", type=float, nargs="+", default=[1.0, 1.3, 1.8])
ap.add_argument("--gens", nargs="+", default=["3", "5"])
ap.add_argument("--tolerance", type=int, default=1)
ap.add_argument("--base-dir", default=os.environ.get("CJF_MAIN", "/home/hjs/projects/cangjie-fluency") + "/weasel")
ap.add_argument("--out", default=os.path.join(ROOT, "packages"))
a = ap.parse_args()

layout = qwerty_pc()
for th in a.theta:
    name = NAMES.get(th, "pc-theta%g" % th)
    if a.tolerance != 1:
        name += "-tol%d" % a.tolerance
    out = os.path.join(a.out, name)
    with tempfile.TemporaryDirectory() as td:
        mp = os.path.join(td, "map.json")
        json.dump(layout.table(th), open(mp, "w"))
        for g in a.gens:
            subprocess.run([sys.executable, os.path.join(HERE, "package_fuzzy.py"), "--map", mp, "--out", out, "--profile-name",
                            PROFILE_LABEL.get(th, "pc \u03b8=%g" % th), "--gen", g, "--tolerance", str(a.tolerance),
                            "--src", os.path.join(a.base_dir, "cangjie%s_fluency.schema.yaml" % g)], check=True, stdout=subprocess.DEVNULL)
    print("theta %g -> %s" % (th, out))
