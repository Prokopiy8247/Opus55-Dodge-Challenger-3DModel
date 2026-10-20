"""Fore-aft motion of suspension nodes in the snapshot window relative to the body cell (peak-to-peak, mm)."""
import json, re, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
g = json.loads((ROOT / "sim/vehicle/hellcat/geometry.json").read_text())
names = [n["name"] for n in g["nodes"]]
parts = [n["part"] for n in g["nodes"]]
data = np.loadtxt(sys.argv[1], delimiter=",", skiprows=1)
ts = np.unique(data[:, 0])
N = len(names)
X = np.zeros((len(ts), N, 3))
for k, t in enumerate(ts):
    rows = data[data[:, 0] == t]
    X[k, rows[:, 1].astype(int)] = rows[:, 2:5]
cell = [i for i in range(N) if parts[i] == "body" and re.split(r"\d", names[i], 1)[0].rstrip("_") in ("sill", "floor", "rail", "tunnel")]
cz = X[:, cell, 2].mean(1)
pre = sys.argv[2] if len(sys.argv) > 2 else "FL_"
rows = []
for i in range(N):
    if names[i].startswith(pre) and not names[i].startswith((pre + "rim", pre + "tr")):
        rel = X[:, i, 2] - cz
        rows.append((names[i], parts[i], (X[:, i, 2].max() - X[:, i, 2].min()) * 1000, (rel.max() - rel.min()) * 1000, X[0, i, 1]))
for nm in ("lca_f", "lca_r", "uca_f", "uca_r"):
    for side in ("L", "R"):
        pass
extra = [i for i in range(N) if names[i].startswith(pre)]
for r in sorted(rows, key=lambda r: -r[4]):
    print(f"  {r[0]:16s} {r[1]:9s} y {r[4]:.3f}  abs fwd p-p {r[2]:6.2f}  rel to cell {r[3]:6.2f}")
print("cell fwd p-p", (cz.max() - cz.min()) * 1000)
