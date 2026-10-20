"""Quick facts about sim/vehicle/<vehicle>/geometry.json for the P3b work: wheels, break groups, parts.

Usage: tools/.venv/Scripts/python.exe tools/p3b/geo_info.py [--vehicle hellcat]
"""
import argparse
import collections
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vehicle", default="hellcat")
    ns = ap.parse_args()
    g = json.loads((ROOT / "sim/vehicle" / ns.vehicle / "geometry.json").read_text(encoding="utf-8"))
    nodes = g["nodes"]
    P = np.array([n["p"] for n in nodes])
    M = np.array([n["m"] for n in nodes])
    print("nodes", len(nodes), "mass", M.sum(), "com", (P * M[:, None]).sum(0) / M.sum())
    for w in g["wheels"]:
        ai, ao = P[w["axleInner"]], P[w["axleOuter"]]
        hub = 0.5 * (ai + ao)
        rim = P[w["rim"]]
        tr = P[w["tread"]]
        axis = (ao - ai) / np.linalg.norm(ao - ai)
        rr = rim - hub
        rr -= np.outer(rr @ axis, axis)
        tt = tr - hub
        tt -= np.outer(tt @ axis, axis)
        rim_mass = M[w["rim"]].sum()
        tread_mass = M[w["tread"]].sum()
        I_rim = (M[w["rim"]] * (np.linalg.norm(rr, axis=1) ** 2)).sum()
        print(f"wheel {w['name']}: hub {hub.round(4)}, axis {axis.round(3)}, radius {w['radius']}, rim {len(w['rim'])} nodes "
              f"{rim_mass:.2f} kg r {np.linalg.norm(rr, axis=1).min():.3f}-{np.linalg.norm(rr, axis=1).max():.3f} I {I_rim:.3f}, "
              f"tread {len(w['tread'])} nodes {tread_mass:.2f} kg r {np.linalg.norm(tt, axis=1).min():.4f}-{np.linalg.norm(tt, axis=1).max():.4f}, "
              f"driven {w['driven']} steered {w['steered']} driveReaction {len(w['driveReaction'])} windupBody {len(w['windupBody'])} "
              f"pg {w['pressureGroup']}")
    bgs = collections.Counter(b["bg"] for b in g["beams"] if b["bg"])
    print("break groups:", len(bgs))
    for k, v in sorted(bgs.items()):
        print(f"  {k}: {v} beams")
    parts = collections.Counter(n["part"] for n in nodes)
    print("parts:", dict(sorted(parts.items())))
    # wheel part nodes (all nodes of the tire assembly)
    for w in g["wheels"]:
        part = nodes[w["axleInner"]]["part"]
        idx = [i for i, n in enumerate(nodes) if n["part"] == part]
        print(f"part of wheel {w['name']} axle: {part} ({len(idx)} nodes, {M[idx].sum():.2f} kg)")
    pg = g["pressureGroups"]
    for p in pg:
        print("pressure group", p["name"], p["wheel"], len(p["tris"]), "tris", p["pressure"], "Pa")


if __name__ == "__main__":
    main()
