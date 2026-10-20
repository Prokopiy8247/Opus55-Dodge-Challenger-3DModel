"""One-off (P4 close): updates docs/STATUS.md - header, latest working file, the P4 section with the run commands, the
plan and the phase log - from the P4 gate result."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
p = ROOT / "docs" / "STATUS.md"
s = p.read_text(encoding="utf-8")
g = json.loads((ROOT / "docs/gates/gate_p4.json").read_text(encoding="utf-8"))
g3b = json.loads((ROOT / "docs/gates/gate_p3b.json").read_text(encoding="utf-8"))
t12 = json.loads((ROOT / "docs/p3b/validation/dynamics_results.json").read_text(encoding="utf-8"))
off = next((c["value"] for t in t12["tests"] if t["id"] == "T12" for c in t["checks"] if "largest path offset" in c["name"]), float("nan"))
p3b_ok = bool(g3b.get("pass", False))
p3b_line = ("P3b PASS" + f" (T12 top-speed path offset {off:.3f} m, limit 0.5 m: marginal)" if p3b_ok else
            f"P3b FAIL on {g3b.get('fail', 1)} check (T12 top-speed path offset {off:.3f} m > 0.5 m)")
r50 = next(r for r in g["table"] if r["scenario"] == "S1" and r["target_kmh"] == 50)

head = f"""# STATUS (resume here after a context compaction or restart)

Last update: 2026-10-14. Phase **P4 done** (skinning in Unity + first scripted crash S1, gate G-Crash {g['verdict']}
{g['fails']} fail / {g['warns']} warn); next **P4b** (game layer: input, cameras, HUD, debug views, reset, record / replay). S1 at
50 km/h: crush {r50['dynamic_crush_m']:.2f} m dynamic / {r50['residual_crush_m']:.2f} m residual, {r50['peak_cfc60_g']:.0f} g CFC 60 peak, cabin intact
(`docs/P4_report.md`, `docs/gates/gate_p4.md`); gates P2 / P3 re-run PASS, {p3b_line}; a long-run directional
instability found in P4 (D-067): **fix it first in P4b**.
AUTONOMY MODE: work continuously P3 -> P7, no stops, no questions (brief top block).
"""
s = re.sub(r"\A# STATUS.*?AUTONOMY MODE:[^\n]*\n", head, s, count=1, flags=re.S)
s = s.replace("Latest working file: `3DDodgeChallenger_v010.blend` (P3b skeleton debug view).",
              "Latest working file: `3DDodgeChallenger_v011.blend` (P4: glass shards in Car_Visual/Glass_Shards).\n"
              "   The project Blender bridge (9876) may be down: `tools\\blender_bg.py <module:function> [--save note]` runs hcar\n"
              "   functions in a background Blender on the latest vNNN file (`tools\\export_all.py` the same for the FBX export).")

p4 = f"""## P4 skinning and crash S1 (decisions D-055 ... D-068)
- Export: `tools\\.venv\\Scripts\\python.exe tools\\export_all.py` (background Blender, latest vNNN) -> 32 FBX + parts.json +
  materials.json + textures in `Assets/Game/Vehicles/Hellcat/Export`; bind: `Tools/Hellcat/Import Car` or batch
  `-executeMethod Hellcat.EditorTools.Car.CarImporter.ImportBatch` (-> `*.skin.bytes`, `Hellcat.prefab`,
  `docs/p4/import_report.json`). Re-import after every skeleton change (the prefab carries the geometry hash).
- Runtime: `SoftBodyCarView` (node bones, best-fit frames D-062, glass swap D-064), `SkinningProbe` (CPU re-skinning for
  the metrics), `CarCrashScenario` + `CrashMetrics` (scene `P4_Crash`, player `Builds/P4_Crash/HellcatCrash.exe`,
  args `-scenario S1|S8 -targetKmh -out -capture 1 [-launch 1] [-breakGlass s] [-fps] [-lead] [-postImpact]`).
- Runs: `& tools\\p4\\crash_series.ps1 [-Import] [-Build] [-Runs 'S1:50:kmh50',...]` (results `sim/cache/<S>/<run>/`,
  frames ignored by git); after a skeleton / solver change `& tools\\p4\\pipeline.ps1 -Tag <t>` (import, build, series,
  X21, P3 and P3b suites). Diagnostics X21 (crash variants), X22 / X23 (per-step energy decomposition).
- Evidence: `tools\\.venv\\Scripts\\python.exe tools\\p4\\make_videos.py` (grid videos, stills, speed series sheet ->
  `docs/video_assets/P4/`); gate `tools\\gate_p4.py` (CFC 60 pulse, metrics table `docs/p4/crash_metrics.csv`, plots);
  report `tools\\p4\\make_p4_report.py` (then the gate again).
- Skeleton: closure joints in 3D (D-063, `tools/skeleton/closure_joints.py`, in gate P2), crush zones without
  rigidifiers (D-057), detachables (D-058); solver: hard contact (D-055), spring-back suppression (D-056), torsion-bar
  failure (D-060), pair impulse (D-061).
- **First task of P4b (D-067):** long-run straight-line stability. With the steering held at zero the car turns +4 deg in
  60 s at 150 km/h and spins at ~90 s; its onset sets T12's top-speed path offset ({off:.3f} m, limit 0.5).
  The road-wheel angles wander slowly (rear toe 0.13 deg in -> 0.6 deg out under drive). Tool: X24 (`-valTests X24`,
  `-valQuick 1` = 120 s runs). No plastic flow involved; present with the P3b data too. Lead suspect: the wind-up angle
  (D-036, `VehicleControlJob`) is integrated from the knuckle's and the body set's least-squares angular velocities
  (`windupAngle += (omegaKnuckle - omegaBody) dt`), so their noise and bias random-walk into a spurious wind-up torque
  (200 kN m/rad) that turns the multi-link knuckles (toe). Check: X24 with `windupK` 0; fix: the geometric angle of a
  knuckle node about the axle line against the body frame (bU) of the alignment element, less its spawn value.
- Open for P6: hood folds as one 0.4-0.6 m tent; body flex moves the closures a few cm in the pulse; S8 glass does not
  break by itself; physics 240-265 us per substep with the detachables' self-collision.

## Architecture (short)"""
s = s.replace("## Architecture (short)", p4, 1)

nxt_old = re.search(r"## Next \(plan\)\n.*?\n\n## Phase log", s, flags=re.S)
nxt = """## Next (plan)
- **P4b** game layer: input, cameras (chase, cockpit), HUD, debug views, reset / repair, record / replay (test 15),
  `controls.md`; measured physics Hz, display fps and input latency, 5-minute drive (gate G-Drive).
- P5 TestMap (O1-O9), P6 scenarios S1-S8 + tuning + sensitivity sweep (hood creases, glass strength, S8 cabin),
  P7 build + README + cost report.

## Phase log"""
s = s[:nxt_old.start()] + nxt + s[nxt_old.end():]
s = s.replace("| P4 | next | - | |",
              f"| P4 | done | {g['verdict']} ({g['fails']} fail, {g['warns']} warn) | docs/gates/gate_p4.md, docs/P4_report.md |\n| P4b | next | - | |")
p.write_text(s, encoding="utf-8")
print("STATUS updated")
