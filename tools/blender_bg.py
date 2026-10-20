"""Run hcar functions in a background Blender on the latest working file (never the original model).

Usage: python tools/blender_bg.py glass_shards:build [module:function ...] [--save "note"] [--blend <file>]
Opens the latest 3DDodgeChallenger_vNNN.blend (or --blend), calls the functions in order through
tools/blender/bg_call.py and, with --save, saves the result as the next version. Prints the functions' results.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from export_all import latest_blend, ORIGINAL  # noqa: E402

ENTRY = ROOT / "tools" / "blender" / "bg_call.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("calls", nargs="+")
    ap.add_argument("--save", default=None)
    ap.add_argument("--blend", type=Path, default=None)
    ap.add_argument("--blender", default=r"W:\Blender\blender.exe")
    ns = ap.parse_args()
    blend = ns.blend or latest_blend()
    if blend.name == ORIGINAL:
        sys.exit("refusing to work on the original model file")
    cmd = [ns.blender, "--background", "--factory-startup", str(blend), "--python", str(ENTRY), "--"] + ns.calls
    if ns.save:
        cmd += ["--save", ns.save]
    print("[blender_bg]", blend.name, ns.calls, flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    result = None
    for line in proc.stdout.splitlines():
        if line.startswith("[bg_call] RESULT "):
            result = json.loads(line[len("[bg_call] RESULT "):])
    if proc.returncode != 0 or result is None:
        print(proc.stdout[-5000:])
        print(proc.stderr[-3000:])
        sys.exit(f"blender failed (exit {proc.returncode})")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
