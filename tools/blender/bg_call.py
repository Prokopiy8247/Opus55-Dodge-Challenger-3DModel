"""Background Blender entry: call hcar functions on an opened working file and optionally save the next version.

    blender --background --factory-startup <vNNN.blend> --python tools/blender/bg_call.py -- <module:function> [...] [--save <note>]

Each module:function of the hcar package is called without arguments, in order; with --save the file is then saved as
the next 3DDodgeChallenger_vNNN.blend (never the original). Prints one RESULT line (JSON). Driven by tools/blender_bg.py.
"""
import importlib
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    note = None
    if "--save" in argv:
        k = argv.index("--save")
        note = argv[k + 1] if k + 1 < len(argv) else "background"
        argv = argv[:k] + argv[k + 2:]
    out = {}
    for spec in argv:
        mod, fn = spec.split(":")
        m = importlib.import_module(f"hcar.{mod}")
        out[spec] = getattr(m, fn)()
    if note is not None:
        from hcar import blend_util
        out["save"] = blend_util.save_version(note)
    print("[bg_call] RESULT " + json.dumps(out, default=str), flush=True)
except Exception:
    traceback.print_exc()
    sys.stdout.flush()
    sys.exit(1)
