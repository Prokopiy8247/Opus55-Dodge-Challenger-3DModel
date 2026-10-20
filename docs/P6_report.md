# P6 report: all scripted scenarios, driven runs and tuning

Gate G-Crash (P6): **PASS** (0 FAIL, 1 WARN, 38 checks, `docs/gates/gate_p6.md`).

**What P6 delivers.** The eight scripted scenarios of brief 9 now run on the test map's lanes (D-084), each from one command line in the
test-map player (`-scenario S1` ... `S8`), and every one of them, at three or more speeds, is measured, recorded, captured and
replayed:

- **Measured** per frame and at 1 kHz near the obstacle: the cabin pulse (filtered CFC 60 in `tools/gate_p6.py`), crush, the
  structure's deformation and the intrusion into the passenger cell at IIHS-like points (D-089), broken beams by material,
  detached parts, the full energy ledger including the work of the engine and the air (D-092), tunnelling, the skinning
  checks; per kind also the sliding contact (S4, S6), the flight and the landing (S5), the debris moved (S7).
- **Recorded**: the run's inputs with a world snapshot at the start (`sim/cache/<S>/kmh<v>/<run>.hrec`, the F5 format).
- **Captured**: four cameras in real time (tracking, side, three-quarter, top; 6-10 s at 60 fps).
- **Replayed**: after the run the saved recording is read back and replayed from its snapshot; the event is re-rendered at
  250 fps from three cameras (the slow-motion variant), and the replay's end state is compared bit for bit with the run's
  (D-086). All 24 scripted runs replay identically, including the debris runs with 46 props in the world.
- **Driven variants**: each scenario is also driven through the game's own controls - the pause-menu teleport at V with the
  speed hold - recorded with F5 and replayed with F6 (D-087).

**Interpretations** (decisions): S3's pole "aimed at the front axle" is a centred frontal pole impact (D-085; the wheel-line
variant glances off like a small-overlap test); the O2 wall is rigid, so S2 is harsher than the IIHS deformable-barrier test
it is compared with.

## Calibration against the car's own NCAP test (brief 15.2)

Reference: NHTSA NCAP frontal test of a 2013 Dodge Challenger SXT (report NCAP-MGA-2013-030, `docs/p6/refs`), 56.4 km/h into a
rigid full-width barrier - the same body as the Hellcat, about 90 kg lighter. The front crush characteristic (rails, rail braces,
crash cans) was scaled x0.7 to match its static crush (D-096; tuning rows P6-006a-c in `docs/tuning_log.csv`). The numbers
below are the final car (P7: hood crease strip at 0.3, D-104; the whole series run again on the final build).

| quantity | NCAP 2013 Challenger SXT | model, S1 at 56 km/h |
|---|---|---|
| test mass, impact speed | 1948 kg, 56.4 km/h | 2040 kg, 55.9 km/h |
| static crush at bumper level (C1..C6) | 573-642 mm, mean 608 mm | 574 mm (bumper beam set-back 425 mm + 149 mm fascia stand-off) |
| largest static crush (centre line) | 740 mm | 671 mm (bumper beam centre 522 mm + 149 mm) |
| cabin pulse | - (not in the report's data sheets) | 51 g peak (CFC 60), cabin at rest after 64 ms, mean 25 g |
| rebound | 2.67 m/s | 4.0 m/s |
| wheelbase | 155 / 149 mm shorter | not shortened (reading -22 / -19 mm, within its +-20 mm pose noise) |
| door openings | 1-6 mm narrower after the test | up to 6 / 7 mm during the crash |
| doors | closed during the impact, operable | latches hold (latch force up to 1.3 kN) |

The crush is inside the NCAP band (at its low end: with the stiffer hood strip of D-104 the residual set-back came out
41 mm shorter than the 615 mm of the calibration run; the sweep shows the residual measure moving by a few cm with small
changes, the dynamic crush - 0.563 m - by less than 1 cm); the rebound and the wheelbase do not match: the front tyres reach the wall at about 0.55 m of cabin travel and
the tyre / knuckle / arm path holds them instead of letting them be pushed back into the wheel wells, so the car stops a little
earlier and the tyres spring it back. The sweep shows the same: the rail thresholds hardly change the crash, the tyre pressure
and the dampers do (open point 2).

**Offset frontal (S2 at 64 km/h, brief 15.2 IIHS-style).** 40 % overlap on the driver side into the rigid O2 wall (IIHS uses a
deformable honeycomb barrier, so this run is the harsher one): the struck side crushes 1.00 m against 0.31 m on the other,
the struck wheel is driven back (left wheelbase 128 mm shorter), the car yaws off the wall. IIHS structure measures (static,
against the rear cabin): firewall 8.0 cm, upper hinge pillar 1.0 cm, steering column 0.3 cm, rocker, toe pan and dash 0.1 cm
or less: the 'good' band (up to 15 cm). The latches hold; the struck door's aperture distorts by up to 23 mm during the crash.

## What the scenarios show

- **S1 full frontal, 30-64 km/h**: bumper beam, crash cans and front rails crumple (dynamic crush 0.28 / 0.40 / 0.51 / 0.56 /
  0.63 m, residual 0.23 / 0.32 / 0.41 / 0.43 / 0.51 m, plastic work 37 / 73 / 121 / 149 / 178 kJ), the hood folds at its
  crease strip and rises 0.32-0.39 m, the headlamps stay on their ductile brackets, no structural beam breaks, the cabin
  stays intact (intrusion 0.3 cm or less, latches closed, roof 3 cm). Peaks 33 / 39 / 45 / 51 / 84 g (CFC 60) in 56-69 ms
  pulses: at 64 km/h the tyres and the engine bay are crushed solid and the pulse stiffens.
- **S3 centred pole, 30-50 km/h**: the pole drives the bumper beam's middle back 0.59 / 0.79 / 0.98 m - twice the wall's
  0.50 m at 50 km/h - and the cabin travels 1.02 m before it stops; the pulse is long and soft, as pole impacts
  are (22 g CFC 60 over 124 ms); at 50 km/h the pole reaches the hood latch, which tears, and the hood springs open (0.71 m);
  the passenger cell is not reached (intrusion 0.3 cm).
- **S8 full frontal at 120 km/h**: 1.13 m dynamic and 0.80 m residual crush, 607 kJ of plastic work (5.0 times S1 50), the
  front wheels driven back 30-32 cm, both mirrors torn off, the hood latch torn, the roof skin buckles 11 cm, the door
  apertures distort by up to 25 mm; 144 g peak (CFC 60) in a 56 ms pulse. The passenger cell keeps its shape (static intrusion
  2.9 cm at the firewall, 9.7 cm during the pulse) - see open point 1.
- **S4 barrier row at 20 deg, 30-50 km/h**: the left front corner meets the F-shape barriers and the car slides along them for
  0.4-0.5 s and glances off; the struck wheel breaks its tie rod and a subframe mount at every speed, plastic work 0.8 / 2.4 /
  10.9 kJ.
- **S5 ramp and landing, 60-80 km/h**: airborne 0.90 / 1.06 / 1.17 s over 14 / 19 / 24 m (the ballistic estimate from the
  take-off speed within 10 %), landing at 5.1-6.1 m/s vertical (14-17 g CFC 60) with 21-30 underbody nodes on the pad; no beam
  breaks (the closure stops hold, D-095), 2-9 kJ of plastic work in the suspension and the underbody.
- **S6 guardrail scrape at 10 deg, 50-70 km/h**: sliding contact of 0.2 / 0.36 / 0.78 s; at 70 km/h the rail tears 108
  supports and 8 clips of the bumper fascia and the wheel-arch flare (partial detachment), plastic work 0.4 / 0.7 / 3.3 kJ.
- **S7 debris, 10-20 km/h**: 35-36 of the 46 props move (thrown up to 15 / 20 / 20 m); light damage (1.7-2.0 kJ), most of it
  from the fence panels at the far end of the field - at 20 km/h a panel tears the left mirror off, at 10 and 15 km/h the car
  meets them differently, so the series is not monotonic (a gate warning).

## Open points

1. **S8 passenger cell.** At 120 km/h the cell deforms less than a real car's would (3 cm static intrusion against tens of cm):
   the front wheels driven back 30-32 cm do not load the hinge pillars, because the tyres do not collide with their own car's
   body (self-collision is on only for the detachable parts, D-058); the cage beams are not reached by the crushed front.
2. **NCAP rebound and wheelbase** (above): a yielding wheel path (lower-arm and subframe mounts that let the wheel move back)
   would bring both closer; not attempted in P6 because the crush, the pulse and the cabin already match.
3. **Hood mesh.** The hood skeleton has rows every 0.17 m; with the crease strip (D-095) it folds at the front instead of
   arching, but it still deforms in a few large facets. At the pole (S3) the struck strip folds round the pole by up to 156 deg
   within one 60 fps frame (`docs/p6/s3_hood_fold_top.jpg`), so the gate reports S3 apart from the frame-flip criterion.
4. **Stretched panels at 120 km/h.** Where the fenders and the roof edge tear (S8), their skinned meshes stretch into sheets
   between the nodes; there is no mesh tearing in the renderer.
5. **Glass** renders nearly transparent (P7 polish item); the debris props are drawn rigid on their best-fit frames (P5).
6. **Inner suspension nodes** do not collide with the ground: where a subframe mount breaks (S4 at 50 km/h) or a short jump
   lands nose-down (S5 at 60 km/h) the front lower-arm pivot dips 2-5 cm below the surface; the nodes that collide never do.

## Gate criteria refined on the final series (D-097)

The G-Crash criteria were written before the scenarios existed. The final series showed six places where a criterion measured
something other than the brief's intent; each was refined with its evidence, and the raw values stay in the gate's detail
column: the energy-creation tolerance now scales with the kinetic energy at the contact (the ledger value it used is relative
and negative); "under the ground" counts the nodes that collide with the ground (an inner lower-arm pivot dips 2-5 cm in S4 50
and S5 60, reported); the frame-flip proxy covers the distributed-load runs and reports the pole runs with S8 (the hood strip
the pole stops folds round it within one frame, `docs/p6/s3_hood_fold_top.jpg`); the largest deformation of the glancing and
light runs may stay level within 1 cm; the debris series' non-monotonic damage is a warning; S8's 5.98 s capture counts as
"about 6 s".

## Per-scenario summary (brief speeds)

Cabin centre of mass filtered CFC 60 (SAE J211). Crush: cabin travel after the contact (dynamic) and the bumper beam's set-back at rest (residual, struck side for S2 / S3). Deformation: largest structure-node displacement against the rigid rear cabin. Intrusion: largest rearward displacement of the IIHS-like points. Broken beams exclude closure stops letting go (D-088).

| scenario | entry km/h | crush dyn / res m | deformation m | peak g (long / resultant) | pulse ms | broken | plastic kJ | detached | intrusion cm | event |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 full frontal, O1 wall | 50.1 | 0.51 / 0.405 | 0.499 | 44.7 / 45.1 | 68 | 0 | 120.87 | - | 0.2 | - |
| S2 40 % offset frontal, O2 wall | 63.9 | 0.77 / 0.996 | 0.724 | 59.8 / 62.4 | 89 | 2 | 172.79 | - | 8 | - |
| S3 centred pole O3 (front axle) | 50 | 1.02 / 0.241 | 0.978 | 22.1 / 22.1 | 124 | 12 | 111.07 | - | 0.3 | - |
| S4 barrier row O4 at 20 deg | 40.1 | - / 0.134 | 0.0969 | 4.2 / 5 | - | 2 | 2.37 | - | 0 | sliding 0.43 s, leaves at 14.8 km/h, 38.6 deg |
| S5 ramp O6 and landing | 79.9 | - / -0.0094 | 0.128 | 7.5 / 8.5 | - | 0 | 8.75 | - | 0.1 | airborne 1.17 s over 23.6 m, landing -6.13 m/s, 15 g vertical |
| S6 guardrail O5 scrape at 10 deg | 69.9 | - / -0.011 | 0.0459 | 5.3 / 5.9 | - | 116 | 3.27 | - | 0 | sliding 0.782 s, leaves at 35.2 km/h, -8.69 deg |
| S7 debris O8 push-through | 15.1 | - / 0.003 | 0.0396 | 0.6 / 0.6 | - | 0 | 1.96 | - | 0 | 36 props moved (up to 19.6 m) |
| S8 full frontal 120 km/h, O1 wall | 119 | 1.12 / 0.797 | 0.998 | 144 / 145 | 56 | 65 | 606.5 | mirror_L+mirror_R | 2.9 | - |

Full table with the speed series: `docs/p6/scenario_summary.md` / `.csv`.

## Damage against speed

| scenario | km/h | entry | crush dyn / res m | deformation m | plastic kJ | broken | detached |
|---|---|---|---|---|---|---|---|
| S1 | 30 | 29.8 | 0.285 / 0.23 | 0.342 | 36.75 | 0 | - |
| S1 | 40 | 39.9 | 0.402 / 0.317 | 0.433 | 73.46 | 0 | - |
| S1 | 50 | 50.1 | 0.51 / 0.405 | 0.499 | 120.87 | 0 | - |
| S1 | 56 | 55.8 | 0.563 / 0.425 | 0.522 | 148.59 | 0 | - |
| S1 | 64 | 63.9 | 0.631 / 0.51 | 0.611 | 177.66 | 0 | - |
| S2 | 40 | 39.6 | 0.534 / -0.104 | 0.517 | 69.76 | 0 | - |
| S2 | 56 | 55.9 | 0.682 / 0.0639 | 0.692 | 124.47 | 1 | - |
| S2 | 64 | 63.9 | 0.77 / 0.309 | 0.724 | 172.79 | 2 | - |
| S3 | 30 | 30 | 0.633 / 0.118 | 0.586 | 43.74 | 0 | - |
| S3 | 40 | 40 | 0.817 / 0.16 | 0.792 | 80.38 | 0 | - |
| S3 | 50 | 50 | 1.02 / 0.241 | 0.978 | 111.07 | 12 | - |
| S4 | 30 | 30.1 | - / 0.0154 | 0.0618 | 0.75 | 2 | - |
| S4 | 40 | 40.1 | - / 0.134 | 0.0969 | 2.37 | 2 | - |
| S4 | 50 | 50.1 | - / 0.202 | 0.154 | 10.91 | 2 | - |
| S5 | 60 | 59.8 | - / 0.0038 | 0.0379 | 2.25 | 0 | - |
| S5 | 70 | 69.9 | - / -0.003 | 0.104 | 6.38 | 0 | - |
| S5 | 80 | 79.9 | - / -0.0094 | 0.128 | 8.75 | 0 | - |
| S6 | 50 | 49.9 | - / -0.038 | 0.0471 | 0.4 | 0 | - |
| S6 | 60 | 59.8 | - / -0.0301 | 0.0483 | 0.69 | 0 | - |
| S6 | 70 | 69.9 | - / -0.011 | 0.0459 | 3.27 | 116 | - |
| S7 | 10 | 10.1 | - / 0.0314 | 0.083 | 1.66 | 0 | - |
| S7 | 15 | 15.1 | - / 0.003 | 0.0396 | 1.96 | 0 | - |
| S7 | 20 | 19.8 | - / 0.0009 | 0.0435 | 1.67 | 18 | mirror_L |
| S8 | 120 | 119 | 1.12 / 0.797 | 0.998 | 606.5 | 65 | mirror_L+mirror_R |

![damage vs speed](p6/plots/damage_vs_speed.png)

![frontal pulses](p6/plots/frontal_pulses.png)

![event pulses](p6/plots/event_pulses.png)

![energy](p6/plots/energy_vs_time.png)

## Driven variants (teleport with the speed hold, F5 / F6)

| scenario | released at km/h | broken | deformation m | detached | recording | replay |
|---|---|---|---|---|---|---|
| S1 50 | 50 (released 1.0 m before the obstacle) | 6 | 0.526 | - | S1_50kmh_driven.hrec (10.4 s, 0.85 MB) | identical |
| S2 64 | 64 (released 1.0 m before the obstacle) | 8 | 0.838 | - | S2_64kmh_driven.hrec (9.33 s, 0.85 MB) | identical |
| S3 50 | 50 (released 1.0 m before the obstacle) | 5 | 0.992 | - | S3_50kmh_driven.hrec (10.4 s, 0.85 MB) | identical |
| S4 40 | 40 (released 1.0 m before the obstacle) | 2 | 0.0996 | - | S4_40kmh_driven.hrec (11.7 s, 0.85 MB) | identical |
| S5 80 | 79.2 (released 1.0 m before the obstacle) | 0 | 0.108 | - | S5_80kmh_driven.hrec (7.85 s, 0.85 MB) | identical |
| S6 70 | 69.4 (released 1.0 m before the obstacle) | 0 | 0.0166 | - | S6_70kmh_driven.hrec (8.75 s, 0.85 MB) | identical |
| S7 15 | 15 (run-up time over) | 0 | 0.0451 | - | S7_15kmh_driven.hrec (27.3 s, 0.85 MB) | identical |
| S8 120 | 118 (released 1.0 m before the obstacle) | 76 | 1.04 | mirror_L+mirror_R | S8_120kmh_driven.hrec (7.55 s, 0.85 MB) | identical |

## Sensitivity sweep (brief 15.5)

Each parameter at x0.8 and x1.2 of the tuned value, everything else unchanged; S1 at 56 km/h (NHTSA full-width frontal), S5 at 80 km/h (ramp landing). Values from the run results and the pulses (CFC 60, tools/gate_p6.py).

### S1 at 56 km/h

| parameter | scale | dynamic_crush_m | residual_crush_m | pulse_ms | peak_cfc60_g | plastic_kJ | broken_beams | max_deformation_m | intrusion_max_cm |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 1 | 0.551 | 0.359 | 65 | 55.5 | 141 | 0 | 0.424 | 1.2 |
| rail_deform | 0.8 | 0.559 | 0.406 | 64 | 54.1 | 145 | 0 | 0.505 | 0.7 |
| rail_deform | 1.2 | 0.546 | 0.385 | 65 | 56.5 | 136 | 0 | 0.516 | 0.2 |
| rail_strength | 0.8 | 0.551 | 0.359 | 65 | 55.5 | 141 | 0 | 0.424 | 1.2 |
| rail_strength | 1.2 | 0.551 | 0.359 | 65 | 55.5 | 141 | 0 | 0.424 | 1.2 |
| clip_strength | 0.8 | 0.551 | 0.359 | 65 | 55.5 | 141 | 0 | 0.424 | 1.2 |
| clip_strength | 1.2 | 0.551 | 0.359 | 65 | 55.5 | 141 | 0 | 0.424 | 1.2 |
| tire_pressure | 0.8 | 0.545 | 0.393 | 65 | 47.5 | 143 | 0 | 0.492 | 0.7 |
| tire_pressure | 1.2 | 0.555 | 0.461 | 65.5 | 53.6 | 147 | 0 | 0.596 | 0.2 |
| damper_rate | 0.8 | 0.55 | 0.399 | 64 | 51.4 | 139 | 0 | 0.531 | 0.1 |
| damper_rate | 1.2 | 0.564 | 0.457 | 66.5 | 56.7 | 146 | 0 | 0.602 | 0.1 |

### S5 at 80 km/h

| parameter | scale | airborne_s | landing_vy | peak_vertical_cfc60_g | underbody_contact | rim_contact | plastic_kJ | broken_beams | max_deformation_m |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 1 | 1.17 | -6.11 | 15.3 | 32 | 0 | 10 | 0 | 0.194 |
| tire_pressure | 0.8 | 1.16 | -6.03 | 16.5 | 32 | 0 | 10.5 | 0 | 0.195 |
| tire_pressure | 1.2 | 1.17 | -6.14 | 14.7 | 29 | 0 | 8.28 | 0 | 0.193 |
| damper_rate | 0.8 | 1.18 | -6.13 | 16.7 | 30 | 0 | 9.25 | 0 | 0.193 |
| damper_rate | 1.2 | 1.14 | -5.92 | 15.6 | 30 | 0 | 9.91 | 0 | 0.195 |

The sweep ran on the P6-005 parameters, before the front calibration x0.7 (D-096), which it informed: the rail yield alone (its cap unchanged) and the break strengths of rails and bumper clips hardly change the 56 km/h crash (no rail or clip breaks there), while the tyre pressure and the dampers move the peak and the rebound - the front wheels reach the wall. The calibrated car's S1 56 km/h is in the summary above (crush 0.567 m, peak 52 g).

## Captures

33 videos in `docs/video_assets/P6/` (stills of every camera at the event and at the end next to them):

- `2026-10-15_P6_S1_50kmh_grid.mp4`
- `2026-10-15_P6_S1_50kmh_side.mp4`
- `2026-10-15_P6_S1_50kmh_side_slowmo.mp4`
- `2026-10-15_P6_S1_50kmh_slowmo.mp4`
- `2026-10-15_P6_S2_64kmh_grid.mp4`
- `2026-10-15_P6_S2_64kmh_side.mp4`
- `2026-10-15_P6_S2_64kmh_side_slowmo.mp4`
- `2026-10-15_P6_S2_64kmh_slowmo.mp4`
- `2026-10-15_P6_S3_50kmh_grid.mp4`
- `2026-10-15_P6_S3_50kmh_side.mp4`
- `2026-10-15_P6_S3_50kmh_side_slowmo.mp4`
- `2026-10-15_P6_S3_50kmh_slowmo.mp4`
- `2026-10-15_P6_S4_40kmh_grid.mp4`
- `2026-10-15_P6_S4_40kmh_side.mp4`
- `2026-10-15_P6_S4_40kmh_side_slowmo.mp4`
- `2026-10-15_P6_S4_40kmh_slowmo.mp4`
- `2026-10-15_P6_S5_80kmh_grid.mp4`
- `2026-10-15_P6_S5_80kmh_side.mp4`
- `2026-10-15_P6_S5_80kmh_side_slowmo.mp4`
- `2026-10-15_P6_S5_80kmh_slowmo.mp4`
- `2026-10-15_P6_S6_70kmh_grid.mp4`
- `2026-10-15_P6_S6_70kmh_side.mp4`
- `2026-10-15_P6_S6_70kmh_side_slowmo.mp4`
- `2026-10-15_P6_S6_70kmh_slowmo.mp4`
- `2026-10-15_P6_S7_15kmh_grid.mp4`
- `2026-10-15_P6_S7_15kmh_side.mp4`
- `2026-10-15_P6_S7_15kmh_side_slowmo.mp4`
- `2026-10-15_P6_S7_15kmh_slowmo.mp4`
- `2026-10-15_P6_S8_120kmh_grid.mp4`
- `2026-10-15_P6_S8_120kmh_side.mp4`
- `2026-10-15_P6_S8_120kmh_side_slowmo.mp4`
- `2026-10-15_P6_S8_120kmh_slowmo.mp4`
- `2026-10-15_P6_scenarios_reel.mp4`

![scenarios](video_assets/P6/2026-10-15_P6_scenarios_sheet.jpg)

## Gate checks

| # | check | status |
|---|---|---|
| 1 | every scenario and speed of the series run on the test map (S1 30-64 and S8 120 km/h; S2-S7 three speeds each) | PASS |
| 2 | metrics table for every run (brief 9: cabin deceleration CFC 60, crush, broken beams, detached parts, energies vs time) | PASS |
| 3 | captures at the brief's speeds: side and tracking camera plus two more angles, about 6-10 s real time; slow-motion replay at >= 240 fps from >= 2 angles (brief 9 and 14) | PASS |
| 4 | reproducibility: each run's recording (.hrec, snapshot + inputs) replayed from the saved file gives the bit-identical end state (WorldState hash) | PASS |
| 5 | driven variant of every scenario (teleport at V with the speed hold, recorded F5, replayed F6 with the recorded frame partition): replay bit-identical (brief 9) | PASS |
| 6 | S1 / S8 damage monotonic in speed: dynamic_crush_m (increasing) | PASS |
| 7 | S1 / S8 damage monotonic in speed: residual_crush_m (increasing) | PASS |
| 8 | S1 / S8 damage monotonic in speed: plastic_kJ (increasing) | PASS |
| 9 | S1 / S8 damage monotonic in speed: broken_beams (non-decreasing) | PASS |
| 10 | S1 / S8 damage monotonic in speed: detached_count (non-decreasing) | PASS |
| 11 | S2 damage monotonic in speed: plastic work and largest deformation | PASS |
| 12 | S3 damage monotonic in speed: plastic work and largest deformation | PASS |
| 13 | S4 damage monotonic in speed: plastic work and largest deformation (level within 1 cm) | PASS |
| 14 | S5 damage monotonic in speed: plastic work (0.3 kJ allowance) and largest deformation (level within 1 cm) | PASS |
| 15 | S6 damage monotonic in speed: plastic work and largest deformation (level within 1 cm) | PASS |
| 16 | S7 damage monotonic in speed: plastic work (0.3 kJ allowance) and largest deformation (level within 1 cm) | WARN |
| 17 | S1 50 km/h crumples bumper, hood and front rails but keeps the cabin intact (brief 9) | PASS |
| 18 | S1 50 km/h in the brief's sanity range (around 0.5-0.7 m crush, tens of g) | PASS |
| 19 | S1 56 km/h in the brief's sanity range (around 0.5-0.7 m crush, tens of g) | PASS |
| 20 | brief 15 target: NHTSA-style 56 km/h full-width rigid barrier (crush ~0.5-0.8 m, peak ~30-50 g, pulse ~70-110 ms) | PASS |
| 21 | brief 15 target: IIHS-style 64 km/h 40 % offset (driver side; rigid wall, conservative): struck side crushes, cabin intrusion rated by the IIHS structure bands | PASS |
| 22 | S8 120 km/h clearly more severe than S1 50: more plastic work and crush, cabin damage, parts detach (brief 9) | PASS |
| 23 | S3 centred pole at 50 km/h: deep intrusion - the pole drives the front in far deeper than the full-width wall at the same speed (brief 9) | PASS |
| 24 | S4 barrier row O4 at 20 deg at 40 km/h: sliding contact along the obstacle, the car glances off (brief 9) | PASS |
| 25 | S6 guardrail O5 scrape at 10 deg at 70 km/h: sliding contact along the obstacle, the car glances off (brief 9) | PASS |
| 26 | S5 ramp O6 at 80 km/h: flight time matches the ballistic estimate within 20 %; the landing loads suspension and underbody (brief 9) | PASS |
| 27 | S7 debris at 10-20 km/h: barrels move, light damage (brief 9) | PASS |
| 28 | no energy created after the contact (kinetic + stored + dissipated - drive and aero work never rises by more than 0.5 % of the kinetic energy at the contact; statics passive) | PASS |
| 29 | no tunnelling: no colliding node inside or through the obstacle at any frame (10-120 km/h), none more than 2 cm under the ground, no non-finite value | PASS |
| 30 | physics time per substep within the 2 kHz real-time budget during the scenarios | PASS |
| 31 | explicit-step criterion S below 2.5 in every run | PASS |
| 32 | no spikes: no node frame joined to the cabin turns more than 120 deg between two frames (linear blend skinning stays inside its bones' rigid motions; P4 criterion) in the distributed-load runs S1, S2, S4-S7; the pole and 120 km/h runs reported | PASS |
| 33 | no mesh inversion in the cabin (S1-S7): outside the impact pulse no cabin mesh turns more than 25 cm2 over against its own skinning transform (P4 criterion); S8 reported | PASS |
| 34 | pre-fractured glass swaps in when the panes' glass beams break (brief 7) | PASS |
| 35 | sensitivity sweep on the 5 most influential parameters at x0.8 / x1.2 with the effects reported (brief 15.5) | PASS |
| 36 | tuning log: P6 parameter changes with their metrics in docs/tuning_log.csv (brief 15.4) | PASS |
| 37 | plots: frontal pulses (CFC 60), event pulses (S4-S7), energy vs time per scenario, damage vs speed | PASS |
| 38 | P6 report written | PASS |

Details per check: `docs/gates/gate_p6.md`.

