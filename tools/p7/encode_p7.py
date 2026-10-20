"""Encodes the P7 capture (HellcatSandbox.exe -scenario showcase at 2560x1440, docs/p7/capture/frames/f_*.jpg) into
docs/video_assets/P7/<date>_P7_showcase_1440p60.mp4 (H.264, 60 fps, CRF 18, faststart), probes the result with ffprobe
(docs/p7/capture/capture.json for the gate) and writes a contact sheet of 8 frames next to the video.

Usage: tools/.venv/Scripts/python.exe tools/p7/encode_p7.py [--date 2026-10-15]
"""
import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / "docs" / "p7" / "capture"
OUT = ROOT / "docs" / "video_assets" / "P7"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-10-15")
    ns = ap.parse_args()
    frames = sorted((CAP / "frames").glob("f_*.jpg"))
    if not frames:
        raise SystemExit(f"no frames in {CAP / 'frames'}")
    w, h = Image.open(frames[0]).size
    OUT.mkdir(parents=True, exist_ok=True)
    mp4 = OUT / f"{ns.date}_P7_showcase_1440p60.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "60", "-i", str(CAP / "frames" / "f_%05d.jpg"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)], check=True)
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                       "stream=width,height,r_frame_rate,nb_frames,codec_name:format=duration,size", "-of", "json", str(mp4)],
                                      check=True, capture_output=True, text=True).stdout)
    st = probe["streams"][0]
    num, den = (int(x) for x in st["r_frame_rate"].split("/"))
    info = {"video": str(mp4.relative_to(ROOT)).replace("\\", "/"), "frames_captured": len(frames), "frame_size": [w, h],
            "width": st["width"], "height": st["height"], "fps": num / den, "codec": st["codec_name"],
            "frames": int(st.get("nb_frames", 0) or 0), "duration_s": float(probe["format"]["duration"]),
            "bytes": int(probe["format"]["size"])}
    (CAP / "capture.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    # contact sheet: 8 frames spread over the capture, 640 px wide each
    step = max(1, len(frames) // 8)
    picks = frames[step // 2::step][:8]
    tiles = [Image.open(f).convert("RGB").resize((640, 360), Image.LANCZOS) for f in picks]
    sheet = Image.new("RGB", (640 * 4, 360 * ((len(tiles) + 3) // 4)), (20, 20, 20))
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % 4) * 640, (k // 4) * 360))
    sheet.save(OUT / f"{ns.date}_P7_showcase_sheet.jpg", quality=90)
    print(json.dumps(info))


if __name__ == "__main__":
    main()
