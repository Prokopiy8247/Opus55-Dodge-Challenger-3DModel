"""Global body stiffness of the skeleton (P3): torsion and bending load cases of the body structure, as in body-in-white
tests, on the solver's linear stiffness (beams + panel hinges, tools/skeleton/mechanisms.assemble).

Structure: the body part and the bonded glass (windshield, rear, quarters); closures (doors, hood, deck lid), fenders,
bumpers, powertrain, suspension and wheels are removed (their DOFs and beams), as in a BIW test.
  torsion: rear spring towers fixed (x, y, z), front-centre support vertical, +-F vertical on the front spring towers;
           twist = (u_L - u_R) / track at the front towers; K_t = F track / twist   (real cars: ~15-35 kN m/deg)
  bending: the four spring towers held vertically (and the minimum horizontal supports), 4 kN down on the cabin floor
           at the seat mounts; K_b = F / max floor deflection                  (real cars: ~10-20 kN/mm)
Reports the stiffness, and the families / materials that store the strain energy (where to stiffen).

Usage: tools/.venv/Scripts/python.exe tools/p3/body_stiffness.py [--top 12]
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
from mechanisms import assemble  # noqa: E402

KEEP_PARTS = ("body", "glass_windshield", "glass_rear", "glass_quarter_L", "glass_quarter_R")
fam = lambda n: re.split(r"\d", n, 1)[0].rstrip("_")


def solve(K, N, fixed_dofs, f):
    free = np.setdiff1d(np.arange(3 * N), fixed_dofs)
    u = np.zeros(3 * N)
    u[free] = spsolve(K[free][:, free].tocsc(), f[free])
    return u


def energy_report(g, p, P, U, keep, top, label):
    mats = {m["name"]: m for m in p["materials"]}
    names = [n["name"] for n in g["nodes"]]
    rows = []
    for b in g["beams"]:
        if not (keep[b["a"]] and keep[b["b"]]):
            continue
        k = mats[b["mat"]].get("spring", 0.0) or 0.0
        if k <= 0:
            continue
        d = P[b["b"]] - P[b["a"]]
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        s = (U[b["b"]] - U[b["a"]]) @ (d / L)
        rows.append((0.5 * k * s * s, b["mat"], names[b["a"]], names[b["b"]]))
    tot = sum(r[0] for r in rows)
    by_mat, by_fam = defaultdict(float), defaultdict(float)
    for e, m, a, b in rows:
        by_mat[m] += e
        by_fam[fam(a)] += e / 2
        by_fam[fam(b)] += e / 2
    print(f"  {label}: strain energy by material: " + ", ".join(f"{m} {100 * v / tot:.0f}%" for m, v in sorted(by_mat.items(), key=lambda kv: -kv[1])[:top]))
    print(f"  {label}: by node family:          " + ", ".join(f"{m} {100 * v / tot:.0f}%" for m, v in sorted(by_fam.items(), key=lambda kv: -kv[1])[:top]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--json", default="", help="write the stiffness results here")
    ns = ap.parse_args()
    res = {}
    g, p = load("hellcat")
    N = len(g["nodes"])
    names = [n["name"] for n in g["nodes"]]
    idx = {n: i for i, n in enumerate(names)}
    P = np.array([n["p"] for n in g["nodes"]], float)
    keep = np.array([n["part"] in KEEP_PARTS and not n["name"].startswith(("arbF_tip", "arbR_tip")) for n in g["nodes"]])
    # remove everything that is not structure: pin the dofs of the removed nodes
    drop = np.where(~keep)[0]
    drop_dofs = np.concatenate([3 * drop + c for c in range(3)])
    # beams from kept nodes to removed nodes still add stiffness on the kept side's diagonal: rebuild K on the kept set
    sub = g.copy()
    sub["beams"] = [b for b in g["beams"] if keep[b["a"]] and keep[b["b"]]]
    sub["hinges"] = [h for h in g.get("hinges", []) if all(keep[i] for i in h["n"])]
    sub["pressureGroups"] = []
    K = assemble(sub, p, geometric=False).tocsr()
    reg = 1e-3 * sp.identity(3 * N)   # tiny: only conditions dofs of mechanism-like stragglers
    Kr = (K + reg).tocsr()

    # ---- torsion
    tL, tR = idx["aplo1_L"], idx["aplo1_R"]
    rL, rR = idx["rtower_L"], idx["rtower_R"]
    front_c = idx["xm1_C"] if "xm1_C" in idx else idx["rack_C"]
    F = 1000.0
    f = np.zeros(3 * N)
    f[3 * tL + 1] += F
    f[3 * tR + 1] -= F
    fixed = np.concatenate([drop_dofs, [3 * rL + c for c in range(3)], [3 * rR + c for c in range(3)], [3 * front_c + 1]])
    u = solve(Kr, N, fixed, f).reshape(-1, 3)
    track = P[tL, 0] - P[tR, 0]
    twist = (u[tL, 1] - u[tR, 1]) / track
    Kt = F * track / twist
    print(f"torsion: couple {F * abs(track):.0f} N m on the front towers -> twist {np.degrees(twist) * 1000:.3f} mdeg -> "
          f"K_t = {abs(Kt) / 1000 * np.pi / 180:.2f} kN m/deg  (real: ~15-35)")
    res["torsion_kNm_per_deg"] = round(abs(Kt) / 1000 * np.pi / 180, 3)
    energy_report(g, p, P, u, keep, ns.top, "torsion")
    # twist distribution along the car: sill / rail stations, (u_y left - u_y right) / (x_left - x_right)
    st = []
    for i in range(N):
        if keep[i] and fam(names[i]) in ("sill", "frail", "rrail", "rail") and names[i].endswith("_L"):
            j = idx.get(names[i][:-2] + "_R")
            if j is not None and keep[j]:
                st.append((P[i, 2], fam(names[i]), (u[i, 1] - u[j, 1]) / (P[i, 0] - P[j, 0])))
    st.sort()
    print("  twist along z (deg per 1 kN m):", ", ".join(f"{fm}@{z:+.2f} {np.degrees(t) / (F * abs(track) / 1000):.3f}"
                                                for z, fm, t in st[::max(1, len(st) // 14)]))

    # ---- bending
    loads = [i for i in range(N) if keep[i] and fam(names[i]) == "floor"]
    ys = P[loads, 1]
    zs = P[loads, 2]
    cabin = [i for i, z in zip(loads, zs) if -1.0 < z < 0.9]
    Ftot = 4000.0
    f = np.zeros(3 * N)
    for i in cabin:
        f[3 * i + 1] -= Ftot / len(cabin)
    fixed = np.concatenate([drop_dofs, [3 * i + 1 for i in (tL, tR, rL, rR)], [3 * rL + 0, 3 * rL + 2, 3 * rR + 2, 3 * tL + 2]])
    u = solve(Kr, N, fixed, f).reshape(-1, 3)
    floor = [i for i in range(N) if keep[i] and fam(names[i]) in ("floor", "sill", "tunnel")]
    dmax = -u[floor, 1].min()
    print(f"bending: {Ftot:.0f} N on {len(cabin)} cabin floor nodes -> max floor deflection {dmax * 1000:.3f} mm -> "
          f"K_b = {Ftot / dmax / 1e6:.2f} kN/mm  (real: ~10-20)")
    sills = sorted((P[i, 2], -u[i, 1]) for i in range(N) if keep[i] and fam(names[i]) == "sill")
    print("  sill deflection along z (mm):", ", ".join(f"{z:+.2f} {d * 1000:.2f}" for z, d in sills[::max(1, len(sills) // 12)]))
    # BIW-style: the same 4 kN on the sills at the B-pillar station only (no local floor sag)
    sb = [i for i in range(N) if keep[i] and fam(names[i]) == "sill" and abs(P[i, 2] + 0.10) < 0.25]
    f = np.zeros(3 * N)
    for i in sb:
        f[3 * i + 1] -= Ftot / len(sb)
    u2 = solve(Kr, N, fixed, f).reshape(-1, 3)
    d2 = -u2[sb, 1].mean()
    print(f"bending (sills at the B-pillar, {len(sb)} nodes): deflection {d2 * 1000:.3f} mm -> K_b = {Ftot / d2 / 1e6:.2f} kN/mm")
    res["bending_kN_per_mm"] = round(Ftot / d2 / 1e6, 3)
    res["bending_floor_kN_per_mm"] = round(Ftot / dmax / 1e6, 3)
    if ns.json:
        Path(ns.json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    energy_report(g, p, P, u, keep, ns.top, "bending")

    return
    # ---- the braking case of T7, linearised: 1 g fore-aft inertia on the structure, reacted at the four towers
    m = np.array([n["m"] for n in g["nodes"]])
    f = np.zeros(3 * N)
    sel = np.where(keep)[0]
    f[3 * sel + 2] = m[sel] * 9.81
    fixed = np.concatenate([drop_dofs, [3 * i + c for i in (tL, tR, rL, rR) for c in range(3)]])
    u = solve(Kr, N, fixed, f).reshape(-1, 3)
    fr = [i for i in range(N) if keep[i] and fam(names[i]) == "frail"]
    print(f"1 g fore-aft inertia of the structure, towers held: frame rail mean vertical {u[fr, 1].mean() * 1000:+.2f} mm, "
          f"max |u| {np.abs(u[sel]).max() * 1000:.2f} mm at {names[sel[np.argmax(np.abs(u[sel]).max(1))]]}")


if __name__ == "__main__":
    main()
