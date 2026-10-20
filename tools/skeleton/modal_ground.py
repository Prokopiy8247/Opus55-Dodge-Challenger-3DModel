"""Whole-vehicle modes standing on the ground (P3): the tread nodes near the bottom of each tire get the contact penalty
springs of the solver (normal alpha_n m / dt^2, tangential anchor alpha_t m / dt^2, params.json contact material "tire"),
the brakes hold every wheel (holding spring between the rim and the knuckle about the axle, as VehicleControlJob), and
everything else is free: rigid-body modes on the tires and suspension (bounce, pitch, roll, fore-aft, yaw), wheel hop,
body modes. Damping: beams, hinges, damp groups (modal_damping.assemble_c) and the contact dampers.

Usage: tools/.venv/Scripts/python.exe tools/skeleton/modal_ground.py [vehicle] [--fmax 12] [--brake-k 4e5] [--free-wheels]
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
from mechanisms import assemble, family  # noqa: E402
from modal_damping import assemble_c  # noqa: E402
import hinges  # noqa: E402


def torsion_elements(g, p, P, extra=()):
    """Torsion bars of the skeleton (anti-roll bars) plus extra [(n1, n2, n3, n4, k, c)] as dihedral elements
    [(nodes, k, c, gradient)] (the hinge format: K += k g g^T, C += c g g^T)."""
    mats = {m["name"]: m for m in p["materials"]}
    out = []
    for t in g.get("torsionBars", []):
        m = mats[t["mat"]]
        gr = hinges.gradient(*(P[i] for i in t["n"]))
        if gr is not None:
            out.append((t["n"], m.get("spring", 0.0), max(m.get("damp", 0.0), 0.0), gr[1]))
    for n1, n2, n3, n4, k, c in extra:
        n = [n1, n2, n3, n4]
        gr = hinges.gradient(*(P[i] for i in n))
        if gr is not None:
            out.append((n, k, c, gr[1]))
    return out


def wheel_coupling(g, w, N):
    """Gradient g (3N) of theta_rim - theta_knuckle about the axle for one wheel (least-squares rotations)."""
    P = np.array([n["p"] for n in g["nodes"]], float)
    ai, ao = P[w["axleInner"]], P[w["axleOuter"]]
    axis = (ao - ai) / np.linalg.norm(ao - ai)
    knuckle = set()
    nb = defaultdict(set)
    for b in g["beams"]:
        nb[b["a"]].add(b["b"])
        nb[b["b"]].add(b["a"])
    skip = set(w["rim"]) | set(w["tread"]) | {w["axleInner"], w["axleOuter"]}
    for n in nb[w["axleInner"]] & nb[w["axleOuter"]]:
        if n in skip:
            continue
        r = P[n] - ai
        r -= (r @ axis) * axis
        if np.linalg.norm(r) > 0.02:
            knuckle.add(n)
    if not knuckle:
        knuckle = {w["arm"]}
    gv = np.zeros(3 * N)
    for nodes, sgn in ((w["rim"], 1.0), (sorted(knuckle), -1.0)):
        rs = []
        for n in nodes:
            r = P[n] - ai
            r -= (r @ axis) * axis
            rs.append(r)
        den = sum(r @ r for r in rs)
        for n, r in zip(nodes, rs):
            gv[3 * n:3 * n + 3] += sgn * np.cross(axis, r) / den
    return gv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--fmax", type=float, default=12.0)
    ap.add_argument("--brake-k", type=float, default=4e5, help="holding spring N m/rad per wheel")
    ap.add_argument("--free-wheels", action="store_true")
    ap.add_argument("--band", type=float, default=0.02, help="tread nodes this close to the lowest one touch (m)")
    ap.add_argument("--windup", default="", help="wind-up bars K,C (N m/rad, N m s/rad) per corner, e.g. 60000,20")
    ap.add_argument("--anchors", default="apron2,shelf68", help="body anchor families front,rear (+ _L/_R)")
    ap.add_argument("--push", action="store_true", help="static 0.25 g fore-aft push instead of the modes")
    ns = ap.parse_args()
    g, p = load(ns.vehicle)
    dt = p.get("dt", 0.0005)
    N = len(g["nodes"])
    P = np.array([n["p"] for n in g["nodes"]], float)
    m = np.array([n["m"] for n in g["nodes"]], float)
    names = [n["name"] for n in g["nodes"]]
    idx = {n: i for i, n in enumerate(names)}
    extra = []
    if ns.windup:
        kw, cw = (float(v) for v in ns.windup.split(","))
        af, ar = ns.anchors.split(",")
        for w in g["wheels"]:
            side = "L" if w["name"].endswith("L") else "R"
            wing = idx[f"{w['name']}_ubj"] if w["name"][0] == "F" else idx[f"{w['name']}_kup"]
            anchor = idx[f"{af if w['name'][0] == 'F' else ar}_{side}"]
            extra.append((wing, w["axleInner"], w["axleOuter"], anchor, kw, cw))
    te = torsion_elements(g, p, P, extra)
    K = (assemble(g, p) + hinges.matrix(N, te, "k")).tolil()
    C = (assemble_c(g, p) + hinges.matrix(N, te, "c")).tolil()
    cm = {c["name"]: c for c in p.get("contactMaterials", [])}.get("tire", {})
    an, zn = cm.get("alphaNormal", 0.35), cm.get("zetaNormal", 0.15)
    at, zt = cm.get("alphaTangent", 0.3), cm.get("zetaTangent", 0.15)
    touching = 0
    for w in g["wheels"]:
        tr = w["tread"]
        ymin = min(P[i][1] for i in tr)
        for i in tr:
            if P[i][1] > ymin + ns.band:
                continue
            touching += 1
            for c, (al, ze) in ((1, (an, zn)), (0, (at, zt)), (2, (at, zt))):
                K[3 * i + c, 3 * i + c] += al * m[i] / dt ** 2
                C[3 * i + c, 3 * i + c] += 2 * ze * m[i] * np.sqrt(al) / dt
        if not ns.free_wheels:
            gv = wheel_coupling(g, w, N)
            nz = np.nonzero(gv)[0]
            for a in nz:
                for b in nz:
                    K[a, b] += ns.brake_k * gv[a] * gv[b]
    K, C = K.tocsr(), C.tocsr()
    if ns.push:
        # static check (matches the solver's WD diagnostic): 0.25 g forward on the body nodes, brakes held
        from scipy.sparse.linalg import spsolve
        body_m = np.array([nd["part"] == "body" for nd in g["nodes"]])
        f = np.zeros(3 * N)
        F = 0.25 * 9.81 * m.sum()
        f[3 * np.where(body_m)[0] + 2] = F * m[body_m] / m[body_m].sum()
        u = spsolve((K + 1e-6 * sp.identity(3 * N)).tocsc(), f).reshape(-1, 3)
        com = (m[:, None] * u).sum(0) / m.sum()
        print(f"static push {F:.0f} N forward: CoM moves {com[2] * 1000:.2f} mm (solver WD: 36.6 mm), "
              f"k = {F / com[2] / 1000:.1f} kN/m")
        for w in g["wheels"][:3:2]:
            hub = 0.5 * (u[w["axleInner"]] + u[w["axleOuter"]])
            gk = wheel_coupling(g, w, N)            # d(theta_rim - theta_knuckle)
            ai = P[w["axleInner"]]
            ax = (P[w["axleOuter"]] - ai) / np.linalg.norm(P[w["axleOuter"]] - ai)
            def rotation(nodes):
                num = den = 0.0
                for i in nodes:
                    r = P[i] - ai
                    r -= (r @ ax) * ax
                    num += np.cross(r, u[i] - hub) @ ax
                    den += r @ r
                return num / den
            top = idx[f"{w['name']}_ubj"] if w["name"][0] == "F" else idx[f"{w['name']}_kup"]
            low = idx[f"{w['name']}_lbj"] if w["name"][0] == "F" else idx[f"{w['name']}_klr"]
            kn = [top, low]
            print(f"   {w['name']} rotations about the axle (mrad, + = ?): rim {rotation(w['rim']) * 1000:+.3f}, "
                  f"knuckle {rotation(kn) * 1000:+.3f}, tread {rotation(w['tread']) * 1000:+.3f}; "
                  f"brake coupling {gk @ u.ravel() * 1000:+.4f} mrad")
            print(f"   {w['name']} hub fwd {hub[2] * 1000:.2f} mm (vs CoM {(hub[2] - com[2]) * 1000:+.2f}), "
                  f"tread bottom fwd {u[[i for i in w['tread'] if P[i][1] < min(P[j][1] for j in w['tread']) + ns.band], 2].mean() * 1000:.3f} mm")
        return
    mi = np.repeat(1 / np.sqrt(m), 3)
    A = K.toarray() * mi[:, None] * mi[None, :]
    B = C.toarray() * mi[:, None] * mi[None, :]
    w2, V = np.linalg.eigh(A)
    body = np.array([n["part"] == "body" for n in g["nodes"]])
    print(f"{touching} tread nodes on the ground; brakes {'off' if ns.free_wheels else f'{ns.brake_k:.0f} N m/rad'}; "
          f"{len(te)} torsion elements ({len(extra)} wind-up bars)")
    for k in range(len(w2)):
        f = np.sqrt(max(w2[k], 0)) / 2 / np.pi
        if f > ns.fmax:
            break
        zeta = V[:, k] @ B @ V[:, k] / (2 * max(np.sqrt(max(w2[k], 0)), 1e-9))
        x = (V[:, k] * mi).reshape(-1, 3)
        x /= np.abs(x).max()
        # body rigid motion: translation (x, y, z) and rotations (pitch about x, roll about z, yaw about y), Unity frame
        Pb, xb = P[body], x[body]
        c0 = Pb.mean(0)
        A6 = np.zeros((3 * len(Pb), 6))
        for j, r in enumerate(Pb - c0):
            A6[3 * j:3 * j + 3, :3] = np.eye(3)
            A6[3 * j:3 * j + 3, 3:] = [[0, r[2], -r[1]], [-r[2], 0, r[0]], [r[1], -r[0], 0]]
        sol, *_ = np.linalg.lstsq(A6, xb.ravel(), rcond=None)
        rig = A6 @ sol
        frac = 1 - np.linalg.norm(xb.ravel() - rig) ** 2 / max(np.linalg.norm(xb.ravel()) ** 2, 1e-12)
        fams = defaultdict(float)
        for j in np.argsort(-np.linalg.norm(x, axis=1))[:40]:
            fams[family(names[j])] += np.linalg.norm(x[j])
        top = ", ".join(f"{a}:{b:.1f}" for a, b in sorted(fams.items(), key=lambda kv: -kv[1])[:4])
        print(f"  {f:6.2f} Hz zeta {zeta:6.3f}  body rigid {frac:4.2f}: lat {sol[0]:+.2f} vert {sol[1]:+.2f} long {sol[2]:+.2f} "
              f"rot x {sol[3]:+.2f} y {sol[4]:+.2f} z {sol[5]:+.2f} | {top}")


if __name__ == "__main__":
    main()
