"""P3b: linear estimate of a front camber element measured against the kingpin axis (steer-invariant, D-051 draft):
compliance toe / camber per kN with the element's stiffness, and where the remaining toe compliance sits."""
import sys
import numpy as np
import scipy.sparse as sp

sys.path.insert(0, "tools/skeleton")
from stability import load  # noqa: E402
import elastokinematics as ek  # noqa: E402

g, p = load("hellcat")
P = np.array([n["p"] for n in g["nodes"]], float)
N = len(P)
I = {n["name"]: i for i, n in enumerate(g["nodes"])}
orig = ek.assemble


def make(kc_front, kc_rear, kt_rear):
    def assemble(g_, p_, P_):
        K, out = orig(g_, p_, P_)
        rows, cols, vals = [], [], []
        for w in g_["wheels"]:
            ai, ao = w["axleInner"], w["axleOuter"]
            d = P_[ao] - P_[ai]
            L = np.linalg.norm(d)
            a = d / L
            front = w["steered"] != 0
            if front:
                s = w["name"][1]
                k = P_[I[f"F{s}_ubj"]] - P_[I[f"F{s}_lbj"]]
                k /= np.linalg.norm(k)
            else:
                k = np.array([0, 1.0, 0])
            terms = [(kc_front if front else kc_rear, k)]
            if not front:
                terms.append((kt_rear, np.array([0, 0, 1.0])))
            for kk, axis in terms:
                if kk <= 0:
                    continue
                gvec = (axis - np.dot(a, axis) * a) / L          # d(a . axis) / d(x_out); minus on x_in
                gv = np.zeros(3 * N)
                gv[3 * ao:3 * ao + 3] = gvec
                gv[3 * ai:3 * ai + 3] = -gvec
                # angle ~ a . axis / sin(phi): sin ~ 1
                nz = np.nonzero(gv)[0]
                for i in nz:
                    for j in nz:
                        rows.append(i)
                        cols.append(j)
                        vals.append(kk * gv[i] * gv[j])
        return K + sp.csr_matrix((vals, (rows, cols)), shape=K.shape), out
    return assemble


for label, (kf, kr, kt) in {"rear element (80k), front none": (0, 80000, 80000),
                            "+ front kingpin camber 40k": (40000, 80000, 80000),
                            "+ front kingpin camber 80k": (80000, 80000, 80000),
                            "+ front kingpin camber 160k": (160000, 80000, 80000)}.items():
    ek.assemble = make(kf, kr, kt)
    res = ek.solve(g, p, energy=(kf == 80000))
    v = res["FR"]
    print(f"{label:32s} FR lateral toe {v['lateral']['toe_in_deg']:+.3f} cam {v['lateral']['camber_deg']:+.3f} | "
          f"brake toe {v['brake']['toe_in_deg']:+.3f} cam {v['brake']['camber_deg']:+.3f} | drive toe {v['drive']['toe_in_deg']:+.3f} | "
          f"vertical toe {v['vertical']['toe_in_deg']:+.3f} cam {v['vertical']['camber_deg']:+.3f}")
    if kf == 80000:
        for c in ("lateral", "brake"):
            print("    energy", c, v[c]["energy"], "hub mm", [round(x, 2) for x in v[c]["hub_mm"]])
ek.assemble = orig
