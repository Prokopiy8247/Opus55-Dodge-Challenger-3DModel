"""Closure joints of a skeleton (D-063): every hinge and latch node of a door, the hood and the deck lid must be held in
all three directions by its hinge / latch beams, or the closure has a free direction that only its soft seals resist.

A node held by beams with unit directions u_k resists a small motion d with stiffness k * sum (u_k . d)^2; the smallest
singular value of the direction matrix [u_k] is 0 when the beams lie in one plane (pins to three nodes in one row: the
door hinges were free along the car, the door latches outward-forward, the hood latch upward, P4).

Usage: tools/.venv/Scripts/python.exe tools/skeleton/closure_joints.py [vehicle] [--min-sv 0.3] [--json out.json]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
JOINT_MATS = ("hinge", "latch", "latch_hood", "latch_tie")
CLOSURES = ("door_", "hood", "trunk")


def joints(g):
    """Closure node index -> (material, [target node indices])."""
    N = g["nodes"]
    out = defaultdict(lambda: [None, []])
    for b in g["beams"]:
        if b["mat"] not in JOINT_MATS:
            continue
        a, c = b["a"], b["b"]
        if not N[a]["part"].startswith(CLOSURES):
            a, c = c, a
        if not N[a]["part"].startswith(CLOSURES) or N[c]["part"].startswith(CLOSURES):
            continue
        out[a][0] = b["mat"]
        out[a][1].append(c)
    return out


def report(g, min_sv):
    N = g["nodes"]
    P = np.array([n["p"] for n in N], float)
    rows = []
    for a, (mat, ts) in sorted(joints(g).items(), key=lambda kv: N[kv[0]]["name"]):
        D = np.array([(P[t] - P[a]) / np.linalg.norm(P[t] - P[a]) for t in ts])
        Dp = np.vstack([D, np.zeros((max(0, 3 - len(D)), 3))])
        _, s, vt = np.linalg.svd(Dp)
        rows.append({"node": N[a]["name"], "part": N[a]["part"], "mat": mat, "beams": len(ts),
                     "targets": [N[t]["name"] for t in ts], "sv_min": round(float(s[-1]), 3),
                     "free_dir": [round(float(v), 2) for v in vt[-1]], "ok": bool(s[-1] >= min_sv)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--min-sv", type=float, default=0.3)
    ap.add_argument("--json", type=Path, default=None)
    ns = ap.parse_args()
    g = json.loads((ROOT / "sim" / "vehicle" / ns.vehicle / "geometry.json").read_text(encoding="utf-8"))
    rows = report(g, ns.min_sv)
    for r in rows:
        print(f"{'ok ' if r['ok'] else 'BAD'} {r['node']:16s} {r['mat']:10s} beams {r['beams']} sv_min {r['sv_min']:.2f} "
              f"weakest {r['free_dir']}  -> {', '.join(r['targets'])}")
    bad = [r for r in rows if not r["ok"]]
    print(f"{len(rows)} closure joints, {len(bad)} below sv_min {ns.min_sv}")
    if ns.json:
        ns.json.write_text(json.dumps({"min_sv": ns.min_sv, "joints": rows}, indent=1), encoding="utf-8")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
