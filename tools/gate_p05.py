"""P0.5 quality gate (vertical slice): Blender export -> Unity solver -> drive -> wall crash -> captures.

Usage:  tools/.venv/Scripts/python.exe tools/gate_p05.py
Output: docs/gates/gate_p05.json and docs/gates/gate_p05.md
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_SHA256 = "AA42CA0C78B5BE03BCDE065E7861075C6BADFBBFD7FDDEF8DF9B2D74F9CFAE68"
results = []


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def sha256(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest().upper()


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8-sig"))


check("original .blend untouched", "PASS" if sha256(ROOT / "3DDodgeChallenger.blend") == ORIGINAL_SHA256 else "FAIL",
      "SHA-256 compared with the P0 fingerprint")

geo = load("sim/vehicle/boxcar/geometry.json")
n_nodes, n_beams = len(geo["nodes"]), len(geo["beams"])
mass = sum(n["m"] for n in geo["nodes"])
check("box car skeleton exported from Blender (30-60 nodes, 4 wheels)",
      "PASS" if 30 <= n_nodes <= 60 and len(geo["wheels"]) == 4 else "FAIL",
      f"{n_nodes} nodes, {n_beams} beams, {len(geo['wheels'])} wheels, {mass:.0f} kg, hydros {geo['hydros']}")
unity_geo = ROOT / "Unity/HellcatSandbox/Assets/StreamingAssets/Vehicles/boxcar/geometry.json"
check("exported geometry reaches the Unity project", "PASS" if unity_geo.exists() and sha256(unity_geo) == sha256(ROOT / "sim/vehicle/boxcar/geometry.json") else "FAIL",
      str(unity_geo.relative_to(ROOT)))
exe = ROOT / "Builds/P05_Slice/HellcatSlice.exe"
check("standalone slice build exists", "PASS" if exe.exists() else "FAIL", str(exe.relative_to(ROOT)))

r50 = load("sim/cache/P05/wall_50/wall_50kmh_result.json")
r50b = load("sim/cache/P05/wall_50_timing/wall_50kmh_result.json")
r80 = load("sim/cache/P05/wall_80/wall_80kmh_result.json")
v = r50["speed_at_impact_kmh"]
check("driven on the plane to the target speed (50 km/h +/- 10 %)", "PASS" if abs(v - 50) <= 5 else "FAIL", f"entry speed {v:.1f} km/h")
check("crash: plastic deformation, no NaN, settles", "PASS" if r50["crush_m"] > 0.1 and r50["plastic_beams"] > 0 and r50["nonfinite_nodes"] == 0 and r50["max_node_speed"] < 0.5 else "FAIL",
      f"crush {r50['crush_m']:.3f} m, {r50['plastic_beams']} plastic beams, plastic work {r50['energy_J']['plastic'] / 1000:.1f} kJ, "
      f"peak {r50['peak_decel_g_frame_avg']:.1f} g (frame avg), max node speed after 3 s {r50['max_node_speed']:.2f} m/s")
check("damage grows with speed", "PASS" if r80["crush_m"] > r50["crush_m"] and r80["energy_J"]["plastic"] > r50["energy_J"]["plastic"] else "FAIL",
      f"{r50['speed_at_impact_kmh']:.1f} km/h: {r50['crush_m']:.3f} m / {r50['energy_J']['plastic'] / 1000:.0f} kJ  vs  "
      f"{r80['speed_at_impact_kmh']:.1f} km/h: {r80['crush_m']:.3f} m / {r80['energy_J']['plastic'] / 1000:.0f} kJ")
ts_a = (ROOT / "sim/cache/P05/wall_50/wall_50kmh_timeseries.csv").read_bytes()
ts_b = (ROOT / "sim/cache/P05/wall_50_timing/wall_50kmh_timeseries.csv").read_bytes()
check("deterministic re-run (time series byte-identical, capture on vs off)", "PASS" if ts_a == ts_b else "FAIL",
      f"{len(ts_a)} bytes, sha256 {hashlib.sha256(ts_a).hexdigest()[:16]}")
check("stability report (S < 2 hard limit)", "PASS" if r50["stability_errors"] == 0 else "FAIL", f"max S {r50['stability_maxS']}")
check("physics cost of the slice", "PASS" if r50b["physics_us_per_substep"] < 50 else "WARN",
      f"{r50b['physics_us_per_substep']:.1f} us/substep, {r50b['physics_ms_per_sim_second']:.1f} ms per simulated second")
smoke = (ROOT / "docs/p05/logs/06_live_smoke.log").read_text(encoding="utf-8", errors="replace")
m = re.search(r"physics (\d+) Hz x(\d+[.,]\d+)", smoke)
rt = float(m.group(2).replace(",", ".")) if m else 0.0
check("windowed live-drive mode runs in real time (2000 Hz)", "PASS" if m and rt >= 0.98 and "Exception" not in smoke else "FAIL",
      m.group(0) if m else "no timing line")
videos = sorted((ROOT / "docs/video_assets/P05").glob("*.mp4"))
stills = sorted((ROOT / "docs/video_assets/P05").glob("*.png"))
check("video assets (MP4 chase + side, slow motion, stills)", "PASS" if len(videos) >= 4 and stills else "FAIL",
      ", ".join(p.name for p in videos + stills))

failed = sum(r["status"] == "FAIL" for r in results)
warned = sum(r["status"] == "WARN" for r in results)
out = ROOT / "docs/gates"
out.mkdir(parents=True, exist_ok=True)
(out / "gate_p05.json").write_text(json.dumps({"gate": "P0.5", "pass": failed == 0, "fail": failed, "warn": warned, "checks": results}, indent=2), encoding="utf-8")
lines = ["# Gate P0.5", "", f"Result: **{'PASS' if failed == 0 else 'FAIL'}** ({failed} FAIL, {warned} WARN, {len(results)} checks)", "",
         "| # | Check | Status | Detail |", "|---|---|---|---|"]
lines += [f"| {i} | {r['check']} | {r['status']} | {r['detail'].replace('|', '/')} |" for i, r in enumerate(results, 1)]
(out / "gate_p05.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
for r in results:
    print(f"{r['status']:4}  {r['check']}  --  {r['detail']}")
print(f"P0.5 gate: {'PASS' if failed == 0 else 'FAIL'} ({failed} fail, {warned} warn)")
sys.exit(1 if failed else 0)
