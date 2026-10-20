"""Modes of the skeleton with the wheel parts held (body on its suspension). Usage: modes_on_wheels.py [k]"""
import sys, re
from collections import defaultdict
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load
from mechanisms import assemble, family
k = int(sys.argv[1]) if len(sys.argv) > 1 else 40
g, p = load("hellcat")
K = assemble(g, p).tocsr()
N = len(g["nodes"])
m = np.array([n["m"] for n in g["nodes"]], float)
held = np.array([n["part"].startswith("wheel_") for n in g["nodes"]])
free_nodes = np.where(~held)[0]
dof = np.repeat(free_nodes * 3, 3) + np.tile([0, 1, 2], len(free_nodes))
Kf = K[dof][:, dof]
Mi = sp.diags(np.repeat(1 / np.sqrt(m[free_nodes]), 3))
w, v = eigsh((Mi @ Kf @ Mi).tocsc(), k=k, sigma=-1.0, which="LM")
o = np.argsort(w); w, v = w[o], v[:, o]
names = [g["nodes"][i]["name"] for i in free_nodes]
P = np.array([g["nodes"][i]["p"] for i in free_nodes])
body = np.array([g["nodes"][i]["part"] == "body" for i in free_nodes])
for i in range(len(w)):
    x = (Mi @ v[:, i]).reshape(-1, 3)
    amp = np.linalg.norm(x, axis=1); amp /= amp.max()
    mov = amp > 0.2
    f = np.sqrt(max(w[i], 0)) / 2 / np.pi
    fams = defaultdict(float)
    for j in np.where(mov)[0]:
        fams[family(names[j])] += amp[j]
    fl = sorted(fams.items(), key=lambda kv: -kv[1])[:4]
    tag = ""
    if mov.sum() > 300:
        dy = x[body, 1]; A = np.c_[np.ones(body.sum()), P[body, 0], P[body, 2]]
        c, *_ = np.linalg.lstsq(A, dy, rcond=None)
        tag = f" GLOBAL: heave {c[0]:+.3f} roll {c[1]:+.3f} pitch {c[2]:+.3f} lat {np.sqrt((x[body,0]**2).mean()):.3f} long {np.sqrt((x[body,2]**2).mean()):.3f}"
    print(f"{i:2d} {f:8.3f} Hz {mov.sum():5d} nodes | {', '.join(f'{a}:{b:.1f}' for a, b in fl)}{tag}")
