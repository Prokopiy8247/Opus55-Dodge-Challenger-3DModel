# Gate P7 (G-Build, standalone build)

Result: **PASS** (0 FAIL, 0 WARN, 14 checks), 2026-10-15T22:45:29Z

| # | check | status | detail |
|---|---|---|---|
| 1 | standalone Windows build present and newer than every game, solver and vehicle source (D10) | PASS | Builds\HellcatSandbox\HellcatSandbox.exe (175 MB, built 2026-10-15 22:26 UTC); newest source Unity\HellcatSandbox\Assets\StreamingAssets\Vehicles\hellcat\params.json 2026-10-15 21:09 UTC |
| 2 | starts from the executable: each check is a fresh start of HellcatSandbox.exe, the game comes up without exceptions | PASS | 8 starts: capture, controls, determinism, drive, drive1440, mapcheck, mapcheck_crease_0.2, mapcheck_crease_0.3 |
| 3 | runs the test map at the reported frame rate (brief 4.5: >= 60 fps display, >= 30 absolute; 1600x900 window) | PASS | 87 fps mean, 1 % low 45, p99 frame 22.2 ms; per view chase 79, cockpit 77, bumper 120, overlay_stress 78, deformation 83; NVIDIA GeForce RTX 5070, 1600x900 at 180 Hz, vsync 1 |
| 4 | physics at 2 kHz in real time while driving the test map (brief 4.5: >= 1000 Hz, 2000 Hz goal, >= 1x real time) | PASS | 1984 Hz = x0.992 real time, 318 us per substep with 2675 nodes / 13747 beams (car and debris), 6 slow-down frames of 26430 |
| 5 | 5-minute continuous drive on the test map's east loop without divergence; record / replay of its first minute bit-identical (G-Drive in the sandbox) | PASS | 300 s, 4.96 km, 11.8 laps, top 92 km/h, path error max 0.91 m; up.y min 0.9993, floor residual 1.67 mm, broken 0, bent 0; replay 60 s identical |
| 6 | input latency in the sandbox (key press -> rendered reaction) | PASS | 10/10 probes, 1.7 frames, 19.3 ms mean, 23.2 ms max |
| 7 | interior LOD while driving outside (brief 4.12) | PASS | 33 interior parts, 160,374 triangles in full (cockpit, inside the cabin); 98,146 from outside, the seats only beyond 35 m, none beyond 90 m; cockpit 77 fps vs chase 79 fps |
| 8 | frame rate at 2560x1440 full screen (the capture resolution; brief 4.5: >= 60 fps, >= 30 absolute) | PASS | 2560x1440: 90 fps mean, 1 % low 45; per view chase 77, cockpit 81, bumper 123, overlay_stress 82, deformation 87; physics x0.977 real time |
| 9 | controls work: every default key of brief 4.12 and the gamepad, through the Input System, change the game as expected | PASS | 23 passed: W, A, D, S, Space, E / Q, C, T, N / Shift+N, H / Shift+H, P / Shift+P, F5 / F6, R, Shift+R, F1, F7 / F8, Esc, gamepad right trigger, gamepad left trigger, gamepad left stick, gamepad B (east), gamepad Y (north), gamepad RB |
| 10 | the sandbox reproduces the P6 crash bit for bit: S1 50 km/h, every result field of the P6 run identical (energies to 0.1 J, crush, pulse, skinning); its recording replays bit-identically | PASS | 129 of 129 fields identical: crush 0.5104 / 0.4054 m, plastic 120871.1 J, peak 44.11 g raw; replay identical; world state 6fdec5fbc7fe02a7 vs P6 6fdec5fbc7fe02a7 (the debris asleep, D-098); data hash 87ba916c2c71ff98 vs 87ba916c2c71ff98 |
| 11 | a short capture at 2560x1440 / 60 fps (brief 14 G-Build) | PASS | docs/video_assets/P7/2026-10-15_P7_showcase_1440p60.mp4: 2560x1440, 60 fps, 45.1 s, h264, 126.1 MB (frames 2560x1440, written by the player frame by frame) |
| 12 | glass look: tinted glass whose reflections keep their strength (URP preserve-specular blending), lighter windshield and front side windows than the privacy rear glass | PASS | CH_Glass_Tint: premultiplied True, alpha 0.6, CH_Glass_Front: premultiplied True, alpha 0.25, CH_Lamp_Lens: premultiplied True, alpha 0.35 |
| 13 | README (how to run, controls, how to tune), controls and the scenario metrics (D9, D10) | PASS | docs/README.md, docs/controls.md, docs/metrics.csv, README.md |
| 14 | P7 report written | PASS | docs\P7_report.md |
