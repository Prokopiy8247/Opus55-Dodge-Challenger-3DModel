# Gate P0.5

Result: **PASS** (0 FAIL, 0 WARN, 12 checks)

| # | Check | Status | Detail |
|---|---|---|---|
| 1 | original .blend untouched | PASS | SHA-256 compared with the P0 fingerprint |
| 2 | box car skeleton exported from Blender (30-60 nodes, 4 wheels) | PASS | 60 nodes, 250 beams, 4 wheels, 1334 kg, hydros ['steering'] |
| 3 | exported geometry reaches the Unity project | PASS | Unity\HellcatSandbox\Assets\StreamingAssets\Vehicles\boxcar\geometry.json |
| 4 | standalone slice build exists | PASS | Builds\P05_Slice\HellcatSlice.exe |
| 5 | driven on the plane to the target speed (50 km/h +/- 10 %) | PASS | entry speed 48.5 km/h |
| 6 | crash: plastic deformation, no NaN, settles | PASS | crush 0.270 m, 26 plastic beams, plastic work 63.3 kJ, peak 31.9 g (frame avg), max node speed after 3 s 0.03 m/s |
| 7 | damage grows with speed | PASS | 48.5 km/h: 0.270 m / 63 kJ  vs  67.6 km/h: 0.508 m / 130 kJ |
| 8 | deterministic re-run (time series byte-identical, capture on vs off) | PASS | 84769 bytes, sha256 3408b86ebbbef983 |
| 9 | stability report (S < 2 hard limit) | PASS | max S 1.745 |
| 10 | physics cost of the slice | PASS | 7.5 us/substep, 15.0 ms per simulated second |
| 11 | windowed live-drive mode runs in real time (2000 Hz) | PASS | physics 2000 Hz x1,00 |
| 12 | video assets (MP4 chase + side, slow motion, stills) | PASS | 2026-10-10_P05_boxcar_wall_50kmh_chase.mp4, 2026-10-10_P05_boxcar_wall_50kmh_side.mp4, 2026-10-10_P05_boxcar_wall_50kmh_side_slowmo_0.25x.mp4, 2026-10-10_P05_boxcar_wall_80kmh_chase.mp4, 2026-10-10_P05_boxcar_wall_80kmh_side.mp4, 2026-10-10_P05_boxcar_skeleton_blender.png, 2026-10-10_P05_boxcar_wall_50kmh_after_side.png, 2026-10-10_P05_boxcar_wall_50kmh_impact_side.png, 2026-10-10_P05_boxcar_wall_80kmh_after_side.png |
