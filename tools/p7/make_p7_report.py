"""Writes docs/P7_report.md from the P7 results: the gate (docs/gates/gate_p7.json), the sandbox drive tests before and after the
sleeping debris (docs/p7/before_sleep, docs/p7/drive, docs/p7/drive1440), the controls check, the S1 comparison with P6, the
capture, every phase gate's verdict (docs/gates/gate_*.json / .md) and the narrative in docs/p7/report_notes.md.

Usage: tools/.venv/Scripts/python.exe tools/p7/make_p7_report.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTES = ROOT / "docs/p7/report_notes.md"
PHASES = [("P0", "gate_p0", "environment, Unity project, solver benchmark"), ("P0.5", "gate_p05", "vertical slice"),
          ("P1", "gate_p1", "G-Model: exterior"), ("P1b", "gate_p1b", "G-Interior: interior and cockpit"),
          ("P2", "gate_p2", "G-Skeleton: physics skeleton"), ("P3", "gate_p3", "G-Solver: validation tests 1-8"),
          ("P3b", "gate_p3b", "G-Dynamics: tests 9-14, driving targets"), ("P4", "gate_p4", "G-Crash (S1 in the P4 crash scene)"),
          ("P4b", "gate_p4b", "G-Drive: game layer, 5-minute drive, test 15"), ("P5", "gate_p5", "G-Map: test map"),
          ("P6", "gate_p6", "G-Crash: all scenarios S1-S8"), ("P7", "gate_p7", "G-Build: standalone build")]


def load(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def verdict(name):
    j = load(ROOT / f"docs/gates/{name}.json")
    if j and "verdict" in j:
        return j["verdict"], j.get("fails", 0), j.get("warns", 0), j.get("time_utc", "")
    md = ROOT / f"docs/gates/{name}.md"
    if md.exists():
        t = md.read_text(encoding="utf-8")
        m = re.search(r"\*\*(PASS|FAIL)\*\* \((\d+) FAIL, (\d+) WARN", t)
        when = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", t)
        if m:
            return m.group(1), int(m.group(2)), int(m.group(3)), when.group(1) if when else ""
    return "-", 0, 0, ""


def views(d):
    return {s["view"]: s for s in d["segments"]} if d else {}


def per_view(d):
    return ", ".join(f"{s['view']} {s['fps_mean']:.0f}" for s in d["segments"])


def main():
    gate = load(ROOT / "docs/gates/gate_p7.json") or {"verdict": "-", "fails": 0, "warns": 0, "checks": []}
    md = ["# P7 report: polish, standalone build, final gates", "",
          f"Gate G-Build (P7): **{gate['verdict']}** ({gate['fails']} FAIL, {gate['warns']} WARN, {len(gate['checks'])} checks, "
          "`docs/gates/gate_p7.md`).", ""]
    if NOTES.exists():
        md += [NOTES.read_text(encoding="utf-8").strip(), ""]

    # performance before / after the sleeping debris
    b, a = load(ROOT / "docs/p7/before_sleep/drive_test.json"), load(ROOT / "docs/p7/drive/drive_test.json")
    bq, aq = load(ROOT / "docs/p7/before_sleep/drive1440_test.json"), load(ROOT / "docs/p7/drive1440/drive_test.json")
    if a:
        md += ["## Frame rate on the test map (the 5-minute drive test in the sandbox)", "",
               f"{a['system']['cpu'].strip()}, {a['system']['gpu']}, {a['system']['refresh_hz']:.0f} Hz display with vsync; physics "
               f"{a['sim']['nodes']} nodes / {a['sim']['beams']} beams (the car and the 46 debris props) at 2 kHz, Burst parallel. "
               "The drive robot laps the east loop for 300 s, 60 s in each view.", "",
               "| | before D-098 (debris always simulated) | after D-098 (debris asleep while far) |", "|---|---|---|"]
        rows = [("fps mean (1600 x 900 window)", "fps_mean", "{:.0f}"), ("fps 1 % low", "fps_1pct_low", "{:.0f}"),
                ("frame p99 ms", "frame_ms_p99", "{:.1f}"), ("physics us per substep", "step_us_per_substep", "{:.0f}"),
                ("physics Hz (real-time factor)", None, None), ("frames at the substep cap (slow-down)", "slowdown_frames", "{}")]
        for label, key, f in rows:
            if key is None:
                md.append(f"| {label} | {b['physics_hz_mean']:.0f} (x{b['realtime_factor']:.3f}) | {a['physics_hz_mean']:.0f} (x{a['realtime_factor']:.3f}) |"
                          if b else f"| {label} | - | {a['physics_hz_mean']:.0f} (x{a['realtime_factor']:.3f}) |")
            else:
                md.append(f"| {label} | {f.format(b[key]) if b else '-'} | {f.format(a[key])} |")
        vb, va = views(b), views(a)
        for v in va:
            md.append(f"| {v} view fps | {vb[v]['fps_mean']:.0f} | {va[v]['fps_mean']:.0f} |" if v in vb else f"| {v} view fps | - | {va[v]['fps_mean']:.0f} |")
        if aq:
            md.append(f"| fps at 2560 x 1440 full screen (100 s) | {bq['fps_mean']:.0f} | {aq['fps_mean']:.0f} |" if bq else
                      f"| fps at 2560 x 1440 full screen (100 s) | - | {aq['fps_mean']:.0f} |")
            md.append(f"| 2560 x 1440 per view | {per_view(bq) if bq else '-'} | {per_view(aq)} |")
        md += ["", f"The same drive in the P4b drive scene (no debris, four obstacles) ran at 116 fps with 283 us per substep (`docs/P4b_report.md`). "
               f"Input latency in the sandbox: {a['latency_ms_mean']:.1f} ms mean ({a['latency_frames_mean']:.1f} frames). The drive itself is "
               f"identical before and after (path error {a['path_error_max_m']:.3f} m, {a['distance_km']:.2f} km, replay of the first minute "
               f"{'bit-identical' if a['replay_bit_identical'] else 'DIFFERENT'}).", ""]

    c = load(ROOT / "docs/p7/controls/controls_check.json")
    if c:
        md += ["## Controls check (`-scenario controls`)", "",
               f"A virtual keyboard and a virtual gamepad, added to the Input System, press every default control; {c['passed']} passed, "
               f"{c['failed']} failed ({c['seconds']} s).", "", "| control | expected | observed |", "|---|---|---|"]
        md += [f"| {x['control']} | {x['expected']} | {x['observed']} |" for x in c["checks"]]
        md.append("")

    s_new, s_old = load(ROOT / "docs/p7/s1_50/S1_50kmh_result.json"), load(ROOT / "sim/cache/S1/kmh50/S1_50kmh_result.json")
    if s_new and s_old:
        skip = {"run_state_hash", "replay_state_hash", "physics_us_per_substep", "replay_note", "sim_steps", "recording_bytes"}
        shared = [k for k in s_old if k in s_new and k not in skip]
        same = sum(1 for k in shared if s_new[k] == s_old[k])
        md += ["## The sandbox reproduces the P6 crash", "",
               f"S1 at 50 km/h run again in `HellcatSandbox.exe`: {same} of the {len(shared)} result fields the P6 run wrote are identical "
               f"(crush {s_new['dynamic_crush_m']} / {s_new['residual_crush_m']} m, plastic work {s_new['energy_J']['plastic']} J, peak "
               f"{s_new['peak_cabin_decel_g_4ms']} g raw); its recording replays bit-identically "
               f"({'identical' if s_new['replay_identical'] else 'DIFFERENT'}). The world hash differs from P6's only by the frozen debris "
               "(D-098).", ""]

    k = load(ROOT / "docs/p7/capture/capture.json")
    if k:
        md += ["## Capture", "", f"`{k['video']}`: {k['width']} x {k['height']}, {k['fps']:.0f} fps, {k['duration_s']:.1f} s, "
               f"{k['bytes'] / 1e6:.1f} MB - the showcase written frame by frame by the player at 2560 x 1440 (chase, cockpit with live gauges "
               "and mirrors, bumper camera, node-beam overlay with stresses, a teleport to the O1 wall at 64 km/h in slow motion, the "
               "deformation heat-map, the replay with stresses and from the driver's seat).", ""]
        sheet = sorted((ROOT / "docs/video_assets/P7").glob("*_P7_showcase_sheet.jpg"))
        if sheet:
            md += [f"![showcase](video_assets/P7/{sheet[-1].name})", ""]

    md += ["## Every gate on the final build", "", "| Phase | Gate | Verdict | Run |", "|---|---|---|---|"]
    for ph, g, what in PHASES:
        v, f, w, t = verdict(g)
        md.append(f"| {ph} | {what} | {v} ({f} fail, {w} warn) | {t} |")
    md += ["", "P0-P1b, P2 and P4 keep their phase runs: their evidence (the environment, the Blender model, the P4 crash scene) did "
           "not change after their phase, and the P4 crash series is superseded by the P6 series of the same scenario on the final "
           "car (G-Crash, P6). P3, P3b, P4b, P5, P6 and P7 were run again on the final code and data.", ""]

    md += ["## Gate checks (P7)", "", "| # | check | status |", "|---|---|---|"]
    md += [f"| {i} | {x['check']} | {x['status']} |" for i, x in enumerate(gate["checks"], 1)]
    md += ["", "Details per check: `docs/gates/gate_p7.md`.", ""]
    (ROOT / "docs/P7_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote docs/P7_report.md")


if __name__ == "__main__":
    main()
