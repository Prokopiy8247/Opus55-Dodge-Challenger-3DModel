"""One-off (P3b): decisions D-051 ... D-053 (front suspension package, alignment reactions on the body frame, test and
diagnostic procedures of the second T10 / T11 / T14 round)."""
from pathlib import Path

P = Path("docs/decisions.md")
s = P.read_text(encoding="utf-8")

ROWS = [
    ("D-051", "2026-10-13",
     "Front suspension package: the front tie-rod ends 40 mm outboard of the kingpin (`hskel.build_front_suspension`) and the "
     "tie-rod hydro factor 0.20 (inner lock 32.8 deg, outer 28.9 deg, Ackermann +52 %, on-centre ratio 15.3:1); a K-member "
     "(`kmember` material) tying both lower-arm pivots across the car and to the rack housing; the front knuckle beams on "
     "`knuckle_f` at 6 MN/m with the lower ball joint 1.25x heavier inside its group (S keeps 2.409); the front anti-roll-bar "
     "drop links on the lower ball joints, the lever tips at x 0.70, `arb_link` / `arb_lever` 2.5 MN/m, torsion rates 2250 / "
     "825 N m/rad (75 % front share); a front alignment element (D-049 extrapolated) whose camber is the angle between the "
     "axle line and the steering axis (lower to upper ball joint, `WheelDef.kingpin`), 80 kN m/rad, static -0.5 deg, gain -22.9 "
     "deg/m, no toe spring (the toe is the rack's). Tools `tools/p3b/steer_kinematics.py`, `front_struct_study*.py`, "
     "`arb_tune.py`; X18 (skidpad balance variants), X20 (drop variants).",
     "T11 failed anti-Ackermann (inner 31 deg, outer 37.8 deg: the tie-rod end sat 10 mm inboard of the kingpin, so the "
     "steering arms' extensions met in front of the axle), the on-centre ratio 20.9:1 and the speed reduction 42 % off. The "
     "linear tool put the front compliance steer at 1.09 deg/kN and the lateral camber at 0.92 deg/kN - 5-9x a real car: the "
     "energy went into the knuckle (26 %), the subframe (27 %) and the arms (11 %), the lower-arm pivots hanging on the rails "
     "alone and the arms yawing fore-aft (f<0.2 Hz). Fixed: Ackermann +52 %, compliance steer 0.38, camber 0.17 deg/kN "
     "(elastokinematics); the skidpad path error 1.5-2 m -> 0.8-1.0 m, the robot returned to the circle. With the front grip "
     "fixed the car then oversteered from 0.8 g (limit 0.83 g); X18 showed the 75 % front bar share lifts the limit to 0.92 g "
     "and keeps K positive through 0.8 g (K = (road-wheel angle - L/R) / a_y: 3.4 / 3.6 / 3.9 deg/g at 0.5 / 0.7 / 0.8 g) - it "
     "is the balance of the real car's 57 % front axle load. The 20 km/h curb strike then bent the exhaust hangers because the "
     "45 deg curb reached under the body (the pipes run 155 mm up at x 0.22-0.54): it now ends at x 0.55, outside the wheels' "
     "path."),
    ("D-052", "2026-10-13",
     "The alignment elements' reaction goes to the nodes that define the frame they are measured against: the torque Q is "
     "applied as the frame's generalized force, a force pair (Q x bF) / |F| on the front / rear set centroids and "
     "(Q . bF) bU / |R| on the right / left ones, spread evenly over each set's nodes; the damping uses the frame's angular "
     "velocity bF x (v_front - v_rear) / |F| + bF (bU . (v_right - v_left)) / |R| instead of the wheel's own set. The camber of "
     "a steered knuckle is measured as the angle between the axle line and the steering axis, which steering leaves unchanged.",
     "With the reaction on the wheel's own body set (D-049) the work removed from the frame did not equal the energy the "
     "element gained while the body deformed: E1 with damping off drifted 6.2 % (limit 1 %) after the front element was added, "
     "and the 0.2 m drop's tire modes were fed. With the frame reaction E1 drifts 8.9e-6 (damping off) / 1.2e-4 (damping on) "
     "and the drop settles by 5.9 s instead of 6.6 s, the residual being the front suspension's own 30 Hz modes (see D-053)."),
    ("D-053", "2026-10-13",
     "Test and diagnostic procedures of the second round: T10 compares the roll gradient with 2.3 (suspension, D-025) + 0.7 "
     "(tires) = 3.0 deg/g +- 15 %, reports the understeer gradient on the circle and strikes the curb from x 0.55 outboard; "
     "T11 measures the on-centre ratio from the angle at zero input and checks the speed-sensitive reduction on the steering "
     "command (the road-wheel angle is reported: the tires' aligning torque acts on the compliance and makes it fall faster); "
     "T14 drives the slalom at 50 km/h and checks that the car reaches each gate's side with at least half the amplitude, "
     "settles within 0.5 m over the last 2 s and does not slide (slip below 4 deg), the skidpad window needs a body slip below "
     "6 deg as well, and the ramp jump requires the running gear intact (wheels, suspension, steering, subframes: body panels "
     "and lamp mounts may take the landing, scenario S5) with the tires still pressurized. The robot's cross-track integral is "
     "an understeer correction: in curves it changes side with the turn and fades on straights (1 s), on straights a second "
     "integral takes a steady pull. X18 balance variants, X19 robot variants on the slalom, X20 drop variants. The T6 rest "
     "criterion is 5 mm/s for the drop (0.03 mm at 30 Hz: the front suspension's local modes have zeta ~0.005 with viscous "
     "beam damping, and 1 cm/s would have meant 5.9 s).",
     "The stale test artefacts of the first round: the roll criterion ignored the tire compliance (2.3 vs 3.2 measured), the "
     "slalom's 0.8 m path error was the robot's (pure pursuit cuts a 18 m / +-1 m slalom by about 1.0 m; the car itself "
     "follows it with a slip below 0.9 deg), the skidpad window (path error < 1.5 m) never opened because the same robot ran "
     "1.3-2 m wide, the ramp's 15 broken beams were the fascia and lamp mounts meeting the ground on a 13 deg nose-down "
     "landing while the running gear survived, and after the slalom the curve integral pushed the car off the run-out "
     "(0.69 m). The T6 drop's 1 cm/s criterion caught a 0.03 mm vibration (X20: the K-member raised the lower-arm pivot "
     "stiffness 1.6x)."),
]

add = ["| D-051 | 2026-10-13 |"]
lines = []
for num, date, what, why in ROWS:
    lines.append(f"| {num} | {date} | {what} | {why} |")
if not s.endswith("\n"):
    s += "\n"
P.write_text(s + "\n".join(lines) + "\n", encoding="utf-8")
print("appended", len(ROWS), "decisions")
