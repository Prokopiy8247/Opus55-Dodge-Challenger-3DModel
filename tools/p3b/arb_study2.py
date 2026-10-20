"""P3b: anti-roll bar chain variants (linear): stiffer links / levers, the front pick node lower (deeper arm), the front
link on the lower ball joint."""
import copy
import sys
import numpy as np

sys.path.insert(0, "tools/p3b")
sys.argv = ["x"]
src = open("tools/p3b/arb_study.py", encoding="utf-8").read().split("design = {")[0]
ns = {}
exec(compile(src, "arb_study", "exec"), ns)
ek = ns["ek"]
base_g, base_p = copy.deepcopy(ns["g"]), copy.deepcopy(ns["p"])
design = {"F": 75903.0, "R": 36733.0}


def evaluate(label, g, p):
    ns["g"], ns["p"] = g, p
    ns["P"] = np.array([n["p"] for n in g["nodes"]], float)
    ns["mats"] = {m["name"]: m for m in p["materials"]}
    P = ns["P"]
    K0, out = ek.assemble(g, p, P)
    line = []
    for axle, (wr, wl), barmat in (("F", ("FR", "FL"), "arb_front"), ("R", ("RR", "RL"), "arb_rear")):
        wR = next(w for w in g["wheels"] if w["name"] == wr)
        wL = next(w for w in g["wheels"] if w["name"] == wl)
        f = np.zeros((len(P), 3))
        for w, s in ((wR, 1.0), (wL, -1.0)):
            f[w["axleInner"], 1] += 500 * s
            f[w["axleOuter"], 1] += 500 * s
        track = abs(0.5 * (P[wR["axleInner"], 0] + P[wR["axleOuter"], 0]) - 0.5 * (P[wL["axleInner"], 0] + P[wL["axleOuter"], 0]))
        ks = []
        for Kb in (K0, K0 + ns["bars_matrix"](only=barmat)):
            U = ns["solve"](Kb, f)
            hR = 0.5 * (U[wR["axleInner"], 1] + U[wR["axleOuter"], 1])
            hL = 0.5 * (U[wL["axleInner"], 1] + U[wL["axleOuter"], 1])
            ks.append(1000 * track / ((hR - hL) / track) / track)
        kb = ks[1] - ks[0]
        line.append(f"{axle}: springs {ks[0] / 1000:.1f} bars {kb / 1000:.1f} kN m/rad ({kb / design[axle] * 100:.0f} %)")
    print(f"{label:34s} " + " | ".join(line))


def mat(p, **kw):
    p = copy.deepcopy(p)
    for m in p["materials"]:
        if m["name"] in kw:
            m["spring"] = kw[m["name"]]
    return p


def move(g, name, dz_up):
    g = copy.deepcopy(g)
    for n in g["nodes"]:
        if n["name"] in (f"FR_{name}", f"FL_{name}"):
            n["p"][1] += dz_up
    return g


def relink(g, to="lbj"):
    g = copy.deepcopy(g)
    I = {n["name"]: i for i, n in enumerate(g["nodes"])}
    for b in g["beams"]:
        if b["mat"] == "arb_link":
            for s in ("R", "L"):
                if I[f"F{s}_lca_sh"] in (b["a"], b["b"]):
                    if b["a"] == I[f"F{s}_lca_sh"]:
                        b["a"] = I[f"F{s}_{to}"]
                    else:
                        b["b"] = I[f"F{s}_{to}"]
    return g


evaluate("as is", base_g, base_p)
evaluate("link 4M", base_g, mat(base_p, arb_link=4e6))
evaluate("link 4M lever 4M", base_g, mat(base_p, arb_link=4e6, arb_lever=4e6))
evaluate("lsh 0.10 m lower", move(base_g, "lca_sh", -0.10), base_p)
evaluate("lsh lower + link/lever 4M", move(base_g, "lca_sh", -0.10), mat(base_p, arb_link=4e6, arb_lever=4e6))
evaluate("front link on the lbj + 4M", relink(base_g), mat(base_p, arb_link=4e6, arb_lever=4e6))
evaluate("... + subframe 3M", relink(base_g), mat(base_p, arb_link=4e6, arb_lever=4e6, subframe=3e6))

print("---- with the factor track (absolute, kN m/rad at the wheels): multiply the numbers above by the track (~1.62 m)")
gl = relink(base_g)
for fr, rr in ((1.0, 2.0), (1.0, 3.0), (0.8, 2.0), (0.8, 3.0)):
    evaluate(f"front on lbj, links 4M, bars F x{fr} R x{rr}", gl,
             mat(base_p, arb_link=4e6, arb_lever=4e6, arb_front=1960 * fr, arb_rear=550 * rr))
