# BeamNG soft-body (JBeam) physics: reference notes for our own solver

Project: Challenger soft-body game (Unity, C#, Burst jobs). Compiled 2026-10-10 from BeamNG's public documentation only. We re-implement our OWN node-beam solver. No BeamNG code, vehicle files, meshes or other assets were downloaded, read or used. Everything below is summarised in our own words, with short attributed quotes only.

**How to read this file**
- `[KEY]` after a statement: documented on the page listed under that key in section 1.
- **INFERENCE**: our reading of a documented statement or example; the docs do not say it explicitly.
- **ASSUMPTION**: our own design choice or general physics background; not in the BeamNG docs.
- "not documented": we looked for it on the pages in section 1 and found nothing.
- Most pages state values "as of 0.39.1.0", the game version the docs describe.

---

## 1. Sources (all accessed 2026-10-10)

| Key | URL | Read for |
|---|---|---|
| VEHICLE | https://documentation.beamng.com/modding/vehicle/ | index, navigation |
| INTRO | https://documentation.beamng.com/modding/vehicle/intro_jbeam/ | node/beam basics, spring, damp, deform, strength, node weight |
| SYNTAX | https://documentation.beamng.com/modding/vehicle/intro_jbeam/jbeamsyntax/ | table and modifier-row syntax |
| TIPS | https://documentation.beamng.com/modding/vehicle/intro_jbeam/jbeamtips/ | collision system, break groups, performance |
| ISSUES | https://documentation.beamng.com/modding/vehicle/intro_jbeam/common_issues/ | instability, clipping, leaking properties |
| DEBUG | https://documentation.beamng.com/modding/vehicle/intro_jbeam/debugtools/ | debug views (what is measured), aero vectors |
| SECTIONS | https://documentation.beamng.com/modding/vehicle/sections/ | list of JBeam sections |
| NODES | https://documentation.beamng.com/modding/vehicle/sections/nodes/ | node parameters, collision rules |
| BEAMS | https://documentation.beamng.com/modding/vehicle/sections/beams/ | beam parameters and types |
| BOUNDED | https://documentation.beamng.com/modding/vehicle/sections/beams/bounded/ | BOUNDED beams, damping variants |
| SUPPORT | https://documentation.beamng.com/modding/vehicle/sections/beams/support/ | SUPPORT beams |
| ANISO | https://documentation.beamng.com/modding/vehicle/sections/beams/anisotropic/ | ANISOTROPIC beams |
| PRESSURED | https://documentation.beamng.com/modding/vehicle/sections/beams/pressured/ | PRESSURED beams |
| LBEAM | https://documentation.beamng.com/modding/vehicle/sections/beams/l-beam/ | L-beams |
| TRIS | https://documentation.beamng.com/modding/vehicle/sections/triangles/ | triangles, collision bias, aero, pressure groups |
| QUADS | https://documentation.beamng.com/modding/vehicle/sections/triangles/quads/ | quads |
| WHEELS | https://documentation.beamng.com/modding/vehicle/sections/wheels/ | Pressure Wheels (pressureWheels) |
| HYDROS | https://documentation.beamng.com/modding/vehicle/sections/hydros/ | hydros |
| RAILS | https://documentation.beamng.com/modding/vehicle/sections/rails/ | slidenodes and rails |
| TORSION | https://documentation.beamng.com/modding/vehicle/sections/torsionbars/ | torsion bars |
| FLEX | https://documentation.beamng.com/modding/vehicle/sections/flexbodies/ | flexbodies (visual mesh binding) |
| TUTLIST | https://documentation.beamng.com/modding/vehicle/tutorials/ | navigation only |
| TUTORIAL | https://documentation.beamng.com/modding/vehicle/tutorials/basic_car_tutorial/ | structure design, typical values, stability debugging |
| VM | https://documentation.beamng.com/modding/programming/virtualmachines/ | physics rate, physics core role, 20 Hz minimum |
| ARCH | https://documentation.beamng.com/beamng_tech/architecture/ | 2000 updates/s, what the physics core computes |
| COUPLING | https://documentation.beamng.com/beamng_tech/tools/cosimulationeditor/tight_coupling/ | 0.5 ms step, step scheduling |
| ARGS | https://documentation.beamng.com/beamng_tech/arguments_and_settings/ | `-physicsfps` |
| DETERM | https://documentation.beamng.com/beamng_tech/deterministic_mode/ | determinism |
| ABOUT | https://beamng.com/game/about/physics/ | official beamng.com page; only corroborates INTRO |

Notes on the sources:
- All pages were read with WebFetch, an automated page-to-text reader; key sentences were re-checked with targeted second reads. Long tables still carry some paraphrase risk; the ANISO parameter table renders garbled, so its types and defaults are partly our reading.
- No page was unreachable.
- Requested topics without a page of their own: slidenodes (on RAILS); pressureWheels (the "Pressure Wheels" page, WHEELS); deformGroups and breakGroups (parameters on BEAMS, more on FLEX and TIPS); physics theory, collision, node weight and stability (spread over INTRO, NODES, TIPS, ISSUES, DEBUG, TUTORIAL).
- No page documents the numerical integrator or the contact force law. Nothing in this file relies on ABOUT alone.

---

## 2. Core model

- BeamNG simulates soft bodies: objects such as cars are node-and-beam structures that can deform [INTRO].
- **Nodes** are point masses that carry all the mass and move freely: "Nodes can be thought of as particles, each node has mass, and can move freely in space." [INTRO]. Nodes handle almost all collision [SECTIONS][NODES].
- **Beams** are massless springs/dampers with exactly one node at each end. They rotate freely around nodes and only hold two nodes at a set distance: "No other forces (such as twisting) are transmitted through them, and they cannot be bent." [INTRO]. Beams never collide [NODES].
- **Triangles** span three nodes and serve collision with nodes (vehicle vs. vehicle and self-collision), aerodynamics, and closed pressure volumes [SECTIONS][TRIS].
- **Why triangulation gives rigidity**: "a box with no cross braces will fall over as the beams can pivot around the nodes." Diagonal braces make it rigid [INTRO]. Background (ASSUMPTION, standard truss mechanics): the structure is a pin-jointed truss; a free 3D body with N nodes needs at least 3N-6 independent, well-placed beams to be rigid, and tetrahedra are the minimal rigid cells.
- **Documented design rules** [TUTORIAL]:
  - each node needs at least 3 beams, roughly perpendicular to each other; a part attached through 1 node rotates freely, through 2 nodes is a hinge, through 3 or more is fixed in rotation;
  - attachment tripods neither too narrow (high stress) nor too wide (risk of "reversals"); beams long enough that small movements do not change their angle; prefer straight lines and right angles;
  - a typical car is 3-4 nodes across its width with similar spacing along its length; more nodes give more deformation detail but are harder to tune;
  - change topology before stiffness: "is impossible to properly rigidify sub-optimal jbeam just by raising the beamspring".
- **Flat panels** (hood, doors) need a **rigidifier node**: non-colliding, about 0.5 m off the surface, beamed to every panel node; panels of at least 3x3 nodes so they can fold; rigidifier beams with a lower `beamDeform` than the surface beams so the panel mostly folds [TUTORIAL][ISSUES].
- **Damage emerges from beams**: they deform permanently (`beamDeform`) and break (`beamStrength`); break groups detach parts; the visible mesh follows the nodes and is cut where beams break [INTRO][BEAMS][FLEX].
- **Clusters** are groups of nodes connected by beams; broken-off parts form new clusters [DEBUG].
- **Engine level**: a C++ physics core "computes the soft-body physics, friction models, node-grabbing physics" and orchestrates the per-vehicle Lua VMs [VM]; it handles "collisions, damage, friction, buoyancy, aerodynamics" [ARCH]. Powertrain and similar systems run in vehicle Lua [VM].

---

## 3. Nodes

Positions are in metres in BeamNG's vehicle frame: +X left, +Y backward, +Z up, forward = -Y. The engine uses SI units and is Z-up [NODES].

| Parameter | Meaning | Unit | Default | Notes | Src |
|---|---|---|---|---|---|
| `id` | node name | - | required | unique per vehicle | NODES |
| `posX`, `posY`, `posZ` | position | m | required | frame above | NODES |
| `nodeWeight` | node mass | kg | `options.nodeWeight`, 25 kg in 0.39.1.0 | tutorial template uses 2-3 kg | NODES, TUTORIAL |
| `group` | node group name, or list of names | - | none | used by flexbodies, wheels, collision exclusion; only the first group counts for collision | NODES |
| `nodeMaterial` | "NM_" + material (METAL, PLASTIC, RUBBER, GLASS, ...) | - | `options.nodeMaterial` | "Node material only affects sound and particle properties, not physics." | NODES |
| `collision` | node may collide with anything | bool | true | false also disables `selfCollision` | NODES, TIPS |
| `selfCollision` | node collides with its own vehicle's triangles | bool | false | | NODES |
| `staticCollision` | node collides with terrain (heightmap) and map objects | bool | true | TIPS: defaults to the `collision` value unless set | NODES, TIPS |
| `frictionCoef` | static friction coefficient | - | 1 | page text: "most of the time set to 0.5"; tutorial uses 0.6 | NODES, TUTORIAL |
| `slidingFrictionCoef` | sliding friction coefficient | - | = `frictionCoef` | | NODES |
| `stribeckExponent` | shape of the static-to-sliding transition | - | 1.75 | smaller = more progressive | NODES, WHEELS |
| `stribeckVelMult` | sets the velocity at which the sliding coefficient applies | not stated | not stated | | NODES, WHEELS |
| `noLoadCoef`, `fullLoadCoef` | friction multiplier at zero / full load | - | not stated | noLoad > fullLoad | NODES, WHEELS |
| `loadSensitivitySlope` | "The loss of coef per newton of normal force" | 1/N | not stated | uses each node's own normal force | NODES, WHEELS |
| `softnessCoef` | "time variant friction behavior" | - (max 1) | 0.6 | higher = soft slick-like rubber | NODES, WHEELS |
| `treadCoef` | multiplies ground roughness coefficient | - | 1 | slick 0, standard 0.7, off-road ~0.9 | NODES, WHEELS |
| `fixed` | node cannot move | bool | false | props only; disables collision even if `collision` is true | NODES |
| `engineGroup` | powertrain group | - | none | `engine_block` (>=2 nodes, thermal mass), `radiator`, `fuel` (fuel mass spread evenly), `engine_intake` | NODES |
| `pairedNode` | inner/outer tire node pairing | - | automatic | do not set by hand | NODES |
| `nodeOffset`, `nodeMove`, `nodeRotate` | placement transforms passed in from slots | m, deg | zero | applied rotate, then offset, then move | NODES |
| `impact*Event`, `highlight`, `nodeWeightFunction` | sound overrides, debug, cargo | - | - | not physics-relevant for us | NODES |

**Collision rules for nodes (documented)**
1. "In BeamNG, collision is handled by nodes alone. (Beams can not collide with anything.)" [NODES]
2. Three node collision types: heightmap; static (map objects); dynamic, against vehicle triangles, split into external (between vehicles) and self (within one vehicle) [NODES][TIPS].
3. Dynamic collision has priority over static and heightmap, so "with high enough force a node can be slightly pushed through a solid wall or the ground." [NODES]
4. Triangle forces "start applying at around 2.5cm distance from the triangle in order to prevent clipping." [NODES]; "Triangles have "thickness" of 2.5 cm", measured from the green (front) side [TIPS]. `externalCollisionBias` on the triangle offsets this distance [NODES][TRIS].
5. **Group exclusion**: a node does not collide with triangles "made of nodes within the same group"; only a node's first group counts, and the rule may misbehave when none of the node's groups contains a flexbody [NODES]. TIPS says it "can and should be abused" to stop specific pairs from colliding.
6. **Clearance** (node-to-triangle at spawn, not node-to-node spacing): "it's best to keep around 3 or 3.5 cm distance between them" [NODES]; a node clipping a triangle generates collision events constantly, so keep at least 3 cm, or 3.5 cm for flexible parts [TIPS]; the Node Triangle Self Collision Detector flags pairs within 0.025 m and recommends at least 0.035 m [DEBUG].
7. **Performance** [NODES][TIPS]: a NORMALTYPE triangle costs nothing extra while no node is within 50 cm; a triangle with no collidable node within 10 cm becomes inactive ("sleep mode"); "keep over 10cm space between collidable components by default, where possible"; heightmap collision is cheaper than static, so off-road vehicles want fewer bottom nodes; thin parts such as mirrors use nodes with `collision` and `selfCollision` off, `staticCollision` on, and no triangles.
8. "All nodes that have collision should have at least NONCOLLIDABLE triangles between them", so vehicles do not get stuck inside each other in crashes [NODES][TIPS].

Node weight versus stiffness and stability: see 4.8.

---

## 4. Beams

### 4.1 Common beam parameters

| Parameter | Meaning | Unit | Default | Src |
|---|---|---|---|---|
| `id1:`, `id2:` | end nodes | - | required | BEAMS |
| `beamType` | behaviour type (4.5) | - | NORMAL | BEAMS |
| `beamSpring` | stiffness | N/m | 4,300,000 | BEAMS |
| `beamDamp` | linear damping | N/(m/s) | 580 | BEAMS |
| `beamDeform` | force needed for permanent deformation; FLT_MAX = never | N | 220,000 | BEAMS |
| `beamStrength` | force the beam withstands before breaking; FLT_MAX = unbreakable | N | FLT_MAX | BEAMS |
| `deformLimit` | "Limits by how much of original length the beam can deform in compression" | ratio | none | BEAMS |
| `deformLimitExpansion` | same, in expansion; "Used to avoid excessive stretching" | ratio | = `deformLimit` | BEAMS |
| `deformLimitStress` | caps the growth of `beamDeform` | N | none | BEAMS |
| `breakGroup` | name, or list of names; beams in a group break together | - | none | BEAMS |
| `breakGroupType` | 0 = breaking this beam breaks its group; 1 = does not trigger the group but is broken by it | - | not stated (reset rows use 0) | BEAMS, ISSUES |
| `disableMeshBreaking` | keep flexbody polygons when this beam breaks | bool | false | BEAMS |
| `disableTriangleBreaking` | keep triangle collision/aero when this beam breaks | bool | false | BEAMS |
| `deformGroup` | triggers flexbody material swaps and some powertrain damage | - | none | BEAMS, FLEX |
| `deformationTriggerRatio` | deformation level that triggers the deformGroup, typically < 0.1 | ratio | none | BEAMS |
| `beamPrecompression` | rest length at spawn as a factor of the spawn distance | ratio | 1.0 | BEAMS |
| `precompressionRange` | rest-length change at spawn; overrides `beamPrecompression` | m | none | BEAMS |
| `beamPrecompressionTime` | time to reach the precompressed length | s | none | BEAMS |
| `dampCutoffHz` | frequency limit for damping; NORMAL, BOUNDED and LBEAM only | Hz | none | BEAMS |
| `optional` | suppress errors if a node is missing | bool | false | BEAMS |
| `name` | identifier used by other systems | - | - | BEAMS |

- `beamSpring` = 0 is allowed and not flagged as a duplicate, so damping-only beams can be added [BEAMS]. Duplicate beams on one node pair give warnings [ISSUES]; beams with a `deformGroup` are exempt, which is how brittle duplicate glass beams are made [BEAMS].

### 4.2 Elastic force and damping

- `beamSpring` is the force needed to change the beam's length by a given amount. Stiffness is not deformation: a soft beam compresses elastically and springs back; plastic deformation does not [INTRO].
- Damping "is the resistance to movement"; without it a spring oscillates forever [INTRO]. INTRO says damping resists "with a force inversely proportional to speed", but the unit N/(m/s) [BEAMS] and the damper parameters in 4.5 imply a force proportional to relative speed. INFERENCE: the INTRO wording is a typo; damping is linear viscous along the beam.
- Typical values:

| Use | beamSpring (N/m) | beamDamp (N/(m/s)) | Other | Src |
|---|---|---|---|---|
| suspension spring | 40,000 | 0 | | INTRO |
| suspension damper | 0 | 4,500 | | INTRO |
| structural, e.g. suspension arms | 8,000,000 | 125 | | INTRO |
| steering rack (very stiff) | 14,001,000 | 250 | | INTRO |
| tutorial chassis | 1,201,000 | 150 | deform 50,000, strength FLT_MAX, deformLimitExpansion 1.2 | TUTORIAL |
| tutorial component mounts | 1,501,000 | 150 | deform 30,000 | TUTORIAL |
| tutorial panel latch (breakGroup) | - | - | deform 15,000 = strength 15,000 | TUTORIAL |
| tutorial rigidifier beams | - | - | deform 5,000 | TUTORIAL |
| tutorial damper (BOUNDED) | - | variable | velocity split 0.2 m/s, fast = slow / 3, dampCutoffHz 500 | TUTORIAL |
| tutorial bump stop (BOUNDED) | 0 | 0 | beamLimitSpring 251,000, beamLimitDamp 5,000, bound ranges 0.12 m, boundZone 0.04 m | TUTORIAL |

### 4.3 Plastic deformation

Documented:
- `beamDeform` is "How much force (N) is required to deform the beam permanently" [BEAMS]; a deformed beam does not return to its original shape [INTRO].
- **Hardening**: "beamDeform increases as the beam deforms, this property caps the deformation." `deformLimitStress` caps that gain (N) and is "Useful to simulate friction on certain kinds of suspension" [BEAMS].
- `deformLimit` / `deformLimitExpansion` cap deformation relative to the original length, in compression / expansion; `deformLimitExpansion` is the one most used. Example values: 1.1 [BEAMS], 1.2 [TUTORIAL].
- The DEBUG "Deformation" view shows "how much the beams are permanently deformed" (blue = stretched past the initial length, red = shortened) [DEBUG]. INFERENCE: deformation is a permanent change of the beam's rest length.

Not documented: the rest-length update law; the hardening rate; whether damping force counts towards the deform threshold; what `deformationTriggerRatio` is compared against; whether `deformLimit` is a fraction of the change or a length ratio.

### 4.4 Breaking, break groups, deform groups

- A beam breaks when the force exceeds `beamStrength` [BEAMS][INTRO]. Broken beams "stop resisting forces"; BROKEN cannot be set in data [BEAMS]. A broken beam no longer connects its nodes, so parts can fall off [INTRO].
- **breakGroup**: when one beam in a group breaks, the others break too. The list form puts a beam in several groups; with `breakGroupType` 1 it breaks when any of its groups triggers [BEAMS][TIPS].
- **Triangles** break when one of their side beams breaks; a triangle `breakGroup` extends this to beams that are not its sides [TRIS]. `disableTriangleBreaking` / `disableMeshBreaking` exempt purely structural beams [BEAMS].
- **Rails and torsion bars** ignore breakGroups: they break when a beam between two of their consecutive nodes breaks. TIPS recommends a "dummy breaker" beam: no spring or damp, maximum deform and strength, mesh and triangle breaking disabled, the desired breakGroup(s), `breakGroupType` 1 [TIPS][TORSION].
- **Glass and wood**: a beam with both `breakGroup` and `deformGroup` spawns glass or wood particles when it breaks, depending on its nodes' `nodeMaterial` [BEAMS].
- **Deform groups** swap a flexbody's material when a beam passes its `deformationTriggerRatio` or breaks (lights, windows) [FLEX]. `deformationTriggerRatio` is the performance-heavy part, so use it only where needed [BEAMS][TIPS].
- **Panel attachment design** [TUTORIAL]: hinge = 2 attachment points, the strongest group; latch = 1-2 points, much weaker so it breaks first; bolted panels = front and rear groups of equal strength.
- **Leaking modifiers** can make, for example, the rear bumper fall off when the front one breaks; end each part with a reset row [ISSUES][TUTORIAL].
- The brief's "close deform/strength = brittle, far apart = tough" is not stated in the docs, but is consistent with the examples: a latch with deform = strength, a chassis with strength FLT_MAX (INFERENCE).

### 4.5 Beam types

**NORMAL**: general-purpose beam with no special behaviour [BEAMS].

**SUPPORT** [BEAMS][SUPPORT]
- "These only resist forces in compression, not in extension." With precompression, the beam resists only once compressed below its precompressed length, so precompression < 1 creates a slack gap.
- `beamLongBound` (ratio of spawned length, default 1.0): when exceeded, "the beam automatically breaks" (0 = on any extension, 0.5 = at 150 %, 1.0 = at 200 %).
- Use: "mostly used as limiters, to prevent structures from reversing themselves or getting stuck where they shouldn't." Example (steering limiters): precompression 0.71, `beamLongBound` 2, spring 5,001,000, damp 250, deform 150,000, strength 550,000. Support beams often have precompression < 1 and high longBound values [DEBUG].

**BOUNDED** [BEAMS][BOUNDED]
- Bounds: `beamShortBound` (ratio, default 1.0; 0.5 = may contract to 50 % of spawned length before limit properties apply, 1.0 = may compress its whole length); `beamLongBound` (ratio, default 1.0; 0.5 = 150 %, 1.0 = 200 %); `shortBoundRange` / `longBoundRange` (m) give the bounds as distances and override the ratios.
- `boundZone` (m, default 1): extra deformation past the bound before the limit properties fully apply. "The properties change progressively from the initial beam properties to the bound properties". The 1 m default is "very progressive" and often too long.

| Parameter | Unit | Default | Meaning |
|---|---|---|---|
| `beamLimitSpring` | N/m | 1.0 | spring that starts at the bound |
| `beamLimitDamp` | N/(m/s) | 1.0 | limit damping; compression only if a rebound value is set |
| `beamLimitDampRebound` | N/(m/s) | = `beamLimitDamp` | limit damping while extending |
| `beamDampRebound` | N/(m/s) | = `beamDamp` | damping while extending; `beamDamp` then applies only while compressing |
| `beamDampFast` | N/(m/s) | = `beamDamp` | used when the rate exceeds the split velocity |
| `beamDampReboundFast` | N/(m/s) | = `beamDampRebound` | rebound damping above the split |
| `beamDampVelocitySplit` | m/s | FLT_MAX | split velocity |
| `beamDampVelocitySplitRebound` | m/s | FLT_MAX | separate split for rebound |

- Position vs. velocity: springs and limits depend on position (is the beam longer or shorter than its spawned length); damp vs. dampRebound depends on the direction of the velocity.
- Curve shape: "The resulting forces will always keep going up as the speed increases"; progressive or digressive depending on the values.
- Cost: "They are computationally expensive to use and should usually only be used in suspension components." Precompressed support beams often suffice instead; several bounded beams can be stacked on one node pair.
- Examples: simple damper (damp 850, rebound 1,700, dampCutoffHz 500); steering damper (damp 100, split 0.1 m/s, fast 1,000); rally (separate bump and rebound beams, splits 0.35 and 0.25 m/s); hydraulic bump stop (limit spring and damp 15,000, shortBoundRange 0.03 m, boundZone 0.01 m).
- Not documented: whether the limit spring adds to or replaces `beamSpring`; the length its force is measured from; the blend shape inside `boundZone`; whether fast damping applies to the whole velocity or only to the part above the split.

**ANISOTROPIC** [BEAMS][ANISO]
- Compression uses `beamSpring`/`beamDamp`; expansion beyond the spawned length uses `springExpansion` (N/m) and `dampExpansion` (N/(m/s)), which default to the compression values.
- `transitionZone`: fraction of the spawned length, default 0 = instant switch; 0.1 ramps over 10 % of the length.
- `beamLongBound` (ratio, default FLT_MAX) breaks the beam automatically past that extension (0.5 = 150 %, 1.0 = 200 %).
- Uses: tire sidewalls (auto-generated), ropes, soft tops. Soft-top example: 5,100 in compression, 41,000 in expansion, `transitionZone` 0.05.

**PRESSURED** [BEAMS][PRESSURED]
- A virtual air cylinder: "Their forces are inversely proportional to their real time length."

| Parameter | Unit | Default | Meaning |
|---|---|---|---|
| `pressure` or `pressurePSI` | Pa or psi | - | starting pressure; set only one of the two |
| `surface` | m^2 | 1.0 | piston area |
| `volumeCoef` | - | 1.0 | progressivity |
| `maxPressure` / `maxPressurePSI` | Pa / psi | FLT_MAX | the beam breaks above this |
| `pressureLimit` / `pressureLimitPSI` | Pa / psi | FLT_MAX | pressure stops rising above this |

- At `volumeCoef` 1: "Compressing the beam to half it's length will cause the volume to be reduced by half, and the pressure to multiply by 2." INFERENCE: P = P0 * L0 / L and F = P * surface.
- `volumeCoef` > 1: pressure rises sooner and reaches infinity before zero length (instability risk); < 1: pressure never reaches infinity; 0: constant pressure.
- When stretched, `beamSpring` acts in addition to the pressure force. Use only one limiter; a maximum close to the initial pressure can break the beam in normal driving.
- Uses: tire sidewalls, air springs (bus example: 60 psi, surface 0.05 m^2, `beamSpring` 100).
- Not documented: gauge vs. absolute pressure, the general `volumeCoef` formula, the reference length.

**LBEAM** [BEAMS][LBEAM]
- Three nodes: the l-beam runs `id1`-`id2`; beams `id1`-`id3` and `id2`-`id3` must already exist. It resists a change of the angle between those two beams at `id3` and does not react when only the l-beam's length changes.
- Stiffness and damping come from `beamSpring`/`beamDamp` (units not stated). Uses: tires (auto-generated; lateral stiffness while the sidewalls compress freely) and leaf springs (example spring 265,140, damp 1,880, precompression 0.957).

**HYDRO**: a beam whose length changes on demand, e.g. a steering rack; it has all normal beam properties [BEAMS]. See 6.2.

**BROKEN**: internal state only, see 4.4 [BEAMS].

### 4.6 Precompression [BEAMS][ISSUES][TIPS]

- `beamPrecompression` sets the rest length as a factor of the spawn distance (2.0 doubles, 0.5 halves); `precompressionRange` (m) overrides it; `beamPrecompressionTime` (s) ramps the change so the structure is not deformed violently at spawn (ISSUES example: 0.5 s).
- Uses: spring preload (coilover with `precompressionRange`), slack gaps in support limiters (0.71), leaf springs (0.957).
- Leaking precompression shows up as stressed beams at spawn [TIPS]; reset to 1 after use [SUPPORT][ISSUES].

### 4.7 Damping variants

| Variant | Applies to | Selected by | Src |
|---|---|---|---|
| linear `beamDamp` | all beams | - | BEAMS |
| `dampExpansion` | ANISOTROPIC | position (expanded beyond spawn length) | ANISO |
| `beamDampRebound`, `beamDampFast`, `beamDampReboundFast`, `beamDampVelocitySplit(Rebound)` | BOUNDED | velocity direction and magnitude | BOUNDED |
| `beamLimitDamp`, `beamLimitDampRebound` | BOUNDED past a bound | position and velocity direction | BOUNDED |
| `dampCutoffHz` | NORMAL, BOUNDED, LBEAM | frequency | BEAMS |
| `damp`, `damp2` | torsion bars | twist direction | TORSION |

- `dampCutoffHz`: "Limits the vibration frequency (Hz) above which damping applies"; its purpose is to allow higher damping before instability; it is expensive [BEAMS].
- Damping-only beams (`beamSpring` 0) fight wobble on long structures, with a breakGroup list covering every link and `breakGroupType` 1 [TIPS].

### 4.8 Mass, stiffness and stability (documented)

- If the combined stiffness of the beams at a node is too high, the node "will begin to vibrate, and may even explode"; fix with a heavier node or softer beams; too-high `beamDamp` does the same. In the INTRO example, raising 4 nodes from 6 kg to 7 kg fixed the vibration [INTRO].
- BEAMS: stiffness too high for the node weight causes vibration and instability; damping too high causes "pulsing stresses and instability". ISSUES names the cause as "beamSpring and/or beamDamp values that are too high for the nodeWeight."
- Symptoms: the vehicle vanishes with "instability detected" or the game pauses itself; breakable parts fall off at spawn; vibration and flashing stress colours [ISSUES][TUTORIAL].
- Debugging: node-forces view in slow motion, looking for rapidly changing forces [TUTORIAL][TIPS]; Node Stability view (exponential moving average of node forces) [DEBUG].
- Other documented instability sources: nodes pushed by triangles at spawn, misaligned slidenodes, too-large or too-fast precompression [ISSUES]; failed `$=` expressions falling back to defaults [SYNTAX]; rising pressure in PRESSURED beams [PRESSURED]; torsion-bar levers far from 90 degrees to the axis [TORSION]; high tire `numRays` [WHEELS].
- TUTORIAL mentions a "weight budget": the number of nodes limits how light the car can be. The brake reaction node `nodeArm` needs at least 2 kg on a car, 5-10 kg on a truck [WHEELS].
- Fix wobble by adding bracing in the direction of motion before raising stiffness [TUTORIAL].

---

## 5. Triangles and collision

### 5.1 Definition and parameters [TRIS]

- "Triangles are defined by 3 nodes, chosen in a counter clockwise order." The front side shows green in the debug view, the back side purple. Expose the front side outward, because it is less prone to objects phasing through in very hard impacts; swapping two nodes flips a triangle.

| Parameter | Meaning | Unit | Default | Notes |
|---|---|---|---|---|
| `dragCoef` | drag as a percentage of a flat plate of the same size | % | 100 | about 10 for exposed body panels |
| `skinDragCoef` | drag along the surface | % | 0 | paddle-like mud tire treads |
| `liftCoef` | lift as a percentage of a flat plate | % | = `dragCoef` | spoilers 80-120 |
| `stallAngle` | angle of attack where lift starts to drop | rad | 0.58 | |
| `triangleType` | NORMALTYPE or NONCOLLIDABLE | - | NORMALTYPE | NONCOLLIDABLE: "Have no collisions, only anticlip." |
| `pressureGroup` | marks the triangle as part of one pressure volume | - | none | flotation and pressure |
| `pressurePSI` / `pressure` | pressure of the pressureGroup | psi / Pa | none | |
| `breakGroup` | lets beams that are not sides break the triangle | - | none | |
| `optional` | suppress missing-node errors | bool | false | |
| `groundModel` | friction material of the surface | - | asphalt | lowercase; SPIKE_STRIP deflates tires |
| `externalCollisionBias` | makes one side "thicker" | - | default bias | see 5.3 |

- Conflict between pages: QUADS says NONCOLLIDABLE triangles "Have no collisions or aero.", while TRIS says "Have no collisions, only anticlip." and does not mention aero. See section 9.

### 5.2 Collision rules (documented)

- "coltris will only collide with nodes"; they "will not collide with other coltris or with static world objects." [TRIS] The static world (heightmap, map objects) therefore only touches nodes [NODES][TIPS].
- Dynamic collision: external (between vehicles, needs `collision`) and self (within a vehicle, needs `selfCollision`, default false); coupled couplers temporarily disable self-collision [NODES][TIPS].
- Same-group exclusion uses each node's first group (section 3, item 5) [NODES][TIPS].
- **Anticlip**: "Triangles have not only collision, but also anticlip system." It "decides on which side of the triangle a node will end up after collision." [TIPS] NONCOLLIDABLE triangles keep anticlip without the collision cost; they suit dense small structures and nodes that collide but have no triangles of their own, such as suspension and exhaust; railings can collide through their nodes only [TRIS][NODES][TIPS].
- Thickness 2.5 cm from the green side; dynamic contacts have priority (section 3, items 3-4) [TIPS][NODES].
- Tire triangles do not collide with vehicles by default (`triangleCollision` false, costly; mostly enabled for big off-road tires) [WHEELS][TIPS].
- **Collision slidenodes**: extra self-collision nodes riding on rails along panel edges add collision density without changing how the part deforms [TIPS].

### 5.3 `externalCollisionBias` [TRIS][QUADS]

| Value | Effect |
|---|---|
| `oneWayIn` | only the inner side collides |
| `in` | both sides equally biased; nodes may clip through either side at medium speed |
| (none, default) | outer side biased somewhat more than inner |
| `out` | outer side strongly biased; nodes may pass from inside even at low speed |
| `oneWayOut` | only the outer side collides |

A thicker side lowers the chance of clipping at high speed; a thinner side lets parts sit closer together at spawn. The actual thickness of each mode is not documented.

### 5.4 Aerodynamics [TRIS][DEBUG]

- Drag depends only on airflow speed, triangle area and the coefficients; forces are applied to the adjacent nodes [TRIS]. DEBUG: "forces are calculated at each node" from the adjacent triangles.
- No shielding: "Triangles are not affected by other triangles."; a rear triangle still produces full drag [TRIS].
- Tilting a triangle up gives lift, tilting it down gives downforce; more angle gives more lift until `stallAngle` [TRIS].
- DEBUG vectors: drag points straight back along the airflow, lift perpendicular to it; a normal aligned with the airflow is 90 deg angle of attack (pure drag); a normal perpendicular to it is 0 deg (no aero force).
- Tires: `dragCoef` default 100, recommended 5-20 [WHEELS]. The tutorial chassis uses `dragCoef` 10 and `groundModel` metal [TUTORIAL].
- Not documented: the force formula, the flat-plate coefficient, air density, the angle dependence, post-stall lift.

### 5.5 Pressure volumes [TRIS][DEBUG][WHEELS]

- A `pressureGroup` turns a set of triangles into one enclosed volume (flotation, tires, items such as a mattress); it should have "no missing surfaces or concave surfaces" to avoid "ghost forces" [TRIS].
- Pressured triangles show blue in the debug type view [DEBUG]; wheels build their pressure group from both hub and tire nodes [WHEELS].

### 5.6 Quads [QUADS]

- A quad n1, n2, n3, n4 creates the triangles (n1, n2, n3) and (n3, n4, n1); same counter-clockwise rule and same parameters as triangles; mostly used for exactly rectangular surfaces.

---

## 6. Wheels, tires and suspension elements

### 6.1 Pressure wheels (`pressureWheels`) [WHEELS][TIPS]

Generation:
- The engine "automatically generate[s] a wheel with the defined parameters around a pair of nodes which acts as an axle" (`node1:`, `node2:`); the position and orientation of the axle nodes set the wheel's pose.
- Hub nodes match the outer layer of the rim and attach to the axle nodes with fairly rigid beams. Tire nodes sit on the outer surface of the tire and connect to the hub nodes and to each other; side 1 is normally the inner side, side 2 the outer. Nodes per ray and the exact layout are not documented.
- Radial (sidewall) beams carry most of the weight and are generated as ANISOTROPIC: soft in compression, stiff in extension, "keeping the tires from expanding at higher speeds."
- Reinforcement beams run from tire nodes on one side to hub nodes on the other, for lateral rigidity. L-beams are described as the better option and disable the diagonal reinforcement beams when enabled.
- "A pressure group is also set-up using both the hub and tire nodes." `pressurePSI` fills it. Sidewall compression is kept soft: "Spring and Damp Should be low to allow air pressure to handle weight of vehicle." "Since 0.22, the spring parameter is often set as a function of tire pressure" (the example scales sidewall spring with tire pressure).

| Parameter | Unit | Default | Meaning / notes |
|---|---|---|---|
| `radius`, `hubRadius` | m | 0.5, 0.65 x radius | tread radius, hub radius |
| `tireWidth`, `hubWidth`, `wheelOffset` | m | axle-node distance, axle-node distance, 0 | tire slightly narrower than hub is advised |
| `numRays` | - | 10 | spokes per side, must be even; 10-20 recommended, most vanilla wheels use 16; more rays cost CPU and are less stable; smoothness effect mainly shows below ~10 km/h |
| `pressurePSI` | psi | - | road car 25-35, rock crawler 5-15, heavy truck 50-100 |
| `maxPressurePSI` | psi | 10 | cap that keeps pressure from rising into instability when the tire deforms |
| `nodeWeight`, `hubNodeWeight` / `tireWeight`, `hubWeight` | kg | - | per-node masses, or totals that override them |
| `frictionCoef`, `slidingFrictionCoef`, `stribeck*`, `noLoadCoef`, `fullLoadCoef`, `loadSensitivitySlope`, `softnessCoef`, `treadCoef` | as in section 3 | | tread friction; load sensitivity uses each node's own normal force |
| `hubBeam*`, `hubTreadBeam*`, `hubPeripheryBeam*`, `hubSideBeam*` (Spring/Damp/Deform/Strength) | N/m, N/(m/s), N | - | hub structure: spring as stiff as stability allows, damp < 10 |
| `wheelSideBeam*` (+`Expansion`) | | - | sidewall: low compression values; expansion spring as high as stability allows |
| `wheelSideReinfBeam*` | | - | sidewall beams spanning +-2 nodes |
| `wheelReinfBeam*` | | - | diagonals or L-beams; lateral stiffness at low slip angles |
| `wheelTreadBeam*`, `wheelTreadReinfBeam*` | | - | across the tread; spring up to 50-75 % of the sidewall expansion spring; reinforcement 1/4-1/2 of the tread spring |
| `wheelPeripheryBeam*`, `wheelPeripheryReinfBeam*` | | - | circumferential; longitudinal stiffness and high-speed growth |
| `enableTireLbeams`, `enableTireReinfBeams`, `enableTireSideReinfBeams`, `enableTreadReinfBeams`, `enableTirePeripheryReinfBeams` | bool | (Reinf: false) | which beam families are generated |
| `enableTireSupportBeams` (v0.38) | bool | false | precompressed support beams from the wheel centre keep a deflated tire off the rim |
| `triangleCollision`, `treadTriangleCollision`, `side1/side2TriangleCollision`, `hubTriangleCollision`, `hubSide1/2TriangleCollision` | bool | false | which tire/hub triangles collide (costly) |
| `collision`, `selfCollision` | bool | - | collision should always be true; selfCollision usually false |
| `brakeTorque`, `parkingTorque` | N*m | 0 | service and parking brake torque |
| `brakeSpring` | N*m/rad | 10 | "brake compliance for stability" |
| `nodeArm:`, `nodeCoupling:`, `torqueArm:`, `torqueCoupling:`, `torqueArm2:` | node | - | nodes that take the brake and drivetrain reaction torque |
| `enableABS`, `absSlipRatioTarget`, `absHz` | -, -, Hz | false, 0.18, 100 | ABS |

- Not documented on WHEELS: `hasTireCoef`, `rotorDir`, `wheelSideTriangle`, `enableExtraHubBeams`, `padGroup` (closest documented names: `hasTire`, `enableExtraHubcapBeams`, `padMaterial`); how pressure triangles are formed internally; how drive torque is applied to the wheel nodes.
- Performance trade-offs [TIPS]: fewer rays perform better but raise rolling resistance and clipping risk; disabling tire L-beams also raises rolling resistance; tire triangle collision is "very costly".

### 6.2 Hydros [HYDROS][BEAMS]

- A beam whose rest length follows an electrics input (`inputSource`, default `steering_input`). Uses: steering racks, hydraulic cylinders, door actuators. Hydros accept most standard beam arguments.
- "With a factor of 1, sending a command of 1 to a beam will cause it to double in length." With factor 0.5, input -1 halves the length and +1 gives 1.5x. INFERENCE: L = L0 * (1 + factor * input); a negative factor reverses the direction. `factor` overrides `inLimit`, `outLimit` and `inputFactor`.

| Parameter | Default | Meaning |
|---|---|---|
| `inLimit` | 1 | minimum length ratio |
| `outLimit` | 2 | maximum length ratio |
| `inputFactor` | 1 | scales the input |
| `inputCenter` | 0 | electric value mapped to the centre |
| `inputInLimit`, `inputOutLimit` | -1, 1 | electric values for fully in / fully out |
| `inRate` | 2 | contraction speed |
| `outRate` | = `inRate` | extension speed |
| `autoCenterRate` | = `inRate` | speed of returning to centre |

- Rate units are not stated. `steeringWheelLock`: steering-wheel angle from centre to lock in degrees, typically about 450-500 (older cars and trucks more, racing cars less).
- Steering rack example: two hydros with opposite factors (+0.14 / -0.14), rates 1.25, lock 510.

### 6.3 Slidenodes and rails [RAILS][TIPS]

- Rails: a polyline of nodes (`links:`, at least 2), with `looped` (default false) and `capped` (default false); `rails2` (v0.38) is the same data in table-row form.

| Slidenode column | Unit | Default | Meaning |
|---|---|---|---|
| `id:` | - | - | the node |
| `railName` | - | - | rail it rides on |
| `attached` | bool | true | attached at spawn |
| `fixToRail` | bool | true | snapped onto the rail at spawn |
| `tolerance` | m | - | distance from the rail before rail forces apply |
| `spring` | N/m | - | force holding the node to the rail |
| `strength` | N | - | force at which the node separates from the rail |
| `capStrength` | N | - | strength of the end caps |

- Uncapped rails let the node slide off the end and detach; capped rails stop it, held by `capStrength`. Misaligned slidenodes snap violently at spawn [ISSUES]. "The slidenodes are not stable yet because the rails lack damping." [TIPS]
- Uses: steering racks (e.g. spring 18,001,000 with unbreakable strength and caps), MacPherson struts, collision slidenodes. Not documented: whether the spring pulls towards the nearest point on the segment.

### 6.4 Torsion bars [TORSION]

- Four nodes: `id1` is the tip of lever 1, `id2`-`id3` is the axis, `id4` is the tip of lever 2. The bar resists relative twist of the two levers about the axis.

| Parameter | Unit | Default | Meaning |
|---|---|---|---|
| `spring` | N*m/rad | - | torsional stiffness |
| `damp` | N*m*s/rad | - | torsional damping |
| `spring2`, `damp2` | as above | = spring, damp | values on the other side of the spawn angle; setting them makes the bar anisotropic |
| `deform` | N*m | - | torque at which the bar deforms |
| `strength` | N*m | - | torque at which the bar breaks |
| `precompressionAngle` | rad | 0 | twist at spawn |
| `precompressionTime` | s | 0 | time to apply that twist |
| `name` | - | - | identifier for other systems |

- Uses: sway bars, stiffening flat structures such as ladder chassis, shock mounts. Spring/damp 0 on one side plus `precompressionAngle` gives a torsional equivalent of a support beam.
- "The angle between the axis and the lever should be as close as possible to 90 degrees", for stability. "If a beam located between 2 consecutive nodes of a torsion bar breaks, the torsion bar itself will break."
- Example: steering-arm rigidifier with spring 10,000,000, damp 100, deform 25,000, strength 100,000; no sway-bar values are given. The angle definition (dihedral or other) is not stated.

### 6.5 Flexbodies, the visual mesh [FLEX][BEAMS][ISSUES]

- Flexbodies are "the models that get mapped to your nodes"; a flexbody lists one or more node groups and is deformed only by nodes in those groups.
- Each vertex is bound to 3 or 4 nearby nodes: a centre node; VX and VY nodes whose lines to the centre form roughly 90 degree angles; where possible a VZ node perpendicular to both. The closest nodes that meet these criteria are chosen, within distance limits.
- A group needs at least 3 non-collinear nodes, "preferably more" [ISSUES], or mapping fails ("VY node not found"). Arrange nodes "in a grid of sorts, with no outliers" to avoid spikes when deforming; non-colliding help nodes fix degenerate groups such as antennas.
- Mesh breaking removes flexbody polygons when a beam breaks so the mesh does not stretch [BEAMS: `disableMeshBreaking`]; FLEX does not describe how polygons are selected. Deform groups swap `deformMaterialBase` for `deformMaterialDamaged` (4.4).
- Other parameters: `pos`, `rot`, `scale` (m, degrees, factor), `nodeOffset`, `nodeMove`, `nodeRotate`, `ignoreNodeOffset`, `materialOverride`.

---

## 7. Simulation facts

| Topic | Fact | Src |
|---|---|---|
| Step | "Physics Steps compute exactly 0.5ms of simulation time (by default), often written as 2000Hz" | COUPLING |
| Rate | physics runs at "2000 updates per second"; the graphics rate is variable; the UI has its own cycle | ARCH |
| Changing it | `-physicsfps f`, default 2000; too high gives slower-than-real-time; "Values lower than the default are not recommended and can result in limited simulation accuracy and stability." | ARGS |
| Scheduling | each frame predicts the next frame's start and runs the steps needed to reach it; steps run in bursts, usually ahead of wall-clock; about 2000 steps/s averaged over e.g. a minute | COUPLING |
| Minimum rate | the graphics update rate is guaranteed to be at least 20 Hz; "When the computer is unable to reach 20fps, then the simulation will slow down as needed." | VM, COUPLING |
| Threads | physics on its own thread; rendering, collision detection and UI on separate threads; each vehicle Lua VM on its own thread; vehicle Lua runs at physics rate (`onPhysicsStep`) or graphics rate | COUPLING, VM |
| Units | SI, Z-up; positions m, masses kg; spring N/m; damp N/(m/s); deform/strength N; torsion N*m/rad; angles rad (degrees for transforms); pressure Pa or psi; dragCoef % of a flat plate | NODES, BEAMS, TORSION, TRIS |
| Collision bias | force onset about 2.5 cm in front of a triangle (green side); adjustable via `externalCollisionBias` | NODES, TIPS |
| Collision priority | dynamic over static/heightmap; strong force can push a node slightly through walls or ground | NODES |
| Integration scheme | **not documented** | - |
| Contact force law, friction formula, aero formula | **not documented** | - |
| Gravity, air density | not documented on these pages (TIPS mentions setting gravity to zero for a stress check) | TIPS |
| Determinism | normal play is paced by variable frame times and can vary between runs; deterministic mode makes the physics time per frame constant but "does not (yet) lead to deterministic simulation for every scenario" | DETERM |

---

## 8. Implementation notes for our solver

Unless marked [KEY] or INFERENCE, everything in this section is **ASSUMPTION**: our own design.

### 8.1 Units, frame, data

- SI units throughout (brief 4.1); the runtime frame is Unity's (Y-up, left-handed). We never parse JBeam, so BeamNG's +X-left/+Y-back frame only matters when reading example values.
- Own data format: JSON tables with a header row; modifier rows apply to the rows after them, as in JBeam [SYNTAX]; per-row inline overrides are allowed. Difference from JBeam: our loader resets all modifiers at each part boundary, avoiding the documented "leaking" bugs [SYNTAX][ISSUES].
- Use explicit flags for "unbreakable" and "never deforms" instead of FLT_MAX, so Burst code never does inf - inf arithmetic.
- `nodeMaterial`-like tags drive only sound and particles, as in BeamNG [NODES]; physics parameters come from our material presets (brief 4.3).

### 8.2 Integration and time step

- Symplectic (semi-implicit) Euler with fixed `dt` = 0.5 ms, matching BeamNG's documented default [COUPLING][ARGS]. BeamNG's own integrator is not documented, so this is our choice. Per step: accumulate forces; `v += dt * F / m`; `x += dt * v`.
- Keep the per-frame substep cap and visible slow-motion indicator (brief 4.12), mirroring BeamNG slowing the simulation when it cannot keep up [VM][COUPLING]. Do not go below 2000 Hz unless forced; BeamNG warns that lower rates reduce accuracy and stability [ARGS].
- Determinism for replays: inputs indexed by step number, not wall-clock time; force accumulation by graph colouring or per-thread buffers reduced in a fixed order; break and deform-group events collected per step and applied in sorted order; no float atomics. Expect bit-exact replays only on the same build and CPU family.
- **Measured in P0** (`docs/benchmarks/`, `Assets/Sim/Benchmark/`): a third option, per-beam force vectors followed by a per-node gather over a CSR node-to-beam list in beam order, gave bit-identical final states for 1-15 worker threads, different batch sizes, the single-threaded scatter version, and editor (JIT) vs. player (AOT) Burst code. It needs no colouring and no extra reduction pass, so it is the default for the solver.

### 8.3 Beam kernel: refinement of the brief's 4.2 pseudo-code

Sign convention as in the brief: `T > 0` is tension; `+T*n` is applied to node a and `-T*n` to node b. `Lspawn` is the rest length after precompression; `L0` is the current rest length, which plasticity moves.

```
d = p[b] - p[a];  L = length(d);  if (L < 1e-5) return;          // degenerate guard (ASSUMPTION)
n = d / L;  vrel = dot(v[b] - v[a], n);                           // vrel > 0: extending
x = L - L0;                                                       // x > 0: longer than rest length
kE = k; cB = cBump; cR = cRebound; limC = 0;                      // cRebound defaults to cBump [BOUNDED]

// 1) spring, selected by position
switch (type)
  SUPPORT:      if (x >= 0) { if (L > Lspawn*(1+longBound)) Break(); return; }   // slack in tension [SUPPORT]
  ANISOTROPIC:  if (x > 0) { w = (tz > 0) ? saturate(x/(tz*Lspawn)) : 1;          // [ANISO], ramp = INFERENCE
                             kE = lerp(k,kExp,w); cB = cR = lerp(c,cExp,w); }
                if (L > Lspawn*(1+longBound)) Break();
  PRESSURED:    P = P0 / max(1 - vc*(1 - L/Lspawn), eps);         // = P0*Lspawn/L at vc = 1 (INFERENCE)
                P = min(P, pLimit); if (P > pMax) Break();
                Fs = -P*surface + (x > 0 ? k*x : 0);              // pushes apart; spring only when stretched
Fs = (type == PRESSURED) ? Fs : kE*x;
if (type == BOUNDED) {                                            // add-on beyond bound: ASSUMPTION
  e = max(L - Llong, Lshort - L);                                 // bounds from ratios or *Range [BOUNDED]
  if (e > 0) { w = saturate(e/boundZone);
               Fs += sign(x)*w*kLim*e;  limC = w*(vrel > 0 ? cLimReb : cLim); } }

// 2) plasticity: 1D return mapping with linear hardening
//    growth of beamDeform is documented [BEAMS]; the law and H are ASSUMPTION
if (deformable && abs(Fs) > Fy) {
  dl = (abs(Fs) - Fy) / (kE + H);
  L0 = clamp(L0 + sign(Fs)*dl, L0min, L0max);                    // deformLimit/-Expansion (INFERENCE)
  Fy = min(Fy + H*dl, FyCap);                                     // FyCap = deformLimitStress
  Fs = kE*(L - L0);
  if (deformGroup && abs(L0 - Lorig)/Lorig > trigRatio) FlagDeformGroup();   // measure: ASSUMPTION
}

// 3) damping, selected by velocity [BOUNDED]; continuous piecewise curve = INFERENCE
s = abs(vrel); reb = vrel > 0;
cs = reb ? cR : cB;  cf = reb ? cRFast : cBFast;  vs = reb ? splitReb : split;
Fd = sign(vrel) * (s <= vs ? cs*s : cs*vs + cf*(s - vs)) + limC*vrel;

// 4) breaking: elastic force by default, option to include Fd (ASSUMPTION)
if (abs(Fs) > Fbreak) { Break(); return; }

// 5) apply
T = Fs + Fd;  f[a] += T*n;  f[b] -= T*n;
```

**Differences from the brief's 4.2 pseudo-code, and why**
1. **Hardening is required.** The brief's update keeps `|k*(L-L0)|` at the threshold for ever (perfect plasticity). With `beamStrength > beamDeform`, the elastic force can then never reach the strength, and beams break only through damping spikes. BeamNG documents that `beamDeform` grows as the beam deforms [BEAMS]. We add a hardening modulus `H` per material (e.g. 2-20 % of `k`, to be tuned), capped by `deformLimitStress`; optional deform limits stop plastic flow, after which the force rises elastically to `beamStrength`. Without the cap, the extra stretch needed to break is (strength - deform) / H, so tune `H` such that frame rails break after a plausible plastic stretch, not metres of it.
2. **Break test** uses the elastic force by default. The docs only say "force" (ASSUMPTION). This avoids spurious breaks from damping spikes in contact events; make it a per-material flag.
3. **Precompression**: ramp `L0` linearly from the spawn distance to `Lspawn` over `beamPrecompressionTime` (ASSUMPTION). Bounds and auto-break lengths use `Lspawn`; plastic limits use the original rest length `Lorig = Lspawn` (ASSUMPTION). The SUPPORT slack test and the ANISOTROPIC switch use the current rest length `L0`; the docs say "spawned length", which is the same until the beam deforms plastically (ASSUMPTION).
4. **Damping**: rebound, fast and split damping follow BOUNDED semantics and are available on any beam kind in our solver. The fast coefficient applies only above the split: INFERENCE from "The resulting forces will always keep going up as the speed increases" [BOUNDED], which a full replacement could violate when fast < slow. Optional `dampCutoffHz`: feed a first-order low-pass filtered `vrel` into the damping term; the filter is an ASSUMPTION, the docs give only the purpose.
5. **Heavy dampers**: by the derived limit in 8.5, a damper of 4,500 N/(m/s) [INTRO] between light nodes is explicitly unstable at 0.5 ms (`c*dt/mu` > 2 when the reduced mass `mu` < 1.1 kg). Options: heavier hub/mount nodes, or exponential (implicit) per-beam damping that removes the fraction `1 - exp(-c*dt/mu)` of the relative normal velocity per step. That form equals the linear one for small `c*dt/mu` and cannot overshoot for a single beam.
6. **LBEAM** (optional, tires): resist angle change at node 3 with a force along id1-id2, `Fs = k*(L - dT)`, where `dT = sqrt(r1^2 + r2^2 - 2*r1*r2*cos(theta0))` uses the current arm lengths `r1 = |p1-p3|`, `r2 = |p2-p3|`. This is zero whenever the angle is unchanged, matching [LBEAM] ("not if only the length ... changes"), and it is a central force pair, so momentum is conserved. The formula is an ASSUMPTION.
7. **Break groups**: map group names to integer ids; each beam stores up to 2 ids plus its type. When a type-0 beam breaks, mark its groups; at the end of the substep, break every beam and triangle in the marked groups. When a beam breaks, mark the triangles that use it as a side. Recompute clusters with union-find after breaks, for camera follow, detached-part handling and the brief's rule that an engine detached from its mounts stops producing torque [DEBUG].

### 8.4 Beam kinds required by the brief

- **NORMAL**: as above.
- **BOUNDED**: bump stops, rebound limits and dampers. Our interpretation: inside the bounds the normal spring/damp apply; past a bound a limit spring/damper acts on the excess length, blended in over `boundZone`. The docs leave add-vs-replace and the reference length open (section 9), so verify by test that the force curve is monotonic and continuous. Prefer precompressed SUPPORT beams where they suffice, because BOUNDED is documented as expensive [BOUNDED].
- **SUPPORT**: compression-only with slack set by precompression, plus auto-break on over-extension (`beamLongBound`) [SUPPORT]. The brief's description ("stiffens only beyond a set length range to stop total crumple") matches only the compression side; note this in code comments.
- **ANISOTROPIC**: needed for tire sidewalls, soft in compression and stiff in extension [WHEELS][ANISO].
- **PRESSURED** beams: optional (air springs). Tires use the volume model in 8.8.

### 8.5 Stability check

- Derived (background, not from the docs): a single mass-spring-damper under symplectic Euler is stable iff `a + 2b < 4` and `b < 2`, with `a = k*dt^2/m` and `b = c*dt/m`; undamped this is `omega*dt < 2`. For a free two-node beam use the reduced mass `mu = ma*mb/(ma+mb)`.
- Damping shrinks the stable stiffness range, so "adding damping" (brief 4.3) is **not** a fix for explicit-integration blow-ups. The docs agree that excessive damping causes instability [BEAMS][INTRO].
- Per-node load-time report (Gershgorin-style heuristic, ASSUMPTION): `S = (Sum_k*dt^2 + 2*Sum_c*dt) / m_node`. Warn at the brief's threshold (`omega*dt > 0.5`, `omega = sqrt(Sum_k/m)`); error at `S > 2`. Contact penalty stiffness and pressure stiffness count towards `Sum_k`.
- Calibration against documented values (INFERENCE, arithmetic only): BeamNG's default beam (4.3e6 N/m) between two default 25 kg nodes gives `omega*dt` = 0.29; the tutorial chassis (1.2e6 N/m, 2 kg nodes) gives 0.55 for a single beam and about 1.0 per node with ~6 such beams. BeamNG-style structures therefore exceed the brief's 0.5 rule; keep 0.5 as a warning, not a hard limit, or every frame node will be flagged.
- Tuning order, following the docs: topology and bracing first [TUTORIAL], then node mass or stiffness [INTRO]. Do not lower `dt` blindly (brief).

### 8.6 Collision

Documented targets: node-vs-triangle only, 2.5 cm onset on the front side, group exclusion, anticlip, NONCOLLIDABLE triangles, dynamic priority, static world touching nodes only.

- **Narrow phase** (ASSUMPTION): signed distance `s` of the node to the triangle plane, inside the triangle's footprint. For `0 < s < 0.025 m` on the front side, apply a penalty force `kc*(0.025 - s)` along the normal, plus approach-only damping and Coulomb friction. The back side gets a thinner zone (e.g. 0.01 m); the docs only say the default biases the outer side "somewhat more" [TRIS]. Distribute the reaction to the triangle's nodes with barycentric weights so momentum is conserved. Support the five `externalCollisionBias` modes as per-triangle front/back thicknesses.
- **Anticlip** (mechanism ASSUMPTION; only its purpose is documented [TIPS]): for each node-triangle pair in proximity, remember the side the node approached from; if the sign flips between substeps inside the footprint, push the node back to that side. NONCOLLIDABLE triangles run only this test.
- **Exclusions**: the triangle's own nodes; nodes with `collision` = false; own-vehicle triangles when `selfCollision` = false; same-group pairs (ASSUMPTION: a triangle belongs to group G only if all 3 of its nodes have G as their first group).
- **Static world**: nodes collide with the ground (plane or heightfield) and with static meshes through a BVH, gated by `staticCollision`. Per the docs, vehicle triangles never collide with the static world [TRIS], so a thin pole can slip between body nodes. Optional deviation: edge-vs-static tests for thin obstacles; decide per scenario and record it.
- **Priority**: "dynamic over static" [NODES]. In a penalty model, give static contacts a finite, capped stiffness so that a node squeezed by a dynamic triangle can sink slightly into the ground, as documented.
- **Tunnelling** (INFERENCE, arithmetic): at 0.5 ms a node moves 16.7 mm per step at 120 km/h (inside the 25 mm zone), but 33 mm per step at a 240 km/h head-on closing speed, which can skip the zone. The anticlip side tracking (a swept test) is therefore mandatory, as the brief already requires.
- **Broad phase**: spatial hash with cells of about 0.1-0.2 m; skip triangles with no collidable node within 0.10 m, like BeamNG's documented sleep rule [TIPS]; report nodes, triangles and candidate pairs per step (brief 4.4).
- **Authoring rules for our car**, from the docs: at least 3-3.5 cm node-to-triangle clearance at spawn [NODES][TIPS]; over 10 cm between collidable components where possible [NODES]; NONCOLLIDABLE triangles between collidable nodes that have no real surface, to stop snagging [NODES][TIPS]; self-collision only where needed (e.g. hood vs. engine), using groups to exclude neighbours.

### 8.7 Friction

| Brief 4.6 | Documented parameter |
|---|---|
| `mu_peak` | `frictionCoef` |
| `mu_slide` | `slidingFrictionCoef` |
| `stribeck_exponent` | `stribeckExponent` (+ `stribeckVelMult`) |
| `load_sensitivity` | `noLoadCoef`, `fullLoadCoef`, `loadSensitivitySlope` |
| `softness` | `softnessCoef` |

- Load factor (INFERENCE from [WHEELS] text): `max(fullLoadCoef, noLoadCoef - loadSensitivitySlope*N)`, using each node's own normal force N.
- Stribeck curve (ASSUMPTION; standard form, consistent with "smaller values give a more progressive transition"): `mu(v) = mu_slide + (mu_static - mu_slide) * exp(-(|v|/v_s)^delta)`, with `delta = stribeckExponent` and `v_s` from `stribeckVelMult`.
- Multiply by the surface's own coefficient (ASSUMPTION; the combination rule is not documented). Use a regularised stick (tangential spring or smooth saturation) for static friction. Model `softnessCoef` as a first-order relaxation of the friction force (ASSUMPTION).

### 8.8 Tires

The brief's torus model is consistent with the documented design: hub/rim ring nodes, tread nodes, ANISOTROPIC radial/sidewall beams (soft in compression, stiff in extension), lateral reinforcement (diagonals or L-beams), tread and periphery beams, and a pressure volume spanned by hub and tire nodes that carries the load [WHEELS].

- **Discretisation**: the brief asks for 24-48 cross-sections; BeamNG recommends 10-20 rays per side (16 typical) and warns that more rays cost CPU and stability [WHEELS]. Start at 24 and benchmark.
- **Pressure** (physics, ASSUMPTION): the brief's `p = p0*V0/V` must use absolute pressure: `P_abs = (P_gauge0 + P_atm) * V0 / V`; force per cavity triangle `F = (P_abs - P_atm) * 0.5 * cross(p1-p0, p2-p0)`, split 1/3 per node; `V` = sum of signed tetrahedra over the closed, outward-oriented cavity mesh.
- **Cavity mesh**: closed and consistently wound with no gaps, or ghost forces appear [TRIS]. Cap `P_abs` (cf. `maxPressurePSI`, `pressureLimit`) so a crushed tire cannot produce unbounded force [WHEELS][PRESSURED].
- **Stiffness ratios** [WHEELS]: sidewall compression low so air carries the load, expansion high; tread spring up to 50-75 % of the sidewall expansion spring; tread reinforcement 1/4-1/2 of tread; hub beams as stiff as stability allows with low damping. Optionally scale sidewall spring with pressure, as BeamNG content does since 0.22.
- **Deflation**: precompressed SUPPORT beams from hub to tread keep a deflated tire off the rim, like `enableTireSupportBeams` [WHEELS]. The leak model, bead failure and rolling resistance are our own; the docs only note that fewer rays and no L-beams raise rolling resistance [TIPS].
- **Drive and brake torque**: apply as tangential force couples on hub nodes with equal and opposite reaction on chassis nodes, mirroring the documented reaction-node concept (`torqueArm`, `nodeArm`) [WHEELS]. For brake lock-up use a stiff torsional "brake spring" at standstill, cf. `brakeSpring` "for stability", rather than a pure Coulomb torque (INFERENCE).

### 8.9 Suspension and steering

- **Springs and dampers** (brief 4.7): NORMAL spring-only beams with preload via `precompressionRange`; BOUNDED dampers with bump/rebound/fast/split; BOUNDED or SUPPORT bump stops. Example magnitudes are in 4.2.
- **Anti-roll bars**: implement documented-style torsion bars (4 nodes, N*m/rad) instead of "torsional-equivalent beams". Angle: dihedral angle about the axis id2-id3 between planes (id1, id2, id3) and (id2, id3, id4); forces from the standard momentum-conserving dihedral-angle gradient used for molecular-dynamics torsion potentials (ASSUMPTION). Levers about 90 degrees to the axis; break when a beam between consecutive nodes breaks [TORSION].
- **Steering rack**: a HYDRO-style beam pair with opposite factors [HYDROS]: `L0(t) = Lspawn*(1 + factor*u)`, with the input `u` slewed at `inRate`/`outRate` (units ASSUMPTION: per second), clamped to `inLimit`/`outLimit`, with speed-sensitive scaling of `u` (brief 4.8). Optional alternative: rail + slidenodes [RAILS]; if used, add damping to the rail constraint, because BeamNG notes rails lack damping [TIPS].
- **Bendable arms**: small triangulated sub-structures with mounts of at least 3 beams per node [TUTORIAL]. Subframe support must be adequate; otherwise the subframe moves, "causing the car to steer by itself" [TUTORIAL].

### 8.10 Aerodynamics (optional)

- Per triangle (ASSUMPTION form, documented semantics [TRIS][DEBUG]): relative air velocity `va`; drag `0.5*rho*|va|^2*A*Cflat*(dragCoef/100)*|cos(alpha)|` along `va`; lift perpendicular to `va`, rising with angle of attack up to `stallAngle` and falling after it; each force split onto the triangle's nodes; no shielding, as in BeamNG.
- Assumed values: `rho` = 1.225 kg/m^3, `Cflat` about 1.2 (flat plate). Calibrate per-panel `dragCoef` (BeamNG content uses about 10 [TRIS]) so the whole car hits its target drag area; without shielding, rear panels add drag too.

### 8.11 Visual mesh

- Bind each visual vertex to a centre node plus two (or three) frame nodes chosen as in [FLEX]: nearest, roughly orthogonal, from the part's node groups. Store local coordinates in that non-orthonormal frame and rebuild them every frame in a Burst job or on the GPU (brief section 7). The binding mathematics is an ASSUMPTION; only the node-selection rules are documented.
- Validate at load time: at least 3 non-collinear nodes per group [ISSUES]; no duplicate node positions [FLEX].
- Mesh breaking: hide visual triangles whose bound nodes end up in different clusters, or whose frame spans a broken beam (ASSUMPTION; the docs only say polygons are removed [BEAMS]). Deform groups drive material swaps for glass and lights [FLEX].

---

## 9. Open questions (not specified by the docs)

1. **Integrator**: BeamNG's numerical integration scheme. We use symplectic Euler.
2. **Plastic update law**: the exact rest-length update, how fast `beamDeform` grows ("increases as the beam deforms"), and whether damping force counts for the deform and break tests.
3. **`deformLimit` / `deformLimitExpansion`**: maximum change as a fraction of the original length, or maximum length ratio? Examples use 1.1 and 1.2. What happens once the limit is reached?
4. **`deformationTriggerRatio`**: the quantity it is compared against (plastic strain?).
5. **BOUNDED limits**: does the limit spring add to or replace `beamSpring`? Is its force measured from the bound or from the spawn length? What is the blend shape inside `boundZone`? Do bounds follow plastic changes of the rest length?
6. **Fast damping**: does the fast coefficient replace the slow one or apply only above the split? We infer the latter.
7. **`dampCutoffHz`**: filter type and order; "frequency above which damping applies" is ambiguous.
8. **PRESSURED beams**: gauge vs. absolute pressure, the `volumeCoef` formula, and the reference length (spawn or precompressed).
9. **LBEAM**: force law and the units of `beamSpring`/`beamDamp` for l-beams.
10. **Contact**: penalty law, stiffness and damping; back-side thickness for each `externalCollisionBias` mode; the anticlip algorithm; how "dynamic priority over static" is realised.
11. **Group exclusion**: does a triangle count as "made of nodes within the same group" when all three nodes share the group, or when any do?
12. **NONCOLLIDABLE aero**: TRIS says "Have no collisions, only anticlip."; QUADS says "Have no collisions or aero." Do NONCOLLIDABLE triangles still produce drag and lift? Our default: no aero, configurable.
13. **Friction**: how node coefficients combine with `groundModel`/terrain; the exact Stribeck formula; `stribeckVelMult` units; the `softnessCoef` model; `treadCoef` on paved surfaces.
14. **Aerodynamics**: force formula, flat-plate coefficient, air density, angle dependence, post-stall lift.
15. **Pressure wheels**: nodes per ray and the internal triangle layout; whether `pressurePSI` is gauge pressure; `maxPressurePSI` defaults to 10, below typical 25-35 psi fills (a margin rather than an absolute cap?); how drive torque reaches the tire; `hasTireCoef` is not documented.
16. **Hydros**: units of `inRate`/`outRate`/`autoCenterRate`; whether `factor` scales the spawn or the precompressed length.
17. **Slidenodes**: spring direction (nearest point on the segment?) and any friction along the rail.
18. **Torsion bars**: the exact angle definition and how `deform` changes the reference angle.
19. **Flexbodies**: how mesh breaking selects the polygons to remove.
20. **Defaults that disagree between pages**: `frictionCoef` default 1 vs. "most of the time set to 0.5"; `staticCollision` default true [NODES] vs. "same as collision" [TIPS]; INTRO's "inversely proportional to speed" for damping, read here as a typo.
21. **Instability detection**: BeamNG shows "instability detected", but the criterion is not documented. Ours: NaN/Inf, node speed above a limit, or total energy growth over N steps; on trigger, pause and report the offending nodes.
22. **Gravity and air density** values used by BeamNG are not stated on these pages.
