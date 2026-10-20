# P0.5 report: vertical slice (box car through the whole pipeline)

Date: 2026-10-10. Gate: `docs/gates/gate_p05.md` — **PASS (12/12)**.

## What was built
- **Blender (via the add-on socket bridge):** `tools/blender/hcar/` package.
  - `sk.py`: skeleton container, checks and the `geometry.json` writer (Blender frame to Unity frame, outward triangle winding).
  - `debugviz.py`: `PH_*` debug collection, beams rendered as Geometry Nodes tubes, nodes as spheres.
  - `boxcar.py`: the slice car, saved to `3DDodgeChallenger_v002`/`v003`.
- **Box car:** 60 nodes, 250 beams, 4 wheels, 1334 kg.
  - Body: 12 nodes, with a crush bay in front and a rigid cabin behind.
  - Wheels: 2 axle nodes on the rotation axis plus 10 rim nodes each; the compliant spokes act as the tire.
  - Suspension: 3 links, a spring and a damper per axle node.
  - Steering: HYDRO tie rods on the `steering` input.
- **Unity solver:** `Assets/Sim/`, Burst, deterministic.
  - Beam kinds NORMAL, ANISOTROPIC, BOUNDED, SUPPORT and HYDRO.
  - Plasticity with linear hardening (D-005), breaking and break groups.
  - Static-world contact: penalty zone, friction anchor for stick/slip, Stribeck curve, load sensitivity, and a hard projection so nodes cannot tunnel.
  - Wheel couples, a simple powertrain, brakes with a holding spring, rolling resistance.
  - Load-time stability report (D-004).
  - Single-thread or parallel job pipeline; per node, forces are gathered in a fixed order.
- **Unity game layer:** `Assets/Game/`.
  - `SimRunner` runs a fixed 0.5 ms step with a per-frame cap and a slow-down flag.
  - Static colliders come from scene objects.
  - Controls: Input System keyboard and gamepad, arcade-style reverse.
  - Views: stress heat-map lines (`SkeletonDebugView`), box body and wheels.
  - Chase camera, HUD, offscreen frame capture, `WallCrashScenario`.
- **Build:** `Builds/P05_Slice/HellcatSlice.exe`, built by `BuildTasks.BuildSlice`.

## Numbers
| Run | Entry speed | Crush | Plastic work | Peak decel (frame avg) | Broken beams |
|---|---|---|---|---|---|
| target 50 km/h | 48.5 km/h | 0.270 m | 63.3 kJ | 31.9 g | 0 |
| target 80 km/h (run-up too short) | 67.6 km/h | 0.508 m | 130.3 kJ | 34.0 g | 0 |

- **Determinism:** the time series of a re-run is byte-identical, with or without frame capture.
- **Physics cost:** 7.5 µs per substep on a single thread, i.e. 15 ms of CPU per simulated second.
- **Windowed live mode:** 2000 Hz at ×1.00 real time, no exceptions.
- **Stability:** max S = 1.745 (hard limit 2), max ω·dt = 0.43, 0 errors.

## Evidence
`docs/video_assets/P05/`:
- skeleton in Blender;
- 50 and 80 km/h crashes, chase and side MP4 at 60 fps;
- side view in 0.25× slow motion;
- stills at impact and after.

Raw data is in `sim/cache/P05/*/`: result JSON, time series CSV and frames.

## Deviations and lessons
- **Wheel spin axis:** a positive couple turned left and right wheels in opposite directions. Spin axes are now all oriented to the car's right (`axisSign`).
- **Heavy face nodes:** heavy nodes on the front face are stopped inelastically by the hard wall projection, which gave little crush and a large spike. Crush-zone nodes must be light. This carries over to the Hellcat skeleton (P2).
- **No beam broke in the slice:** with hardening the crush beams reach their deform limit before their strength. Breaking is covered by validation test 4 and the Hellcat break groups.
- **Rolling losses:** the decagon wheels lose energy at every contact change, so the slice accelerates at about 2.5 m/s² instead of 3.4. The pressurized torus tire replaces them in P3b.
- **HUD in captures:** the IMGUI HUD is not drawn in offscreen captures. A HUD for video capture follows in P4b.
