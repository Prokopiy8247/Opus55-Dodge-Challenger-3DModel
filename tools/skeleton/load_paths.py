"""Static load-path check of a skeleton (P3): where does the body give under its own weight?

The wheel parts are held, the body carries gravity through the suspension (springs with their preloads). A weak
ground spring (100 N/m per node) keeps mechanisms bounded so they do not hide the global answer. Reports the sag
of the main structure families and the beams that store the most strain energy (the soft links of the load path).

Usage: tools/.venv/Scripts/python.exe tools/skeleton/load_paths.py [vehicle] [--top 40]
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
from mechanisms import assemble, family  # noqa: E402

REG = 0.01   # N/m per node: keeps the solve regular, negligible now that the skeleton has no mechanisms
MAIN = ["sill", "floor", "tunnel", "rail", "hinge", "fw", "cowl", "bp", "cp", "frail", "rrail", "aplo", "apron", "rtower",
        "whouse", "roof", "shelf", "bulk", "hdrF", "hdrR", "bowB", "rpanel_lo", "rpanel_hi", "tfloor", "xm", "rsub_m", "eng"]


def solve(g, p):
    mats = {m["name"]: m for m in p["materials"]}
    N = len(g["nodes"])
    P = np.array([n["p"] for n in g["nodes"]], float)
    m = np.array([n["m"] for n in g["nodes"]], float)
    K = assemble(g, p).tocsr()
    f = np.zeros((N, 3))
    f[:, 1] = -m * p.get("gravity", 9.81)
    for b in g["beams"]:
        pl = mats[b["mat"]].get("preload", 0.0) or 0.0
        if pl > 0:
            e = P[b["b"]] - P[b["a"]]
            e /= np.linalg.norm(e)
            f[b["a"]] -= pl * e
            f[b["b"]] += pl * e
    held = np.array([n["part"].startswith("wheel_") for n in g["nodes"]])
    free = np.where(~held)[0]
    dof = np.repeat(free * 3, 3) + np.tile([0, 1, 2], len(free))
    Kf = K[dof][:, dof] + REG * sp.identity(len(dof), format="csr")
    u = np.zeros(3 * N)
    u[dof] = spsolve(Kf.tocsc(), f.ravel()[dof])
    return u.reshape(-1, 3), P, mats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--top", type=int, default=40)
    ns = ap.parse_args()
    g, p = load(ns.vehicle)
    U, P, mats = solve(g, p)
    names = [n["name"] for n in g["nodes"]]
    fam = defaultdict(list)
    for i, nm in enumerate(names):
        fam[family(nm)].append(U[i, 1])
    print("sag of the main structure (mm, mean / min):")
    for f in MAIN:
        if f in fam:
            v = np.array(fam[f]) * 1000
            print(f"  {f:10s} {v.mean():8.1f} {v.min():8.1f}  n={len(v)}")
    # strain energy per beam
    E = []
    for j, b in enumerate(g["beams"]):
        k = mats[b["mat"]].get("spring", 0.0) or 0.0
        if k <= 0:
            continue
        d = P[b["b"]] - P[b["a"]]
        e = d / np.linalg.norm(d)
        x = np.dot(e, U[b["b"]] - U[b["a"]])
        E.append((0.5 * k * x * x, j, k * x))
    E.sort(reverse=True)
    tot = sum(e for e, _, _ in E)
    print(f"strain energy total {tot:.1f} J; top beams:")
    for e, j, F in E[:ns.top]:
        b = g["beams"][j]
        print(f"  {e:8.2f} J {100 * e / tot:5.1f} %  {names[b['a']]:>14s} - {names[b['b']]:<14s} {b['mat']:12s} force {F:9.0f} N")
    by = defaultdict(float)
    for e, j, _ in E:
        b = g["beams"][j]
        key = tuple(sorted((family(names[b["a"]]), family(names[b["b"]]))))
        by[key] += e
    print("strain energy by family pair:")
    for key, e in sorted(by.items(), key=lambda kv: -kv[1])[:25]:
        print(f"  {e:8.2f} J {100 * e / tot:5.1f} %  {key[0]} - {key[1]}")


if __name__ == "__main__":
    main()
