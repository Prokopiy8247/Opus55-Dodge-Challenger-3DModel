"""One-off (P4b close): updates docs/STATUS.md - header, the P4b section with the run commands, the architecture line,
the plan and the phase log - from the P4b gate result and the drive test."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
p = ROOT / "docs" / "STATUS.md"
s = p.read_text(encoding="utf-8")
g = json.loads((ROOT / "docs/gates/gate_p4b.json").read_text(encoding="utf-8"))
d = json.loads((ROOT / "docs/p4b/drive/drive_test.json").read_text(encoding="utf-8"))
p4b_end = sys.argv[1] if len(sys.argv) > 1 else ""

head = f"""# STATUS (resume here after a context compaction or restart)

Last update: 2026-10-14. Phase **P4b done** (game layer, gate G-Drive {g['verdict']} {g['fails']} fail / {g['warns']} warn); next **P5**
(test map O1-O9). The Hellcat is drivable in `Builds/P4b_Drive/HellcatDrive.exe`: input, chase / bumper / cockpit / free
cameras, live cockpit (needles, wheel, pedals, mirrors), HUD with energy bars, node-beam / stress / deformation views,
reset / repair / teleports, slow motion, pause / step, pause menu, settings.json + F9 params reload, deterministic record /
replay (test 15 PASS). Measured in the player: physics {d['physics_hz_mean']:.0f} Hz (x{d['realtime_factor']:.3f} real time), {d['fps_mean']:.0f} fps mean,
input latency {d['latency_ms_mean']:.1f} ms, 5-minute drive ({d['distance_km']:.1f} km) without divergence (`docs/P4b_report.md`, `docs/controls.md`).
AUTONOMY MODE: work continuously P3 -> P7, no stops, no questions (brief top block).
"""
s = re.sub(r"\A# STATUS.*?AUTONOMY MODE:[^\n]*\n", head, s, count=1, flags=re.S)
if p4b_end and "P4 end" not in s:
    s = s.replace("P2 end 2026-10-11T18:33:43Z, P3 end 2026-10-12T19:32:01Z, P3b end 2026-10-13T04:16:54Z.",
                  f"P2 end 2026-10-11T18:33:43Z, P3 end 2026-10-12T19:32:01Z, P3b end 2026-10-13T04:16:54Z,\n"
                  f"   P4 end 2026-10-14T18:58:24Z, P4b end {p4b_end}.")

p4b = """## P4b game layer (decisions D-069 ... D-080)
- Scene `Assets/Scenes/P4b_Drive.unity` (`Tools/Hellcat/Build P4b Drive Scene`, `DriveSceneBuilder`); player
  `-executeMethod Hellcat.EditorTools.Build.BuildTasks.BuildDrive` -> `Builds/P4b_Drive/HellcatDrive.exe`. Keys and
  menus: `docs/controls.md`. Settings `settings.json` and `recordings/` next to the exe.
- Components (`Assets/Game`): `GameControls` (keys, safe pose, reset / repair / teleport with the speed hold
  `ApproachHoldSource` D-080, F9), `CameraRig` (chase,
  bumper, cockpit, free), `CockpitInstruments` (needles, wheel, pedals, mirrors), `Hud`, `PauseMenu`, `GameSettings`,
  `DebugViews` + `SkeletonDebugView` (N, Shift+N, H, Shift+H; deformation shader `Hellcat/DeformationHeatmap` reads UV3
  written by `CarSkinPostprocessor` v2), `ReplayController` (F5 / F6), `RobotDriverSource`, `SpawnPoint`.
- Sim: `WorldState` (snapshot of every native array, `Hash`), `InputRecording` (`.hrec`), `SimRunner.RespawnSettled /
  RestoreState / ReloadVehicleData / SubstepOverride / PendingSteps`, `Respawn` restarts the grid schedule (`clock[1]`).
- Tests: test 15 `-executeMethod Hellcat.EditorTools.Validation.ValidationTasks.RunGame` -> `docs/p4b/validation/`;
  G-Drive `HellcatDrive.exe -scenario drive [-driveSeconds 300 -driveRecord 60 -driveOut dir]` (windowed, ~7 min) ->
  `docs/p4b/drive/`; short capture `-scenario showcase [-captureOut dir]` (1920x1080 frames, then
  `tools\\p4b\\encode_capture.ps1`). Gate `tools\\gate_p4b.py`; report `tools\\p4b\\make_p4b_report.py`.
- Open: the glass reads almost clear in renders (P7 look); the P4 crash series predates D-069 (re-run in P6); the drive
  scene's four obstacles are stand-ins for P5's test map.
"""
if "## P4b game layer" in s:
    s = re.sub(r"## P4b game layer.*?(?=\n## )", p4b.rstrip("\n") + "\n", s, count=1, flags=re.S)
else:
    s = s.replace("## Architecture (short)", p4b + "\n## Architecture (short)")
s = s.replace("- Game `Assets/Game`: SimRunner, LiveDriverInput, SkeletonDebugView, BoxCarView, ChaseCamera, Hud, FrameCapture, WallCrashScenario.",
              "- Game `Assets/Game`: SimRunner, LiveDriverInput / RobotDriverSource, GameControls, CameraRig, CockpitInstruments, Hud,\n"
              "  PauseMenu, DebugViews / SkeletonDebugView, ReplayController, SoftBodyCarView, scenarios (CarCrashScenario, DriveTest,\n"
              "  ShowcaseCapture), FrameCapture; legacy slice pieces BoxCarView, ChaseCamera, WallCrashScenario.")
s = re.sub(r"## Next \(plan\).*?(?=\n## Phase log)", """## Next (plan)
- **P5** test map O1-O9 (brief 9): obstacles as static primitives with spawn points (`SpawnPoint`, teleport at speed),
  the drive loop kept for G-Drive.
- P6 scenarios S1-S8 + tuning + sensitivity sweep (hood creases, glass strength, S8 cabin), re-run of the crash series
  with D-069; P7 build + README + cost report.
""", s, count=1, flags=re.S)
s = s.replace("| P4b | in progress | - | D-069 (straight-line stability) done |",
              f"| P4b | done | {g['verdict']} ({g['fails']} fail, {g['warns']} warn) | docs/gates/gate_p4b.md, docs/P4b_report.md, docs/controls.md |")
p.write_text(s, encoding="utf-8")
print("STATUS updated")
