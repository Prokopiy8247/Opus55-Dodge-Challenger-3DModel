"""Lists the shared edges whose two triangles traverse them in the same direction (inconsistent winding).

Usage: tools/.venv/Scripts/python.exe tools/skeleton/diag_winding.py [vehicle]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main():
    vehicle = sys.argv[1] if len(sys.argv) > 1 else "hellcat"
    g = json.loads((ROOT / "sim/vehicle" / vehicle / "geometry.json").read_text(encoding="utf-8"))
    nodes, tris = g["nodes"], g["triangles"]
    P = np.array([n["p"] for n in nodes])
    pressure = {i for pg in g["pressureGroups"] for i in pg["tris"]}
    edge = defaultdict(list)
    for i, t in enumerate(tris):
        if i in pressure:
            continue
        a, b, c = t["a"], t["b"], t["c"]
        for e in ((a, b), (b, c), (c, a)):
            edge[(min(e), max(e))].append((i, e))
    for (u, v), lst in edge.items():
        if len(lst) == 2 and lst[0][1] == lst[1][1]:
            (i, _), (j, _) = lst
            ni = np.cross(P[tris[i]["b"]] - P[tris[i]["a"]], P[tris[i]["c"]] - P[tris[i]["a"]])
            nj = np.cross(P[tris[j]["b"]] - P[tris[j]["a"]], P[tris[j]["c"]] - P[tris[j]["a"]])
            ni, nj = ni / np.linalg.norm(ni), nj / np.linalg.norm(nj)
            print(f"{nodes[u]['name']:>14} {nodes[v]['name']:>14}  tri {i} ({tris[i]['group']}) n {np.round(ni, 2)}"
                  f"  tri {j} ({tris[j]['group']}) n {np.round(nj, 2)}")


if __name__ == "__main__":
    main()
