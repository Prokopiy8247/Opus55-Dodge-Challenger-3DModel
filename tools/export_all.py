"""One-command re-export of the visual car for Unity (brief 7).

Runs Blender in the background on the latest working file 3DDodgeChallenger_vNNN.blend (never the original
3DDodgeChallenger.blend) and calls hcar.export_unity.export_all: one FBX per part group of the skeleton (the parts listed
in sim/vehicle/hellcat/geometry.json), parts.json, materials.json and the textures, written to
Unity/HellcatSandbox/Assets/Game/Vehicles/Hellcat/Export. Then bind in Unity: Tools/Hellcat/Import Car, or in batch
-executeMethod Hellcat.EditorTools.Car.CarImporter.ImportBatch (tools/unity/run_unity_batch.ps1).

Usage: python tools/export_all.py [--blend <file.blend>] [--only body,radiator] [--blender W:\\Blender\\blender.exe]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = "3DDodgeChallenger.blend"
ENTRY = ROOT / "tools" / "blender" / "export_entry.py"


def latest_blend():
    files = sorted(ROOT.glob("3DDodgeChallenger_v[0-9][0-9][0-9].blend"),
                   key=lambda p: int(re.search(r"_v(\d+)\.blend$", p.name).group(1)))
    if not files:
        sys.exit("no 3DDodgeChallenger_vNNN.blend in the project root")
    return files[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", type=Path, default=None)
    ap.add_argument("--only", default="", help="comma-separated FBX groups (default: all)")
    ap.add_argument("--blender", default=r"W:\Blender\blender.exe")
    ns = ap.parse_args()
    blend = ns.blend or latest_blend()
    if blend.name == ORIGINAL:
        sys.exit("refusing to work on the original model file")
    # factory startup: no user add-ons (the MCP add-on would open its socket server); the FBX exporter is built in
    cmd = [ns.blender, "--background", "--factory-startup", str(blend), "--python", str(ENTRY), "--", ns.only]
    print("[export_all]", " ".join(f'"{c}"' if " " in c else c for c in cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    result = None
    for line in proc.stdout.splitlines():
        if line.startswith("[export_entry] RESULT "):
            result = json.loads(line[len("[export_entry] RESULT "):])
        elif line.startswith("[export_entry]") or "Error" in line or "Traceback" in line:
            print(line)
    if proc.returncode != 0 or result is None:
        print(proc.stdout[-4000:])
        print(proc.stderr[-4000:])
        sys.exit(f"blender failed (exit {proc.returncode})")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
