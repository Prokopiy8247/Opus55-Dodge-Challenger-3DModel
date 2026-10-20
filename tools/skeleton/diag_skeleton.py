"""Skeleton diagnostics: duplicate node pairs (< 1 cm), beam materials in use, node valence and
mass per part. Reads sim/vehicle/hellcat/geometry.json (Unity frame: x right, y up, z forward).

Usage: tools/.venv/Scripts/python.exe tools/skeleton/diag_skeleton.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main():
    g = json.loads((ROOT / "sim/vehicle/hellcat/geometry.json").read_text(encoding="utf-8"))
    P = np.array([n["p"] for n in g["nodes"]])
    names = [n["name"] for n in g["nodes"]]
    from scipy.spatial import cKDTree
    pairs = sorted(cKDTree(P).query_pairs(0.01))
    print(f"duplicate pairs (<1 cm): {len(pairs)}")
    for a, b in pairs[:40]:
        print(f"  {names[a]:28s} {names[b]:28s} {np.linalg.norm(P[a] - P[b]) * 1000:.1f} mm")
    mats = Counter(b["mat"] for b in g["beams"])
    print("materials:", ", ".join(f"{k} {v}" for k, v in sorted(mats.items())))
    parts = defaultdict(float)
    for n in g["nodes"]:
        parts[n["part"]] += n["m"]
    print("mass by part:", ", ".join(f"{k} {v:.1f}" for k, v in sorted(parts.items(), key=lambda kv: -kv[1])))
    deg = Counter()
    for b in g["beams"]:
        deg[b["a"]] += 1
        deg[b["b"]] += 1
    print("valence max", max(deg.values()), "mean", round(sum(deg.values()) / len(P), 2))


if __name__ == "__main__":
    main()
