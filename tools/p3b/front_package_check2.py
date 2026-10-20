"""P3b: front package (front_package_check.package) with the lower ball joint heavier inside its knuckle group (sum kept):
exact S, anti-roll-bar effectiveness and front compliance per kN with the kingpin camber element."""
import copy
import sys
import numpy as np

sys.path.insert(0, "tools/skeleton")
sys.path.insert(0, "tools/p3b")
from stability import load, analyse  # noqa: E402
from front_package_check import package  # noqa: E402

g0, p0 = load("hellcat")


def weight_lbj(g, w_lbj):
    I = {n["name"]: i for i, n in enumerate(g["nodes"])}
    for s in ("R", "L"):
        ids = [I[f"F{s}_{k}"] for k in ("lbj", "ubj", "tre", "axle_in", "axle_out")]
        tot = sum(g["nodes"][i]["m"] for i in ids)
        ws = [w_lbj, 1, 1, 1, 1]
        for i, wv in zip(ids, ws):
            g["nodes"][i]["m"] = tot * wv / sum(ws)


if __name__ == "__main__":
    for wl in (1.0, 1.25, 1.5):
        g, p = package(g0, p0, link=2.5e6, lever=2.5e6, arb_f=1960 * 0.9, arb_r=550 * 3)
        weight_lbj(g, wl)
        out = analyse(g, p, modes=4)
        print(f"lbj weight {wl}: lbj {g['nodes'][[n['name'] for n in g['nodes']].index('FR_lbj')]['m']:.2f} kg, S {out['S_exact_max']:.4f}, "
              f"top {out['top_modes'][0]['nodes'][:3]}")
    # bar effectiveness with this package (arb_study machinery)
    src = open("tools/p3b/arb_study2.py", encoding="utf-8").read().split('evaluate("as is"')[0]
    ns = {"__name__": "x"}
    exec(compile(src, "arb_study2", "exec"), ns)
    for af, ar in ((1.0, 3.0), (0.9, 3.0), (0.9, 2.5)):
        g, p = package(g0, p0, link=2.5e6, lever=2.5e6, arb_f=1960 * af, arb_r=550 * ar)
        ns["evaluate"](f"package, bars F x{af} R x{ar}", g, p)
