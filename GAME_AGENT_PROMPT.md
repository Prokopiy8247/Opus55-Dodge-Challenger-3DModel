# PROJECT BRIEF: Drivable Soft-Body Crash Sandbox: Dodge Challenger SRT Hellcat Widebody (Blender + Unity)

You are an expert vehicle 3D artist, technical artist and real-time physics programmer. You will deliver a **small playable game/sandbox** in which the user **drives a Dodge Challenger SRT Hellcat Widebody around a test map and crashes it into obstacles**, with **BeamNG.drive-style soft-body physics**: the car deforms and breaks as a consequence of the simulation, not as a pre-made animation. The game is a test bench for the car: the 3D model must be thoroughly developed for physics and destruction, and the map exists to contain obstacles that exercise all of that.

**Roles of the tools:**
- **Blender 5.2.2 LTS (through the Blender MCP connection):** authoring. You model the car (exterior and interior), build the physics skeleton (nodes, beams, collision triangles, break groups), and export everything to the game.
- **Unity 6 (6000.6.0f1 is installed; Unity Hub is installed):** runtime. You build the playable game: the soft-body solver, the driving model, input, cameras, HUD, the test map with obstacles, record/replay, and a standalone Windows build.

Communicate with the user in **Russian**. Write all code, comments, file names and documentation in English.

**Decisions already made by the user (do not ask again):**
- The goal is a **playable game/sandbox** (driving + crashing on a test map), built with Blender for the car and a game engine for the runtime. The BeamNG engine is **not** used (the user will not run BeamNG).
- Blender version **5.2.2 LTS**; the car is a **Hellcat Widebody**, left-hand drive, **white body with black wheels** exactly as in the photos in `reference\`; interior and first-person view are required; pressurized tires and a real suspension model are required.
- Compute time and build time have **no limit set by the user**: choose what gives the best result, but report expected wall times.
- Engine choice: **Unity** (installed) was recommended by the consultant and is the working assumption. If P0 proves it unworkable, report the evidence and propose an alternative; do not switch silently.

---

## AUTONOMY MODE (highest priority; overrides every conflicting rule below)

The user has delegated the **whole project** to you and wants it finished **end to end without interruptions**. Work continuously from the current phase to the last one until every deliverable (section 1) is built and verified, and the final reports are written. **Do not stop at checkpoints, do not wait for confirmation, do not ask questions.**

This mode **cancels**:
- rule 6 ("stop at every checkpoint") and the "stop after each, wait for the user" wording of section 11 (you still run the gates and write the reports after every phase, then continue immediately);
- rule 8 and any "ask the user" instruction: decide yourself with the best available option, write the decision and the reason into `docs\decisions.md`, and continue. Collect real open questions and ask them once, in the final message;
- rule 11's "stop and propose": when an approach fails, try different approaches until it works, or apply the section 12 fallback and continue; never stall;
- the restrictions of section 2 "Safety": you may install and use any tool, package, MCP server or utility you judge necessary for the best result (for example a Unity MCP server, ffmpeg, extra Unity packages), may use any location on the machine that the work requires, and may run long jobs. Choose the **highest-quality** option, not the most conservative one.

**What stays (because it protects the work, not because it limits you):**
- Never overwrite the original `3DDodgeChallenger.blend`; keep versioned copies.
- Keep `docs\STATUS.md` (current phase, what is done, what is next, how to resume), `docs\changelog.md`, `docs\cost_log.csv` and a git commit after every phase, so you can resume after a context compaction or a session restart.
- Keep running the quality gates (section 14) and fix failures before moving on. Quality is the goal; speed is not.
- Final message (Russian) when everything is done: what is ready, where it is, how to run it, deviations from the plan and why, remaining open questions, and the cost report from section 18.

---

## Success definition, priorities and non-goals (read this first)

**Success = all of the following, demonstrated with evidence (screenshots, numbers, files):**
1. The Hellcat Widebody looks like the reference photos (silhouette overlay matches within 2 % of length/height).
2. It is **stable**: sits still, drives, and survives curbs without exploding.
3. It **deforms plastically and breaks** in a plausible, speed-dependent way when it hits the map obstacles.
4. The user can **launch the game and drive** (accelerate, brake, steer, shift) and crash the car, with live deformation, at an interactive frame rate.
5. Every run is **reproducible** (record/replay) and can be **captured to video** for YouTube.
6. A **first-person (driver's eye) view** works with a fully modelled interior: dashboard, animated instrument cluster, steering wheel that turns with the steering input, seats, mirrors, pedals; damage is visible from inside.
7. A **standalone Windows build** (`.exe`) of the sandbox exists, so the user can play without the Unity editor.

**Priority order when trade-offs are needed:** (1) stability, (2) plausible crumple and breakage, (3) driveability, (4) visual quality, (5) extra realism details. Never trade (1) for (4) or (5).

**Non-goals (do NOT spend time on them unless asked):** airbags, working lights/audio design, AI traffic, multiplayer, menus beyond a minimal start/pause screen, terrain sculpting, career/mission modes, fluid/fire simulation, copying any BeamNG proprietary content.

---

## 0. Non-negotiable rules

1. **Never overwrite the original file.** The project file is `W:\YouTube\3D Model Dodge Challenger\3DDodgeChallenger.blend`. It is only about 97 KB, so assume it is nearly empty; inspect it first and report what is in it. Save every working state as `3DDodgeChallenger_v001.blend`, `v002`, ... in the same folder.
2. **Save before every heavy operation.** MCP executes arbitrary Python inside Blender; a crash loses unsaved work. Commit/copy the Unity project state before large refactors.
3. **Keep every script as a file** under `tools\` (Blender side) or in the Unity project (runtime side) so everything is reproducible and re-runnable. Do not leave logic only inside one-off MCP calls.
4. **Do not run the solver inside Blender.** Blender is for authoring only; the physics runs in the Unity runtime. Keep Blender MCP calls short so the socket does not time out.
5. **Do not copy BeamNG assets.** BeamNG vehicle files (JBeam, meshes) are proprietary. Implement your own system based on the *public* documentation. Do not download or import BeamNG vehicles.
6. **Stop at every checkpoint** (section 11) and show results (viewport screenshots, numbers) before continuing.
7. **Be honest about limits.** If something has to be simplified (e.g. tire pressure model, interior detail), say so explicitly in the checkpoint report.
8. **Ask once, in one batched message**, if a decision is truly blocking. Otherwise choose sensible defaults, state them, and continue.
9. **Code the MCP calls defensively.** Prefer the data API (`bmesh`, `mesh.from_pydata`, `foreach_set`) over `bpy.ops` (which depends on UI context). Keep each call short (well under ~30 s), idempotent (safe to re-run), and make it print a short JSON status. Batch object creation. Never leave Blender in edit mode or a modal state at the end of a call.
10. **Self-verify before you report.** After each phase run the checks in section 14, fix failures, and only then report. Include the checklist with PASS/FAIL, not just a summary.
11. **Time-box and escalate.** If an approach has not produced a stable result after 3 distinct, documented attempts, stop, report the evidence and propose the cheapest alternative (see section 12) instead of continuing to thrash.
12. **Capture video assets as you go.** For every phase save before/after screenshots and short captures (Blender viewport or Unity game view) into `docs\video_assets\Pxx\` (named, dated). The user is making a YouTube video about this build.
13. **Track cost as you go.** Append a row to `docs\cost_log.csv` at every checkpoint and produce the final cost report described in section 18 (time, tokens, API-equivalent dollars).

---

## 1. Deliverables

| # | Deliverable | Location |
|---|---|---|
| D1 | Visual Hellcat Widebody (exterior, separate named parts, materials) | Blender `.blend`, exported FBX |
| D2 | Physics skeleton: nodes, beams, collision triangles, material presets, break groups | `sim\vehicle\*.json` (+ debug collection in Blender) |
| D3 | Fully modelled interior and first-person cockpit | Blender `.blend`, FBX, Unity prefab |
| D4 | Node-beam soft-body solver (Burst/Jobs) with plastic deformation, breaking and collisions | Unity project, `Assets\Sim\` |
| D5 | Vehicle dynamics: pressurized tires, suspension, steering, powertrain, brakes | Unity project, `docs\dynamics_report.md` |
| D6 | Mesh skinning from nodes to visual meshes (GPU or Burst) | Unity project |
| D7 | Test map with obstacles | Unity scene `Assets\Scenes\TestMap.unity` |
| D8 | Game layer: input (keyboard/gamepad), cameras (chase, bumper, cockpit, free), HUD, debug views, reset/repair, slow motion, record/replay | Unity project |
| D9 | Scripted regression scenarios S1–S8 with metrics, plus validation tests | `docs\metrics.csv`, `docs\validation_report.md` |
| D10 | Standalone Windows build and README (how to run, controls, how to tune) | `Builds\`, `docs\README.md`, `docs\controls.md` |

---

## 2. Tools, environment and operating notes

**Verified on the user's machine (confirm, do not assume):** Windows 11; CPU AMD Ryzen 7 5700X3D (8 cores / 16 threads); 64 GB RAM; NVIDIA GeForce RTX 5070 (Blackwell; driver 32.0.16.1692); free disk space is low on `C:` (about 19 GB), so **put everything on `W:`**. Installed: Blender 5.2.2, Unity Hub 3.22.2 and Unity 6000.6.0f1, Unreal Engine 5.8.2 (`W:\Unreal Engine 5\UE_5.8`) and Godot 4.7.2 (not used), Visual Studio Community 2026, .NET SDK 10, VS Code, Python 3.12, uv/uvx (WinGet), Git (`W:\Git`).

**Blender (authoring, through MCP):**
- **Where the car work happens (hard requirement):** the car, interior, skeleton debug geometry and materials are built **inside Blender, in the open project file, through the Blender MCP connection**. Do not model in other software.
- The Blender MCP add-on server answers on **localhost port 9876**; MCP server `mcp-for-blender` (pinned 2.1.9, telemetry disabled) is started by Claude Desktop; tools include `execute_blender_code`, `get_scene_info`, `get_addon_status` and a viewport/render image tool (`look`). The project file `W:\YouTube\3D Model Dodge Challenger\3DDodgeChallenger.blend` is open; **first action: save as `3DDodgeChallenger_v001.blend`** so the original is never overwritten.
- World setup in Blender: metric units, 1 unit = 1 m, **Z up**, car forward = **+Y** (document it; handle the axis conversion on export), scale applied on all objects, sensible origins.
- Naming: `CH_Body`, `CH_Hood`, `CH_Door_L`, `CH_Bumper_F`, ... for visual parts; `PH_Nodes`, `PH_Beams`, `PH_Tris` for the physics debug collection. Collections: `Car_Visual`, `Car_Interior`, `Car_Physics`.
- MCP coding rules: prefer the data API (`bmesh`, `mesh.from_pydata`, `foreach_set`) over `bpy.ops`; keep each call short (well under ~30 s) and idempotent; print a short JSON status; never leave Blender in edit mode; save before heavy operations.

**Unity (runtime, built by you):**
- Create the project with Unity Hub's installed editor 6000.6.0f1 at `W:\YouTube\3D Model Dodge Challenger\Unity\HellcatSandbox`. This version may be newer than the long-term-support release: **verify package compatibility in P0** (Burst, Collections, Mathematics, Input System, Test Framework, Recorder) and report problems before building on them.
- Drive Unity from the command line: `Unity.exe -batchmode -projectPath <path> -executeMethod <Class.Method> -logFile <file>` for imports, tests and builds; **do not install a third-party Unity MCP server without asking the user** (it executes code in the editor and has no audit; if the user agrees, pin the version and follow the same safety rules as for Blender MCP). Do not assume a screenshot tool exists: implement your own in-game capture (`ScreenCapture`) that writes PNG files so you can inspect results.
- Packages: Burst, Collections, Mathematics, Jobs, Input System, Test Framework, Recorder, Cinemachine (optional). Render pipeline: **URP** by default (choose HDRP only if the user asks).
- C# only for gameplay and solver; no editor-only code in builds; no managed allocations in the per-frame simulation path.
- **Unity licence:** batch mode needs an active Unity licence. In P0 verify that the editor starts in batch mode; if it reports a missing licence or sign-in, stop and ask the user (in Russian) to sign in via Unity Hub.

**Safety:** `execute_blender_code` runs arbitrary Python with the user's rights; keep the MCP server stopped when not working. Do not modify files outside the project folder (except Unity's own caches and the engine installation's `Library`/`Temp` areas); do not read personal files. Use the network only for documentation and for Unity Package Manager downloads of the packages listed above.

---

## 3. How BeamNG soft-body physics works (what to reproduce)

Research the official documentation first (https://documentation.beamng.com, sections *Introduction to JBeam*, *nodes*, *beams*, *triangles*), then summarise your understanding in `docs\physics_notes.md`. Core principles:

- A vehicle is a **skeleton of nodes (point masses) and beams (massless springs)**. Nodes are particles with mass that move freely. Beams have a node at each end and only keep a set distance; they do not transmit bending or torsion and rotate freely around nodes. Rigidity comes from **triangulated cross-bracing**. A box with no diagonals collapses.
- Every beam has **spring** `beamSpring` (N/m), **damping** `beamDamp` (N/(m/s)), **deform threshold** `beamDeform` (force above which the beam permanently changes its rest length, i.e. plastic deformation) and **break strength** `beamStrength` (force above which the beam snaps and no longer connects its nodes). Strength is normally above deform. If the two are close, the part is brittle (glass, plastic clips); if strength is far higher, the part is tough (frame rails).
- Very high stiffness relative to node mass causes vibration and instability, so node mass, stiffness, damping and time step must be balanced.
- **Break groups:** beams in the same group fail together (so a bumper, door or mirror detaches as a unit).
- **Collision is node-vs-triangle only.** Nodes collide with *collision triangles* ("coltris") spanned between nodes. Beams never collide. Triangles do not collide with each other or with world geometry. Nodes of the same group do not collide with that group's triangles. Collision force starts slightly before the surface (about 2.5 cm in BeamNG) to avoid clipping; dynamic contacts take priority over static/heightmap; at very high force a node can be pushed slightly through a surface and pop back.
- Typical placement hints from the docs: keep collidable nodes roughly 3 cm or more apart, avoid unnecessary triangles near each other, use non-collidable triangles to prevent snagging where needed.
- The physics step is small: BeamNG runs at **2000 Hz (0.5 ms per step)**.
- Damage emerges from stress: energy is absorbed by beams (spring energy, plastic work, breaking), not played back from pre-made animations.
- The **visual mesh follows the nodes** (flexbodies): when the skeleton crumples the panels crumple; when the skeleton's beams break the attached parts separate.

---

## 4. Physics specification (your own implementation)

### 4.1 State and integration
- SI units everywhere (m, kg, s, N).
- State per node: position, velocity, mass, flags (collision, selfCollision, staticCollision, fixed), friction coefficients (static and sliding), group id, part id.
- Fixed time step `dt = 0.0005 s` (2000 Hz) as the default; allow `dt` to be configured. Semi-implicit (symplectic) Euler is acceptable; justify any other choice.
- Output frames at 60 fps by default (≈ 33 sub-steps per frame); option to store at 240 fps for slow motion.
- Gravity 9.81 m/s². Optional later: aerodynamic drag per triangle (`dragCoef`).

### 4.2 Beam force and plasticity (pseudo-code, refine as needed)
```
L   = |p_b - p_a|              # current length
dir = (p_b - p_a) / L
v_rel = dot(v_b - v_a, dir)
F = k * (L - L0) + c * v_rel   # force along beam, positive = tension
if |k * (L - L0)| > deform_threshold:   # plastic deformation
    # move rest length so that spring force sits at the threshold
    L0 = L - sign(F_spring) * deform_threshold / k
if |F| > break_strength: beam.broken = True; propagate to its break group
apply +F*dir to node a, -F*dir to node b
```
- Support at least these beam kinds: **NORMAL**, **BOUNDED** (soft limit on how far it may compress or stretch), **SUPPORT** (stiffens only beyond a set length range to stop total crumple). Read the `beams` documentation for exact semantics of each and note any differences you implement.
- Optional: pre-compression, one-way (anisotropic) behavior, `PRESSURED`-style beams/triangles for tires (required, see 4.6).

### 4.3 Mass, stiffness and stability
- Node mass range: 0.5–15 kg for body/frame nodes, heavier for engine/drivetrain clusters. Sum of node masses must equal the target vehicle mass (≈ 2,000 kg).
- Stability guideline for explicit integration: keep `ω·dt < 0.5`, where `ω = sqrt(sum_k_attached / m_node)`. Compute this per node at load time and **auto-report nodes that violate it**, then fix by raising mass, lowering stiffness or adding damping. Do not just reduce `dt` blindly.
- Damping starting points: structural metal low damping ratio; plastic and rubber much higher; suspension dampers dedicated beams.
- Material presets (relative guidance, tune numerically; units depend on your node masses):
  - `steel_frame`: high spring, deform ≈ 0.4–0.6 × strength, strength ≈ 2× deform.
  - `steel_body_panel`: medium spring, low deform threshold, strength ≈ 2–3× deform, low damping.
  - `plastic_trim` / bumper cover: low spring, high damping, low deform, strength ≈ 3–4× deform.
  - `glass`: moderate spring, deform ≈ strength (brittle).
  - `rubber` (tire sidewall): low spring, very high damping, deform = unbreakable.
  - `mount` (engine/suspension/hinge): defined break strength to allow detachment.

### 4.4 Collision
- Node-vs-triangle for **vehicle self-collision** (off by default, enable only where needed, e.g. hood into engine) and **vehicle vs other bodies**.
- Node-vs-world for the ground (analytic plane or heightfield) and for static obstacles (triangle meshes with BVH or spatial hash).
- Penalty-based contact with Coulomb friction (static and sliding coefficients), small bias distance in front of surfaces (≈ 2.5 cm), thin-wall protection (swept test or velocity-limited sub-stepping) so nodes do not tunnel through walls at 120 km/h.
- Spatial acceleration (uniform grid / spatial hash) mandatory. Report average nodes, triangles and candidate pairs per step.

### 4.5 Complexity budget (starting target, report actuals)
- Nodes: 2,500–6,000 (the pressurized tires add about 100–200 nodes each). Beams: 12,000–40,000. Collision triangles: 3,000–8,000.
- **Real-time is required for the game**: at least 60 fps display with the physics stepping at **≥ 1,000 Hz (target 2,000 Hz)** on the user's machine (Ryzen 7 5700X3D, 16 threads; RTX 5070). Benchmark early (P0) with a synthetic 3,000-node / 15,000-beam structure and report steps/s per frame. If the full budget is not reachable, in order: reduce node count in non-critical areas, use per-region time stepping or substep scaling with stiffness adjustment, move spring integration to a compute shader, and only then lower the step rate. Always state which mode is active.

### 4.6 Pressurized tire model (required, not a stretch goal)
- Each tire is a closed node-beam torus: **rim ring nodes** (inner and outer rows, rigidly attached to the wheel hub), **sidewall nodes**, **tread/belt nodes** (several per cross-section, 24–48 cross-sections around the wheel), and a **closed inner triangle mesh** that defines the air volume.
- Beams: radial (rim to belt), circumferential (belt ring), lateral (belt side to side), diagonal bracing of sidewalls, and bead beams holding the tire on the rim. Rubber is low-stiffness and highly damped; belts are stiffer; the bead can fail (tire coming off the rim after a hard impact).
- **Pressure force:** treat the air as an ideal gas (isothermal by default): `p = p0 · V0 / V`. For every inner triangle apply `F = (p − p_atm) · area · normal` split across its three nodes. Compute the cavity volume each step by summing signed tetrahedra volumes.
- Target inflation about 32–36 psi (≈ 220–250 kPa); Widebody size 305/35 ZR20 (outer diameter ≈ 720 mm; verify; the standard body uses 275/40 ZR20, ≈ 728 mm).
- **Punctures/leaks:** when sidewall or tread beams break (or the triangle patch is flagged), pressure bleeds off with a leak coefficient so the tire deflates progressively; deflated tire changes ride height and handling.
- **Contact friction** (tread nodes against ground triangles and other geometry): Coulomb friction with a load-sensitive coefficient and a Stribeck-type transition from static to sliding friction. Make `mu_peak`, `mu_slide`, `load_sensitivity`, `softness`, `stribeck_exponent` explicit tunable parameters per tire compound and per surface (asphalt, concrete, grass, gravel). Verify that cornering force rises with slip angle and saturates.
- Rolling resistance and tire thermal effects: rolling resistance required, thermal effects optional.

### 4.7 Suspension (required, tuned from first principles)
- Front: double-wishbone / SLA with coil-over strut and anti-roll bar. Rear: multi-link (5-link style) independent with coil-over and anti-roll bar. Model each arm as a small triangulated node-beam structure with mounting points on the subframe so bending and breaking of arms is possible.
- Springs and dampers are dedicated beams (spring beam with `spring` only, damper beam with `damp` only, or a combined coil-over with separate compression/rebound damping). Add **bump stops** and **rebound limits** (BOUNDED-style beams), plus anti-roll bars as torsional-equivalent beams coupling left/right.
- Derive stiffness from a ride target rather than guessing: for each corner `k = m_sprung · (2π f)²` with ride frequency about 1.2–1.5 Hz front and 1.4–1.7 Hz rear; damping `c = 2 ζ √(k · m_sprung)` with ζ ≈ 0.25–0.4 on rebound and slightly less on compression. Document the numbers.
- Static setup: ride height, static sag, weight distribution (front-heavy, roughly 55–57 % front; verify), wheel loads per corner printed at rest and checked against the target.
- Suspension must also deform plastically (bent control arms, bent wheel alignment) and break at defined loads, with visible consequences (wheel toe/camber change, car pulling to one side).

### 4.8 Steering
- Front steering via a **rack**: a steering rack node pair driven by a controllable (hydraulic-style) beam whose length changes with the steering input, connected to the steering arms by tie-rod beams. Steering angle must be visible on the visual wheels and spindles.
- Steering ratio and lock-to-lock about 2.5–3 turns; limit the maximum wheel angle (about 30–35° at the wheel); speed-sensitive steering reduction so the car is drivable at 150+ km/h.
- Damage to tie rods/rack must cause a realistic change (toe error, crooked steering).

### 4.9 Powertrain
- Engine: supercharged 6.2 L V8, ≈ 707 hp at 6,000 rpm and ≈ 650 lb-ft (≈ 881 N·m) torque around 4,000 rpm, redline about 6,200 rpm (verify for the chosen model year). Idle about 700 rpm. Use a torque curve (tabulated vs rpm) with a throttle map, engine inertia and engine braking.
- Transmission: 8-speed automatic (a 6-speed manual is optional). Provide gear ratios, final drive and efficiency from public data (not found in simple searches, so look them up and document sources); torque converter modeled as a simple slip clutch. Automatic shift logic with manual override (gear up/down keys).
- Drive layout **RWD with a limited-slip differential** (model the diff as a preload + torque-bias coupling), torque applied to the rear wheel hubs as tangential forces on rim nodes (or an equivalent torque coupling) so wheelspin and loss of traction emerge from the tire model.
- Optional: traction/stability control toggles (off by default for burnouts), launch control.
- Engine/drivetrain damage is optional; at minimum an engine detached from its mounts must stop producing torque.

### 4.10 Brakes
- Disc brakes on all four wheels with brake torque distribution (approx. 60/40 front/rear; verify), pedal input → brake torque with ABS optional/toggle. Handbrake acts on the rear wheels only. Brake torque must be able to lock wheels and produce skidding.

### 4.11 Aerodynamics and resistances
- Aerodynamic drag and lift per triangle (`dragCoef`, `liftCoef`) or an equivalent frontal-area model; consider the effect of a deformed hood/bumper (optional). Rolling resistance and drivetrain losses so top speed and coast-down are plausible.

### 4.12 Runtime architecture in Unity (the game)
- **Solver:** C# with Burst-compiled jobs, `Unity.Mathematics`, `NativeArray`/structure-of-arrays layout. Fixed step `dt = 0.5 ms` (2000 Hz) accumulated against the frame time (≈ 33 substeps per 60 fps frame) with a cap on substeps per frame and a visible "slow-down" indicator if the cap is hit. Parallel force accumulation via per-thread buffers or beam colouring (no atomics races); node-triangle collision with a uniform spatial hash rebuilt per substep (or every N substeps with a safety margin); static world collision against the obstacle meshes using your own BVH / SDF / analytic shapes. **Do not use Unity's PhysX for the car**; PhysX may be used only for non-car conveniences (camera collision, triggers).
- **Rendering:** each visual vertex is bound to nearby nodes (section 7). Skin on the GPU with a compute shader or in a Burst job writing mesh vertex buffers; no CPU readbacks per frame. LODs for the interior while driving outside.
- **Input:** Unity Input System; keyboard and gamepad. Default keys: `W` throttle, `S` brake/reverse, `A`/`D` steer (smoothing, speed-sensitive), `Space` handbrake, `Q`/`E` gear down/up, `R` reset car to last safe position (clears damage), `Shift+R` full repair, `C` cycle cameras, `T` slow motion (0.1×), `N` toggle node/beam debug view, `H` stress heat-map, `P` pause/step, `F5` start/stop input recording, `F6` replay.
- **Cameras:** chase camera with damped follow, bumper camera, **first-person cockpit camera at the driver's eye point (section 5.4)** that rides on the cabin nodes, and a free camera for crash close-ups.
- **HUD:** speed, rpm, gear, throttle/brake/steering, G-force, broken-beam count, simulation Hz/fps, active quality mode.
- **Record and replay:** record timestamped control inputs plus initial state; the replay is deterministic at the same fixed step (same seed, same inputs), and can run with more substeps for video quality. Capture video with Unity Recorder (1440p/60 fps) or frame sequences.
- **Quality of life:** pause menu with scenario spawn points at each obstacle, a "teleport to obstacle N at speed V" helper for tests, and a settings file for tuning parameters (`params` hot-reload without restarting is a bonus).

### 4.13 Driving acceptance targets (approximate; verify, tolerance ±15 %)
- 0–100 km/h in about 3.5–4.0 s (RWD, warm tires, launch control off may be worse); top speed limited around 290–320 km/h by drag and gearing (stock Hellcat is reported near 320 km/h; verify).
- 100–0 km/h braking in about 33–38 m on asphalt.
- Steady-state cornering on a skidpad about 0.85–1.0 g.
- Plausible weight transfer: visible dive under braking, squat under acceleration, roll in corners.
- The car must be controllable: no self-oscillation at speed, no random flipping, recoverable slides, reasonable understeer/oversteer balance (RWD, 700+ hp: easy to spin tires on launch and in corners).

---

## 5. Visual car model specification

### 5.1 Reference dimensions (verify; trim differences exist)
Target: **Challenger SRT Hellcat Widebody** (3rd generation, 2015–2023 body), left-hand drive. Approximate figures (third-party databases; verify and document sources): length **5,018 mm**, wheelbase **2,951 mm**, height **≈ 1,450–1,461 mm**, width **≈ 1,990 mm** without mirrors for the Widebody (the standard body is ≈ 1,923 mm; the flares add roughly 3–4 cm per side), curb mass **≈ 2,040 kg** for the Widebody (≈ 4,400–4,490 lb depending on source), tires **305/35 ZR20** on 11-inch-wide wheels (verify; standard body uses 275/40 ZR20), wider track than the standard car (derive from photos + width). Engine: 6.2 L supercharged V8 (about 230–260 kg for the engine block assembly; verify).
Do not guess proportions from memory only: build from the reference photos with a silhouette overlay (5.1b).

### 5.1b Reference inventory (provided by the user in `reference\`) and protocol
**Exterior photos (white Hellcat Widebody, dealer showroom):**
- `1.jpg`, `4.jpg` front three-quarter views (both sides), `2.jpg` almost straight-on front view, `3.jpg`, `5.jpg` rear three-quarter views (both sides), `6.jpg` almost straight-on rear view.
- `Передние фары.png` close-up of the headlight/grille strip, `Задняя фара.jpg` rear lamp close-up, `Зеркало заднего вида.jpg` side mirror close-up (blind-spot and heater icons).

**Interior photos (black leather, red belts):**
- `Салон 1.jpg` overhead-ish view of the dashboard and both front seats; `Салон 2.jpg` driver's view of dashboard and centre console; `Панель.jpg` instrument cluster close-up; `Руль 1.jpg`, `Руль 2.jpg` steering wheel (flat-bottom SRT wheel, paddles, buttons); `Кресла 1.jpg`, `Кресла 2.jpg` front seats (SRT Hellcat embossed backs, perforated inserts, contrast stitching); `Задние кресла 1.jpg`, `Задние кресла 2.jpg` rear bench with red belts and centre armrest.

**What the photos show (use as the ground truth for details):**
- Wide fender flares on all four wheels (Widebody); front fascia with **two round projector headlights with halo rings on each side** and a full-width black grille with an SRT/Hellcat badge on the right-centre, a large lower mesh intake plus two small side ducts, and a black front splitter; **matte black hood with one centred scoop and two small side heat-extractor vents**, **matte black roof panel** (the A/B/C pillars and the rest of the body are white); side mirrors on stalks, white oval housings; rear: black flat-blade spoiler with SRT badge and a small camera, **segmented LED racetrack tail-lamps**, centred "DODGE" lettering, small white licence-plate recess, black lower valance with **two rectangular black exhaust tips (one at each corner)**, small roof antenna.
- Wheels: 5-spoke, satin dark graphite/black, large visible brake calipers (orange/red), wide low-profile tires.
- Interior: flat-bottom steering wheel with SRT badge, paddles, multi-function buttons; round instrument pods with red-lit tachometer (to 7 ×1000, redline from about 6,000) and speedometer (to 200 mph) around a digital centre display that shows km/h and gear (P R N D M); 8.4-inch touchscreen with Performance Pages; textured carbon-style trim around the vents and centre console; red illuminated start button; automatic shifter with cup holders; leather door cards; rear bench seat (two outer seats and a centre armrest).

**Known gaps (no photo exists):** pure side profile (orthographic-like), pure top view, underbody/engine bay, open-door and trunk views, wheel face-on view.

**Protocol:**
1. In P1 first build the proportion block (body mass, glass, wheel positions) using the dimension table and the front/rear/3-quarter photos; estimate the side profile from the 3-quarter photos (use known perspective: wheelbase, height, tire diameter as scale references) and state the uncertainty. Ask the user once (batched, Russian) for a **pure side photo from a long distance** and a **top view** if you need them; do not wait on them.
2. Import references as image planes with **measured scale** (use wheel diameter ≈ 720 mm and wheelbase 2,951 mm as scale), lock them, and build with a **silhouette-overlay check**: render the model with the matching camera/lens and compare with the photo outlines.
3. If web access exists, you may additionally consult *dimensions.com* ("Dodge Challenger SRT Hellcat (3rd Gen)" scaled drawings; verify license) and public spec sheets for numbers. Treat third-party drawings as approximate. Do not import third-party car models as the final car.
4. Do not invent small details that are not in the references; list assumptions in `docs\model_notes.md`.

### 5.2 Parts (each is a separate object, named, with its own material)
Body shell (with roof and pillars), hood (with functional scoops/heat extractors and hood latch area), front fenders L/R, doors L/R (outer skin + inner panel), trunk lid, rear quarter panels, front bumper cover + lower valance + splitter, rear bumper cover + diffuser, grille, headlights L/R, taillights (full-width LED light bar), side mirrors L/R, door handles, windshield, side windows, rear window, roof, rocker panels, exhaust with 2 rectangular tips (as in the photos), underbody/floor pan, fuel tank (simple), engine block with supercharger, radiator and core support, front/rear subframes, suspension arms and struts (simple), brake discs/calipers, 4 wheels (rim + tire separate), **full interior (section 5.4)**, Widebody fender flares (separate objects or integrated into fenders/quarters as on the real car), license plate, badges (simple).

### 5.3 Mesh quality rules
- Quad-dominant topology with clean edge flow; panels thin (1–2 mm real thickness via Solidify or modelled), correct panel gaps (≈ 4–6 mm).
- **Panel density:** enough evenly distributed vertices to bend smoothly (target edge length ≈ 3–6 cm on large panels) — damage must not look faceted. Export at the final tessellation; do not rely on runtime subdivision.
- No n-gons on deforming panels; no overlapping geometry between parts; every part has its own origin.
- UVs for paint/trim; PBR materials: clearcoat paint (**gloss white**, user's choice), **dark satin-graphite/black wheels** as in the references, **matte black hood and roof panel**, **black rear spoiler**, white painted mirror housings, black grille/trim, tinted glass, chrome/satin accents, rubber, plastic, brake disc with dark calipers.
- Poly count budget: visual car ≈ 300k–800k triangles total at subdivision level used for rendering.

### 5.4 Interior and first-person (cockpit) view (required)
The interior is visible in the first-person camera, through the windows in replays, and after crashes, so it must be modelled and deform with the cabin.

**Modelling targets (left-hand drive, from the interior references):**
- Dashboard (upper pad, vents with slats, trim with carbon-style texture), 8.4-inch touchscreen (Performance Pages look), red start button, instrument cluster hood with two round pods and a digital centre display, glove box, A-pillar trims, headliner, sun visors, interior mirror.
- Steering wheel: flat-bottom SRT wheel with badge, paddle shifters, multi-function buttons, stitching; **rotates with steering input** (correct ratio, about 2.5–3 turns lock-to-lock), steering column (breakable/collapsible in hard impacts).
- Instruments (animated by the simulation): tachometer 0–7 ×1000 with redline from ≈ 6,000; speedometer in mph with km/h digital readout; coolant temperature and fuel gauges; gear indicator P R N D M (with current gear); optional warning lights (door ajar, seat belt). Implement in Unity as a small component that sets needle rotations and text each frame from the simulation state.
- Centre console: automatic shifter with boot, switch panel with buttons, cup holders, armrest/storage lid; door cards with window and lock switches, door handles, speaker grilles; floor mats, pedals (accelerator, brake, footrest; pedals move with input).
- Seats: two front bucket seats (SRT Hellcat embossed backs, perforated inserts, stitching, headrests, side bolsters) and a rear bench with two outer positions and a centre armrest; red three-point seat belts (front and rear).
- Mirrors: interior rear-view mirror and both side mirrors show the scene behind the car (use Unity reflection probes or a render-texture camera; document the performance cost and provide a cheaper fallback).
- Visible driver-view details: hood visible from the driver's eye point with the scoop; A-pillars; windshield with frit band; correct field of view (≈ 80–95° horizontal; configurable) and eye height (≈ 1.05–1.10 m above ground; verify against the photos).

**First-person camera:** driver's eye point inside the head position; small head-bob/offset from g-forces is optional; **cockpit camera rides on the cabin nodes** (not on a rigid body frame) so the view shakes and shifts realistically in impacts; keys to cycle cameras are in 4.12. Option to hide the steering wheel/driver's hands is not needed (no driver model).

**Deformation and breakage from inside:**
- Interior parts are bound to the passenger-cell node groups (dashboard, door cards, seats, headliner), so they move with the structure; **steering column and dashboard can intrude** in severe frontal hits; seats are mounted on floor nodes via breakable mounts; door cards deform with the doors.
- Glass: the windshield and windows crack/shatter and are visible from inside; the hood crumpling, buckling and hinge failure are visible through the windshield.
- No occupants are required; do not model airbag deployment (non-goal).

**Quality and budget:** interior visual mesh budget ≈ 150k–400k triangles total; apply LOD/lower subdivision for the interactive display; only the parts the first-person camera can see need high detail; export interior as a separate FBX with its own LODs (dashboard, steering wheel, instruments, front seats, A-pillars, visible door cards).

---

## 6. Physics skeleton construction

Build the skeleton as a separate low-poly structure that mirrors the real car's load paths. Generate it by script (parametric) rather than clicking by hand, so it can be re-tuned.

### 6.1 Structural zones
- Front crush zone: bumper beam, crush cans / front rails, radiator support, hood hinges and latch, fender mounts.
- Engine bay: engine block + supercharger (heavy node cluster), transmission, engine cradle with mounts that can fail.
- Passenger cell: firewall/bulkhead, floor pan, A/B/C pillars, roof rails and roof bows, door frames, sills (rocker panels). Make it noticeably stiffer than crush zones so survivability is plausible.
- Interior structure inside the passenger cell: dashboard cross-beam and steering column (with collapse threshold), seat frames on floor mounts, door-card nodes tied to door inner panels, headliner nodes tied to roof bows; these carry the visual interior meshes of section 5.4.
- Rear zone: rear rails, trunk floor, fuel tank mounts, rear bumper beam.
- Doors, hood, trunk: each a separate node group connected to the body by hinge and latch beam groups with defined strength so they can open, bend, or tear off.
- Suspension: front double-wishbone-like arms and strut, rear multi-link; springs and dampers as dedicated beams; spindle/hub nodes; wheel mounts that can break.
- Wheels: full pressurized tire model from section 4.6 (rim rings, sidewall, belt/tread nodes, closed inner volume, ground contact through tread nodes); wheel hubs carry torque from the powertrain (4.9) and brakes (4.10).
- Suspension, steering and drivetrain mounting points follow sections 4.7–4.9; the engine/transmission cluster is mounted on the cradle with breakable mounts.
- Glass: windshield (laminated: can crack but stay attached for a while), side and rear windows (break easily).
- Plastic trim: bumper covers attach with weak clip beams.

### 6.2 Collision triangles
- Cover the exterior surface of each part with outward-facing triangles (counter-clockwise winding), plus inner triangles where inner surfaces matter.
- Use non-collidable triangles for anti-clip support if you implement that concept.

### 6.3 Break groups
Define at least: `bumper_F`, `bumper_R`, `hood`, `trunk`, `door_FL`, `door_FR`, `mirror_L`, `mirror_R`, `wheel_FL/FR/RL/RR`, `exhaust`, `headlight_L/R`, `glass_windshield`, `glass_side_*`, `glass_rear`.

### 6.4 Export format
Plain JSON with arrays: `nodes` (id, x, y, z, mass, flags, friction, group, part), `beams` (id, a, b, type, spring, damp, deform, strength, breakGroup, limits), `triangles` (a, b, c, group, dragCoef, breakGroup), `parts` (name, node ids, linked visual objects). The Unity solver loads only this file (and the FBX meshes) and has no dependency on Blender.

---

## 7. Export from Blender and skinning in Unity

**Export (Blender → Unity):**
1. **Visual meshes:** one FBX per part group (body panels, doors, hood and trunk, bumpers, glass, wheels and tires, interior, engine, underbody), correct scale (1 unit = 1 m) and axes, applied transforms, named exactly as in section 5, with PBR materials set up for URP. Keep a mapping file `parts.json` (part → FBX → mesh name).
2. **Skeleton:** `geometry.json` from section 6.4 plus `params.yaml` (materials and tuning values).
3. **Skinning data (computed in Blender or in a Unity editor script):** for every visual vertex store up to 4 node indices (same part group only), weights and the vertex coordinates in the local frame of those nodes at rest. Write a compact binary file next to each FBX.
4. Re-export is one command (`tools\export_all.py` in Blender, `Tools/Import Car` in Unity) so tuning iterations are cheap.

**Skinning (runtime):**
- Bind each visual vertex to its nearest `k = 4` nodes of the same part, using local frames built from 3 nearest nodes (origin, axes by Gram–Schmidt) plus inverse-distance weights; final position is the weighted sum of per-node-frame reconstructions. **Do not use plain displacement blending**: it breaks when the whole car rotates.
- Detached parts have their own nodes, so after their linking beams break they fly free automatically.
- Glass: pre-fractured shard meshes (Cell Fracture in Blender) swap in when the glass beams break; shards inherit node velocities.
- Validation: at rest, the skinned meshes reproduce the original meshes within 1 mm; report max vertex displacement per frame to catch spikes.

---

## 8. Test map (Unity scene `TestMap`)

Build the map **in Unity** (code-generated geometry, ProBuilder-style primitives, or props exported from Blender). Compact flat asphalt proving ground, **up to 300 m × 200 m** (smaller is fine as long as every obstacle has its run-up lane), coordinates in metres, measuring marks every 10 m, and a **60 m clean run-up lane** per obstacle so every test can reach target speed. Rigid, static, with proper collision meshes, and friction coefficients (asphalt ≈ 0.9, concrete ≈ 0.8, grass ≈ 0.6; document the values used).

| ID | Obstacle | Size / spec | Purpose |
|---|---|---|---|
| O1 | Concrete wall, full frontal | 12 m wide × 3 m high × 1 m thick | Full-width frontal crash |
| O2 | Same wall with offset marker | 40 % overlap line painted on ground | Offset frontal crash |
| O3 | Steel pole / lamp post | Ø 0.30 m × 6 m, fixed in ground | Narrow-object impact |
| O4 | Jersey barrier row | 6 units, each ≈ 3.66 m long × 0.81 m high, placed at 20° to the lane | Glancing / side impact |
| O5 | Guardrail section | ≈ 15 m, posts every 1.9 m, W-beam height ≈ 0.7 m | Scrape and glancing hit |
| O6 | Ramp + landing pad | Ramp 6 m long, 1.2 m high; landing 25 m beyond | Jump, hard landing, possible roll-over |
| O7 | Curb + speed bump | Curb 0.15 m; bump 0.10 m high × 3 m | Low-speed suspension/wheel damage |
| O8 | Dynamic debris field | 12 barrels (Ø 0.58 × 0.88 m, ≈ 20 kg), 20 boxes (0.5 m cubes, ≈ 5 kg), 8 traffic cones (0.7 m, ≈ 1.5 kg), wooden fence 6 panels | Secondary collision, scattering |
| O9 | Drop-off / bank | 3 m ledge with lower pad, plus 30° bank | Fall / rollover |

Debris must interact with the soft body. Simplest consistent approach: model debris as additional small rigid node-beam bodies in the **same solver** (e.g. box = 8 nodes + cross braces) so there is one physics world.

---

## 9. Test scenarios

The **main mode is interactive driving** (D8): the user spawns on the map, drives to any obstacle at any speed and angle, and crashes. The table below defines **scripted regression scenarios** that use recorded or programmatic inputs (target speed hold, steering waypoints) so results are comparable between builds. Each scripted scenario also has a driven variant that can be recorded and replayed.

| ID | Description | Entry speed | Notes |
|---|---|---|---|
| S1 | Full frontal into O1 | 50 km/h | Baseline |
| S2 | 40 % offset frontal into O2 | 64 km/h | Offset load path, door/pillar behaviour |
| S3 | Pole impact into O3 (aimed at front axle) | 50 km/h | Deep intrusion expected |
| S4 | Side hit into O4 (barrier row at 20°) | 40 km/h | Sliding contact |
| S5 | Ramp O6 and landing | 80 km/h | Suspension and underbody damage |
| S6 | Guardrail scrape O5 | 70 km/h | Glancing, partial detachment |
| S7 | Low-speed nudges into debris O8 | 10–20 km/h | Light damage, barrels move |
| S8 | High-speed full frontal into O1 | 120 km/h | Severe, cabin damage, parts detach |

For each scenario record: peak deceleration of the cabin centre of mass, crush depth, number of broken beams, number of detached parts, total energy (kinetic, spring, plastic work, lost to breaking, friction) vs time. Save `sim\cache\Sx\` (input recording and results) and a ≈ 6–10 s capture from Unity with at least two camera angles (a side camera and a tracking camera), plus a slow-motion variant (replay at ≥ 240 fps).

### Acceptance criteria
- **Stability**: car at rest on the ground settles within 1 s, max node speed < 0.01 m/s afterwards, ride height changes < 2 cm; no energy gain without impact.
- **Plausibility**: damage grows monotonically with speed; S1 at 50 km/h crumples bumper, hood and front rails but keeps the cabin intact; S8 at 120 km/h is clearly more severe. As a sanity range (approximate; verify against public crash-test data), a 50–56 km/h full-width rigid-barrier crash of a car like this typically shows around 0.5–0.7 m of crush and peak deceleration in the tens of g.
- **Visual**: no mesh tearing, no vertex spikes, no tunnelling through walls at 120 km/h, no jittering at rest.
- **Reproducibility**: fixed time step, fixed seeds, same input gives bit-comparable caches (within float tolerance).
- **Driveability**: all driving targets of section 4.13 met within tolerance; steering, throttle and brakes respond without noticeable lag; the car does not self-destruct at rest or while driving normally over curbs and bumps at 30–50 km/h.
- **Interactive performance**: report physics steps per second and displayed frames per second while driving; target ≥ 1,000 Hz physics (2,000 Hz goal) at ≥ 1× real time and ≥ 60 fps display (≥ 30 fps absolute minimum). If this is not reached, follow the fallback order of section 4.5 and state clearly which mode is active.

---

## 10. Validation tests (run before trusting the car)

1. Single beam stretch/compress and oscillation frequency vs analytic `sqrt(k/m)`.
2. Two-node pendulum, hanging chain: energy conservation within a few percent over 5 s.
3. Cube of nodes with and without diagonal braces (shows why bracing matters).
4. Beam bending / crush test with a falling mass: force vs displacement curve shows elastic, plastic and breaking regions.
5. Rigid box drop onto ground and onto a slope (friction check).
6. Car drop from 0.2 m onto flat ground and settle.
7. Car sliding on ground (friction) and braking from 50 km/h with locked wheels.
8. Node-vs-triangle tunnelling test at 120 km/h against a 20 cm thick wall.
9. Tire tests: static load vs deflection, pressure vs inflation volume, rolling free on a flat plane, slip-angle sweep (lateral force curve), longitudinal slip sweep, puncture/leak response.
10. Suspension tests: static sag per corner, bump/rebound response (step input), curb strike at 20 km/h, body roll in a steady cornering test, anti-roll bar effect.
11. Steering test: angle vs input, ratio, speed-sensitive reduction, return to center.
12. Powertrain tests: idle, rev limit, gear ratios, 0–100 km/h, top-speed run, engine braking, wheelspin on launch.
13. Brake tests: 100–0 km/h stopping distance, ABS toggle, handbrake lock-up, fade-free.
14. Drive tests on the map: slalom, skidpad circle, figure-8, driving over curb and speed bump, jump from ramp and landing; car stays controllable.
15. Record/replay determinism test: the same input recording must reproduce the same path within tolerance.

Write results with plots/screenshots into `docs\validation_report.md`.

---

## 11. Phases and checkpoints (stop after each, wait for the user)

| Phase | Work | Checkpoint output |
|---|---|---|
| P0 | Environment audit (Blender MCP, Unity editor and licence in batch mode, packages, GPU), create the Unity project, read BeamNG docs, write `physics_notes.md`, run a **Burst solver micro-benchmark** (3,000 nodes / 15,000 beams, 2000 Hz), plan and risks | Short plan + benchmark numbers + open questions |
| P0.5 | **Vertical slice:** simple box-shaped car (30–60 nodes, 4 simple wheels) built through the whole pipeline: Blender export → Unity solver → driven on a flat plane → crashes into a wall → screenshot/video | Screenshots + timing numbers. Proves the pipeline before the Hellcat |
| P1 | Visual Hellcat Widebody **exterior** | Orthographic + 3/4 screenshots, silhouette overlays vs references |
| P1b | **Interior and cockpit view** (section 5.4) | Cockpit-view screenshots compared with the interior references |
| P2 | Physics skeleton, material presets and the export pipeline | Debug-view screenshots, node/beam counts, mass check |
| P3 | Solver core + structural validation tests (tests 1–8) in Unity | `validation_report.md`, steps/s |
| P3b | Vehicle dynamics: pressurized tires, suspension, steering, powertrain, brakes; tests 9–14, driving targets (4.13) | `dynamics_report.md`, plots |
| P4 | Skinning in Unity and first scripted crash S1 | Screenshots before/after, metrics |
| P4b | Game layer: input, cameras, HUD, debug views, reset/repair, record/replay (test 15) | Short capture, fps/Hz numbers, `controls.md` |
| P5 | Test map with all obstacles | Top-down and perspective screenshots with dimensions |
| P6 | All scripted scenarios + driven runs, parameter tuning | Per-scenario summary table + captures |
| P7 | Polish, standalone Windows build, README, **final cost report (section 18)** | Build path, README, `docs\cost_report.md` |

If a phase blows past its budget, report the problem and the cheapest alternative instead of silently degrading quality.

---

## 12. Known risks and fallbacks

- **Solver too slow for real-time:** first reduce nodes in non-critical regions and use cheaper tire/collision representations; then move spring integration to a GPU compute shader; then lower step rate with stiffness scaling and document the effect. Keep the offline high-fidelity replay path.
- **Instability / "exploding" car:** fix mass distribution, stiffness, damping and node valence first; sub-step second.
- **Nodes tunnelling:** thicker collision bias, velocity-limited sub-stepping, thicker triangles in front of obstacles.
- **Pressurized tire unstable:** build in steps (unpressurized ring with contact friction, then pressure with one cross-section, then full torus), damp the pressure force, verify the cavity volume stays positive; it remains required.
- **Unity 6000.6 package incompatibility:** report with evidence and propose the nearest long-term-support editor; do not switch silently.
- **GPU/driver quirks on the RTX 5070:** keep CPU Burst path as the baseline; treat compute-shader solver as an optimization.
- **Floating-point nondeterminism across runs:** use fixed order of accumulation, fixed seeds; accept tolerance-based replay validation.
- **Blender MCP timeouts:** keep calls short and idempotent.
- **Scope creep:** respect the non-goals list.

---

## 13. Reporting style

At each checkpoint: 5–10 lines in Russian, then screenshots/numbers. List what was built, what deviates from the spec and why, what is next, and any question that blocks progress. Keep a `docs\changelog.md` with version, date, what changed.

---

## 14. Quality gates and self-review (run before every checkpoint)

**G-Model (P1):** orthographic side/front/top screenshots overlaid on reference images; report length/width/height/wheelbase in metres vs targets (±2 %); no flipped normals, no non-manifold edges on body parts, no overlapping parts, all parts named per section 2; panel gaps visible; wheels round and correctly placed.
**G-Interior (P1b):** driver-eye camera screenshot matches the reference layout (steering wheel position, cluster, centre screen, shifter) at the same FOV; gauges respond to test values (needle angles for 0, 3000, 6000 rpm and 0, 100, 200 mph); steering wheel rotates with steering input; mirrors show the scene; interior triangle budget reported; no z-fighting or clipping through the dashboard at the cockpit camera.
**G-Skeleton (P2):** node, beam, triangle counts reported; total mass equals target ±1 %; centre of mass position and axle load split reported; every node is connected; no isolated components; no duplicate nodes within 1 cm unless intentional; no node with `ω·dt ≥ 0.5`; every outer-surface triangle has outward winding (checked numerically).
**G-Solver (P3):** tests 1–8 pass numerically; energy drift without impact below 1 % over 10 s; deterministic re-run matches.
**G-Dynamics (P3b):** tests 9–14 pass; target table in 4.13 filled with measured values.
**G-Crash (P4/P6):** for every scenario report the metrics table, check monotonic damage vs speed, and view at least 3 camera angles; no tunnelling, no spikes, no mesh inversion.
**G-Drive (P4b):** measured physics Hz, display fps, input latency (key press → visible reaction) reported; 5-minute continuous drive without divergence.
**G-Build (P7):** the standalone Windows build starts from the executable, runs the test map at the reported fps, controls work, and a short capture at 2560×1440 / 60 fps is produced.

Each gate is a short script (`tools\gate_*.py`) that writes a PASS/FAIL JSON and a human-readable summary into `docs\gates\`.

---

## 15. Calibration and tuning methodology (do not tune by feel only)

1. **Order:** tune static (mass, centre of mass, ride height) → suspension and tires (dynamics tests) → structure stiffness (static load tests) → crash behavior (deform/break thresholds) → visuals.
2. **Crash targets** (approximate public-test conventions, verify): NHTSA-style full-width rigid-barrier frontal at about 56 km/h (35 mph); IIHS moderate-overlap frontal at about 64 km/h (40 mph), 40 % overlap on a deformable barrier. Compare qualitative outcomes: crush depth, intrusion into the passenger cell, peak deceleration and pulse duration. Note that this car is heavy (≈ 2 t), so crush will be larger than for a compact car.
3. **Parameter file:** all material and structural parameters live in `sim\vehicle\params.yaml` (or JSON), separate from geometry, so tuning never needs regenerating the skeleton.
4. **Regression log:** keep `docs\tuning_log.csv` (run id, parameter changes, metrics) so the user can see what changed and roll back.
5. **Sensitivity:** before final tuning run a small sweep on the 5 most influential parameters (e.g. rail deform threshold, rail strength, bumper clip strength, tire pressure, damper rate) and report the effects.

---

## 16. Debug and showcase visualizations (also great for the video)

- Beam **stress heat-map** (colour by force / deform threshold ratio: blue → yellow → red; broken beams black), togglable live while driving and in renders.
- **Deformation heat-map** on the visual mesh (colour by displacement from rest).
- Live HUD: speed, rpm, gear, throttle/brake/steering, G-force, energy bars, broken-beam count.
- Energy graphs (kinetic, elastic, plastic work, lost) and deceleration pulse plot per crash, exported as images.
- A "node-beam skeleton overlay" shot of the car for the video (wireframe of nodes/beams over the paint).

---

## 17. Project organisation (so everything is re-runnable)

```
W:\YouTube\3D Model Dodge Challenger\
  3DDodgeChallenger.blend            (original, never overwritten)
  3DDodgeChallenger_vNNN.blend       (working versions)
  reference\                         (photos supplied by the user)
  tools\                             (Blender export scripts, gate_*.py, run_all_tests.*)
  sim\vehicle\                       (geometry.json, params.yaml, dynamics.json, skinning bins)
  sim\cache\                         (scenario inputs and results, captures)
  Unity\HellcatSandbox\              (Unity project: Assets\Sim, Assets\Game, Assets\Scenes, Assets\Car)
  Builds\                            (standalone Windows build)
  docs\ docs\gates\ docs\video_assets\ renders\
```
- One entry point per task (`tools\export_all.py` in Blender, `Unity.exe -batchmode ... -executeMethod Tests.RunAll`, `Builds\HellcatSandbox.exe`).
- Pin package versions in `Packages\manifest.json`. Log solver version and parameter hash into every cache and capture header.
- Automated tests (Unity Test Framework) next to the validation tests of section 10.

---

## 18. Final cost report (required at the end of the project, and a short running log during it)

The user wants to know what this project cost. Keep a running log and produce a final report.

**Running log (every checkpoint):** append one row to `docs\cost_log.csv`: timestamp, phase, wall-clock time since the previous row, estimated active working time, input / output / cache-write / cache-read tokens used since the previous row (if you can obtain them), number of sub-agents or parallel sessions used, and a short note.

**Final report `docs\cost_report.md` (and a short summary to the user in Russian) must contain:**
1. **Time:** (a) wall-clock time from the first message to the final deliverable; (b) **active** agent working time (exclude idle gaps where the agent was waiting for the user, for example gaps longer than 10 minutes between messages; state the rule you used); (c) a breakdown by phase P0–P7; (d) time spent in long-running jobs (Unity builds, simulations, tests) if known.
2. **Tokens:** totals for input, output, cache-write and cache-read tokens, per model used (main agent and any sub-agents), plus a breakdown by phase. Obtain them in this order of preference: (i) any usage/cost facility exposed by the client or session tools; (ii) the session transcript files of Claude Code (JSON-lines files under the user's `.claude\projects\...` folder) which contain per-message usage fields; sum them for **all sessions of this project**; (iii) if neither is available, give a clearly labelled estimate and explain how you made it. Never invent exact numbers.
3. **Money, API-equivalent in US dollars:** convert the token totals to cost using the **current official Anthropic API price list** for every model that was used (input, output, cache write, cache read, any long-context surcharge or batch discount if applicable). Look the prices up at report time, quote the source URL and the date, show the formula and per-model subtotals. State that this is an **API-equivalent estimate**, not the user's actual subscription billing.
4. **Uncertainty:** list what is exact, what is estimated, and what is missing (for example sessions that were deleted, or tool-side costs outside the model such as third-party services).
5. **Context:** also report the numbers that make the cost meaningful: number of phases completed, lines of code written, files produced, number of Blender MCP calls and Unity builds/tests run, if you can count them.

Present the final table in Russian (numbers and units clear), place the raw data in `docs\cost_log.csv`, and keep the report out of the way of the main deliverables.

---

