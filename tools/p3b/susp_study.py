"""P3b study: suspension elastokinematics vs solver stability for material / mass variants (D-049).

Usage: tools/.venv/Scripts/python.exe tools/p3b/susp_study.py
"""
import copy
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load, analyse  # noqa: E402
import elastokinematics as ek  # noqa: E402

SUSP = re.compile(r"link|_kl|_kup|lbj|ubj|tre|lca|uca|axle|rack|tierod|steer|rsub|fsub")


PIVOT = re.compile(r"^(F[RL]_(lca_f|lca_r|lca_sh|uca_f|uca_r)|R[RL]_link\d)$")


def split_pins(g, p, k_pin, rear_only=False):
    """The suspension pivots' pins (subframe material) as their own material link_pin."""
    names = [n["name"] for n in g["nodes"]]
    pat = re.compile(r"^R[RL]_link\d$") if rear_only else PIVOT
    for b in g["beams"]:
        if b["mat"] == "subframe" and (pat.match(names[b["a"]]) or pat.match(names[b["b"]])):
            b["mat"] = "link_pin"
    p["materials"].append({"name": "link_pin", "spring": k_pin, "damp": 50})


def variant(g, p, scales=None, masses=None, pin=None, moves=None):
    g2, p2 = copy.deepcopy(g), copy.deepcopy(p)
    split_pins(g2, p2, pin if pin else 1500000.0, rear_only=True)
    if moves:
        idx = {n["name"]: i for i, n in enumerate(g2["nodes"])}
        for nm, dz in moves.items():
            g2["nodes"][idx[nm]]["p"][2] += dz
    for m in p2["materials"]:
        if scales and m["name"] in scales:
            m["spring"] = m.get("spring", 0.0) * scales[m["name"]]
    if masses:
        for n in g2["nodes"]:
            for pat, mass in masses.items():
                if re.match(pat, n["name"]):
                    n["m"] = mass
    return g2, p2


def report(name, g, p, full_s=True):
    res = ek.solve(g, p)
    print(f"== {name}")
    for wn in ("FR", "RR"):
        cs = res[wn]
        print("  " + wn + "  " + "  ".join(f"{cn} toe {v['toe_in_deg']:+.3f} cam {v['camber_deg']:+.3f} dz {v['hub_mm'][2]:+.2f}"
                                          for cn, v in cs.items()))
    if full_s:
        st = analyse(g, p, modes=3)
        fam = {k: v for k, v in st["family_S"].items() if SUSP.search(k)}
        top = sorted(fam.items(), key=lambda kv: -kv[1])[:8]
        print(f"  S exact max {st['S_exact_max']}  (top modes {[m['nodes'][0][0] for m in st['top_modes']]})")
        print("  suspension families S: " + ", ".join(f"{k} {v}" for k, v in top))


def main():
    g, p = load("hellcat")
    piv = {r"^R[RL]_link\d$": 3.5}
    report("R1: link, rail_r_brace x2", *variant(g, p, {"link": 2.0, "rail_r_brace": 2.0}))
    report("R2: R1 + rear pivots 3.5 kg", *variant(g, p, {"link": 2.0, "rail_r_brace": 2.0}, piv))
    report("R3: R2 + rear pins 3 MN/m", *variant(g, p, {"link": 2.0, "rail_r_brace": 2.0}, piv, 3.0e6))


if __name__ == "__main__":
    main()
