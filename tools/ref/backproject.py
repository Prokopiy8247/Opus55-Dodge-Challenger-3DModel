"""Back-project photo pixels through a fitted camera (docs/p1b/photo_cams/<key>.json) onto horizontal
planes z = const: 3D estimates of landmarks that are not in the model yet.

Usage: tools/.venv/Scripts/python.exe tools/ref/backproject.py cabin2 "name:u,v,z;name:u,v,z"
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main():
    key, spec = sys.argv[1], sys.argv[2]
    cj = json.loads((ROOT / "docs" / "p1b" / "photo_cams" / f"{key}.json").read_text(encoding="utf-8"))
    W, H = cj["size"]
    f = cj["focal_px"]
    M = np.array(cj["matrix_world"])
    C = M[:3, 3]
    Rb = M[:3, :3]                 # Blender camera axes (x right, y up, z back) -> world
    out = {}
    for item in spec.split(";"):
        name, rest = item.split(":")
        u, v, z = (float(t) for t in rest.split(","))
        d_cam = np.array([(u - W / 2) / f, -(v - H / 2) / f, -1.0])
        d = Rb @ d_cam
        t = (z - C[2]) / d[2]
        out[name] = [round(float(c), 3) for c in C + t * d]
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
