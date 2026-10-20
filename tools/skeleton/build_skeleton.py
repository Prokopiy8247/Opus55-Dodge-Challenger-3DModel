"""Build the Hellcat physics skeleton without Blender (plain python) and print its statistics.

Usage: tools/.venv/Scripts/python.exe tools/skeleton/build_skeleton.py
Writes sim/vehicle/hellcat/geometry.json (+ the StreamingAssets copy) and skeleton_stats.json.
For the debug view in Blender call hcar.hskel:main through the bridge instead.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
from hcar import hskel  # noqa: E402


if __name__ == "__main__":
    res = hskel.main(viz=False)
    print(json.dumps({k: v for k, v in res.items() if k != "viz"}, indent=1))
