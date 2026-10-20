"""P4 videos and stills from the crash runs (tools/p4/crash_series.ps1 -> sim/cache/<scenario>/<run>/frames).

- a 2x2 grid video per run (chase | side / front34 | top), 1920x1080 H.264, at the capture rate (60 fps real time;
  the 250 fps slow-motion run played at 30 fps = 1/8.3 speed) with a label;
- the run's stills at impact and at the end (4 cameras each), copied with the asset naming of docs/video_assets;
- a contact sheet of the speed series: the final three-quarter view (left rear) per speed, and the side view 50 ms after the
  contact per speed.

Usage: tools/.venv/Scripts/python.exe tools/p4/make_videos.py [--date 2026-10-14]
Output: docs/video_assets/P4/
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "video_assets" / "P4"
RUNS = [  # scenario, folder, km/h, capture fps, playback fps, label
    ("S1", "kmh50", 50, 60, 60, "S1 rigid wall 50 km/h - real time"),
    ("S1", "kmh50_slowmo", 50, 250, 30, "S1 rigid wall 50 km/h - 250 fps capture, 1/8.3 speed"),
    ("S1", "kmh56", 56, 60, 60, "S1 rigid wall 56 km/h - real time"),
    ("S1", "kmh64", 64, 60, 60, "S1 rigid wall 64 km/h - real time"),
    ("S8", "kmh120", 120, 60, 60, "S8 rigid wall 120 km/h (rolling launch) - real time"),
    ("S8", "kmh120_glasstest", 120, 60, 60, "Glass shard swap test (all panes broken at 0.4 s) - 120 km/h"),
]
SERIES = [("S1", "kmh30", 30), ("S1", "kmh40", 40), ("S1", "kmh50", 50), ("S1", "kmh56", 56), ("S1", "kmh64", 64),
          ("S8", "kmh120", 120)]
CAMS = ("chase", "side", "front34", "top")


def font(size):
    for f in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def grid_video(sc, folder, kmh, fps_in, fps_out, label, date):
    d = ROOT / "sim" / "cache" / sc / folder / "frames"
    n = len(list(d.glob("chase_*.jpg")))
    if n == 0:
        print("no frames:", d)
        return None
    out = OUT / f"{date}_P4_{sc}_{folder}_grid.mp4"
    inputs = []
    for cam in CAMS:
        inputs += ["-framerate", str(fps_out), "-i", str(d / f"{cam}_%04d.jpg")]
    # label strip: rendered once as a PNG overlay (no ffmpeg font configuration needed)
    strip = OUT / f"_label_{folder}.png"
    im = Image.new("RGBA", (1920, 56), (0, 0, 0, 150))
    dr = ImageDraw.Draw(im)
    dr.text((18, 10), f"{label}   |   cameras: chase, side / three-quarter, top", font=font(28), fill=(255, 255, 255, 255))
    im.save(strip)
    flt = ("[0][1][2][3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0,scale=1920:1080:flags=lanczos[g];"
           "[g][4]overlay=0:H-h[v]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + ["-i", str(strip), "-filter_complex", flt, "-map", "[v]",
                                                             "-c:v", "libx264", "-preset", "slow", "-crf", "19",
                                                             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    strip.unlink()
    res = json.loads((d.parent / f"{sc}_{kmh}kmh_result.json").read_text(encoding="utf-8"))
    print(f"{out.name}: {n} frames at {fps_out} fps ({n / fps_out:.1f} s; captured at {fps_in} fps), "
          f"{out.stat().st_size / 1e6:.1f} MB, impact {res['speed_at_impact_kmh']} km/h")
    return out


def stills(sc, folder, kmh, date):
    d = ROOT / "sim" / "cache" / sc / folder
    for when in ("at_impact", "final"):
        for cam in CAMS:
            src = d / f"{sc}_{kmh}kmh_{when}_{cam}.png"
            if src.exists():
                shutil.copy2(src, OUT / f"{date}_P4_{sc}_{folder}_{when}_{cam}.png")


def contact_frame(sc, folder, kmh, after_ms):
    """Frame index 'after_ms' after the impact, from the result's capture start (older results: a 0.6 s lead)."""
    res = json.loads((ROOT / "sim" / "cache" / sc / folder / f"{sc}_{kmh}kmh_result.json").read_text(encoding="utf-8"))
    fps = res.get("capture_fps", 60)
    lead = res["impact_time_s"] - res["capture_start_s"] if res.get("capture_start_s", -1) >= 0 else 0.6
    return int(round((lead + after_ms / 1000.0) * fps))


def series_sheet(date):
    rows = []
    for cam, pick, title in (("front34", lambda n: n - 1, "final state (three-quarter, left rear)"),
                             ("side", None, "50 ms after the contact (side)")):
        tiles = []
        for sc, folder, kmh in SERIES:
            d = ROOT / "sim" / "cache" / sc / folder / "frames"
            frames = sorted(d.glob(f"{cam}_*.jpg"))
            if not frames:
                continue
            k = pick(len(frames)) if pick else min(len(frames) - 1, contact_frame(sc, folder, kmh, 50))
            im = Image.open(frames[k]).convert("RGB")
            w, h = im.size
            im = im.crop((int(w * 0.18), int(h * 0.12), int(w * 0.86), int(h * 0.88))).resize((640, 358))
            ImageDraw.Draw(im).text((12, 8), f"{kmh} km/h", font=font(30), fill=(20, 20, 20))
            tiles.append(im)
        rows.append((title, tiles))
    W = 640 * 3
    H = sum(48 + 358 * ((len(t) + 2) // 3) for _, t in rows)
    sheet = Image.new("RGB", (W, H), (240, 240, 240))
    y = 0
    dr = ImageDraw.Draw(sheet)
    for title, tiles in rows:
        dr.text((12, y + 8), f"S1 / S8 speed series: {title}", font=font(28), fill=(0, 0, 0))
        y += 48
        for k, t in enumerate(tiles):
            sheet.paste(t, ((k % 3) * 640, y + (k // 3) * 358))
        y += 358 * ((len(tiles) + 2) // 3)
    out = OUT / f"{date}_P4_speed_series.jpg"
    sheet.save(out, quality=90)
    print(out.name, sheet.size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-10-14")
    ns = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("tmp_*"):
        old.unlink()
    for sc, folder, kmh, fin, fout, label in RUNS:
        grid_video(sc, folder, kmh, fin, fout, label, ns.date)
        if not folder.endswith("slowmo"):
            stills(sc, folder, kmh, ns.date)
    series_sheet(ns.date)


if __name__ == "__main__":
    main()
