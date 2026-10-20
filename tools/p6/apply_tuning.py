"""Writes the P6 tuning into sim/vehicle/hellcat/params.json (comments kept): closure stops survive a lid lifting twice
their length, headlamp brackets bend before they tear, the hood's front strip is a crease zone (materialZones).

Usage: tools/.venv/Scripts/python.exe tools/p6/apply_tuning.py [--crease 0.3]
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARAMS = ROOT / "sim/vehicle/hellcat/params.json"


def set_fields(text, mat, fields, comment=None):
    pat = re.compile(r'(\n[ \t]*)(\{\s*"name":\s*"' + re.escape(mat) + r'"[^}]*\})')
    m = pat.search(text)
    if not m:
        raise SystemExit(f"material {mat} not found")
    line = m.group(2)
    for k, v in fields.items():
        km = re.search(r',\s*"' + k + r'":\s*-?[\d.eE+]+', line)
        if km:
            line = line[:km.start()] + f', "{k}": {v:g}' + line[km.end():]
        else:
            line = line[:-1].rstrip() + f', "{k}": {v:g} }}'
    indent = m.group(1)
    pre = ""
    if comment and comment.split("\n")[0] not in text:
        pre = "".join(f"{indent}// {c}" for c in comment.split("\n"))
    return text[:m.start()] + pre + indent + line + text[m.end():]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crease", type=float, default=0.3)
    ap.add_argument("--front", type=float, default=1.0, help="scale of the front crush characteristic (rails, braces, crash cans)")
    ns = ap.parse_args()
    t = PARAMS.read_text(encoding="utf-8")
    t = set_fields(t, "stop_closure", {"longBound": 2.0},
                   "P6 (D-095): the stops let go once a lid lifts twice their length (a buckled hood, a lid torn open), not half\n"
                   "(the hood and deck lid flexing 2-9 cm on a hard landing released them and the lids sank into their openings, D-034)")
    t = set_fields(t, "lamp_mount", {"deform": 1500, "hardening": 6000, "deformCap": 4000, "strength": 3000},
                   "P6 (D-095): headlamp brackets bend before they tear (1.5 kN yield, break at 3 kN after ~25 cm of stretch):\n"
                   "as brittle 1.8 kN mounts on the fascia both lamps fell off at 30 km/h and on the S5 landing")
    if ns.front != 1.0:
        f = ns.front
        note = (f"P6 (D-096): front crush characteristic x{f:g} (yield, hardening, cap) calibrated on NHTSA's 2013 Challenger NCAP\n"
                "test (56.4 km/h, static crush 573-642 mm, docs/p6/refs): x1.0 gave 508 mm, x0.8 575 mm, x0.7 615 mm")
        t = set_fields(t, "rail_f", {"deform": 42000 * f, "hardening": 200000 * f, "deformCap": 110000 * f}, note)
        t = set_fields(t, "rail_f_brace", {"deform": 30000 * f, "hardening": 150000 * f, "deformCap": 80000 * f})
        t = set_fields(t, "crush_can", {"deform": 22000 * f, "hardening": 90000 * f, "deformCap": 55000 * f})
    if '"materialZones"' not in t:
        zone = ('  // P6 (D-095): hood crease initiators - the front strip (skin rows 5-7, the inner frame\'s front bay) yields at\n'
                f'  // {ns.crease:g} x its materials\' thresholds, so the hood folds at its leading edge in a 30 km/h hit instead of\n'
                '  // arching up as one panel (0.39 m at 30 km/h before)\n'
                '  "materialZones": [\n'
                '    { "part": "hood", "materials": ["panel", "panel_brace", "panel_inner", "panel_link"], "min": [-1.0, 0.0, 1.93], '
                f'"max": [1.0, 2.0, 2.40], "deformScale": {ns.crease:g}, "hardeningScale": {ns.crease:g}, "capScale": {ns.crease:g} }}\n'
                '  ],\n')
        t = t.replace('  "surfaces": [', zone + '  "surfaces": [', 1)
    PARAMS.write_text(t, encoding="utf-8")
    print("params.json updated")


if __name__ == "__main__":
    main()
