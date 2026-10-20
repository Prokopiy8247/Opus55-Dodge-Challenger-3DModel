"""P3b: displacement of the front-right suspension hard points under the elastokinematics load cases (1 kN), to see the
compliance-steer mechanism. Usage: compliance_field.py [case ...]"""
import sys
import numpy as np

sys.path.insert(0, "tools/skeleton")
from stability import load  # noqa: E402
import elastokinematics as ek  # noqa: E402
from scipy.sparse.linalg import splu  # noqa: E402
import scipy.sparse as sp  # noqa: E402
import re  # noqa: E402

g, p = load("hellcat")
P = np.array([n["p"] for n in g["nodes"]], float)
N = len(P)
names = [n["name"] for n in g["nodes"]]
I = {n: i for i, n in enumerate(names)}
K, out = ek.assemble(g, p, P)
fixed = set()
for i, nd in enumerate(g["nodes"]):
    if out[i] or (nd["part"] == "body" and re.match(r"^(sill|floor|tunnel)", nd["name"])):
        fixed.update((3 * i, 3 * i + 1, 3 * i + 2))
free = np.array(sorted(set(range(3 * N)) - fixed))
Kf = K[free][:, free].tocsc()
Kf = Kf + 1e-7 * Kf.diagonal().mean() * sp.identity(len(free), format="csc")
lu = splu(Kf)
w = next(w for w in g["wheels"] if w["name"] == "FR")
ai, ao = w["axleInner"], w["axleOuter"]
d = P[ao] - P[ai]
R = 0.352
show = ["FR_lbj", "FR_ubj", "FR_tre", "FR_axle_in", "FR_axle_out", "rack_R", "FR_lca_f", "FR_lca_r", "FR_uca_f", "FR_uca_r"]


def load_case(F, M):
    f = np.zeros((N, 3))
    f[ai] += 0.5 * F
    f[ao] += 0.5 * F
    axis = d / np.linalg.norm(d)
    Mp = M - np.dot(M, axis) * axis
    fc = np.cross(Mp, d) / np.dot(d, d)
    f[ao] += fc
    f[ai] -= fc
    Ma = np.dot(M, axis) * axis
    if np.linalg.norm(Ma) > 0:
        kn = ek.knuckle_nodes(g, w)
        cc = P[kn].mean(axis=0)
        rr = [(P[i] - cc) - np.dot(P[i] - cc, axis) * axis for i in kn]
        S = sum(np.dot(r, r) for r in rr)
        for i, r in zip(kn, rr):
            f[i] += np.cross(Ma, r) / S
    return f


fwd = np.array([0, 0, 1.0])
ground = np.array([0, -R, 0])
cases = {"brake": load_case(-1000 * fwd, np.cross(ground, -1000 * fwd)),
         "lateral": load_case(np.array([-1000.0, 0, 0]), np.cross(ground, np.array([-1000.0, 0, 0]))),
         "drive": load_case(1000 * fwd, np.zeros(3))}
for c in (sys.argv[1:] or cases):
    u = np.zeros(3 * N)
    u[free] = lu.solve(cases[c].ravel()[free])
    U = u.reshape(-1, 3) * 1000
    print("==", c, "(mm per kN)")
    for n in show:
        print(f"   {n:12s} {U[I[n]][0]:+7.3f} {U[I[n]][1]:+7.3f} {U[I[n]][2]:+7.3f}")
