"""Blender-side entry of tools/export_all.py (runs inside `blender --background <file> --python export_entry.py -- [only]`).

Imports the hcar package from tools/blender and calls hcar.export_unity.export_all; prints one RESULT line (JSON).
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from hcar import export_unity

    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = [g for g in (argv[0].split(",") if argv and argv[0] else []) if g]
    res = export_unity.export_all(only=only or None)
    print("[export_entry] RESULT " + json.dumps(res, default=str), flush=True)
except Exception:
    traceback.print_exc()
    sys.stdout.flush()
    sys.exit(1)
