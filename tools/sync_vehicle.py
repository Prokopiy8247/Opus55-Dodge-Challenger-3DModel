"""Copies sim/vehicle/<name>/*.json and *.bin into the Unity project's StreamingAssets/Vehicles/<name>/
(same rule as the editor menu Tools/Hellcat/Sync Vehicle Data, VehicleAssetSync.cs), so parameter changes
reach Unity without regenerating the skeleton or opening the editor.

Usage: tools/.venv/Scripts/python.exe tools/sync_vehicle.py [name ...]     (default: every vehicle)
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sim/vehicle"
DST = ROOT / "Unity/HellcatSandbox/Assets/StreamingAssets/Vehicles"


def main():
    names = sys.argv[1:] or sorted(d.name for d in SRC.iterdir() if d.is_dir())
    for name in names:
        target = DST / name
        target.mkdir(parents=True, exist_ok=True)
        for f in sorted((SRC / name).iterdir()):
            if f.suffix.lower() in (".json", ".bin"):
                shutil.copyfile(f, target / f.name)
                print(f"{f.relative_to(ROOT)} -> {(target / f.name).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
