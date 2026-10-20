# Gate P3 (G-Solver)

Vehicle `hellcat`. Result: **PASS** (0 FAIL, 0 WARN, 18 checks)

| # | Check | Status | Detail |
|---|---|---|---|
| 1 | full validation run with every required test | PASS | run 2026-10-15T22:11:51Z, quick=False, tests T1, T2, T3, T4, T5, T6, T7, T8, E1, D1; missing: none |
| 2 | results newer than the vehicle data and the solver sources | PASS | results 2026-10-15 22:11:51 UTC, newest input sim\vehicle\hellcat\params.json 2026-10-15 21:09:36 UTC |
| 3 | test 1: Single beam: frequency, damping, static stretch and compression | PASS | 6/6 numeric checks pass in 0.7 s |
| 4 | test 2: Pendulum and hanging chain: period and energy | PASS | 3/3 numeric checks pass in 0.4 s |
| 5 | test 3: Cube with and without diagonal bracing | PASS | 2/2 numeric checks pass in 0.0 s |
| 6 | test 4: Force-displacement: tensile cycle and falling-mass crush | PASS | 10/10 numeric checks pass in 0.1 s |
| 7 | test 5: Rigid box: drop on the ground, rest and slide on slopes | PASS | 6/6 numeric checks pass in 0.1 s |
| 8 | test 6: Hellcat: drop from 0.2 m, settle, rest | PASS | 26/26 numeric checks pass in 17.9 s |
| 9 | test 7: Hellcat: locked-wheel stop from 50 km/h and lateral slide | PASS | 2/2 numeric checks pass in 3.2 s |
| 10 | test 8: Tunnelling at 120 km/h: 20 cm static wall, node-beam wall | PASS | 6/6 numeric checks pass in 1.8 s |
| 11 | energy drift without impact < 1 % over 10 s (damping on: mechanical + dissipated; off: mechanical) | PASS | free Hellcat, damping on: /drift of (mechanical + dissipated)/, 1 s windows, 10 s = 9.97e-05; free Hellcat, damping off: /drift of the mechanical energy/, 1 s windows, 10 s = 0.000198 |
| 12 | angular momentum conserved in free flight (< 0.1 %) | PASS | damping on: angular momentum error = 0.00027; damping off: angular momentum error = 0.000623 |
| 13 | deterministic re-run matches (bit-identical, parallel and single-thread) | PASS | re-run with the same inputs gives bit-identical node states (parallel): 1; single-thread run gives bit-identical node states: 1 |
| 14 | exact stability S < 2.5 on the built world (D-024) and the C# / Python agreement | PASS | S = 2.4418 (<= 2.5); beams-only S = 2.4413 vs Python 2.4403 +- 2 % |
| 15 | physics time per substep within the 2 kHz real-time budget | PASS | 240.0 us (<= 500) |
| 16 | vehicle data in sync with the Unity StreamingAssets copy | PASS | sim\vehicle\hellcat -> Unity\HellcatSandbox\Assets\StreamingAssets\Vehicles\hellcat: identical |
| 17 | global body stiffness at or above the D-040 floor (torsion >= 5 kN m/deg, bending >= 1.5 kN/mm) | PASS | torsion 6.833 kN m/deg, bending 1.776 kN/mm (real cars ~15-35 / ~10-20: the 2 kHz stability limit, D-040) |
| 18 | validation report written | PASS | docs\validation_report.md 27,006 bytes |
