"""P3b (D-051 draft): the whole front package in memory - tie-rod ends 40 mm outboard (hydro factor 0.20), K-member and
rack ties ("kmember" material = subframe), front knuckle beams on "knuckle_f", the front anti-roll-bar links on the
lower ball joints, link / lever stiffness - exact stability S and the anti-roll-bar effectiveness."""
import copy
import sys
import numpy as np

sys.path.insert(0, "tools/skeleton")
from stability import load, analyse  # noqa: E402

KM = [("FR_lca_f", "FL_lca_f"), ("FR_lca_r", "FL_lca_r"), ("FR_lca_f", "FL_lca_r"), ("FR_lca_r", "FL_lca_f")]
RT = [("rack_R", "FR_lca_f"), ("rack_R", "FR_lca_r"), ("rack_L", "FL_lca_f"), ("rack_L", "FL_lca_r"),
      ("rack_C", "FR_lca_r"), ("rack_C", "FL_lca_r")]


def package(g0, p0, knuckle_f=6e6, link=2.5e6, lever=2.5e6, arb_f=None, arb_r=None, tre_dx=0.04, relink=True):
    g = copy.deepcopy(g0)
    p = copy.deepcopy(p0)
    I = {n["name"]: i for i, n in enumerate(g["nodes"])}
    names = [n["name"] for n in g["nodes"]]
    for s, sx in (("R", 1), ("L", -1)):
        g["nodes"][I[f"F{s}_tre"]]["p"][0] += sx * tre_dx
    for a, b in KM + RT:
        g["beams"].append({"a": I[a], "b": I[b], "type": "NORMAL", "mat": "kmember", "bg": "", "bgt": 0, "pre": 0.0})
    for bm in g["beams"]:
        na, nb = names[bm["a"]], names[bm["b"]]
        if bm["mat"] == "knuckle" and (na.startswith(("FR_", "FL_")) or nb.startswith(("FR_", "FL_"))):
            bm["mat"] = "knuckle_f"
        if bm["mat"] == "tierod":
            bm["hf"] = 0.20 if bm["hf"] > 0 else -0.20
        if relink and bm["mat"] == "arb_link":
            for s in ("R", "L"):
                sh, lbj = I[f"F{s}_lca_sh"], I[f"F{s}_lbj"]
                if bm["a"] == sh:
                    bm["a"] = lbj
                elif bm["b"] == sh:
                    bm["b"] = lbj
    mats = {m["name"]: m for m in p["materials"]}
    p["materials"].append(dict(mats["knuckle"], name="knuckle_f", spring=knuckle_f))
    p["materials"].append(dict(mats["subframe"], name="kmember"))
    for m in p["materials"]:
        if m["name"] == "arb_link":
            m["spring"] = link
        if m["name"] == "arb_lever":
            m["spring"] = lever
        if m["name"] == "arb_front" and arb_f:
            m["spring"] = arb_f
        if m["name"] == "arb_rear" and arb_r:
            m["spring"] = arb_r
    return g, p


if __name__ == "__main__":
    g0, p0 = load("hellcat")
    for link, lever in ((2.5e6, 2.5e6), (4e6, 2.5e6), (4e6, 4e6)):
        g, p = package(g0, p0, link=link, lever=lever)
        out = analyse(g, p, modes=4)
        fam = out["family_S"]
        keys = ("arbF_tip_R", "arbR_tip_R", "arbF_axis_R", "arbR_axis_R", "wheel_lbj", "wheel_klr", "wheel_lca_f", "rack_C")
        print(f"link {link / 1e6:.1f}M lever {lever / 1e6:.1f}M: S {out['S_exact_max']:.4f} | " +
              " ".join(f"{k} {fam.get(k, float('nan')):.2f}" for k in keys))
        print("     top", out["top_modes"][0]["nodes"][:3])
