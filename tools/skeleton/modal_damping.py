"""Modal damping of a skeleton on its wheels (P3 finding: panels and glass kept ringing for seconds after settling).

Beam dampers act only along the beam axis, so a mode that moves nodes across their beams (out-of-plane panel
bending, a mirror wobbling on its mount) gets almost no damping. With the wheel parts held, this solves the undamped
modes K phi = w^2 M phi (dense, all modes) and reports the modal damping ratio zeta = phi^T C phi / (2 w) of each
(phi mass-normalised; C = sum c n n^T over the beams, slow damping of the dampers).

Usage: tools/.venv/Scripts/python.exe tools/skeleton/modal_damping.py [vehicle] [--fmax 120] [--zeta 0.02] [--json out]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
from mechanisms import assemble, family  # noqa: E402
import hinges  # noqa: E402


def beam_damping(m):
    c = m.get("damp", 0.0) or 0.0
    if m.get("dampRebound") is not None:
        c = 0.5 * (c + m["dampRebound"])
    return max(c, 0.0)


def assemble_c(g, p, extra=None):
    """Axial damping matrix; extra(j, beam, material) may return an additional isotropic coefficient (N s/m)."""
    mats = {m["name"]: m for m in p["materials"]}
    N = len(g["nodes"])
    P = np.array([n["p"] for n in g["nodes"]], float)
    rows, cols, vals = [], [], []
    for j, b in enumerate(g["beams"]):
        m = mats[b["mat"]]
        c = beam_damping(m)
        a, d = b["a"], b["b"]
        v = P[d] - P[a]
        L = np.linalg.norm(v)
        if L < 1e-9:
            continue
        e = v / L
        blk = c * np.outer(e, e)
        if extra is not None:
            ci = extra(j, b, m)
            if ci:
                blk = blk + ci * (np.eye(3) - np.outer(e, e))
        if not blk.any():
            continue
        for (i, jj, s) in ((a, a, 1), (d, d, 1), (a, d, -1), (d, a, -1)):
            for r in range(3):
                for q in range(3):
                    rows.append(3 * i + r)
                    cols.append(3 * jj + q)
                    vals.append(s * blk[r, q])
    C = sp.csr_matrix((vals, (rows, cols)), shape=(3 * N, 3 * N))
    he = hinges.elements(g, p, P)        # panel shell bending damping (D-032)
    if he:
        C = C + hinges.matrix(N, he, "c")
    Cg = group_damping(g, p, P)
    if Cg is not None:
        C = C + Cg
    return C


def group_damping(g, p, P):
    """Deformation damping groups (D-033): rate (M - M Phi (Phi^T M Phi)^-1 Phi^T M) per group, Phi = the group's six
    rigid modes about its centre of mass (the linearisation of Hellcat.Sim.GroupDampJob)."""
    rates = {m["name"]: m["rate"] for m in p.get("dampGroupMaterials", [])}
    N = len(g["nodes"])
    m = np.array([n["m"] for n in g["nodes"]], float)
    rows, cols, vals = [], [], []
    for dg in g.get("dampGroups", []):
        rate = rates.get(dg["mat"], 0.0)
        ids = np.array(dg["nodes"], int)
        if rate <= 0 or len(ids) < 2:
            continue
        mg = np.repeat(m[ids], 3)
        x = P[ids]
        xc = (m[ids, None] * x).sum(0) / m[ids].sum()
        r = x - xc
        Phi = np.zeros((3 * len(ids), 6))
        for k, rk in enumerate(r):
            Phi[3 * k:3 * k + 3, :3] = np.eye(3)
            Phi[3 * k:3 * k + 3, 3:] = [[0, rk[2], -rk[1]], [-rk[2], 0, rk[0]], [rk[1], -rk[0], 0]]
        MPhi = mg[:, None] * Phi
        G = Phi.T @ MPhi
        Cb = rate * (np.diag(mg) - MPhi @ np.linalg.pinv(G) @ MPhi.T)
        dof = (3 * ids[:, None] + np.arange(3)[None, :]).ravel()
        rows.append(np.repeat(dof, len(dof)))
        cols.append(np.tile(dof, len(dof)))
        vals.append(Cb.ravel())
    if not rows:
        return None
    return sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(3 * N, 3 * N))


def analyse(g, p, fmax=120.0, C=None):
    K = assemble(g, p).tocsr()
    if C is None:
        C = assemble_c(g, p)
    C = C.tocsr()
    m = np.array([n["m"] for n in g["nodes"]], float)
    held = np.array([n["part"].startswith("wheel_") for n in g["nodes"]])
    free = np.where(~held)[0]
    dof = np.repeat(free * 3, 3) + np.tile([0, 1, 2], len(free))
    mi = np.repeat(1.0 / np.sqrt(m[free]), 3)
    A = (K[dof][:, dof]).toarray() * mi[:, None] * mi[None, :]
    B = (C[dof][:, dof]).toarray() * mi[:, None] * mi[None, :]
    w2, V = np.linalg.eigh(A)
    w = np.sqrt(np.clip(w2, 0.0, None))
    zeta = np.einsum("ij,ij->j", V, B @ V) / (2.0 * np.maximum(w, 1e-9))
    names = [g["nodes"][i]["name"] for i in free]
    out = []
    for i in range(len(w)):
        f = w[i] / (2 * np.pi)
        if f > fmax:
            break
        x = (V[:, i] * mi).reshape(-1, 3)
        amp = np.linalg.norm(x, axis=1)
        amp /= amp.max()
        fams = defaultdict(float)
        for j in np.where(amp > 0.2)[0]:
            fams[family(names[j])] += amp[j]
        top = np.argsort(-amp)[:4]
        out.append({"hz": float(f), "zeta": float(zeta[i]), "tau_s": float(1.0 / max(zeta[i] * w[i], 1e-9)),
                    "moving": int((amp > 0.2).sum()),
                    "families": sorted(((a, round(b, 1)) for a, b in fams.items()), key=lambda kv: -kv[1])[:4],
                    "nodes": [names[j] for j in top]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--fmax", type=float, default=120.0)
    ap.add_argument("--zeta", type=float, default=0.02, help="list modes below this damping ratio")
    ap.add_argument("--json", default="")
    ns = ap.parse_args()
    g, p = load(ns.vehicle)
    modes = analyse(g, p, ns.fmax)
    low = [md for md in modes if md["zeta"] < ns.zeta]
    print(f"{len(modes)} modes below {ns.fmax} Hz, {len(low)} with zeta < {ns.zeta}")
    for md in modes:
        flag = " <" if md["zeta"] < ns.zeta else ""
        print(f"  {md['hz']:8.2f} Hz  zeta {md['zeta']:7.4f}  tau {md['tau_s']:7.3f} s  {md['moving']:4d} nodes  "
              f"{', '.join(f'{a}:{b}' for a, b in md['families'])}{flag}")
    if ns.json:
        Path(ns.json).write_text(json.dumps(modes, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
