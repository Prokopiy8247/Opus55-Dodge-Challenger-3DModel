"""One-off (P3): append decisions D-028 ... D-041 to docs/decisions.md."""
from pathlib import Path

p = Path("docs/decisions.md")
s = p.read_text(encoding="utf-8")
assert "| D-028 |" not in s
rows = [
    ("D-028", "Tire cord pre-tension: at build the beams between cavity nodes get the forces of the linear cavity structure under the spawn pressure load (K u = f on the cavity nodes, t = k n·du; minimum complementary energy), scaled with the group's inflation, so the modelled tire shape is in equilibrium at 241 kPa (residual 2.7e-5 N). Their geometric stiffness counts in the exact S.",
     "Without it the 240-triangle torus inflated into a different shape at spawn and the tread lifted off the ground. The inflated tire is also the realistic one: its rim-to-patch fore-aft stiffness is 517 kN/m with pressure and pre-tension vs 346 kN/m beams only (`tools/p3/tire_tangent.py`)."),
    ("D-029", "Thin contact zone for the tire compound (bias 5 mm instead of the 2.5 cm default of brief 4.4); the hard projection after integration keeps fast nodes out of solids.",
     "A 2.5 cm zone held the tread 2.5 cm above the asphalt at ride height and floated the car; bodies and panels keep 2.5 cm."),
    ("D-030", "Mechanism-free skeleton: anchor beams for nodes with fewer than three independent directions, 3D bumper sections, panel supports, closure seals, dual-layer glass (20 mm sandwich), and 96 braces designed by compliance sensitivity under gravity (`tools/skeleton/brace_design.py`).",
     "The P2 cage sagged ~10 cm and had 34 zero-stiffness mechanisms (`tools/skeleton/mechanisms.py`)."),
    ("D-031", "Mass balancing (`tools/skeleton/mass_balance.py`): per-node weight multipliers (`hcar/hskel_mass_boost.json`) for the cage nodes that dominate the exact modes above the stability target; total mass, centre of mass (cell mass tilt, clip widened to ±0.2 for D-040) and the 57 / 43 split preserved.",
     "Stiff braces and mounts raise S locally; moving cell mass to the nodes that carry them is cheaper than softening them."),
    ("D-032", "Shell bending hinges: a dihedral spring-damper across every interior panel edge, k = D·|e|²/(A1+A2)·0.56 (calibrated against the Kirchhoff simply supported square plate), plastic rest angle (dents), broken with a shared beam, softened (g0/g)² when a panel is crushed; slivers skipped.",
     "Beams carry no bending: panels and glass sagged and rang out of plane with zeta 0.002-0.01."),
    ("D-033", "Deformation damping groups: per panel, pane, wheel (rim + tread: tire carcass hysteresis) and the body structure, F_i = rate·m_i·(v_cm + w x r_i - v_i) towards the group's own rigid motion (momentum and angular momentum conserving, zeta = rate / 2 omega); detachable parts leave the body group when their break group fires.",
     "Mass-proportional damping reaches the low modes that stiffness-proportional beam damping cannot reach without costing stability (2 dt rate per node)."),
    ("D-034", "Closure lips and perimeter stops (hood, deck lid on the cowl / tray lips), seat mounts on floor + tunnel + sill, mirror mounts on the door top.",
     "Closures sank into their openings, and seats and mirrors rang on single soft beams."),
    ("D-035", "Suspension pick-up mounts: every link pivot gets k = 3 beams (`subframe_mount`, 1.1 MN/m) to the nearest structural nodes in diverse directions.",
     "The pivots hung on a few soft beams (knuckle wind-up 3 kN m/rad); softer than first tried because the stiffer mount raised S above 2.5."),
    ("D-036", "Wind-up element per wheel: a rotational spring-damper about the spin axis between the knuckle reaction nodes and the body nodes carrying the suspension (link pivots, their mounts, the spring tower), 200 kN m/rad, 150 / 70 N m s/rad front / rear, strength 15 / 12 kN m, gone when the wheel's links break. Every wheel couple (rim, knuckle, wind-up body set, differential) is applied as f_i = (J^-1 tau) x r_i with the set's full inertia tensor (zero net force, torque exactly tau) and the matching least-squares rates. The drive-torque reaction goes to the differential nodes, not the knuckle. Brake hold 300 / 150 kN m/rad, budgeted with the wind-up on the knuckle inertia; both count in the exact S and in the energy ledger.",
     "Measured wind-up 7 / 5 kN m/rad (real corners 50-300): the parked car rocked at 1.0 Hz and a 1 g stop wound the knuckles 20-50 deg with -7 deg porpoising. A single-anchor torsion bar only reached 14 / 17 kN m/rad, because its reaction is a net force on the knuckle that the links carry; projected radii broke angular momentum (E1 error 1.28, now 8e-5)."),
    ("D-037", "Settled spawn: `SoftBodyWorld.Settle` relaxes a body to static equilibrium on the statics by kinetic damping (velocities zeroed at every kinetic-energy peak; converged when a peak stays below 1 mJ), keeping the model rest lengths, angles and volumes.",
     "The car is modelled in the unloaded pose (round tires, springs at the design length); put on the ground it bounced for ~3 s. A parked spawn must be at rest (brief 10 acceptance): ~0.9 s simulated, 0.3 s wall."),
    ("D-038", "Relative damping of attached parts: a damp group may reference another (closures, bumpers, fenders, roof, quarters, glass, exhaust -> the body; side glass -> its door): F_i = relRate·m_i·(v_ref(x_i) - v_i) towards the reference group's rigid motion, the reaction applied to the reference group as m_j (a + alpha x r_j) (momentum conserving, power -relRate·sum m |dv|²), relRate 15 / 10 1/s, ended by the part's latch / hinge / clip break groups.",
     "A part's own damp group does not damp its rigid motion: after a drop the hood and doors flapped on their hinges with zeta ~0.005."),
    ("D-039", "Validation references: T6 checks the brief's 'settles within 1 s, < 1 cm/s afterwards' on the car at rest (settled spawn) and gives the 0.2 m drop 4 s: every node below 1 cm/s after a 2 m/s impact takes ln(v0 / 0.01) / (zeta omega) ~3.3-3.7 s at the design heave / pitch damping, and 4 s still catches any mode below zeta ~0.15. T7 compares the deceleration with the contact impulse the solver applied (the Coulomb law alone omits the anchor force). T8 counts colliding nodes only and interpolates the slab face.",
     "The brief sets no time for the drop; the earlier 3 s was arbitrary. The T7 / T8 references were errors of the tests themselves (12 % and 7.5 mm)."),
    ("D-040", "Rigidifiers: 252 long invisible beams (1.5 MN/m, yield 25 kN, break 90 kN) through the cabin and between the cabin and its ends, designed by compliance sensitivity on torsion, bending and end-cantilever load cases with a per-node stiffness budget (`tools/skeleton/rigidifier_design.py`): body torsion 1.1 -> 6.4 kN m/deg, bending 0.18 -> 1.75 kN/mm (`tools/p3/body_stiffness.py`), 1 g braking droop 68 -> 6 mm. Gate P3 holds the floor at 5 kN m/deg and 1.5 kN/mm.",
     "The stability bound caps each beam near m / dt², and the open door frames carry no shear: the body was 15-50x softer than a real one. Real values (15-35 kN m/deg) need ~4 kHz (twice the brief's target); the remaining softness (~1 deg twist on a 4 kN m curb couple) is not visible. The crash limits keep the cabin crushable (tuned in P5 / P6)."),
    ("D-041", "Damping retune: damper targets zeta 0.28 compression / 0.38 rebound (brief 0.25-0.4); the measured tire rate 292.9 kN/m in the design tool (supersedes the 300 kN/m assumption of D-025); 3 kg moved from the rear rim to the knuckle node carrying the damper; tire carcass damp groups (rate 12 1/s); anti-roll-bar lever and drop-link bushing damping 250 N s/m.",
     "The heave mode got only ~0.6 of the mean damper ratio (tire in series, blow-off); the rear damper on a 4 kg node limited S; a front-tire tread mode (zeta ~0.005) and the 220 Hz lever-tip mode (zeta 0.026) rang for seconds after a drop."),
]
if not s.endswith("\n"):
    s += "\r\n"
s += "".join(f"| {d} | 2026-10-12 | {a} | {b} |\r\n" for d, a, b in rows)
p.write_text(s, encoding="utf-8")
print("decisions now", s.count("\n| D-"))
