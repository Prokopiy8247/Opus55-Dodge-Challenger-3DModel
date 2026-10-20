"""Mechanism check of a skeleton: zero-stiffness modes beyond the six rigid-body modes (P3 finding, decision D-030).

A node-beam structure is only rigid when its stiffness matrix K has rank 3N - 6. Every extra near-zero eigenvalue
is a mechanism: under gravity it sags until geometric nonlinearity stiffens it (cables), which made the Hellcat body
sit about 10 cm low in the first solver run. K holds the beams (axial k n n^T) plus the geometric stiffness of the
tire cord pre-tension (T / L transverse, computed like the solver, D-028), which is what makes the tread stable.

Prints the number of mechanisms and, per mechanism mode, the nodes that move most.
Usage: tools/.venv/Scripts/python.exe tools/skeleton/mechanisms.py [vehicle] [--k 60] [--hz 0.5] [--json out.json]
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
import hinges  # noqa: E402


def tire_pretension(g, p):
    """Beam index -> pre-tension (N) of the tire cords, the same linear static solve as the solver (D-028)."""
    mats = {m["name"]: m for m in p["materials"]}
    P = np.array([n["p"] for n in g["nodes"]], float)
    out = {}
    for pg in g.get("pressureGroups", []):
        tris = [g["triangles"][i] for i in pg["tris"]]
        cav = sorted({v for t in tris for v in (t["a"], t["b"], t["c"])})
        loc = {n: i for i, n in enumerate(cav)}
        f = np.zeros((len(cav), 3))
        for t in tris:
            a, b, c = P[t["a"]], P[t["b"]], P[t["c"]]
            s = 0.5 * np.cross(b - a, c - a)
            for v in (t["a"], t["b"], t["c"]):
                f[loc[v]] += pg["pressure"] * s / 3
        beams = [(j, b) for j, b in enumerate(g["beams"]) if b["a"] in loc and b["b"] in loc
                 and b["type"] not in ("HYDRO", "SUPPORT") and mats[b["mat"]].get("spring", 0) > 0]
        n = len(cav)
        K = np.zeros((3 * n, 3 * n))
        rows = []
        for j, b in beams:
            k = mats[b["mat"]]["spring"]
            ia, ib = loc[b["a"]], loc[b["b"]]
            d = P[b["b"]] - P[b["a"]]
            e = d / np.linalg.norm(d)
            blk = k * np.outer(e, e)
            for (r, c, s) in ((ia, ia, 1), (ib, ib, 1), (ia, ib, -1), (ib, ia, -1)):
                K[3 * r:3 * r + 3, 3 * c:3 * c + 3] += s * blk
            rows.append((j, ia, ib, e, k))
        eps = 1e-9 * np.trace(K) / (3 * n)
        u = np.linalg.solve(K + eps * np.eye(3 * n), f.ravel()).reshape(-1, 3)
        for (j, ia, ib, e, k) in rows:
            out[j] = k * np.dot(e, u[ib] - u[ia])
    return out


def assemble(g, p, geometric=True):
    mats = {m["name"]: m for m in p["materials"]}
    N = len(g["nodes"])
    P = np.array([n["p"] for n in g["nodes"]], float)
    pre = tire_pretension(g, p) if geometric else {}
    rows, cols, vals = [], [], []
    for j, b in enumerate(g["beams"]):
        m = mats[b["mat"]]
        k = m.get("spring", 0.0) or 0.0
        if b["type"] == "BOUNDED":
            k = max(k, 0.0)   # limit springs act only past a bound
        a, c = b["a"], b["b"]
        d = P[c] - P[a]
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        e = d / L
        blk = k * np.outer(e, e)
        t = pre.get(j, 0.0)
        if t > 0:
            blk = blk + t / L * (np.eye(3) - np.outer(e, e))
        if not blk.any():
            continue
        for (i, jj, s) in ((a, a, 1), (c, c, 1), (a, c, -1), (c, a, -1)):
            for r in range(3):
                for q in range(3):
                    rows.append(3 * i + r)
                    cols.append(3 * jj + q)
                    vals.append(s * blk[r, q])
    K = sp.csr_matrix((vals, (rows, cols)), shape=(3 * N, 3 * N))
    he = hinges.elements(g, p, P)        # panel shell bending (D-032)
    if he:
        K = K + hinges.matrix(N, he, "k")
    return K


def family(name):
    return re.split(r"\d", name, 1)[0].rstrip("_")


def analyse(g, p, k=60, hz=0.5):
    K = assemble(g, p)
    m = np.array([n["m"] for n in g["nodes"]], float)
    Mi = sp.diags(np.repeat(1.0 / np.sqrt(m), 3))
    A = (Mi @ K @ Mi).tocsc()
    w, v = eigsh(A, k=k, sigma=-1.0, which="LM")
    order = np.argsort(w)
    w, v = w[order], v[:, order]
    freq = np.sqrt(np.clip(w, 0, None)) / (2 * np.pi)
    names = [n["name"] for n in g["nodes"]]
    soft = [i for i in range(len(w)) if freq[i] < hz]
    modes = []
    for i in range(len(w)):
        x = (Mi @ v[:, i]).reshape(-1, 3)
        amp = np.linalg.norm(x, axis=1)
        amp /= amp.max()
        top = np.argsort(-amp)[:8]
        fams = defaultdict(float)
        for j in np.where(amp > 0.2)[0]:
            fams[family(names[j])] += amp[j]
        modes.append({"hz": round(float(freq[i]), 4), "nodes": [(names[j], round(float(amp[j]), 2)) for j in top],
                      "families": sorted(((kf, round(vf, 2)) for kf, vf in fams.items()), key=lambda kv: -kv[1])[:6],
                      "moving_nodes": int((amp > 0.2).sum())})
    return {"nodes": len(m), "mechanisms": max(0, len(soft) - 6), "soft_modes": len(soft), "threshold_hz": hz, "modes": modes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--k", type=int, default=60)
    ap.add_argument("--hz", type=float, default=0.5)
    ap.add_argument("--json", default="")
    ns = ap.parse_args()
    g, p = load(ns.vehicle)
    res = analyse(g, p, ns.k, ns.hz)
    print(f"{res['nodes']} nodes: {res['soft_modes']} modes below {ns.hz} Hz -> {res['mechanisms']} mechanisms beyond the 6 rigid modes")
    for i, md in enumerate(res["modes"]):
        print(f"  mode {i:2d} {md['hz']:9.4f} Hz  {md['moving_nodes']:4d} nodes  {', '.join(f'{a}:{b}' for a, b in md['nodes'][:5])}  | "
              f"{', '.join(f'{a}:{b}' for a, b in md['families'][:4])}")
    if ns.json:
        Path(ns.json).write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
