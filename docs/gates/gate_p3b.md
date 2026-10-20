# Gate P3b (G-Dynamics)

Vehicle `hellcat`. Result: **PASS** (0 FAIL, 0 WARN, 18 checks)

| # | Check | Status | Detail |
|---|---|---|---|
| 1 | dynamics run with every required test (9-14) | PASS | run 2026-10-15T22:16:55Z, tests T9, T10, T11, T12, T13, T14; missing: none |
| 2 | dynamics results newer than the vehicle data and the solver sources | PASS | results 2026-10-15 22:16:55 UTC, newest input sim\vehicle\hellcat\params.json 2026-10-15 21:09:36 UTC |
| 3 | test 9: Tire: load-deflection, pressure vs volume, free rolling, slip-angle and slip-ratio sweeps, puncture | PASS | 34/34 numeric checks pass in 9.7 s |
| 4 | test 10: Suspension: static corner loads, bounce, 50 mm step, curb strike, roll gradient, anti-roll bars | PASS | 17/17 numeric checks pass in 51.3 s |
| 5 | test 11: Steering: angle vs input on turntables, ratio, speed-sensitive reduction, return to centre | PASS | 8/8 numeric checks pass in 19.0 s |
| 6 | test 12: Powertrain: idle, rev limit, gear ratios, 0-100 km/h, top speed, engine braking, wheelspin | PASS | 21/21 numeric checks pass in 105.9 s |
| 7 | test 13: Brakes: 100-0 km/h with and without ABS, steering while braking, handbrake, repeated stops | PASS | 11/11 numeric checks pass in 42.8 s |
| 8 | test 14: Drive tests: slalom, skidpad, figure eight, speed bump and curb, ramp jump | PASS | 21/21 numeric checks pass in 64.2 s |
| 9 | 4.13 0-100 km/h: 3.5-4.0 s | PASS | 3.945 s (band 2.975-4.6 s); 1-ft rollout like the published figures; 4.31 s from the throttle application |
| 10 | 4.13 top speed: 290-320 km/h (stock ~314) | PASS | 282.5 km/h (band 246.5-368 km/h); asymptote of the acceleration vs speed of a full-throttle run from 270 km/h |
| 11 | 4.13 100-0 km/h braking: 33-38 m | PASS | 33.47 m (band 28.05-43.7 m); ABS on, asphalt |
| 12 | 4.13 skidpad: 0.85-1.0 g | PASS | 0.943 g (band 0.7225-1.15 g); R 45.7 m (300 ft), highest 2 s mean a_y on the circle without sliding |
| 13 | 4.13 weight transfer: visible dive, squat, roll | PASS | dive 3.9 deg (100-0 km/h), squat 2.1 deg (launch), roll gradient 3.19 deg/g |
| 14 | 4.13 controllable: no self-oscillation, no flipping, recoverable slides, balance; easy wheelspin | PASS | T12 straight-line stability at top speed (robot steering): 0.681 deg/s; T12 open-loop straight line: 0.451 deg; T13 ABS keeps the car steerable: 4.39 ; T14 slalom: 0.989 deg; T14 slalom: 0.0454 m; T14 figure eight: 2.07 deg; T14 ramp jump: 0.469 deg; T14 ramp jump: 0.243 deg; T12 wheelspin on launch (traction control off): 6.08 ; understeer gradient 3.7 deg/g (understeer) |
| 15 | P3 suite (tests 1-8, energy drift, determinism) re-run after the P3b changes | PASS | run 2026-10-15T22:11:51Z, failing: none |
| 16 | exact stability S < 2.5 on the current skeleton (D-024) | PASS | S = 2.4403 (2107 nodes, 11399 beams) |
| 17 | vehicle data in sync with the Unity StreamingAssets copy | PASS | sim\vehicle\hellcat -> Unity\HellcatSandbox\Assets\StreamingAssets\Vehicles\hellcat: identical |
| 18 | dynamics report with plots | PASS | docs\dynamics_report.md 40,419 bytes, 14 plots in docs/p3b/plots |
