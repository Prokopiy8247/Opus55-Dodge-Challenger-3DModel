# Gate P4b (G-Drive)

Result: **PASS** (0 FAIL, 0 WARN, 19 checks), 2026-10-15T22:25:25Z

| # | check | status | detail |
|---|---|---|---|
| 1 | test 15 results newer than the solver sources and the vehicle data | PASS | run 2026-10-15T22:17:50Z, newest input sim\vehicle\hellcat\params.json 2026-10-15 21:09:36 UTC |
| 2 | test 15 record / replay (snapshot, partition, file, respawn) | PASS | 15 checks, failed: none; 250 fps replay deviation 0 m; recorded run 12.0 s with a crash at 54.5 km/h |
| 3 | drive test newer than the solver, game sources and vehicle data | PASS | run 2026-10-15T22:24:21Z, newest input sim\vehicle\hellcat\params.json 2026-10-15 21:09:36 UTC |
| 4 | drive test in the player build (not the editor) | PASS | AMD Ryzen 7 5700X3D 8-Core Processor, 16 threads, NVIDIA GeForce RTX 5070, 1600x900 at 180.0 Hz, vsync 1 |
| 5 | 5-minute continuous drive | PASS | 300.0 s simulated, 300.7 s real, 7.81 km, 8.0 laps of the 977 m loop |
| 6 | physics Hz measured (target 2000 Hz in real time) | PASS | 1996 Hz mean = x0.998 real time, 279 us per substep, 3 slow-down frames of 36872 |
| 7 | display fps measured | PASS | 123 fps mean, 1 % low 60 fps (p99 frame 16.7 ms, max 550 ms); chase 114, cockpit 105, bumper 167, overlay_stress 110, deformation 117 |
| 8 | every camera and view at 60 fps or more | PASS | slowest: cockpit 105 fps, 1996 Hz physics |
| 9 | input latency measured (key press -> rendered reaction) | PASS | 10/10 probes reacted; 2.8 frames, 20.8 ms mean, 26.4 ms max (engine: Input System event -> rendered frame; the display adds its refresh interval) |
| 10 | no divergence over the drive | PASS | non-finite 0, up.y min 0.9990, floor residual max 1.68 mm, broken 0, bent beams 0, max node speed 2.51 x the car's |
| 11 | no structural creep (bent beams after the drive) | PASS | 0 beams with a changed rest length after 7.8 km of driving |
| 12 | the driver robot holds the loop | PASS | path error max 2.01 m, rms 0.94 m (after the first 20 s), top speed 155 km/h |
| 13 | in-game record / replay of the drive bit-identical (F5 / F6 path) | PASS | 60.0 s, 6921 frames recorded; end-state hash A61E88979F097C5C vs replay A61E88979F097C5C (58.9 s real) |
| 14 | player log free of exceptions | PASS | 0 exception lines in player.log |
| 15 | live cockpit: needles, steering wheel, pedals, mirrors (D-021) | PASS | 5 moving parts, 3 mirrors |
| 16 | screenshots of every camera, view and mirror | PASS | 8/8 present |
| 17 | docs/controls.md covers the brief's default keys | PASS | missing: none |
| 18 | HUD fields of brief 4.12 (and energy bars of 16) | PASS | missing: none |
| 19 | short capture | PASS | p4b_showcase.mp4 61.7 MB |
