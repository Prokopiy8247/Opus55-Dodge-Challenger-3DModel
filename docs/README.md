# Hellcat Sandbox

A small drivable soft-body crash sandbox: a Dodge Challenger SRT Hellcat Widebody, modelled in Blender, simulated as a
BeamNG-style node-beam structure by its own solver in Unity, driven around a test map and crashed into its obstacles. The car
deforms and breaks as a consequence of the simulation: 2,107 nodes and about 11,400 beams stepped at 2,000 Hz, pressurized tyres,
a real suspension, steering, an eight-speed powertrain and brakes, skinned to a 780,000-triangle visual model with a full
interior and a working cockpit.

## Run it

1. Start **`Builds\HellcatSandbox\HellcatSandbox.exe`** (Windows 10 / 11, DirectX 12). It opens in a 1600 x 900 window
   (resizable; Alt+Enter for full screen).
2. A start card shows the main keys; press any key or gamepad button to drive.
3. Drive with W / A / S / D (or a gamepad), press **Esc** for the menu: teleport to any obstacle at rest or at a chosen speed
   (the speed is held to 1 m before the obstacle, so the car hits at that speed), reset, repair, cameras, views, recordings.

Measured on the development machine (Ryzen 7 5700X3D, RTX 5070, 180 Hz display): physics at 2,000 Hz (x0.99 real time, 318 us per substep with the debris asleep), 87 fps on average at 1600 x 900 (77 fps or more in every camera view) and 90 fps at 2560 x 1440 full screen (77 or more); input latency 19 ms.

All keys: [`docs/controls.md`](controls.md). The most used:

| Key | Action | Key | Action |
|---|---|---|---|
| W / S | throttle / brake (hold S at rest: reverse) | C | camera: chase, bumper, cockpit, free |
| A / D | steer | T | slow motion x0.1 |
| Space | handbrake | N / Shift+N | node-beam view / overlay on the paint |
| Q / E | gear down / up | H / Shift+H | beam-stress / deformation heat-map |
| R | reset to the last safe spot | P / Shift+P | pause / single step |
| Shift+R | repair in place | F5 / F6 | record / replay (bit-identical) |
| Ctrl+R | debris back in place | Esc | menu (teleports, settings) |

## The test map

300 m x 200 m of asphalt with 10 m marks, every obstacle with its own 60 m run-up lane and a spawn point in the menu:

| ID | Obstacle | ID | Obstacle |
|---|---|---|---|
| O1 | concrete wall 12 x 3 x 1 m (full frontal) | O6 | ramp 6 m x 1.2 m with a landing pad 25 m beyond |
| O2 | the same wall with a 40 % offset line | O7 | speed bump 0.10 x 3 m and a 0.15 m curb |
| O3 | steel pole 0.30 m x 6 m | O8 | debris: 12 barrels, 20 boxes, 8 cones, 6 fence panels (soft bodies in the same solver) |
| O4 | six jersey barriers at 20 deg | O9 | 3 m ledge with a lower pad, and a 30 deg grass bank |
| O5 | guardrail 15 m, posts every 1.9 m, met at 10 deg | east | open asphalt: skidpad R 30 m, the drive-test loop |

## What the crashes look like (P6, `docs/P6_report.md`)

| Scenario | Result |
|---|---|
| S1 full frontal, 50 km/h | 0.51 m crush, 45 g peak (CFC 60) over 68 ms, hood folded, cabin intact |
| S1 at 56 km/h vs the 2013 Challenger NHTSA NCAP test | static crush 574 mm vs 573-642 mm (calibrated); 51 g peak |
| S2 40 % offset, 64 km/h | struck side 1.00 m, IIHS-style intrusion "good" (8 cm), latches hold |
| S3 centred pole, 50 km/h | the pole goes 1.0 m into the front (twice the wall), soft 22 g pulse, the hood latch tears |
| S4 barrier row at 20 deg, 40 km/h | slides 0.4 s along the barriers, tie rod and a subframe mount break |
| S5 ramp, 80 km/h | 1.17 s in the air over 24 m, lands at 6.1 m/s, no beam breaks |
| S6 guardrail scrape, 70 km/h | 0.8 s along the rail, 116 fascia supports and clips torn |
| S7 debris, 10-20 km/h | 35-36 of 46 props moved; at 20 km/h a fence panel tears the left mirror off |
| S8 full frontal, 120 km/h | 1.13 m crush, 607 kJ of plastic work, 144 g peak, mirrors torn off |

Every run is recorded and replays bit for bit. Speed series, pulses, energies: `docs/metrics.csv`, `docs/p6/`. Videos:
`docs/video_assets/P6/` (four cameras plus 250 fps slow motion per scenario) and `docs/video_assets/P7/` (1440p showcase).

## How to tune

All physical parameters live in **`params.json`**, separate from the geometry (brief 15.3):

- in the repository: `sim/vehicle/hellcat/params.json` (`//` comments allowed), copied into the Unity project by
  `tools\sync_vehicle.py hellcat` (or the editor menu);
- in a build: `<exe>_Data\StreamingAssets\Vehicles\hellcat\params.json` - edit it while the game runs and press **F9** to rebuild
  the car from it (no restart).

What is in it:

- **Beam materials.** Spring, damping, deform threshold, hardening, strength per material: cage, rails, crash cans, panels,
  plastic clips, glass, mounts and more. Keep the explicit-step criterion S < 2.5: `tools\skeleton\stability.py`.
- **Material zones.** These scale the yield and break thresholds of one part's beams inside a box (D-090), for example the hood's
  crease strip.
- **Tyres.** Pressure scale, compound friction (peak, slide, load sensitivity, Stribeck), losses.
- **Suspension, steering, powertrain, brakes and aids.**
  - The springs, dampers and bars come from `tools\skeleton\suspension_design.py`.
  - The powertrain block holds the engine curve, ratios, converter and LSD.
  - The brake bias and the ABS / TC gains are in the same file.

To try a variant without touching the default, run a scenario with `-vehicleParams <file>`. For example
`HellcatSandbox.exe -scenario S1 -targetKmh 56 -out <dir> -vehicleParams my.json` writes the crash metrics to `<dir>`.

- `tools\p6\tune.py` and `tools\p6\sweep.py` run variant sets and the sensitivity sweep.
- Every adopted change goes into `docs\tuning_log.csv` and `docs\decisions.md`.
- Calibration targets and their sources: `docs/P6_report.md` (NHTSA, IIHS) and `docs/dynamics_report.md` (driving targets).

## Build and verify from source

| Task | Command (PowerShell, from the project root) |
|---|---|
| Car export (Blender 5.2.2, latest `3DDodgeChallenger_vNNN.blend`) | `tools\.venv\Scripts\python.exe tools\export_all.py` |
| Skeleton (`sim/vehicle/hellcat/geometry.json`) | `& tools\blender\bcall.ps1 hcar.hskel:main` (see `docs/STATUS.md`) |
| Bind the visual model to the nodes | `& tools\unity\run_unity_batch.ps1 -LogFile <log> -ProjectPath Unity\HellcatSandbox -UnityArgs @('-executeMethod','Hellcat.EditorTools.Car.CarImporter.ImportBatch')` |
| The standalone sandbox | `& tools\p7\run_p7.ps1 -Build` (`BuildTasks.BuildSandbox`, then the G-Build checks) |
| Validation tests 1-8 (+ energy drift, determinism) | `... -UnityArgs @('-executeMethod','Hellcat.EditorTools.Validation.ValidationTasks.RunAll')` -> `docs/validation_report.md` |
| Vehicle dynamics tests 9-14 | `... ValidationTasks.RunDynamics -valTests T9,T10,T11,T12,T13,T14` -> `docs/dynamics_report.md` |
| Record / replay test 15 | `... ValidationTasks.RunGame` |
| Crash scenarios S1-S8 with captures | `& tools\p6\run_all_p6.ps1` |
| Every gate again | `& tools\p7\run_suites.ps1` then `tools\.venv\Scripts\python.exe tools\gate_p7.py` |

The Unity project is `Unity\HellcatSandbox` (Unity 6000.6.0f1, URP, Burst, Input System).

- **Solver:** `Assets/Sim`.
- **Game layer:** `Assets/Game`.
- **Scene builders and batch tasks:** `Assets/Editor`.

Quality gates are `tools\gate_*.py`. They write `docs/gates/gate_*.md`, and each phase has its report `docs/P*_report.md`.
How to resume work: `docs/STATUS.md`; every design decision with its reason: `docs/decisions.md`.

## Command-line scenarios (the sandbox)

| Arguments | What it does |
|---|---|
| `-scenario S1` ... `S8` `[-targetKmh v] -out <dir> [-capture 1]` | scripted crash with metrics, recording, replay check, 250 fps slow motion |
| `-scenario S1 -driven 1 -out <dir>` | the same lane driven through the game's teleport and speed hold, F5 / F6 |
| `-replay <file.hrec>` | plays any recording, then you drive on |
| `-scenario drive [-driveSeconds 300]` | the G-Drive test: latency probes, a 5-minute robot drive in five views, record / replay |
| `-scenario controls` | presses every control through a virtual keyboard and gamepad |
| `-scenario showcase -captureOut <dir>` | the scripted showcase written frame by frame (any resolution) |
| `-scenario mapcheck` | the map check: debris at rest, one run per lane, screenshots |

## Known limitations

- **S8 passenger cell.** At 120 km/h the passenger cell keeps more of its shape than a real car's would. The tyres do not collide
  with their own body, so the front wheels pushed back 34-40 cm do not load the hinge pillars.
- **NCAP comparison.** The crush matches the 56 km/h NCAP test, but the rebound is 4.0 m/s instead of 2.7. The wheelbase does not
  shorten, while NCAP measured 150 mm.
- **Top speed.** It is 283 km/h against the published 314 km/h: the node tyres lose more power under drive (`docs/dynamics_report.md`).
- **Hood.** The hood skeleton is coarse, with rows every 0.17 m. At 120 km/h the torn fenders and roof edge stretch their
  skinned panels into sheets.
- **Debris.** The props are drawn rigid; their soft bodies deform in the solver only.

The full list of open points is in the phase reports and `docs/P7_report.md`.
