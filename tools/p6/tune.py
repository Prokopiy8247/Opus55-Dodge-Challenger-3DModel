"""P6 tuning runs (brief 15): a candidate change of params.json (material fields scaled or set) run through the test-map
player with -vehicleParams on chosen scenarios and speeds, no captures; one summary line per run, results in
sim/cache/tune/<tag>/<scenario>_<kmh>/. Candidates are named in CANDIDATES below.

Usage:  tools/.venv/Scripts/python.exe tools/p6/tune.py <candidate> [S1:30 S1:50 S5:80 ...]
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARAMS = ROOT / "sim/vehicle/hellcat/params.json"
EXE = ROOT / "Builds/TestMap/HellcatTestMap.exe"

HOOD = ('{{ "part": "hood", "materials": ["panel", "panel_brace", "panel_inner", "panel_link"], "min": [-1.0, 0.0, 1.93], '
        '"max": [1.0, 2.0, 2.40], "deformScale": {s}, "hardeningScale": {s}, "capScale": {s} }}')

# candidate -> {material: {field: value}} (absolute values; None removes the field)
CANDIDATES = {
    "base": {},
    # closure stops survive a lid lifting 2x their length (hard landings, D-034); the headlamp brackets bend before they tear
    "stops_lamps": {"stop_closure": {"longBound": 2.0},
                    "lamp_mount": {"deform": 1500, "hardening": 6000, "deformCap": 4000, "strength": 3000}},
    "stops_lamps2": {"stop_closure": {"longBound": 2.0},
                     "lamp_mount": {"deform": 2000, "hardening": 8000, "deformCap": 6000, "strength": 4500}},
    # + hood crease initiators: the front strip (rows 5-7 of the skin, the inner frame's front bay) yields early, so the
    # hood folds at its leading edge instead of arching as one panel
    "crease30": {"stop_closure": {"longBound": 2.0},
                 "lamp_mount": {"deform": 1500, "hardening": 6000, "deformCap": 4000, "strength": 3000},
                 "@zones": HOOD.format(s=0.3)},
    "crease20": {"stop_closure": {"longBound": 2.0},
                 "lamp_mount": {"deform": 1500, "hardening": 6000, "deformCap": 4000, "strength": 3000},
                 "@zones": HOOD.format(s=0.2)},
    "crease10": {"stop_closure": {"longBound": 2.0},
                 "lamp_mount": {"deform": 1500, "hardening": 6000, "deformCap": 4000, "strength": 3000},
                 "@zones": HOOD.format(s=0.1)},
    # frontal calibration against NHTSA's 2013 Challenger (D-091), on top of the adopted P6 parameters: the front crush
    # characteristic (yield, hardening, cap) of the rails, their braces and the crash cans scaled
    "front80": {"rail_f": {"deform": 33600, "hardening": 160000, "deformCap": 88000},
                "rail_f_brace": {"deform": 24000, "hardening": 120000, "deformCap": 64000},
                "crush_can": {"deform": 17600, "hardening": 72000, "deformCap": 44000}},
    "front70": {"rail_f": {"deform": 29400, "hardening": 140000, "deformCap": 77000},
                "rail_f_brace": {"deform": 21000, "hardening": 105000, "deformCap": 56000},
                "crush_can": {"deform": 15400, "hardening": 63000, "deformCap": 38500}},
}


def edited_params(cand):
    text = PARAMS.read_text(encoding="utf-8")
    zones = CANDIDATES[cand].get("@zones")
    if zones:
        text = text.replace('  "surfaces": [', '  "materialZones": [\n    ' + zones + '\n  ],\n  "surfaces": [', 1)
    for mat, fields in CANDIDATES[cand].items():
        if mat.startswith("@"):
            continue
        pat = re.compile(r'(\{\s*"name":\s*"' + re.escape(mat) + r'"[^}]*\})')
        m = pat.search(text)
        if not m:
            raise SystemExit(f"material {mat} not found")
        line = m.group(1)
        for k, v in fields.items():
            km = re.search(r',\s*"' + k + r'":\s*-?[\d.eE+]+', line)
            if v is None:
                if km:
                    line = line[:km.start()] + line[km.end():]
                continue
            if km:
                line = line[:km.start()] + f', "{k}": {v:g}' + line[km.end():]
            else:
                line = line[:-1].rstrip() + f', "{k}": {v:g} }}'
        text = text[:m.start(1)] + line + text[m.end(1):]
    return text


def main():
    cand = sys.argv[1]
    runs = sys.argv[2:] or ["S1:30", "S1:50"]
    out = ROOT / "sim/cache/tune" / cand
    out.mkdir(parents=True, exist_ok=True)
    pf = out / "params.json"
    pf.write_text(edited_params(cand), encoding="utf-8")
    for r in runs:
        sc, kmh = r.split(":")
        d = out / f"{sc}_{kmh}"
        d.mkdir(parents=True, exist_ok=True)
        args = [str(EXE), "-logFile", str(d / "player.log"), "-screen-width", "1280", "-screen-height", "720", "-scenario", sc,
                "-targetKmh", kmh, "-out", str(d), "-capture", "0", "-replayCheck", "0", "-vehicleParams", str(pf)]
        t0 = time.time()
        subprocess.run(args, timeout=1800, check=False)
        rj = d / f"{sc}_{kmh}kmh_result.json"
        if not rj.exists():
            print(f"{cand} {sc} {kmh}: NO RESULT")
            continue
        j = json.loads(rj.read_text(encoding="utf-8"))
        print(f"{cand} {sc} {kmh}: entry {j.get('entry_speed_kmh')} crush {j.get('dynamic_crush_m')}/{j.get('residual_crush_m')} "
              f"deform {j.get('max_deformation_m')} broken {j.get('broken_beams')} ({j.get('broken_by_material')}) stops "
              f"{j.get('closure_stops_released')} plastic {j['energy_J']['plastic'] / 1000:.1f} kJ det {'+'.join(j['detached_parts']) or '-'} "
              f"hood {j.get('hood_rise_m')} air {j.get('airborne_s')} S {j.get('stability_maxS')} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
