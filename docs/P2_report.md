# P2 report: physics skeleton, material presets, export

Date: 2026-10-11. Gate: `docs/gates/gate_p2.md` — **PASS** (14 checks: 0 FAIL, 2 WARN).

## What was built
`hcar.hskel:main` (Blender, about 25 s) builds the node-beam skeleton of the Hellcat from the finished visual model and writes:
- `sim/vehicle/hellcat/geometry.json`: nodes, beams, triangles, wheels, pressure groups, torsion bars, parts with linked visual objects, camera mounts. Unity frame: x right, y up, z forward; triangle normal `cross(b - a, c - a)` points out of the body.
- the debug collection `Car_Physics/PH_Hellcat`: nodes as spheres, beams as tubes coloured by category, rendered by Geometry Nodes.

All tunable values live in `sim/vehicle/hellcat/params.json`: 70 beam materials, contact materials, surfaces, brakes, powertrain, steering and aero. Tuning never regenerates the skeleton (brief 15.3). `tools/sync_vehicle.py` copies both files to `StreamingAssets/Vehicles/hellcat/`, the same rule as the editor menu *Tools/Hellcat/Sync Vehicle Data*.

Generator: `tools/blender/hcar/hskel.py`, with tables in `hskel_tables.py` and the container and writer in `sk.py`.

### Structure (brief 6.1)
- **Passenger cell (heavy cage):**
  - sills, floor and tunnel, firewall, A/B/C pillars, roof rails and bows, rear bulkhead, parcel shelf;
  - dash cross member with the steering column (collapse threshold, `deformLimitMin` 0.55);
  - seat frames on floor mounts; door-card nodes on the door inner frames.
- **Front crush zone:**
  - front rails in three sections with crush behaviour (`rail_f`, deform 42 kN with hardening, `deformLimitMin` 0.12);
  - crush cans and bumper beam;
  - radiator core support, aprons and towers;
  - hood hinges and latch, fender mounts.
- **Engine bay:** engine and supercharger cluster (270 kg) and transmission (95 kg) on breakable mounts (break group `engine_mount`); radiator package; battery.
- **Rear zone:** rear rails (stations 1, 3 and 4 reinforced), trunk floor, fuel tank on straps, rear bumper beam, crush cans, subframe on four breakable mounts.
- **Closures:**
  - doors, hood and trunk are two-layer node groups: outer skin plus inner frame;
  - they hang on 3-beam pinned hinges and latches with their own break groups;
  - bumper covers sit on weak clips; glass is on mount beams.
- **Suspension:**
  - front SLA: lower and upper A-arms, knuckle, coil-over (spring, damper with rebound and blow-off, BOUNDED bump stop) and anti-roll bar;
  - rear five-link with coil-over and anti-roll bar;
  - steering: rack ends pinned to the housing, HYDRO tie rods (D-023);
  - arms, links and tie rods deform plastically and break.
- **Wheels:**
  - pressurized torus tire: 24 sections; inner and outer rim rings, three tread rows, sidewalls;
  - 240-triangle closed air volume per tire, 241 kPa (35 psi);
  - tread and outer-sidewall triangles collide;
  - break groups `tire_*` (bead) and `wheel_*` (hub).
- **Collision triangles:** exterior panels, glass, underbody and the tire surfaces, all wound outward (checked numerically).

## Numbers
| Item | Value |
|---|---|
| Nodes / beams / triangles | 2,023 / 9,500 (NORMAL 9,490, BOUNDED 4, SUPPORT 4, HYDRO 2) / 2,308 (COLLIDE 1,924, PRESSURE 384) |
| Beams by category | panel 3,677, tire 1,632, rigid 1,379, rim 808, glass 623, crush 578, plastic 536, mount 213, suspension 52, hydro 2 |
| Nodes by part | body 759, wheels 125-126 each (48 rim, 72 tread, axle, knuckle, arm), hood 92, doors 90, trunk 57, bumpers 55, fenders 60, glass 9-54, engine 16, exhaust 16, lamps and mirrors 3 |
| Mass | 2,040.0 kg (target 2,040 kg, MY18 curb, D-015) |
| Centre of mass | 1.682 m ahead of the rear axle, height 0.569 m, 2.7 mm right of centre |
| Axle split | 57.0 % front / 43.0 % rear (target 57 / 43, brief 55-57 %) |
| Corner loads (rigid-body estimate) | FL 579, FR 583, RL 437, RR 440 kg |
| Connectivity | 1 component, valence min 3 / median 9 / max 52 |
| Duplicates within 1 cm | 21 pairs, all between separate parts at shut lines (intentional) |
| Tire air volume | 52.5 l per tire, closed two-manifold, positive volume |
| Break groups | 37, including every group of brief 6.3 |

Mass by part (kg):

| Part | Mass |
|---|---|
| body (cell, crush zones, chassis, interior structure) | 1,161.9 |
| engine | 365.0 |
| wheel corners | 73 / 73 / 60 / 60 |
| doors | 32 each |
| exhaust | 30 |
| hood | 27.3 |
| trunk | 18 |
| windshield | 15 |
| fenders | 15 each |
| bumpers | 13.8 each |
| rear glass | 11.2 |
| side glass | 5.2 each |
| headlights | 3 each |
| quarter glass | 2.2 each |
| mirrors | 1.6 each |

Fixed group masses (`hskel_tables.GROUP_MASS`) total 1,229 kg. The cell takes the remaining 811 kg by node weights plus a linear tilt along the car that puts the centre of mass on the 57 / 43 split.

### Stability at 2 kHz (D-024)
`tools/skeleton/stability.py` assembles the full system and computes the exact spectral measure:

S = λ_max(M⁻¹(dt²K + 2·dt·C + D_contact)), where symplectic Euler is stable for S < 4.

| Measure | Value |
|---|---|
| S (exact) | **2.355** (hard limit 2.5) |
| Top modes | rear rails, sills, front rails, hinges, firewall |
| Block-Gershgorin bound (old D-004 measure) | 6.1, about 2.6× too pessimistic |
| ω·dt ≥ 0.5 warnings | 1,955 of 2,023 nodes (max 1.54) |

The ω·dt warning is the brief's single-node estimate. It ignores that neighbours move together, which is why it flags almost every node of a stiff, well-connected structure. Following user answer 4 it stays a warning, and the exact criterion is the gate (`docs/p2_stability.json`).

Stability tuning history is in `docs/tuning_log.csv`. The first full skeleton had S = 12.45. The changes that brought it down:
- rim and disc mass moved onto the rim rings;
- rim skip beams removed;
- coil-overs moved to the heavy knuckle nodes;
- heavier towers, hinges and latches;
- softer skins and mounts.

### Suspension design (D-025, D-026)
`tools/skeleton/suspension_design.py` solves the first-order kinematics of each knuckle on its five two-force links and derives the rates from targets. The "Spring rate", "Damper" and "Torsion bar" rows were written into `params.json` with `--apply`.

| | Front (SLA) | Rear (5-link) |
|---|---|---|
| Corner load / unsprung / sprung (kg) | 581 / 73 / 508 | 439 / 60 / 379 |
| Spring motion ratio (inclination) | 0.932 (14.6°) | 0.911 (19.1°) |
| Ride frequency target → wheel rate | 1.40 Hz → 39.3 kN/m | 1.55 Hz → 35.9 kN/m |
| Spring rate | 45.2 kN/m | 43.3 kN/m |
| Ride frequency with tire (300 kN/m assumed) | 1.32 Hz | 1.46 Hz |
| Preload at ride height (static compression) | 5,349 N (118 mm) | 4,078 N (94 mm) |
| Damper compression / rebound (ζ 0.24 / 0.32 at the wheel) | 2,470 / 3,290 N·s/m | 2,130 / 2,840 N·s/m |
| Fast damping above 0.20 / 0.25 m/s | 990 / 1,320 | 850 / 1,140 |
| Roll centre | 0.090 m | 0.099 m |
| Camber gain | -22.9°/m | -22.8°/m |
| Bump steer | -0.42°/m | 0.00°/m |
| Anti-roll-bar lever ratio | 3.75 rad/m | 4.95 rad/m |
| Roll stiffness: springs + bar = total | 54.7 + 77.4 = 132.1 kN·m/rad | 50.0 + 38.1 = 88.1 kN·m/rad |
| Torsion bar | 1,980 N·m/rad | 560 N·m/rad |

Whole car:
- sprung mass 1,774 kg, sprung centre of mass at 0.601 m;
- roll axis 0.094 m under it, so the roll moment arm is 0.508 m;
- total roll stiffness 220 kN·m/rad, which gives a **roll gradient of 2.30°/g** with a 60 % front share.

The tire vertical rate is an assumption until test 9 (P3b) measures it.

What the analysis found and fixed in the first skeleton:
- **Front arms nearly parallel.** The front-view instant centre was 40 m away, giving -3°/m camber gain and a 0.18 m roll centre.
- **Rear upper links falling outward.** The instant centre was outboard of the wheel, giving +42°/m camber gain and a roll centre below the ground.
- **Bump steer of 34-49°/m**, i.e. 3.4-4.9° of toe per 10 cm of travel.
- **Anti-roll-bar beams ran from the bar axis straight onto the knuckles.** They acted as extra springs against the arm's arc.

The rebuilt geometry:
- lower and upper pivot heights now put the instant centres 2.5 m inboard;
- the rack and toe-link heights were solved numerically for zero bump steer;
- the bars have lever nodes rotating about their axis, with drop links to the lower arm (front) and the knuckle (rear).

**Spring preload.** A beam material can now carry a `preload` (N). Its rest length is spawn·pre + preload/k, implemented in `SoftBodyWorld.Resolve` and `SimParamsDef`. The springs therefore hold the body at the modelled ride height, and a new spring rate does not move it.

## Gate G-Skeleton (brief 14)
| Check | Result |
|---|---|
| Counts reported | PASS |
| Complexity vs the starting target | WARN, see *Resolution* |
| Mass ±1 % | PASS (+0.00 %) |
| Centre of mass and axle split | PASS (57.0 / 43.0 %) |
| Every node connected, one component | PASS |
| No unintended duplicates, no degenerate beams | PASS (21 shut-line pairs; no beam shorter than 2 cm, shortest 35.5 mm) |
| Materials defined for every beam, torsion bar and node | PASS |
| Break groups of 6.3 | PASS |
| Exact stability S < 2.5 | PASS (2.355) |
| ω·dt per node | WARN (user answer 4) |
| Tire air volumes closed, outward, positive | PASS (4 × 52.5 l) |
| Outward winding of every surface triangle | PASS (see below) |
| Export copy in sync | PASS |
| Evidence renders | PASS |

**How the winding is checked numerically.**
- Triangles are grouped into patches that grow only across consistently wound shared edges.
- Each patch is oriented by ray voting: from each centroid, rays go into both hemispheres, and the side whose rays escape more often is outside.
- Result: 1,344 surface triangles in 19 patches, all outward, with vote margins of 0.43 or more. There are no inconsistent edges, no non-manifold edges, and 4 intentional two-sided mirror triangles.
- The check found 20 inconsistent edges in the first build. Fender cells at the wheel-arch lip had been flipped by the old per-cell winding rule. `grid_tris` now winds each grid as a whole.

**Short beams.** The bumper-corner clips and the door-glass mounts had beams of 5-12 mm to the nearest node across a shut line. Such a beam flips direction as soon as its nodes cross. They now skip nodes closer than 3 cm, and the gate rejects beams under 2 cm.

## Resolution
The skeleton has 2,023 nodes, 9,500 beams and 2,308 triangles, below the brief's 4.5 starting target of 2,500 / 12,000 / 3,000 (D-027).
- **Why it stops here.** The binding constraint is stability at 2 kHz with the real 2,040 kg. Each extra node makes the nodes lighter, and at unchanged stiffness S grows.
- **Why it is enough.** The panel grids already put a node every 12-15 cm:
  - door skin 11 × 6 nodes, fender 10 × 6, quarter 12 × 7, hood 9 × 8, roof 9 × 9;
  - two-layer closures.
- **Room to grow.** The P0 benchmark ran 3,000 nodes and 15,000 beams in real time, so P6 can raise the panel resolution if the crash look needs it.

## Evidence
`docs/video_assets/P2/`, 1920 × 1080, Eevee:
- full skeleton (`2026-10-11_P2_<view>_skel.png`) in five views: front 3/4, rear 3/4, side, top, under;
- the same over the dimmed paint (`_overlay.png`), plus the beauty pass (`_car.png`);
- structure only (cage grey, crush zones orange, mounts red, suspension green, tires and rims grey) in four views (`2026-10-11_P2_structure_*`).

Beam colours: panels yellow, plastic magenta, glass light blue, crush orange, rigid grey, mounts red, suspension green.

## Deviations and next steps
- **Unity solver work in P3:**
  - torsion bars (dihedral spring on the lever nodes);
  - tire pressure groups (ideal gas, signed volume);
  - `StabilityReport` with the exact λ_max by power iteration (D-024);
  - spawn 1 cm above the ground with settling (D-026).
  
  `VehicleDef` already reads `torsionBars` and `pressureGroups`.
- **Suspension visual proxies** in `mechanics.py` still have the old pivot heights. They are rebuilt from the skeleton hard points when the skinning bindings are made (P4).
- **Tire vertical rate, ride heights and corner loads at rest** are measured in the solver in P3b (tests 9-14). The design script is re-run with the measured tire rate.
