"""Rotational stiffness of the suspension mounting structure relative to the cabin (P3, D-036).

The wind-up element puts a pure couple about the spin axis on each wheel's body set (link pivots, their mounts, the
spring tower). This applies that couple (f_i = (J^-1 T e) x r_i, as VehicleControlJob) to the body set of one wheel with
the cabin cell held (sill, floor, tunnel, cabin rails, posts), solves K u = f and reports the set's least-squares
rotation about the spin axis, i.e. the structure's own wind-up stiffness in series with the element, and the beams that
store the most strain energy (where the compliance is).

Usage: tools/.venv/Scripts/python.exe tools/p3/end_stiffness.py [FL|RL] [--top 14]
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
from mechanisms import assemble  # noqa: E402

CELL = ("sill", "floor", "tunnel", "rail", "bp", "cp", "hdrF", "hdrR", "post", "roof_rail", "bulk")


def set_frame(P, ids):
    c = P[ids].mean(0)
    r = P[ids] - c
    J = np.zeros((3, 3))
    for d in r:
        J += (d @ d) * np.eye(3) - np.outer(d, d)
    return c, r, J


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wheel", nargs="?", default="FL")
    ap.add_argument("--top", type=int, default=14)
    ns = ap.parse_args()
    g, p = load("hellcat")
    N = len(g["nodes"])
    names = [n["name"] for n in g["nodes"]]
    P = np.array([n["p"] for n in g["nodes"]], float)
    fam = lambda n: re.split(r"\d", n, 1)[0].rstrip("_")
    w = next(x for x in g["wheels"] if x["name"] == ns.wheel)
    body = np.array(w["windupBody"])
    e = P[w["axleOuter"]] - P[w["axleInner"]]
    e /= np.linalg.norm(e)
    cell = np.array([i for i in range(N) if g["nodes"][i]["part"] == "body" and fam(names[i]) in CELL
                     and fam(names[i]) != "rail" or names[i].startswith(("rail2", "rail3", "rail4", "rail5", "rail6", "rail7", "rail8"))])
    cell = np.array(sorted(set(cell.tolist()) - set(body.tolist())))
    K = assemble(g, p).tocsr()
    free = np.setdiff1d(np.arange(N), cell)
    # wheel parts float freely with nothing holding them: hold them too (only the structure is measured)
    wheel = np.array([i for i in range(N) if g["nodes"][i]["part"].startswith("wheel_")])
    free = np.setdiff1d(free, wheel)
    dof = np.repeat(free * 3, 3) + np.tile([0, 1, 2], len(free))
    lu = splu((K[dof][:, dof] + 1e-6 * sp.identity(len(dof))).tocsc())
    T = 1000.0
    c, r, J = set_frame(P, body)
    alpha = np.linalg.solve(J, T * e)
    f = np.zeros((N, 3))
    f[body] = np.cross(alpha, r)
    u = np.zeros(3 * N)
    u[dof] = lu.solve(f.ravel()[dof])
    U = u.reshape(-1, 3)
    # least-squares rotation of the set: w = J^-1 sum r x u
    L = np.cross(r, U[body] - U[body].mean(0)).sum(0)
    rot = np.linalg.solve(J, L) @ e
    print(f"{ns.wheel}: body set {len(body)} nodes, cabin cell held ({len(cell)} nodes); couple {T:.0f} N m about the spin "
          f"axis -> set rotation {rot * 1000:.3f} mrad -> structure wind-up stiffness {T / rot / 1000:.1f} kN m/rad")
    mats = {m["name"]: m for m in p["materials"]}
    energy = []
    for b in g["beams"]:
        k = mats[b["mat"]].get("spring", 0.0) or 0.0
        if k <= 0:
            continue
        d = P[b["b"]] - P[b["a"]]
        L0 = np.linalg.norm(d)
        if L0 < 1e-9:
            continue
        s = (U[b["b"]] - U[b["a"]]) @ (d / L0)
        energy.append((0.5 * k * s * s, names[b["a"]], names[b["b"]], b["mat"], s))
    tot = sum(x[0] for x in energy)
    energy.sort(reverse=True)
    print(f"strain energy {tot:.4f} J; top beams:")
    for en, a, bb, mat, s in energy[:ns.top]:
        print(f"   {100 * en / tot:5.1f} %  {a:14s} {bb:14s} {mat:16s} stretch {s * 1000:+.4f} mm")
    by_mat = {}
    for en, a, bb, mat, s in energy:
        by_mat[mat] = by_mat.get(mat, 0.0) + en
    print("by material:", ", ".join(f"{m} {100 * v / tot:.0f} %" for m, v in sorted(by_mat.items(), key=lambda kv: -kv[1])[:8]))


if __name__ == "__main__":
    main()
