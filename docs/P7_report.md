# P7 report: polish, standalone build, final gates

Gate G-Build (P7): **PASS** (0 FAIL, 0 WARN, 14 checks, `docs/gates/gate_p7.md`).

**What P7 delivers.**

- **The standalone game** is `Builds/HellcatSandbox/HellcatSandbox.exe` (D-102): the test map with the full game layer and a
  minimal start screen. It also runs every command-line check: crash scenarios, driven variants, the map check, the drive test,
  the controls check and the showcase capture. How to run, the controls and how to tune: `docs/README.md` and `docs/controls.md`.
- **Polish:**
  - glass that reads as glass: tinted, with full-strength reflections, a lighter windshield and a privacy rear (D-099);
  - a procedural sky for the background and the reflections (D-100);
  - interior level of detail while driving outside (brief 4.12, D-101).
- **Frame rate.** The first sandbox drive test showed the 46 debris props costing a quarter of every substep: 53-56 fps in the
  chase and cockpit views. Sleeping debris (D-098) puts them to sleep while they are at rest and the car is far away. The result
  is 87 fps on average and 77 fps or more in every view (90 fps at 2560 x 1440), with the car's physics unchanged bit for bit.
- **A regression found and fixed.** The final re-run of the validation suite failed T6: after the 0.2 m drop one hood beam
  had yielded. The map check, now reporting bent beams by material (D-103), showed the speed bump bending the same strip: the
  hood's crease zone from P6 (D-095) yielded at a tenth of the panel thresholds. At 0.3 (D-104) the drop and the bump stay
  elastic. The whole P6 series was run again with it on the final build.
- **Final verification.**
  - **G-Build:** the controls check (23 controls through a virtual keyboard and gamepad), the 5-minute drive, frame rates at
    1600 x 900 and 2560 x 1440, and the 1440p / 60 fps capture.
  - **Earlier evidence re-run on the final code:** the validation and dynamics suites, test 15, the P4b drive test, the map
    check and the whole P6 crash series.
- **Deliverables D9 and D10 completed:**
  - `docs/metrics.csv`, one row per scripted run;
  - `docs/README.md` and the root `README.md`;
  - the cost report `docs/cost_report.md` (brief 18).

**Deviations from the brief.**

- **No skinned debris.** The debris props are drawn rigid on the best-fit frames of their nodes; they deform in the solver only.
- **Vehicle self-collision.** It is limited to the detachable parts (D-058). The tyres do not collide with their own body, so at
  120 km/h the wheels pushed back do not load the hinge pillars (P6 open point 1).
- **Top speed** is 283 km/h against the published 314 km/h (P3b open point): the node tyres lose power under drive.
- **Calibration gaps.** The NCAP rebound and the wheelbase shortening are not matched (P6). The S7 debris damage is not
  monotonic in speed (a gate warning): the fence panels decide it.
- **Drive loop.** The drive test and the showcase use a 419 m loop in the east of the map rather than P4b's 977 m loop, which
  does not fit on the 300 x 200 m map. The P4b drive scene keeps the long loop and its own drive test.


**Open questions for the user** (none blocks the delivery):

1. **S8 passenger cell.** Should the cell collapse more at 120 km/h? That needs tyre-to-body self-collision, a solver cost.
2. **Top speed.** Is 283 km/h acceptable, or should the tyre losses under drive be re-tuned?
3. **Hood.** Would a finer hood skeleton be worth a re-export and a new P2 / P4 / P6 cycle? It would give smaller folds.

## Frame rate on the test map (the 5-minute drive test in the sandbox)

AMD Ryzen 7 5700X3D 8-Core Processor, NVIDIA GeForce RTX 5070, 180 Hz display with vsync; physics 2675 nodes / 13747 beams (the car and the 46 debris props) at 2 kHz, Burst parallel. The drive robot laps the east loop for 300 s, 60 s in each view.

| | before D-098 (debris always simulated) | after D-098 (debris asleep while far) |
|---|---|---|
| fps mean (1600 x 900 window) | 60 | 87 |
| fps 1 % low | 30 | 45 |
| frame p99 ms | 33.3 | 22.2 |
| physics us per substep | 358 | 318 |
| physics Hz (real-time factor) | 1978 (x0.989) | 1984 (x0.992) |
| frames at the substep cap (slow-down) | 338 | 6 |
| chase view fps | 56 | 79 |
| cockpit view fps | 53 | 77 |
| bumper view fps | 83 | 120 |
| overlay_stress view fps | 54 | 78 |
| deformation view fps | 56 | 83 |
| fps at 2560 x 1440 full screen (100 s) | 69 | 90 |
| 2560 x 1440 per view | chase 58, cockpit 65, bumper 97, overlay_stress 61, deformation 66 | chase 77, cockpit 81, bumper 123, overlay_stress 82, deformation 87 |

The same drive in the P4b drive scene (no debris, four obstacles) ran at 116 fps with 283 us per substep (`docs/P4b_report.md`). Input latency in the sandbox: 19.3 ms mean (1.7 frames). The drive itself is identical before and after (path error 0.913 m, 4.96 km, replay of the first minute bit-identical).

## Controls check (`-scenario controls`)

A virtual keyboard and a virtual gamepad, added to the Input System, press every default control; 23 passed, 0 failed (17.9 s).

| control | expected | observed |
|---|---|---|
| W | throttle 1, the car accelerates | throttle 1.00, speed 3.3 -> 65.5 km/h |
| A | steer left (-1) | steer -1.00 |
| D | steer right (+1) | steer 1.00 |
| S | brake 1, the car slows | brake 1.00, speed 55.8 -> 11.2 km/h |
| Space | handbrake 1 | handbrake 1.00 |
| E / Q | gear up, gear down (manual request) | manual gear 0 -> E 1 -> Q 0, driven gear 1 |
| C | cycles chase, bumper, cockpit, free and back | Chase > Bumper > Cockpit > Free > Chase |
| T | slow motion on and off | time scale 0.1 -> 1 |
| N / Shift+N | node-beam view, then overlay on the paint | Alone, Overlay, then Off |
| H / Shift+H | stress heat-map, deformation heat-map | stress True, deformation True, then False / False |
| P / Shift+P | pause (no steps), single step (33 substeps), resume | paused True, 0 steps while paused, step 33, running again True |
| F5 / F6 | record, stop, replay, stop | Recording, Idle (114 frames), Replaying, Idle |
| R | reset: a fresh car at rest at the last safe spot | respawns +1, speed 1.0 km/h; 'reset to the last safe position (4.2 s of driving ago)' |
| Shift+R | repair in place | respawns +1; 'repaired' |
| F1 | HUD off and on | True -> False -> True |
| F7 / F8 | ABS and traction control toggle | ABS True -> False, TC True -> False |
| Esc | pause menu opens and closes | open True, then False |
| gamepad right trigger | analog throttle 0.8 | throttle 0.80 |
| gamepad left trigger | analog brake 0.6 | brake 0.60 |
| gamepad left stick | analog steering -0.5 | steer -0.47 |
| gamepad B (east) | handbrake | handbrake 1.00 |
| gamepad Y (north) | next camera | Chase -> Bumper |
| gamepad RB | gear up | manual gear 0 -> 1 |

## The sandbox reproduces the P6 crash

S1 at 50 km/h run again in `HellcatSandbox.exe`: 129 of the 129 result fields the P6 run wrote are identical (crush 0.5104 / 0.4054 m, plastic work 120871.1 J, peak 44.11 g raw); its recording replays bit-identically (identical). The world hash differs from P6's only by the frozen debris (D-098).

## Capture

`docs/video_assets/P7/2026-10-15_P7_showcase_1440p60.mp4`: 2560 x 1440, 60 fps, 45.1 s, 126.1 MB - the showcase written frame by frame by the player at 2560 x 1440 (chase, cockpit with live gauges and mirrors, bumper camera, node-beam overlay with stresses, a teleport to the O1 wall at 64 km/h in slow motion, the deformation heat-map, the replay with stresses and from the driver's seat).

![showcase](video_assets/P7/2026-10-15_P7_showcase_sheet.jpg)

## Every gate on the final build

| Phase | Gate | Verdict | Run |
|---|---|---|---|
| P0 | environment, Unity project, solver benchmark | PASS (0 fail, 3 warn) |  |
| P0.5 | vertical slice | PASS (0 fail, 0 warn) |  |
| P1 | G-Model: exterior | PASS (0 fail, 1 warn) |  |
| P1b | G-Interior: interior and cockpit | PASS (0 fail, 1 warn) |  |
| P2 | G-Skeleton: physics skeleton | PASS (0 fail, 2 warn) |  |
| P3 | G-Solver: validation tests 1-8 | PASS (0 fail, 0 warn) | 2026-10-15T22:11:51Z |
| P3b | G-Dynamics: tests 9-14, driving targets | PASS (0 fail, 0 warn) | 2026-10-15T22:16:55Z |
| P4 | G-Crash (S1 in the P4 crash scene) | PASS (0 fail, 0 warn) | 2026-10-14T18:57:25Z |
| P4b | G-Drive: game layer, 5-minute drive, test 15 | PASS (0 fail, 0 warn) | 2026-10-15T22:25:25Z |
| P5 | G-Map: test map | PASS (0 fail, 0 warn) | 2026-10-15T22:45:38Z |
| P6 | G-Crash: all scenarios S1-S8 | PASS (0 fail, 1 warn) | 2026-10-15T22:25:28Z |
| P7 | G-Build: standalone build | PASS (0 fail, 0 warn) | 2026-10-15T22:45:29Z |

P0-P1b, P2 and P4 keep their phase runs: their evidence (the environment, the Blender model, the P4 crash scene) did not change after their phase, and the P4 crash series is superseded by the P6 series of the same scenario on the final car (G-Crash, P6). P3, P3b, P4b, P5, P6 and P7 were run again on the final code and data.

## Gate checks (P7)

| # | check | status |
|---|---|---|
| 1 | standalone Windows build present and newer than every game, solver and vehicle source (D10) | PASS |
| 2 | starts from the executable: each check is a fresh start of HellcatSandbox.exe, the game comes up without exceptions | PASS |
| 3 | runs the test map at the reported frame rate (brief 4.5: >= 60 fps display, >= 30 absolute; 1600x900 window) | PASS |
| 4 | physics at 2 kHz in real time while driving the test map (brief 4.5: >= 1000 Hz, 2000 Hz goal, >= 1x real time) | PASS |
| 5 | 5-minute continuous drive on the test map's east loop without divergence; record / replay of its first minute bit-identical (G-Drive in the sandbox) | PASS |
| 6 | input latency in the sandbox (key press -> rendered reaction) | PASS |
| 7 | interior LOD while driving outside (brief 4.12) | PASS |
| 8 | frame rate at 2560x1440 full screen (the capture resolution; brief 4.5: >= 60 fps, >= 30 absolute) | PASS |
| 9 | controls work: every default key of brief 4.12 and the gamepad, through the Input System, change the game as expected | PASS |
| 10 | the sandbox reproduces the P6 crash bit for bit: S1 50 km/h, every result field of the P6 run identical (energies to 0.1 J, crush, pulse, skinning); its recording replays bit-identically | PASS |
| 11 | a short capture at 2560x1440 / 60 fps (brief 14 G-Build) | PASS |
| 12 | glass look: tinted glass whose reflections keep their strength (URP preserve-specular blending), lighter windshield and front side windows than the privacy rear glass | PASS |
| 13 | README (how to run, controls, how to tune), controls and the scenario metrics (D9, D10) | PASS |
| 14 | P7 report written | PASS |

Details per check: `docs/gates/gate_p7.md`.

