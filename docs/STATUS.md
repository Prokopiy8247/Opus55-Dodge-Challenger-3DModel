# STATUS (resume here after a context compaction or restart)

Last update: 2026-10-15. **All phases done (P0-P7)**; gate G-Build P7 PASS 0 fail / 0 warn, every earlier gate re-run on the final code (`docs/P7_report.md`). The game: `Builds/HellcatSandbox/HellcatSandbox.exe`; how to run, controls, tuning: `docs/README.md`; cost: `docs/cost_report.md`. `dev` merged into `main`.
AUTONOMY MODE: work continuously P3 -> P7, no stops, no questions (brief top block).

## How to resume
1. Read `GAME_AGENT_PROMPT.md` (AUTONOMY MODE block first), this file, `docs/decisions.md`, `docs/changelog.md`.
2. `git -C "W:\YouTube\3D Model Dodge Challenger" log --oneline -20` (branch `dev`; `main` is created at the very end).
3. Blender: project Blender = 127.0.0.1:9876 (title `3DDodgeChallenger_vNNN.blend`).
   **Never use the session's `mcp__*blender*` tools: they drive other projects (ports 9883-9888).**
   Bridge: `tools\.venv\Scripts\python.exe -I tools\blender\blender_bridge.py ping|exec <file.py>|call hcar.mod:fn`;
   from PowerShell prefer `& tools\blender\bcall.ps1 hcar.<module>:<function> @{ key = value } -Timeout 300`.
   Package `tools/blender/hcar/` is re-imported on every call. Save versions with `hcar.blend_util:save_version`
   (in-place: `save_current`). One-off probes live in `tools/blender/scratch/` (run with `exec`).
   If Blender crashed: start `W:\Blender\blender.exe "<latest vNNN.blend>"`; the add-on server starts itself.
4. Unity batch: `& tools\unity\run_unity_batch.ps1 -LogFile <log> -ProjectPath Unity\HellcatSandbox -UnityArgs @('-executeMethod','Hellcat.EditorTools.Build.BuildTasks.BuildSlice')`.
   Player runs: `& tools\run_player.ps1 -Exe <exe> -LogFile <log> -PlayerArgs @(...)` (`-Windowed` for a window).
5. Python tools: `tools\.venv\Scripts\python.exe` (numpy, scipy, cv2, PIL, matplotlib, yaml). ffmpeg on PATH.
6. Never overwrite `3DDodgeChallenger.blend` (SHA-256 AA42CA0C...AE68). Latest working file: `3DDodgeChallenger_v011.blend` (P4: glass shards in Car_Visual/Glass_Shards).
   The project Blender bridge (9876) may be down: `tools\blender_bg.py <module:function> [--save note]` runs hcar
   functions in a background Blender on the latest vNNN file (`tools\export_all.py` the same for the FBX export).
7. Cost: `tools\.venv\Scripts\python.exe tools\cost\collect_usage.py --since <ISO> --until <ISO> --json docs\cost\usage_<P>.json`
   then `tools\cost\append_row.py docs\cost\usage_<P>.json <P> <ISO> <subagents> "<note>"` (one row per phase).
   Phase boundaries so far: P0 end 2026-10-10T17:41:52Z, P0.5 end 21:01:33Z, P1 end 2026-10-11T07:53:24Z, P1b end 09:55:49Z,
   P2 end 2026-10-11T18:33:43Z, P3 end 2026-10-12T19:32:01Z, P3b end 2026-10-13T04:16:54Z,
   P4 end 2026-10-14T18:58:24Z, P4b end 2026-10-14T21:27:23Z, P5 end 2026-10-14T22:10:20Z, P6 end see cost_log.csv.

## Done
- P0: audit, Unity project, packages, physics notes, Burst benchmark, gate PASS (`docs/P0_report.md`).
- P0.5: vertical slice (box car), solver core + game layer + build, gate PASS 12/12 (`docs/P05_report.md`).
- P1: exterior (128 CH_* parts, 619k tris), gate G-Model PASS 0 fail / 1 warn (`docs/P1_report.md`, `docs/model_notes.md`).
- P1b: interior (35 CH_Int_* parts, 163k tris), cockpit.json, photo layout fit, gate G-Interior PASS 0 fail / 1 warn (mirrors -> P4b) (`docs/P1b_report.md`).
- P2: physics skeleton (2,023 nodes, 9,500 beams, 2,308 triangles, 2,040 kg, 57/43), suspension designed from targets,
  exact stability S = 2.355 < 2.5, gate G-Skeleton PASS 0 fail / 2 warn (`docs/P2_report.md`).
- P3: solver features (shell hinges, damp groups incl. relative damping, wind-up element and exact wheel couples,
  drive reaction on the differential, settled spawn, cord pre-tension, thin tire zone), skeleton fixes (mechanism-free,
  braces, pick-up mounts, 252 rigidifiers: torsion 6.4 kN m/deg, bending 1.75 kN/mm), damping retune; skeleton now
  2,107 nodes / 11,442 beams / 1,544 hinges / 23 damp groups, S = 2.362; validation tests T1-T8 + E1 + D1 all PASS
  (`docs/validation_report.md`), gate G-Solver PASS 0 fail / 0 warn (`docs/gates/gate_p3.md`); D-028 ... D-041.

## P3b vehicle dynamics (decisions D-042 ... D-054)
- Engine-mode driveline (D-042), tire losses / ring tension / inflation stiffness (D-043 ... D-045), wheel damp-group
  prefix bug fixed (D-046: once-per-revolution hop), ABS / TC as PI slip controllers (D-047), tire compound with a slow
  Stribeck decay + friction ellipse + stiffer anchor (D-048), rear rail braces x2 + knuckle alignment element
  (camber / toe spring-dampers on the axle line, D-049), driver robot and T12 / T13 procedures (D-050).
- Measured: 0-100 km/h 3.92 s (1-ft rollout; 4.28 s from the throttle), 0-60 mph 3.74 s, top speed 282 km/h (314 real:
  node-tire losses under drive, open question), 100-0 km/h 33.5 m (no ABS 39 m), stable at full throttle from 270 km/h.
- Front suspension package (D-051): tie-rod ends 40 mm outboard (Ackermann +52 %), K-member (`kmember`), front
  knuckle `knuckle_f` 6 MN/m, anti-roll-bar links on the lower ball joints (tips at x 0.62, D-054), bars 2950 / 825
  N m/rad (74 % front roll share), front camber element about the kingpin + steering damper 20 N m s/rad (D-054);
  alignment reactions on the body frame centroids (D-052: E1 drift 4e-6). Measured: skidpad 0.96 g, roll 2.97 deg/g,
  understeer 3.9 deg/g, inner lock 32.9 deg / outer 30.0, on-centre 14.5:1, drop settles in 3.45 s.
- Tests: `-executeMethod Hellcat.EditorTools.Validation.ValidationTasks.RunDynamics -valTests T9,T10,T11,T12,T13,T14`
  (results `docs/p3b/validation/dynamics_results.json`); diagnostics X9 ... X20 (run only when listed): X12 straight
  line at speed, X13 assist gains, X14 / X15 tire friction on the rig, X16 robot at speed, X17 elastokinematics, X18
  skidpad balance variants, X19 robot variants on the slalom, X20 drop variants (`DropDiagnostics.cs`).
  `tools/p3b/show_results.py <json> [ids]` prints a results file. Gate `tools/gate_p3b.py [--run]`; report
  `tools/p3b/plots.py` then `tools/p3b/make_dynamics_report.py`.
- Linear tools: `tools/skeleton/elastokinematics.py` (compliance per kN), `tools/p3b/arb_tune.py` / `arb_tune2.py`
  (bar rates through the link chain), `tools/p3b/steer_kinematics.py` (Ackermann, ratio), `front_struct_study*.py`.
  **Do not run `suspension_design.py --apply` blindly**: it writes the rigid-chain bar rates (half the effect, D-051).

## P4 skinning and crash S1 (decisions D-055 ... D-068)
- Export: `tools\.venv\Scripts\python.exe tools\export_all.py` (background Blender, latest vNNN) -> 32 FBX + parts.json +
  materials.json + textures in `Assets/Game/Vehicles/Hellcat/Export`; bind: `Tools/Hellcat/Import Car` or batch
  `-executeMethod Hellcat.EditorTools.Car.CarImporter.ImportBatch` (-> `*.skin.bytes`, `Hellcat.prefab`,
  `docs/p4/import_report.json`). Re-import after every skeleton change (the prefab carries the geometry hash).
- Runtime: `SoftBodyCarView` (node bones, best-fit frames D-062, glass swap D-064), `SkinningProbe` (CPU re-skinning for
  the metrics), `CarCrashScenario` + `CrashMetrics` (scene `P4_Crash`, player `Builds/P4_Crash/HellcatCrash.exe`,
  args `-scenario S1|S8 -targetKmh -out -capture 1 [-launch 1] [-breakGlass s] [-fps] [-lead] [-postImpact]`).
- Runs: `& tools\p4\crash_series.ps1 [-Import] [-Build] [-Runs 'S1:50:kmh50',...]` (results `sim/cache/<S>/<run>/`,
  frames ignored by git); after a skeleton / solver change `& tools\p4\pipeline.ps1 -Tag <t>` (import, build, series,
  X21, P3 and P3b suites). Diagnostics X21 (crash variants), X22 / X23 (per-step energy decomposition).
- Evidence: `tools\.venv\Scripts\python.exe tools\p4\make_videos.py` (grid videos, stills, speed series sheet ->
  `docs/video_assets/P4/`); gate `tools\gate_p4.py` (CFC 60 pulse, metrics table `docs/p4/crash_metrics.csv`, plots);
  report `tools\p4\make_p4_report.py` (then the gate again).
- Skeleton: closure joints in 3D (D-063, `tools/skeleton/closure_joints.py`, in gate P2), crush zones without
  rigidifiers (D-057), detachables (D-058); solver: hard contact (D-055), spring-back suppression (D-056), torsion-bar
  failure (D-060), pair impulse (D-061).
- **Fixed in P4b (D-067 -> D-069):** long-run straight-line stability. The wind-up angle (D-036) was integrated from
  the knuckle's and the body set's least-squares angular velocities and random-walked into a spurious wind-up torque
  that turned the knuckles (toe); it is now pulled with a 1 s time constant towards the angle read from the pose
  (`WheelStatic.windupRef / windupPhi0`). X24 (`-valTests X24`, `-valQuick 1` = 120 s runs) is the check.
- Open for P6: hood folds as one 0.4-0.6 m tent; body flex moves the closures a few cm in the pulse; S8 glass does not
  break by itself; physics 240-265 us per substep with the detachables' self-collision.

## P4b game layer (decisions D-069 ... D-080)
- Scene `Assets/Scenes/P4b_Drive.unity` (`Tools/Hellcat/Build P4b Drive Scene`, `DriveSceneBuilder`); player
  `-executeMethod Hellcat.EditorTools.Build.BuildTasks.BuildDrive` -> `Builds/P4b_Drive/HellcatDrive.exe`. Keys and
  menus: `docs/controls.md`. Settings `settings.json` and `recordings/` next to the exe.
- Components (`Assets/Game`): `GameControls` (keys, safe pose, reset / repair / teleport with the speed hold
  `ApproachHoldSource` D-080, F9), `CameraRig` (chase,
  bumper, cockpit, free), `CockpitInstruments` (needles, wheel, pedals, mirrors), `Hud`, `PauseMenu`, `GameSettings`,
  `DebugViews` + `SkeletonDebugView` (N, Shift+N, H, Shift+H; deformation shader `Hellcat/DeformationHeatmap` reads UV3
  written by `CarSkinPostprocessor` v2), `ReplayController` (F5 / F6), `RobotDriverSource`, `SpawnPoint`.
- Sim: `WorldState` (snapshot of every native array, `Hash`), `InputRecording` (`.hrec`), `SimRunner.RespawnSettled /
  RestoreState / ReloadVehicleData / SubstepOverride / PendingSteps`, `Respawn` restarts the grid schedule (`clock[1]`).
- Tests: test 15 `-executeMethod Hellcat.EditorTools.Validation.ValidationTasks.RunGame` -> `docs/p4b/validation/`;
  G-Drive `HellcatDrive.exe -scenario drive [-driveSeconds 300 -driveRecord 60 -driveOut dir]` (windowed, ~7 min) ->
  `docs/p4b/drive/`; short capture `-scenario showcase [-captureOut dir]` (1920x1080 frames, then
  `tools\p4b\encode_capture.ps1`). Gate `tools\gate_p4b.py`; report `tools\p4b\make_p4b_report.py`.
- Open: interior LOD while driving outside (brief 4.12 rendering; fps is 104+ without it, P5 / P7); the glass reads
  almost clear in renders (P7 look); the P4 crash series predates D-069 (re-run in P6); the drive
  scene's four obstacles are stand-ins for P5's test map.

## P5 test map (decisions D-081 ... D-083)
- Scene `Assets/Scenes/TestMap.unity` (`Tools/Hellcat/Build Test Map`, `TestMapBuilder`, which also writes
  `docs/p5/map_layout.json`); player `-executeMethod Hellcat.EditorTools.Build.BuildTasks.BuildTestMap` ->
  `Builds/TestMap/HellcatTestMap.exe`. Shared rig of every game scene: `Editor/Build/GameRigBuilder.cs`.
- Debris: `Sim/Props/PropFactory.cs` (barrel, box, cone, fence panel), `Game/World/PropField.cs` (`IDynamicBodySource`,
  rigid views, Ctrl+R reset); obstacles: `StaticBoxSource`, `StaticCylinderSource`, `StaticPrismSource` (convex prisms);
  spawns: `SpawnPoint` (`holdThrough` for drivable lanes).
- Check: `HellcatTestMap.exe -scenario mapcheck [-mapOut dir] [-mapSettleOnly 1]` -> `docs/p5/mapcheck/`; then
  `tools\p5\annotate_map.py` and `tools\gate_p5.py`.
- Open for P6: closure rubber stops release on hard landings (D-034), headlamps detach at 30 km/h frontal; debris drawn rigid.

## P6 scenarios S1-S8 and tuning (decisions D-084 ... D-097)
- Scenarios in the test-map player: `Builds/TestMap/HellcatTestMap.exe -scenario S1..S8 [-targetKmh v] -out <dir>
  [-capture 1] [-lateral m] [-breakGlass s] [-vehicleParams file]`; driven variant `-driven 1`; play a recording
  `-replay <file.hrec>`. Spec table `CarCrashScenario.Specs` (lane, obstacle, kind, capture window, cameras); metrics
  `CrashMetrics` (SDF contact, tunnelling by plate crossing D-093, IIHS-like intrusion D-089, deformation).
- Series: `& tools\p6\run_all_p6.ps1 [-NoBuild] [-Only captured,series,glass,driven]` (build, 8 captured runs, 16 series
  runs, glass test, 8 driven variants, gate); single runs `& tools\p6\run_scenarios.ps1 -Runs 'S1:50:kmh50' [-Capture]
  [-Build]`. Results `sim/cache/<S>/kmh<v>/` (result JSON, pulse, timeseries, .hrec; frames ignored by git), driven
  `sim/cache/<S>/driven/`.
- Evidence: `tools\p6\make_videos.py [--sheet-only]` -> `docs/video_assets/P6/`; gate `tools\gate_p6.py` (summary
  `docs/p6/scenario_summary.md`, plots `docs/p6/plots/`); report `tools\p6\make_p6_report.py` (narrative
  `docs/p6/report_notes.md`); close `tools\p6\close_p6.py`.
- Tuning: `tools\p6\tune.py` (candidate sets -> `sim/cache/tune/<name>/`), `apply_tuning.py --crease 0.1 --front 0.7`
  (adopted), `sweep.py` (sensitivity -> `docs/p6/sensitivity.*`), `tuning_log.py` (rows P6-001 ... P6-006 of
  `docs/tuning_log.csv`). Params added: `pressure.gaugeScale`, `materialZones`, `-vehicleParams` (D-090).
- Calibration (D-091, D-096): NHTSA NCAP 2013 Challenger (`docs/p6/refs`): static crush 615 vs 608 mm; rebound (4.0 vs
  2.7 m/s) and wheelbase shortening (none vs 150 mm) not matched (the wheel path holds the front wheels).
- Open: S8 cell intrusion small (tyres do not collide with their own body, D-058); hood mesh coarse; stretched skins at
  120 km/h; inner suspension nodes do not collide with the ground (the lower-arm pivot dips 2-5 cm in S4 50 / S5 60);
  S7 damage not monotonic (fence panels); glass look (P7).

## P7 polish, standalone build, final gates (decisions D-098 ... D-104)
- The game: `Builds/HellcatSandbox/HellcatSandbox.exe` (`BuildTasks.BuildSandbox`; the test map scene with the game rig, the
  start screen `StartScreen`, the interior LOD `InteriorLod`, the drive test and showcase on the east loop, the controls check
  `ControlsCheck`). `Builds/TestMap/HellcatTestMap.exe` is the same scene for the P5 / P6 tools.
- Checks: `& tools\p7\run_p7.ps1 [-Build] [-Only controls,drive,drive1440,determinism,mapcheck,capture]` -> `docs/p7/`, the
  capture encoded by `tools\p7\encode_p7.py` -> `docs/video_assets/P7/`; gate `tools\gate_p7.py` (G-Build); report
  `tools\p7\make_p7_report.py` (narrative `docs/p7/report_notes.md`).
- Every earlier gate on the final code: `& tools\p7\run_suites.ps1` (P3 / P3b suites, test 15, the P4b drive player and its drive
  test, then gates P2, P3, P3b, P4b, P5, P6).
- Solver: sleeping debris (D-098, `TailSleepPhase`, `SoftBodyWorld.MarkSleepable / WakeTail`); look: glass (D-099, importer),
  sky (D-100, `CameraSky`), interior LOD (D-101).
- Docs: `docs/README.md` (run, controls, tuning, rebuilding), root `README.md`, `docs/metrics.csv` (`tools\p7\write_metrics.py`),
  `docs/cost_report.md` (`tools\cost\make_cost_report.py`).

## Architecture (short)
- Solver `Assets/Sim`: `SoftBodyWorld` (all bodies in one set of NativeArrays), `Kernels.cs` (beam law, SDF, contact),
  `SimJobs.cs` (BeamForceJob, NodeIntegrateJob), `SerialPhaseJob.cs` (break groups, clock, vehicle control, ST job),
  `Vehicle/VehicleControlJob.cs` (steering hydro, wheel kinematics, simple powertrain, brakes), `StabilityReport.cs`.
- Data: `sim/vehicle/<name>/geometry.json` (Blender export) + `params.json` (tuning, // comments allowed),
  synced to `Assets/StreamingAssets/Vehicles/<name>/` by `tools/sync_vehicle.py` (or the editor menu `VehicleAssetSync`).
  Beam materials have `preload` (N): rest = spawn * pre + preload / spring (D-026).
- Game `Assets/Game`: SimRunner, LiveDriverInput / RobotDriverSource, GameControls, CameraRig, CockpitInstruments, Hud,
  PauseMenu, DebugViews / SkeletonDebugView, ReplayController, SoftBodyCarView, scenarios (CarCrashScenario, DriveTest,
  ShowcaseCapture), FrameCapture; legacy slice pieces BoxCarView, ChaseCamera, WallCrashScenario.

## P1 exterior: how the car is built (D-016, docs/model_notes.md)
- `hcar.assemble:build_car` (~65 s) = body.preview_all + preview_flares_wheels + preview_panels + details.build_all +
  mechanics.build_all + finalize (names CH_*, L/R split, origins, UVs, Solidify thickness, orientation fix).
- Shape data: `hcar/body_tables.py`; surfaces `shape.py`, `caps.py`; panels `panels.py` (Coons patch, inset, flange,
  openings with tunnels + plugs), `body_panels.py`, `gh_panels.py`, `flares.py`; `wheels.py`; `details.py`; `mechanics.py`.
- Gate: `hcar.gate_model:audit` + `:measure` -> `tools/ref/gate_overlay.py` -> `hcar.render:ortho_views` +
  `tools/ref/ortho_overlay.py` -> `tools/gate_p1.py` (docs/gates/gate_p1.md).
- Renders: `hcar.render:setup`, `:beauty`, `:turntable` (batches), ffmpeg.
- Car frame: Z up, +Y forward, +X right, y=0 mid-wheelbase, wheel centres y=+-1.4755, x=+-0.8335/0.8345, z=0.352.
- Interior: `hcar.interior:build_interior` (~8 s, needs Car_Visual) -> Car_Interior; tables `interior_tables.py`;
  audit `hcar.gate_interior:audit`; photo fit `tools/ref/interior_pnp.py cabin2`; gate `tools/gate_p1b.py`;
  `hcar.interior:export_cockpit` -> sim/vehicle/hellcat/cockpit.json; shots `hcar.ishots`.

## P2 skeleton: how it is built
- `& tools\blender\bcall.ps1 hcar.hskel:main @{ viz = $true; save = $false } -Timeout 600` (~25 s): writes
  sim/vehicle/hellcat/geometry.json (+ StreamingAssets copy) and skeleton_stats.json, debug collection Car_Physics/PH_Hellcat.
  Tables `hcar/hskel_tables.py` (group masses, stations, panel resolutions), container/writer `hcar/sk.py`
  (Blender frame -> Unity frame u = (x, z, y), triangle b/c swapped on export), debug view `hcar/debugviz.py`.
- Tools (venv): `tools/skeleton/stability.py` (exact S, D-024), `suspension_design.py [--apply]` (D-025; writes
  spring/damper/arb/preload into params.json), `diag_skeleton.py`, `diag_winding.py`, `composite.py`;
  `tools/sync_vehicle.py`; gate `tools/gate_p2.py` (docs/gates/gate_p2.md, p2_winding.json, docs/p2_stability.json).
- Shots: `hcar.pshots:shots_blender` (beauty + skeleton passes; `hide_cats` for structure-only) + `tools/skeleton/composite.py`.
- After changing params.json: run `tools\sync_vehicle.py hellcat`; after changing hardpoints or masses: rerun
  `suspension_design.py --apply`, `stability.py`, the gate.

## P3 solver and validation: how to run
- Suite: `& tools\unity\run_unity_batch.ps1 -LogFile docs\p3\logs\suite.log -ProjectPath Unity\HellcatSandbox -UnityArgs
  @('-executeMethod','Hellcat.EditorTools.Validation.ValidationTasks.RunAll')` (optional `'-valTests','T6,T7'`,
  `'-valQuick','1'`; leave `-valOut` out: a relative path resolves inside the Unity project) -> `docs/p3/validation/`.
  Tests live in `Assets/Sim/Validation/` (StructuralTests T1-T5, VehicleTests T6-T8 / E1 / D1, ValidationSuite).
- Gate: `tools\.venv\Scripts\python.exe tools\gate_p3.py [--run]` (fails stale results); report
  `tools\.venv\Scripts\python.exe -I tools\p3\make_validation_report.py`.
- After any skeleton change: build (`tools/skeleton/build_skeleton.py` or `hcar.hskel:main` in Blender; byte-identical),
  `suspension_design.py --apply`, `stability.py --json docs/p2_stability.json` (the C# / Python S reference of T6),
  `tools/p3/body_stiffness.py --json docs/p3/body_stiffness.json`, copy params.json to StreamingAssets, gates P2 and P3.
- Design tools: `tools/skeleton/rigidifier_design.py` (D-040), `mass_balance.py` (D-031), `brace_design.py` (D-030),
  `hinges.py` (D-032), `modal_damping.py`, `modal_ground.py` (modes on the ground with torsion bars, `--push`),
  `tire_rate.py`; analysis `tools/p3/`: `body_stiffness.py`, `end_stiffness.py`, `tire_tangent.py`, `windup_bar.py`,
  `point_stiffness.py`, `windup.py`, snapshot analysis `snap_*.py`.
- Solver pieces added in P3: `Core/HingeJob.cs` (D-032), `Core/GroupDampJob.cs` (D-033 own + D-038 relative pass),
  wind-up / brake / drive couples in `Vehicle/VehicleControlJob.cs` (D-036), `SoftBodyWorld.Settle` (D-037),
  `SoftBodyWorld.VehicleCouplings` (exact S), `ClearContactImp` / `contactImp` (T7 impulse reference).

## Next (plan)
- Nothing scheduled: the brief's deliverables are complete. Open questions for the user are at the end of `docs/P7_report.md`.
## Phase log
| Phase | Status | Gate | Notes |
|---|---|---|---|
| P0 | done | PASS (0 fail, 3 warn) | docs/gates/gate_p0.md |
| P0.5 | done | PASS (12/12) | docs/gates/gate_p05.md |
| P1 | done | PASS (0 fail, 1 warn) | docs/gates/gate_p1.md |
| P1b | done | PASS (0 fail, 1 warn) | docs/gates/gate_p1b.md |
| P2 | done | PASS (0 fail, 2 warn) | docs/gates/gate_p2.md |
| P3 | done | PASS (0 fail, 0 warn) | docs/gates/gate_p3.md, docs/validation_report.md |
| P3b | done | PASS (0 fail, 0 warn) | docs/gates/gate_p3b.md, docs/dynamics_report.md |
| P4 | done | PASS (0 fail, 0 warn) | docs/gates/gate_p4.md, docs/P4_report.md |
| P4b | done | PASS (0 fail, 0 warn) | docs/gates/gate_p4b.md, docs/P4b_report.md, docs/controls.md |
| P5 | done | PASS (0 fail, 0 warn) | docs/gates/gate_p5.md, docs/P5_report.md |
| P6 | done | PASS (0 fail, 1 warn) | docs/gates/gate_p6.md, docs/P6_report.md |
| P7 | done | PASS (0 fail, 0 warn) | docs/gates/gate_p7.md, docs/P7_report.md, docs/cost_report.md |
