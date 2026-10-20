"""Internal feature lines of all four views of the dimensions.com drawing, in the car frame, with an
index plot per view (to identify beltline, window openings, panel cuts, lamps ...).

Output: docs/p1/ref_features.json  {"side": [...], "plan": [...], "front": [...], "rear": [...]}
        each line: {"i": index, "bbox": [min_a, min_b, max_a, max_b], "pts": [[a, b], ...]}
          side : a = y (forward), b = z (up)
          plan : a = y, b = x (right; the drawing's plan shows the car's right side at the bottom)
          front: a = x (right as seen from the front = car's left!), b = z  -> stored as car x (negated)
          rear : a = x (car x), b = z
        docs/p1/ref_features_<view>.png
"""
import json
from pathlib import Path

import numpy as np
from svgelements import SVG, Path as SvgPath, Shape, SimpleLine

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "reference_extra" / "dimensions_com"
OUT = ROOT / "docs" / "p1"
prof = json.loads((OUT / "ref_profiles.json").read_text(encoding="utf-8"))
S = prof["svg_units_per_m"]


def sample(e, n):
    p = SvgPath(e)
    return np.array([[q.x, q.y] for q in (p.point(t) for t in np.linspace(0, 1, n))])


def view_frames():
    """SVG -> car-frame transforms per view, from the outline drawing bboxes."""
    o = SVG.parse(str(SRC / "hellcat_outlines.svg"))
    boxes = {}
    for e in o.elements():
        if isinstance(e, Shape) and not isinstance(e, SimpleLine) and e.stroke is not None and str(e.stroke) != "None":
            bb = e.bbox()
            if bb is None or bb[2] - bb[0] > 900:
                continue
            cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            key = ("side" if cy < 300 else "plan") if cx < 680 else ("front" if cy < 300 else "rear")
            boxes[key] = bb
    side, plan = boxes["side"], boxes["plan"]
    y_rear = prof["y_rear"]
    # side: svg x -> y, svg y -> z (ground at the side bbox bottom)
    fs = lambda p: np.c_[(p[:, 0] - side[0]) / S + y_rear, (side[3] - p[:, 1]) / S]
    # plan: svg x -> y (same left edge = rear), svg y -> x; car centreline = middle of the body (mirrors symmetric)
    pc = 0.5 * (plan[1] + plan[3])
    fp = lambda p: np.c_[(p[:, 0] - plan[0]) / S + y_rear, (p[:, 1] - pc) / S]
    fr = boxes["front"]
    fcx = 0.5 * (fr[0] + fr[2])
    ff = lambda p: np.c_[-(p[:, 0] - fcx) / S, (fr[3] - p[:, 1]) / S]
    rr = boxes["rear"]
    rcx = 0.5 * (rr[0] + rr[2])
    frr = lambda p: np.c_[(p[:, 0] - rcx) / S, (rr[3] - p[:, 1]) / S]
    return {"side": (side, fs), "plan": (plan, fp), "front": (fr, ff), "rear": (rr, frr)}


def main():
    frames = view_frames()
    d = SVG.parse(str(SRC / "hellcat_dimensions.svg"))
    result = {k: [] for k in frames}
    for e in d.elements():
        if not isinstance(e, Shape) or isinstance(e, SimpleLine):
            continue
        bb = e.bbox()
        if bb is None:
            continue
        for key, (vb, tf) in frames.items():
            if vb[0] - 3 <= bb[0] and bb[2] <= vb[2] + 3 and vb[1] - 3 <= bb[1] and bb[3] <= vb[3] + 3:
                pts = tf(sample(e, 300))
                lo, hi = pts.min(axis=0), pts.max(axis=0)
                result[key].append({"i": len(result[key]), "bbox": [round(float(v), 4) for v in (*lo, *hi)],
                                    "pts": [[round(float(a), 4), round(float(b), 4)] for a, b in pts[::3]]})
                break
    (OUT / "ref_features.json").write_text(json.dumps(result), encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sizes = {"side": (26, 9), "plan": (26, 11), "front": (14, 10), "rear": (14, 10)}
    for key, lines in result.items():
        fig, ax = plt.subplots(figsize=sizes[key])
        cmap = plt.get_cmap("tab20")
        for ln in lines:
            a = np.array(ln["pts"])
            c = cmap(ln["i"] % 20)
            ax.plot(a[:, 0], a[:, 1], "-", color=c, lw=0.9)
            m = a[len(a) // 2]
            ax.text(m[0], m[1], str(ln["i"]), fontsize=7, color=c)
        ax.set_aspect("equal")
        ax.grid(True, lw=0.25)
        ax.minorticks_on()
        ax.grid(True, which="minor", lw=0.1)
        ax.set_title(f"{key}: {len(lines)} lines (car frame, m)")
        fig.tight_layout()
        fig.savefig(OUT / f"ref_features_{key}.png", dpi=80)
        plt.close(fig)
        print(key, len(lines))


if __name__ == "__main__":
    main()
