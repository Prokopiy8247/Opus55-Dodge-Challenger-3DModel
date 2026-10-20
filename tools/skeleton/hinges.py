"""Shell bending hinges of a skeleton (decision D-032), shared by the Python analysis tools.

A hinge [n1, n2, n3, n4] resists the change of the dihedral angle across the edge n2-n3 of the triangles (n1, n2, n3)
and (n2, n3, n4); the solver kernel is Hellcat.Sim.TorsionKernel / HingeForceJob. Per hinge the plate values of its
material (params.json "hingeMaterials": bend D in N m, damp in N m s) are scaled by the triangle geometry:
    k = D |e|^2 / (A1 + A2) * GEOMETRY        (same for the damping),
and its linearised stiffness / damping matrices are k g g^T / c g g^T with g = dphi/dx (12-vector).

GEOMETRY (= HingeConst.Geometry in HingeJob.cs) is calibrated so a simply supported square plate meshed like the
panel grids (cells split along one diagonal) sags like the Kirchhoff plate: w_max = 0.00406 q a^4 / D.

Usage: tools/.venv/Scripts/python.exe tools/skeleton/hinges.py --calibrate [--n 17]
"""
import argparse

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

GEOMETRY = 0.56


def gradient(x1, x2, x3, x4):
    """Dihedral angle phi and its gradient (4 x 3) as Hellcat.Sim.TorsionKernel.Gradient; None if degenerate."""
    b1, b2, b3 = x2 - x1, x3 - x2, x4 - x3
    n1, n2 = np.cross(b1, b2), np.cross(b2, b3)
    lb2 = np.linalg.norm(b2)
    nn1, nn2 = n1 @ n1, n2 @ n2
    if lb2 < 1e-6 or nn1 < 1e-14 or nn2 < 1e-14:
        return None
    phi = np.arctan2(lb2 * (b1 @ n2), n1 @ n2)
    g1 = -lb2 / nn1 * n1
    g4 = lb2 / nn2 * n2
    s1 = (b1 @ b2) / (lb2 * lb2)
    s3 = (b3 @ b2) / (lb2 * lb2)
    g2 = -(1.0 + s1) * g1 + s3 * g4
    g3 = -(g1 + g2 + g4)
    return phi, np.array([g1, g2, g3, g4])


def scale(P, n):
    """|e|^2 / (A1 + A2) * GEOMETRY for the hinge n at positions P."""
    x1, x2, x3, x4 = (P[i] for i in n)
    e2 = float((x3 - x2) @ (x3 - x2))
    area = 0.5 * (np.linalg.norm(np.cross(x2 - x1, x3 - x1)) + np.linalg.norm(np.cross(x3 - x4, x2 - x4)))
    return GEOMETRY * e2 / max(area, 1e-12)


def elements(g, p, P=None):
    """[(nodes, k, c, gradient 4x3)] of the hinges of a skeleton (geometry dict g, params dict p)."""
    P = np.array([n["p"] for n in g["nodes"]], float) if P is None else P
    mats = {m["name"]: m for m in p.get("hingeMaterials", [])}
    out = []
    for h in g.get("hinges", []):
        n = h["n"]
        m = mats[h["mat"]]
        gr = gradient(*(P[i] for i in n))
        if gr is None:
            continue
        s = scale(P, n)
        out.append((n, m.get("bend", 0.0) * s, max(m.get("damp", 0.0), 0.0) * s, gr[1]))
    return out


def matrix(N, elems, which="k"):
    """Sparse 3N x 3N matrix sum w g g^T of the hinge elements (which: "k" stiffness, "c" damping)."""
    rows, cols, vals = [], [], []
    for n, k, c, G in elems:
        w = k if which == "k" else c
        if w == 0.0:
            continue
        dof = np.array([3 * i + r for i in n for r in range(3)])
        gv = G.ravel()
        blk = w * np.outer(gv, gv)
        rows.append(np.repeat(dof, 12))
        cols.append(np.tile(dof, 12))
        vals.append(blk.ravel())
    if not rows:
        return sp.csr_matrix((3 * N, 3 * N))
    return sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(3 * N, 3 * N))


def grid_hinges(ids, tris):
    """Hinges of one triangulated grid: every edge shared by exactly two of its triangles (wing, e0, e1, wing)."""
    edges = {}
    for t in tris:
        for k in range(3):
            a, b, c = t[k], t[(k + 1) % 3], t[(k + 2) % 3]
            edges.setdefault((min(a, b), max(a, b)), []).append(c)
    out = []
    for (a, b), opp in sorted(edges.items()):
        if len(opp) == 2 and opp[0] != opp[1]:
            out.append((opp[0], a, b, opp[1]))
    return out


def calibrate(n=17, a=1.0, D=100.0, q=100.0):
    """Centre deflection of a simply supported square plate (hinges only, out-of-plane) vs Kirchhoff."""
    xs = np.linspace(0.0, a, n)
    P = np.array([[x, y, 0.0] for x in xs for y in xs])
    idx = np.arange(n * n).reshape(n, n)
    tris = []
    for i in range(n - 1):
        for j in range(n - 1):
            A, B, C, Dn = idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]
            tris += [(A, B, C), (A, C, Dn)]
    hs = grid_hinges(idx, tris)
    g = {"nodes": [{"p": list(p)} for p in P], "hinges": [{"n": list(h), "mat": "m"} for h in hs]}
    prm = {"hingeMaterials": [{"name": "m", "bend": D, "damp": 0.0}]}
    K = matrix(len(P), elements(g, prm, P)).tocsr()
    zd = np.arange(len(P)) * 3 + 2
    Kz = K[zd][:, zd]
    h = a / (n - 1)
    f = np.full(len(P), q * h * h)
    edge = np.zeros(len(P), bool)
    edge[idx[0]] = edge[idx[-1]] = edge[idx[:, 0]] = edge[idx[:, -1]] = True
    f[edge] = 0.0
    free = np.where(~edge)[0]
    w = np.zeros(len(P))
    w[free] = spsolve(Kz[free][:, free].tocsc(), f[free])
    w_model = w[idx[n // 2, n // 2]]
    w_plate = 0.00406 * q * a ** 4 / D
    return w_model, w_plate, len(hs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--n", type=int, default=17)
    ns = ap.parse_args()
    if ns.calibrate:
        for n in (9, ns.n, 33):
            wm, wp, nh = calibrate(n)
            print(f"n={n:3d}: {nh} hinges, centre sag {wm * 1000:.3f} mm with GEOMETRY={GEOMETRY}, Kirchhoff "
                  f"{wp * 1000:.3f} mm -> ratio {wm / wp:.4f} (calibrated GEOMETRY = {GEOMETRY * wm / wp:.4f})")


if __name__ == "__main__":
    main()
