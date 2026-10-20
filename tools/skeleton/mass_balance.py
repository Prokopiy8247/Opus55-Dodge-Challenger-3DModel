"""Exact mass balancing of the cell nodes against the stability measure (P3, decision D-031).

S = lambda_max(M^-1 (dt^2 K + 2 dt C + D)) (tools/skeleton/stability.py). For a mode with mass-normalised shape phi,
d lambda / d m_i = -lambda phi_i^2: adding mass where the top modes move most lowers S fastest. Each iteration builds the
skeleton, takes the modes above the target and raises the weight multipliers of the cage nodes in proportion to their
participation; the cell mass total and the 57 / 43 tilt are kept by hskel.distribute_mass. Multipliers are written to
tools/blender/hcar/hskel_mass_boost.json (read by hskel).

Usage: tools/.venv/Scripts/python.exe tools/skeleton/mass_balance.py [--target 2.3] [--iters 4] [--modes 16]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
sys.path.insert(0, str(ROOT / "tools" / "blender"))
from stability import beam_kc, load  # noqa: E402

OUT = ROOT / "tools" / "blender" / "hcar" / "hskel_mass_boost.json"


def matrix(g, p):
    dt = p.get("dt", 0.0005)
    mats = {m["name"]: m for m in p["materials"]}
    cm = {c["name"]: c for c in p.get("contactMaterials", [])}
    N = len(g["nodes"])
    P = np.array([n["p"] for n in g["nodes"]], float)
    m = np.array([n["m"] for n in g["nodes"]], float)
    rows, cols, vals = [], [], []
    for b in g["beams"]:
        k, c = beam_kc(mats[b["mat"]], b["type"])
        a_, b_ = b["a"], b["b"]
        d = P[b_] - P[a_]
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        blk = (dt * dt * k + 2 * dt * c) * np.outer(d / L, d / L)
        for (i, j, s) in ((a_, a_, 1), (b_, b_, 1), (a_, b_, -1), (b_, a_, -1)):
            for r in range(3):
                for q in range(3):
                    rows.append(3 * i + r)
                    cols.append(3 * j + q)
                    vals.append(s * blk[r, q])
    for i, n in enumerate(g["nodes"]):
        if n["flags"] & 4:
            c = cm.get(n["cmat"], {})
            an, zn = c.get("alphaNormal", 0.35), c.get("zetaNormal", 0.15)
            at, zt = c.get("alphaTangent", 0.3), c.get("zetaTangent", 0.15)
            v = max(an + 4 * zn * np.sqrt(an), at + 4 * zt * np.sqrt(at)) * m[i]
            for r in range(3):
                rows.append(3 * i + r)
                cols.append(3 * i + r)
                vals.append(v)
    A = sp.csr_matrix((vals, (rows, cols)), shape=(3 * N, 3 * N))
    Mi = sp.diags(np.repeat(1 / np.sqrt(m), 3))
    return Mi @ A @ Mi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=2.3)
    ap.add_argument("--iters", type=int, default=4)
    ap.add_argument("--modes", type=int, default=16)
    ap.add_argument("--gain", type=float, default=1.5)
    ns = ap.parse_args()
    from hcar import hskel  # noqa: E402
    boost = json.loads(OUT.read_text()) if OUT.exists() else {}
    for it in range(ns.iters + 1):
        hskel.main(viz=False)
        g, p = load("hellcat")
        names = [n["name"] for n in g["nodes"]]
        cage = set(json.loads((ROOT / "sim" / "vehicle" / "hellcat" / "skeleton_stats.json").read_text()).get("cage", []))
        w, v = eigsh(matrix(g, p), k=ns.modes, which="LA", tol=1e-6, maxiter=30000)
        order = np.argsort(-w)
        w, v = w[order], v[:, order]
        print(f"iter {it}: S top {np.round(w[:6], 4).tolist()}", flush=True)
        if it == ns.iters or w[0] <= ns.target:
            break
        push = np.zeros(len(names))
        for lam, vec in zip(w, v.T):
            if lam <= ns.target:
                continue
            part = np.sum(vec.reshape(-1, 3) ** 2, axis=1)
            push += (lam / ns.target - 1.0) * part / part.max()
        for i, nm in enumerate(names):
            if push[i] > 0.02 and (not cage or nm in cage) and g["nodes"][i]["part"] == "body":
                boost[nm] = round(min(boost.get(nm, 1.0) * (1.0 + ns.gain * push[i]), 4.0), 4)
        OUT.write_text(json.dumps(boost, indent=0, sort_keys=True), encoding="utf-8")
    print(f"{len(boost)} boosted nodes -> {OUT}")


if __name__ == "__main__":
    main()
