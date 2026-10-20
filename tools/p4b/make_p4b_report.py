"""Writes docs/P4b_report.md (P4b: the game layer, gate G-Drive) from docs/gates/gate_p4b.json, the drive test
docs/p4b/drive/drive_test.json and test 15 docs/p4b/validation/game_results.json. Run tools/gate_p4b.py first, then this.

Usage: tools/.venv/Scripts/python.exe tools/p4b/make_p4b_report.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def main():
    g = load("docs/gates/gate_p4b.json")
    d = load("docs/p4b/drive/drive_test.json")
    gr = load("docs/p4b/validation/game_results.json")
    t15 = next(t for t in gr["tests"] if t["id"] == "T15")
    c15 = {c["name"]: c for c in t15["checks"]}

    def v(name, f="{:.3g}"):
        c = c15.get(name)
        return f.format(c["value"]) if c else "n/a"

    seg = "\n".join(f"| {s['view']} | {s['frames']} | {s['fps_mean']:.0f} | {s['frame_ms_p99']:.1f} | {s['physics_hz']:.0f} | "
                    f"{s['step_us_per_substep']:.0f} | {s['slowdown_frames']} |" for s in d["segments"])
    checks = "\n".join(f"| {k} | {r['check']} | {r['status']} | {r['detail']} |" for k, r in enumerate(g["checks"], 1))
    sysinfo = d["system"]
    lines = [
        "# P4b report: the game layer",
        "",
        f"Gate G-Drive: **{g['verdict']}** ({g['fails']} FAIL, {g['warns']} WARN, {len(g['checks'])} checks, `docs/gates/gate_p4b.md`).",
        "The Hellcat is now a drivable sandbox (`Builds/P4b_Drive/HellcatDrive.exe`, scene `P4b_Drive`), with:",
        "",
        "- keyboard and gamepad input;",
        "- chase, bumper, cockpit and free cameras;",
        "- a live cockpit: needles, steering wheel and pedals driven by the simulation, and three mirrors that show the scene;",
        "- the HUD with energy bars;",
        "- node-beam, stress and deformation views;",
        "- reset, repair and teleports, slow motion, pause and step;",
        "- a pause menu, a settings file and parameter hot reload;",
        "- deterministic record and replay.",
        "",
        "Measured in the player on this machine "
        f"({sysinfo['cpu'].strip()}, {sysinfo['gpu']}, {sysinfo['screen']} window at {sysinfo['refresh_hz']:.0f} Hz, vsync on):",
        "",
        f"- **Physics:** {d['physics_hz_mean']:.0f} Hz, x{d['realtime_factor']:.3f} real time.",
        f"- **Display:** {d['fps_mean']:.0f} fps mean, 1 % low {d['fps_1pct_low']:.0f} fps.",
        f"- **Input latency:** {d['latency_ms_mean']:.1f} ms mean, from key press to the rendered reaction ({d['latency_frames_mean']:.1f} frames).",
        f"- **5-minute drive:** {d['drive_seconds']:.0f} s, {d['distance_km']:.1f} km, {d['laps']:.0f} laps, without divergence.",
        f"- **In-game replay:** the replay of the first {d['replay_seconds']:.0f} s is bit-identical.",
        "",
        "Test 15 (record and replay determinism) passes.",
        "Decisions D-070 ... D-080 are in `docs/decisions.md`; the controls are in `docs/controls.md`.",
        "",
        "## What was built",
        "",
        "- **Input** (`LiveDriverInput`, Unity Input System).",
        "  - Keys: W / S / A / D / Space / Q / E, the arrows, gamepad triggers, stick and shoulders.",
        "  - It reads before the solver steps, so a key drives the same frame (D-075).",
        "  - ABS and traction control are on by default (F7 / F8).",
        "- **Cameras** (`CameraRig`, D-071).",
        "  - Chase camera: constant distance at any speed, with a lagging heading.",
        "  - Bumper camera: just ahead of the fascia.",
        "  - Cockpit camera: at the driver's eye, riding on the cabin nodes with a best-fit rotation, 85 deg horizontal field of view.",
        "  - Free camera.",
        "- **Live cockpit** (`CockpitInstruments`, D-072, completes D-021).",
        "  - Tach and speedometer needles, steering wheel (1.3 turns each way) and pedals follow the simulation.",
        "  - They are drawn as rigid copies of their meshes that ride on the dash nodes and turn about their cockpit.json pivots.",
        "  - The interior and both side mirrors show the scene through render textures, rendered only in the cockpit view.",
        "- **HUD** (`Hud`, D-076).",
        "  - Speed, rpm, gear, pedals, steering, G, broken and bent beams, ABS / TC.",
        "  - Energy bars: kinetic, elastic, plastic work, breaking + damping.",
        "  - Physics Hz, fps, step time, quality mode and the slow-down flag.",
        "  - Camera, time scale, pause, recording / replay state and messages. F1 hides it.",
        "- **Debug views** (`SkeletonDebugView`, `DebugViews`, D-073).",
        "  - N: node-beam view. Shift+N: x-ray overlay.",
        "  - H: beam stress heat-map.",
        "  - Shift+H: deformation heat-map on the visual mesh (UV3 rest positions against the cabin floor's rigid frame).",
        "- **Reset, repair and teleport** (`GameControls`, `SimRunner.RespawnSettled`, D-074).",
        "  - R: the last safe pose.",
        "  - Shift+R: repair in place, moved clear of obstacles.",
        "  - Pause-menu teleports to spawn points; obstacle spawns stand 60 m before the face, at a chosen speed.",
        "  - The speed is held on the lane and the pedals are released 1 m before the obstacle, so the car arrives at V (D-080).",
        "  - Slow motion x0.1 (T), pause and one-frame step (P / Shift+P), screenshots (F12).",
        "- **Record and replay** (`WorldState`, `InputRecording`, `ReplayController`, D-070).",
        "  - F5: snapshot of the whole world plus per-frame substeps and inputs, saved as `.hrec` + `.csv`.",
        "  - F6: replay. Bit-identical with the recorded partition; per-substep inputs in slow motion.",
        "  - A respawn restarts the collision-grid schedule, so respawn-based recordings (scripted scenarios) replay exactly as well.",
        "- **Pause menu** (Esc, `PauseMenu`): reset / repair, spawn points and obstacle teleports at 0-200 km/h, camera, time scale, views, aids, recordings, settings.",
        "- **Settings and tuning** (`GameSettings`, D-078).",
        "  - `settings.json` next to the executable.",
        "  - F9 reloads `params.json` / `geometry.json` and rebuilds the world without restarting (the brief's bonus).",
        "- **Drive scene** (`DriveSceneBuilder`, `BuildTasks.BuildDrive`).",
        "  - A 1 km asphalt square with the drive-test loop.",
        "  - Four demo obstacles, each with an approach spawn: O1 wall, O2 pole, O3 40 % offset block, O4 ramp (P5 replaces them with the test map).",
        "- **G-Drive test** (`DriveTest`, `-scenario drive`, D-077) and the short capture (`ShowcaseCapture`, `-scenario showcase`).",
        "",
        "## G-Drive: measured numbers",
        "",
        "| quantity | value |",
        "|---|---|",
        f"| simulated drive | {d['drive_seconds']:.1f} s, {d['distance_km']:.2f} km, {d['laps']:.1f} laps of the 977 m loop (160 km/h straights, 75 km/h curves), top speed {d['speed_max_kmh']:.0f} km/h |",
        f"| real time | {d['real_seconds']:.1f} s, {d['frames']} frames |",
        f"| physics | {d['physics_hz_mean']:.0f} Hz mean (x{d['realtime_factor']:.4f} real time), {d['step_us_per_substep']:.0f} us per 0.5 ms substep, {d['slowdown_frames']} slow-down frames |",
        f"| display | {d['fps_mean']:.0f} fps mean, median frame {d['frame_ms_p50']:.2f} ms, p99 {d['frame_ms_p99']:.1f} ms (1 % low {d['fps_1pct_low']:.0f} fps), longest {d['frame_ms_max']:.0f} ms (the settled respawn at the start) |",
        f"| input latency | {d['latency_reacted']}/{d['latency_probes']} probes, {d['latency_ms_mean']:.1f} ms mean, {d['latency_ms_max']:.1f} ms max ({d['latency_frames_mean']:.1f} frames mean, {d['latency_frames_max']} max); per probe: {', '.join(str(x) for x in d['latency_list_ms'])} ms |",
        f"| divergence | non-finite {d['non_finite']}, cabin up.y min {d['up_min']:.4f}, cabin floor residual max {d['floor_residual_max_mm']:.2f} mm, broken beams {d['broken_beams']}, bent beams {d['plastic_beams']}, max node speed {d['node_speed_ratio_max']:.2f} x the car's |",
        f"| path (driver robot) | error max {d['path_error_max_m']:.2f} m, rms {d['path_error_rms_m']:.2f} m |",
        f"| in-game replay | {d['replay_seconds']:.1f} s, {d['replay_frames']} frames: end-state hash {d['replay_hash_recorded']} recorded, {d['replay_hash_replayed']} replayed |",
        "",
        "By camera and view (60 s each; the first segment includes the start):",
        "",
        "| view | frames | fps mean | p99 frame ms | physics Hz | us per substep | slow-down frames |",
        "|---|---|---|---|---|---|---|",
        seg,
        "",
        "**How latency is measured.** A key-down event (D) is queued on a virtual keyboard through the Input System while the car is at rest. The test waits for the end of each frame, after the GPU skinning, until the front wheel has turned 0.25 deg. The time includes:",
        "",
        "- the Input System update;",
        "- `LiveDriverInput`;",
        "- the solver substeps of the frame;",
        "- the rate-limited steering moving the knuckle nodes;",
        "- the bone update and the render.",
        "",
        "The display then adds up to one refresh interval (5.6 ms at 180 Hz).",
        "",
        "## Test 15: record and replay",
        "",
        "The driver robot drives the settled car through a 3.5 m lane change into a rigid wall at 55 km/h. Each frame has 25-40 substeps (seeded), and the run is recorded from a world snapshot.",
        "",
        "| check | value |",
        "|---|---|",
        f"| recorded run | {v('recorded run: duration / frames')} s, wall at {v('recorded run: speed at the wall', '{:.1f}')} km/h, broken / bent beams at the end {v('recorded run: broken / plastic beams at the end', '{:.0f}')} |",
        f"| snapshot restore reproduces the state | {'yes' if c15.get('snapshot restore reproduces the captured state', {}).get('pass') else 'no'} |",
        f"| replay with the recorded partition: end state bit-identical, path deviation | {'yes' if c15.get('replay, recorded partition: end state bit-identical', {}).get('pass') else 'no'}, {v('replay, recorded partition: largest path deviation')} m |",
        f"| replay at 8 substeps per frame (250 fps capture): path deviation, end state identical | {v('replay at 8 substeps per frame: largest path deviation')} m, {'yes' if c15.get('replay at 8 substeps per frame: end state bit-identical', {}).get('value') == 1 else 'no'} |",
        f"| through a recording file | {'bit-identical' if c15.get('recording file round trip: end state bit-identical', {}).get('pass') else 'different'}, {v('recording file size (gzip, snapshot included)', '{:.2f}')} MB |",
        f"| respawn starts after different histories | settled state {'identical' if c15.get('respawn start after another history: settled state identical', {}).get('pass') else 'different'}, replay {'bit-identical' if c15.get('respawn start after another history: replay bit-identical', {}).get('pass') else 'different'} |",
        f"| world snapshot | {v('world snapshot size', '{:.2f}')} MB raw |",
        "",
        "## Gate checks",
        "",
        "| # | check | status | detail |",
        "|---|---|---|---|",
        checks,
        "",
        "## Captures and files",
        "",
        "- **Short capture:** `docs/p4b/capture/p4b_showcase.mp4`, 1920x1080 at 60 fps, written frame by frame. The sequence:",
        "  1. chase, cockpit and bumper cameras on the loop;",
        "  2. the node-beam overlay with the stress map through a curve;",
        "  3. a teleport to the O1 wall at 64 km/h, recorded, with the impact at x0.1 from the side;",
        "  4. the deformation heat-map around the wreck;",
        "  5. the crash replayed from the driver's seat.",
        "- **Screenshots of every view** in `docs/p4b/drive/` (`drive_*.png`) and the three mirror images (`mirror_*.png`).",
        "- **Drive test:** `docs/p4b/drive/drive_test.json`, `drive_timeseries.csv`, `drive_record.hrec`. Test 15: `docs/p4b/validation/`.",
        "",
        "## Deviations and open points",
        "",
        "- **Bumper camera.** It is positioned in the camera rig (9 cm ahead of the fascia), not in the skeleton's mount, to keep geometry.json and the P4 crash evidence unchanged. A later skeleton export can move the mount.",
        "- **Side mirrors.** The exported side mirror glass is flat and faces straight back. The mirror camera is aimed the way a driver would set the glass (6 deg outboard) instead of reflecting the eye ray about the flat glass.",
        "- **Glass.** The tinted glass shows little reflection in these renders (a view from behind sees the cabin through the rear window almost unobstructed); the material look is for P7 polish.",
        "- **Editor validation runs compile Burst synchronously (D-079).** One test-15 session differed from the others from the first frame (3e-7 m, then 54.59 instead of 54.49 km/h at the wall): the editor had run some substeps of the settle as managed code while the Burst code loaded. Replays inside every session stayed bit-identical, and the shipped player compiles Burst ahead of time.",
        "- **P4 crash series.** It was produced before D-069 (P4b's straight-line fix) and is re-run with P6's scenarios.",
        "- **Demo obstacles.** The four obstacles in the drive scene are stand-ins; P5 builds the brief's test map.",
        "",
    ]
    (ROOT / "docs/P4b_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote docs/P4b_report.md")


if __name__ == "__main__":
    main()
