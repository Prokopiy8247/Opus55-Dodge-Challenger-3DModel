"""Rigid-body decomposition of the dominant snapshot oscillation: the body's translation and rotation vs the wheel
assemblies (rim rings, tread, knuckles) over time, to locate the compliance of a fore-aft rocking mode."""
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
def sel(f):
    return np.array([i for i in range(N) if f(i)])
body = sel(lambda i: parts[i] == "body" and re.split(r"\d", names[i], 1)[0].rstrip("_") in ("sill", "floor", "rail", "tunnel", "bp", "cp"))
groups = {"body(cell)": body}
for w in ("FL", "FR", "RL", "RR"):
    groups[f"{w} rim"] = sel(lambda i, w=w: names[i].startswith(f"{w}_rim"))
    groups[f"{w} tread bottom"] = None
    groups[f"{w} axle"] = sel(lambda i, w=w: names[i].startswith(f"{w}_axle"))
for w in ("FL", "FR", "RL", "RR"):
    tr = sel(lambda i, w=w: names[i].startswith(f"{w}_tr"))
    groups[f"{w} tread bottom"] = tr[np.argsort(X[0, tr, 1])[:9]]
print("peak-to-peak motion over the window (mm): z fwd / y up; rotation about x (pitch, mrad)")
for name, ids in groups.items():
    c = X[:, ids].mean(1)
    zz = (c[:, 2].max() - c[:, 2].min()) * 1000
    yy = (c[:, 1].max() - c[:, 1].min()) * 1000
    # pitch of the group: fit z-displacement vs y height (rotation about x)
    P0 = X[0, ids]
    rot = []
    for k in range(len(ts)):
        d = X[k, ids] - P0
        A = np.c_[np.ones(len(ids)), P0[:, 1] - P0[:, 1].mean()]
        coef, *_ = np.linalg.lstsq(A, d[:, 2], rcond=None)
        rot.append(coef[1])
    rot = np.array(rot)
    print(f"  {name:18s} fwd p-p {zz:6.2f}  up p-p {yy:6.2f}  pitch p-p {(rot.max()-rot.min())*1000:6.2f}")
