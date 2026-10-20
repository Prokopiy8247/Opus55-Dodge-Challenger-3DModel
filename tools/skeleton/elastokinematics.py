"""Linear elastokinematics of the suspension (P3b): toe and camber of every knuckle under unit loads at its wheel,
the cabin floor held (D-049).

K = assembled axial beam stiffness of the skeleton (springs included; dampers, bump stops and the tire / rim nodes
out) plus the wind-up elements (D-036) as rotational springs about each spin axis between the knuckle nodes and the
wind-up body nodes. Per corner, 1 kN load cases:
  drive    forward force at the axle (the drive torque goes to the differential, not the knuckle)
  brake    backward force at the ground: the force at the axle plus the brake moment F R on the knuckle
  lateral  inward force at the ground: the force at the axle plus the moment F R about the longitudinal axis
           (carried by the two bearing rows: a couple on the axle nodes)
  vertical upward force at the axle (wheel travel against the spring: bump steer plus compliance)
Toe: rotation of the axle line about the vertical (toe-in positive), camber: about the longitudinal axis (top
outward positive), per kN.

Usage: tools/.venv/Scripts/python.exe tools/skeleton/elastokinematics.py [vehicle] [--json out.json]
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

UP = np.array([0.0, 1.0, 0.0])          # Unity frame: x right, y up, z forward
RING = re.compile(r"^(FL|FR|RL|RR)_(rimI|rimO|trI|trC|trO)\d+$")


def assemble(g, p, P):
    mats = {m["name"]: m for m in p["materials"]}
    N = len(g["nodes"])
    names = [n["name"] for n in g["nodes"]]
    out = np.array([bool(RING.match(nm)) for nm in names])
    rows, cols, vals = [], [], []
    for b in g["beams"]:
        a, c = b["a"], b["b"]
        if out[a] or out[c] or b["type"] in ("BOUNDED", "SUPPORT"):
            continue
        m = mats[b["mat"]]
        k = m.get("spring", 0.0) or 0.0
        if k <= 0:
            continue
        d = P[c] - P[a]
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        e = d / L
        blk = k * np.outer(e, e)
        for (i, j, s) in ((a, a, 1), (c, c, 1), (a, c, -1), (c, a, -1)):
            for r in range(3):
                for q in range(3):
                    rows.append(3 * i + r)
                    cols.append(3 * j + q)
                    vals.append(s * blk[r, q])
    K = sp.csr_matrix((vals, (rows, cols)), shape=(3 * N, 3 * N))
    return K, out


def knuckle_nodes(g, w):
    """Nodes tied to the axle nodes by knuckle beams (the knuckle body)."""
    ax = {w["axleInner"], w["axleOuter"]}
    s = set(ax)
    for b in g["beams"]:
        if b["mat"].startswith("knuckle") and (b["a"] in ax or b["b"] in ax):
            s.add(b["a"])
            s.add(b["b"])
    return sorted(s)


def rot_gradient(P, ids, axis, N):
    """d(theta)/du of the rotation of a node set about axis (small-rotation fit, equal weights)."""
    c = P[ids].mean(axis=0)
    g = np.zeros(3 * N)
    S = 0.0
    for i in ids:
        r = P[i] - c
        r = r - np.dot(r, axis) * axis
        S += np.dot(r, r)
    for i in ids:
        r = P[i] - c
        r = r - np.dot(r, axis) * axis
        g[3 * i:3 * i + 3] = np.cross(axis, r)
    return g / max(S, 1e-12)


def energy_by_material(g, p, P, U):
    """Elastic energy (J) per beam material for a displacement field U (N x 3)."""
    mats = {m["name"]: m for m in p["materials"]}
    names = [n["name"] for n in g["nodes"]]
    out = {}
    for b in g["beams"]:
        a, c = b["a"], b["b"]
        if RING.match(names[a]) or RING.match(names[c]) or b["type"] in ("BOUNDED", "SUPPORT"):
            continue
        k = mats[b["mat"]].get("spring", 0.0) or 0.0
        if k <= 0:
            continue
        d = P[c] - P[a]
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        e = d / L
        dl = np.dot(U[c] - U[a], e)
        out[b["mat"]] = out.get(b["mat"], 0.0) + 0.5 * k * dl * dl
    return out


def solve(g, p, extra=None, energy=False):
    P = np.array([n["p"] for n in g["nodes"]], float)
    N = len(P)
    K, out = assemble(g, p, P)
    names = [n["name"] for n in g["nodes"]]
    # wind-up elements: K_wu (theta_knuckle - theta_body)^2 / 2
    wu = {w["name"]: w for w in p.get("windup", [])} if isinstance(p.get("windup"), list) else {}
    wmat = {m["name"]: m for m in p.get("windup", [])} if isinstance(p.get("windup"), list) else {}
    low = []
    for w in g["wheels"]:
        kn = knuckle_nodes(g, w)
        axis = P[w["axleOuter"]] - P[w["axleInner"]]
        axis /= np.linalg.norm(axis)
        body = w.get("windupBody") or []
        mat = wmat.get(w.get("windup", ""), {})
        kw = mat.get("stiffness", 0.0)
        if kw > 0 and body:
            gv = rot_gradient(P, kn, axis, N) - rot_gradient(P, body, axis, N)
            nz = np.nonzero(gv)[0]
            low.append((nz, gv[nz], kw))
    for nz, gz, kw in low:
        K = K + sp.csr_matrix((kw * np.outer(gz, gz).ravel(), (np.repeat(nz, len(nz)), np.tile(nz, len(nz)))), shape=K.shape)
    fixed = set()
    for i, nd in enumerate(g["nodes"]):
        if out[i] or (nd["part"] == "body" and re.match(r"^(sill|floor|tunnel)", nd["name"])):
            fixed.update((3 * i, 3 * i + 1, 3 * i + 2))
    free = np.array(sorted(set(range(3 * N)) - fixed))
    Kf = K[free][:, free].tocsc()
    eps = 1e-7 * Kf.diagonal().mean()
    Kf = Kf + eps * sp.identity(len(free), format="csc")
    from scipy.sparse.linalg import splu
    lu = splu(Kf)
    res = {}
    R = 0.352
    for w in g["wheels"]:
        ai, ao = w["axleInner"], w["axleOuter"]
        c = 0.5 * (P[ai] + P[ao])
        d = P[ao] - P[ai]
        side = 1.0 if c[0] > 0 else -1.0
        axis = d / np.linalg.norm(d)
        kn = knuckle_nodes(g, w)
        fwd = np.array([0.0, 0.0, 1.0])
        inward = np.array([-side, 0.0, 0.0])
        ground = np.array([0.0, -R, 0.0])
        cases = {}

        def axle_load(F, M):
            f = np.zeros((N, 3))
            f[ai] += 0.5 * F
            f[ao] += 0.5 * F
            Mp = M - np.dot(M, axis) * axis            # the bearing rows carry the moment off the spin axis
            fc = np.cross(Mp, d) / np.dot(d, d)
            f[ao] += fc
            f[ai] -= fc
            Ma = np.dot(M, axis) * axis                # about the spin axis: the brake, on the knuckle body
            if np.linalg.norm(Ma) > 0:
                cc = P[kn].mean(axis=0)
                S = sum(np.dot(r, r) for r in [(P[i] - cc) - np.dot(P[i] - cc, axis) * axis for i in kn])
                for i in kn:
                    r = (P[i] - cc) - np.dot(P[i] - cc, axis) * axis
                    f[i] += np.cross(Ma, r) / S
            return f

        F = 1000.0
        cases["drive"] = axle_load(F * fwd, np.zeros(3))
        cases["brake"] = axle_load(-F * fwd, np.cross(ground, -F * fwd))
        cases["lateral"] = axle_load(F * inward, np.cross(ground, F * inward))
        cases["vertical"] = axle_load(F * UP, np.zeros(3))
        out_w = {}
        for name, f in cases.items():
            u = np.zeros(3 * N)
            u[free] = lu.solve(f.ravel()[free])
            U = u.reshape(-1, 3)
            dd = (P[ao] + U[ao]) - (P[ai] + U[ai])

            def toe_camber(v):
                a_out = v / np.linalg.norm(v)
                h = np.cross(side * a_out, UP)          # wheel heading (forward for both sides)
                h /= np.linalg.norm(h)
                return -side * np.degrees(np.arcsin(h[0])), -np.degrees(np.arcsin(np.dot(a_out, UP)))
            t1, c1 = toe_camber(dd)
            t0, c0 = toe_camber(d)
            toe_in, camber = t1 - t0, c1 - c0
            hub = 0.5 * (U[ai] + U[ao])
            out_w[name] = {"toe_in_deg": float(toe_in), "camber_deg": float(camber),
                           "hub_mm": [float(x * 1000) for x in hub]}
            if energy:
                en = energy_by_material(g, p, P, U)
                tot = sum(en.values())
                out_w[name]["energy"] = {k: round(v / tot, 3) for k, v in sorted(en.items(), key=lambda kv: -kv[1])[:8]}
        res[w["name"]] = out_w
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--json", default="")
    ns = ap.parse_args()
    g, p = load(ns.vehicle)
    res = solve(g, p)
    print("per 1 kN: toe-in (deg, + in), camber (deg, + top out), hub displacement (mm, x right, y up, z forward)")
    for wn, cs in res.items():
        for cn, v in cs.items():
            h = v["hub_mm"]
            print(f"  {wn} {cn:8s} toe-in {v['toe_in_deg']:+.3f}  camber {v['camber_deg']:+.3f}  hub {h[0]:+6.2f} {h[1]:+6.2f} {h[2]:+6.2f}")
    if ns.json:
        Path(ns.json).write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
