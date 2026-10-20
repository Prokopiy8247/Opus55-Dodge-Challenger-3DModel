"""P3b: chosen front package - K-member + rack ties + front knuckle beams on their own material + kingpin camber
element - compliance per kN (linear)."""
import copy
import sys
import numpy as np

sys.path.insert(0, "tools/skeleton")
sys.path.insert(0, "tools/p3b")
import front_struct_study as fs  # noqa: E402

g0, p0 = copy.deepcopy(fs.g), copy.deepcopy(fs.p)
names = [n["name"] for n in g0["nodes"]]


def setup(knuckle_f):
    g = copy.deepcopy(g0)
    p = copy.deepcopy(p0)
    for bm in g["beams"]:
        if bm["mat"] == "knuckle" and (names[bm["a"]].startswith(("FR_", "FL_")) or names[bm["b"]].startswith(("FR_", "FL_"))):
            bm["mat"] = "knuckle_f"
    mats = {m["name"]: m for m in p["materials"]}
    p["materials"].append(dict(mats["knuckle"], name="knuckle_f", spring=knuckle_f))
    fs.g, fs.p = g, p


print("---- chosen package")
for kf in (4e6, 6e6, 8e6):
    setup(kf)
    fs.run(f"kmember+racktie, knuckle_f {kf / 1e6:.0f}M, camber 80k", ["kmember", "racktie"], kc=80000.0, energy=(kf == 6e6))
setup(6e6)
fs.run("kmember+racktie, knuckle_f 6M, no camber element", ["kmember", "racktie"], kc=0.0)
