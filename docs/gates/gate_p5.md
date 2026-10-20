# Gate P5 (G-Map)

Result: **PASS** (0 FAIL, 0 WARN, 26 checks), 2026-10-15T22:45:38Z

| # | check | status | detail |
|---|---|---|---|
| 1 | map layout newer than the map builder | PASS | layout 2026-10-15 22:26:03, builder 2026-10-15 19:59:28 UTC |
| 2 | extent up to 300 x 200 m | PASS | 300 x 200 m, 10 m marks in the ground texture |
| 3 | O1: concrete wall, full frontal as specified | PASS | size [12, 3, 1] m (brief 12 x 3 x 1) |
| 4 | O2: concrete wall with 40 % offset line as specified | PASS | size [12, 3, 1] m, overlap line 40 % (brief: same wall, 40 % line) |
| 5 | O3: steel pole as specified | PASS | diameter 0.3 m x 6.0 m (brief 0.30 x 6 m) |
| 6 | O4: jersey barrier row as specified | PASS | 6 units 3.66 x 0.81 m at 20 deg (brief 6 x ~3.66 x 0.81 m at 20 deg) |
| 7 | O5: guardrail as specified | PASS | 15.2 m, posts every 1.9 m, W-beam top 0.705 m (brief ~15 m, 1.9 m, ~0.7 m) |
| 8 | O6: ramp and landing pad as specified | PASS | ramp 6.0 x 1.2 m, landing 25.0 m beyond (brief 6 x 1.2 m, 25 m) |
| 9 | O7: speed bump and curb as specified | PASS | curb 0.15 m, bump 0.1 x 3.0 m (brief 0.15 m; 0.10 x 3 m) |
| 10 | O8: debris field as specified | PASS | 12 barrels [0.58, 0.88] m 20 kg, 20 boxes 0.5 m 5 kg, 8 cones 0.7 m 1.5 kg, 6 fence panels; soft bodies in the car's solver (brief 12 / 20 / 8 / 6) |
| 11 | O9: 3 m ledge with lower pad as specified | PASS | ledge 3.0 m with a lower pad, bank 30 deg (brief 3 m ledge, 30 deg bank) |
| 12 | every obstacle lane has 60 m of clean run-up | PASS | 10 lanes, shortest 60.1 m |
| 13 | surfaces and friction documented | PASS | asphalt x1.0, concrete x0.9, grass x0.6 of the tyre friction (car on asphalt: skidpad 0.94 g, tyre peak 1.20: about 0.94 / 0.85 / 0.57 g; brief ~0.9 / 0.8 / 0.6) |
| 14 | map check newer than the map, debris and check sources | PASS | run 2026-10-15T22:40:11Z, newest MapCheck.cs 2026-10-15 20:55:54 UTC |
| 15 | solver stable with the debris in the world (S < 2.5) | PASS | exact S 2.4418 with 46 debris bodies (568 nodes) and the car; 2675 nodes, 13747 beams |
| 16 | debris at rest (no creep, no jitter) | PASS | after 5 s: fastest debris node 0.055 m/s, largest drift 3.3 cm, 0 moved > 5 cm |
| 17 | physics within the 2 kHz real-time budget with the debris | PASS | 294.4 us per 0.5 ms substep (solver only, player) |
| 18 | no tunnelling or non-finite values in any lane run | PASS | 10 runs; deepest node inside an obstacle 0 mm |
| 19 | teleport speed hold delivers V at the crash obstacles (D-080) | PASS | O1 30.0 km/h, O2 30.0 km/h, O3 30.0 km/h, O4 40.0 km/h, O5 50.0 km/h |
| 20 | the car meets every crash obstacle (damage recorded) | PASS | O1: 1 broken, 494 bent; O2: 3 broken, 444 bent; O3: 3 broken, 482 bent; O4: 2 broken, 127 bent; O5: 0 broken, 37 bent |
| 21 | curb and bump at 30 km/h without structural damage (brief 9): no structural beam broken or bent, skin and trim flow below 3 mm | PASS | over at 29.1 km/h, end 28.5 km/h; broken: none (closure stops released by design, D-034); bent 0: - - structural none, skin flow up to 0.00 mm |
| 22 | curb and bump at 50 km/h without structural damage (brief 9): no structural beam broken or bent, skin and trim flow below 3 mm | PASS | over at 50.5 km/h, end 48.7 km/h; broken: none (closure stops released by design, D-034); bent 0: - - structural none, skin flow up to 0.00 mm |
| 23 | O6 ramp jump flies and lands upright | PASS | airborne 0.845 s, up 1.0, broken none |
| 24 | O9 3 m drop flies and lands upright | PASS | airborne 0.817 s, up 1.0, broken none |
| 25 | O8 debris scatters on impact | PASS | 36 props moved, car bent 68 beams |
| 26 | top-down and perspective screenshots with dimensions | PASS | annotated top-down, overview, 10 lane views captioned in map_lanes_sheet.jpg, 10 run views |
