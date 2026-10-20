"""One-off patch (P3, D-030): add the designed braces (tools/blender/hcar/hskel_braces.json) in hskel.build."""
import sys
from pathlib import Path

hs = Path(sys.argv[1])
s = hs.read_text(encoding="utf-8")
a = '''    register_wheels(B, st)
    # underbody collision: floor quads between sills and tunnel (outward = down)'''
b = '''    register_wheels(B, st)
    add_braces(B)
    # underbody collision: floor quads between sills and tunnel (outward = down)'''
if a not in s:
    sys.exit("build anchor not found")
s = s.replace(a, b)
a = '''def build():'''
b = '''BRACES = os.path.join(os.path.dirname(__file__), "hskel_braces.json")


def add_braces(B):
    """Bracing designed by tools/skeleton/brace_design.py (compliance sensitivity, D-030): the shear webs of the
    inner fenders, wheel houses, quarter inner panels and parcel shelf, and cross members, as node-name pairs."""
    import json
    if not os.path.exists(BRACES):
        return 0
    n = 0
    for a, b in json.load(open(BRACES, encoding="utf-8")):
        if a in B.tags and b in B.tags:
            B.beam(B.tags[a], B.tags[b], "brace")
            n += 1
    return n


def build():'''
s = s.replace(a, b, 1)
hs.write_text(s, encoding="utf-8", newline="\n")
pp = Path(sys.argv[2])
t = pp.read_text(encoding="utf-8")
anchor = '    // ---- skins (steel / aluminium), plastic covers, glass'
if '"name": "brace"' not in t:
    t = t.replace(anchor, '    // designed bracing (tools/skeleton/brace_design.py, D-030): elastic in driving, yields early in a crash\n'
                          '    { "name": "brace",         "spring": 600000,  "damp": 25,  "deform": 15000, "hardening": 60000, "deformCap": 45000, "strength": 90000 },\n' + anchor, 1)
pp.write_text(t, encoding="utf-8", newline="\n")
print("patched")
