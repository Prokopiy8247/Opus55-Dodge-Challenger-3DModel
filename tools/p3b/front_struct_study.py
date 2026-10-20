"""P3b: linear estimate of front-structure additions (K-member ties, rack ties, tower links) on the front compliance
steer / camber (per kN), with and without a kingpin-referenced camber element."""
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

SETS = {
    "kmember": [("FR_lca_f", "FL_lca_f"), ("FR_lca_r", "FL_lca_r"), ("FR_lca_f", "FL_lca_r"), ("FR_lca_r", "FL_lca_f")],
    "racktie": [("rack_R", "FR_lca_f"), ("rack_R", "FR_lca_r"), ("rack_L", "FL_lca_f"), ("rack_L", "FL_lca_r"),
                ("rack_C", "FR_lca_r"), ("rack_C", "FL_lca_r")],
    "tower": [("FR_uca_f", "FR_lca_f"), ("FR_uca_r", "FR_lca_r"), ("FR_uca_f", "FR_lca_r"), ("FR_uca_r", "FR_lca_f"),
              ("FL_uca_f", "FL_lca_f"), ("FL_uca_r", "FL_lca_r"), ("FL_uca_f", "FL_lca_r"), ("FL_uca_r", "FL_lca_f")],
    "ucatie": [("FR_uca_f", "FL_uca_f"), ("FR_uca_r", "FL_uca_r")],
}


def make(extra, k_extra, kc_front):
    def assemble(g_, p_, P_):
        K, out = orig(g_, p_, P_)
        rows, cols, vals = [], [], []

        def add(i, j, k):
            d = P_[j] - P_[i]
            e = d / np.linalg.norm(d)
            blk = k * np.outer(e, e)
            for (a, b, s) in ((i, i, 1), (j, j, 1), (i, j, -1), (j, i, -1)):
                for r in range(3):
                    for q in range(3):
                        rows.append(3 * a + r)
                        cols.append(3 * b + q)
                        vals.append(s * blk[r, q])
        for (a, b) in extra:
            add(I[a], I[b], k_extra)
        for w in g_["wheels"]:
            ai, ao = w["axleInner"], w["axleOuter"]
            d = P_[ao] - P_[ai]
            L = np.linalg.norm(d)
            a = d / L
            front = w["steered"] != 0
            if front:
                s = w["name"][1]
                kk = P_[I[f"F{s}_ubj"]] - P_[I[f"F{s}_lbj"]]
                kk /= np.linalg.norm(kk)
                terms = [(kc_front, kk)]
            else:
                terms = [(80000.0, np.array([0, 1.0, 0])), (80000.0, np.array([0, 0, 1.0]))]
            for kv, axis in terms:
                if kv <= 0:
                    continue
                gvec = (axis - np.dot(a, axis) * a) / L
                idx = list(range(3 * ao, 3 * ao + 3)) + list(range(3 * ai, 3 * ai + 3))
                gv = np.concatenate([gvec, -gvec])
                for x, gi in zip(idx, gv):
                    for y, gj in zip(idx, gv):
                        rows.append(x)
                        cols.append(y)
                        vals.append(kv * gi * gj)
        return K + sp.csr_matrix((vals, (rows, cols)), shape=K.shape), out
    return assemble


def run(label, sets, kc=0.0, k_extra=1.5e6, energy=False):
    extra = [b for s in sets for b in SETS[s]]
    ek.assemble = make(extra, k_extra, kc)
    res = ek.solve(g, p, energy=energy)
    v = res["FR"]
    print(f"{label:44s} lat toe {v['lateral']['toe_in_deg']:+.3f} cam {v['lateral']['camber_deg']:+.3f} | brake toe "
          f"{v['brake']['toe_in_deg']:+.3f} | drive toe {v['drive']['toe_in_deg']:+.3f} | hub lat {v['lateral']['hub_mm'][0]:+.2f} "
          f"brake {v['brake']['hub_mm'][2]:+.2f} mm")
    if energy:
        for c in ("lateral", "brake"):
            print("      energy", c, {k: float(x) for k, x in v[c]["energy"].items()})
    ek.assemble = orig


run("base (rear element only)", [])
run("kmember", ["kmember"])
run("racktie", ["racktie"])
run("kmember + racktie", ["kmember", "racktie"])
run("kmember + racktie + tower", ["kmember", "racktie", "tower"])
run("all + ucatie", ["kmember", "racktie", "tower", "ucatie"])
run("all + ucatie + camber 80k", ["kmember", "racktie", "tower", "ucatie"], kc=80000.0, energy=True)
run("kmember + racktie + camber 80k", ["kmember", "racktie"], kc=80000.0)
