# Gate P1b (G-Interior)

Result: **PASS** (0 FAIL, 1 WARN, 11 checks)

| # | Check | Status | Detail |
|---|---|---|---|
| 1 | all interior parts present and named (CH_Int_*) | PASS | 35 objects; missing none; bad names none |
| 2 | every interior mesh has a material and UVs | PASS | no material: none; no UV: none |
| 3 | interior triangle budget 150k-400k | PASS | 162,596 triangles; largest: SteeringWheel 23,014, Seat_FL 15,480, Seat_FR 15,480, Seat_Rear 11,678, Carpet 10,504, Console 9,592 |
| 4 | no clipping: no unexpected intersections (interior x interior and x exterior), no coincident faces | PASS | unexpected none; coincident none; 20 contacts by design (mounted parts, parts resting on the carpet, belts) |
| 5 | cockpit camera clear of geometry (near clip 0.01 m) | PASS | nearest geometry to the eye point: CH_Int_Seat_FL at 0.2082 m |
| 6 | gauges respond to test values (0 / 3000 / 6000 rpm, 0 / 100 / 200 mph) | PASS | tach 0: -120.0 deg (expected -120.0); speedo 0: -120.0 deg (expected -120.0); tach 3000: -17.14 deg (expected -17.14); speedo 100: -0.0 deg (expected 0.0); tach 6000: 85.71 deg (expected 85.71); speedo 200: 120.0 deg (expected 120.0); renders 2026-10-11_P1b_gauges_*.png |
| 7 | steering wheel rotates about the column axis with the steering input | PASS | -90.0 deg -> rim top at -90.0 deg, off-plane -0.0 mm; 0.0 deg -> rim top at 0.0 deg, off-plane 0.0 mm; 90.0 deg -> rim top at 90.0 deg, off-plane 0.0 mm; 468.0 deg -> rim top at 108.0 deg, off-plane -0.0 mm; renders 2026-10-11_P1b_steer_*.png and the cockpit animation |
| 8 | layout matches the reference (wheel, cluster, centre screen, vents, start button, console) - camera fitted to reference/Interior 2.jpg | PASS | fit on 9 landmarks: RMS 17.1 px (0.89 % of the width), lens 41.2 mm eq.; residuals (px): wheel_badge 4.2, tach_centre 2.1, speedo_centre 24.8, screen_tl 22.2, screen_tr 13.6, screen_bl 15.2, screen_br 22.1, vent_left 20.4, vent_right 13.5, start_button 12.0, knob_left 12.1, knob_right 33.2, shifter_top 61.0; overlay docs/p1b/photo_cams/overlay_cabin2.jpg |
| 9 | driver eye point and field of view | PASS | eye [-0.375, -0.36, 1.12] m (z 1.12 m: brief 1.05-1.10, SAE estimate 1.16 +- 0.05, decision D-020), horizontal FOV 85.0 deg (configurable in Unity) |
| 10 | mirrors show the scene behind the car | WARN | needs the Unity runtime: render-texture cameras on CH_Int_Mirror / CH_Mirror_Glass_L/R are implemented and verified in P4b (cockpit.json carries the mirror frames) |
| 11 | evidence: driver-view screenshots, cut-aways, gauge and steering renders, cockpit animation | PASS | 13 stills, videos: 2026-10-11_P1b_cockpit_gauges_steering_720p24.mp4 |
