"""Writes docs/dynamics_report.md (P3b, gate G-Dynamics evidence) from docs/p3b/validation/dynamics_results.json and the
filled target table docs/p3b/targets_4_13.json, listing the plots of tools/p3b/plots.py.

Usage: tools/.venv/Scripts/python.exe tools/p3b/make_dynamics_report.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLOTS = [
    ("t9_lateral_force", "T9: tire rig, lateral force vs slip angle at 4.3 / 5.4 kN"),
    ("t9_longitudinal_slip", "T9: tire rig, longitudinal slip sweep (drive and brake)"),
    ("t10_bounce", "T10: bounce tests, body height at the front and rear axles after the release"),
    ("t10_roll_gradient", "T10: roll in steady cornering with and without the anti-roll bars against the design"),
    ("t10_curb_strike", "T10: 120 mm curb strike at 20 km/h on the right wheels (travel and tire load)"),
    ("t11_angle_vs_input", "T11: road-wheel angle vs steering input on the turntables"),
    ("t11_speed_reduction", "T11: speed-sensitive steering reduction (command and road-wheel angle)"),
    ("t12_launch", "T12: launch at full throttle with and without traction control"),
    ("t12_top_speed", "T12: top-speed run from 270 km/h"),
    ("t13_stop", "T13: 100-0 km/h stop with and without ABS"),
    ("t14_skidpad", "T14: skidpad R 45.7 m, lateral acceleration target rising 0.6 -> 1.15 g"),
    ("t14_slalom_50", "T14: 18 m / +-1 m slalom at 50 km/h"),
    ("t14_figure8_40", "T14: figure eight of 2 x 20 m circles at 40 km/h"),
    ("t14_ramp_jump", "T14: 0.45 m ramp jump at 60 km/h"),
]

NARRATIVE = """# Dynamics report (P3b, gate G-Dynamics)

Vehicle dynamics of the Hellcat on the production solver: validation tests 9-14 of brief section 10 (tires, suspension,
steering, powertrain, brakes, drive tests) and the driving acceptance targets of brief 4.13. Result of the run below:
**{passed}/{total} dynamics tests PASS** ({time}), target table filled, plots in `docs/p3b/plots/`.
Gate: `tools/gate_p3b.py` (`docs/gates/gate_p3b.md`), targets `docs/p3b/targets_4_13.json`.

## How the tests run

`Hellcat.EditorTools.Validation.ValidationTasks.RunDynamics` (Unity batch via `tools/unity/run_unity_batch.ps1`) builds
every scenario as a `SoftBodyWorld` with the production solver (Burst jobs, dt = 0.5 ms, symplectic Euler) and writes
`docs/p3b/validation/dynamics_results.json` plus one CSV time series per scenario. T9 uses the tire rig (one wheel on a
drum, `TireTests`); T10-T14 drive the whole car with a driver robot (`DynamicsCommon.DriverRobot`: pure pursuit with a
look-ahead, a cross-track integral, yaw-rate damping, speed control, traction control on) on flat asphalt with the
obstacles built per scenario. The linear suspension tools (`tools/skeleton/elastokinematics.py`,
`tools/p3b/arb_tune.py`, `tools/p3b/front_struct_study*.py`) predict the compliances the tests then measure; the
diagnostics X9-X20 are only run when listed.

| Test | Scenario | Pass criteria |
|---|---|---|
| T9 | tire rig: static load vs deflection, inflation volume, free rolling, slip-angle sweep, longitudinal slip sweep, puncture | rate and hysteresis vs the measurements; mu-slip curve rises and saturates; puncture deflates |
| T10 | static corner loads and ride height, bounce (heave / front / rear), 50 mm step, 120 mm curb at 20 km/h, roll gradient, anti-roll-bar effect | loads within 5 % of the centre-of-mass split, total = m g; ride frequencies within the brief's +-15 %, zeta 0.21-0.56; no damage on step and curb; roll gradient 3.0 +- 15 % deg/g (suspension + tires); bars at least x1.5 |
| T11 | angle vs input on turntables, ratio, speed-sensitive reduction, return to centre | inner lock 32.5 +- 15 %, Ackermann positive, symmetry; 2.6 turns lock to lock; on-centre ratio 15 +- 20 %; the steering command follows the reduction curve within 2 %; back to centre in 0.6 s |
| T12 | idle, rev limit, gear ratios, 0-100 km/h, top-speed run, coast-down, engine braking, wheelspin | brief 4.13 bands (+-15 %); straight-line stability at top speed; the car spins its tires with TC off |
| T13 | 100-0 km/h with and without ABS, steering while braking, handbrake, repeated stops | 33-38 m +- 15 %; ABS shortens the stop; no lock-ups with ABS; rear-only handbrake; stops within 3 % |
| T14 | slalom, skidpad, figure eight, speed bump and curb, ramp jump | weaves through every gate at 50 km/h without sliding, settles on the run-out; skidpad 0.85-1.0 g +- 15 %; figure eight within 1.5 m, no spin; no damage on bumps and curbs; the jump lands with the running gear intact and the tires pressurized |

## Driving targets (brief 4.13)

| Target | Brief | Measured | Verdict |
|---|---|---|---|
{targets}

## What the dynamics work changed

Decisions D-042 ... D-054 in `docs/decisions.md`; the P3b changes to the model and the tests:

- **Engine-mode driveline (D-042).** Torque-curve engine with inertia and engine braking, a torque converter with a
  lock-up clutch, the ZF 8HP90 ratios (S15) with a 2.62 final drive, an LSD and driveline compliance. 0-100 km/h
  3.92 s with the 1-ft rollout of the published figures.
- **Tire losses, hoop tension, inflation stiffness (D-043 ... D-045).** The carcass and rim damping is viscous with a
  velocity split; the belt ring carries a hoop tension proportional to omega^2; the carcass stiffness scales with the
  inflation. Fixed the wheel damp groups, which had swallowed the front knuckle's tie-rod end node and made the front
  wheels hop once per revolution at speed (D-046).
- **ABS and traction control (D-047)** as PI controllers on the slip speed with speed-scheduled targets.
- **Tire compound and contact friction (D-048).** A slow Stribeck decay (1.60 -> 0.75 over ~12 m/s), a friction
  ellipse with the lateral friction 0.88 of the longitudinal, and a stiffer tangential anchor; the tire's usable
  friction in the car then matches the rig.
- **Rear axle and alignment element (D-049).** Rear rail braces and a knuckle camber / toe spring-damper on the axle
  line (80 kN m/rad) that removed the compliance steer and camber that made the car weave at full throttle above
  200 km/h.
- **Front suspension package (D-051).** Tie-rod ends 40 mm outboard (Ackermann 52 % instead of -34 %), a K-member that
  ties the lower-arm pivots and the rack into one cradle, the front knuckle beams on their own stiffer material, the
  front anti-roll-bar links on the lower ball joints (the bar had worked at half its rate through the flat lower arm),
  torsion rates for the design bar contributions, and a front camber element measured against the steering axis.
  Front compliance steer 1.09 -> 0.38 deg/kN, lateral camber 0.92 -> 0.17 deg/kN.
- **Alignment reactions on the body frame (D-052).** The reaction of both elements goes to the four wind-up body sets
  that define the frame they are measured against, and the damping uses the frame's angular velocity, so the elements
  are conservative while the body deforms (E1 drift with damping off: 6 % -> 1e-5).
- **Steering damper and bar levers (D-054).** After the package the 0.2 m drop rang for 5.9 s: the front wheels yawed
  at 12 Hz on their stuck tire patches (the steering system against the tires' twist, with only the tie rods' 1.4 N m s/rad
  about the kingpin) and the bar's lever tips, moved outboard in D-051, swung fore-aft at 30 Hz. The front alignment
  element now also damps the steered knuckles' toe rate (20 N m s/rad, a power-steering gear's damping) and the tips are
  back at x 0.62: the drop settles in about 3.5 s again.
- **Test and robot procedures (D-050, D-053).** Gear-shift and lock-up logic in the stops and launches, the 1-ft
  rollout as the gate figure, the 95th percentile of the TC slip above 10 m/s; the curbs end outboard of the exhaust
  (they used to run under it), the roll gradient is compared with the design plus the tire compliance, the
  speed-sensitive reduction is measured on the command, the slalom is checked by whether the car reaches each gate,
  the ramp jump checks the running gear, and the robot's cross-track integral is an understeer correction that changes
  side with the turn.

## Findings and limitations

- **Long-run straight-line stability (found in P4, D-067; fixed in P4b, D-069).** The tests drive straight for 15-45 s.
  Diagnostic X24 (`-valTests X24`; `-valQuick 1` for the 120 s runs) showed a slow directional instability: with the
  steering held at zero the car turned about +4 deg in 60 s at a 150 km/h cruise and spun at about 90 s (with the P3b
  skeleton and parameters too). Cause: the wind-up angle (D-036) was integrated from the knuckle's and the body set's
  angular velocities and random-walked; its 200 kN m/rad torque turned the knuckles (toe). Anchored to the angle read
  from the pose (D-069) the car runs 120 s with the steering at zero within +-0.6 deg of heading (33 m off the line
  over 5 km) and T12's top-speed path offset fell from 0.505 to 0.21 m.
- **Top speed {vtop} km/h against the 314 km/h of the Widebody.** Under drive the node tire's losses reach about
  100 kW at 280 km/h (the tread nodes at 34 m/s carry a slip speed of 0.3-0.5 m/s against the Stribeck curve and the
  carcass hysteresis); the drag-limited asymptote of the acceleration-vs-speed fit is what T12 reports. A finer tire
  discretization or a loss compensation at the tread would close the gap (open question for the user).
- **Braking dive {dive} deg and launch squat {squat} deg** come from the springs alone (1.4 / 1.55 Hz, no anti-dive or
  anti-squat geometry); a real Hellcat has some (~30 %). The roll gradient is {roll} deg/g against 3.0 predicted
  (suspension 2.3 + tires 0.7).
- **Front tire cornering stiffness is at the low end of the literature** (0.25 /deg against 0.3-0.4 for a 305/35 at
  5.4 kN); the understeer gradient on the circle is {us} deg/g, at the top of the passenger-car range but plausible
  for a 2,040 kg front-heavy RWD car with a 74 % front roll-stiffness share; the skidpad limit is {skid} g (published
  Widebody tests 0.93-0.97 g).
- **Beam damping is viscous** while real bushings are hysteretic: local suspension modes in the 10-30 Hz range need
  explicit damping elements (the wind-up, alignment and steering dampers) rather than more beam damping, which the
  2 kHz stability limit caps (D-024).
- **The global body stiffness (7.2 kN m/deg torsion, 1.8 kN/mm bending) is below a real body's** - the 2 kHz stability
  limit at the modeled node masses (D-040). Under 1 g braking the front rails droop 6 mm relative to the cabin.

## Per-test results
"""


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, (int, float)):
        a = abs(v)
        if a != 0 and (a < 1e-3 or a >= 1e5):
            return f"{v:.3e}"
        return f"{v:.4g}"
    return str(v)


def main():
    vr = json.loads((ROOT / "docs/p3b/validation/dynamics_results.json").read_text(encoding="utf-8"))
    targets = json.loads((ROOT / "docs/p3b/targets_4_13.json").read_text(encoding="utf-8"))
    tests = vr["tests"]
    by_id = {t["id"]: t for t in tests}

    def val(tid, frag):
        for c in by_id.get(tid, {}).get("checks", []):
            if frag in c["name"]:
                return c["value"]
        return None

    rows = []
    for r in targets:
        m = f"{r['measured']:.4g} {r['unit']}" if r["measured"] is not None else "-"
        band = f"{r['band'][0]:.4g}-{r['band'][1]:.4g} {r['unit']}" if r["band"] else "-"
        rows.append(f"| {r['target']} | {r['brief']} (band {band}) | {m} | {'PASS' if r['pass'] else 'FAIL'} - {r['note']} |")
    passed = sum(t["pass"] for t in tests)
    out = [NARRATIVE.format(passed=passed, total=len(tests), time=vr["time_utc"], targets="\n".join(rows),
                            vtop=f"{val('T12', 'top speed (drag and gearing limited') or 0:.0f}",
                            dive=f"{val('T13', 'braking dive at 100-0') or 0:.1f}",
                            squat=f"{val('T12', 'launch, traction control on: peak squat') or 0:.1f}",
                            roll=f"{val('T10', 'roll gradient in steady cornering') or 0:.2f}",
                            us=f"{val('T10', 'understeer gradient on the circle') or 0:.1f}",
                            skid=f"{val('T14', 'skidpad: brief 0.85-1.0 g, -15') or 0:.2f}")]
    for t in tests:
        out.append(f"### {t['id']}: {t['title']} - {'PASS' if t['pass'] else 'FAIL'} ({t['seconds']:.1f} s)\n")
        out.append("| Check | Value | Unit | Limit | Result |")
        out.append("|---|---|---|---|---|")
        for c in t["checks"]:
            res = "info" if c["info"] else ("PASS" if c["pass"] else "FAIL")
            out.append(f"| {c['name'].replace('|', '/')} | {fmt(c['value'])} | {c['unit']} | {str(c['limit']).replace('|', '/')} | {res} |")
        files = t.get("files") or []
        if files:
            out.append("")
            out.append("Time series: " + ", ".join(f"`docs/p3b/validation/{f}`" for f in files))
        if t.get("notes"):
            out.append("")
            out.append("<details><summary>notes</summary>\n")
            out += [f"- {n}" for n in t["notes"]]
            out.append("\n</details>")
        out.append("")
    out.append("## Plots\n")
    for name, cap in PLOTS:
        p = ROOT / "docs/p3b/plots" / f"{name}.png"
        if p.exists():
            out.append(f"![{cap}](p3b/plots/{name}.png)\n")
    (ROOT / "docs/dynamics_report.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote docs/dynamics_report.md ({passed}/{len(tests)} PASS, {len(targets)} targets)")


if __name__ == "__main__":
    main()
