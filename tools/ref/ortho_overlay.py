"""Orthographic renders of the model with the reference silhouettes drawn on top (G-Model overlays).

The reference lines come from docs/p1/ref_profiles.json (traced from the dimensions.com drawing,
standard body) and the spec sheet; the renders and their framing from hcar.render.ortho_views.

Usage: tools/.venv/Scripts/python.exe tools/ref/ortho_overlay.py <views.json> [date prefix]
Writes docs/p1/overlay_gate/ortho_<view>.png and a copy in docs/video_assets/P1/.
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
REF = (0, 200, 255, 255)        # reference silhouette
GRID = (255, 255, 255, 70)


def arr(v):
    return np.array([np.nan if x is None else x for x in v], float)


def to_px(meta, P):
    """World points (n, 3) -> pixel coordinates for an ortho view."""
    W, H = meta["res"]
    s = W / meta["width_m"]
    (ax, sx), (ay, sy) = meta["axes"]
    t = np.asarray(meta["target"], float)
    u = W / 2 + sx * (P[:, ax] - t[ax]) * s
    v = H / 2 - sy * (P[:, ay] - t[ay]) * s
    return np.stack([u, v], axis=1)


def polylines(meta, view, rp):
    """Reference polylines (lists of world points) for a view."""
    out = []
    if view == "side":
        y = np.array(rp["side"]["y"])
        for key in ("z_top", "z_bottom"):
            z = arr(rp["side"][key])
            ok = ~np.isnan(z)
            out.append(np.stack([np.zeros(ok.sum()), y[ok], z[ok]], axis=1))
    elif view in ("front", "rear"):
        z = np.array(rp[f"{view}_view"]["z"])
        hw = arr(rp[f"{view}_view"]["half_width"])
        ok = ~np.isnan(hw)
        for sgn in (1, -1):
            out.append(np.stack([sgn * hw[ok], np.zeros(ok.sum()), z[ok]], axis=1))
    elif view == "top":
        y = np.array(rp["plan"]["y"])
        hw = arr(rp["plan"]["half_width"])
        ok = ~np.isnan(hw)
        for sgn in (1, -1):
            out.append(np.stack([sgn * hw[ok], y[ok], np.zeros(ok.sum())], axis=1))
    return out


def split_nan_jumps(px, max_jump=60):
    """Break a pixel polyline where consecutive points jump (gaps in the traced profile)."""
    d = np.linalg.norm(np.diff(px, axis=0), axis=1)
    cuts = np.nonzero(d > max_jump)[0] + 1
    return np.split(px, cuts)


def main():
    views_json = Path(sys.argv[1])
    date = sys.argv[2] if len(sys.argv) > 2 else "2026-10-11"
    views = json.loads(views_json.read_text(encoding="utf-8"))
    rp = json.loads((ROOT / "docs/p1/ref_profiles.json").read_text(encoding="utf-8"))
    od = ROOT / "docs/p1/overlay_gate"
    va = ROOT / "docs/video_assets/P1"
    od.mkdir(parents=True, exist_ok=True)
    va.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    for view, meta in views.items():
        img = Image.open(meta["png"]).convert("RGBA")
        bg = Image.new("RGBA", img.size, (38, 40, 44, 255))
        dr = ImageDraw.Draw(bg)
        # 10 cm grid, labelled every metre
        W, H = meta["res"]
        s = W / meta["width_m"]
        (ax, sx), (ay, sy) = meta["axes"]
        t = meta["target"]
        for k in range(-60, 61):
            x = W / 2 + sx * (k * 0.1 - t[ax]) * s
            y = H / 2 - sy * (k * 0.1 - t[ay]) * s
            wdt = 2 if k % 10 == 0 else 1
            if 0 <= x < W:
                dr.line([(x, 0), (x, H)], fill=GRID, width=wdt)
            if 0 <= y < H:
                dr.line([(0, y), (W, y)], fill=GRID, width=wdt)
        bg.alpha_composite(img)
        dr = ImageDraw.Draw(bg)
        for P in polylines(meta, view, rp):
            for seg in split_nan_jumps(to_px(meta, P)):
                if len(seg) > 1:
                    dr.line([tuple(p) for p in seg], fill=REF, width=3)
        dr.text((24, 18), f"{view}: model render (orthographic) + reference silhouette (cyan, dimensions.com profile, "
                          f"standard body); grid 10 cm", fill=(255, 255, 255, 255), font=font)
        out = od / f"ortho_{view}.png"
        bg.convert("RGB").save(out)
        shutil.copy(out, va / f"{date}_P1_ortho_overlay_{view}.png")
        print(out)


if __name__ == "__main__":
    main()
