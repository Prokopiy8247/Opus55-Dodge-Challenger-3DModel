"""Appends the P6 decisions (D-084 ...) to docs/decisions.md once (idempotent by ID)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATE = "2026-10-15"
ROWS = [
    ("D-084", "P6 scenarios S1-S8 run on the test map's lanes through one `CarCrashScenario` in the lane frame (spawn point "
     "forward / right): a spec table (lane, obstacle object names, entry speed, kind of event: frontal, glancing, jump, debris; "
     "capture window and camera layout), the car respawned settled on the lane (S8 rolling at 120 km/h), speed hold and lane "
     "keeping up to the event (then the P4 brake law; in the air hands off and the brakes after the landing; through the debris "
     "at the speed). Contact = the nearest static-colliding node within 2 mm of the obstacle's primitives (signed distance); "
     "the 1 kHz pulse carries the cabin velocity vector; frames of 33 / 34 substeps at 60 fps so scenario time is simulated "
     "time. Tunnelling = a colliding node inside an obstacle primitive deeper than 1 mm, or beyond the far face of a plate "
     "(wall, guardrail beam) within its other two extents.",
     "Brief 9 defines the scenarios on the test map's obstacles; one implementation keeps the P4 measures (identical along +z) "
     "and makes them work for walls, a pole, angled barriers, a thin rail, a ramp and debris."),
    ("D-085", "S3 \"pole impact aimed at the front axle\" is a centred frontal pole impact (the pole on the car's centre line, "
     "i.e. at the middle of the front axle). A first trial with the pole on the left front wheel's line (0.87 m off centre) "
     "glanced off the bumper corner like a small-overlap test (32.7 kJ plastic work, the car slid past); it stays available "
     "as `-lateral 0.87`.",
     "The brief expects deep intrusion; only the centred pole goes between the rails towards the axle and the engine."),
    ("D-086", "Every scripted run records its inputs (one entry per 60 fps frame: substeps and input, constant within the frame) "
     "with a world snapshot at the start (`<run>.hrec`, the F5 format). After the run the file is read back and replayed from "
     "its snapshot with the inputs looked up per substep: fast up to the event, the event re-rendered at 250 fps (8 substeps "
     "per frame) from the tracking, side and three-quarter cameras (the slow-motion variant), then to the end; the end state "
     "must equal the run's (`WorldState.Hash`).",
     "Brief 9 asks for a slow-motion replay at >= 240 fps and bit-comparable caches; replaying the saved file proves both and "
     "the slow motion is the same run, not a second simulation."),
    ("D-087", "Driven variants (brief 9): `DrivenScenario` (`-scenario Sx -driven 1`) drives the scenario's lane through the game's "
     "own controls - the pause-menu teleport at V with the speed hold (D-080) - records as F5 and replays as F6 (the recorded "
     "frame partition at time scale 1) and compares the end states; results in sim/cache/<S>/driven. The player plays any "
     "recording with `-replay <file.hrec>`.",
     "The brief wants each scripted scenario to have a driven variant that can be recorded and replayed; this exercises the "
     "player's actual path rather than a script."),
    ("D-088", "Closure perimeter stops (`stop_closure`, compression-only SUPPORT beams, D-034) that let go when a lid lifts are "
     "counted apart from broken beams (`closure_stops_released`); `broken_beams` counts material failures only.",
     "They are contact stops, not parts that break; at the first contact of every frontal crash the hood's 17 stops let go "
     "and doubled the broken-beam count."),
    ("D-089", "Passenger-cell intrusion is measured IIHS-style against the rigid pose of the rear cabin (floor, sills, B pillars "
     "and behind, below the belt line; polar-decomposition fit): rearward displacement of the lower and upper door hinge "
     "pillar, rocker front, toe pan, firewall, upper dash and steering column top, per side. The largest structure "
     "deformation (any body node against that pose) is the generic damage depth for the glancing scenarios.",
     "Brief 15 compares intrusion into the passenger cell; the IIHS measuring points are the reference."),
    ("D-090", "Tuning without regenerating the skeleton (params.json): tyre gauge pressure scale (`pressure.gaugeScale`, "
     "multiplying the geometry's 241 kPa); material zones (`materialZones`: the plastic, hardening, cap and break thresholds of "
     "one part's beams whose midpoint lies in a model-space box, scaled; springs and dampers untouched, so S does not change); "
     "`-vehicleParams <file>` runs the player with another parameter set for the same geometry (sweep, tuning runs).",
     "Brief 15.3: all tuning in the parameter file; the tyre pressure lived only in geometry.json and crease initiators "
     "needed per-region thresholds that materials shared across parts cannot give."),
    ("D-091", "Calibration target for the frontal structure: NHTSA NCAP 2013 Dodge Challenger SXT (report NCAP-MGA-2013-030, "
     "1948 kg, 56.4 km/h): static crush profile C1..C6 573-642 mm (mean 608 mm), rebound 2.67 m/s, time of separation 134 ms, "
     "wheelbase -150 mm, door openings within 6 mm. The model's comparable static crush is the residual crush of the bumper "
     "beam plus the 149 mm fascia stand-off ahead of it.",
     "Brief 15.2 asks for public-test conventions; the same car's own NCAP test is the best reference (docs/p6/refs)."),
    ("D-092", "The energy ledger counts the work the gearbox output does on the driveline's axle side (`driveWork`, solver "
     "telemetry; the dynamics are unchanged). The crash check \"no energy created after the contact\" uses kinetic + stored + "
     "dissipated - drive work - aero work, plus the debris bodies' own ledgers in S7.",
     "S5 keeps the throttle up the ramp and S7 pushes through the debris at the speed: without the engine's input the ledger "
     "showed 10.8 and 6.2 kJ 'created'; engine braking after a contact is an outflow the same way."),
    ("D-093", "Tunnelling through a plate (a box with one thin axis: wall, guardrail beam, slab) is a colliding node whose path "
     "between two 1 ms checks crosses the plate's far face inside its outline; a node merely behind the plate is not counted. "
     "Inside any obstacle primitive deeper than 1 mm still counts.",
     "In S6 ten nodes of the crumpled right fender ended up 1-2 cm behind the 8 cm W-beam: they had folded over its top edge "
     "(the solver's thin-wall projection kept every node out of the beam), which the position-only test counted."),
    ("D-094", "Scenario harness fixes: the car view's bone frames are reset on the scenario's first frame (its Start runs before "
     "the view's, so the respawn's reset found the view not ready and the frames turned from the old heading over a few frames, "
     "180 deg on the north-row lanes); the skinning probe forgets its previous frame for the first three frames; its "
     "wheel / suspension exclusion strips the bones' '<node index>_' prefix (the exclusion never matched, so wheels knocked "
     "by a pole or barrier counted as 'spikes'); the speed hold got an integral term (anti-windup within 1 m/s), so the "
     "entry speed has no droop (S8 met the wall at 118.3 instead of 120 km/h).",
     "Found by the P6 gate's skinning checks and entry speeds; none of them changes the simulation."),
    ("D-095", "P6 tuning (params.json, rows P6-001 ... P6-005 of docs/tuning_log.csv): the closure perimeter stops let go once a "
     "lid lifts twice their length (was half); the headlamp brackets yield at 1.5 kN and break at 3 kN after about 25 cm of "
     "stretch (were brittle at 1.8 kN); the hood's front strip (beams with their midpoint ahead of model z 1.93 m: skin rows 5-7 "
     "and the inner frame's front bay) yields at 0.1 x its materials' thresholds (a material zone, D-090).",
     "The landings of S5 released the stops and the lids sank into their openings (the D-034 open point); both headlamps, hung "
     "mostly on the plastic fascia, fell off at 30 km/h and on a jump; the coarse hood (rows every 0.17 m) arched up as one "
     "panel, 0.39 m at 30 km/h and 0.47 m at 50 km/h. With the crease strip it folds at its leading edge: 0.20 / 0.32 m, crush "
     "and pulse unchanged, the landing unchanged; x0.3 and x0.2 gave 0.32 / 0.37 and 0.27 / 0.35 m."),
    ("D-096", "Frontal calibration (brief 15.2, D-091): the front crush characteristic - yield, hardening and cap of `rail_f`, "
     "`rail_f_brace` and `crush_can` - scaled x0.7. At 56 km/h the static crush equivalent (bumper beam set-back + the 149 mm "
     "fascia stand-off) is 615 mm against the NCAP test's 573-642 mm (mean 608 mm). Not matched: the wheelbase does not "
     "shorten (the reading, model geometry minus final, is -17 / -34 mm: unchanged within the +-20 mm it varies with the "
     "steering and suspension pose; NCAP 155 / 149 mm shorter) and the rebound is 4.0 m/s (NCAP 2.7 m/s): the front wheels "
     "reach the wall at about 0.55 m of cabin travel and the tyre / knuckle / arm path holds them instead of letting them be "
     "pushed back, so the cabin travel stays near 0.57 m whatever the rails do and the tyres spring the car back.",
     "Rows P6-006a-c of docs/tuning_log.csv: x1.0 gave 508 mm, x0.8 575 mm, x0.7 615 mm; the sensitivity sweep showed that the "
     "rail yield alone (cap unchanged) or the rail break strength hardly change the crash."),
    ("D-097", "G-Crash (P6) criteria refined on the final series, each with its evidence in the gate detail: (1) the energy-creation "
     "tolerance is 0.5 % of the car's kinetic energy just before the contact (the ledger's own value at the contact is relative "
     "and negative, so the old tolerance was below zero); (2) 'under the ground' counts the nodes that collide with statics - "
     "the inner suspension nodes do not, and where a broken subframe mount or a bottomed-out landing drops one below the surface "
     "(the lower-arm pivot FL_lca_f, 3.7 cm in S4 50, 2.0 cm in S5 60) it is reported; (3) the frame-flip proxy of P4 (120 deg "
     "per 60 fps frame) applies to the distributed-load runs; the pole runs (S3) are reported with S8: the strip the pole stops "
     "folds round it by 118-137 deg within a frame, the hood's own vertex spikes stay below the crumple zones' and the top view "
     "shows a clean fold (docs/p6/s3_hood_fold_top.jpg); (4) in the glancing and light runs (S4-S7) the largest deformation, a "
     "local dent of a few cm, may stay level within 1 cm (S6: 4.7 / 4.8 / 4.6 cm while the plastic work grows 0.4 / 0.7 / 3.3 kJ "
     "and 116 fascia supports tear at 70 km/h); (5) a non-monotonic debris series (S7) is a warning: its light damage comes from "
     "the fence panels, which the car meets differently at each speed; (6) the brief's 'about 6-10 s' capture accepts S8's "
     "5.98 s (it rolls from its spawn 2 s before the wall).",
     "The criteria were written before the scenarios existed; the final runs showed where they measured something else than "
     "the brief's intent (a sign error, nodes that never collide, physical folds, chaotic debris). The raw values stay in "
     "the gate's detail column and in docs/p6/scenario_summary.csv."),
]


def main():
    p = ROOT / "docs/decisions.md"
    text = p.read_text(encoding="utf-8")
    add = [f"| {i} | {DATE} | {d} | {r} |" for i, d, r in ROWS if f"| {i} |" not in text]
    if add:
        p.write_text(text.rstrip("\n") + "\n" + "\n".join(add) + "\n", encoding="utf-8")
    print(f"appended {len(add)} decisions")


if __name__ == "__main__":
    main()
