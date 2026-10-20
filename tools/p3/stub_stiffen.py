"""Prototype (P3): stiffen the suspension pick-up points and measure the knuckle wind-up stiffness and the low modes.

The body-side pick-ups (front lower / upper arm pivots, rear link inner pivots, rack ends and the anti-roll bar axis)
hang on a few soft beams, so the knuckles rotate fore-aft at 3 kN m/rad (a real corner is 50-300) and the parked car
rocks on its wheels at ~0.9 Hz with almost no damping (the dampers act vertically). This adds k extra beams from each
pick-up to the nearest structural nodes (B.anchor style, direction-diverse) and reports the change.

Usage: tools/.venv/Scripts/python.exe tools/p3/stub_stiffen.py [--k 4] [--maxd 0.45] [--mat subframe_mount]
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh, splu

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
from mechanisms import assemble  # noqa: E402

STRUCT = ("frail", "rail", "sill", "floor", "tunnel", "apron", "aplo", "core", "xm", "cowl", "fw", "hinge", "bp", "cp",
          "whouse", "rtower", "rrail", "rsub", "bulk", "shelf", "dash", "subframe", "tfloor", "rpanel", "bulk")


def anchors(g, names, idx, pickups, k, maxd, mat, existing):
    beams = []
    P = np.array([n["p"] for n in g["nodes"]], float)
    fam = lambda n: re.split(r"\d", n, 1)[0].rstrip("_")
    pool = [i for i, n in enumerate(g["nodes"]) if fam(n["name"]) in STRUCT and n["part"] == "body"]
    for a in pickups:
        pa = P[a]
        cand = []
        for i in pool:
            if i == a:
                continue
            d = P[i] - pa
            L = float(np.linalg.norm(d))
            if 0.02 <= L <= maxd and (min(a, i), max(a, i)) not in existing:
                cand.append((L, i, d / L))
        cand.sort(key=lambda c: c[0])
        chosen = []
        for L, i, u in cand:
            if not chosen:
                chosen.append((i, u))
            elif len(chosen) == 1:
                if abs(u @ chosen[0][1]) < 0.9:
                    chosen.append((i, u))
            else:
                nn = np.cross(chosen[0][1], chosen[1][1])
                nn /= np.linalg.norm(nn)
                if abs(u @ nn) > 0.35:
                    chosen.append((i, u))
            if len(chosen) >= k:
                break
        for i, _ in chosen:
            beams.append((a, i, mat))
    return beams


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--maxd", type=float, default=0.45)
    ap.add_argument("--mat", default="subframe_mount")
    ns = ap.parse_args()
    g, p = load("hellcat")
    names = [n["name"] for n in g["nodes"]]
    idx = {n: i for i, n in enumerate(names)}
    pickups = []
    for w in ("FL", "FR"):
        pickups += [idx[f"{w}_{k}"] for k in ("lca_f", "lca_r", "uca_f", "uca_r", "tre")]
    for w in ("RL", "RR"):
        pickups += [idx[f"{w}_link{n}"] for n in range(5)]
    pickups += [idx[n] for n in names if n.startswith(("rack_", "arbF_axis_", "arbR_axis_"))]
    existing = {(min(b["a"], b["b"]), max(b["a"], b["b"])) for b in g["beams"]}
    extra = anchors(g, names, idx, pickups, ns.k, ns.maxd, ns.mat, existing)
    print(f"{len(pickups)} pick-ups, {len(extra)} extra beams")
    K0 = assemble(g, p).tocsr()
    mats = {m["name"]: m for m in p["materials"]}
    N = len(g["nodes"])
    P = np.array([n["p"] for n in g["nodes"]], float)
    m = np.array([n["m"] for n in g["nodes"]], float)
    m[list(idx.values())] = np.maximum(m, 1e-6)
    rows, cols, vals = [], [], []
    for a, b, mat in extra:
        mm = mats[mat]
        k = mm.get("spring", 0.0) or 0.0
        d = P[b] - P[a]
        L = np.linalg.norm(d)
        e = d / L
        blk = k * np.outer(e, e)
        for (i, j, s) in ((a, a, 1), (b, b, 1), (a, b, -1), (b, a, -1)):
            for r in range(3):
                for q in range(3):
                    rows.append(3 * i + r)
                    cols.append(3 * j + q)
                    vals.append(s * blk[r, q])
    dK = sp.csr_matrix((vals, (rows, cols)), shape=(3 * N, 3 * N))
    for label, KK in (("before", K0), ("after", K0 + dK)):
        free = np.arange(N)
        dof = np.repeat(free * 3, 3) + np.tile([0, 1, 2], len(free))
        # wheel parts held (body on its suspension), reduced: modes of the body
        held = np.array([n["part"].startswith("wheel_") for n in g["nodes"]])
        free = np.where(~held)[0]
        dof = np.repeat(free * 3, 3) + np.tile([0, 1, 2], len(free))
        mi = np.repeat(1 / np.sqrt(m[free]), 3)
        A = (KK[dof][:, dof]).toarray() * mi[:, None] * mi[None, :]
        w2, V = np.linalg.eigh(A)
        f = np.sqrt(np.clip(w2, 0, None)) / 2 / np.pi
        keep = [i for i in range(len(f)) if f[i] > 0.5][:5]
        txt = ", ".join(f"{f[i]:.2f}" for i in keep)
        # wind-up of the front left knuckle
        cell = np.array([g["nodes"][i]["part"] == "body" and re.split(r"\d", names[i], 1)[0].rstrip("_") in
                         ("sill", "floor", "rail", "tunnel", "bp", "cp") for i in range(N)])
        wr = np.where(~cell)[0]
        wdof = np.repeat(wr * 3, 3) + np.tile([0, 1, 2], len(wr))
        lu = splu((KK[wdof][:, wdof] + 1e-6 * sp.identity(len(wdof))).tocsc())
        F = 100.0
        fv = np.zeros(3 * N)
        up, lo = idx["FL_ubj"], idx["FL_lbj"]
        fv[3 * up + 2] += F
        fv[3 * lo + 2] -= F
        u = np.zeros(3 * N)
        u[wdof] = lu.solve(fv[wdof])
        U = u.reshape(-1, 3)
        rot = (U[up, 2] - U[lo, 2]) / (P[up, 1] - P[lo, 1])
        print(f"  {label:6s}: first modes (wheel parts held) {txt} Hz; FL wind-up {F * (P[up, 1] - P[lo, 1]) / rot / 1000:.1f} kN m/rad")


if __name__ == "__main__":
    main()
