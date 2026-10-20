"""Prototype of the tire cord pre-tension (form finding, decision D-028) on the exported skeleton.

The tire cavity is closed and pressurized. Without pre-tension the beams sit at their rest length at spawn,
so the pressure would inflate the tire until the beams balance it. With pre-tension every beam between two
cavity nodes carries, at the spawn shape, the force the linear elastic structure would carry under the
pressure load (minimum complementary energy, i.e. the linear static solution K u = f, t = k n.du), so the
spawn shape is an equilibrium of pressure + cord tension.

Usage: tools/.venv/Scripts/python.exe tools/p3/proto_tire_pretension.py [wheel FR]
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import strip_comments  # noqa: E402


def main():
    wheel = sys.argv[1] if len(sys.argv) > 1 else "FR"
    d = ROOT / "sim" / "vehicle" / "hellcat"
    g = json.loads((d / "geometry.json").read_text(encoding="utf-8"))
    p = json.loads(strip_comments((d / "params.json").read_text(encoding="utf-8")))
    mats = {m["name"]: m for m in p["materials"]}
    P = np.array([n["p"] for n in g["nodes"]], float)
    pg = next(x for x in g["pressureGroups"] if x["wheel"] == wheel)
    tris = [g["triangles"][i] for i in pg["tris"]]
    cav = sorted({v for t in tris for v in (t["a"], t["b"], t["c"])})
    loc = {n: i for i, n in enumerate(cav)}
    pres = pg["pressure"]
    f = np.zeros((len(cav), 3))
    vol = 0.0
    o = P[cav].mean(0)
    for t in tris:
        a, b, c = P[t["a"]], P[t["b"]], P[t["c"]]
        s = 0.5 * np.cross(b - a, c - a)
        for v in (t["a"], t["b"], t["c"]):
            f[loc[v]] += pres * s / 3
        vol += np.dot(a - o, np.cross(b - o, c - o)) / 6
    print(f"cavity {wheel}: {len(tris)} tris, {len(cav)} nodes, V = {vol * 1000:.2f} l, |sum f| = {np.abs(f.sum(0)).max():.3g} N, "
          f"|sum x x f| = {np.abs(np.cross(P[cav], f).sum(0)).max():.3g} N m")
    beams = [(j, b) for j, b in enumerate(g["beams"]) if b["a"] in loc and b["b"] in loc]
    n = len(cav)
    K = np.zeros((3 * n, 3 * n))
    rows = []
    for j, b in beams:
        k = mats[b["mat"]]["spring"]
        ia, ib = loc[b["a"]], loc[b["b"]]
        dvec = P[b["b"]] - P[b["a"]]
        L = np.linalg.norm(dvec)
        e = dvec / L
        blk = k * np.outer(e, e)
        for (r, c, s) in ((ia, ia, 1), (ib, ib, 1), (ia, ib, -1), (ib, ia, -1)):
            K[3 * r:3 * r + 3, 3 * c:3 * c + 3] += s * blk
        rows.append((j, b["mat"], ia, ib, e, k, L))
    eps = 1e-9 * np.trace(K) / (3 * n)
    u = np.linalg.solve(K + eps * np.eye(3 * n), f.ravel()).reshape(-1, 3)
    ev = np.linalg.eigvalsh(K)
    print(f"beams in the cavity set: {len(beams)}; stiffness eigenvalues: {np.sum(ev < 1e-6 * ev.max())} near zero "
          f"(6 = rigid modes only), smallest nonzero {ev[ev > 1e-6 * ev.max()].min():.3g} N/m")
    t = np.array([k * np.dot(e, u[ib] - u[ia]) for (_, _, ia, ib, e, k, _) in rows])
    # residual of the pretension equilibrium at the spawn shape
    res = f.copy()
    for (row, tj) in zip(rows, t):
        _, _, ia, ib, e, _, _ = row
        res[ia] += tj * e
        res[ib] -= tj * e
    print(f"pre-tension residual max {np.abs(res).max():.3g} N (pressure force per node up to {np.abs(f).max():.0f} N)")
    by = {}
    for (row, tj) in zip(rows, t):
        by.setdefault(row[1], []).append((tj, tj / row[5] / row[6]))
    for m, vals in sorted(by.items()):
        tt = np.array([v[0] for v in vals])
        st = np.array([v[1] for v in vals])
        print(f"  {m:16s} n={len(vals):3d} tension {tt.min():8.0f} .. {tt.max():8.0f} N   strain t/(kL) {st.min():6.2f} .. {st.max():6.2f}")
    # inflation growth without pre-tension (linear estimate): radial displacement of the tread rows
    ax = np.array(P[g["wheels"][[w["name"] for w in g["wheels"]].index(wheel)]["axleInner"]])
    names = [g["nodes"][i]["name"] for i in cav]
    for tag in ("trC", "trI", "trO", "rimO"):
        idx = [i for i, nm in enumerate(names) if f"_{tag}" in nm]
        rr = []
        for i in idx:
            r0 = P[cav[i]] - ax
            r0[0] = 0
            rr.append(np.dot(u[i], r0 / np.linalg.norm(r0)))
        print(f"  linear inflation growth of {tag}: radial {np.mean(rr) * 1000:.1f} mm (no pre-tension)")


if __name__ == "__main__":
    main()
