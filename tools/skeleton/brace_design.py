"""Brace design by compliance sensitivity (P3, decision D-030).

The body sagged several centimetres under its own weight: the front and rear structures are shallow trusses joined to
the cell through few members. This tool adds bracing beams where they reduce the static compliance most per unit of
stability cost:
  - static solve K u = f (gravity + spring preloads, wheel parts held, as tools/skeleton/load_paths.py);
  - for a candidate beam a-b of stiffness k the compliance falls by about k e^2, e = n_ab . (u_b - u_a) (truss topology
    sensitivity); its stability cost is about k (1/m_a + 1/m_b) dt^2; score = e^2 / (1/m_a + 1/m_b);
  - candidates: pairs of structure nodes 0.2-1.0 m apart inside the front structure (y > 0.74), the rear structure
    (y < -0.96) or the floor (z < 0.45), never across the door openings or the cabin;
  - greedy rounds: best candidates with distinct nodes, added in mirror pairs, re-solve, repeat.
Writes tools/blender/hcar/hskel_braces.json (node-name pairs), which hskel.py adds with the "brace" material.

Usage: tools/.venv/Scripts/python.exe tools/skeleton/brace_design.py [--rounds 4] [--per-round 12] [--k 600000]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
from mechanisms import assemble  # noqa: E402

OUT = ROOT / "tools" / "blender" / "hcar" / "hskel_braces.json"
STRUCT = ("sill", "floor", "tunnel", "rail", "hinge", "fw", "cowl", "bp", "cp", "frail", "rrail", "aplo", "apron",
          "rtower", "whouse", "shelf", "bulk", "rpanel_lo", "rpanel_hi", "tfloor", "xm", "core_lo", "core_hi")


def family(n):
    return re.split(r"\d", n, 1)[0].rstrip("_")


def zone(p):
    x, z, y = p[0], p[1], p[2]        # geometry.json is in Unity axes: x right, y up (index 1), z forward (index 2)
    if y > 0.74:
        return "front"
    if y < -0.96:
        return "rear"
    if z < 0.45:
        return "floor"
    return None


def solve(K, f, free, N):
    dof = np.repeat(free * 3, 3) + np.tile([0, 1, 2], len(free))
    Kf = K[dof][:, dof] + 0.01 * sp.identity(len(dof), format="csr")
    u = np.zeros(3 * N)
    u[dof] = spsolve(Kf.tocsc(), f.ravel()[dof])
    return u.reshape(-1, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--per-round", type=int, default=12)
    ap.add_argument("--k", type=float, default=600000.0)
    ap.add_argument("--keep", action="store_true", help="start from the existing hskel_braces.json")
    ns = ap.parse_args()
    g, p = load("hellcat")
    mats = {m["name"]: m for m in p["materials"]}
    names = [n["name"] for n in g["nodes"]]
    N = len(names)
    P = np.array([n["p"] for n in g["nodes"]], float)
    m = np.array([n["m"] for n in g["nodes"]], float)
    idx = {n: i for i, n in enumerate(names)}
    existing = {(min(b["a"], b["b"]), max(b["a"], b["b"])) for b in g["beams"]}
    braces = json.loads(OUT.read_text()) if ns.keep and OUT.exists() else []
    # gravity + spring preloads
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
    struct = [i for i, nm in enumerate(names) if family(nm) in STRUCT or nm.startswith(("core_lo", "core_hi"))]
    K0 = assemble(g, p).tocsr()

    def with_braces(K, bl):
        rows, cols, vals = [], [], []
        for a_n, b_n in bl:
            a, b = idx[a_n], idx[b_n]
            e = P[b] - P[a]
            e /= np.linalg.norm(e)
            blk = ns.k * np.outer(e, e)
            for (i, j, s) in ((a, a, 1), (b, b, 1), (a, b, -1), (b, a, -1)):
                for r in range(3):
                    for q in range(3):
                        rows.append(3 * i + r)
                        cols.append(3 * j + q)
                        vals.append(s * blk[r, q])
        return K + sp.csr_matrix((vals, (rows, cols)), shape=K.shape)

    def mirror(n):
        if n.endswith("_R"):
            return n[:-2] + "_L"
        if n.endswith("_L"):
            return n[:-2] + "_R"
        return n

    cand = []
    for ii, a in enumerate(struct):
        za = zone(P[a])
        if za is None:
            continue
        for b in struct[ii + 1:]:
            if zone(P[b]) != za or (min(a, b), max(a, b)) in existing:
                continue
            L = np.linalg.norm(P[b] - P[a])
            if not (0.2 <= L <= 1.0):
                continue
            if za == "floor" and abs(P[a][0]) > 0.05 and abs(P[b][0]) > 0.05 and P[a][0] * P[b][0] < 0:
                continue                                   # floor braces stay on one side of the tunnel
            cand.append((a, b))
    print(f"{len(cand)} candidate pairs")
    sel = {(min(idx[a], idx[b]), max(idx[a], idx[b])) for a, b in braces}

    def report(U, tag):
        fam = {}
        for i, nm in enumerate(names):
            fam.setdefault(family(nm), []).append(U[i, 1])
        print(f"  {tag}: " + ", ".join(f"{k} {np.mean(fam[k]) * 1000:.1f}" for k in ("sill", "floor", "tunnel", "rail", "roof",
                                                                                  "rrail", "rpanel_lo", "frail", "fw") if k in fam) + " mm")

    U = solve(with_braces(K0, braces), f, free, N)
    report(U, "start")
    for rnd in range(ns.rounds):
        scores = []
        for a, b in cand:
            if (a, b) in sel:
                continue
            e = P[b] - P[a]
            e /= np.linalg.norm(e)
            el = float(np.dot(e, U[b] - U[a]))
            scores.append((el * el / (1.0 / m[a] + 1.0 / m[b]), a, b))
        scores.sort(reverse=True)
        used = set()
        added = 0
        for sc, a, b in scores:
            if a in used or b in used:
                continue
            pair = (names[a], names[b])
            mpair = (mirror(names[a]), mirror(names[b]))
            for x, y in ([pair, mpair] if mpair != pair and set(mpair) != set(pair) else [pair]):
                key = (min(idx[x], idx[y]), max(idx[x], idx[y]))
                if key in sel or key in existing:
                    continue
                sel.add(key)
                braces.append([x, y])
                used |= {idx[x], idx[y]}
            added += 1
            if added >= ns.per_round:
                break
        U = solve(with_braces(K0, braces), f, free, N)
        report(U, f"round {rnd + 1} ({len(braces)} braces)")
    OUT.write_text(json.dumps(braces, indent=0), encoding="utf-8")
    print(f"wrote {OUT} with {len(braces)} braces")


if __name__ == "__main__":
    main()
