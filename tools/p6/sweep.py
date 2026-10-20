"""P6 sensitivity sweep (brief 15.5): the five most influential parameters at x0.8 and x1.2 around the tuned set, each run
through the test-map player with -vehicleParams (a modified copy of params.json, the geometry unchanged):

  rail_deform   front rail deform threshold        rail_f / rail_f_brace "deform"
  rail_strength front rail strength (break force)  rail_f / rail_f_brace "strength"
  clip_strength bumper fascia clip strength        clip "strength"
  tire_pressure tyre gauge pressure                pressure "gaugeScale" (241 kPa in geometry.json)
  damper_rate   damper rates (bump and rebound)    damper_f / damper_r damp, dampRebound, dampFast, dampReboundFast

Scenarios: S1 at 56 km/h (the NHTSA full-width frontal: crush, pulse, peak, plastic work) for all five, S5 at 80 km/h (the
ramp landing: landing pulse, underbody contact, damage) for the tyre pressure and the dampers.

Usage:  tools/.venv/Scripts/python.exe tools/p6/sweep.py [--only rail_deform,...] [--scenarios S1,S5] [--collect]
Output: sim/cache/sweep/<scenario>/<param>_<scale>/ (player results), docs/p6/sensitivity.json / .csv / .md,
        rows in docs/tuning_log.csv
"""
import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARAMS = ROOT / "sim/vehicle/hellcat/params.json"
EXE = ROOT / "Builds/TestMap/HellcatTestMap.exe"
OUT = ROOT / "sim/cache/sweep"
SCALES = (0.8, 1.2)

# parameter -> list of (material or section, keys)
SWEEP = {
    "rail_deform": [("rail_f", ["deform"]), ("rail_f_brace", ["deform"])],
    "rail_strength": [("rail_f", ["strength"]), ("rail_f_brace", ["strength"])],
    "clip_strength": [("clip", ["strength"])],
    "tire_pressure": [("@pressure", ["gaugeScale"])],
    "damper_rate": [("damper_f", ["damp", "dampRebound", "dampFast", "dampReboundFast"]),
                    ("damper_r", ["damp", "dampRebound", "dampFast", "dampReboundFast"])],
}
SCENARIOS = {"S1": (56, list(SWEEP)), "S5": (80, ["tire_pressure", "damper_rate"])}


def scaled_params(param, scale):
    """params.json text with the parameter's values scaled (comments kept)."""
    text = PARAMS.read_text(encoding="utf-8")
    for target, keys in SWEEP[param]:
        if target == "@pressure":
            if '"pressure":' in text:
                raise SystemExit("params.json already has a pressure section: extend the sweep script")
            # a pressure section with only the gauge scale (the other fields keep their defaults)
            text = text.replace('  "surfaces": [', f'  "pressure": {{ "gaugeScale": {scale:g} }},\n  "surfaces": [', 1)
            continue
        pat = re.compile(r'(\{\s*"name":\s*"' + re.escape(target) + r'"[^}]*\})')
        m = pat.search(text)
        if not m:
            raise SystemExit(f"material {target} not found")
        line = m.group(1)
        for k in keys:
            km = re.search(r'"' + k + r'":\s*(-?[\d.eE+]+)', line)
            if not km:
                raise SystemExit(f"{target}.{k} not found")
            v = float(km.group(1)) * scale
            line = line[:km.start(1)] + f"{v:.6g}" + line[km.end(1):]
        text = text[:m.start(1)] + line + text[m.end(1):]
    return text


def run(scenario, kmh, tag, params_file, log):
    out = OUT / scenario / tag
    out.mkdir(parents=True, exist_ok=True)
    args = [str(EXE), "-logFile", str(log), "-screen-width", "1280", "-screen-height", "720",
            "-scenario", scenario, "-targetKmh", str(kmh), "-out", str(out), "-capture", "0", "-replayCheck", "0"]
    if params_file:
        args += ["-vehicleParams", str(params_file)]
    t0 = time.time()
    subprocess.run(args, timeout=1800, check=False)
    res = out / f"{scenario}_{kmh}kmh_result.json"
    if not res.exists():
        print(f"{scenario} {tag}: NO RESULT ({time.time() - t0:.0f} s)")
        return None
    r = json.loads(res.read_text(encoding="utf-8"))
    print(f"{scenario} {tag}: broken {r['broken_beams']} plastic {r['energy_J']['plastic'] / 1000:.1f} kJ "
          f"crush {r.get('dynamic_crush_m')} / {r.get('residual_crush_m')} ({time.time() - t0:.0f} s)")
    return r


def pulse_peak(folder, scenario, kmh):
    """Peak CFC 60 deceleration along the lane and the resultant (g), and the landing's vertical peak, from the pulse."""
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from gate_p6 import pulse_metrics  # noqa: E402
    p = folder / f"{scenario}_{kmh}kmh_pulse.csv"
    return pulse_metrics(p) if p.exists() else None


def metrics(r, folder, scenario, kmh):
    pm = pulse_peak(folder, scenario, kmh) or {}
    return {
        "entry_kmh": r.get("entry_speed_kmh"), "dynamic_crush_m": r.get("dynamic_crush_m"), "residual_crush_m": r.get("residual_crush_m"),
        "pulse_ms": r.get("pulse_duration_ms"), "peak_cfc60_g": pm.get("peak_long_g"), "peak_resultant_cfc60_g": pm.get("peak_res_g"),
        "peak_vertical_cfc60_g": pm.get("landing_peak_vert_g", pm.get("peak_vert_g")), "plastic_kJ": round(r["energy_J"]["plastic"] / 1000, 2),
        "broken_beams": r["broken_beams"], "detached": "+".join(r["detached_parts"]), "max_deformation_m": r.get("max_deformation_m"),
        "intrusion_max_cm": max((r.get("intrusion_cm") or {"-": 0}).values()), "underbody_contact": r.get("underbody_contact_nodes_max"),
        "rim_contact": r.get("rim_contact_nodes_max"), "airborne_s": r.get("airborne_s"), "landing_vy": r.get("landing_vertical_speed_mps"),
        "stability_maxS": r.get("stability_maxS"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--scenarios", default="S1,S5")
    ap.add_argument("--collect", action="store_true", help="only collect existing results")
    ns = ap.parse_args()
    only = [s for s in ns.only.split(",") if s]
    logs = ROOT / "docs/p6/logs/sweep"
    logs.mkdir(parents=True, exist_ok=True)
    pdir = OUT / "params"
    pdir.mkdir(parents=True, exist_ok=True)
    table = []
    for sc in [s for s in ns.scenarios.split(",") if s]:
        kmh, params = SCENARIOS[sc]
        base_dir = OUT / sc / "baseline"
        if not ns.collect:
            # the baseline reads the same file as the variants (sim/vehicle/hellcat/params.json now, not the build's copy)
            pb = pdir / "params_baseline.json"
            pb.write_text(PARAMS.read_text(encoding="utf-8"), encoding="utf-8")
            run(sc, kmh, "baseline", pb, logs / f"{sc}_baseline.log")
        base_json = base_dir / f"{sc}_{kmh}kmh_result.json"
        if not base_json.exists():
            continue
        base = metrics(json.loads(base_json.read_text(encoding="utf-8")), base_dir, sc, kmh)
        table.append({"scenario": sc, "kmh": kmh, "parameter": "baseline", "scale": 1.0, **base})
        for prm in params:
            if only and prm not in only:
                continue
            for s in SCALES:
                tag = f"{prm}_{s:g}"
                pf = pdir / f"params_{tag}.json"
                pf.write_text(scaled_params(prm, s), encoding="utf-8")
                if not ns.collect:
                    run(sc, kmh, tag, pf, logs / f"{sc}_{tag}.log")
                rj = OUT / sc / tag / f"{sc}_{kmh}kmh_result.json"
                if rj.exists():
                    table.append({"scenario": sc, "kmh": kmh, "parameter": prm, "scale": s,
                                  **metrics(json.loads(rj.read_text(encoding="utf-8")), rj.parent, sc, kmh)})
    write(table)


def write(table):
    d = ROOT / "docs/p6"
    d.mkdir(parents=True, exist_ok=True)
    (d / "sensitivity.json").write_text(json.dumps(table, indent=1), encoding="utf-8")
    if not table:
        return
    keys = list(table[0].keys())
    with (d / "sensitivity.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(table)
    # effects: relative change of each metric from the baseline per +-20 %
    md = ["# P6 sensitivity sweep (brief 15.5)", "",
          "Each parameter at x0.8 and x1.2 of the tuned value, everything else unchanged; S1 at 56 km/h (NHTSA full-width "
          "frontal), S5 at 80 km/h (ramp landing). Values from the run results and the pulses (CFC 60, tools/gate_p6.py).", ""]
    for sc in sorted({r["scenario"] for r in table}):
        rows = [r for r in table if r["scenario"] == sc]
        cols = ["dynamic_crush_m", "residual_crush_m", "pulse_ms", "peak_cfc60_g", "plastic_kJ", "broken_beams", "max_deformation_m",
                "intrusion_max_cm"] if sc == "S1" else \
               ["airborne_s", "landing_vy", "peak_vertical_cfc60_g", "underbody_contact", "rim_contact", "plastic_kJ", "broken_beams", "max_deformation_m"]
        md += [f"## {sc} at {rows[0]['kmh']} km/h", "", "| parameter | scale | " + " | ".join(cols) + " |",
               "|---|---|" + "---|" * len(cols)]
        for r in rows:
            md.append(f"| {r['parameter']} | {r['scale']:g} | " + " | ".join(fmt(r.get(c)) for c in cols) + " |")
        md.append("")
    (d / "sensitivity.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote docs/p6/sensitivity.json / .csv / .md")


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3g}"
    return str(v)


if __name__ == "__main__":
    main()
