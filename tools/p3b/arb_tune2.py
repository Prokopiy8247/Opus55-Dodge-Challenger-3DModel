"""P3b (D-054): front anti-roll-bar rate for the lever tips back at x 0.62 that keeps the effective bar roll stiffness of
the tips-at-0.70 configuration (2250 / 825 N m/rad, X18 balance); linear, cabin floor held (tools/p3b/arb_tune.py)."""
import copy
import sys
import numpy as np

src = open("tools/p3b/arb_tune.py", encoding="utf-8").read().split("for af, ar in")[0]
ns = {"__name__": "x"}
exec(compile(src, "arb_tune", "exec"), ns)
g0 = ns["g"]
p0 = ns["p0"]


def with_tips(x):
    g = copy.deepcopy(g0)
    for n in g["nodes"]:
        if n["name"] in ("arbF_tip_R", "arbF_tip_L"):
            n["p"][0] = x if n["name"].endswith("R") else -x
    return g


def rates(g, af, ar):
    ns["g"] = g
    ns["P"] = np.array([n["p"] for n in g["nodes"]], float)
    p = copy.deepcopy(p0)
    for m in p["materials"]:
        if m["name"] == "arb_front":
            m["spring"] = af
        if m["name"] == "arb_rear":
            m["spring"] = ar
    sf, bf = ns["roll_k"](p, "F")
    sr, br = ns["roll_k"](p, "R")
    return sf, bf, sr, br


ref = rates(with_tips(0.70), 2250, 825)
print("tips 0.70, 2250 / 825: F springs %.1f bar %.1f | R springs %.1f bar %.1f kN m/rad" % tuple(v / 1000 for v in ref))
g62 = with_tips(0.62)
for af in (2250, 3000, 3400, 3800, 4200):
    v = rates(g62, af, 825)
    tot = sum(v)
    print("tips 0.62, %4d / 825: F springs %.1f bar %.1f | R springs %.1f bar %.1f kN m/rad; front share %.0f %%" %
          (af, *(x / 1000 for x in v), (v[0] + v[1]) / tot * 100))
