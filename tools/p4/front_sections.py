"""P4 crash diagnosis: axial crush resistance of the Hellcat's front structure by cross-section.

For planes z = const from the bumper back to the cabin, sums over the intact beams that cross the plane the axial
component (|dz| / L) of their yield force (first yield, the yield cap reached by hardening) and of their break strength,
by material. A node-beam structure can only crush through a section by yielding (or breaking) the beams that cross it, or
by a mechanism (beams rotating about their nodes), so the yield sum is an upper bound of the section's initial crush
force. Writes docs/p4/front_sections.csv and prints a table.

Usage: python -I tools/p4/front_sections.py [--z0 2.6] [--z1 0.6] [--step 0.05]
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VEH = ROOT / "sim" / "vehicle" / "hellcat"


def load_jsonc(path):
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    return json.loads(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--z0", type=float, default=2.6)
    ap.add_argument("--z1", type=float, default=0.4)
    ap.add_argument("--step", type=float, default=0.05)
    ap.add_argument("--ymax", type=float, default=1.3, help="ignore beams entirely above this height (roof, glass)")
    ap.add_argument("--detail", type=float, nargs="*", default=[], help="z planes to list beam by beam")
    a = ap.parse_args()
    geo = json.loads((VEH / "geometry.json").read_text(encoding="utf-8"))
    prm = load_jsonc(VEH / "params.json")
    mats = {m["name"]: m for m in prm["materials"]}
    nodes = geo["nodes"]
    P = [n["p"] for n in nodes]
    front = max(p[2] for p in P)
    print(f"front-most node z = {front:.3f} m; nodes {len(nodes)}, beams {len(geo['beams'])}")
    inf = float("inf")

    def mval(m, key):
        v = m.get(key, -1)
        return inf if v is None or v < 0 else v

    rows = []
    z = a.z0
    while z >= a.z1 - 1e-9:
        by = defaultdict(lambda: [0, 0.0, 0.0, 0.0])   # count, yield, cap, strength (axial)
        rigid = []
        detail = []
        for bi, b in enumerate(geo["beams"]):
            pa, pb = P[b["a"]], P[b["b"]]
            if (pa[2] - z) * (pb[2] - z) >= 0:
                continue
            if min(pa[1], pb[1]) > a.ymax:
                continue
            m = mats.get(b["mat"])
            if m is None:
                continue
            L = sum((pb[k] - pa[k]) ** 2 for k in range(3)) ** 0.5
            c = abs(pb[2] - pa[2]) / L
            y = mval(m, "deform")
            cap = mval(m, "deformCap") if y < inf else inf
            if y < inf and cap == inf:
                cap = y if m.get("hardening", 0) <= 0 else inf
            st = mval(m, "strength")
            if m.get("spring", 0) <= 0:
                continue
            e = by[b["mat"]]
            e[0] += 1
            e[1] += c * min(y, st)
            e[2] += c * min(cap, st)
            e[3] += c * st
            if any(abs(z - d) < 1e-6 for d in a.detail):
                detail.append((b["mat"], nodes[b["a"]]["name"], nodes[b["b"]]["name"], c, min(y, st), st))
        tot = [sum(v[i] for v in by.values()) for i in range(4)]
        rows.append((z, tot, dict(by)))
        if detail:
            print(f"\n-- z = {z:.2f}: {len(detail)} beams")
            for d in sorted(detail, key=lambda d: -d[3] * min(d[4], 1e9)):
                print(f"   {d[0]:14s} {d[1]:18s} {d[2]:18s} cos {d[3]:.2f}  yield {d[4]/1e3:8.1f} kN  strength {d[5]/1e3:8.1f} kN")
        z = round(z - a.step, 6)

    out = ROOT / "docs" / "p4" / "front_sections.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    allm = sorted({k for _, _, by in rows for k in by})
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["z_m", "yield_kN", "cap_kN", "strength_kN"] + [f"{m}_yield_kN" for m in allm])
        for z, tot, by in rows:
            w.writerow([f"{z:.3f}"] + [f"{t/1e3:.1f}" if t < inf else "inf" for t in tot[1:]] +
                       [f"{by[m][1]/1e3:.1f}" if m in by and by[m][1] < inf else ("inf" if m in by else "") for m in allm])
    print(f"\n{'z':>6} {'yield kN':>10} {'cap kN':>10} {'strength':>10}   main contributors (axial yield, kN)")
    for z, tot, by in rows:
        top = sorted(by.items(), key=lambda kv: -min(kv[1][1], 1e12))[:7]
        s = ", ".join(f"{k}x{v[0]} {('inf' if v[1] == inf else f'{v[1]/1e3:.0f}')}" for k, v in top)
        f = lambda t: "inf" if t == inf else f"{t/1e3:.0f}"
        print(f"{z:6.2f} {f(tot[1]):>10} {f(tot[2]):>10} {f(tot[3]):>10}   {s}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
