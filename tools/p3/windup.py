"""Wind-up stiffness of each knuckle: a pure couple about the wheel's spin axis (fore-aft forces +F at the upper and -F
at the lower ball joint), the body cell held by inertia relief, wheel parts free; reports the knuckle rotation and the
beams that store the most strain energy (where the compliance is). Usage: windup.py [FL|RL]"""
import re, sys
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load
from mechanisms import assemble
g, p = load("hellcat")
K = assemble(g, p).tocsr()
N = len(g["nodes"])
P = np.array([n["p"] for n in g["nodes"]], float)
m = np.array([n["m"] for n in g["nodes"]], float)
names = [n["name"] for n in g["nodes"]]
idx = {n: i for i, n in enumerate(names)}
mats = {mm["name"]: mm for mm in p["materials"]}
w = sys.argv[1] if len(sys.argv) > 1 else "FL"
up, lo = (f"{w}_ubj", f"{w}_lbj") if w[0] == "F" else (f"{w}_kup", f"{w}_klr")
fam = lambda n: re.split(r"\d", n, 1)[0].rstrip("_")
cell = np.array([g["nodes"][i]["part"] == "body" and fam(names[i]) in ("sill", "floor", "rail", "tunnel", "bp", "cp") for i in range(N)])
# hold the cell rigidly (all its dofs) to remove rigid motion; everything else free
free = np.where(~cell)[0]
dof = np.repeat(free * 3, 3) + np.tile([0, 1, 2], len(free))
lu = splu((K[dof][:, dof] + 1e-6 * sp.identity(len(dof))).tocsc())
F = 100.0
f = np.zeros((N, 3))
f[idx[up], 2] += F
f[idx[lo], 2] -= F
h = P[idx[up], 1] - P[idx[lo], 1]
u = np.zeros(3 * N)
u[dof] = lu.solve(f.ravel()[dof])
U = u.reshape(-1, 3)
rot = (U[idx[up], 2] - U[idx[lo], 2]) / h
print(f"{w}: couple {F * h:.1f} N m -> knuckle rotation {rot * 1000:.3f} mrad -> wind-up stiffness {F * h / rot / 1000:.1f} kN m/rad")
E = []
for j, b in enumerate(g["beams"]):
    k = mats[b["mat"]].get("spring", 0.0) or 0.0
    if k <= 0:
        continue
    d = P[b["b"]] - P[b["a"]]
    L = np.linalg.norm(d)
    e = d / L
    s = e @ (U[b["b"]] - U[b["a"]])
    E.append((0.5 * k * s * s, names[b["a"]], names[b["b"]], b["mat"], s * 1000))
E.sort(key=lambda r: -r[0])
tot = sum(r[0] for r in E)
print(f"strain energy {tot:.4f} J; top beams:")
for r in E[:14]:
    print(f"   {r[0] / tot * 100:5.1f} %  {r[1]:14s} {r[2]:14s} {r[3]:12s} stretch {r[4]:+.4f} mm")
