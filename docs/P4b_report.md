# P4b report: the game layer

Gate G-Drive: **PASS** (0 FAIL, 0 WARN, 19 checks, `docs/gates/gate_p4b.md`).
The Hellcat is now a drivable sandbox (`Builds/P4b_Drive/HellcatDrive.exe`, scene `P4b_Drive`), with:

- keyboard and gamepad input;
- chase, bumper, cockpit and free cameras;
- a live cockpit: needles, steering wheel and pedals driven by the simulation, and three mirrors that show the scene;
- the HUD with energy bars;
- node-beam, stress and deformation views;
- reset, repair and teleports, slow motion, pause and step;
- a pause menu, a settings file and parameter hot reload;
- deterministic record and replay.

Measured in the player on this machine (AMD Ryzen 7 5700X3D 8-Core Processor, NVIDIA GeForce RTX 5070, 1600x900 window at 180 Hz, vsync on):

- **Physics:** 1996 Hz, x0.998 real time.
- **Display:** 116 fps mean, 1 % low 60 fps.
- **Input latency:** 21.0 ms mean, from key press to the rendered reaction (2.9 frames).
- **5-minute drive:** 300 s, 7.8 km, 8 laps, without divergence.
- **In-game replay:** the replay of the first 60 s is bit-identical.

Test 15 (record and replay determinism) passes.
Decisions D-070 ... D-080 are in `docs/decisions.md`; the controls are in `docs/controls.md`.

## What was built

- **Input** (`LiveDriverInput`, Unity Input System).
  - Keys: W / S / A / D / Space / Q / E, the arrows, gamepad triggers, stick and shoulders.
  - It reads before the solver steps, so a key drives the same frame (D-075).
  - ABS and traction control are on by default (F7 / F8).
- **Cameras** (`CameraRig`, D-071).
  - Chase camera: constant distance at any speed, with a lagging heading.
  - Bumper camera: just ahead of the fascia.
  - Cockpit camera: at the driver's eye, riding on the cabin nodes with a best-fit rotation, 85 deg horizontal field of view.
  - Free camera.
- **Live cockpit** (`CockpitInstruments`, D-072, completes D-021).
  - Tach and speedometer needles, steering wheel (1.3 turns each way) and pedals follow the simulation.
  - They are drawn as rigid copies of their meshes that ride on the dash nodes and turn about their cockpit.json pivots.
  - The interior and both side mirrors show the scene through render textures, rendered only in the cockpit view.
- **HUD** (`Hud`, D-076).
  - Speed, rpm, gear, pedals, steering, G, broken and bent beams, ABS / TC.
  - Energy bars: kinetic, elastic, plastic work, breaking + damping.
  - Physics Hz, fps, step time, quality mode and the slow-down flag.
  - Camera, time scale, pause, recording / replay state and messages. F1 hides it.
- **Debug views** (`SkeletonDebugView`, `DebugViews`, D-073).
  - N: node-beam view. Shift+N: x-ray overlay.
  - H: beam stress heat-map.
  - Shift+H: deformation heat-map on the visual mesh (UV3 rest positions against the cabin floor's rigid frame).
- **Reset, repair and teleport** (`GameControls`, `SimRunner.RespawnSettled`, D-074).
  - R: the last safe pose.
  - Shift+R: repair in place, moved clear of obstacles.
  - Pause-menu teleports to spawn points; obstacle spawns stand 60 m before the face, at a chosen speed.
  - The speed is held on the lane and the pedals are released 1 m before the obstacle, so the car arrives at V (D-080).
  - Slow motion x0.1 (T), pause and one-frame step (P / Shift+P), screenshots (F12).
- **Record and replay** (`WorldState`, `InputRecording`, `ReplayController`, D-070).
  - F5: snapshot of the whole world plus per-frame substeps and inputs, saved as `.hrec` + `.csv`.
  - F6: replay. Bit-identical with the recorded partition; per-substep inputs in slow motion.
  - A respawn restarts the collision-grid schedule, so respawn-based recordings (scripted scenarios) replay exactly as well.
- **Pause menu** (Esc, `PauseMenu`): reset / repair, spawn points and obstacle teleports at 0-200 km/h, camera, time scale, views, aids, recordings, settings.
- **Settings and tuning** (`GameSettings`, D-078).
  - `settings.json` next to the executable.
  - F9 reloads `params.json` / `geometry.json` and rebuilds the world without restarting (the brief's bonus).
- **Drive scene** (`DriveSceneBuilder`, `BuildTasks.BuildDrive`).
  - A 1 km asphalt square with the drive-test loop.
  - Four demo obstacles, each with an approach spawn: O1 wall, O2 pole, O3 40 % offset block, O4 ramp (P5 replaces them with the test map).
- **G-Drive test** (`DriveTest`, `-scenario drive`, D-077) and the short capture (`ShowcaseCapture`, `-scenario showcase`).

## G-Drive: measured numbers

| quantity | value |
|---|---|
| simulated drive | 300.0 s, 7.81 km, 8.0 laps of the 977 m loop (160 km/h straights, 75 km/h curves), top speed 155 km/h |
| real time | 300.6 s, 35007 frames |
| physics | 1996 Hz mean (x0.9979 real time), 283 us per 0.5 ms substep, 6 slow-down frames |
| display | 116 fps mean, median frame 5.56 ms, p99 16.7 ms (1 % low 60 fps), longest 550 ms (the settled respawn at the start) |
| input latency | 10/10 probes, 21.0 ms mean, 29.1 ms max (2.9 frames mean, 4 max); per probe: 18.5, 13.9, 17.9, 24.3, 29.1, 19.1, 18.8, 22.7, 24.8, 20.6 ms |
| divergence | non-finite 0, cabin up.y min 0.9990, cabin floor residual max 1.68 mm, broken beams 0, bent beams 0, max node speed 2.47 x the car's |
| path (driver robot) | error max 2.01 m, rms 0.94 m |
| in-game replay | 60.0 s, 6347 frames: end-state hash FA84247D0400A654 recorded, FA84247D0400A654 replayed |

By camera and view (60 s each; the first segment includes the start):

| view | frames | fps mean | p99 frame ms | physics Hz | us per substep | slow-down frames |
|---|---|---|---|---|---|---|
| chase | 6347 | 105 | 16.7 | 1982 | 283 | 3 |
| cockpit | 6265 | 104 | 16.7 | 1997 | 282 | 2 |
| bumper | 9652 | 161 | 11.1 | 2000 | 284 | 0 |
| overlay_stress | 6346 | 106 | 16.7 | 2000 | 281 | 0 |
| deformation | 6397 | 107 | 16.7 | 2000 | 285 | 1 |

**How latency is measured.** A key-down event (D) is queued on a virtual keyboard through the Input System while the car is at rest. The test waits for the end of each frame, after the GPU skinning, until the front wheel has turned 0.25 deg. The time includes:

- the Input System update;
- `LiveDriverInput`;
- the solver substeps of the frame;
- the rate-limited steering moving the knuckle nodes;
- the bone update and the render.

The display then adds up to one refresh interval (5.6 ms at 180 Hz).

## Test 15: record and replay

The driver robot drives the settled car through a 3.5 m lane change into a rigid wall at 55 km/h. Each frame has 25-40 substeps (seeded), and the run is recorded from a world snapshot.

| check | value |
|---|---|
| recorded run | 12 s, wall at 54.5 km/h, broken / bent beams at the end 31 |
| snapshot restore reproduces the state | yes |
| replay with the recorded partition: end state bit-identical, path deviation | yes, 0 m |
| replay at 8 substeps per frame (250 fps capture): path deviation, end state identical | 0 m, yes |
| through a recording file | bit-identical, 0.63 MB |
| respawn starts after different histories | settled state identical, replay bit-identical |
| world snapshot | 3.83 MB raw |

## Gate checks

| # | check | status | detail |
|---|---|---|---|
| 1 | test 15 results newer than the solver sources and the vehicle data | PASS | run 2026-10-14T21:11:21Z, newest input Unity\HellcatSandbox\Assets\Sim\Core\InputRecording.cs 2026-10-14 20:00:30 UTC |
| 2 | test 15 record / replay (snapshot, partition, file, respawn) | PASS | 15 checks, failed: none; 250 fps replay deviation 0 m; recorded run 12.0 s with a crash at 54.5 km/h |
| 3 | drive test newer than the solver, game sources and vehicle data | PASS | run 2026-10-14T21:25:37Z, newest input Unity\HellcatSandbox\Assets\Game\UI\Hud.cs 2026-10-14 21:16:11 UTC |
| 4 | drive test in the player build (not the editor) | PASS | AMD Ryzen 7 5700X3D 8-Core Processor, 16 threads, NVIDIA GeForce RTX 5070, 1600x900 at 180.0 Hz, vsync 1 |
| 5 | 5-minute continuous drive | PASS | 300.0 s simulated, 300.6 s real, 7.81 km, 8.0 laps of the 977 m loop |
| 6 | physics Hz measured (target 2000 Hz in real time) | PASS | 1996 Hz mean = x0.998 real time, 283 us per substep, 6 slow-down frames of 35007 |
| 7 | display fps measured | PASS | 116 fps mean, 1 % low 60 fps (p99 frame 16.7 ms, max 550 ms); chase 105, cockpit 104, bumper 161, overlay_stress 106, deformation 107 |
| 8 | every camera and view at 60 fps or more | PASS | slowest: cockpit 104 fps, 1997 Hz physics |
| 9 | input latency measured (key press -> rendered reaction) | PASS | 10/10 probes reacted; 2.9 frames, 21.0 ms mean, 29.1 ms max (engine: Input System event -> rendered frame; the display adds its refresh interval) |
| 10 | no divergence over the drive | PASS | non-finite 0, up.y min 0.9990, floor residual max 1.68 mm, broken 0, bent beams 0, max node speed 2.47 x the car's |
| 11 | no structural creep (bent beams after the drive) | PASS | 0 beams with a changed rest length after 7.8 km of driving |
| 12 | the driver robot holds the loop | PASS | path error max 2.01 m, rms 0.94 m (after the first 20 s), top speed 155 km/h |
| 13 | in-game record / replay of the drive bit-identical (F5 / F6 path) | PASS | 60.0 s, 6347 frames recorded; end-state hash FA84247D0400A654 vs replay FA84247D0400A654 (58.2 s real) |
| 14 | player log free of exceptions | PASS | 0 exception lines in player.log |
| 15 | live cockpit: needles, steering wheel, pedals, mirrors (D-021) | PASS | 5 moving parts, 3 mirrors |
| 16 | screenshots of every camera, view and mirror | PASS | 8/8 present |
| 17 | docs/controls.md covers the brief's default keys | PASS | missing: none |
| 18 | HUD fields of brief 4.12 (and energy bars of 16) | PASS | missing: none |
| 19 | short capture | PASS | p4b_showcase.mp4 61.7 MB |

## Captures and files

- **Short capture:** `docs/p4b/capture/p4b_showcase.mp4`, 1920x1080 at 60 fps, written frame by frame. The sequence:
  1. chase, cockpit and bumper cameras on the loop;
  2. the node-beam overlay with the stress map through a curve;
  3. a teleport to the O1 wall at 64 km/h, recorded, with the impact at x0.1 from the side;
  4. the deformation heat-map around the wreck;
  5. the crash replayed from the driver's seat.
- **Screenshots of every view** in `docs/p4b/drive/` (`drive_*.png`) and the three mirror images (`mirror_*.png`).
- **Drive test:** `docs/p4b/drive/drive_test.json`, `drive_timeseries.csv`, `drive_record.hrec`. Test 15: `docs/p4b/validation/`.

## Deviations and open points

- **Bumper camera.** It is positioned in the camera rig (9 cm ahead of the fascia), not in the skeleton's mount, to keep geometry.json and the P4 crash evidence unchanged. A later skeleton export can move the mount.
- **Side mirrors.** The exported side mirror glass is flat and faces straight back. The mirror camera is aimed the way a driver would set the glass (6 deg outboard) instead of reflecting the eye ray about the flat glass.
- **Glass.** The tinted glass shows little reflection in these renders (a view from behind sees the cabin through the rear window almost unobstructed); the material look is for P7 polish.
- **Editor validation runs compile Burst synchronously (D-079).** One test-15 session differed from the others from the first frame (3e-7 m, then 54.59 instead of 54.49 km/h at the wall): the editor had run some substeps of the settle as managed code while the Burst code loaded. Replays inside every session stayed bit-identical, and the shipped player compiles Burst ahead of time.
- **P4 crash series.** It was produced before D-069 (P4b's straight-line fix) and is re-run with P6's scenarios.
- **Demo obstacles.** The four obstacles in the drive scene are stand-ins; P5 builds the brief's test map.
