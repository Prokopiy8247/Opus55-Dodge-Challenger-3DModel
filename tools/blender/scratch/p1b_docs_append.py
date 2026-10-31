"""One-off: append the P1b decisions, changelog row and model notes section."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
p = ROOT / "docs" / "decisions.md"
t = p.read_text(encoding="utf-8").rstrip("\n") + "\n"
t += (
    "| D-020 | 2026-10-11 | Driver eye point (cockpit camera) at z = 1.12 m (H-point 0.49 m, 0.27 m above the floor, torso 25 deg), "
    "x = -0.375 m, y = -0.36 m; horizontal FOV 85 deg (configurable). | The brief says 1.05-1.10 m, the spec research "
    "(SAE J1100 headroom + J941 eyellipse, docs/specs.md section 9) estimates 1.16 +- 0.05 m; 1.12 m lies within the "
    "estimate and keeps the hood scoop visible over the dash. |\n"
    "| D-021 | 2026-10-11 | G-Interior is split: layout, budget, clipping, needle and steering-wheel kinematics are verified in "
    "Blender in P1b; 'mirrors show the scene' and gauges driven by the simulation are verified in the Unity cockpit (P4b). "
    "The layout check is a camera fitted to cockpit landmarks of reference/Interior 2.jpg (solvePnP, RMS < 2 % of the width) "
    "plus a render overlay. | Mirrors need render textures and the live vehicle state, which exist only in the Unity "
    "runtime; the reference photos are not taken from the driver's eye, so a fitted camera is the fair comparison. |\n"
    "| D-022 | 2026-10-11 | Interior built procedurally (numpy lofts / sweeps / lathes, ikit.py) in the car frame; shell-following "
    "trims (headliner, quarter / C-pillar / A-pillar trims) placed by ray casts against the finished exterior; layout "
    "corrected from the fitted photo camera (back-projection of console landmarks); gauge, display and screen faces are "
    "generated textures (tools/textures/make_interior_textures.py). The floor tunnel was narrowed under the seats and the "
    "front subframe rails shortened so seats, console and carpet fit without intersections. | Reproducible, measurable "
    "(audit + photo fit), parts and pivots ready for skinning and animation in Unity; no third-party interior assets. |\n"
)
p.write_text(t, encoding="utf-8")
c = ROOT / "docs" / "changelog.md"
ct = c.read_text(encoding="utf-8").rstrip("\n") + "\n"
ct += ("| P1b | 2026-10-11 | P1b | Interior and cockpit: 35 CH_Int_* parts (162,596 triangles, 26 materials) built by "
       "hcar.interior:build_interior (dash, cluster with needles, flat-bottom SRT wheel, stack with Performance Pages screen, "
       "console waterfall with switch bank and selector, seats with pleats and emboss, rear bench, door cards, ray-cast trims, "
       "headliner, carpet, pedals, belts, mirror, visors, frit); generated interior textures; cockpit.json for Unity; photo "
       "camera fit on reference/Interior 2.jpg (0.89 % RMS); interior audit (no clipping); see-through tinted glass; floor tunnel "
       "narrowed under the seats; G-Interior gate PASS (1 warn: mirrors in P4b). Blender `3DDodgeChallenger_v007.blend`. |\n")
c.write_text(ct, encoding="utf-8")
m = ROOT / "docs" / "model_notes.md"
mt = m.read_text(encoding="utf-8").rstrip("\n") + "\n\n"
mt += """## Interior (P1b, docs/P1b_report.md)
- Collection `Car_Interior`, 35 objects `CH_Int_*` plus `CH_Glass_Frit`, 162,596 triangles. Rebuild with `hcar.interior:build_interior` (~8 s, needs `Car_Visual`).
- Layout tables: `tools/blender/hcar/interior_tables.py`:
  - eye point and H-point (decision D-020);
  - wheel centre and column angle;
  - cluster and pods;
  - stack, screen and start button;
  - console top profile, switch bank, selector and cup holders;
  - pedals, seats and mirror.
- Animated parts and their pivots: steering wheel, two needles, two pedals. Their rest pose is straight / 12 o'clock / released, and `pose_cockpit()` sets test poses. `sim/vehicle/hellcat/cockpit.json` gives the pivots and axes to Unity.
- Assumptions:
  - Buttons and switches are blank shapes.
  - The Hellcat cat-head logo is not drawn: the seat emboss is "SRT HELLCAT" text, and the wheel badge is "SRT".
  - The headliner, door and quarter trims are simplified surfaces 1.2-6 cm inside the body shell.
  - The rear seat narrows beside the wheel houses, whose inner walls come in to |x| = 0.598 m.
"""
m.write_text(mt, encoding="utf-8")
print("ok")
