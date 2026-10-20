"""One-off (P4b close): appends the P4b row to docs/changelog.md from the gate and the drive test."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
g = json.loads((ROOT / "docs/gates/gate_p4b.json").read_text(encoding="utf-8"))
d = json.loads((ROOT / "docs/p4b/drive/drive_test.json").read_text(encoding="utf-8"))
row = (
    "| P4b | 2026-10-14 | P4b | Game layer, drivable sandbox `Builds/P4b_Drive/HellcatDrive.exe` (scene P4b_Drive): input with ABS / TC "
    "(read before the solver steps), chase / bumper / cockpit / free cameras (D-071), live cockpit with needles, steering wheel, "
    "pedals and three mirrors (D-072, completes D-021), HUD with energy bars (D-076), node-beam view and overlay, stress and "
    "deformation heat-maps (D-073, UV3 rest positions), reset to the last safe pose / repair in place / teleports at speed "
    "(D-074) with the speed held to the obstacle (D-080), slow motion, pause and step, pause menu, settings.json and F9 params "
    "reload (D-078), synchronous Burst compilation in validation runs (D-079), deterministic record / "
    "replay from a full world snapshot (D-070; test 15 PASS, bit-identical also at 250 fps and from respawns). Wind-up angle "
    f"anchored to the pose (D-069, fixes D-067). G-Drive {g['verdict']} ({g['fails']} fail, {g['warns']} warn): physics "
    f"{d['physics_hz_mean']:.0f} Hz (x{d['realtime_factor']:.3f}), {d['fps_mean']:.0f} fps mean, input latency {d['latency_ms_mean']:.1f} ms, "
    f"5-minute drive {d['distance_km']:.1f} km without divergence, in-game replay bit-identical. `docs/P4b_report.md`, "
    "`docs/controls.md`, capture `docs/p4b/capture/p4b_showcase.mp4`. |"
)
p = ROOT / "docs/changelog.md"
s = p.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
if "| P4b | 2026-10-14 |" in s:
    raise SystemExit("P4b row already present")
p.write_bytes((s + "\n" + row + "\n").encode("utf-8"))
print("changelog: P4b row appended")
