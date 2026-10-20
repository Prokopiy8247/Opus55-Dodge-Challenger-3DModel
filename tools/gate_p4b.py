"""P4b quality gate (G-Drive, brief 14): the game layer.

G-Drive: measured physics Hz, display fps, input latency (key press -> visible reaction) reported; a 5-minute continuous
drive without divergence. Also the P4b deliverables: test 15 (record / replay determinism), docs/controls.md covering
the brief's default keys, the HUD fields of brief 4.12, the screenshots of every camera and debug view, the live cockpit
(needles, steering wheel, pedals, mirrors: D-021) and the short capture.

Inputs:
    docs/p4b/validation/game_results.json   ValidationTasks.RunGame (T15)
    docs/p4b/drive/drive_test.json          HellcatDrive.exe -scenario drive (DriveTest), screenshots, mirror images
    docs/p4b/drive/player.log               the drive test's player log
    docs/controls.md, docs/p4b/capture/*.mp4

Usage:  tools/.venv/Scripts/python.exe tools/gate_p4b.py
Output: docs/gates/gate_p4b.json, docs/gates/gate_p4b.md
"""
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
results = []

KEYS = ["W", "S", "A / D", "Space", "Q / E", "R", "Shift+R", "C", "T", "N", "H", "P", "F5", "F6"]
HUD_FIELDS = {"speed": r"km/h", "rpm": r"rpm", "gear": r"gear", "throttle": r"throttle", "brake": r"brake",
              "steering": r"steer", "G-force": r"G long", "broken beams": r"broken beams", "energy bars": r"Bar\(\"kinetic\"",
              "simulation Hz": r"physics .* Hz", "fps": r"fps", "quality mode": r"quality:"}


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def mtime(p):
    return dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).replace(microsecond=0)


def newest(paths):
    paths = [p for p in paths if p.exists()]
    p = max(paths, key=lambda q: q.stat().st_mtime)
    return p, mtime(p)


def grade(name, value, ok, warn, detail, higher=True):
    """PASS when value meets ok, WARN when it meets warn, else FAIL (higher or lower is better)."""
    if value is None:
        check(name, "FAIL", detail + " (missing)")
        return
    good = value >= ok if higher else value <= ok
    soft = value >= warn if higher else value <= warn
    check(name, "PASS" if good else "WARN" if soft else "FAIL", detail)


def main():
    sim = list((ROOT / "Unity/HellcatSandbox/Assets/Sim").rglob("*.cs"))
    # the game runtime (the capture script does not run in the drive test)
    game = [q for q in (ROOT / "Unity/HellcatSandbox/Assets/Game").rglob("*.cs") if q.name != "ShowcaseCapture.cs"]
    vd = ROOT / "sim/vehicle/hellcat"
    data = [vd / "geometry.json", vd / "params.json", vd / "cockpit.json"]

    # ---- test 15
    gr = ROOT / "docs/p4b/validation/game_results.json"
    if gr.exists():
        g = json.loads(gr.read_text(encoding="utf-8"))
        t15 = next((t for t in g["tests"] if t["id"] == "T15"), None)
        when = dt.datetime.strptime(g["time_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        src, st = newest(sim + data[:2])
        check("test 15 results newer than the solver sources and the vehicle data", "PASS" if when >= st else "FAIL",
              f"run {g['time_utc']}, newest input {src.relative_to(ROOT)} {st:%Y-%m-%d %H:%M:%S} UTC")
        if t15 is None:
            check("test 15 record / replay", "FAIL", "T15 missing from game_results.json")
        else:
            bad = [c["name"] for c in t15["checks"] if not c["pass"] and not c["info"]]
            byname = {c["name"]: c["value"] for c in t15["checks"]}
            dev = byname.get("replay at 8 substeps per frame: largest path deviation")
            check("test 15 record / replay (snapshot, partition, file, respawn)", "PASS" if t15["pass"] else "FAIL",
                  f"{len(t15['checks'])} checks, failed: {bad or 'none'}; 250 fps replay deviation {dev} m; "
                  f"recorded run {byname.get('recorded run: duration / frames', 0):.1f} s with a crash at {byname.get('recorded run: speed at the wall', 0):.1f} km/h")
    else:
        check("test 15 record / replay", "FAIL", f"{gr.relative_to(ROOT)} missing (ValidationTasks.RunGame)")

    # ---- the drive test
    dj = ROOT / "docs/p4b/drive/drive_test.json"
    if not dj.exists():
        check("G-Drive drive test", "FAIL", f"{dj.relative_to(ROOT)} missing (HellcatDrive.exe -scenario drive)")
        return finish()
    d = json.loads(dj.read_text(encoding="utf-8"))
    when = dt.datetime.strptime(d["time_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    src, st = newest(sim + game + data)
    check("drive test newer than the solver, game sources and vehicle data", "PASS" if when >= st else "FAIL",
          f"run {d['time_utc']}, newest input {src.relative_to(ROOT)} {st:%Y-%m-%d %H:%M:%S} UTC")
    check("drive test in the player build (not the editor)", "PASS" if not d["system"]["editor"] else "WARN",
          f"{d['system']['cpu'].strip()}, {d['system']['threads']} threads, {d['system']['gpu']}, {d['system']['screen']} at "
          f"{d['system']['refresh_hz']} Hz, vsync {d['system']['vsync']}")
    grade("5-minute continuous drive", d["drive_seconds"], 300.0, 240.0,
          f"{d['drive_seconds']:.1f} s simulated, {d['real_seconds']:.1f} s real, {d['distance_km']:.2f} km, {d['laps']:.1f} laps of the 977 m loop")
    grade("physics Hz measured (target 2000 Hz in real time)", d["realtime_factor"], 0.98, 0.95,
          f"{d['physics_hz_mean']:.0f} Hz mean = x{d['realtime_factor']:.3f} real time, {d['step_us_per_substep']:.0f} us per substep, "
          f"{d['slowdown_frames']} slow-down frames of {d['frames']}")
    grade("display fps measured", d["fps_mean"], 60.0, 30.0,
          f"{d['fps_mean']:.0f} fps mean, 1 % low {d['fps_1pct_low']:.0f} fps (p99 frame {d['frame_ms_p99']:.1f} ms, max {d['frame_ms_max']:.0f} ms); "
          + ", ".join(f"{s['view']} {s['fps_mean']:.0f}" for s in d["segments"]))
    worst_view = min(d["segments"], key=lambda s: s["fps_mean"]) if d["segments"] else None
    if worst_view:
        grade("every camera and view at 60 fps or more", worst_view["fps_mean"], 60.0, 30.0,
              f"slowest: {worst_view['view']} {worst_view['fps_mean']:.0f} fps, {worst_view['physics_hz']:.0f} Hz physics")
    reacted = d["latency_reacted"] == d["latency_probes"] and d["latency_probes"] > 0
    check("input latency measured (key press -> rendered reaction)", "PASS" if reacted and d["latency_ms_mean"] <= 50 else "WARN" if reacted else "FAIL",
          f"{d['latency_reacted']}/{d['latency_probes']} probes reacted; {d['latency_frames_mean']:.1f} frames, "
          f"{d['latency_ms_mean']:.1f} ms mean, {d['latency_ms_max']:.1f} ms max (engine: Input System event -> rendered frame; "
          "the display adds its refresh interval)")
    div = []
    if d["non_finite"] > 0: div.append(f"{d['non_finite']} non-finite values")
    if d["up_min"] < 0.9: div.append(f"roll / pitch: up.y {d['up_min']:.3f}")
    if d["floor_residual_max_mm"] > 5.0: div.append(f"cabin floor bent {d['floor_residual_max_mm']:.1f} mm")
    if d["broken_beams"] > 0: div.append(f"{d['broken_beams']} broken beams")
    if d["node_speed_ratio_max"] > 3.5: div.append(f"node speed {d['node_speed_ratio_max']:.2f} x car speed")
    check("no divergence over the drive", "PASS" if not div else "FAIL",
          f"non-finite {d['non_finite']}, up.y min {d['up_min']:.4f}, floor residual max {d['floor_residual_max_mm']:.2f} mm, "
          f"broken {d['broken_beams']}, bent beams {d['plastic_beams']}, max node speed {d['node_speed_ratio_max']:.2f} x the car's"
          + (f"; problems: {', '.join(div)}" if div else ""))
    grade("no structural creep (bent beams after the drive)", -d["plastic_beams"], 0, -20,
          f"{d['plastic_beams']} beams with a changed rest length after {d['distance_km']:.1f} km of driving")
    grade("the driver robot holds the loop", d["path_error_max_m"], 3.0, 5.0,
          f"path error max {d['path_error_max_m']:.2f} m, rms {d['path_error_rms_m']:.2f} m (after the first 20 s), top speed {d['speed_max_kmh']:.0f} km/h",
          higher=False)
    check("in-game record / replay of the drive bit-identical (F5 / F6 path)", "PASS" if d["replay_bit_identical"] else "FAIL",
          f"{d['replay_seconds']:.1f} s, {d['replay_frames']} frames recorded; end-state hash {d['replay_hash_recorded']} vs replay "
          f"{d['replay_hash_replayed']} ({d['replay_real_seconds']:.1f} s real)")

    log = ROOT / "docs/p4b/drive/player.log"
    if log.exists():
        text = log.read_text(encoding="utf-8", errors="replace")
        exc = len(re.findall(r"Exception", text))
        m = re.search(r"\[CockpitInstruments\] (\d+) moving parts, (\d+) mirrors", text)
        check("player log free of exceptions", "PASS" if exc == 0 else "FAIL", f"{exc} exception lines in player.log")
        check("live cockpit: needles, steering wheel, pedals, mirrors (D-021)", "PASS" if m and int(m.group(1)) >= 5 and int(m.group(2)) >= 3 else "FAIL",
              f"{m.group(1)} moving parts, {m.group(2)} mirrors" if m else "no [CockpitInstruments] line")
    shots = ["drive_1_chase.png", "drive_2_cockpit.png", "drive_3_bumper.png", "drive_4_overlay_stress.png", "drive_5_deformation.png",
             "mirror_CH_Int_Mirror.png", "mirror_CH_Mirror_Glass_L.png", "mirror_CH_Mirror_Glass_R.png"]
    missing = [s for s in shots if not (ROOT / "docs/p4b/drive" / s).exists()]
    check("screenshots of every camera, view and mirror", "PASS" if not missing else "FAIL", f"{len(shots) - len(missing)}/{len(shots)} present"
          + (f"; missing {missing}" if missing else ""))

    # ---- static deliverables
    cm = ROOT / "docs/controls.md"
    if cm.exists():
        text = cm.read_text(encoding="utf-8")
        miss = [k for k in KEYS if f"| {k}" not in text and f" {k} " not in text and f"{k} or" not in text]
        check("docs/controls.md covers the brief's default keys", "PASS" if not miss else "FAIL", f"missing: {miss or 'none'}")
    else:
        check("docs/controls.md covers the brief's default keys", "FAIL", "missing")
    hud = (ROOT / "Unity/HellcatSandbox/Assets/Game/UI/Hud.cs").read_text(encoding="utf-8")
    miss = [k for k, rx in HUD_FIELDS.items() if not re.search(rx, hud)]
    check("HUD fields of brief 4.12 (and energy bars of 16)", "PASS" if not miss else "FAIL", f"missing: {miss or 'none'}")
    caps = sorted((ROOT / "docs/p4b/capture").glob("*.mp4")) if (ROOT / "docs/p4b/capture").exists() else []
    check("short capture", "PASS" if caps else "FAIL", ", ".join(f"{c.name} {c.stat().st_size / 1e6:.1f} MB" for c in caps) or "no MP4 in docs/p4b/capture")
    finish()


def finish():
    fails = sum(1 for r in results if r["status"] == "FAIL")
    warns = sum(1 for r in results if r["status"] == "WARN")
    verdict = "PASS" if fails == 0 else "FAIL"
    out = {"gate": "G-Drive (P4b)", "time_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "verdict": verdict, "fails": fails, "warns": warns, "checks": results}
    gd = ROOT / "docs/gates"
    gd.mkdir(parents=True, exist_ok=True)
    (gd / "gate_p4b.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    md = [f"# Gate P4b (G-Drive)\n", f"Result: **{verdict}** ({fails} FAIL, {warns} WARN, {len(results)} checks), {out['time_utc']}\n",
          "| # | check | status | detail |", "|---|---|---|---|"]
    for k, r in enumerate(results, 1):
        md.append(f"| {k} | {r['check']} | {r['status']} | {r['detail']} |")
    (gd / "gate_p4b.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['status']:5s} {r['check']}  --  {r['detail']}")
    print(f"P4b gate: {verdict} ({fails} fail, {warns} warn)")


if __name__ == "__main__":
    main()
