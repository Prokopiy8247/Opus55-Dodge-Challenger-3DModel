"""Appends the P7 decisions (D-098 ...) to docs/decisions.md once (idempotent by ID)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATE = "2026-10-15"
ROWS = [
    ("D-098", "Sleeping debris: the bodies a scene marks sleepable (`SoftBodyWorld.MarkSleepable`; the test map's 46 props, "
     "added after the car) form the tail of the node and beam arrays. Every 32 substeps, on the world's step counter, the "
     "serial phase compares the tail with the car (`TailSleepPhase`). The tail falls asleep once all its nodes have been slower "
     "than 0.05 m/s for 62 checks in a row (about 1 s) while its bounding box stays more than 12 m from the car's. Asleep, the "
     "beam, contact and node passes skip its elements, so it costs nothing and does not move. It wakes as soon as the car "
     "comes within 8 m, or when Ctrl+R puts the debris back (`WakeTail`). The state is a world array, so snapshots and "
     "replays carry it; the HUD shows it.",
     "In the standalone sandbox the 46 props added a quarter to every substep (358 against 283 us), so physics took 72 % of "
     "real time at 2 kHz. Chase and cockpit views ran at 53-56 fps, below the brief's 60. Asleep they cost almost nothing: "
     "315-318 us per substep, 85-87 fps on average and 73-77 fps or more in every view, with 4-6 instead of 338 frames at the substep "
     "cap. The decision runs on fixed substeps, so every frame partition gives the same result and replays stay "
     "bit-identical. The car's physics does not change: S1 at 50 km/h matches its 124 P6 result fields, from the crush to "
     "the energies to 0.1 J. The world hash differs only by the frozen debris. S7, the only run that meets the debris, was "
     "run again."),
    ("D-099", "Glass look: URP's \"preserve specular lighting\" blending (premultiplied diffuse, full-strength reflections) for "
     "the tinted glass and the lamp lenses; the windshield and the front side windows get their own lighter material "
     "(`CH_Glass_Front`, alpha 0.25: the driver looks out through them) and the rear and quarter windows a privacy tint "
     "(alpha 0.6) - set by `CarImporter` (FBX material remap per glass file), so a re-import keeps it.",
     "With plain alpha blending at the Blender material's alpha 0.3 the glass faded its own reflections and read as holes: "
     "the car looked like a convertible in every render (P4 / P5 / P6 open point)."),
    ("D-100", "A procedural sky (`Skybox/Procedural`, sun disk on the directional light) clears every game camera, the mirror and "
     "capture cameras included (`CameraSky`), and is what the reflection probe and the glass reflect; the ambient light stays "
     "the trilight of P4b.",
     "The flat clear colour gave the paint and the new glass nothing to reflect; one helper keeps the scenario, mirror and "
     "map-check cameras consistent with the main camera."),
    ("D-101", "Interior level of detail (brief 4.12, `InteriorLod`): the full interior (33 parts, 160 k triangles) only from the "
     "cockpit or a camera inside the cabin; from outside the parts seen through the glass (seats, dash, steering wheel, "
     "headliner, pillar and quarter trims, parcel shelf: 98 k triangles); beyond 35 m only the seats, beyond 90 m none. "
     "Switched renderers are not skinned either. Crash scenarios and the map check keep the full interior (their capture "
     "cameras are not the main camera).",
     "Brief 4.12 asks for interior LODs while driving outside; the small parts (switches, needles, pedals, carpet, centre "
     "stack) are invisible through the tinted glass."),
    ("D-102", "The standalone game is `Builds/HellcatSandbox/HellcatSandbox.exe` (`BuildTasks.BuildSandbox`): the test map scene "
     "with the game rig, a minimal start screen (title, main keys, any key to drive; not shown for command-line runs), the "
     "drive test and the showcase capture on a stadium loop in the open east of the map (90 m straights, R 38 m curves at "
     "55 km/h) and a controls check (`-scenario controls`: a virtual keyboard and gamepad through the Input System press "
     "every default control and the game's reaction is checked). G-Build (`tools/gate_p7.py`, `tools/p7/run_p7.ps1`) "
     "measures the frame rate at 1600 x 900 and 2560 x 1440, the 5-minute drive, the controls and the 1440p / 60 fps capture.",
     "Brief 14 G-Build: the executable starts, runs the test map at the reported fps, controls work, a 2560 x 1440 / 60 fps "
     "capture; the P4b drive scene's 977 m loop does not fit on the 300 x 200 m map."),
    ("D-103", "G-Map's curb-and-bump check (30 and 50 km/h over O7) judges the bent beams by material and size: no structural "
     "material broken or bent, and the skin and trim (panels, plastics and their supports) flowing less than 3 mm. The map "
     "check now writes each run's bent beams by material with their largest plastic change of length (`bent_by_material`).",
     "The P5 rule allowed 5 bent beams, but 'bent' counts any plastic change above 0.01 mm. Re-run on the P6 car, the "
     "bump bent 6 / 19 beams, all in the hood's P6 crease strip, at 0.55 mm and 2.4 mm. The new report found the cause "
     "(D-104); with the strip at 0.3 the bump bends none."),
    ("D-104", "The hood crease strip (D-095) yields at 0.3 x its materials' thresholds, not 0.1. Tuning row P7-001 in "
     "docs/tuning_log.csv. The whole P6 series, the glass test and the driven variants were run again with it on the final "
     "build.",
     "The P7 re-run of the validation suite failed T6: after the 0.2 m drop one hood beam had flowed, against the test's "
     "zero. The map check showed the bump bending the same strip (D-103). Thresholds of 70-180 N yield under the hood's "
     "own inertia. At 0.3 and 0.2, T6 keeps every beam elastic; over the bump at 50 km/h, 0.3 bends none and 0.2 bends 5 "
     "(0.57 mm). In P6's tuning 0.3 still cut the hood's arch at 30 / 50 km/h from 0.39 / 0.47 m to 0.32 / 0.37 m (0.1: "
     "0.20 / 0.32 m). The P6 tuning had not re-run the validation suite - it is part of every final gate now."),
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
