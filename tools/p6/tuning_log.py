"""Adds P6 rows to docs/tuning_log.csv (brief 15.4): run id, parameter changes and the crash metrics they gave. The
crash columns are appended to the header once (older rows get empty cells). Rows are given in ROWS (id, changes, result
JSON of the run that measured them, notes); an id already in the log is replaced.

Usage: tools/.venv/Scripts/python.exe tools/p6/tuning_log.py
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from gate_p6 import pulse_metrics  # noqa: E402

LOG = ROOT / "docs/tuning_log.csv"
CRASH = ["scenario", "kmh", "crush_dyn_m", "crush_res_m", "peak_cfc60_g", "pulse_ms", "plastic_kJ", "broken_beams", "detached",
         "max_deformation_m", "hood_rise_m"]
# (run id, changes, result json relative to ROOT, notes) - filled as the P6 tuning proceeds
T = "sim/cache/tune"
ROWS = [
    ("P6-001a", "P6 start: P5 parameters, scenario on the test map", f"{T}/base_p6/S1_50/S1_50kmh_result.json",
     "both headlamps off (18 lamp_mount beams), hood arch 0.47 m, 18 closure stops released at the first contact"),
    ("P6-001b", "P6 start: P5 parameters", f"{T}/base_p6/S5_80/S5_80kmh_result.json",
     "ramp landing tore both headlamps off and released 10 closure stops (the D-034 open point)"),
    ("P6-001c", "P6 start: P5 parameters", f"{T}/base_p6/S8_120/S8_120kmh_result.json", "reference for the severe end"),
    ("P6-002a", "stop_closure longBound 0.5 -> 2.0; lamp_mount ductile (deform 1500 N, hardening 6000 N/m, cap 4000 N, strength 1800 -> 3000 N)",
     f"{T}/stops_lamps/S1_30/S1_30kmh_result.json", "lamps stay on at 30 km/h; hood still arches 0.39 m"),
    ("P6-002b", "as P6-002a", f"{T}/stops_lamps/S1_50/S1_50kmh_result.json", "lamps stay on at 50 km/h"),
    ("P6-002c", "as P6-002a", f"{T}/stops_lamps/S5_80/S5_80kmh_result.json", "landing: no stop released, lamps on"),
    ("P6-003a", "+ hood crease zone (front strip, thresholds x0.3)", f"{T}/crease30/S1_30/S1_30kmh_result.json", "hood rise 0.39 -> 0.32 m"),
    ("P6-003b", "+ hood crease zone x0.3", f"{T}/crease30/S1_50/S1_50kmh_result.json", "hood rise 0.47 -> 0.37 m"),
    ("P6-003c", "+ hood crease zone x0.3", f"{T}/crease30/S8_120/S8_120kmh_result.json", "mirrors detach; lamps stay with the fascia"),
    ("P6-004a", "hood crease zone x0.2", f"{T}/crease20/S1_30/S1_30kmh_result.json", "hood rise 0.27 m"),
    ("P6-004b", "hood crease zone x0.2", f"{T}/crease20/S1_50/S1_50kmh_result.json", "hood rise 0.35 m"),
    ("P6-005a", "hood crease zone x0.1 (adopted, D-095)", f"{T}/crease10/S1_30/S1_30kmh_result.json", "hood rise 0.20 m: the front strip folds, no arch"),
    ("P6-005b", "hood crease zone x0.1 (adopted)", f"{T}/crease10/S1_50/S1_50kmh_result.json", "hood rise 0.32 m; crush unchanged"),
    ("P6-005c", "hood crease zone x0.1 (adopted)", f"{T}/crease10/S5_80/S5_80kmh_result.json", "landing unchanged (hood flex 0.09 m)"),
    ("P6-006a", "NHTSA calibration start: P6-005 parameters at 56 km/h", "sim/cache/sweep/S1/baseline/S1_56kmh_result.json",
     "static crush equivalent (residual + 149 mm fascia) 508 mm vs NHTSA 573-642 mm; wheelbase not shortened (reading -26 / +2 mm) vs NHTSA 155 / 149 mm shorter"),
    ("P6-006b", "front crush characteristic x0.8 (rail_f, rail_f_brace, crush_can: deform, hardening, deformCap)",
     f"{T}/front80/S1_56/S1_56kmh_result.json", "static crush equivalent 575 mm; cabin travel limited by the wheels at the wall"),
    ("P6-006c", "front crush characteristic x0.7 (adopted, D-096)", f"{T}/front70/S1_56/S1_56kmh_result.json",
     "static crush equivalent 615 mm vs NHTSA mean 608 mm; peak 52 g; rebound 4.0 m/s vs 2.7 (wheel / tyre path, open point)"),
    ("P7-001", "hood crease zone x0.3 (was x0.1; adopted, D-104): the T6 0.2 m drop and the O7 bump keep the strip elastic",
     "sim/cache/S1/kmh50/S1_50kmh_result.json", "final car, S1 at 50 km/h on the final build (sleeping debris, D-098)", "P7"),
    ("P7-001b", "as P7-001", "sim/cache/S1/kmh56/S1_56kmh_result.json", "final car at the NHTSA speed", "P7"),
]


def metrics(rj):
    r = json.loads((ROOT / rj).read_text(encoding="utf-8"))
    pc = (ROOT / rj).with_name((ROOT / rj).name.replace("_result.json", "_pulse.csv"))
    p = pulse_metrics(pc, r) if pc.exists() else {}
    return {"scenario": r["scenario"], "kmh": r["target_kmh"], "crush_dyn_m": r.get("dynamic_crush_m"), "crush_res_m": r.get("residual_crush_m"),
            "peak_cfc60_g": round(p["peak_long_g"], 1) if p.get("peak_long_g") is not None else "", "pulse_ms": p.get("pulse_ms", ""),
            "plastic_kJ": round(r["energy_J"]["plastic"] / 1000, 1), "broken_beams": r["broken_beams"],
            "detached": "+".join(r["detached_parts"]), "max_deformation_m": r.get("max_deformation_m"), "hood_rise_m": r.get("hood_rise_m")}


def main(rows=ROWS):
    old = list(csv.DictReader(open(LOG, encoding="utf-8")))
    head = list(old[0].keys()) if old else ["run_id", "date", "phase", "changes"]
    for c in CRASH:
        if c not in head:
            head.append(c)
    ids = {r[0] for r in rows}
    out = [r for r in old if r["run_id"] not in ids]
    for row in rows:
        rid, changes, rj, notes = row[:4]
        phase = row[4] if len(row) > 4 else "P6"
        m = metrics(rj) if rj else {}
        out.append({"run_id": rid, "date": "2026-10-15", "phase": phase, "changes": changes, "notes": notes, **m})
    with LOG.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=head, extrasaction="ignore")
        w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, "") for k in head})
    print(f"{len(rows)} P6 rows -> {LOG.relative_to(ROOT)} ({len(out)} rows)")


if __name__ == "__main__":
    main()
