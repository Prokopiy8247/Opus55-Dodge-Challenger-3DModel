# P6 scenario summary

Scripted runs on the test map (CarCrashScenario; tools/p6/run_scenarios.ps1). Peaks are the cabin centre of mass filtered CFC 60 (SAE J211) from the 1 kHz pulse: longitudinal deceleration along the lane, resultant, and for S5 the vertical landing peak (kinematic; an accelerometer reads 1 g more). Crush: cabin travel after the contact (dynamic) and the front structure's shortening at rest (residual). Deformation: largest displacement of a structure node from the rigid pose of the rear cabin. Intrusion: largest rearward displacement of the IIHS-like points (hinge pillars, rocker, toe pan, firewall, dash, steering column) against the rear cabin.

| scenario | km/h (entry) | crush dyn / res m | deformation m | peak long / res g | pulse ms | broken | plastic kJ | detached | intrusion max cm | event | replay |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 full frontal, O1 wall | 30 (29.8) | 0.285 / 0.23 | 0.342 | 33.3 / 33.5 | 63 | 0 | 36.75 | - | 0.2 | - | identical |
| S1 full frontal, O1 wall | 40 (39.9) | 0.402 / 0.317 | 0.433 | 39.3 / 39.4 | 69 | 0 | 73.46 | - | 0.3 | - | identical |
| S1 full frontal, O1 wall | 50 (50.1) | 0.51 / 0.405 | 0.499 | 44.7 / 45.1 | 68 | 0 | 120.87 | - | 0.2 | - | identical |
| S1 full frontal, O1 wall | 56 (55.8) | 0.563 / 0.425 | 0.522 | 51.3 / 51.3 | 64 | 0 | 148.59 | - | 0 | - | identical |
| S1 full frontal, O1 wall | 64 (63.9) | 0.631 / 0.51 | 0.611 | 84.3 / 85.3 | 56 | 0 | 177.66 | - | 0.2 | - | identical |
| S2 40 % offset frontal, O2 wall | 40 (39.6) | 0.534 / -0.104 | 0.517 | 26.2 / 27.7 | 94 | 0 | 69.76 | - | 0.2 | - | identical |
| S2 40 % offset frontal, O2 wall | 56 (55.9) | 0.682 / 0.0639 | 0.692 | 55.2 / 58.8 | 81 | 1 | 124.47 | - | 1.4 | - | identical |
| S2 40 % offset frontal, O2 wall | 64 (63.9) | 0.77 / 0.309 | 0.724 | 59.8 / 62.4 | 89 | 2 | 172.79 | - | 8 | - | identical |
| S3 centred pole O3 (front axle) | 30 (30) | 0.633 / 0.118 | 0.586 | 10.6 / 10.8 | 132 | 0 | 43.74 | - | 0.5 | - | identical |
| S3 centred pole O3 (front axle) | 40 (40) | 0.817 / 0.16 | 0.792 | 18.5 / 18.6 | 141 | 0 | 80.38 | - | 0.3 | - | identical |
| S3 centred pole O3 (front axle) | 50 (50) | 1.02 / 0.241 | 0.978 | 22.1 / 22.1 | 124 | 12 | 111.07 | - | 0.3 | - | identical |
| S4 barrier row O4 at 20 deg | 30 (30.1) | - / 0.0154 | 0.0618 | 3.8 / 4.2 | - | 2 | 0.75 | - | 0 | contact 0.41 s, exit 18.2 km/h at 14.3 deg | identical |
| S4 barrier row O4 at 20 deg | 40 (40.1) | - / 0.134 | 0.0969 | 4.2 / 5 | - | 2 | 2.37 | - | 0 | contact 0.43 s, exit 14.8 km/h at 38.6 deg | identical |
| S4 barrier row O4 at 20 deg | 50 (50.1) | - / 0.202 | 0.154 | 7.7 / 8.5 | - | 2 | 10.91 | - | 0.1 | contact 0.52 s, exit 20.1 km/h at 43.4 deg | identical |
| S5 ramp O6 and landing | 60 (59.8) | - / 0.0038 | 0.0379 | 5.3 / 5.7 | - | 0 | 2.25 | - | 0.1 | airborne 0.90 s over 13.8 m, landing 14.4 g vertical | identical |
| S5 ramp O6 and landing | 70 (69.9) | - / -0.003 | 0.104 | 6.4 / 7.9 | - | 0 | 6.38 | - | 0.1 | airborne 1.06 s over 18.8 m, landing 16.5 g vertical | identical |
| S5 ramp O6 and landing | 80 (79.9) | - / -0.0094 | 0.128 | 7.5 / 8.5 | - | 0 | 8.75 | - | 0.1 | airborne 1.17 s over 23.6 m, landing 15.0 g vertical | identical |
| S6 guardrail O5 scrape at 10 deg | 50 (49.9) | - / -0.038 | 0.0471 | 2.5 / 3.4 | - | 0 | 0.4 | - | 0 | contact 0.20 s, exit 41.4 km/h at -7.45 deg | identical |
| S6 guardrail O5 scrape at 10 deg | 60 (59.8) | - / -0.0301 | 0.0483 | 3.6 / 4.3 | - | 0 | 0.69 | - | 0 | contact 0.36 s, exit 44.2 km/h at -15.8 deg | identical |
| S6 guardrail O5 scrape at 10 deg | 70 (69.9) | - / -0.011 | 0.0459 | 5.3 / 5.9 | - | 116 | 3.27 | - | 0 | contact 0.78 s, exit 35.2 km/h at -8.69 deg | identical |
| S7 debris O8 push-through | 10 (10.1) | - / 0.0314 | 0.083 | 0.4 / 0.4 | - | 0 | 1.66 | - | 0 | 36 props moved (up to 14.9 m) | identical |
| S7 debris O8 push-through | 15 (15.1) | - / 0.003 | 0.0396 | 0.6 / 0.6 | - | 0 | 1.96 | - | 0 | 36 props moved (up to 19.6 m) | identical |
| S7 debris O8 push-through | 20 (19.8) | - / 0.0009 | 0.0435 | 1 / 1 | - | 18 | 1.67 | mirror_L | 0 | 35 props moved (up to 20 m) | identical |
| S8 full frontal 120 km/h, O1 wall | 120 (119) | 1.12 / 0.797 | 0.998 | 144 / 145 | 56 | 65 | 606.5 | mirror_L+mirror_R | 2.9 | - | identical |
