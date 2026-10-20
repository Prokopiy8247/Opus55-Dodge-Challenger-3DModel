"""Extract scaled profiles of the Challenger from the dimensions.com outline drawing (private reference).

Input:  reference_extra/dimensions_com/hellcat_outlines.svg   (side, plan, front, rear silhouettes)
        reference_extra/dimensions_com/hellcat_dimensions.svg (same layout, with internal feature lines)
Output: docs/p1/ref_profiles.json  (all lengths in metres, car frame: x right, y forward, z up,
                                    origin on the ground at mid-wheelbase on the centreline)
        docs/p1/ref_features_side.json (internal lines of the side view as polylines, car frame)
        docs/p1/ref_profiles.png   (check plot)

Usage: tools/.venv/Scripts/python.exe tools/ref/extract_outlines.py
"""
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from shapely.geometry import LineString, Polygon
from svgelements import SVG, Path as SvgPath, Shape, SimpleLine

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "reference_extra" / "dimensions_com"
OUT = ROOT / "docs" / "p1"
LENGTH_M = 5.02          # dimensions.com overall length (standard body; Widebody 5.017 m official)
GROUND_Y = 247.1         # SVG y of the dashed ground line


def sample(path, n=6000):
    p = SvgPath(path)
    pts = [p.point(t) for t in np.linspace(0.0, 1.0, n)]
    return np.array([[q.x, q.y] for q in pts])


def load_views():
    svg = SVG.parse(str(SRC / "hellcat_outlines.svg"))
    views = {}
    for e in svg.elements():
        if not isinstance(e, Shape) or isinstance(e, SimpleLine) or e.stroke is None or str(e.stroke) == "None":
            continue
        bb = e.bbox()
        if bb is None or bb[2] - bb[0] > 900:
            continue
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        key = ("side" if cy < 300 else "plan") if cx < 680 else ("front" if cy < 300 else "rear")
        views[key] = sample(e)
    return views


def crossings(poly, x):
    line = LineString([(x, -1e4), (x, 1e4)])
    inter = poly.boundary.intersection(line)
    ys = []
    for g in getattr(inter, "geoms", [inter]):
        if g.is_empty:
            continue
        if g.geom_type == "Point":
            ys.append(g.y)
        else:
            ys.extend(c[1] for c in g.coords)
    return sorted(ys)


def fit_circle(pts):
    def res(c):
        return np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1]) - c[2]
    x0 = [pts[:, 0].mean(), pts[:, 1].mean() - 20, 20]
    r = least_squares(res, x0)
    return r.x, float(np.sqrt(np.mean(res(r.x) ** 2)))


def main():
    views = load_views()
    side = views["side"]
    xmin, xmax = side[:, 0].min(), side[:, 0].max()
    scale = (xmax - xmin) / LENGTH_M  # SVG units per metre

    # Wheels: the side outline follows the tire circle between the arch openings, below the body.
    side_poly = Polygon(side).buffer(0)
    lower = side[side[:, 1] > GROUND_Y - 0.33 * scale]
    wheels = []
    for lo, hi in ((xmin, (xmin + xmax) / 2), ((xmin + xmax) / 2, xmax)):
        seg = lower[(lower[:, 0] > lo) & (lower[:, 0] < hi)]
        # keep the arc: points well below the rocker line and not on the bumper
        cx_guess = seg[np.argmax(seg[:, 1]), 0]
        arc = seg[np.abs(seg[:, 0] - cx_guess) < 0.33 * scale]
        arc = arc[arc[:, 1] > GROUND_Y - 0.28 * scale]
        c, rms = fit_circle(arc)
        wheels.append({"cx": float(c[0]), "cy": float(c[1]), "r": float(c[2]), "rms": rms, "n": int(len(arc))})
    rear_w, front_w = sorted(wheels, key=lambda w: w["cx"])
    x_mid = 0.5 * (rear_w["cx"] + front_w["cx"])

    def to_y(sx):
        return (sx - x_mid) / scale

    def to_z(sy):
        return (GROUND_Y - sy) / scale

    stations = np.arange(math.ceil(to_y(xmin) * 100) / 100, to_y(xmax), 0.01)
    top, bottom = [], []
    for y in stations:
        ys = crossings(side_poly, x_mid + y * scale)
        if len(ys) < 2:
            top.append(None)
            bottom.append(None)
            continue
        top.append(round(to_z(ys[0]), 4))
        bottom.append(round(to_z(ys[-1]), 4))

    # Plan: half-width per station from the plan silhouette (mirrors bridged by interpolation).
    plan = views["plan"]
    plan_poly = Polygon(plan).buffer(0)
    p_xmin, p_xmax = plan[:, 0].min(), plan[:, 0].max()
    p_scale = (p_xmax - p_xmin) / LENGTH_M
    p_mid_x = p_xmin + (x_mid - xmin) * p_scale / scale
    halfw, centre = [], []
    for y in stations:
        ys = crossings(plan_poly, p_mid_x + y * p_scale)
        if len(ys) < 2:
            halfw.append(None)
            centre.append(None)
            continue
        halfw.append((ys[-1] - ys[0]) / 2 / p_scale)
        centre.append((ys[-1] + ys[0]) / 2)
    halfw = np.array([np.nan if v is None else v for v in halfw])
    # mirror bump: local maxima above the smooth envelope -> bridge with linear interpolation
    smooth = halfw.copy()
    ok = ~np.isnan(halfw)
    med = np.nanmedian(halfw[ok][len(halfw[ok]) // 4: 3 * len(halfw[ok]) // 4])
    mirror = halfw > med + 0.025
    if mirror.any():
        idx = np.where(mirror)[0]
        lo, hi = max(idx[0] - 3, 0), min(idx[-1] + 3, len(halfw) - 1)
        smooth[lo:hi + 1] = np.interp(np.arange(lo, hi + 1), [lo, hi], [halfw[lo], halfw[hi]])
    mirror_span = [float(stations[np.where(mirror)[0][0]]), float(stations[np.where(mirror)[0][-1]])] if mirror.any() else None

    # Front and rear views: half-width envelope per height.
    def envelope(pts):
        poly = Polygon(pts).buffer(0)
        cx = 0.5 * (pts[:, 0].min() + pts[:, 0].max())
        ground = pts[:, 1].max()  # each view stands on its own ground line
        heights = np.arange(0.0, (ground - pts[:, 1].min()) / scale, 0.01)
        out = []
        for z in heights:
            sy = ground - z * scale
            line = LineString([(-1e4, sy), (1e4, sy)])
            inter = poly.boundary.intersection(line)
            xs = []
            for g in getattr(inter, "geoms", [inter]):
                if g.is_empty:
                    continue
                if g.geom_type == "Point":
                    xs.append(g.x)
                else:
                    xs.extend(c[0] for c in g.coords)
            out.append(None if len(xs) < 2 else round((max(xs) - min(xs)) / 2 / scale, 4))
        return [round(float(h), 3) for h in heights], out, float(cx)

    fz, fw, fcx = envelope(views["front"])
    rz, rw, rcx = envelope(views["rear"])

    result = {
        "source": "dimensions.com Dodge Challenger SRT Hellcat (3rd Gen) outline drawing (standard body), private reference",
        "frame": "x right, y forward, z up; origin on the ground at mid-wheelbase, centreline",
        "svg_units_per_m": scale,
        "length_m": LENGTH_M,
        "y_front": round(to_y(xmax), 4),
        "y_rear": round(to_y(xmin), 4),
        "height_max_m": round(to_z(side[:, 1].min()), 4),
        "wheelbase_m": round((front_w["cx"] - rear_w["cx"]) / scale, 4),
        "wheels": {
            "front": {"y": round(to_y(front_w["cx"]), 4), "z": round(to_z(front_w["cy"]), 4), "r": round(front_w["r"] / scale, 4), "fit_rms_m": round(front_w["rms"] / scale, 5)},
            "rear": {"y": round(to_y(rear_w["cx"]), 4), "z": round(to_z(rear_w["cy"]), 4), "r": round(rear_w["r"] / scale, 4), "fit_rms_m": round(rear_w["rms"] / scale, 5)},
        },
        "side": {"y": [round(float(v), 3) for v in stations], "z_top": top, "z_bottom": bottom},
        "plan": {"y": [round(float(v), 3) for v in stations],
                 "half_width_raw": [None if np.isnan(v) else round(float(v), 4) for v in halfw],
                 "half_width": [None if np.isnan(v) else round(float(v), 4) for v in smooth],
                 "mirror_span_y": mirror_span},
        "front_view": {"z": fz, "half_width": fw},
        "rear_view": {"z": rz, "half_width": rw},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ref_profiles.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    # Internal lines of the side view (dimensions drawing) in the car frame.
    feats = []
    dsvg = SVG.parse(str(SRC / "hellcat_dimensions.svg"))
    for e in dsvg.elements():
        if not isinstance(e, Shape) or isinstance(e, SimpleLine):
            continue
        bb = e.bbox()
        if bb is None or not (xmin - 5 <= bb[0] and bb[2] <= xmax + 5 and 60 <= bb[1] and bb[3] <= GROUND_Y + 2):
            continue
        pts = sample(e, 400)
        feats.append({"bbox_m": [round(to_y(bb[0]), 3), round(to_z(bb[3]), 3), round(to_y(bb[2]), 3), round(to_z(bb[1]), 3)],
                      "pts": [[round(to_y(p[0]), 4), round(to_z(p[1]), 4)] for p in pts[::4]]})
    (OUT / "ref_features_side.json").write_text(json.dumps({"lines": feats}, indent=0), encoding="utf-8")

    # Check plot.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(16, 15))
    ax = axes[0]
    ax.plot(to_y(side[:, 0]), to_z(side[:, 1]), "m-", lw=1, label="side outline")
    for f in feats:
        a = np.array(f["pts"])
        ax.plot(a[:, 0], a[:, 1], "-", color="0.6", lw=0.6)
    for w in (front_w, rear_w):
        t = np.linspace(0, 2 * np.pi, 200)
        ax.plot(to_y(w["cx"] + w["r"] * np.cos(t)), to_z(w["cy"] + w["r"] * np.sin(t)), "b--", lw=0.8)
    ax.set_aspect("equal")
    ax.grid(True, lw=0.3)
    ax.set_title(f"side: wheelbase {result['wheelbase_m']} m, wheels r={result['wheels']['front']['r']}/{result['wheels']['rear']['r']} m")
    ax = axes[1]
    ax.plot(stations, halfw, "r-", lw=0.8, label="plan half-width raw")
    ax.plot(stations, smooth, "k-", lw=1, label="no mirrors")
    ax.grid(True, lw=0.3)
    ax.legend()
    ax.set_title("plan half-width (m) vs y")
    ax = axes[2]
    ax.plot(fw, fz, "g-", label="front view half-width")
    ax.plot(rw, rz, "b-", label="rear view half-width")
    ax.set_aspect("equal")
    ax.grid(True, lw=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "ref_profiles.png", dpi=90)
    print(json.dumps({k: result[k] for k in ("svg_units_per_m", "y_front", "y_rear", "height_max_m", "wheelbase_m", "wheels")}, indent=1))
    print("mirror span", mirror_span, "features", len(feats))


if __name__ == "__main__":
    main()
