"""P6 videos and stills from the scenario runs (tools/p6/run_scenarios.ps1 -> sim/cache/<S>/kmh<v>/frames, frames_slowmo).

Per scenario at the brief's speed:
- a 2x2 grid video in real time (tracking | side / three-quarter | top), 1920x1080 H.264 at 60 fps, with a label;
- the slow-motion replay (250 fps re-render of the recording) as a 3-up strip (tracking | side | three-quarter) played at
  30 fps (1/8.3 speed), 1920x1080;
- the side camera alone in real time and in slow motion (the brief's side + tracking pair is in the grid);
- the stills at the event and at the end (four cameras each) as JPG with the asset naming of docs/video_assets.
Plus a contact sheet of all eight scenarios (per scenario one still at the event and one of the outcome, from the camera
that shows it best) and a reel of the eight grids.

Usage: tools/.venv/Scripts/python.exe tools/p6/make_videos.py [--date 2026-10-15] [--only S1,S2] [--sheet-only]
Output: docs/video_assets/P6/
"""
import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "video_assets" / "P6"
RUNS = [("S1", 50), ("S2", 64), ("S3", 50), ("S4", 40), ("S5", 80), ("S6", 70), ("S7", 15), ("S8", 120)]
CAMS = ("chase", "side", "front34", "top")
SLOW = ("chase", "side", "front34")


def font(size):
    for f in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def strip_png(text, path, width=1920):
    im = Image.new("RGBA", (width, 56), (0, 0, 0, 150))
    ImageDraw.Draw(im).text((18, 10), text, font=font(28), fill=(255, 255, 255, 255))
    im.save(path)


def encode(inputs, flt, out, extra=()):
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + ["-filter_complex", flt, "-map", "[v]", "-c:v", "libx264", "-preset", "slow",
                                                             "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", *extra, str(out)]
    subprocess.run(cmd, check=True)


def label(sc, kmh, res):
    what = res.get("what", "")
    if res.get("kind") == "Jump" and res.get("airborne_s"):
        ev = f"airborne {res['airborne_s']:.2f} s"
    elif res.get("kind") == "Debris":
        ev = f"{res.get('props_moved')} props moved"
    else:
        ev = f"entry {res.get('entry_speed_kmh')} km/h"
    return f"{sc} {what} - {kmh} km/h, {ev}"


def videos(sc, kmh, date):
    d = ROOT / "sim" / "cache" / sc / f"kmh{kmh}"
    rj = d / f"{sc}_{kmh}kmh_result.json"
    if not rj.exists():
        print("no result:", rj)
        return []
    res = json.loads(rj.read_text(encoding="utf-8"))
    made = []
    fr = d / "frames"
    n = len(list(fr.glob("chase_*.jpg")))
    if n:
        out = OUT / f"{date}_P6_{sc}_{kmh}kmh_grid.mp4"
        strip = OUT / f"_label_{sc}.png"
        strip_png(label(sc, kmh, res) + "   |   real time; tracking, side / three-quarter, top", strip)
        inputs = []
        for cam in CAMS:
            inputs += ["-framerate", "60", "-i", str(fr / f"{cam}_%04d.jpg")]
        encode(inputs + ["-i", str(strip)], "[0][1][2][3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0,scale=1920:1080:flags=lanczos[g];"
                                             "[g][4]overlay=0:H-h[v]", out)
        strip.unlink()
        made.append(out)
        out = OUT / f"{date}_P6_{sc}_{kmh}kmh_side.mp4"
        encode(["-framerate", "60", "-i", str(fr / "side_%04d.jpg")], "[0]scale=1920:1080:flags=lanczos[v]", out)
        made.append(out)
        print(f"{sc}: real time {n} frames ({n / 60:.1f} s)")
    sl = d / "frames_slowmo"
    m = len(list(sl.glob("chase_*.jpg")))
    if m:
        fps = res.get("slowmo_fps") or 250
        out = OUT / f"{date}_P6_{sc}_{kmh}kmh_slowmo.mp4"
        strip = OUT / f"_label_{sc}_slow.png"
        strip_png(label(sc, kmh, res) + f"   |   replay re-rendered at {fps} fps, played at 30 fps (1/{fps / 30:.1f} speed)", strip)
        inputs = []
        for cam in SLOW:
            inputs += ["-framerate", "30", "-i", str(sl / f"{cam}_%04d.jpg")]
        # three 640x360 tiles over a 1920x1080 frame: tracking and side large, three-quarter below
        encode(inputs + ["-i", str(strip)],
               "[0]scale=960:540[a];[1]scale=960:540[b];[2]scale=960:540[c];"
               "color=c=black:s=1920x1080:r=30[bg];[bg][a]overlay=0:0:shortest=1[t1];[t1][b]overlay=960:0[t2];"
               "[t2][c]overlay=480:540[g];[g][3]overlay=0:H-h[v]", out)
        strip.unlink()
        made.append(out)
        out = OUT / f"{date}_P6_{sc}_{kmh}kmh_side_slowmo.mp4"
        encode(["-framerate", "30", "-i", str(sl / "side_%04d.jpg")], "[0]scale=1920:1080:flags=lanczos[v]", out)
        made.append(out)
        print(f"{sc}: slow motion {m} frames at {fps} fps ({m / 30:.1f} s at 30 fps)")
    for when in ("at_impact", "final"):
        for cam in CAMS:
            src = d / f"{sc}_{kmh}kmh_{when}_{cam}.png"
            if src.exists():   # JPG (quality 92): a tenth of the PNG's size, the PNG stays in sim/cache
                Image.open(src).convert("RGB").save(OUT / f"{date}_P6_{sc}_{kmh}kmh_{when}_{cam}.jpg", quality=92)
    return made


# contact sheet: (moment, camera, caption) of the event and of the outcome per scenario; the fixed cameras look at the
# obstacle, so the runs that carry on past it (S5, S6) show their outcome from the tracking camera
SHEET = {
    "S1": (("at_impact", "side", "contact"), ("final", "front34", "at rest")),
    "S2": (("at_impact", "side", "contact"), ("final", "top", "at rest, turned by the offset load")),
    "S3": (("at_impact", "side", "contact"), ("final", "front34", "at rest, pole in the front")),
    "S4": (("at_impact", "side", "sliding along the barriers"), ("final", "top", "glanced off")),
    "S5": (("at_impact", "front34", "landing"), ("final", "chase", "driving on")),
    "S6": (("at_impact", "side", "scraping the rail"), ("at_impact", "front34", "scraping the rail")),
    "S7": (("at_impact", "side", "into the barrels"), ("final", "top", "debris scattered")),
    "S8": (("at_impact", "side", "contact"), ("final", "side", "at rest")),
}


def sheet(date):
    w, h = 640, 360
    sh = Image.new("RGB", (w * 4, h * 4), (30, 30, 30))
    n = 0
    for k, (sc, kmh) in enumerate(RUNS):
        d = ROOT / "sim" / "cache" / sc / f"kmh{kmh}"
        for j, (when, cam, cap) in enumerate(SHEET[sc]):
            f = d / f"{sc}_{kmh}kmh_{when}_{cam}.png"
            if not f.exists():
                continue
            im = Image.open(f).convert("RGB").resize((w, h), Image.LANCZOS)
            dr = ImageDraw.Draw(im)
            dr.rectangle((0, 0, w, 36), fill=(0, 0, 0))
            dr.text((10, 4), f"{sc} {kmh} km/h - {cap}", font=font(22), fill=(255, 255, 255))
            sh.paste(im, ((k % 4) * w, ((k // 4) * 2 + j) * h))
            n += 1
    if not n:
        return
    out = OUT / f"{date}_P6_scenarios_sheet.jpg"
    sh.save(out, quality=90)
    print(out.name, sh.size, n, "stills")


def reel(grids, date):
    if len(grids) < 2:
        return
    lst = OUT / "_reel.txt"
    lst.write_text("".join(f"file '{g.as_posix()}'\n" for g in grids), encoding="utf-8")
    out = OUT / f"{date}_P6_scenarios_reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True)
    lst.unlink()
    print(out.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-10-15")
    ap.add_argument("--only", default="")
    ap.add_argument("--sheet-only", action="store_true")
    ns = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if ns.sheet_only:
        sheet(ns.date)
        return
    only = [s for s in ns.only.split(",") if s]
    grids = []
    for sc, kmh in RUNS:
        if only and sc not in only:
            continue
        made = videos(sc, kmh, ns.date)
        grids += [m for m in made if m.name.endswith("_grid.mp4")]
    sheet(ns.date)
    if not only:
        reel(grids, ns.date)


if __name__ == "__main__":
    main()
