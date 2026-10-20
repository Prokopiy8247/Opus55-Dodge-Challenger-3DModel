"""Linear static sag and low modes of a skeleton (P3 structural check).

Static: K u = f with K the assembled beam stiffness (axial k n n^T; springs included, dampers and limit-only beams
not), f = node weights + the suspension spring preloads (internal forces that hold the body at ride height when the
body is rigid). The hub (axle) nodes are held vertically and a few nodes horizontally, so u is the sag of the body
relative to the wheel centres (structure + suspension). Prints the sag per node family.

Modes: the lowest eigenpairs of M^-1 K for the free structure (rigid modes skipped), to find soft body modes.

Usage: tools/.venv/Scripts/python.exe tools/skeleton/static_sag.py [vehicle] [--modes 8] [--json out.json]
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh, spsolve

ROOT = Path(__file__).resolve().parents[2]
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402


def family(name):
    key = re.split(r"\d", name, 1)[0].rstrip("_")
    return re.sub(r"^(FL|FR|RL|RR)_", "wheel_", key)


def assemble(g, p, include_springs=True):
    mats = {m["name"]: m for m in p["materials"]}
    N = len(g["nodes"])
    P = np.array([n["p"] for n in g["nodes"]], float)
    rows, cols, vals = [], [], []
    preload = np.zeros((N, 3))
    for b in g["beams"]:
        m = mats[b["mat"]]
        k = m.get("spring", 0.0) or 0.0
        if b["type"] == "HYDRO":
            pass
        if not include_springs and b["mat"].startswith("spring"):
            continue
        a, c = b["a"], b["b"]
        d = P[c] - P[a]
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        e = d / L
        pl = m.get("preload", 0.0) or 0.0
        if pl > 0:
            # compression force at the spawn length pushes the nodes apart
            preload[a] -= pl * e
            preload[c] += pl * e
        if k <= 0:
            continue
        blk = k * np.outer(e, e)
        for (i, j, s) in ((a, a, 1), (c, c, 1), (a, c, -1), (c, a, -1)):
            for r in range(3):
                for q in range(3):
                    rows.append(3 * i + r)
                    cols.append(3 * j + q)
                    vals.append(s * blk[r, q])
    K = sp.csr_matrix((vals, (rows, cols)), shape=(3 * N, 3 * N))
    return K, P, preload


def static_sag(g, p):
    K, P, preload = assemble(g, p)
    N = len(g["nodes"])
    m = np.array([n["m"] for n in g["nodes"]], float)
    gacc = p.get("gravity", 9.81)
    f = preload.copy()
    f[:, 1] -= m * gacc
    # supports: axle nodes fixed in y; x and z of the four inner axle nodes (removes the horizontal rigid modes)
    fixed = []
    for w in g["wheels"]:
        for n in (w["axleInner"], w["axleOuter"]):
            fixed.append(3 * n + 1)
        fixed += [3 * w["axleInner"], 3 * w["axleInner"] + 2]
    fixed = sorted(set(fixed))
    free = np.setdiff1d(np.arange(3 * N), fixed)
    Kf = K[free][:, free].tocsc()
    # light regularisation for mechanisms (nodes with too few beams); reported below
    eps = 1e-6 * Kf.diagonal().mean()
    u = np.zeros(3 * N)
    u[free] = spsolve(Kf + eps * sp.identity(len(free), format="csc"), f.ravel()[free])
    U = u.reshape(-1, 3)
    names = [n["name"] for n in g["nodes"]]
    fam = defaultdict(list)
    for i, nm in enumerate(names):
        fam[(g["nodes"][i]["part"], family(nm))].append(U[i, 1])
    out = sorted(((np.mean(v), k, len(v), np.min(v)) for k, v in fam.items()), key=lambda x: x[0])
    return U, out


def modes(g, p, k=8):
    K, P, _ = assemble(g, p)
    m = np.array([n["m"] for n in g["nodes"]], float)
    Minv = sp.diags(np.repeat(1.0 / np.sqrt(m), 3))
    A = Minv @ K @ Minv
    # shift-invert around a small negative sigma finds the lowest modes (rigid ones are ~0)
    w, v = eigsh(A, k=k + 6, sigma=-1.0, which="LM")
    order = np.argsort(w)
    w, v = w[order], v[:, order]
    res = []
    names = [n["name"] for n in g["nodes"]]
    for i in range(len(w)):
        f_hz = np.sqrt(max(w[i], 0.0)) / (2 * np.pi)
        amp = np.linalg.norm((Minv @ v[:, i]).reshape(-1, 3), axis=1)
        top = np.argsort(-amp)[:6]
        fams = defaultdict(float)
        for j in np.argsort(-amp)[:60]:
            fams[family(names[j])] += amp[j]
        res.append((f_hz, [names[j] for j in top], sorted(fams.items(), key=lambda kv: -kv[1])[:5]))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--modes", type=int, default=10)
    ap.add_argument("--json", default="")
    ns = ap.parse_args()
    g, p = load(ns.vehicle)
    U, out = static_sag(g, p)
    print("static sag relative to the wheel centres (mean / min dy per part, family):")
    for mean, key, n, mn in out[:30]:
        print(f"  {mean * 1000:8.1f} mm  min {mn * 1000:8.1f} mm  {key[0]:16s} {key[1]:14s} n={n}")
    body = [i for i, nd in enumerate(g["nodes"]) if nd["part"] == "body"]
    print(f"body part: mean {U[body, 1].mean() * 1000:.1f} mm, min {U[body, 1].min() * 1000:.1f} mm")
    if ns.modes > 0:
        print("lowest modes of the free skeleton:")
        for f_hz, top, fams in modes(g, p, ns.modes):
            print(f"  {f_hz:8.2f} Hz  {', '.join(top[:4])}  | {', '.join(f'{k}:{v:.2f}' for k, v in fams[:4])}")
    if ns.json:
        Path(ns.json).write_text(json.dumps({"body_mean_mm": float(U[body, 1].mean() * 1000),
                                             "body_min_mm": float(U[body, 1].min() * 1000),
                                             "families": [[float(a * 1000), list(b), c, float(d * 1000)] for a, b, c, d in out]},
                                            indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
