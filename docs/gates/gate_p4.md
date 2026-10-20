# Gate P4 (G-Crash)

Result: **PASS** (0 FAIL, 0 WARN, 22 checks), 2026-10-14T18:57:25Z

| # | check | status | detail |
|---|---|---|---|
| 1 | metrics table for every run (brief 9: deceleration, crush, broken beams, detached parts, energies) | PASS | 6 runs -> docs\p4\crash_metrics.csv |
| 2 | damage monotonic in speed: dynamic_crush_m (increasing) | PASS | 30 km/h 0.279, 40 km/h 0.3962, 50 km/h 0.4902, 56 km/h 0.5682, 64 km/h 0.622, 120 km/h 1.1267 |
| 3 | damage monotonic in speed: residual_crush_m (increasing) | PASS | 30 km/h 0.1881, 40 km/h 0.2543, 50 km/h 0.3703, 56 km/h 0.4496, 64 km/h 0.4519, 120 km/h 0.7515 |
| 4 | damage monotonic in speed: plastic_kJ (increasing) | PASS | 30 km/h 32.1, 40 km/h 62.5, 50 km/h 110.8, 56 km/h 142.5, 64 km/h 165.5, 120 km/h 590.4 |
| 5 | damage monotonic in speed: broken_beams (non-decreasing) | PASS | 30 km/h 33, 40 km/h 34, 50 km/h 34, 56 km/h 47, 64 km/h 52, 120 km/h 104 |
| 6 | detached parts non-decreasing in speed | PASS | 30 km/h 2 (headlight_L+headlight_R), 40 km/h 2 (headlight_L+headlight_R), 50 km/h 2 (headlight_L+headlight_R), 56 km/h 2 (headlight_L+headlight_R), 64 km/h 2 (headlight_L+headlight_R), 120 km/h 4 (headlight_L+headlight_R+mirror_L+mirror_R) |
| 7 | S1 50 km/h in the brief's sanity range (around 0.5-0.7 m crush, tens of g) | PASS | dynamic crush 0.490 m, residual 0.370 m, peak 44.8 g CFC 60 (45.76 g raw 4 ms), mean 20.0 g over 70.0 ms |
| 8 | S1 56 km/h in the brief's sanity range (around 0.5-0.7 m crush, tens of g) | PASS | dynamic crush 0.568 m, residual 0.450 m, peak 46.8 g CFC 60 (49.98 g raw 4 ms), mean 23.4 g over 67.0 ms |
| 9 | S1 50 km/h crumples bumper, hood and front rails but keeps the cabin intact (brief 9) | PASS | residual crush 0.370 m, hood buckled 0.46 m up, roof skin 0.034 m, door latches closed; plastic work front 108.4 / cabin 0.1 / rear 0.0 kJ (X21, 50 km/h) |
| 10 | closures (D-063): the doors stay latched in every S1 run; door offsets from the cabin's rigid motion reported | PASS | S1 30 km/h door 0.024 m / roof skin rise 0.024 m, S1 40 km/h door 0.033 m / roof skin rise 0.029 m, S1 50 km/h door 0.032 m / roof skin rise 0.034 m, S1 56 km/h door 0.034 m / roof skin rise 0.031 m, S1 64 km/h door 0.064 m / roof skin rise 0.037 m, S8 120 km/h door 0.196 m / roof skin rise 0.094 m |
| 11 | S8 120 km/h clearly more severe than S1 50 km/h | PASS | plastic 590.4 vs 110.8 kJ, crush 1.13 vs 0.49 m, detached headlight_L+headlight_R+mirror_L+mirror_R |
| 12 | no energy created after the contact (kinetic + stored + dissipated never rises; wall and ground passive) | PASS | 30 km/h 0.0 J, 40 km/h 0.0 J, 50 km/h 0.0 J, 56 km/h 0.0 J, 64 km/h 0.0 J, 120 km/h 0.0 J |
| 13 | no tunnelling: no colliding node past the wall face at any frame, no non-finite node | PASS | 0 at every speed (30-120 km/h) |
| 14 | X21 solver diagnostic present (contact and structure variants, energy balance) | PASS | S1 configuration created 0 J; without D-055 0 J; without D-056 rebound 5.279979762710456 m/s |
| 15 | at rest the skinned meshes reproduce the originals within 1 mm (bind pose, every vertex) | PASS | 165 objects, 572,039 vertices: worst bind error 0.0005 mm (CH_Spoiler), axis error 0.0002 mm |
| 16 | no spikes (S1): linear blend skinning keeps every vertex inside the rigid motions of its bones, so a spike needs a bone frame that flips - no node frame joined to the cabin turns more than 120 deg between two frames (60 fps) | PASS | S1 30 km/h 50.9 deg (0290_bbF_f_C), S1 40 km/h 58.5 deg (0316_bbF_t76_L), S1 50 km/h 70.7 deg (0290_bbF_f_C), S1 56 km/h 84.6 deg (0800_fender_L_6_2), S1 64 km/h 94.7 deg (0266_frail4_2_R), S8 120 km/h 144.2 deg (0267_frail4_3_R) (S8 for reference: a front rail folding at 33 m/s) | largest vertex move per frame (brief 7): 30 km/h 286 mm, 40 km/h 392 mm, 50 km/h 489 mm, 56 km/h 570 mm, 64 km/h 628 mm, 120 km/h 1061 mm (the spinning tires at speed; see the report) |
| 17 | no mesh inversion in the cabin (S1): outside the impact pulse (before the contact and from 150 ms after it) no cabin mesh turns more than 25 cm2 (a 5 x 5 cm patch, about the smallest the cockpit camera resolves) over against its own blended skinning transform; transient trim folds in the pulse and the crushed ends reported | PASS | S1 30 km/h cabin 9.2 cm2 (CH_FloorPan), in the pulse 9 cm2 (CH_FloorPan), crush zones 129 cm2 (CH_Fender_L), S1 40 km/h cabin 9.2 cm2 (CH_FloorPan), in the pulse 15 cm2 (CH_Int_SteeringWheel), crush zones 781 cm2 (CH_WheelLiners_L), S1 50 km/h cabin 9.2 cm2 (CH_FloorPan), in the pulse 85 cm2 (CH_Int_Sill_L), crush zones 1005 cm2 (CH_CoreSupport), S1 56 km/h cabin 9.2 cm2 (CH_FloorPan), in the pulse 23 cm2 (CH_Int_SteeringWheel), crush zones 2070 cm2 (CH_CoreSupport), S1 64 km/h cabin 9.4 cm2 (CH_Int_SteeringWheel), in the pulse 79 cm2 (CH_Int_Sill_R), crush zones 2637 cm2 (CH_Subframe_Front), S8 120 km/h cabin 125.9 cm2 (CH_Int_Sill_R), in the pulse 189 cm2 (CH_FloorPan), crush zones 2400 cm2 (CH_CoreSupport) |
| 18 | at least 3 camera angles per run (brief 14) | PASS | cameras ['chase', 'front34', 'side', 'top']; 6 runs with frames |
| 19 | pre-fractured glass swaps in when the panes' glass beams break (brief 7) | PASS | 6 of 6 panes shattered in the -breakGlass test |
| 20 | physics time per substep within the 2 kHz real-time budget during the crashes | PASS | 243-270 us per substep (budget 500) |
| 21 | P4 report written | PASS | docs\P4_report.md |
| 22 | plots: crash pulses (CFC 60), damage vs speed, S1 energy | PASS | docs\p4\plots |

## Metrics table

| run | impact km/h | dynamic / residual crush m | pulse ms | peak CFC 60 g (raw 4 ms) | mean g | rebound m/s | broken / plastic beams | plastic kJ | detached | energy created J |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 30 | 29.6 | 0.279 / 0.188 | 63 | 30.1 (32.96) | 13.2 | 1.82 | 33 / 406 | 32.1 | headlight_L+headlight_R | 0.0 |
| S1 40 | 39.8 | 0.396 / 0.254 | 72 | 36.5 (41.53) | 15.5 | 2.56 | 34 / 598 | 62.5 | headlight_L+headlight_R | 0.0 |
| S1 50 | 49.5 | 0.490 / 0.370 | 70 | 44.8 (45.76) | 20.0 | 2.59 | 34 / 757 | 110.8 | headlight_L+headlight_R | 0.0 |
| S1 56 | 55.4 | 0.568 / 0.450 | 67 | 46.8 (49.98) | 23.4 | 3.45 | 47 / 823 | 142.5 | headlight_L+headlight_R | 0.0 |
| S1 64 | 63.4 | 0.622 / 0.452 | 56 | 82.3 (86.85) | 31.5 | 4.83 | 52 / 1023 | 165.5 | headlight_L+headlight_R | 0.0 |
| S8 120 | 118.3 | 1.127 / 0.751 | 54 | 154.0 (175.61) | 63.2 | 4.09 | 104 / 2228 | 590.4 | headlight_L+headlight_R+mirror_L+mirror_R | 0.0 |
