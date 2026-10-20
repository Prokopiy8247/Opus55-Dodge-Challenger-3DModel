"""P3b: exact stability S (D-024) of front-structure variants (K-member, rack ties, stiffer knuckle / arm / tie rod /
subframe) evaluated on the skeleton in memory."""
import copy
import sys

sys.path.insert(0, "tools/skeleton")
from stability import load, analyse  # noqa: E402

KM = [("FR_lca_f", "FL_lca_f"), ("FR_lca_r", "FL_lca_r"), ("FR_lca_f", "FL_lca_r"), ("FR_lca_r", "FL_lca_f")]
RT = [("rack_R", "FR_lca_f"), ("rack_R", "FR_lca_r"), ("rack_L", "FL_lca_f"), ("rack_L", "FL_lca_r"),
      ("rack_C", "FR_lca_r"), ("rack_C", "FL_lca_r")]
g0, p0 = load("hellcat")


def variant(label, beams=(), mats=None):
    g = copy.deepcopy(g0)
    p = copy.deepcopy(p0)
    I = {n["name"]: i for i, n in enumerate(g["nodes"])}
    for a, b in beams:
        g["beams"].append({"a": I[a], "b": I[b], "type": "NORMAL", "mat": "subframe", "bg": "", "bgt": 0, "pre": 0.0})
    for m in p["materials"]:
        if mats and m["name"] in mats:
            m["spring"] = mats[m["name"]]
    out = analyse(g, p, modes=4)
    fam = out["family_S"]
    keys = [k for k in fam if k.startswith("wheel_") and not any(k.startswith("wheel_" + r) for r in ("tr", "rim"))]
    keys += [k for k in ("rack_C", "rack_R", "rack_L", "frail", "xm") if k in fam]
    print(f"{label:40s} S {out['S_exact_max']:.4f}  " + "  ".join(f"{k[6:] if k.startswith('wheel_') else k} {fam[k]:.2f}" for k in keys))
    print("      top mode", out["top_modes"][0]["nodes"][:3])


if len(sys.argv) == 1:
    variant("as is")
    variant("K-member + rack ties", KM + RT)
    variant("+ knuckle 10M", KM + RT, {"knuckle": 10e6})
    variant("+ knuckle 10M arm 5M tierod 8M", KM + RT, {"knuckle": 10e6, "arm": 5e6, "tierod": 8e6})
    variant("+ knuckle 10M arm 5M tierod 8M subframe 3M", KM + RT, {"knuckle": 10e6, "arm": 5e6, "tierod": 8e6, "subframe": 3e6})


def front_only(label, k_kn, k_arm, k_tr, beams=KM + RT):
    """Front knuckle / arm beams on their own materials (knuckle_f, arm_f)."""
    g = copy.deepcopy(g0)
    p = copy.deepcopy(p0)
    I = {n["name"]: i for i, n in enumerate(g["nodes"])}
    names = [n["name"] for n in g["nodes"]]
    for a, b in beams:
        g["beams"].append({"a": I[a], "b": I[b], "type": "NORMAL", "mat": "subframe", "bg": "", "bgt": 0, "pre": 0.0})
    for bm in g["beams"]:
        na, nb = names[bm["a"]], names[bm["b"]]
        front = na.startswith(("FR_", "FL_")) or nb.startswith(("FR_", "FL_"))
        if front and bm["mat"] == "knuckle":
            bm["mat"] = "knuckle_f"
        if front and bm["mat"] == "arm":
            bm["mat"] = "arm_f"
    mats = {m["name"]: m for m in p["materials"]}
    p["materials"].append(dict(mats["knuckle"], name="knuckle_f", spring=k_kn))
    p["materials"].append(dict(mats["arm"], name="arm_f", spring=k_arm))
    for m in p["materials"]:
        if m["name"] == "tierod":
            m["spring"] = k_tr
    out = analyse(g, p, modes=4)
    fam = out["family_S"]
    keys = [k for k in ("wheel_lbj", "wheel_ubj", "wheel_tre", "wheel_axle_in", "wheel_axle_out", "wheel_lca_f", "wheel_lca_r",
                        "wheel_uca_f", "wheel_uca_r", "wheel_lca_sh", "rack_C", "rack_R") if k in fam]
    print(f"{label:40s} S {out['S_exact_max']:.4f}  " + "  ".join(f"{k.replace('wheel_', '')} {fam[k]:.2f}" for k in keys))
    print("      top mode", out["top_modes"][0]["nodes"][:3])
    return g, p


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "front":
    for kn, ka, kt in ((8e6, 5e6, 8e6), (10e6, 5e6, 8e6), (12e6, 5e6, 8e6)):
        front_only(f"front knuckle {kn / 1e6:.0f}M arm {ka / 1e6:.0f}M tierod {kt / 1e6:.0f}M", kn, ka, kt)


def reweight(g, weights):
    """Redistribute the mass within each front corner's knuckle and arm groups by name suffix weights (group sum kept)."""
    I = {n["name"]: i for i, n in enumerate(g["nodes"])}
    for s in ("R", "L"):
        for grp in (("lbj", "ubj", "tre", "axle_in", "axle_out"), ("lca_f", "lca_r", "lca_sh", "uca_f", "uca_r")):
            ids = [I[f"F{s}_{k}"] for k in grp]
            tot = sum(g["nodes"][i]["m"] for i in ids)
            ws = [weights.get(k, 1.0) for k in grp]
            for i, wv in zip(ids, ws):
                g["nodes"][i]["m"] = tot * wv / sum(ws)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "weights":
    W = {"lbj": 1.35, "ubj": 1.0, "tre": 0.85, "axle_in": 0.9, "axle_out": 0.9,
         "lca_f": 1.6, "lca_r": 1.6, "lca_sh": 0.6, "uca_f": 0.6, "uca_r": 0.6}
    for kn, ka, kt in ((8e6, 4e6, 6e6), (8e6, 5e6, 8e6), (10e6, 5e6, 8e6)):
        g, p = front_only(f"knuckle {kn / 1e6:.0f}M arm {ka / 1e6:.0f}M tierod {kt / 1e6:.0f}M (unweighted)", kn, ka, kt)
        reweight(g, W)
        out = analyse(g, p, modes=4)
        fam = out["family_S"]
        keys = [k for k in ("wheel_lbj", "wheel_ubj", "wheel_tre", "wheel_axle_in", "wheel_axle_out", "wheel_lca_f", "wheel_lca_r",
                            "wheel_uca_f", "wheel_uca_r", "wheel_lca_sh", "rack_C", "rack_R") if k in fam]
        print(f"{'   reweighted':40s} S {out['S_exact_max']:.4f}  " + "  ".join(f"{k.replace('wheel_', '')} {fam[k]:.2f}" for k in keys))
        print("      top mode", out["top_modes"][0]["nodes"][:3])


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "knuckle":
    for kn in (6e6, 8e6, 10e6):
        front_only(f"front knuckle {kn / 1e6:.0f}M, arms / tie rod as is", kn, 2.5e6, 2.5e6)
