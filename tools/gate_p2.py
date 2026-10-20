"""P2 quality gate (G-Skeleton): physics skeleton of a vehicle.

Inputs:
    sim/vehicle/<vehicle>/geometry.json    hcar.hskel:main (nodes, beams, triangles, wheels, pressure groups,
                                           torsion bars, parts, cameras); Unity frame x right, y up, z forward,
                                           triangle normal cross(b - a, c - a) points out of the body
    sim/vehicle/<vehicle>/params.json      materials, contact materials, solver settings
    tools/blender/hcar/hskel_tables.py     mass and centre-of-mass targets (pure Python)
    tools/skeleton/stability.py            exact stability measure (decision D-024)
    docs/video_assets/P2/                  skeleton debug-view renders

Outward winding is checked numerically without the visual model: triangles are grouped into patches
(connected through edges shared by exactly two triangles); every patch must be consistently wound, and its
orientation is decided by ray voting - from each triangle centroid rays are cast into the hemisphere of the
normal and into the opposite one, and the side from which more rays escape to infinity (no triangle hit) is
the outside. The closed tire air volumes must be closed two-manifolds with positive signed volume.

Usage:  tools/.venv/Scripts/python.exe tools/gate_p2.py [vehicle]
Output: docs/gates/gate_p2.json and docs/gates/gate_p2.md (+ docs/gates/p2_winding.json)
"""
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
results = []

REQUIRED_BREAK_GROUPS = ["bumper_F", "bumper_R", "hood", "trunk", "door_FL", "door_FR", "mirror_L", "mirror_R",
                         "wheel_FL", "wheel_FR", "wheel_RL", "wheel_RR", "exhaust", "headlight_L", "headlight_R",
                         "glass_windshield", "glass_side_*", "glass_rear"]
BUDGET = {"nodes": (2500, 6000), "beams": (12000, 40000), "triangles": (3000, 8000)}     # brief 4.5 starting target
RAYS = 192              # Fibonacci directions on the sphere; about half fall in each hemisphere
RAY_OFFSET = 0.003      # m, ray origins off the triangle plane
VOTE_MIN = 0.05         # |area-weighted escape difference| below this leaves a patch undecided


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------ geometry helpers
def components(n, edges):
    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    roots = [find(i) for i in range(n)]
    return len(set(roots)), roots


def fibonacci_sphere(n):
    k = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * k / n)
    th = np.pi * (1 + 5 ** 0.5) * k
    return np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], axis=1)


def any_hit(O, D, V0, E1, E2):
    """Moeller-Trumbore, all rays against all triangles: True where ray O + t D (t > 0) hits a triangle."""
    P = np.cross(D[:, None, :], E2[None, :, :])
    det = np.einsum("rtk,tk->rt", P, E1)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    S = O[:, None, :] - V0[None, :, :]
    u = np.einsum("rtk,rtk->rt", S, P) * inv
    Q = np.cross(S, E1[None, :, :])
    v = np.einsum("rk,rtk->rt", D, Q) * inv
    t = np.einsum("tk,rtk->rt", E2, Q) * inv
    return (ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6)).any(axis=1)


def escape_votes(P, T, idx, batch=4):
    """For triangles idx of (P, T): escape fraction of rays from the normal side minus the opposite side."""
    A, B, C = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    V0, E1, E2 = A, B - A, C - A
    N = np.cross(E1, E2)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    cen = (A + B + C) / 3
    dirs = fibonacci_sphere(RAYS)
    votes = np.zeros(len(idx))
    for s in range(0, len(idx), batch):
        rows, O, D, owner = idx[s:s + batch], [], [], []
        for k, t in enumerate(rows):
            c = dirs @ N[t]
            for sign in (1, -1):
                d = dirs[sign * c > 0.1]
                O.append(np.repeat((cen[t] + sign * RAY_OFFSET * N[t])[None], len(d), axis=0))
                D.append(d)
                owner.append(np.full(len(d), 2 * k + (sign < 0)))
        O, D, owner = np.concatenate(O), np.concatenate(D), np.concatenate(owner)
        esc = ~any_hit(O, D, V0, E1, E2)
        for k in range(len(rows)):
            votes[s + k] = esc[owner == 2 * k].mean() - esc[owner == 2 * k + 1].mean()
    return votes


def winding(g):
    P = np.array([n["p"] for n in g["nodes"]], float)
    T = np.array([(t["a"], t["b"], t["c"]) for t in g["triangles"]], int)
    area = 0.5 * np.linalg.norm(np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]), axis=1)
    out = {"degenerate": int((area < 1e-6).sum())}

    # closed air volumes of the tires
    tires = []
    in_pressure = set()
    for pg in g["pressureGroups"]:
        ids = np.array(pg["tris"])
        in_pressure.update(ids.tolist())
        directed = Counter()
        for a, b, c in T[ids]:
            directed.update([(a, b), (b, c), (c, a)])
        und = Counter()
        for (a, b), k in directed.items():
            und[(min(a, b), max(a, b))] += k
        open_edges = sum(1 for k in und.values() if k != 2)
        same_dir = sum(1 for (a, b), k in directed.items() if k > 1 or (b, a) not in directed)
        A, B, C = P[T[ids, 0]], P[T[ids, 1]], P[T[ids, 2]]
        vol = float(np.einsum("ij,ij->i", A, np.cross(B, C)).sum() / 6)
        tires.append({"group": pg["name"], "triangles": len(ids), "edges_not_shared_by_two": open_edges,
                      "inconsistent_edges": same_dir, "volume_l": round(vol * 1000, 2)})
    out["tires"] = tires

    # surface patches (everything outside the tire air volumes)
    rest = np.array([i for i in range(len(T)) if i not in in_pressure])
    key = {}
    for i in rest:
        key.setdefault(tuple(sorted(T[i])), []).append(i)
    two_sided = set()
    for tri_ids in key.values():
        if len(tri_ids) == 2:
            a, b = tri_ids
            ca = np.cross(P[T[a, 1]] - P[T[a, 0]], P[T[a, 2]] - P[T[a, 0]])
            cb = np.cross(P[T[b, 1]] - P[T[b, 0]], P[T[b, 2]] - P[T[b, 0]])
            if np.dot(ca, cb) < 0:
                two_sided.update(tri_ids)
    out["two_sided_triangles"] = sorted(int(i) for i in two_sided)
    vote_ids = np.array([i for i in rest if i not in two_sided])
    edge_tris = defaultdict(list)
    for i in vote_ids:
        a, b, c = T[i]
        for e0, e1 in ((a, b), (b, c), (c, a)):
            edge_tris[(min(e0, e1), max(e0, e1))].append((i, (e0, e1)))
    # patches grow only across consistently wound shared edges, so a flipped cell forms its own patch and
    # votes on its own
    adj = defaultdict(list)
    inconsistent, nonmanifold = 0, 0
    for (u, v), lst in edge_tris.items():
        if len(lst) == 2:
            (i, d0), (j, d1) = lst
            if d0 == d1:
                inconsistent += 1
                continue
            adj[i].append(j)
            adj[j].append(i)
        elif len(lst) > 2:
            nonmanifold += 1
    out["inconsistent_edges"] = inconsistent
    out["edges_shared_by_3_or_more"] = nonmanifold
    votes = dict(zip(vote_ids.tolist(), escape_votes(P, T, vote_ids)))
    seen, patches = set(), []
    for i in vote_ids:
        if i in seen:
            continue
        stack, members = [i], []
        seen.add(i)
        while stack:
            k = stack.pop()
            members.append(k)
            for j in adj[k]:
                if j not in seen:
                    seen.add(j)
                    stack.append(j)
        w = area[members]
        v = np.array([votes[k] for k in members])
        mean = float((w * v).sum() / w.sum())
        groups = Counter(g["triangles"][k]["group"] for k in members)
        patches.append({"groups": dict(groups), "triangles": len(members), "area_m2": round(float(w.sum()), 3),
                        "vote": round(mean, 3), "triangles_voting_outward": round(float((v > 0).mean()), 3),
                        "orientation": "outward" if mean > VOTE_MIN else "inward" if mean < -VOTE_MIN else "undecided"})
    out["patches"] = sorted(patches, key=lambda p: p["vote"])
    out["voted_triangles"] = len(vote_ids)
    return out


# ------------------------------------------------------------------------------------------------- gate
def main():
    vehicle = sys.argv[1] if len(sys.argv) > 1 else "hellcat"
    d = ROOT / "sim/vehicle" / vehicle
    stab = module(ROOT / "tools/skeleton/stability.py", "stability")
    tables = module(ROOT / "tools/blender/hcar/hskel_tables.py", "hskel_tables")
    g, p = stab.load(vehicle)
    nodes, beams, tris = g["nodes"], g["beams"], g["triangles"]
    N = len(nodes)
    P = np.array([n["p"] for n in nodes], float)
    m = np.array([n["m"] for n in nodes], float)

    # counts
    tri_types = Counter(t["type"] for t in tris)
    beam_types = Counter(b["type"] for b in beams)
    check("node, beam and triangle counts reported", "PASS",
          f"{N} nodes, {len(beams)} beams ({', '.join(f'{k} {v}' for k, v in beam_types.most_common())}), "
          f"{len(tris)} triangles ({', '.join(f'{k} {v}' for k, v in tri_types.most_common())}), "
          f"{len(g['wheels'])} wheels, {len(g['pressureGroups'])} pressure groups, {len(g['torsionBars'])} torsion "
          f"bars, {len(g['parts'])} parts, {len(g['cameras'])} camera mounts")
    counts = {"nodes": N, "beams": len(beams), "triangles": len(tris)}
    below = [f"{k} {v} < {BUDGET[k][0]}" for k, v in counts.items() if v < BUDGET[k][0]]
    above = [f"{k} {v} > {BUDGET[k][1]}" for k, v in counts.items() if v > BUDGET[k][1]]
    check("complexity vs the brief's starting target (4.5: 2,500-6,000 nodes, 12,000-40,000 beams, 3,000-8,000 "
          "triangles)", "PASS" if not below and not above else "WARN",
          ("within the starting target" if not below and not above else
           "; ".join(below + above) + " - the resolution is set by the 2 kHz stability limit at the real mass "
           "budget (D-024; docs/P2_report.md section 'Resolution')"))

    # mass, centre of mass, axle split
    M = float(m.sum())
    target = tables.MASS_TOTAL
    err = (M - target) / target
    check("total mass equals target +-1 %", "PASS" if abs(err) <= 0.01 else "FAIL",
          f"{M:.1f} kg vs {target:.0f} kg ({err * 100:+.2f} %)")
    com = (m[:, None] * P).sum(0) / M
    hubs = {w["name"]: (P[w["axleInner"]] + P[w["axleOuter"]]) / 2 for w in g["wheels"]}
    zf = np.mean([hubs[k][2] for k in hubs if k.startswith("F")])
    zr = np.mean([hubs[k][2] for k in hubs if k.startswith("R")])
    front = (com[2] - zr) / (zf - zr)
    corners = {}
    for ax, share in (("F", front), ("R", 1 - front)):
        xl, xr = hubs[ax + "L"][0], hubs[ax + "R"][0]
        left = (xr - com[0]) / (xr - xl)
        corners[ax + "L"], corners[ax + "R"] = M * share * left, M * share * (1 - left)
    com_ok = abs(front - tables.FRONT_SHARE) <= 0.01 and abs(com[0]) < 0.01
    check("centre of mass and axle load split reported (target 57 / 43 %, brief 55-57 % front)",
          "PASS" if com_ok else "FAIL",
          f"CoM (Unity x, y, z) = ({com[0]:+.4f}, {com[1]:.4f}, {com[2]:+.4f}) m, i.e. {com[2] - zr:.3f} m ahead of "
          f"the rear axle, height {com[1]:.3f} m; wheelbase {zf - zr:.3f} m; front {front * 100:.1f} % / rear "
          f"{(1 - front) * 100:.1f} %; rigid-body corner loads " + ", ".join(f"{k} {v:.0f} kg" for k, v in corners.items()))

    # connectivity
    deg = np.zeros(N, int)
    for b in beams:
        deg[b["a"]] += 1
        deg[b["b"]] += 1
    ncomp, _ = components(N, [(b["a"], b["b"]) for b in beams])
    check("every node connected, no isolated components", "PASS" if deg.min() >= 1 and ncomp == 1 else "FAIL",
          f"{int((deg == 0).sum())} nodes without beams, {ncomp} connected component(s); valence min {deg.min()}, "
          f"median {int(np.median(deg))}, max {deg.max()}; nodes with fewer than 3 beams: {int((deg < 3).sum())}")

    # duplicates and degenerate beams
    pairs = sorted(cKDTree(P).query_pairs(0.01))
    same_part = [(nodes[a]["name"], nodes[b]["name"]) for a, b in pairs if nodes[a]["part"] == nodes[b]["part"]]
    lens = np.array([np.linalg.norm(P[b["b"]] - P[b["a"]]) for b in beams])
    # a beam of a few mm flips direction as soon as its nodes cross; 0.1 mm float tolerance (the dual-layer glass
    # through-thickness beams of D-030 are exactly 20.0 mm)
    short = int((lens < 0.0199).sum())
    cross = Counter(tuple(sorted((nodes[a]["part"], nodes[b]["part"]))) for a, b in pairs
                    if nodes[a]["part"] != nodes[b]["part"])
    check("no duplicate nodes within 1 cm unless intentional; no degenerate beams",
          "PASS" if not same_part and short == 0 else "FAIL",
          f"{len(pairs)} pairs within 1 cm, all between separate parts meeting at a shut line (intentional: each "
          f"part keeps its own nodes so it can detach): " + ", ".join(f"{a}/{b} {k}" for (a, b), k in cross.items())
          + f"; same-part pairs: {same_part or 'none'}; beams shorter than 2 cm: {short} (shortest "
          f"{lens.min() * 1000:.1f} mm)")

    # materials and references
    mats = {x["name"] for x in p["materials"]}
    cmats = {x["name"] for x in p.get("contactMaterials", [])}
    miss_b = sorted({b["mat"] for b in beams} - mats)
    miss_t = sorted({t["mat"] for t in g["torsionBars"]} - mats)
    miss_c = sorted({n["cmat"] for n in nodes} - cmats)
    bad_idx = sum(1 for t in tris for k in "abc" if not 0 <= t[k] < N)
    used = Counter(b["mat"] for b in beams)
    check("every beam, torsion bar and node references a defined material preset (params.json)",
          "PASS" if not (miss_b or miss_t or miss_c or bad_idx) else "FAIL",
          f"{len(used)} beam materials used of {len(mats)} defined, {len({n['cmat'] for n in nodes})} contact "
          f"materials; missing beam {miss_b or 'none'}, torsion {miss_t or 'none'}, contact {miss_c or 'none'}; "
          f"triangles with bad node index {bad_idx}")

    # break groups
    bgs = {b["bg"] for b in beams if b["bg"]} | {t["bg"] for t in tris if t["bg"]}
    miss_bg = [r for r in REQUIRED_BREAK_GROUPS
               if not (any(x.startswith(r[:-1]) for x in bgs) if r.endswith("*") else r in bgs)]
    check("break groups of section 6.3 defined", "PASS" if not miss_bg else "FAIL",
          f"{len(bgs)} groups: {', '.join(sorted(bgs))}; missing {miss_bg or 'none'}")

    # closure joints (D-063): every hinge / latch node of a door, the hood and the deck lid held in all three directions
    cj = module(ROOT / "tools/skeleton/closure_joints.py", "closure_joints")
    rows = cj.report(g, 0.3)
    bad = [r for r in rows if not r["ok"]]
    check("closure hinges and latches hold their nodes in 3D (smallest singular value of the beam directions >= 0.3, "
          "D-063)", "PASS" if rows and not bad else "FAIL",
          f"{len(rows)} joints, smallest {min(r['sv_min'] for r in rows):.2f} ({min(rows, key=lambda r: r['sv_min'])['node']})"
          + (f"; free: " + ", ".join(f"{r['node']} {r['sv_min']}" for r in bad) if bad else ""))

    # stability
    st = stab.analyse(g, p, modes=6)
    (ROOT / "docs/p2_stability.json").write_text(json.dumps(st, indent=1), encoding="utf-8")
    check(f"stability at dt = {st['dt'] * 1000:.2f} ms: exact S = lambda_max(M^-1 (dt^2 K + 2 dt C + contact)) < "
          f"{stab.HARD_LIMIT} (D-024, exact limit 4)", "PASS" if st["pass"] and not st["missing_materials"] else "FAIL",
          f"S = {st['S_exact_max']} (top modes {st['S_exact_top']}); stiffest families: " +
          ", ".join(f"{k} {v}" for k, v in list(st["family_S"].items())[:6]) +
          f"; Gershgorin upper bound max {st['gershgorin_max']} (D-004 bound, superseded)")
    check("omega*dt >= 0.5 per node (warning only, user answer 4 / D-004; the hard limit is the exact criterion)",
          "WARN" if st["omega_dt_warnings"] else "PASS",
          f"{st['omega_dt_warnings']} of {N} nodes at omega*dt >= 0.5 (max {st['omega_dt_max']}); omega = "
          "sqrt(sum k / m) ignores that neighbours move with the node, so it overstates the step-size demand of "
          "stiff clusters; the exact spectral S above is the stability criterion")

    # winding
    w = winding(g)
    (ROOT / "docs/gates/p2_winding.json").write_text(json.dumps(w, indent=1), encoding="utf-8")
    bad_t = [t for t in w["tires"] if t["edges_not_shared_by_two"] or t["inconsistent_edges"] or t["volume_l"] <= 0]
    check("tire air volumes: closed, consistently wound, positive volume (normals out of the cavity)",
          "PASS" if not bad_t else "FAIL",
          "; ".join(f"{t['group']}: {t['triangles']} tris, open edges {t['edges_not_shared_by_two']}, "
                    f"inconsistent {t['inconsistent_edges']}, {t['volume_l']} l" for t in w["tires"]))
    inward = [x for x in w["patches"] if x["orientation"] == "inward"]
    undecided = [x for x in w["patches"] if x["orientation"] == "undecided"]
    status = "FAIL" if inward or w["inconsistent_edges"] or w["degenerate"] else "WARN" if undecided else "PASS"
    weakest = w["patches"][:3]
    check("every outer-surface triangle wound outward (numeric: patch consistency + ray-escape voting)", status,
          f"{w['voted_triangles']} surface triangles in {len(w['patches'])} patches: "
          f"{sum(x['orientation'] == 'outward' for x in w['patches'])} outward, {len(inward)} inward, "
          f"{len(undecided)} undecided; inconsistent shared edges {w['inconsistent_edges']}, edges shared by 3+ "
          f"triangles {w['edges_shared_by_3_or_more']}, degenerate triangles {w['degenerate']}, two-sided "
          f"triangles {len(w['two_sided_triangles'])}; weakest patches: " +
          "; ".join(f"{'/'.join(x['groups'])} vote {x['vote']} ({x['triangles']} tris)" for x in weakest) +
          " (details docs/gates/p2_winding.json)")

    # export pipeline and evidence
    sa = ROOT / "Unity/HellcatSandbox/Assets/StreamingAssets/Vehicles" / vehicle
    same = all((sa / f).exists() and (sa / f).read_bytes() == (d / f).read_bytes() for f in ("geometry.json", "params.json"))
    check("export pipeline: geometry.json + params.json written for the Unity project (StreamingAssets copy in sync)",
          "PASS" if same else "FAIL", f"{d.relative_to(ROOT)} -> {sa.relative_to(ROOT)}: "
          f"{'identical' if same else 'missing or different'}; geometry.json {(d / 'geometry.json').stat().st_size:,} bytes")
    va = ROOT / "docs/video_assets/P2"
    pics = sorted(x.name for x in va.glob("*.png"))
    overlays = [x for x in pics if x.endswith("_overlay.png")]
    check("evidence: skeleton debug-view renders (skeleton alone and over the paint)",
          "PASS" if len(pics) >= 10 and overlays else "FAIL", f"{len(pics)} stills ({len(overlays)} overlays)")

    failed = sum(r["status"] == "FAIL" for r in results)
    warned = sum(r["status"] == "WARN" for r in results)
    out = ROOT / "docs/gates"
    (out / "gate_p2.json").write_text(json.dumps({"gate": "P2 (G-Skeleton)", "vehicle": vehicle, "pass": failed == 0,
                                                  "fail": failed, "warn": warned, "checks": results}, indent=2),
                                      encoding="utf-8")
    lines = ["# Gate P2 (G-Skeleton)", "", f"Vehicle `{vehicle}`. Result: **{'PASS' if failed == 0 else 'FAIL'}** "
             f"({failed} FAIL, {warned} WARN, {len(results)} checks)", "", "| # | Check | Status | Detail |",
             "|---|---|---|---|"]
    lines += [f"| {i} | {r['check']} | {r['status']} | {r['detail'].replace('|', '/')} |" for i, r in enumerate(results, 1)]
    (out / "gate_p2.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['status']:4}  {r['check']}  --  {r['detail'][:300]}")
    print(f"P2 gate: {'PASS' if failed == 0 else 'FAIL'} ({failed} fail, {warned} warn)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
