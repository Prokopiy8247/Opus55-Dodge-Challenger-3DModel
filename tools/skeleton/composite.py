"""Composite the skeleton pass over the painted car (hcar.pshots.shots_blender outputs).

Usage: tools/.venv/Scripts/python.exe tools/skeleton/composite.py <folder> <prefix> [dim]
Writes <prefix>_<view>_overlay.png next to the inputs (car dimmed by `dim`, default 0.55).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def main():
    folder, prefix = Path(sys.argv[1]), sys.argv[2]
    dim = float(sys.argv[3]) if len(sys.argv) > 3 else 0.55
    for car in sorted(folder.glob(f"{prefix}_*_car.png")):
        view = car.name[len(prefix) + 1:-len("_car.png")]
        sk = folder / f"{prefix}_{view}_skel.png"
        if not sk.exists():
            continue
        a = np.asarray(Image.open(car).convert("RGB")).astype(float) * dim
        s = np.asarray(Image.open(sk).convert("RGBA")).astype(float)
        al = s[..., 3:4] / 255.0
        out = a * (1 - al) + s[..., :3] * al
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(folder / f"{prefix}_{view}_overlay.png")
        print(folder / f"{prefix}_{view}_overlay.png")


if __name__ == "__main__":
    main()
