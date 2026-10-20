"""P3b (D-051): anti-roll-bar rates for the rebuilt skeleton - effective roll stiffness of springs and bars per axle
(linear, cabin floor held) for candidate torsion rates; target the design bar contributions (suspension_design.py:
front 75.9, rear 36.7 kN m/rad at the wheels)."""
import copy
import sys
import numpy as np

src = open("tools/p3b/arb_study.py", encoding="utf-8").read().split("design = {")[0]
ns = {"__name__": "x"}
exec(compile(src, "arb_study", "exec"), ns)
ek = ns["ek"]
g, p0 = ns["g"], ns["p"]
P = ns["P"]


def roll_k(p, axle):
    ns["mats"] = {m["name"]: m for m in p["materials"]}
    K0, _ = ek.assemble(g, p, P)
    wr, wl, barmat = {"F": ("FR", "FL", "arb_front"), "R": ("RR", "RL", "arb_rear")}[axle]
    wR = next(w for w in g["wheels"] if w["name"] == wr)
    wL = next(w for w in g["wheels"] if w["name"] == wl)
    f = np.zeros((len(P), 3))
    for w, s in ((wR, 1.0), (wL, -1.0)):
        f[w["axleInner"], 1] += 500 * s
        f[w["axleOuter"], 1] += 500 * s
    track = abs(0.5 * (P[wR["axleInner"], 0] + P[wR["axleOuter"], 0]) - 0.5 * (P[wL["axleInner"], 0] + P[wL["axleOuter"], 0]))
    out = []
    for Kb in (K0, K0 + ns["bars_matrix"](only=barmat)):
        U = ns["solve"](Kb, f)
        hR = 0.5 * (U[wR["axleInner"], 1] + U[wR["axleOuter"], 1])
        hL = 0.5 * (U[wL["axleInner"], 1] + U[wL["axleOuter"], 1])
        out.append(1000.0 * track / ((hR - hL) / track))
    return out[0], out[1] - out[0]


for af, ar in ((1960, 550), (1760, 1650), (1500, 1650), (1300, 1650), (1500, 1900)):
    p = copy.deepcopy(p0)
    for m in p["materials"]:
        if m["name"] == "arb_front":
            m["spring"] = af
        if m["name"] == "arb_rear":
            m["spring"] = ar
    sf, bf = roll_k(p, "F")
    sr, br = roll_k(p, "R")
    tot = sf + bf + sr + br
    grad = 1774 * 9.81 * 0.501 / tot
    print(f"arb_front {af:5.0f} arb_rear {ar:5.0f}: F springs {sf / 1000:5.1f} bar {bf / 1000:5.1f} | R springs {sr / 1000:5.1f} bar {br / 1000:5.1f} "
          f"kN m/rad; total {tot / 1000:.0f}, front share {(sf + bf) / tot * 100:.0f} %, roll {np.degrees(grad):.2f} deg/g (+ tires ~0.69)")
