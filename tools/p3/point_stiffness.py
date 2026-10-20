"""Local static stiffness at nodes relative to the body cell (P3 structural check).

Unit load at a node along a car axis, balanced by inertia relief over the cell nodes (so the suspension carries no net
load), wheel parts held; the cell's best-fit rigid motion is removed from the displacement. k = 1 / relative deflection.
Usage: point_stiffness.py node[:x|y|z] ...   (car frame, default z = up)"""
import re, sys
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load
from mechanisms import assemble
from panel_check import relative_sag
g, p = load("hellcat")
K = assemble(g, p).tocsr()
N = len(g["nodes"])
P = np.array([n["p"] for n in g["nodes"]], float)
m = np.array([n["m"] for n in g["nodes"]], float)
names = [n["name"] for n in g["nodes"]]
idx = {n: i for i, n in enumerate(names)}
fam = lambda n: re.split(r"\d", n, 1)[0].rstrip("_")
CELL = ("sill", "floor", "rail", "bulk", "tunnel", "shelf", "hinge", "bp", "cp", "whouse", "hdrF", "hdrR", "bowB", "cowl", "fw")
cell = np.array([g["nodes"][i]["part"] == "body" and fam(names[i]) in CELL for i in range(N)])
held = np.array([n["part"].startswith("wheel_") for n in g["nodes"]])
free = np.where(~held)[0]
dof = np.repeat(free * 3, 3) + np.tile([0, 1, 2], len(free))
lu = splu((K[dof][:, dof] + 1e-6 * sp.identity(len(dof))).tocsc())
unity = {"x": 0, "y": 2, "z": 1}
for arg in sys.argv[1:]:
    nm, _, ax = arg.partition(":")
    ax = ax or "z"
    c = unity[ax]
    f = np.zeros((N, 3))
    f[idx[nm], c] += 1.0
    f[cell, c] -= m[cell] / m[cell].sum()
    u = np.zeros(3 * N)
    u[dof] = lu.solve(f.ravel()[dof])
    d, _ = relative_sag(g, u.reshape(-1, 3), P)
    k = 1.0 / d[idx[nm], c]
    mv = np.argsort(-np.linalg.norm(d, axis=1))[:6]
    print(f"{nm:22s} {ax}: k = {k / 1000:8.1f} kN/m;  moving: " + ", ".join(f"{names[i]} {np.linalg.norm(d[i]) * k:.2f}" for i in mv))
