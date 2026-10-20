"""P3b: as front_struct_study.py plus a rear knuckle node (brake-caliper mount 0.145 m behind the axle at hub height,
knuckle beams to the five knuckle nodes) and stiffer arms; geometry modified in memory."""
import copy
import sys
import numpy as np

sys.path.insert(0, "tools/skeleton")
sys.path.insert(0, "tools/p3b")
from stability import load  # noqa: E402
import elastokinematics as ek  # noqa: E402
import front_struct_study as fs  # noqa: E402  (runs its own table on import)


def with_knuckle_node(g0, dz=-0.145, dx=0.03):
    g = copy.deepcopy(g0)
    I = {n["name"]: i for i, n in enumerate(g["nodes"])}
    for s, sx in (("R", 1), ("L", -1)):
        ai, ao = I[f"F{s}_axle_in"], I[f"F{s}_axle_out"]
        hub = 0.5 * (np.array(g["nodes"][ai]["p"]) + np.array(g["nodes"][ao]["p"]))
        p = [float(sx * (abs(hub[0]) - dx)), float(hub[1] + 0.01), float(hub[2] + dz)]
        g["nodes"].append({"name": f"F{s}_kn_r", "p": p, "m": 1.0, "flags": 0, "cmat": "metal", "group": "k", "part": f"wheel_F{s}"})
        k = len(g["nodes"]) - 1
        for q in (ai, ao, I[f"F{s}_lbj"], I[f"F{s}_ubj"], I[f"F{s}_tre"]):
            g["beams"].append({"a": q, "b": k, "type": "NORMAL", "mat": "knuckle", "bg": "", "bgt": 0, "pre": 0.0})
    return g


g, p = load("hellcat")
gk = with_knuckle_node(g)
fs.g = gk
fs.P = np.array([n["p"] for n in gk["nodes"]], float)
fs.N = len(fs.P)
fs.I = {n["name"]: i for i, n in enumerate(gk["nodes"])}
print("---- with the rear knuckle node")
fs.run("knuckle node", [])
fs.run("knuckle node + kmember + racktie", ["kmember", "racktie"])
fs.run("knuckle node + kmember + racktie + camber 80k", ["kmember", "racktie"], kc=80000.0, energy=True)
p2 = copy.deepcopy(p)
for m in p2["materials"]:
    if m["name"] == "arm":
        m["spring"] = 5.0e6
fs.p = p2
fs.run("... + arms 5 MN/m", ["kmember", "racktie"], kc=80000.0, energy=True)
