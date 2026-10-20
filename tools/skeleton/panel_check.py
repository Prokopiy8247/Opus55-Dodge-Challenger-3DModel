"""Panel and closure check of a skeleton (P3): linear static sag relative to the body cell and the modal damping of the
local modes, per node family. Static: tools/skeleton/load_paths.solve (wheel parts held, gravity + spring preloads);
the cell's best-fit rigid motion is removed so the numbers are the panels' own deflection. Modes: modal_damping.analyse.

Usage: tools/.venv/Scripts/python.exe tools/skeleton/panel_check.py [vehicle] [--fmax 60] [--json out.json]
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
from load_paths import solve  # noqa: E402
from modal_damping import analyse as modal  # noqa: E402

CELL = ("sill", "floor", "rail", "bulk", "tunnel", "shelf", "hinge", "bp", "cp", "whouse", "hdrF", "hdrR", "bowB", "cowl", "fw")


def fam(n):
    return re.split(r"\d", n, 1)[0].rstrip("_")


def relative_sag(g, u, P):
    """u minus the best-fit rigid motion of the cell nodes (small-rotation least squares)."""
    names = [n["name"] for n in g["nodes"]]
    cell = np.array([n["part"] == "body" and fam(nm) in CELL for n, nm in zip(g["nodes"], names)])
    c0 = P[cell].mean(0)
    r = P[cell] - c0
    # u = t + w x r  ->  linear least squares in (t, w)
    A = np.zeros((3 * cell.sum(), 6))
    for k, (x, y, z) in enumerate(r):
        A[3 * k:3 * k + 3, :3] = np.eye(3)
        A[3 * k:3 * k + 3, 3:] = [[0, z, -y], [-z, 0, x], [y, -x, 0]]
    sol, *_ = np.linalg.lstsq(A, u[cell].ravel(), rcond=None)
    t, w = sol[:3], sol[3:]
    rigid = t + np.cross(w, P - c0)
    return u - rigid, names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--fmax", type=float, default=60.0)
    ap.add_argument("--json", default="")
    ap.add_argument("--no-modes", action="store_true")
    ns = ap.parse_args()
    g, p = load(ns.vehicle)
    u, P, _ = solve(g, p)
    d, names = relative_sag(g, u, P)
    byf = defaultdict(list)
    for i, n in enumerate(names):
        byf[fam(n)].append(i)
    res = {"static": {}, "modes": {}}
    rows = []
    for f, idx in byf.items():
        dy = d[idx, 1]            # Unity frame: y up
        rows.append((float(dy.min()), f, len(idx), float(dy.mean()), float(np.linalg.norm(d[idx], axis=1).max())))
    rows.sort()
    print("static sag relative to the cell (mm): family, nodes, min dy, mean dy, max |d|")
    for mn, f, n, mean, mx in rows[:30]:
        print(f"  {f:22s} {n:4d}  {mn * 1000:8.1f}  {mean * 1000:8.1f}  {mx * 1000:8.1f}")
        res["static"][f] = {"min_dy_mm": round(mn * 1000, 2), "mean_dy_mm": round(mean * 1000, 2), "max_d_mm": round(mx * 1000, 2)}
    if not ns.no_modes:
        modes = modal(g, p, ns.fmax)
        first = {}
        low = defaultdict(int)
        for md in modes:
            fams = md["families"]
            tot = sum(v for _, v in fams) or 1.0
            f0, v0 = fams[0]
            if v0 / tot < 0.5:
                continue
            if md["zeta"] < 0.02:
                low[f0] += 1
            if f0 not in first:
                first[f0] = md
        print(f"\nlocal modes below {ns.fmax} Hz: family, first mode Hz, zeta, number of modes with zeta < 0.02")
        for f, md in sorted(first.items(), key=lambda kv: kv[1]["hz"]):
            print(f"  {f:22s} {md['hz']:7.2f} Hz  zeta {md['zeta']:.4f}  low-damped {low[f]:3d}  {md['nodes'][:3]}")
            res["modes"][f] = {"hz": round(md["hz"], 3), "zeta": round(md["zeta"], 4), "low_damped": low[f]}
        res["low_damped_total"] = int(sum(1 for md in modes if md["zeta"] < 0.02))
        print(f"\nmodes with zeta < 0.02 below {ns.fmax} Hz: {res['low_damped_total']} of {len(modes)}")
    if ns.json:
        Path(ns.json).write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
