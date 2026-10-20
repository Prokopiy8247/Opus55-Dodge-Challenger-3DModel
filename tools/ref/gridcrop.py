"""Zoomed crop of a reference photo with a labelled pixel grid, for reading feature coordinates.

Usage: tools/.venv/Scripts/python.exe tools/ref/gridcrop.py <image> <x0> <y0> <x1> <y1> <out.png> [--step 20] [--scale 3]
Grid lines every --step source pixels; labels show source-image coordinates.
Optional --points "x,y;x,y" draws crosses at given source coordinates (to verify picks).
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("x0", type=int)
    ap.add_argument("y0", type=int)
    ap.add_argument("x1", type=int)
    ap.add_argument("y1", type=int)
    ap.add_argument("out")
    ap.add_argument("--step", type=int, default=20)
    ap.add_argument("--scale", type=float, default=3.0)
    ap.add_argument("--points", default="")
    ns = ap.parse_args()

    img = Image.open(ns.image).convert("RGB")
    crop = img.crop((ns.x0, ns.y0, ns.x1, ns.y1))
    w, h = crop.size
    big = crop.resize((int(w * ns.scale), int(h * ns.scale)), Image.LANCZOS)
    d = ImageDraw.Draw(big)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    s = ns.scale
    start_x = (ns.x0 // ns.step + 1) * ns.step
    for x in range(start_x, ns.x1, ns.step):
        px = (x - ns.x0) * s
        major = x % (ns.step * 5) == 0
        d.line([(px, 0), (px, big.height)], fill=(255, 0, 0) if major else (255, 140, 140), width=1)
        if major:
            d.text((px + 2, 2), str(x), fill=(255, 255, 0), font=font)
    start_y = (ns.y0 // ns.step + 1) * ns.step
    for y in range(start_y, ns.y1, ns.step):
        py = (y - ns.y0) * s
        major = y % (ns.step * 5) == 0
        d.line([(0, py), (big.width, py)], fill=(0, 160, 255) if major else (140, 200, 255), width=1)
        if major:
            d.text((2, py + 2), str(y), fill=(0, 255, 255), font=font)
    if ns.points:
        for pair in ns.points.split(";"):
            x, y = (float(v) for v in pair.split(","))
            px, py = (x - ns.x0) * s, (y - ns.y0) * s
            d.line([(px - 8, py), (px + 8, py)], fill=(0, 255, 0), width=2)
            d.line([(px, py - 8), (px, py + 8)], fill=(0, 255, 0), width=2)
    Path(ns.out).parent.mkdir(parents=True, exist_ok=True)
    big.save(ns.out)
    print(f"{ns.out}: {big.width}x{big.height}")


if __name__ == "__main__":
    main()
