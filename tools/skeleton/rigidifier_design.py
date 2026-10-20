"""Rigidifier design for the global body stiffness (P3, decision D-040).

The node-beam body is 15-50x too soft globally (tools/p3/body_stiffness.py: torsion ~1.1 kN m/deg, bending ~0.2 kN/mm;
real cars ~15-35 kN m/deg and ~10-20 kN/mm): the stability bound caps every beam at roughly m / dt^2, and the cabin is an
open frame around the door openings whose stiffness in a real car comes from closed-section shells. As in BeamNG-style
models, long invisible "rigidifier" beams through the cabin and between the cabin and its ends stand in for that shell
stiffness; with k L^2 leverage a few of them stiffen the body far more per unit of stability cost than local members.

Method (as tools/skeleton/brace_design.py, D-030): truss topology sensitivity on several global load cases of the
body-in-white structure (body part + bonded glass; closures, suspension, wheels and powertrain removed):
  torsion  rear spring towers fixed, front-centre vertical support, +-F on the front towers
  bending  the four towers held, 4 kN down on the sills at the B-pillar station
  front    cabin floor held, 2 kN down on the front towers (front structure cantilever) and 4 kN fore-aft (braking path)
  rear     cabin floor held, 2 kN down on the rear towers
For a candidate beam a-b of stiffness k, each case's compliance falls by about k e^2 (e = n_ab . (u_b - u_a)); the score
is the sum of these reductions relative to each case's compliance, per unit stability cost (1/m_a + 1/m_b). Greedy
rounds of mirror pairs with distinct nodes (at most --per-node rigidifiers per node), re-solved after each round.
Writes tools/blender/hcar/hskel_rigidifiers.json (node-name pairs), which hskel.py adds with the "rigidifier" material.

Crush zones (D-057): with --zone-front / --zone-rear no candidate node lies ahead of / behind those z (hskel drops any
listed rigidifier that reaches into a zone anyway). --append starts from the rigidifiers already in geometry.json, counts
them against the per-node limit and budget, and writes them back together with the new ones; --target-bending stops
the rounds once the bending stiffness reaches it.

Usage: tools/.venv/Scripts/python.exe tools/skeleton/rigidifier_design.py [--rounds 8] [--per-round 8] [--k 1500000]
       [--zone-front 1.6 --zone-rear -2.0] [--append] [--target-bending 1.75]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
from mechanisms import assemble  # noqa: E402

OUT = ROOT / "tools" / "blender" / "hcar" / "hskel_rigidifiers.json"
KEEP_PARTS = ("body", "glass_windshield", "glass_rear", "glass_quarter_L", "glass_quarter_R")
STRUCT = ("sill", "floor", "tunnel", "rail", "hinge", "fw", "cowl", "bp", "cp", "frail", "rrail", "aplo", "apron",
          "rtower", "whouse", "shelf", "bulk", "rpanel_lo", "rpanel_hi", "tfloor", "xm", "core_lo", "core_hi", "hdrF",
          "hdrR", "dash")
fam = lambda n: re.split(r"\d", n, 1)[0].rstrip("_")


def mirror(n):
    if n.endswith("_L"):
        return n[:-2] + "_R"
    if n.endswith("_R"):
        return n[:-2] + "_L"
    return n


class Body:
    def __init__(self, g, p, k):
        self.g, self.p, self.k = g, p, k
        self.N = N = len(g["nodes"])
        self.names = [n["name"] for n in g["nodes"]]
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.P = np.array([n["p"] for n in g["nodes"]], float)
        self.m = np.array([n["m"] for n in g["nodes"]], float)
        self.keep = np.array([n["part"] in KEEP_PARTS and "_tip_" not in n["name"] for n in g["nodes"]])
        sub = dict(g)
        sub["beams"] = [b for b in g["beams"] if self.keep[b["a"]] and self.keep[b["b"]]]
        sub["hinges"] = [h for h in g.get("hinges", []) if all(self.keep[i] for i in h["n"])]
        sub["pressureGroups"] = []
        self.K0 = assemble(sub, p, geometric=False).tocsr()
        self.extra = []                                   # (a, b) rigidifiers
        self.drop = np.where(~self.keep)[0]
        i = self.idx
        self.tL, self.tR, self.rL, self.rR = i["aplo1_L"], i["aplo1_R"], i["rtower_L"], i["rtower_R"]
        fc = i["xm1_C"] if "xm1_C" in i else i["rack_C"]
        cabin = [j for j in range(N) if self.keep[j] and fam(self.names[j]) in ("sill", "floor", "tunnel")
                 and -0.9 < self.P[j, 2] < 0.9]
        sb = [j for j in range(N) if self.keep[j] and fam(self.names[j]) == "sill" and abs(self.P[j, 2] + 0.10) < 0.25]
        dofs = lambda nodes, cs: [3 * n + c for n in nodes for c in cs]
        self.cases = []
        F = 1000.0
        f = np.zeros(3 * N)
        f[3 * self.tL + 1], f[3 * self.tR + 1] = F, -F
        self.cases.append(("torsion", f, dofs([self.rL, self.rR], (0, 1, 2)) + [3 * fc + 1]))
        f = np.zeros(3 * N)
        f[[3 * j + 1 for j in sb]] = -4000.0 / len(sb)
        self.cases.append(("bending", f, dofs([self.tL, self.tR, self.rL, self.rR], (1,)) +
                           [3 * self.rL + 0, 3 * self.rL + 2, 3 * self.rR + 2, 3 * self.tL + 2]))
        f = np.zeros(3 * N)
        f[[3 * self.tL + 1, 3 * self.tR + 1]] = -1000.0
        f[[3 * self.tL + 2, 3 * self.tR + 2]] = -2000.0
        self.cases.append(("front", f, dofs(cabin, (0, 1, 2))))
        f = np.zeros(3 * N)
        f[[3 * self.rL + 1, 3 * self.rR + 1]] = -1000.0
        self.cases.append(("rear", f, dofs(cabin, (0, 1, 2))))
        self.track = self.P[self.tL, 0] - self.P[self.tR, 0]

    def K(self):
        if not self.extra:
            return self.K0
        rows, cols, vals = [], [], []
        for a, b in self.extra:
            d = self.P[b] - self.P[a]
            e = d / np.linalg.norm(d)
            blk = self.k * np.outer(e, e)
            for (i, j, s) in ((a, a, 1.0), (b, b, 1.0), (a, b, -1.0), (b, a, -1.0)):
                for r in range(3):
                    for q in range(3):
                        rows.append(3 * i + r)
                        cols.append(3 * j + q)
                        vals.append(s * blk[r, q])
        return self.K0 + sp.csr_matrix((vals, (rows, cols)), shape=self.K0.shape)

    def solve_all(self):
        K = (self.K() + 1e-3 * sp.identity(3 * self.N)).tocsr()
        drop = np.concatenate([3 * self.drop + c for c in range(3)])
        out = []
        for name, f, fixed in self.cases:
            fx = np.union1d(drop, fixed)
            free = np.setdiff1d(np.arange(3 * self.N), fx)
            u = np.zeros(3 * self.N)
            u[free] = splu(K[free][:, free].tocsc()).solve(f[free])
            out.append((name, u.reshape(-1, 3), float(f @ u)))
        return out

    def metrics(self, sols):
        d = {n: (u, c) for n, u, c in sols}
        u = d["torsion"][0]
        twist = (u[self.tL, 1] - u[self.tR, 1]) / self.track
        kt = 1000.0 * abs(self.track) / abs(twist) / 1000 * np.pi / 180
        names = self.names
        sb = [j for j in range(self.N) if self.keep[j] and fam(names[j]) == "sill" and abs(self.P[j, 2] + 0.10) < 0.25]
        kb = 4000.0 / (-d["bending"][0][sb, 1].mean()) / 1e6
        fr = -d["front"][0][[self.tL, self.tR], 1].mean()
        rr = -d["rear"][0][[self.rL, self.rR], 1].mean()
        return {"torsion_kNm_per_deg": round(kt, 2), "bending_kN_per_mm": round(kb, 3),
                "front_tower_mm_per_kN": round(fr * 1000, 3), "rear_tower_mm_per_kN": round(rr * 1000, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--per-round", type=int, default=8, help="mirror pairs per round")
    ap.add_argument("--k", type=float, default=1500000.0)
    ap.add_argument("--per-node", type=int, default=2)
    ap.add_argument("--min-len", type=float, default=0.6)
    ap.add_argument("--max-len", type=float, default=3.6)
    ap.add_argument("--target-kt", type=float, default=15.0)
    ap.add_argument("--budget", type=float, default=0.4,
                    help="per node: added dt^2 sum k / m of the rigidifiers at most this (mass balancing absorbs it)")
    ap.add_argument("--zone-front", type=float, default=99.0, help="no candidate node ahead of this z (crush zone, D-057)")
    ap.add_argument("--zone-rear", type=float, default=-99.0, help="no candidate node behind this z")
    ap.add_argument("--append", action="store_true", help="keep the rigidifiers in geometry.json and add to them")
    ap.add_argument("--target-bending", type=float, default=0.0, help="stop once bending reaches this (kN/mm)")
    ns = ap.parse_args()
    g, p = load("hellcat")
    B = Body(g, p, ns.k)
    names, P, m = B.names, B.P, B.m
    existing = {(min(b["a"], b["b"]), max(b["a"], b["b"])) for b in g["beams"]}
    cand_nodes = [i for i in range(B.N) if B.keep[i] and fam(names[i]) in STRUCT and m[i] >= 0.5
                  and ns.zone_rear <= P[i, 2] <= ns.zone_front]
    kept = []
    if ns.append:
        kept = [(b["a"], b["b"]) for b in g["beams"] if b["mat"] == "rigidifier"]
        print(f"{len(kept)} rigidifiers kept from geometry.json")
    print(f"{len(cand_nodes)} candidate nodes")
    ci = np.array(cand_nodes)
    A, Bn = np.triu_indices(len(ci), 1)
    a, b = ci[A], ci[Bn]
    d = P[b] - P[a]
    L = np.linalg.norm(d, axis=1)
    ok = (L >= ns.min_len) & (L <= ns.max_len)
    a, b, d, L = a[ok], b[ok], d[ok], L[ok]
    ok = np.array([(min(x, y), max(x, y)) not in existing for x, y in zip(a, b)])
    a, b, d, L = a[ok], b[ok], d[ok], L[ok]
    n_hat = d / L[:, None]
    cost = 1.0 / m[a] + 1.0 / m[b]
    print(f"{len(a)} candidate pairs")
    used = {}
    for x, y in kept:
        for n in (x, y):
            used[n] = used.get(n, 0) + 1
    sols = B.solve_all()
    print("start:", B.metrics(sols))
    for rnd in range(ns.rounds):
        score = np.zeros(len(a))
        for name, u, c in sols:
            e = np.einsum("ij,ij->i", n_hat, u[b] - u[a])
            score += ns.k * e * e / c
        score /= cost
        order = np.argsort(-score)
        added = 0
        for j in order:
            if added >= ns.per_round:
                break
            x, y = int(a[j]), int(b[j])
            mx, my = B.idx.get(mirror(names[x])), B.idx.get(mirror(names[y]))
            pair = [(x, y)]
            if mx is not None and my is not None and {mx, my} != {x, y}:
                pair.append((mx, my))
            nodes = [n for pr in pair for n in pr]
            dt2 = p.get("dt", 0.0005) ** 2
            if any(used.get(n, 0) >= ns.per_node or dt2 * ns.k * (used.get(n, 0) + 1) / m[n] > ns.budget for n in nodes)                     or any(pr in B.extra or pr[::-1] in B.extra for pr in pair):
                continue
            for pr in pair:
                B.extra.append(pr)
                for n in pr:
                    used[n] = used.get(n, 0) + 1
            added += 1
        sols = B.solve_all()
        met = B.metrics(sols)
        print(f"round {rnd + 1}: {len(B.extra)} rigidifiers -> {met}")
        if met["torsion_kNm_per_deg"] >= ns.target_kt or (ns.target_bending > 0 and met["bending_kN_per_mm"] >= ns.target_bending):
            break
    OUT.write_text(json.dumps([[names[x], names[y]] for x, y in kept + B.extra], indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({len(B.extra)} pairs)")
    for x, y in B.extra[:12]:
        print(f"   {names[x]:14s} - {names[y]:14s} {np.linalg.norm(P[y] - P[x]):.2f} m  m {m[x]:.1f}/{m[y]:.1f} kg")


if __name__ == "__main__":
    main()
