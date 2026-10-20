"""One-off (P3 close-out): update docs/STATUS.md and docs/changelog.md."""
from pathlib import Path

p = Path("docs/STATUS.md")
s = p.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)


rep("Last update: 2026-10-11 ~12:30 UTC. Phase **P2 done (gate PASS)**, next **P3 (solver core on the Hellcat + validation tests 1-8)**.",
    "Last update: 2026-10-12 ~19:35 UTC. Phase **P3 done (gate G-Solver PASS)**, next **P3b (vehicle dynamics: tires, powertrain, brakes/ABS, aero, tests 9-14, 4.13 targets)**.")
rep("6. Never overwrite `3DDodgeChallenger.blend` (SHA-256 AA42CA0C...AE68). Latest working file: `3DDodgeChallenger_v008.blend`.",
    "6. Never overwrite `3DDodgeChallenger.blend` (SHA-256 AA42CA0C...AE68). Latest working file: `3DDodgeChallenger_v009.blend`.")
rep("   P2 end 2026-10-11T18:33:43Z.",
    "   P2 end 2026-10-11T18:33:43Z, P3 end 2026-10-12T19:32:01Z.")
rep('''  exact stability S = 2.355 < 2.5, gate G-Skeleton PASS 0 fail / 2 warn (`docs/P2_report.md`).''',
    '''  exact stability S = 2.355 < 2.5, gate G-Skeleton PASS 0 fail / 2 warn (`docs/P2_report.md`).
- P3: solver features (shell hinges, damp groups incl. relative damping, wind-up element and exact wheel couples,
  drive reaction on the differential, settled spawn, cord pre-tension, thin tire zone), skeleton fixes (mechanism-free,
  braces, pick-up mounts, 252 rigidifiers: torsion 6.4 kN m/deg, bending 1.75 kN/mm), damping retune; skeleton now
  2,107 nodes / 11,442 beams / 1,544 hinges / 23 damp groups, S = 2.362; validation tests T1-T8 + E1 + D1 all PASS
  (`docs/validation_report.md`), gate G-Solver PASS 0 fail / 0 warn (`docs/gates/gate_p3.md`); D-028 ... D-041.''')
rep('''## Next (plan)''', '''## P3 solver and validation: how to run
- Suite: `& tools\\unity\\run_unity_batch.ps1 -LogFile docs\\p3\\logs\\suite.log -ProjectPath Unity\\HellcatSandbox -UnityArgs
  @('-executeMethod','Hellcat.EditorTools.Validation.ValidationTasks.RunAll')` (optional `'-valTests','T6,T7'`,
  `'-valQuick','1'`; leave `-valOut` out: a relative path resolves inside the Unity project) -> `docs/p3/validation/`.
  Tests live in `Assets/Sim/Validation/` (StructuralTests T1-T5, VehicleTests T6-T8 / E1 / D1, ValidationSuite).
- Gate: `tools\\.venv\\Scripts\\python.exe tools\\gate_p3.py [--run]` (fails stale results); report
  `tools\\.venv\\Scripts\\python.exe -I tools\\p3\\make_validation_report.py`.
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

## Next (plan)''')
rep('''- **P3** (solver on the Hellcat, tests 1-8, `docs/validation_report.md`, gate G-Solver):
  - load `hellcat` in Unity (SimRunner), spawn 1 cm above the ground and settle (D-026);
  - `StabilityReport`: exact lambda_max by power iteration (D-024), Gershgorin / omega*dt as warnings;
  - torsion bars (dihedral spring about the bar axis on [tip_R, axis_R, axis_L, tip_L]);
  - pressure groups (ideal gas p = p0 V0 / V, signed tetra volume, leak on broken tire beams);
  - node-triangle collision for vehicle vs other bodies (self-collision off by default);
  - validation tests 1-8 per brief section 10, energy drift < 1 % / 10 s, deterministic re-run.
- **P3b** dynamics: tire tests (vertical rate -> rerun suspension_design with the measured rate), engine mode 8HP90,
  brakes/ABS, aero; tests 9-14; 4.13 targets table; `docs/dynamics_report.md`.''',
    '''- **P3b** dynamics: tire tests 9-14 (static load / deflection, pressure vs volume, free rolling incl. the rolling
  resistance of the tire damp groups, slip-angle and longitudinal-slip sweeps, puncture / leak), engine mode 8HP90
  (torque curve, converter, gears), brakes / ABS (100-0 km/h 33-38 m), aero (drag, top speed), 4.13 targets table,
  braking dive vs target (3.4 deg peak at 0.95 g now), the game spawner on `SoftBodyWorld.Settle`;
  `docs/dynamics_report.md`, gate.''')
rep("| P3 | next | - | |",
    "| P3 | done | PASS (0 fail, 0 warn) | docs/gates/gate_p3.md, docs/validation_report.md |\n| P3b | next | - | |")
p.write_text(s, encoding="utf-8")

c = Path("docs/changelog.md")
t = c.read_text(encoding="utf-8")
row = ("| P3 | 2026-10-12 | P3 | Solver core on the Hellcat and the validation suite (`Assets/Sim/Validation`): tests T1-T8 of "
       "brief 10 + E1 energy drift + D1 determinism, all PASS; gate G-Solver `tools/gate_p3.py` PASS (0 fail, 0 warn), "
       "`docs/validation_report.md`. Solver: shell bending hinges (D-032), deformation damp groups and relative damping "
       "of attached parts (D-033, D-038), wind-up element with exact pure wheel couples and the drive reaction on the "
       "differential (D-036), settled spawn (D-037), tire cord pre-tension and thin tire contact zone (D-028, D-029), "
       "vehicle couplings in the exact S, contact impulse telemetry. Skeleton: mechanism-free cage, 96 braces, pick-up "
       "mounts, closure lips/stops, 252 rigidifiers (torsion 1.1 -> 6.4 kN m/deg, bending 0.18 -> 1.75 kN/mm), mass "
       "balance (S = 2.362), dampers zeta 0.28 / 0.38, measured tire rate 292.9 kN/m, export rounded to 1 um / 1e-9 kg "
       "(byte-identical builds). Test references fixed (T7 applied impulse, T8 colliding nodes / interpolated face). "
       "Analysis tools in `tools/p3/`, design tools in `tools/skeleton/`; decisions D-028 ... D-041. Blender "
       "`3DDodgeChallenger_v009.blend`. |")
if not t.endswith("\n"):
    t += "\n"
t += row + "\n"
c.write_text(t, encoding="utf-8")
print("status and changelog updated")
