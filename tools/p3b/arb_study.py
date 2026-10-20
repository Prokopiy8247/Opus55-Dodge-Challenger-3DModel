"""P3b: effectiveness of the anti-roll bars (linear, cabin floor held): opposite vertical hub forces on one axle, wheel
travel with and without the bars, the bars' effective roll stiffness against the design (suspension_design.py), and
where the bar load path deforms (energy by material)."""
import copy
import re
import sys
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

sys.path.insert(0, "tools/skeleton")
from stability import load  # noqa: E402
import elastokinematics as ek  # noqa: E402

g, p = load("hellcat")
P = np.array([n["p"] for n in g["nodes"]], float)
N = len(P)
names = [n["name"] for n in g["nodes"]]
I = {n: i for i, n in enumerate(names)}
mats = {m["name"]: m for m in p["materials"]}


def dihedral_grad(x1, x2, x3, x4):
    b1, b2, b3 = x2 - x1, x3 - x2, x4 - x3
    n1, n2 = np.cross(b1, b2), np.cross(b2, b3)
    lb2 = np.linalg.norm(b2)
    g1 = -lb2 / np.dot(n1, n1) * n1
    g4 = lb2 / np.dot(n2, n2) * n2
    s1, s3 = np.dot(b1, b2) / lb2 ** 2, np.dot(b3, b2) / lb2 ** 2
    g2 = (s1 - 1) * g1 - s3 * g4
    g3 = (s3 - 1) * g4 - s1 * g1
    return [g1, g2, g3, g4]


def bars_matrix(scale=1.0, only=None):
    rows, cols, vals = [], [], []
    for tb in g["torsionBars"]:
        if only and tb["mat"] != only:
            continue
        k = mats[tb["mat"]]["spring"] * scale
        n = tb["n"]
        gr = dihedral_grad(*[P[i] for i in n])
        idx, gv = [], []
        for i, gi in zip(n, gr):
            idx += [3 * i, 3 * i + 1, 3 * i + 2]
            gv += list(gi)
        for a, ga in zip(idx, gv):
            for b, gb in zip(idx, gv):
                rows.append(a)
                cols.append(b)
                vals.append(k * ga * gb)
    return sp.csr_matrix((vals, (rows, cols)), shape=(3 * N, 3 * N))


K0, out = ek.assemble(g, p, P)
fixed = set()
for i, nd in enumerate(g["nodes"]):
    if out[i] or (nd["part"] == "body" and re.match(r"^(sill|floor|tunnel)", nd["name"])):
        fixed.update((3 * i, 3 * i + 1, 3 * i + 2))
free = np.array(sorted(set(range(3 * N)) - fixed))


def solve(K, f):
    Kf = K[free][:, free].tocsc()
    Kf = Kf + 1e-7 * Kf.diagonal().mean() * sp.identity(len(free), format="csc")
    u = np.zeros(3 * N)
    u[free] = splu(Kf).solve(f.ravel()[free])
    return u.reshape(-1, 3)


design = {"F": 75903.0, "R": 36733.0}      # bar roll stiffness at the wheels (N m/rad), suspension_design.py
for axle, (wr, wl), barmat in (("F", ("FR", "FL"), "arb_front"), ("R", ("RR", "RL"), "arb_rear")):
    wR = next(w for w in g["wheels"] if w["name"] == wr)
    wL = next(w for w in g["wheels"] if w["name"] == wl)
    F = 1000.0
    f = np.zeros((N, 3))
    for w, s in ((wR, 1.0), (wL, -1.0)):
        f[w["axleInner"], 1] += 0.5 * s * F
        f[w["axleOuter"], 1] += 0.5 * s * F
    hubs = lambda U: [0.5 * (U[w["axleInner"], 1] + U[w["axleOuter"], 1]) for w in (wR, wL)]
    track = abs(0.5 * (P[wR["axleInner"], 0] + P[wR["axleOuter"], 0]) - 0.5 * (P[wL["axleInner"], 0] + P[wL["axleOuter"], 0]))
    res = {}
    for label, Kb in (("springs", K0), ("springs + bars", K0 + bars_matrix(only=barmat))):
        U = solve(Kb, f)
        hR, hL = hubs(U)
        roll = (hR - hL) / track                     # rad per (F track) of roll moment
        Kroll = F * track / roll
        res[label] = (Kroll, U)
        print(f"[{axle}] {label:15s}: hub travel R {hR * 1000:+.2f} L {hL * 1000:+.2f} mm per kN -> roll stiffness {Kroll / 1000:.1f} kN m/rad")
    kb = res["springs + bars"][0] - res["springs"][0]
    print(f"    bar effective {kb / 1000:.1f} kN m/rad vs the design {design[axle] / 1000:.1f} ({kb / design[axle] * 100:.0f} %)")
    U = res["springs + bars"][1]
    en = ek.energy_by_material(g, p, P, U)
    tot = sum(en.values())
    print("    energy:", {k: round(v / tot, 3) for k, v in sorted(en.items(), key=lambda kv: -kv[1])[:8]})
