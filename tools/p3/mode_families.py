"""Shape of the low modes (wheel parts held): per family the mean displacement direction and size, to tell vertical bending,
lateral sway and torsion apart. Usage: mode_families.py [fmax] [count]"""
import re, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load
from mechanisms import assemble
from modal_damping import assemble_c
fmax = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
g, p = load("hellcat")
K = assemble(g, p).tocsr(); C = assemble_c(g, p).tocsr()
m = np.array([n["m"] for n in g["nodes"]], float)
held = np.array([n["part"].startswith("wheel_") for n in g["nodes"]])
free = np.where(~held)[0]
dof = np.repeat(free * 3, 3) + np.tile([0, 1, 2], len(free))
mi = np.repeat(1 / np.sqrt(m[free]), 3)
A = K[dof][:, dof].toarray() * mi[:, None] * mi[None, :]
Bc = C[dof][:, dof].toarray() * mi[:, None] * mi[None, :]
w2, V = np.linalg.eigh(A)
names = [g["nodes"][i]["name"] for i in free]
P = np.array([g["nodes"][i]["p"] for i in free])
fam = lambda n: re.split(r"\d", n, 1)[0].rstrip("_")
for k in range(len(w2)):
    f = np.sqrt(max(w2[k], 0)) / 2 / np.pi
    if f > fmax:
        break
    if f < 0.5:
        continue
    zeta = V[:, k] @ Bc @ V[:, k] / (2 * np.sqrt(w2[k]))
    x = (V[:, k] * mi).reshape(-1, 3)
    x /= np.abs(x).max()
    agg = defaultdict(lambda: np.zeros(3)); amp = defaultdict(float); cnt = defaultdict(int)
    for j, n in enumerate(names):
        agg[fam(n)] += x[j]; amp[fam(n)] += np.linalg.norm(x[j]); cnt[fam(n)] += 1
    top = sorted(amp, key=lambda q: -amp[q] / cnt[q])[:6]
    # unity frame: x right, y up, z forward
    desc = ", ".join(f"{q}:{amp[q]/cnt[q]:.2f}{np.round(agg[q]/cnt[q], 2).tolist()}" for q in top)
    print(f"{f:6.2f} Hz z {zeta:.3f}: {desc}")
