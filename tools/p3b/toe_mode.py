"""P3b: linear modes of the parked car (contact-patch tread nodes held) that move the front wheels in toe: frequency and
modal damping ratio (beam dampers only), for two skeleton / params versions. Usage: toe_mode.py geomA paramsA geomB paramsB"""
import json
import sys
import numpy as np
import scipy.linalg as sl

sys.path.insert(0, "tools/skeleton")
from stability import strip_comments, beam_kc  # noqa: E402


def load(gp, pp):
    g = json.load(open(gp, encoding="utf-8"))
    p = json.loads(strip_comments(open(pp, encoding="utf-8").read()))
    return g, p


def modes(g, p, label):
    N = len(g["nodes"])
    P = np.array([n["p"] for n in g["nodes"]], float)
    m = np.array([n["m"] for n in g["nodes"]], float)
    names = [n["name"] for n in g["nodes"]]
    mats = {x["name"]: x for x in p["materials"]}
    K = np.zeros((3 * N, 3 * N))
    C = np.zeros((3 * N, 3 * N))
    for b in g["beams"]:
        mat = mats[b["mat"]]
        if b["type"] in ("BOUNDED",):
            k, c = (mat.get("spring", 0) or 0), (mat.get("damp", 0) or 0)
        else:
            k, c = beam_kc(mat, b["type"])
            if b["type"] == "SUPPORT":
                k, c = 0.0, 0.0
        a, bb = b["a"], b["b"]
        d = P[bb] - P[a]
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        e = d / L
        blk = np.outer(e, e)
        for (i, j, s) in ((a, a, 1), (bb, bb, 1), (a, bb, -1), (bb, a, -1)):
            K[3 * i:3 * i + 3, 3 * j:3 * j + 3] += s * k * blk
            C[3 * i:3 * i + 3, 3 * j:3 * j + 3] += s * c * blk
    # contact patch: tread nodes within 2 cm of the ground held
    held = [i for i, nm in enumerate(names) if P[i, 1] < 0.02 and "_tr" in nm]
    keep = np.ones(3 * N, bool)
    for i in held:
        keep[3 * i:3 * i + 3] = False
    Kf, Cf = K[keep][:, keep], C[keep][:, keep]
    Mf = np.repeat(m, 3)[keep]
    Ms = 1 / np.sqrt(Mf)
    A = Ms[:, None] * Kf * Ms[None, :]
    w2, V = sl.eigh(A, subset_by_value=(( 2 * np.pi * 5) ** 2, (2 * np.pi * 400) ** 2))
    Phi = Ms[:, None] * V              # mass-normalized mode shapes
    full = np.zeros((3 * N, Phi.shape[1]))
    full[keep] = Phi
    # toe of the front wheels: rotation of the axle line about the vertical
    out = []
    for k in range(Phi.shape[1]):
        u = full[:, k].reshape(N, 3)
        toe = 0.0
        for s in ("R", "L"):
            ai, ao = names.index(f"F{s}_axle_in"), names.index(f"F{s}_axle_out")
            d0 = P[ao] - P[ai]
            du = u[ao] - u[ai]
            toe += abs((du[2] * d0[0] - du[0] * d0[2]) / np.dot(d0, d0))
        zeta = Phi[:, k] @ Cf @ Phi[:, k] / (2 * np.sqrt(w2[k]))
        out.append((toe, np.sqrt(w2[k]) / 2 / np.pi, zeta))
    out.sort(key=lambda x: -x[0])
    print(label)
    for toe, f, z in out[:6]:
        print(f"   toe participation {toe:.4f}  f {f:6.1f} Hz  zeta {z:.4f}")


if __name__ == "__main__":
    a = load(sys.argv[1], sys.argv[2])
    b = load(sys.argv[3], sys.argv[4])
    modes(*a, "A: " + sys.argv[1])
    modes(*b, "B: " + sys.argv[3])
