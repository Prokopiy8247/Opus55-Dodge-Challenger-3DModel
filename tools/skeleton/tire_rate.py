"""Static vertical rate of a tire (P3b): rigid ground contact at the lowest tread node, increasing load, the hub held
vertically, so the deflection of the hub is the tire squash (tread ring + sidewall bending + cavity pressure).

The tread is a ring on sidewall and lateral cords, so its local contact stiffness is much softer than the pressure
stiffness alone: this solves the actual node-beam tire and reports the rate at the design load, which is what
tools/skeleton/suspension_design.py needs as --tire-rate (D-025 said the rate would be measured in P3).

Usage: tools/.venv/Scripts/python.exe tools/skeleton/tire_rate.py [vehicle] [--load 5704] [--json out.json]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402


def assemble_tire(g, p, wheel, N, hub):
    """Beam stiffness of the wheel's own structure plus the two axle nodes (hub), the rest of the car held fixed."""
    mats = {m["name"]: m for m in p["materials"]}
    P = np.array([n["p"] for n in g["nodes"]], float)
    nodes = set(wheel["rim"]) | set(wheel["tread"]) | {wheel["axleInner"], wheel["axleOuter"], wheel["arm"]}
    nodes.add(hub)
    rows, cols, vals = [], [], []
    for b in g["beams"]:
        if b["a"] not in nodes or b["b"] not in nodes:
            continue
        m = mats[b["mat"]]
        k = m.get("spring", 0.0) or 0.0
        if b["type"] == "BOUNDED":
            k = max(k, 0.0)
        if k <= 0:
            continue
        d = P[b["b"]] - P[b["a"]]
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        e = d / L
        blk = k * np.outer(e, e)
        for (i, j, s) in ((b["a"], b["a"], 1), (b["b"], b["b"], 1), (b["a"], b["b"], -1), (b["b"], b["a"], -1)):
            pass
        for (i, j, s) in ((b["a"], b["a"], 1.0), (b["b"], b["b"], 1.0), (b["a"], b["b"], -1.0), (b["b"], b["a"], -1.0)):
            for r in range(3):
                for q in range(3):
                    rows.append(3 * i + r)
                    cols.append(3 * j + q)
                    vals.append(s * blk[r, q])
    return sp.csr_matrix((vals, (rows, cols)), shape=(3 * N, 3 * N)), nodes, P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--load", type=float, default=5704.0, help="design corner load at the front (N)")
    ap.add_argument("--json", default="")
    ns = ap.parse_args()
    g, p = load(ns.vehicle)
    N = len(g["nodes"])
    names = [n["name"] for n in g["nodes"]]
    mats = {m["name"]: m for m in p["materials"]}
    out = {}
    for wheel in g["wheels"]:
        nm = wheel["name"] if "name" in wheel else wheel.get("name", "")
        hub = wheel["axleInner"]
        K, nodes, P = assemble_tire(g, p, wheel, N, hub)
        tread = wheel["tread"]
        ymin = min(P[i][1] for i in tread)
        bottom = [i for i in tread if P[i][1] < ymin + 0.02]
        # free: the wheel's own nodes; held: the hub sideways (the axle) and the bottom tread nodes vertically and
        # sideways (rigid ground), the loaded hub node free to move vertically
        free_nodes = []                    # (node, component)
        for i in sorted(nodes):
            for c in range(3):
                if i == hub and c == 1:
                    free_nodes.append((i, c))
                elif i == hub:
                    continue
                elif i in bottom:
                    continue
                else:
                    free_nodes.append((i, c))
        dof = np.array([3 * i + c for i, c in free_nodes])
        for i in bottom:                   # ground: normal and tangential anchor
            K[3 * i + 1, 3 * i + 1] += 1e6
            K[3 * i, 3 * i] += 1e6
            K[3 * i + 2, 3 * i + 2] += 1e6
        Kf = K[dof][:, dof] + 1e-6 * sp.identity(len(dof))
        lu = splu(Kf.tocsc())
        loads = np.array([500.0, 2000.0, ns.load, 8000.0])
        defl = []
        for F in loads:
            f = np.zeros(3 * N)
            f[3 * hub + 1] = F                    # the hub carries the corner load
            u = np.zeros(3 * N)
            u[dof] = lu.solve(f[dof])
            U = u.reshape(-1, 3)
            defl.append(-U[hub, 1])
        rate = ns.load / abs(defl[2]) if abs(defl[2]) > 1e-9 else float("nan")
        out[wheel["name"]] = {"rate_kN_per_m": rate / 1000.0,
                              "deflection_mm": [round(d * 1000, 2) for d in defl],
                              "loads_N": loads.tolist()}
        print(f"  {wheel['name']}: deflection at {loads.tolist()} N = {[round(d * 1000, 2) for d in defl]} mm, "
              f"rate at {ns.load:.0f} N = {rate / 1000:.1f} kN/m")
    if ns.json:
        Path(ns.json).write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
