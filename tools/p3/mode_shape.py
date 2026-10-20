"""Shape of the lowest global modes of the skeleton (P3 diagnosis). Usage: mode_shape.py [mode indices]"""
import sys
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load
from mechanisms import assemble
g, p = load("hellcat")
K = assemble(g, p)
m = np.array([n["m"] for n in g["nodes"]], float)
Mi = sp.diags(np.repeat(1.0 / np.sqrt(m), 3))
w, v = eigsh((Mi @ K @ Mi).tocsc(), k=60, sigma=-1.0, which="LM")
o = np.argsort(w); w, v = w[o], v[:, o]
P = np.array([n["p"] for n in g["nodes"]])
names = [n["name"] for n in g["nodes"]]
body = np.array([n["part"] == "body" for n in g["nodes"]])
for i in range(len(w)):
    x = (Mi @ v[:, i]).reshape(-1, 3)
    amp = np.linalg.norm(x, axis=1)
    if (amp > 0.2 * amp.max()).sum() < 200:
        continue
    f = np.sqrt(max(w[i], 0)) / 2 / np.pi
    # project body-node motion on rigid modes + bending/torsion patterns (x right, y up, z forward)
    B = body
    dy = x[B, 1]; px = P[B, 0]; pz = P[B, 2]
    A = np.c_[np.ones(B.sum()), px, pz, pz ** 2, px * pz]
    c, *_ = np.linalg.lstsq(A, dy, rcond=None)
    fit = A @ c
    r2 = 1 - ((dy - fit) ** 2).sum() / max(((dy - dy.mean()) ** 2).sum(), 1e-30)
    lat = x[B, 0]; lon = x[B, 2]
    print(f"mode {i} {f:.3f} Hz, moving nodes {(amp > 0.2 * amp.max()).sum()}: dy fit 1 {c[0]:+.3f} x {c[1]:+.3f} z {c[2]:+.3f} "
          f"z^2 {c[3]:+.3f} xz(torsion) {c[4]:+.3f} (R2 {r2:.2f}); rms lateral {np.sqrt((lat**2).mean()):.3f} long {np.sqrt((lon**2).mean()):.3f} vert {np.sqrt((dy**2).mean()):.3f}")
    top = np.argsort(-amp)[:6]
    print("   top:", ", ".join(f"{names[j]} {x[j].round(2)}" for j in top))
