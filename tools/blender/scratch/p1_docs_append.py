"""One-off: append the P1 decisions and changelog row (run with the venv python)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
p = ROOT / "docs" / "decisions.md"
t = p.read_text(encoding="utf-8").rstrip("\n") + "\n"
t += (
    "| D-017 | 2026-10-11 | G-Model gate interpretation: the silhouettes are compared numerically with the dimensions.com "
    "drawing of the standard body (side top line, plan, front and rear half widths; the plan comparison excludes the "
    "widebody flares and sills), the widebody parts are judged against the photos (perspective overlay on photo 4 with a "
    "solvePnP camera), and dimensions against docs/specs.md (+-2 %). The side bottom line is informational (WARN) because "
    "the widebody sills differ from the drawing. | No pure side or top photo exists (brief 5.1b known gaps); the drawing is "
    "the only orthographic source and it shows the standard body. |\n"
    "| D-018 | 2026-10-11 | Panel thickness is a live Solidify modifier (body 1.5 mm, bumpers/flares/valance 3 mm, glass "
    "4.5 mm, small trim 0.8 mm, even thickness off); recess back plates (grilles, tail panel) are single-sided and shaded "
    "two-sided. The base meshes stay thin quad shells for skinning. | Even-thickness offset produced spikes at sharp flange "
    "corners; back plates are only visible from the front; keeping the modifier live keeps the skinning source (the shell) "
    "separate from the render thickness. |\n"
    "| D-019 | 2026-10-11 | Mechanics (engine, transmission, subframes, suspension, exhaust, tank, floor) are simplified "
    "proxies positioned from the specs and checked for intersections; they exist for crash visuals (hood torn off, parts "
    "detached) and as anchors for the skeleton's heavy clusters, not as detailed models. | No reference photos of the engine "
    "bay or underbody (brief 5.1b); priority order puts visual extras last. |\n"
)
p.write_text(t, encoding="utf-8")
c = ROOT / "docs" / "changelog.md"
ct = c.read_text(encoding="utf-8").rstrip("\n") + "\n"
ct += ("| P1 | 2026-10-11 | P1 | Procedural exterior of the 2018 Challenger SRT Hellcat Widebody (`tools/blender/hcar/`: "
       "shape, caps, panels, flares, wheels, details, mechanics, assemble, render, gate_model), 128 parts named CH_*, 619k "
       "triangles, 29 materials; G-Model gate PASS (0 fail, 1 warn) with dimensions, silhouette overlays, photo PnP overlay, "
       "exhaustive normal/manifold/intersection audit, panel gaps; renders and turntable in `docs/video_assets/P1/`; "
       "`docs/model_notes.md`, `docs/P1_report.md`; Blender `3DDodgeChallenger_v006.blend`. |\n")
c.write_text(ct, encoding="utf-8")
print("ok")
