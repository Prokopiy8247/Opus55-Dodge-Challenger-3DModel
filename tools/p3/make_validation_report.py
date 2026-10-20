"""Writes docs/validation_report.md from docs/p3/validation/validation_results.json (P3, G-Solver evidence).

The narrative (method, what the tests found and what was changed, limitations) is part of this script so the report
can be regenerated after every suite run; the per-test tables come from the results file.

Usage: tools/.venv/Scripts/python.exe tools/p3/make_validation_report.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, (int, float)):
        a = abs(v)
        if a != 0 and (a < 1e-3 or a >= 1e5):
            return f"{v:.3e}"
        return f"{v:.4g}"
    return str(v)


NARRATIVE = """# Validation report (P3, gate G-Solver)

Solver core on the Hellcat skeleton: validation tests 1-8 of brief section 10 plus the energy-drift and determinism
checks of gate G-Solver (brief 14). Result of the run below: **{passed}/{total} tests PASS** ({time}, full run).
Gate: `tools/gate_p3.py` (`docs/gates/gate_p3.md`).

## How the tests run

`Hellcat.EditorTools.Validation.ValidationTasks.RunAll` (Unity batch, `tools/unity/run_unity_batch.ps1`) builds every
scenario as a `SoftBodyWorld` with the production solver (Burst jobs, 2 kHz, symplectic Euler) and writes
`docs/p3/validation/validation_results.json` plus one CSV time series per scenario next to it. T1-T5 use small
hand-built bodies with analytic answers; T6-T8, E1 and D1 load the Hellcat from `sim/vehicle/hellcat/` (the
StreamingAssets copy). `tools/gate_p3.py --run` runs the suite and evaluates it; it fails results that are older than
the vehicle data or any solver source. This report is written by `tools/p3/make_validation_report.py`.

| Test | Scenario | Pass criteria |
|---|---|---|
| T1 | single beam: fixed-free / free-free oscillation, damped oscillation, static stretch and compression | omega, zeta, omega_d within 0.5-3 % of the analytic values; static deflection within 0.2 % |
| T2 | pendulum (60 deg, exact elliptic period) and a hanging chain released from horizontal | period within 0.5 %; energy error < 1 % (pendulum) / 3 % (chain, 5 s) |
| T3 | cube with and without face / body diagonals under gravity on the ground | unbraced collapses (< 30 % height), braced holds (> 99 %) |
| T4 | tensile cycle with linear hardening and failure; falling mass on a crush tube at 5 / 15 m/s | hardening slope, permanent set, failure force / displacement within 1 %; energy ledger error < 2-3 % |
| T5 | rigid box: drop on the ground, rest, slopes of 20 and 40 deg | no penetration; rest in the contact zone; static friction holds at 20 deg; sliding acceleration g (sin - mu cos) within 3 % at 40 deg |
| T6 | Hellcat at rest on the ground (settled spawn, D-037) and dropped from 0.2 m, parked (brakes, handbrake) | exact S < 2.5 and C# = Python; at rest: settled within 1 s, max node speed < 1 cm/s, ride-height drift < 2 cm, no energy gain, loads match m g / 57-43 / left-right; drop: settled within 4 s (D-039), then the same rest checks |
| T7 | locked-wheel stop from 50 km/h; sideways slide from 10 m/s | the body's deceleration equals the contact impulse the solver applied (3 %) |
| T8 | Hellcat at 120 km/h into a 20 cm static wall; 35 loose nodes and a 10 kg box at 120 km/h into a node-beam slab (fixed and free, 252 kg) | no colliding node behind or inside the wall (1 mm); no projectile node past the slab's front face (1 mm); momentum error < 0.5 % |
| E1 | Hellcat floating free 10 s (no gravity, spin + random velocity field), damping on and off | drift of mechanical + dissipated energy < 1 % (1 s windows); angular momentum error < 0.1 % |
| D1 | the same input twice, and single-thread vs parallel | bit-identical node states (hash) |

## What the tests found, and what changed

The suite was brought up against the P2 skeleton; most failures came from the model, two from the tests themselves.

**Test measurements corrected (no solver change).**
- *T8 wall*: the check counted every node, but 317 of the Hellcat's nodes are deliberately non-colliding (panel inner
  grids, dash ribs, wheel and rack internals, `flags = 0`). Counted over the colliding nodes the deepest point is
  -1e-7 m (the projection epsilon): nothing tunnels. *T8 slab*: the front face was taken at the nearest front node of
  a 0.25 m grid while the measured band was 1 m wide, an error of up to 7.5 mm against a 1 mm limit; the face is now
  interpolated bilinearly over the grid (projectiles stop 1.1 mm in front of it).
- *T7*: the reference was Coulomb friction mu(slip) lf(load) N alone, which leaves out the sticking-anchor force of the
  contact law and reported a 12 % "error". The reference is now the contact impulse the solver actually applied over
  each sample (accumulated per node, including the anti-tunnelling projection): measured and applied deceleration agree
  to 0.2 %. The Coulomb value stays as information (the anchor adds 3-8 %).

**Model and solver changes (decisions D-028 ... D-040 in `docs/decisions.md`).**
- *Panels and closures rang for seconds* (beam damping is axial; out-of-plane panel modes had zeta 0.002-0.01): shell
  bending hinges across every interior panel edge (D-032), mass-proportional damping groups per panel, pane, wheel and
  the body structure (D-033), closure lips and stops, seat and mirror mounts (D-034), and relative damping of every
  attached part towards the body's rigid motion until its latch, hinges or clips break (D-038).
- *The parked car rocked fore-aft at 1.0 Hz with zeta 0.07*: decomposing the snapshot showed the wheels rolling on a
  stuck contact patch while the knuckles wound up about the spin axis (wind-up stiffness 7 kN m/rad front, 5 rear;
  real corners 50-300; a 1 g stop wound the knuckles 20-50 deg and the body porpoised at -7 deg pitch). The link
  stiffness is capped by the stability limit, so a wind-up element was added (D-036): a rotational spring-damper about
  the spin axis between the knuckle nodes and the body nodes that carry the suspension, applied as exact pure couples
  (f = (J^-1 tau) x r, zero net force, torque exactly T e). With it the brake hold and the knuckle reaction became pure
  couples too (the old axle-node force balance left a torque normal to the axis), the drive-torque reaction moved from
  the knuckle to the differential, and pick-up mounts stiffen the link pivots (D-035).
- *Body far too soft globally*: a body-in-white style analysis (`tools/p3/body_stiffness.py`) gave torsion 1.1 kN m/deg
  and bending 0.18 kN/mm (real cars ~15-35 and ~10-20); under 1 g braking the front rails drooped 68 mm relative to
  the cabin. 252 rigidifiers (D-040, `tools/skeleton/rigidifier_design.py`) - long invisible cabin and end diagonals
  standing in for the closed-section shell, with crash yield and break limits - and a mass rebalance raise them to
  {torsion} kN m/deg and {bending} kN/mm; the 1 g droop is now 6 mm.
- *Spawn*: the car is built in the unloaded model pose (tires round, springs at the design length), so a spawn on the
  ground dropped and bounced; the settled spawn (D-037) relaxes it to static equilibrium first (about 0.9 s simulated,
  0.3 s wall) with the tire squash, spring length and brake / wind-up / friction preloads in place.
- *Ride and damping*: tire vertical rate measured (292.9 kN/m at 5.7 kN, `tools/skeleton/tire_rate.py`); damper targets
  zeta 0.28 compression / 0.38 rebound (inside the brief's 0.25-0.4) because the tire in series and the blow-off leave
  ~0.6 of the mean in the heave mode; 3 kg of the rear rim moved to the knuckle node carrying the damper to keep S;
  tire carcass hysteresis as a damp group per wheel; anti-roll-bar bushing damping (their 1.7 kg lever tips had a
  220 Hz mode at zeta 0.026).

## Limitations

- The global body stiffness ({torsion} kN m/deg, {bending} kN/mm) is about a third of a real body's torsion and a tenth
  of its bending. At dt = 0.5 ms every beam is capped near m / dt^2 (the exact S < 2.5 of D-024); real values would need
  about 4 kHz (twice the brief's 2 kHz target and two thirds of the CPU at 60 fps). It is visually rigid: about 1 deg of
  twist under a 4 kN m curb couple, 6 mm of front droop under 1 g braking.
- Front knuckle wind-up under a 1 g stop is still about 5 deg relative to the cabin floor (mostly the front structure
  between the cabin and the towers, which the D-040 floor bounds); the cabin dives 3.4 deg peak at 0.95 g (springs
  1.4 / 1.55 Hz, no anti-dive geometry). P3b compares braking dive with the targets.
- The drop criterion (4 s for every node below 1 cm/s) is derived from the design damping (D-039), not given by the
  brief; the brief's "settles within 1 s" applies to the car at rest, which settles immediately.

## Per-test results
"""


def main():
    vr = json.loads((ROOT / "docs/p3/validation/validation_results.json").read_text(encoding="utf-8"))
    bs = json.loads((ROOT / "docs/p3/body_stiffness.json").read_text(encoding="utf-8"))
    tests = vr["tests"]
    passed = sum(t["pass"] for t in tests)
    out = [NARRATIVE.format(passed=passed, total=len(tests), time=vr["time_utc"],
                            torsion=f"{bs['torsion_kNm_per_deg']:.1f}", bending=f"{bs['bending_kN_per_mm']:.2f}")]
    for t in tests:
        out.append(f"### {t['id']}: {t['title']} - {'PASS' if t['pass'] else 'FAIL'} ({t['seconds']:.1f} s)\n")
        out.append("| Check | Value | Unit | Limit | Result |")
        out.append("|---|---|---|---|---|")
        for c in t["checks"]:
            res = "info" if c["info"] else ("PASS" if c["pass"] else "FAIL")
            out.append(f"| {c['name'].replace('|', '/')} | {fmt(c['value'])} | {c['unit']} | "
                       f"{str(c['limit']).replace('|', '/')} | {res} |")
        files = t.get("files") or []
        if files:
            out.append("")
            out.append("Time series: " + ", ".join(f"`docs/p3/validation/{f}`" for f in files))
        if t.get("notes"):
            out.append("")
            out.append("<details><summary>notes</summary>\n")
            out += [f"- {n}" for n in t["notes"]]
            out.append("\n</details>")
        out.append("")
    (ROOT / "docs/validation_report.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote docs/validation_report.md ({passed}/{len(tests)} PASS)")


if __name__ == "__main__":
    main()
