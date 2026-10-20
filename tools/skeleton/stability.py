"""Stability of a skeleton + params at the solver time step (decision D-004, refined in D-024).

Symplectic Euler with beam damping is stable for every mode when
    S = lambda_max( M^-1 (dt^2 K + 2 dt C + D_contact) ) < 4
(single degree of freedom: (w dt)^2 + 4 zeta w dt < 4). K and C are the assembled beam stiffness and
damping matrices (beams act along their axis: k n n^T blocks), D_contact adds the static-contact
penalty terms of colliding nodes (alpha + 4 zeta sqrt(alpha)) * m. Hard limit (D-024): S < 2.5, a factor
1.6 below the exact limit; the margin covers geometric stiffness of highly tensioned beams in crashes. Also reported per node: the block-Gershgorin bound used before (upper bound of S, D-004) and
the brief's warning omega*dt = dt sqrt(sum k / m) >= 0.5.

Usage: tools/.venv/Scripts/python.exe tools/skeleton/stability.py [vehicle] [--modes 6]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
import hinges  # noqa: E402

COLLISION, STATIC = 1, 4
HARD_LIMIT = 2.5


def strip_comments(text):
    out, in_str, i = [], False, 0
    while i < len(text):
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                i += 1
            out.append("\n")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def load(vehicle):
    d = ROOT / "sim" / "vehicle" / vehicle
    g = json.loads((d / "geometry.json").read_text(encoding="utf-8"))
    p = json.loads(strip_comments((d / "params.json").read_text(encoding="utf-8")))
    return g, p


def beam_kc(m, btype):
    def v(key, default):
        x = m.get(key, default)
        return default if x is None or x < 0 else x
    k = v("spring", 0.0)
    if btype == "ANISOTROPIC":
        k = max(k, v("springExp", k))
    if btype == "BOUNDED":
        k += v("limitSpring", 0.0)
    c0 = v("damp", 0.0)
    c = max(c0, v("dampRebound", c0), v("dampFast", c0), v("dampReboundFast", c0))
    if btype == "ANISOTROPIC":
        c = max(c, v("dampExp", c0))
    if btype == "BOUNDED":
        c += max(v("limitDamp", 0.0), v("limitDampRebound", v("limitDamp", 0.0)))
    return k, c


def analyse(g, p, modes=6, top=15):
    dt = p.get("dt", 0.0005)
    mats = {m["name"]: m for m in p["materials"]}
    cmats = {c["name"]: c for c in p.get("contactMaterials", [])}
    N = len(g["nodes"])
    P = np.array([n["p"] for n in g["nodes"]], float)
    m = np.array([n["m"] for n in g["nodes"]], float)
    rows, cols, vals = [], [], []
    sumk = np.zeros(N)
    gersh = np.zeros(N)
    missing = set()
    for b in g["beams"]:
        mat = mats.get(b["mat"])
        if mat is None:
            missing.add(b["mat"])
            continue
        k, c = beam_kc(mat, b["type"])
        a_, b_ = b["a"], b["b"]
        d = P[b_] - P[a_]
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        n = d / L
        w = dt * dt * k + 2 * dt * c
        blk = w * np.outer(n, n)
        for (i, j, s) in ((a_, a_, 1), (b_, b_, 1), (a_, b_, -1), (b_, a_, -1)):
            for r in range(3):
                for q in range(3):
                    rows.append(3 * i + r)
                    cols.append(3 * j + q)
                    vals.append(s * blk[r, q])
        sumk[a_] += k
        sumk[b_] += k
        gersh[a_] += (dt * dt * k + 2 * dt * c) * (1 / m[a_] + 1 / np.sqrt(m[a_] * m[b_]))
        gersh[b_] += (dt * dt * k + 2 * dt * c) * (1 / m[b_] + 1 / np.sqrt(m[a_] * m[b_]))
    # static contact penalty (colliding nodes)
    contact = np.zeros(N)
    for i, n in enumerate(g["nodes"]):
        if n["flags"] & STATIC:
            cm = cmats.get(n["cmat"], {})
            an, zn = cm.get("alphaNormal", 0.35), cm.get("zetaNormal", 0.15)
            at, zt = cm.get("alphaTangent", 0.3), cm.get("zetaTangent", 0.15)
            contact[i] = max(an + 4 * zn * np.sqrt(an), at + 4 * zt * np.sqrt(at))
            for r in range(3):
                rows.append(3 * i + r)
                cols.append(3 * i + r)
                vals.append(contact[i] * m[i])
    # deformation damping groups (D-033): at most 2 dt rate m_i per group node
    rates = {mm["name"]: mm["rate"] for mm in p.get("dampGroupMaterials", [])}
    for dg in g.get("dampGroups", []):
        for i in dg["nodes"]:
            for r in range(3):
                rows.append(3 * i + r)
                cols.append(3 * i + r)
                vals.append(2 * dt * rates.get(dg["mat"], 0.0) * m[i])
    A = sp.csr_matrix((vals, (rows, cols)), shape=(3 * N, 3 * N))
    # panel hinges (shell bending, D-032): (dt^2 k + 2 dt c) g g^T, part of the panel stiffness
    he = hinges.elements(g, p, P)
    if he:
        A = A + dt * dt * hinges.matrix(N, he, "k") + 2 * dt * hinges.matrix(N, he, "c")
    Minv_sqrt = sp.diags(np.repeat(1.0 / np.sqrt(m), 3))
    Bm = Minv_sqrt @ A @ Minv_sqrt
    w_, v_ = eigsh(Bm, k=modes, which="LA", tol=1e-6, maxiter=20000)
    order = np.argsort(-w_)
    w_, v_ = w_[order], v_[:, order]
    names = [n["name"] for n in g["nodes"]]
    out = {"dt": dt, "nodes": N, "beams": len(g["beams"]), "hinges": len(he), "missing_materials": sorted(missing),
           "S_exact_max": round(float(w_[0]), 4), "S_exact_top": [round(float(x), 4) for x in w_],
           "hard_limit": HARD_LIMIT, "exact_limit": 4.0, "pass": bool(w_[0] < HARD_LIMIT)}
    modes_out = []
    for k in range(len(w_)):
        amp = np.linalg.norm(v_[:, k].reshape(-1, 3), axis=1)
        idx = np.argsort(-amp)[:5]
        modes_out.append({"S": round(float(w_[k]), 4), "nodes": [(names[i], round(float(amp[i]), 3)) for i in idx]})
    out["top_modes"] = modes_out
    # exact S of every node family (the submatrix of the nodes whose name starts the same way, the rest
    # held fixed): localizes the stiff spots
    fam = {}
    for i, nm in enumerate(names):
        key = re.split(r"\d", nm, 1)[0].rstrip("_")
        key = re.sub(r"^(FL|FR|RL|RR)_", "wheel_", key)
        fam.setdefault(key, []).append(i)
    fam_s = {}
    for key, ids in fam.items():
        dof = np.repeat(np.array(ids) * 3, 3) + np.tile([0, 1, 2], len(ids))
        sub = Bm[dof][:, dof]
        if sub.shape[0] <= 6:
            ev = np.linalg.eigvalsh(sub.toarray())
            fam_s[key] = round(float(ev.max()), 3)
        else:
            fam_s[key] = round(float(eigsh(sub, k=1, which="LA", tol=1e-5, maxiter=20000)[0][0]), 3)
    out["family_S"] = dict(sorted(fam_s.items(), key=lambda kv: -kv[1]))
    od = dt * np.sqrt(sumk / m)
    out["gershgorin_max"] = round(float((gersh + contact).max()), 3)
    out["gershgorin_over_2"] = int(((gersh + contact) >= 2).sum())
    out["omega_dt_max"] = round(float(od.max()), 3)
    out["omega_dt_warnings"] = int((od >= 0.5).sum())
    worst = np.argsort(-(gersh + contact))[:top]
    out["worst_gershgorin"] = [(names[i], round(float(gersh[i] + contact[i]), 3), round(float(m[i]), 3)) for i in worst]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--modes", type=int, default=6)
    ap.add_argument("--json", default="")
    ns = ap.parse_args()
    g, p = load(ns.vehicle)
    out = analyse(g, p, ns.modes)
    text = json.dumps(out, indent=1)
    if ns.json:
        Path(ns.json).write_text(text, encoding="utf-8")
    print(re.sub(r'\[\n\s+("|[-\d])', r'[\1', text))


if __name__ == "__main__":
    main()
