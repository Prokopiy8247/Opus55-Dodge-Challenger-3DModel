"""P7: a copy of sim/vehicle/hellcat/params.json with the hood crease zone (materialZones, D-095) scaled by another factor -
for the T6 drop and the O7 bump checks of the crease strip (D-103).

Usage: tools/.venv/Scripts/python.exe tools/p7/crease_variant.py --scale 0.2 --out <file>
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--src", default=str(ROOT / "sim/vehicle/hellcat/params.json"))
    ns = ap.parse_args()
    s = Path(ns.src).read_text(encoding="utf-8")
    n = 0
    for key in ("deformScale", "hardeningScale", "capScale"):
        s, k = re.subn(r'("' + key + r'":\s*)[\d.]+', lambda m: m.group(1) + f"{ns.scale:g}", s)
        n += k
    if n == 0:
        raise SystemExit("no material zone scales found")
    Path(ns.out).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.out).write_text(s, encoding="utf-8")
    print(f"{n} scales set to {ns.scale:g} -> {ns.out}")


if __name__ == "__main__":
    main()
