# Model notes: Challenger SRT Hellcat Widebody (visual model)

Target: **2018 Challenger SRT Hellcat Widebody**, left-hand drive, gloss white, matte black hood and roof panel, satin graphite wheels (decision D-015). Sources: the user's photos in `reference\`, the spec sheet `docs/specs.md`, and the dimensions.com drawing of the standard-body Hellcat (private reference, not versioned; decision D-016).

## Conventions
- Blender units are metres, Z up, car forward = **+Y**, car right = **+X** (left-hand drive: the driver sits at x < 0).
- Origin of the car frame: x = 0 on the centreline; y = 0 halfway between the axles; z = 0 on the ground.
- Wheel centres: y = ±1.4755 m (wheelbase 2.951 m), x = ±0.8335 m front and ±0.8345 m rear (track 1.667 / 1.669 m).
- Wheel centre height is z = 0.352 m, the static loaded radius. The unloaded tire is 0.3608 m, so the tread sits 8.8 mm "into" the ground plane. This is the static deflection; the soft-body tire supplies it at runtime.
- The exporter converts Blender (x, y, z) to Unity (x, z, y), with the winding reversed (P0.5 exporter).
- Each part has its own origin at the centre of its bounding box. Wheel parts are parented to `CH_Wheel_XX` empties at the hub centres.
- Parts are split into `_L` / `_R` objects wherever left and right are separate pieces.
- Collections: `Car_Visual` (with the child `Wheels`); `Car_Interior` follows in P1b.

## How it is built (re-runnable)
`hcar.assemble:build_car` (about 65 s) rebuilds the whole exterior from the tables in `tools/blender/hcar/body_tables.py`.
- Body strip, greenhouse loft and height-field caps are built first.
- Panels are Coons patches cut from these surfaces. Each panel has a 5 mm gap (hood 6.6 mm), a rolled edge with a flange, and openings with return flanges and back plates.
- Then come the widebody flares, wheels, details and simplified mechanics.
- `finalize()` then:
  - names every part `CH_*` and splits it into `_L` / `_R`;
  - sets the origins and box-projected UVs;
  - adds Solidify thickness: body panels 1.5 mm, bumpers, flares and valance 3 mm, glass 4.5 mm, small trim 0.8 mm;
  - makes open trim shells two-sided.

Quality checks are run by `hcar.gate_model:audit`, `hcar.gate_model:measure`, `tools/ref/gate_overlay.py`, `tools/ref/ortho_overlay.py` and `tools/gate_p1.py`.

## Parts (128 objects, 619k triangles with thickness)
- **Body:**
  - panels: `CH_Hood`, `CH_DeckLid`, `CH_Roof`, `CH_Cowl`, `CH_Fender_L/R`, `CH_Door_L/R`, `CH_Quarter_L/R`, `CH_Rocker_L/R`, `CH_Pillars_L/R`;
  - flares: `CH_Flare_front_L/R`, `CH_Flare_rear_L/R`;
  - bumpers: `CH_Bumper_F` (fascia), `CH_Bumper_R`.
- **Glass:** `CH_Glass_Windshield`, `CH_Glass_Rear`, `CH_Glass_Door_L/R`, `CH_Glass_Quarter_L/R`.
- **Front:**
  - headlamps, per side: `CH_Headlamp_Housing`, `_Reflector`, `_Halo`, `_Lens` (two round lamps each);
  - grilles: `CH_Grille_Upper`, `CH_Grille_Lower`, `CH_Grille_Duct_L/R`;
  - trim: `CH_Splitter`, `CH_Marker_Front_L/R`, `CH_Badge_SRT_Front`.
- **Hood:** `CH_Hood_Scoop`, `CH_Hood_Scoop_Mesh`, `CH_Hood_Extractor_L/R`, `CH_Hood_Extractor_Vent_L/R`.
- **Rear:**
  - lamps and panel: `CH_TailPanel`, `CH_TailLamp_Red`, `CH_TailLamp_Lens`, `CH_TailLamp_Bar` (reverse lamps);
  - badges and spoiler: `CH_Badge_DODGE`, `CH_Spoiler`, `CH_Badge_SRT_Rear`;
  - lower and plate: `CH_Valance`, `CH_Exhaust_Tips_L/R`, `CH_PlateRecess`, `CH_Plate_Rear`, `CH_Marker_Rear_L/R`.
- **Side:**
  - mirrors: `CH_Mirror_Housing_L/R`, `CH_Mirror_Glass_L/R`, `CH_Mirror_Stalk_L/R`;
  - other: `CH_Door_Handle_L/R`, `CH_FuelDoor`, `CH_Antenna`, `CH_SideSill_L/R`, `CH_Badge_Hellcat_L/R`, `CH_WheelLiners_L/R`.
- **Wheels:** `CH_Wheel_FL|FR|RL|RR` (empty at the hub) with `_Rim`, `_Tire`, `_Disc` and `_Caliper`.
  - Rim: 20x11 in, 5 split spokes.
  - Tire: 305/35 ZR20.
- **Mechanics (simplified proxies):**
  - floor, tank and engine bay: `CH_FloorPan` (tunnel and kick-ups), `CH_FuelTank` (saddle), `CH_Engine` (block, heads, supercharger), `CH_Engine_Pulleys`, `CH_Transmission`, `CH_Radiator`, `CH_CoreSupport`, `CH_RadiatorShroud`;
  - subframes and driveline: `CH_Subframe_Front/Rear`, `CH_DriveShaft`, `CH_Differential`, `CH_HalfShaft_L/R`;
  - suspension, per side: `CH_Knuckles`, `CH_Susp_Front_Arms`, `_Damper`, `_Spring`; `CH_Susp_Rear_Links`, `_Damper`, `_Spring`;
  - exhaust: `CH_Exhaust_L/R`.
- **Materials (29):** gloss white clearcoat paint, matte black paint (hood and roof), satin graphite wheels, red calipers, tinted glass, chrome, black gloss and black trim plastics, grille mesh, lamp lenses (halo, tail red, smoke, reverse), rubber, brake disc, underbody, steel, aluminium, orange engine, red springs, exhaust steel, plate.

## Assumptions (not visible in the references)
- **Side profile and plan view.** They follow the dimensions.com drawing of the standard body; the widebody flares (3-4 cm per side) are added from the photos. The overall width matches the spec within 0.2 %. The rocker line sits 15-30 mm lower than on the drawing because of the widebody side sills (gate WARN, informational).
- **Underbody, engine bay and suspension.** They are simplified proxies placed from the specs (engine position, subframes, coil-over axes). No photos exist; they are only seen when parts detach or the hood opens.
- **Wheel face.** It comes from the 3/4 photos: five split spokes, a concave face and a satin graphite finish. The calipers are simplified red U-shaped bodies over the disc.
- **Panel gaps.** They are 5 mm, a typical production value (4-6 mm in the brief). The hood-fender gap measures 6.6 mm because the hood's side curve is built separately.
- **Licence plate.** It is a blank white plate (no text), since the photos show dealer plates.
- **No invented logos beyond the photos:** SRT front and rear, DODGE rear, red Hellcat badges on the fenders.
- **Interior.** Not part of P1; it follows in P1b.

## Measured result (gate P1, `docs/gates/gate_p1.md`)
| Dimension | Model | Spec | Deviation |
|---|---|---|---|
| Length | 5.020 m | 5.017 m | +0.06 % |
| Width without mirrors | 1.986 m | 1.990 m | -0.20 % |
| Width with mirrors | 2.168 m | 2.169 m | -0.05 % |
| Height | 1.454 m | 1.460 m | -0.41 % |
| Wheelbase | 2.951 m | 2.951 m | 0.00 % |
| Track front / rear | 1.667 / 1.669 m | 1.667 / 1.669 m | 0.00 % |

Silhouette RMS against the drawing:

| View | RMS |
|---|---|
| Side top | 20.9 mm |
| Plan | 15.1 mm |
| Front | 20.6 mm |
| Rear | 14.7 mm |

The limit is 2 % of the height (29 mm) or of the width (40 mm). On photo 4 the fitted camera and the model agree to 24.8 px RMS over 10 points.

## Uncertainty
- Body sections between the drawing's lines are interpolated, so local surface errors of about ±1 cm are possible.
- The hood scoop and extractor shapes come from the photos alone, about ±1 cm.
- Wheel offset and flare depth come from the photos, about ±1 cm.

## Interior (P1b, docs/P1b_report.md)
- Collection `Car_Interior`, 35 objects `CH_Int_*` plus `CH_Glass_Frit`, 162,596 triangles. Rebuild with `hcar.interior:build_interior` (~8 s, needs `Car_Visual`).
- Layout tables: `tools/blender/hcar/interior_tables.py`:
  - eye point and H-point (decision D-020);
  - wheel centre and column angle;
  - cluster and pods;
  - stack, screen and start button;
  - console top profile, switch bank, selector and cup holders;
  - pedals, seats and mirror.
- Animated parts and their pivots: steering wheel, two needles, two pedals. Their rest pose is straight / 12 o'clock / released, and `pose_cockpit()` sets test poses. `sim/vehicle/hellcat/cockpit.json` gives the pivots and axes to Unity.
- Assumptions:
  - Buttons and switches are blank shapes.
  - The Hellcat cat-head logo is not drawn: the seat emboss is "SRT HELLCAT" text, and the wheel badge is "SRT".
  - The headliner, door and quarter trims are simplified surfaces 1.2-6 cm inside the body shell.
  - The rear seat narrows beside the wheel houses, whose inner walls come in to |x| = 0.598 m.
