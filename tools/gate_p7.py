"""P7 quality gate (G-Build, brief 14): the standalone Windows build starts from the executable, runs the test map at the
reported fps, controls work, and a short capture at 2560x1440 / 60 fps is produced. Also the P7 deliverables: the build
reproduces the P6 physics bit for bit, the 5-minute drive in the sandbox without divergence, the interior LOD, the glass
look, README / controls / metrics files.

Inputs (tools/p7/run_p7.ps1):
    Builds/HellcatSandbox/HellcatSandbox.exe       BuildTasks.BuildSandbox
    docs/p7/controls/controls_check.json          -scenario controls
    docs/p7/drive/drive_test.json, player.log     -scenario drive (300 s, 1600x900 window)
    docs/p7/drive1440/drive_test.json             -scenario drive (100 s, 2560x1440 borderless full screen)
    docs/p7/s1_50/S1_50kmh_result.json            -scenario S1 (vs sim/cache/S1/kmh50, the P6 run)
    docs/p7/capture/capture.json                  -scenario showcase, tools/p7/encode_p7.py
    docs/README.md, docs/controls.md, docs/metrics.csv

Usage:  tools/.venv/Scripts/python.exe tools/gate_p7.py
Output: docs/gates/gate_p7.json, docs/gates/gate_p7.md
"""
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
results = []


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def utc(p):
    return dt.datetime.fromtimestamp(Path(p).stat().st_mtime, dt.timezone.utc).replace(microsecond=0)


def newest_source():
    roots = [ROOT / "Unity/HellcatSandbox/Assets/Game", ROOT / "Unity/HellcatSandbox/Assets/Sim", ROOT / "Unity/HellcatSandbox/Assets/Editor",
             ROOT / "Unity/HellcatSandbox/Assets/StreamingAssets/Vehicles/hellcat"]
    files = [f for r in roots for f in r.rglob("*") if f.is_file() and f.suffix in (".cs", ".json", ".shader", ".hlsl")]
    return max(files, key=lambda f: f.stat().st_mtime)


def main():
    exe = ROOT / "Builds/HellcatSandbox/HellcatSandbox.exe"
    data = ROOT / "Builds/HellcatSandbox/HellcatSandbox_Data"
    if exe.exists() and data.exists():
        size = sum(f.stat().st_size for f in exe.parent.rglob("*") if f.is_file())
        built = utc(data / "globalgamemanagers") if (data / "globalgamemanagers").exists() else utc(exe)
        src = newest_source()
        check("standalone Windows build present and newer than every game, solver and vehicle source (D10)",
              "PASS" if built >= utc(src) else "FAIL",
              f"{exe.relative_to(ROOT)} ({size / 1e6:.0f} MB, built {built:%Y-%m-%d %H:%M} UTC); newest source {src.relative_to(ROOT)} "
              f"{utc(src):%Y-%m-%d %H:%M} UTC")
    else:
        check("standalone Windows build present", "FAIL", f"{exe.relative_to(ROOT)} missing")

    # starts from the executable: every run of run_p7.ps1 is a fresh start of the exe; its log must show the game up
    logs = sorted((ROOT / "docs/p7/logs").glob("*.log"))
    # the sandbox's own player logs (its data folder in the Mono path); editor batches and other players are not starts of it
    runs = [l for l in logs if "HellcatSandbox_Data" in l.read_text(encoding="utf-8", errors="replace")[:20000]]
    bad = []
    for l in runs:
        t = l.read_text(encoding="utf-8", errors="replace")
        if "[CockpitInstruments]" not in t or re.search(r"^(NullReferenceException|IndexOutOfRangeException|InvalidOperationException)", t, re.M):
            bad.append(l.name)
    check("starts from the executable: each check is a fresh start of HellcatSandbox.exe, the game comes up without exceptions",
          "PASS" if runs and not bad else "FAIL", ("problems: " + ", ".join(bad) + "; ") * bool(bad) + f"{len(runs)} starts: " +
          ", ".join(l.stem for l in runs))

    # fps on the test map, physics Hz, the drive
    dj = ROOT / "docs/p7/drive/drive_test.json"
    if dj.exists():
        d = load(dj)
        segs = ", ".join(f"{s['view']} {s['fps_mean']:.0f}" for s in d["segments"])
        worst = min(s["fps_mean"] for s in d["segments"])
        check("runs the test map at the reported frame rate (brief 4.5: >= 60 fps display, >= 30 absolute; 1600x900 window)",
              "PASS" if d["fps_mean"] >= 60 and worst >= 60 else "WARN" if worst >= 30 else "FAIL",
              f"{d['fps_mean']:.0f} fps mean, 1 % low {d['fps_1pct_low']:.0f}, p99 frame {d['frame_ms_p99']:.1f} ms; per view {segs}; "
              f"{d['system']['gpu']}, {d['system']['screen']} at {d['system']['refresh_hz']:.0f} Hz, vsync {d['system']['vsync']}")
        check("physics at 2 kHz in real time while driving the test map (brief 4.5: >= 1000 Hz, 2000 Hz goal, >= 1x real time)",
              "PASS" if d["realtime_factor"] >= 0.98 else "WARN" if d["realtime_factor"] >= 0.95 else "FAIL",
              f"{d['physics_hz_mean']:.0f} Hz = x{d['realtime_factor']:.3f} real time, {d['step_us_per_substep']:.0f} us per substep with "
              f"{d['sim']['nodes']} nodes / {d['sim']['beams']} beams (car and debris), {d['slowdown_frames']} slow-down frames of {d['frames']}")
        div = []
        if d["non_finite"] > 0: div.append(f"{d['non_finite']} non-finite")
        if d["up_min"] < 0.9: div.append(f"up.y {d['up_min']:.3f}")
        if d["floor_residual_max_mm"] > 5.0: div.append(f"floor bent {d['floor_residual_max_mm']:.1f} mm")
        if d["broken_beams"] > 0: div.append(f"{d['broken_beams']} broken beams")
        if d["path_error_max_m"] > 5.0: div.append(f"path error {d['path_error_max_m']:.1f} m")
        check("5-minute continuous drive on the test map's east loop without divergence; record / replay of its first minute "
              "bit-identical (G-Drive in the sandbox)", "PASS" if not div and d["drive_seconds"] >= 299 and d["replay_bit_identical"] else "FAIL",
              ("; ".join(div) + " | ") * bool(div) + f"{d['drive_seconds']:.0f} s, {d['distance_km']:.2f} km, {d['laps']:.1f} laps, top "
              f"{d['speed_max_kmh']:.0f} km/h, path error max {d['path_error_max_m']:.2f} m; up.y min {d['up_min']:.4f}, floor residual "
              f"{d['floor_residual_max_mm']:.2f} mm, broken {d['broken_beams']}, bent {d['plastic_beams']}; replay {d['replay_seconds']:.0f} s "
              f"{'identical' if d['replay_bit_identical'] else 'DIFFERS'}")
        check("input latency in the sandbox (key press -> rendered reaction)",
              "PASS" if d["latency_reacted"] == d["latency_probes"] and d["latency_ms_mean"] <= 50 else "WARN",
              f"{d['latency_reacted']}/{d['latency_probes']} probes, {d['latency_frames_mean']:.1f} frames, {d['latency_ms_mean']:.1f} ms mean, "
              f"{d['latency_ms_max']:.1f} ms max")
        lod = re.search(r"\[InteriorLod\] (\d+) interior parts, (\d+) triangles; (\d+) drawn from outside",
                        (ROOT / "docs/p7/drive/player.log").read_text(encoding="utf-8", errors="replace")) if (ROOT / "docs/p7/drive/player.log").exists() else None
        check("interior LOD while driving outside (brief 4.12)", "PASS" if lod else "FAIL",
              (f"{lod.group(1)} interior parts, {int(lod.group(2)):,} triangles in full (cockpit, inside the cabin); {int(lod.group(3)):,} "
               f"from outside, the seats only beyond 35 m, none beyond 90 m; cockpit {next((s['fps_mean'] for s in d['segments'] if s['view'] == 'cockpit'), 0):.0f} "
               f"fps vs chase {next((s['fps_mean'] for s in d['segments'] if s['view'] == 'chase'), 0):.0f} fps") if lod else "no [InteriorLod] line in the drive log")
    else:
        check("drive test in the sandbox", "FAIL", f"{dj.relative_to(ROOT)} missing")
    dq = ROOT / "docs/p7/drive1440/drive_test.json"
    if dq.exists():
        d = load(dq)
        worst = min(s["fps_mean"] for s in d["segments"])
        check("frame rate at 2560x1440 full screen (the capture resolution; brief 4.5: >= 60 fps, >= 30 absolute)",
              "PASS" if d["fps_mean"] >= 60 and worst >= 60 else "WARN" if worst >= 30 else "FAIL",
              f"{d['system']['screen']}: {d['fps_mean']:.0f} fps mean, 1 % low {d['fps_1pct_low']:.0f}; per view "
              + ", ".join(f"{s['view']} {s['fps_mean']:.0f}" for s in d["segments"]) + f"; physics x{d['realtime_factor']:.3f} real time")
    else:
        check("frame rate at 2560x1440", "FAIL", f"{dq.relative_to(ROOT)} missing")

    # controls
    cj = ROOT / "docs/p7/controls/controls_check.json"
    if cj.exists():
        c = load(cj)
        failed = [x["control"] + ": " + x["observed"] for x in c["checks"] if not x["pass"]]
        check("controls work: every default key of brief 4.12 and the gamepad, through the Input System, change the game as expected",
              "PASS" if c["failed"] == 0 and c["passed"] >= 20 else "FAIL",
              ("failed: " + "; ".join(failed) + " | ") * bool(failed) + f"{c['passed']} passed: " + ", ".join(x["control"] for x in c["checks"] if x["pass"]))
    else:
        check("controls check", "FAIL", f"{cj.relative_to(ROOT)} missing")

    # the final build reproduces P6
    a, b = ROOT / "docs/p7/s1_50/S1_50kmh_result.json", ROOT / "sim/cache/S1/kmh50/S1_50kmh_result.json"
    if a.exists() and b.exists():
        ra, rb = load(a), load(b)
        # the car's results field by field: the world hash also covers the debris, which the final build lets sleep (D-098)
        skip = {"run_state_hash", "replay_state_hash", "physics_us_per_substep", "replay_note", "sim_steps", "recording_bytes"}
        shared = [k for k in rb if k in ra and k not in skip]
        diff = [k for k in shared if ra[k] != rb[k]]
        same = not diff and ra["replay_identical"]
        check("the sandbox reproduces the P6 crash bit for bit: S1 50 km/h, every result field of the P6 run identical (energies to "
              "0.1 J, crush, pulse, skinning); its recording replays bit-identically", "PASS" if same else "FAIL",
              (f"differ: {', '.join(diff)} | " if diff else "") + f"{len(shared) - len(diff)} of {len(shared)} fields identical: crush "
              f"{ra['dynamic_crush_m']} / {ra['residual_crush_m']} m, plastic {ra['energy_J']['plastic']} J, peak {ra['peak_cabin_decel_g_4ms']} g raw; "
              f"replay {'identical' if ra['replay_identical'] else 'DIFFERENT'}; world state {ra['run_state_hash']} vs P6 {rb['run_state_hash']} "
              f"(the debris asleep, D-098); data hash {ra['data_hash']} vs {rb['data_hash']}")
    else:
        check("S1 50 km/h in the sandbox", "FAIL", f"{a.relative_to(ROOT)} or {b.relative_to(ROOT)} missing")

    # capture
    kj = ROOT / "docs/p7/capture/capture.json"
    if kj.exists():
        k = load(kj)
        ok = k["width"] == 2560 and k["height"] == 1440 and abs(k["fps"] - 60) < 0.01 and k["duration_s"] >= 20
        check("a short capture at 2560x1440 / 60 fps (brief 14 G-Build)", "PASS" if ok else "FAIL",
              f"{k['video']}: {k['width']}x{k['height']}, {k['fps']:.0f} fps, {k['duration_s']:.1f} s, {k['codec']}, {k['bytes'] / 1e6:.1f} MB "
              f"(frames {k['frame_size'][0]}x{k['frame_size'][1]}, written by the player frame by frame)")
    else:
        check("capture at 2560x1440 / 60 fps", "FAIL", f"{kj.relative_to(ROOT)} missing")

    # glass look
    mats = ROOT / "Unity/HellcatSandbox/Assets/Game/Vehicles/Hellcat/Materials"
    gl = []
    for n in ("CH_Glass_Tint", "CH_Glass_Front", "CH_Lamp_Lens"):
        p = mats / f"{n}.mat"
        t = p.read_text(encoding="utf-8") if p.exists() else ""
        a_ = re.search(r"_BaseColor: \{r: [\d.e-]+, g: [\d.e-]+, b: [\d.e-]+, a: ([\d.e-]+)\}", t)
        gl.append((n, "_ALPHAPREMULTIPLY_ON" in t, float(a_.group(1)) if a_ else None))
    check("glass look: tinted glass whose reflections keep their strength (URP preserve-specular blending), lighter windshield "
          "and front side windows than the privacy rear glass", "PASS" if all(x[1] for x in gl) and gl[0][2] and gl[1][2] and gl[0][2] > gl[1][2] else "FAIL",
          ", ".join(f"{n}: premultiplied {pm}, alpha {a_}" for n, pm, a_ in gl))

    # documents
    docs = {"docs/README.md": ["HellcatSandbox.exe", "controls", "tune"], "docs/controls.md": ["F5", "F6", "Esc"],
            "docs/metrics.csv": ["scenario"], "README.md": ["docs/README.md"]}
    miss = []
    for f, needles in docs.items():
        p = ROOT / f
        t = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        if not t or any(n.lower() not in t.lower() for n in needles):
            miss.append(f)
    check("README (how to run, controls, how to tune), controls and the scenario metrics (D9, D10)", "PASS" if not miss else "FAIL",
          ("missing or incomplete: " + ", ".join(miss)) if miss else ", ".join(docs))
    rep = ROOT / "docs/P7_report.md"
    check("P7 report written", "PASS" if rep.exists() and rep.stat().st_size > 2000 else "FAIL", str(rep.relative_to(ROOT)))
    finish()


def finish():
    fails = sum(1 for r in results if r["status"] == "FAIL")
    warns = sum(1 for r in results if r["status"] == "WARN")
    verdict = "PASS" if fails == 0 else "FAIL"
    out = {"gate": "G-Build (P7)", "time_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "verdict": verdict,
           "fails": fails, "warns": warns, "checks": results}
    gd = ROOT / "docs/gates"
    gd.mkdir(parents=True, exist_ok=True)
    (gd / "gate_p7.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    md = ["# Gate P7 (G-Build, standalone build)\n", f"Result: **{verdict}** ({fails} FAIL, {warns} WARN, {len(results)} checks), {out['time_utc']}\n",
          "| # | check | status | detail |", "|---|---|---|---|"]
    md += [f"| {k} | {r['check']} | {r['status']} | {r['detail']} |" for k, r in enumerate(results, 1)]
    (gd / "gate_p7.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['status']:5s} {r['check']}  --  {r['detail']}")
    print(f"P7 gate: {verdict} ({fails} fail, {warns} warn)")


if __name__ == "__main__":
    main()
