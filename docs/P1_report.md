# P1 report: visual Hellcat Widebody exterior

Date: 2026-10-11. Gate: `docs/gates/gate_p1.md` — **PASS** (15 checks: 0 FAIL, 1 WARN).

## What was built
- **Procedural exterior, rebuilt in about 65 s by `hcar.assemble:build_car`.** All shape data is in `tools/blender/hcar/body_tables.py`; the method is in D-016 and `docs/model_notes.md`.
  - **Body strip** (`shape.py`): a perimeter surface swept around the plan outline through feature curves K0-K5 (rocker, shoulder, belt, character line).
  - **Greenhouse:** a loft over y.
  - **Caps:** hood and deck lid are height fields blended into the strip's tangent plane.
- **Panels** (`panels.py`, `body_panels.py`, `gh_panels.py`, `flares.py`):
  - Each panel is a Coons patch in its surface's parameter space, with creases on the feature rows and Winslow untangling where rows bunch up.
  - The border is inset perpendicular to the shut line.
  - Edges get a rolled edge and a flange.
  - Openings get return flanges (tunnels) and back plates.
  - Panel grids have no inverted faces; the median edge is 13-24 mm.
- **Details** (`details.py`):
  - front: four round headlamps with halos, upper, lower and duct grilles (holes for the lamp cups), splitter, markers;
  - hood: central scoop with mesh, two heat extractors;
  - rear: segmented tail lamps with smoked lenses and reverse bars, DODGE lettering, flat spoiler with SRT badge, valance with two rectangular black tips, plate recess and plate;
  - side and roof: mirrors on stalks, handles, fuel door, antenna, side sills, wheel liners (inner walls and slots for the coil-overs), cowl, badges.
- **Wheels** (`wheels.py`): 305/35 ZR20 tire, 20x11 five split-spoke rim, disc, U-shaped caliper.
- **Mechanics** (`mechanics.py`), simplified proxies:
  - underbody and tank: floor pan with tunnel and kick-ups, saddle fuel tank;
  - engine bay: V8 with supercharger and pulleys, 8-speed transmission, radiator, core support, radiator shroud with an upright lip;
  - chassis and driveline: front and rear subframes, SLA front and 5-link rear suspension with coil-overs, drive shaft, differential, half shafts;
  - exhaust: pipes and mufflers.
- **Assembly** (`assemble.py`):
  - `CH_*` names, `_L` / `_R` split, origins and box UVs;
  - Solidify thickness: 1.5 mm body, 3 mm bumpers, flares and valance, 4.5 mm glass;
  - outward normals by ray voting; two-sided open trim shells.
- **Look-dev:** EEVEE, Poly Haven studio HDRI (CC0), showroom floor; `render.py` makes beauty, orthographic and turntable renders.

## Numbers
- **Dimensions** (±2 % target, all pass):

  | Dimension | Model | Deviation |
  |---|---|---|
  | Length | 5.020 m | +0.06 % |
  | Width without mirrors | 1.986 m | -0.20 % |
  | Width with mirrors | 2.168 m | -0.05 % |
  | Height | 1.454 m | -0.41 % |
  | Wheelbase | 2.951 m | 0.00 % |
  | Track front / rear | 1.667 / 1.669 m | 0.00 % |

- **Silhouettes against the drawing** (limits 29 / 40 mm):

  | View | RMS |
  |---|---|
  | Side top | 20.9 mm |
  | Plan | 15.1 mm |
  | Front | 20.6 mm |
  | Rear | 14.7 mm |

- **Photo overlay:** camera fitted to photo 4 with solvePnP (f ≈ 50 mm equivalent), reprojection RMS 24.8 px.
- **Mesh:** 128 objects, 124 meshes, 619k triangles.
  - Normals: no back faces visible from 128 directions (1.55 M rays).
  - No non-manifold edges on body parts.
  - No panel intersections. The exhaustive all-pairs triangle test finds only 30 contacts, all by design (mounted details, joints).
  - No coincident faces.
- **Shut lines:** 5.0 mm (door, fender, quarter, rocker, fascia, bumper), 6.6 mm hood and deck lid; 3 mm flare seams.
- **Wheels:** 360.8 mm radius, 0.01 mm out of round, centres within 0.0 mm of the spec positions.

## Evidence
`docs/video_assets/P1/`:
- orthographic overlays: front, rear, side, top;
- six final stills: 3/4 front L/R, 3/4 rear L/R, low side, top;
- 8 s turntable, 1080p30 MP4;
- earlier WIP stills.

The photo 4 overlay is `docs/p1/photo_cams/overlay_photo4.jpg`.

## Deviations and notes
- **Gate WARN, side bottom line:** RMS 54 mm. The widebody side sills hang 15-30 mm below the drawing's standard-body rocker line, and the bumper lower edges are steep in 1 cm bins. This is informational; the upper silhouette and the widths pass.
- **Mechanics are proxies.** They are placed from the specs (no photos exist); detail there is not a goal.
- **FBX export comes with the export pipeline (P2/P4):** `tools/export_all.py`, one FBX per part group, plus `parts.json`.
- **Problems fixed during the gate:**
  - flipped normals on small details;
  - Solidify spikes, fixed by turning even-thickness off;
  - folded Coons grids over the arches, fixed with Winslow smoothing;
  - fender flanges under the flares;
  - open recesses showing the engine bay, fixed with closed tunnels, back plates, the shroud lip and a radiator overlapping its support;
  - seams on the mirror plane, fixed by snapping mirror-side borders exactly to x = 0 and welding mirror pairs;
  - suspension and exhaust parts passing through the floor.
