"""Rest-shape deviation from a T6 node dump: per family, displacement after removing the best-fit rigid motion of the
cell (Unity frame y up). Usage: rest_shape.py docs/p3/validation/T6_spawn_nodes.csv"""
import csv, re, sys
from collections import defaultdict
import numpy as np

rows = list(csv.DictReader(open(sys.argv[1])))
M = np.array([[float(r["mx"]), float(r["my"]), float(r["mz"])] for r in rows])
X = np.array([[float(r["x"]), float(r["y"]), float(r["z"])] for r in rows])
names = [r["name"] for r in rows]
parts = [r["part"] for r in rows]
fam = lambda n: re.split(r"\d", n, 1)[0].rstrip("_")
cell = np.array([p == "body" and fam(n) in ("sill", "floor", "rail", "bulk", "tunnel", "shelf", "apillar", "bp", "cpillar", "whouse", "hdrF", "hdrR", "bowB")
                 for n, p in zip(names, parts)])
if cell.sum() < 10:
    cell = np.array([p == "body" for p in parts])
A, B = M[cell], X[cell]
ca, cb = A.mean(0), B.mean(0)
H = (A - ca).T @ (B - cb)
U, S, Vt = np.linalg.svd(H)
D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
R = Vt.T @ D @ U.T
Y = (M - ca) @ R.T + cb                      # model positions moved rigidly onto the cell
d = X - Y
print(f"cell nodes {cell.sum()}, rigid translation {cb - ca}, rms cell residual {np.sqrt((d[cell]**2).sum(1).mean())*1000:.1f} mm")
byf = defaultdict(list)
for i, n in enumerate(names):
    byf[fam(n)].append(i)
out = []
for f, idx in byf.items():
    dd = d[idx]
    out.append((np.abs(dd[:, 1]).max(), f, len(idx), dd[:, 1].mean(), dd[:, 1].min(), np.linalg.norm(dd, axis=1).max()))
for mx, f, n, mean, mn, mxn in sorted(out, reverse=True)[:40]:
    print(f"  {f:22s} {n:4d} nodes  dy mean {mean*1000:7.1f} mm  min {mn*1000:7.1f}  max|d| {mxn*1000:7.1f} mm")
