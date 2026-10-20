"""Annotates the test map's top-down render (MapCheck: docs/p5/mapcheck/map_topdown.png, orthographic, 10 px per metre,
centred on the origin, north up) with the obstacle dimensions, the lanes' clean run-up lengths, the map extent, a scale
bar and a north arrow, from docs/p5/map_layout.json. Writes docs/p5/map_topdown_annotated.png.

Usage: tools/.venv/Scripts/python.exe tools/p5/annotate_map.py
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
PX = 10.0                  # pixels per metre
HALF_W, HALF_H = 151.5, 101.0


def to_px(x, z):
    return ((x + HALF_W) * PX, (HALF_H - z) * PX)


def font(size):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def label(d, xy, text, f, anchor="mm", fill=(255, 255, 255), bg=(20, 20, 20, 190), pad=8):
    box = d.textbbox(xy, text, font=f, anchor=anchor)
    d.rectangle((box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad), fill=bg)
    d.text(xy, text, font=f, fill=fill, anchor=anchor)


def o_dims(o):
    return f"{o['diameter_m']:.2f} m x {o['height_m']:.0f} m"


def arrow(d, a, b, fill, width=5, head=22):
    d.line((a, b), fill=fill, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for s in (-1, 1):
        d.line((b, (b[0] - head * math.cos(ang + s * 0.45), b[1] - head * math.sin(ang + s * 0.45))), fill=fill, width=width)


def main():
    lay = json.loads((ROOT / "docs/p5/map_layout.json").read_text(encoding="utf-8"))
    src = ROOT / "docs/p5/mapcheck/map_topdown.png"
    img = Image.open(src).convert("RGBA")
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    f_big, f_mid, f_small = font(46), font(30), font(25)
    obs = {o["id"]: o for o in lay["obstacles"]}

    # map extent
    W, H = lay["extent_m"]
    x0, y0 = to_px(-W / 2, H / 2)
    x1, y1 = to_px(W / 2, -H / 2)
    d.rectangle((x0, y0, x1, y1), outline=(255, 230, 80, 255), width=4)
    label(d, ((x0 + x1) / 2, y0 + 40), f"TestMap {W:.0f} m x {H:.0f} m  (x east, z north; grid 10 m; grass band {obs['ground']['grass_band_m']} m)", f_big)

    # lanes: spawn -> face with the clean run-up
    for ln in lay["lanes"]:
        a = to_px(*ln["spawn"])
        b = to_px(*ln["face"])
        arrow(d, a, b, (80, 200, 255, 230), width=4)
        mid = ((a[0] + b[0]) / 2 + 26, (a[1] + b[1]) / 2)
        label(d, mid, f"{ln['clean_run_m']:.1f} m", f_small, anchor="lm", fill=(150, 220, 255), bg=(10, 30, 50, 200), pad=5)

    # short tags on the obstacles, the dimensions in a legend (the east part of the map is open)
    tags = {"O1": (0, 4), "O2": (0, 4), "O3": (0, 4), "O4": (4, 2), "O5": (3, 10), "O6": (6, 0), "O7": (6, 0),
            "O8": (8, 4), "O9": (7, 0), "O9b": (2, 0)}
    for oid, (dx, dz) in tags.items():
        o = obs[oid]
        label(d, to_px(o["centre"][0] + dx, o["centre"][2] + dz), oid.replace("O9b", "O9 bank"), f_mid,
              fill=(255, 240, 120), bg=(30, 30, 30, 210), pad=6)
    o2 = obs["O2"]
    o4, o5, o6, o7, o8, o9, o9b = (obs[k] for k in ("O4", "O5", "O6", "O7", "O8", "O9", "O9b"))
    run = {ln["id"]: ln["clean_run_m"] for ln in lay["lanes"]}
    rows = [
        f"O1  concrete wall 12 x 3 x 1 m (full frontal); clean run-up {run['O1']:.1f} m",
        f"O2  the same wall, {o2['overlap'] * 100:.0f} % offset line (driver side); run-up {run['O2']:.1f} m",
        f"O3  steel pole {o_dims(obs['O3'])}; run-up {run['O3']:.1f} m",
        f"O4  {o4['units']} jersey barriers {o4['unit_length_m']} x {o4['height_m']} m (base {o4['base_width_m']}, top {o4['top_width_m']} m) at {o4['angle_to_lane_deg']} deg; run-up {run['O4']:.1f} m",
        f"O5  guardrail {o5['size'][2]} m, {o5['posts']} posts every {o5['post_spacing_m']} m, W-beam top {o5['wbeam_top_m']:.2f} m; lane at {o5['lane_angle_deg']} deg; run-up {run['O5']:.1f} m",
        f"O6  ramp {o6['ramp_length_m']:.0f} m x {o6['ramp_height_m']} m ({o6['ramp_angle_deg']:.1f} deg), landing pad {o6['landing_beyond_lip_m']:.0f} m beyond the lip; run-up {run['O6']:.1f} m",
        f"O7  speed bump {o7['bump_height_m']:.2f} m x {o7['bump_length_m']:.0f} m, curb {o7['curb_height_m']:.2f} m at {o7['curb_angle_deg']} deg; run-up {run['O7']:.1f} m",
        f"O8  debris (soft bodies): {o8['barrels']} barrels {o8['barrel_m'][0]} x {o8['barrel_m'][1]} m {o8['barrel_kg']:.0f} kg, {o8['boxes']} boxes {o8['box_m']} m {o8['box_kg']:.0f} kg,",
        f"      {o8['cones']} cones {o8['cone_m']} m {o8['cone_kg']} kg, {o8['fence_panels']} fence panels {o8['fence_panel_m'][0]} x {o8['fence_panel_m'][1]} m {o8['fence_panel_kg']:.0f} kg; run-up {run['O8']:.1f} m",
        f"O9  ledge {o9['ledge_height_m']:.0f} m over a lower pad, access ramp {o9['access_ramp_m']:.0f} m; run-up {run['O9']:.1f} m (incl. the ramp)",
        f"O9  bank {o9b['angle_deg']} deg, {o9b['height_m']:.0f} m high, {o9b['size'][2]:.0f} m long (steer onto it); run-up {run['O9b']:.1f} m",
        f"surfaces: asphalt x{lay['surfaces']['asphalt']}, concrete x{lay['surfaces']['concrete']}, grass x{lay['surfaces']['grass']} of the tyre's friction; skidpad R {obs['skidpad']['radius_m']} m",
    ]
    lx, ly = to_px(14, -12)
    widths = [d.textbbox((0, 0), r, font=f_small)[2] for r in rows]
    d.rectangle((lx - 14, ly - 14, lx + max(widths) + 14, ly + 36 * len(rows) + 6), fill=(15, 15, 15, 215))
    for k, r in enumerate(rows):
        d.text((lx, ly + 36 * k), r, font=f_small, fill=(255, 255, 255))

    # scale bar and north arrow
    sx, sy = to_px(60, -92)
    ex, _ = to_px(110, -92)
    d.line(((sx, sy), (ex, sy)), fill=(255, 255, 255, 255), width=8)
    for t in range(0, 51, 10):
        tx, _ = to_px(60 + t, -92)
        d.line(((tx, sy - 14), (tx, sy + 14)), fill=(255, 255, 255, 255), width=4)
    label(d, ((sx + ex) / 2, sy - 40), "50 m", f_mid)
    nx, ny = to_px(135, -80)
    arrow(d, (nx, ny + 70), (nx, ny - 40), (255, 255, 255, 255), width=8, head=30)
    label(d, (nx, ny - 75), "N", f_big)

    out = Image.alpha_composite(img, over).convert("RGB")
    dst = ROOT / "docs/p5/map_topdown_annotated.png"
    out.save(dst, optimize=True)
    print(f"wrote {dst.relative_to(ROOT)} ({out.size[0]}x{out.size[1]})")
    lane_sheet(rows, run)


def lane_sheet(rows, run):
    """Perspective shot of every lane with its dimension line, as a 2 x 5 sheet (docs/p5/map_lanes_sheet.jpg)."""
    shots = sorted((ROOT / "docs/p5/mapcheck").glob("lane_*_O*.png"))
    if not shots:
        return
    text = {}
    last = None
    for r in rows:
        key = r[:3].strip()
        if r.startswith("      ") and last:
            text[last] += " " + r.strip()
        elif key.startswith("O") and key not in text:
            text[key] = r[4:].strip()
            last = key
        else:
            last = None
    bank = [r for r in rows if r.startswith("O9  bank")]
    tiles = []
    f = font(30)
    for sh in shots:
        im = Image.open(sh).convert("RGB")
        oid = sh.stem.split("_")[2]
        order = int(sh.stem.split("_")[1])
        caption = (bank[0][4:].strip() if order == 10 and bank else text.get(oid, oid))
        d = ImageDraw.Draw(im, "RGBA")
        f_cap = font(30) if d.textlength(caption, font=font(30)) < im.size[0] - 120 else font(22)
        d.rectangle((0, im.size[1] - 70, im.size[0], im.size[1]), fill=(0, 0, 0, 190))
        d.text((20, im.size[1] - 35), f"{oid}: {caption}", font=f_cap, fill=(255, 255, 255), anchor="lm")
        tiles.append(im)
    w, h = tiles[0].size
    cols = 2
    rows_n = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w // 2, rows_n * h // 2), (30, 30, 30))
    for k, t in enumerate(tiles):
        sheet.paste(t.resize((w // 2, h // 2), Image.LANCZOS), ((k % cols) * w // 2, (k // cols) * h // 2))
    dst = ROOT / "docs/p5/map_lanes_sheet.jpg"
    sheet.save(dst, quality=90)
    print(f"wrote {dst.relative_to(ROOT)} ({len(tiles)} lanes)")


if __name__ == "__main__":
    main()
