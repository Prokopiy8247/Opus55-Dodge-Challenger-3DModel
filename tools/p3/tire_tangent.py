"""Tangent stiffness of one inflated tire (P3): beams + cord pre-tension (D-028) + isothermal cavity pressure, the same
force model as the solver, finite-differenced at the model (spawn) shape and at the solver's loaded rest state.

Reports the hub stiffness against a stuck contact patch with the rim locked against rotation (brakes on):
fore-aft (z), lateral (x) and vertical (y), for four force models: beams only (what the linear tools see), beams +
pre-tension, beams + pressure, and the full model. The parked car's fore-aft surge mode sits on the fore-aft value.

Usage: tools/.venv/Scripts/python.exe tools/p3/tire_tangent.py [--wheel FR] [--nodes docs/p3/validation/T6_spawn_nodes.csv]
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402

ATM = 101325.0


class Tire:
    def __init__(self, g, p, wheel):
        self.g, self.p = g, p
        mats = {m["name"]: m for m in p["materials"]}
        w = next(x for x in g["wheels"] if x["name"] == wheel)
        self.w = w
        self.rigid = sorted(set(w["rim"]) | {w["axleInner"], w["axleOuter"]})
        nodes = set(w["rim"]) | set(w["tread"]) | {w["axleInner"], w["axleOuter"]}
        self.nodes = sorted(nodes)
        self.loc = {n: k for k, n in enumerate(self.nodes)}
        P0 = np.array([g["nodes"][n]["p"] for n in self.nodes], float)
        self.P0 = P0
        self.beams = []                                   # (ia, ib, k, L0)
        for b in g["beams"]:
            if b["a"] not in nodes or b["b"] not in nodes:
                continue
            k = mats[b["mat"]].get("spring", 0.0) or 0.0
            if k <= 0 or b["type"] in ("HYDRO", "SUPPORT"):
                continue
            ia, ib = self.loc[b["a"]], self.loc[b["b"]]
            L0 = np.linalg.norm(P0[ib] - P0[ia]) * (b.get("pre", 1.0) or 1.0)
            self.beams.append((ia, ib, k, L0))
        pg = next(x for x in g["pressureGroups"] if x.get("wheel") == wheel or x["name"] == f"tire_{wheel}")
        self.p0 = pg["pressure"]
        self.tris = np.array([[self.loc[g["triangles"][t][c]] for c in ("a", "b", "c")] for t in pg["tris"]])
        self.cavity = sorted(set(self.tris.ravel()))
        self.V0 = self.volume(P0)
        self.gas0 = (self.p0 + ATM) * self.V0
        self.T = self.pretension()

    def volume(self, X):
        o = X[self.tris[0, 0]]
        a, b, c = X[self.tris[:, 0]] - o, X[self.tris[:, 1]] - o, X[self.tris[:, 2]] - o
        return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)

    def pressure_forces(self, X, p_gauge):
        F = np.zeros_like(X)
        a, b, c = X[self.tris[:, 0]], X[self.tris[:, 1]], X[self.tris[:, 2]]
        area = 0.5 * np.cross(b - a, c - a)
        for k in range(3):
            np.add.at(F, self.tris[:, k], p_gauge * area / 3.0)
        return F

    def pretension(self):
        """SolvePretension of SoftBodyWorld: cords between cavity nodes carry the beam forces of K u = f_pressure."""
        cav = set(self.cavity)
        cl = {n: k for k, n in enumerate(self.cavity)}
        dim = 3 * len(cl)
        K = np.zeros((dim, dim))
        cords = []
        for q, (ia, ib, k, L0) in enumerate(self.beams):
            if ia not in cav or ib not in cav:
                continue
            e = self.P0[ib] - self.P0[ia]
            e /= np.linalg.norm(e)
            a, b = 3 * cl[ia], 3 * cl[ib]
            blk = k * np.outer(e, e)
            K[a:a + 3, a:a + 3] += blk
            K[b:b + 3, b:b + 3] += blk
            K[a:a + 3, b:b + 3] -= blk
            K[b:b + 3, a:a + 3] -= blk
            cords.append((q, e))
        f = self.pressure_forces(self.P0, self.p0)[self.cavity].ravel()
        u = None
        eps = 1e-9
        while u is None:
            A = K + eps * np.trace(K) / dim * np.eye(dim)
            try:
                L = np.linalg.cholesky(A)
                u = np.linalg.solve(L.T, np.linalg.solve(L, f))
            except np.linalg.LinAlgError:
                eps *= 100
        T = np.zeros(len(self.beams))
        for q, e in cords:
            ia, ib, k, _ = self.beams[q]
            du = u[3 * cl[ib]:3 * cl[ib] + 3] - u[3 * cl[ia]:3 * cl[ia] + 3]
            T[q] = k * (e @ du)
        return T

    def forces(self, X, pre=True, pres=True):
        F = np.zeros_like(X)
        for q, (ia, ib, k, L0) in enumerate(self.beams):
            d = X[ib] - X[ia]
            L = np.linalg.norm(d)
            e = d / L
            t = k * (L - L0) + (self.T[q] if pre else 0.0)
            F[ia] += t * e
            F[ib] -= t * e
        if pres:
            pg = self.gas0 / self.volume(X) - ATM
            F += self.pressure_forces(X, pg)
        return F

    def tangent(self, X, pre=True, pres=True, h=1e-6):
        n = 3 * len(self.nodes)
        K = np.zeros((n, n))
        for j in range(n):
            Xp, Xm = X.copy(), X.copy()
            Xp.flat[j] += h
            Xm.flat[j] -= h
            K[:, j] = -(self.forces(Xp, pre, pres) - self.forces(Xm, pre, pres)).ravel() / (2 * h)
        return 0.5 * (K + K.T), K


def hub_stiffness(K, tire, patch):
    """Stiffness of the rigid rim set (translation only: rotation locked) against the stuck patch nodes, per axis."""
    n = len(tire.nodes)
    R = [tire.loc[i] for i in tire.rigid]
    fixed = set(R) | set(patch)
    F = [k for k in range(n) if k not in fixed]
    fd = np.array([3 * k + c for k in F for c in range(3)])
    out = {}
    for ax, c in (("fore-aft z", 2), ("lateral x", 0), ("vertical y", 1)):
        uR = np.zeros(3 * n)
        for k in R:
            uR[3 * k + c] = 1.0
        rhs = -K[np.ix_(fd, np.arange(3 * n))] @ uR
        uF = np.linalg.solve(K[np.ix_(fd, fd)], rhs)
        u = uR.copy()
        u[fd] = uF
        f = K @ u
        out[ax] = sum(f[3 * k + c] for k in R)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wheel", default="FR")
    ap.add_argument("--nodes", default=str(ROOT / "docs/p3/validation/T6_spawn_nodes.csv"))
    ns = ap.parse_args()
    g, p = load("hellcat")
    tire = Tire(g, p, ns.wheel)
    print(f"{ns.wheel}: {len(tire.nodes)} nodes, {len(tire.beams)} beams, {len(tire.tris)} cavity triangles, "
          f"V0 {tire.V0 * 1000:.2f} L, pre-tension max {np.abs(tire.T).max():.0f} N, "
          f"{int((tire.T != 0).sum())} cords")
    # equilibrium check at the spawn shape: pre-tension balances the pressure
    r = tire.forces(tire.P0)
    print(f"  spawn residual |F| max over the tread {np.abs(r[[tire.loc[i] for i in tire.w['tread']]]).max():.3e} N")
    # loaded rest state from the solver's node dump (positions at rest, contact forces)
    rows = list(csv.DictReader(open(ns.nodes)))
    Xl = np.array([[float(rows[n]["x"]), float(rows[n]["y"]), float(rows[n]["z"])] for n in tire.nodes])
    patch = [tire.loc[n] for n in tire.w["tread"] if float(rows[n]["contact_N"]) > 0]
    print(f"  loaded state: {len(patch)} tread nodes in contact, volume {tire.volume(Xl) / tire.V0:.4f} V0, "
          f"gauge {(tire.gas0 / tire.volume(Xl) - ATM) / 1000:.1f} kPa")
    # the spawn shape has no contact: use the same nodes as the patch (lowest tread nodes)
    for label, X in (("spawn shape", tire.P0), ("loaded rest", Xl)):
        print(f"  {label}:")
        for model, pre, pres in (("beams only", False, False), ("beams + pre-tension", True, False),
                                 ("beams + pressure", False, True), ("full (solver)", True, True)):
            K, Kraw = tire.tangent(X, pre, pres)
            asym = np.abs(Kraw - Kraw.T).max() / np.abs(Kraw).max()
            k = hub_stiffness(K, tire, patch)
            ev = np.linalg.eigvalsh(K)
            print(f"    {model:20s} " + "  ".join(f"{a} {v / 1000:8.1f} kN/m" for a, v in k.items())
                  + f"   (negative eigenvalues {int((ev < -1e-3 * ev.max()).sum())}, asym {asym:.1e})")


if __name__ == "__main__":
    main()
