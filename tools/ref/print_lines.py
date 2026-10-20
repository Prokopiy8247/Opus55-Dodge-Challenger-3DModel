"""Print feature lines of a view as resampled point lists (for building the shape tables).

Usage: tools/.venv/Scripts/python.exe tools/ref/print_lines.py side 4 10 23 [--step 0.1] [--axis a]
  --axis a : resample at regular values of the first coordinate (y for side/plan, x for front/rear)
  --axis b : resample along the second coordinate; default: arc length
"""
import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("view")
    ap.add_argument("ids", nargs="+", type=int)
    ap.add_argument("--step", type=float, default=0.1)
    ap.add_argument("--axis", default="s")
    ns = ap.parse_args()
    data = json.loads((ROOT / "docs/p1/ref_features.json").read_text(encoding="utf-8"))[ns.view]
    for i in ns.ids:
        ln = next(l for l in data if l["i"] == i)
        p = np.array(ln["pts"])
        if ns.axis in ("a", "b"):
            k = 0 if ns.axis == "a" else 1
            lo, hi = p[:, k].min(), p[:, k].max()
            vals = np.arange(np.ceil(lo / ns.step) * ns.step, hi + 1e-9, ns.step)
            out = []
            for v in vals:
                # all crossings of the polyline with the line coordinate k = v
                for j in range(len(p) - 1):
                    a, b = p[j, k], p[j + 1, k]
                    if (a - v) * (b - v) <= 0 and a != b:
                        t = (v - a) / (b - a)
                        q = p[j] + t * (p[j + 1] - p[j])
                        out.append((round(float(q[0]), 3), round(float(q[1]), 3)))
            pts = out
        else:
            seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
            s = np.arange(0, seg[-1] + 1e-9, ns.step)
            pts = [(round(float(np.interp(v, seg, p[:, 0])), 3), round(float(np.interp(v, seg, p[:, 1])), 3)) for v in s]
        print(f"{ns.view}#{i} bbox={ln['bbox']} n={len(pts)}")
        print("  " + " ".join(f"({a},{b})" for a, b in pts))


if __name__ == "__main__":
    main()
