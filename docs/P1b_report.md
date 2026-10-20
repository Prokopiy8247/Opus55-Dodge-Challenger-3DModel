# P1b report: interior and cockpit view

Date: 2026-10-11. Gate: `docs/gates/gate_p1b.md` — **PASS** (11 checks: 0 FAIL, 1 WARN).

## What was built
`hcar.interior:build_interior` builds the interior in about 8 s into the collection `Car_Interior`: 35 objects `CH_Int_*`, 162,596 triangles, 26 materials. Sources:
- layout in `tools/blender/hcar/interior_tables.py`;
- geometry in `interior.py` and `interior_trim.py`;
- mesh kit in `ikit.py`;
- textures from `tools/textures/make_interior_textures.py`.

### Parts
- **Dashboard and cluster:**
  - Soft-touch dash; its top follows the windshield and cowl, found by ray casts.
  - Cluster brow over two round pods with chrome bezels.
  - Tach 0-7 ×1000 with the red line from 6,000; speedo 0-200 mph with the SRT logo.
  - Centre TFT (km/h, PRNDM, temperature and fuel) sized to the window between the pods.
  - Needles as separate objects, pivot at the origin.
- **Steering wheel and column:**
  - Flat-bottom SRT wheel: perforated grips, stitching, side spokes with button pods and silver frames.
  - Satin silver lower spoke, hub with a chrome surround and the SRT badge, paddles.
  - The wheel rotates about the column axis (23°). The column shroud carries two stalks.
- **Centre stack and console:**
  - Carbon-twill surround around the 8.4" Performance Pages screen and two vents; red start button on the dash face.
  - Console waterfall: switch bank with volume and tuner knobs and a red hazard button.
  - Pistol-grip selector with boot, two cup holders, leather arm rest with stitching.
- **Seats and belts:**
  - Front buckets: perforated inserts, bolsters with pleats, contrast stitching, headrests on chrome posts.
  - "SRT HELLCAT" emboss on the front backrests; hard back shells, rails, side shields, buckles.
  - Rear bench narrowed beside the wheel houses: two contoured seats, integrated headrests, folded centre arm rest, buckles.
  - Red belts: two front belts from the B-pillar anchors, three rear belts from the parcel shelf.
- **Trim and floor:**
  - Door cards: leather insert, arm rest, switch pod, chrome handle, speaker grille.
  - Quarter, C-pillar, B-pillar and A-pillar trims follow the body shell (ray casts with bisection to the glass edges).
  - Headliner (ray cast, 12 mm under the roof) with a dome light; sun visors; interior mirror.
  - Carpet on the floor pan's own grid, 10 mm along its normal, with toe board and firewall; floor mats; sill plates; kick panels; parcel shelf with speakers.
  - Windshield and rear-glass frit bands.
  - Pedals with pivots (accelerator, brake) and a footrest.
- **Exterior glass** is now tinted see-through (alpha 0.30, transparent shadows), so the cabin is visible.
- **`sim/vehicle/hellcat/cockpit.json`** describes the eye point and FOV, the wheel axis and turns lock to lock, needle pivots and axes with the gauge mapping, pedal pivots, interior and side mirror frames, and the display and screen quads. The Unity cockpit (P4b) uses it.

## Numbers
- **Driver eye** at (-0.375, -0.36, 1.12) m. The H-point is at 0.49 m (0.27 m above the floor); horizontal FOV 85° (D-020).
- **Layout check against `reference/Салон 2.jpg`:** a camera is fitted to 9 landmarks.
  - Landmarks: wheel badge, two dial centres, four screen corners, two vents.
  - Fit RMS 17.1 px (0.89 % of the width), lens 41 mm equivalent.
  - The start button and the console knobs and selector are not in the fit; their residuals are 12 px and 30-80 px.
- **Layout corrections from the fit:**
  - dial spacing 0.274 → 0.22 m;
  - start button moved to (-0.20, 0.70);
  - console redesigned as a waterfall with the switch bank, selector 10 cm further forward, cup holders.
- **Needles:** 0 / 3000 / 6000 rpm → -120 / -17.1 / 85.7°; 0 / 100 / 200 mph → -120 / 0 / 120°. The error is 0.000°.
- **Steering wheel:** -90 / 0 / 90 / 468° rotate the rim top by the same angle with 0.000 mm off-plane motion. The lock is 2.6 turns (±468°).
- **Clipping:** no unexpected intersections between interior parts or with the exterior. There are 20 contacts by design and no coincident faces.
  - The nearest geometry to the eye is 0.21 m away (the headrest behind).
  - The exterior G-Model audit is still clean after the floor and tunnel changes.

## Evidence
`docs/video_assets/P1b/`:
- driver, passenger and dash close-up views;
- rear seat view and front seats from the rear;
- side and top cut-aways;
- gauge tests at the three value pairs;
- steering at -90 / 0 / +90°;
- the layout overlay on the photo;
- a 4 s cockpit animation (needles sweep, wheel turns).

## Deviations and notes
- **Mirrors:** showing the scene needs the Unity runtime (render textures). It is planned and gated in P4b; this gate gives a WARN.
- **Interior detail is procedural.** Shapes are fitted to the photos and the photo camera fit.
  - Buttons are blank shapes, without icons.
  - The Hellcat cat-head logo is not drawn; the emboss is text only.
  - Fine leather grain and perforation are textures.
- **Floor pan tunnel changes (exterior), so the seats and console fit:**
  - the tunnel is narrow under the seats (flat top ±0.095 m) and widens only ahead of the cushions;
  - it keeps its top across the rear kick-up;
  - the front subframe rails start under the toe board.
- **Exterior glass material** changed to see-through. The exterior gate stays PASS.
